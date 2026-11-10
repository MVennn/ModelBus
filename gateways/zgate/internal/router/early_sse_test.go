package router

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// 这里钉四件事：
//  1. 等上游响应头的空窗里，先给客户端 200 + text/event-stream 并补心跳；
//  2. 窗口内上游就回话的，状态码一律原样透出（老行为不能被我改坏）；
//  3. 提前交卷之后上游才失败，错误改写成流内 error 事件，而不是裸 502；
//  4. 网关整条链路上真的这么走（不是只有 writer 层对）。

func TestEarlySSEWriterPingsBeforeHeader(t *testing.T) {
	rec := httptest.NewRecorder()
	ew := newEarlySSEWriter(rec)
	ew.start(10*time.Millisecond, 15*time.Millisecond)
	time.Sleep(80 * time.Millisecond)
	ew.finish()

	if rec.Code != http.StatusOK {
		t.Fatalf("提前交卷应为 200，got %d", rec.Code)
	}
	if ct := rec.Header().Get("Content-Type"); !strings.HasPrefix(ct, "text/event-stream") {
		t.Fatalf("Content-Type = %q，应为 text/event-stream", ct)
	}
	if n := strings.Count(rec.Body.String(), ": zgate keepalive"); n < 2 {
		t.Fatalf("心跳至少两条，got %d：%q", n, rec.Body.String())
	}
}

func TestEarlySSEWriterFastPathKeepsStatus(t *testing.T) {
	rec := httptest.NewRecorder()
	ew := newEarlySSEWriter(rec)
	ew.start(200*time.Millisecond, 10*time.Millisecond)
	ew.Header().Set("Content-Type", "application/json; charset=utf-8")
	ew.WriteHeader(http.StatusTooManyRequests)
	_, _ = ew.Write([]byte(`{"error":{"message":"rate limited"}}`))
	ew.finish()

	if rec.Code != http.StatusTooManyRequests {
		t.Fatalf("窗口内回话必须原样透出 429，got %d", rec.Code)
	}
	if strings.Contains(rec.Body.String(), "keepalive") {
		t.Fatalf("窗口内就该结束，不该有心跳：%q", rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "rate limited") {
		t.Fatalf("错误体应原样透出：%q", rec.Body.String())
	}
}

func TestEarlySSEWriterRewritesLateErrorAsEvent(t *testing.T) {
	rec := httptest.NewRecorder()
	ew := newEarlySSEWriter(rec)
	ew.start(10*time.Millisecond, 50*time.Millisecond)
	time.Sleep(40 * time.Millisecond) // 交卷之后上游才失败

	ew.Header().Set("Content-Type", "application/json")
	ew.WriteHeader(http.StatusBadGateway)
	_, _ = ew.Write([]byte(`{"error":{"message":"all 7 hops failed","type":"upstream_error"}}`))
	ew.finish()

	if rec.Code != http.StatusOK {
		t.Fatalf("提前交卷后状态码已定死 200，got %d", rec.Code)
	}
	body := rec.Body.String()
	if !strings.Contains(body, "all 7 hops failed") {
		t.Fatalf("错误 message 应转进流内事件：%q", body)
	}
	if !strings.Contains(body, "data: [DONE]") {
		t.Fatalf("流内错误要收尾：%q", body)
	}
	if strings.Contains(body, `"all 7 hops failed","type"`) && !strings.Contains(body, "data: ") {
		t.Fatalf("不该把裸 JSON 写进 SSE：%q", body)
	}
}

func newEarlyServer(t *testing.T, upstream string, window, ping time.Duration) *Server {
	t.Helper()
	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + upstream + `","protocol":"chat",
		"chain":[{"upstream":"m","base":"` + upstream + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, upstream)
	srv.earlyCommit = window
	srv.earlyPing = ping
	return srv
}

const earlyStreamBody = `{"model":"M","stream":true,"messages":[{"role":"user","content":"hi"}],"max_tokens":8}`

// 网关级：上游 300ms 才给响应头，客户端应在窗口（40ms）后就拿到 200 + event-stream。
func TestGatewayCommitsEarlyThenStreams(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(300 * time.Millisecond)
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "data: {\"choices\":[{\"delta\":{\"content\":\"hi\"}}]}\n\n")
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
	}))
	defer up.Close()

	srv := newEarlyServer(t, up.URL, 40*time.Millisecond, 40*time.Millisecond)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	started := time.Now()
	resp, err := http.Post(front.URL+"/v1/chat/completions", "application/json", strings.NewReader(earlyStreamBody))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if elapsed := time.Since(started); elapsed > 200*time.Millisecond {
		t.Fatalf("响应头应在窗口后立刻到，实测等了 %v", elapsed)
	}
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d", resp.StatusCode)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/event-stream") {
		t.Fatalf("Content-Type = %q", ct)
	}
	raw, _ := io.ReadAll(resp.Body)
	if !strings.Contains(string(raw), `"content":"hi"`) {
		t.Fatalf("上游正文应照常到达：%q", raw)
	}
	if !strings.Contains(string(raw), ": zgate keepalive") {
		t.Fatalf("等头期间应补心跳：%q", raw)
	}
}

// 网关级：上游 300ms 后给 500，客户端拿到的是 200 + 流内 error，而不是裸 502。
func TestGatewayRewritesSlowFailureIntoEvent(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(300 * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, `{"error":{"message":"upstream says no","type":"server_error"}}`)
	}))
	defer up.Close()

	srv := newEarlyServer(t, up.URL, 40*time.Millisecond, 40*time.Millisecond)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, err := http.Post(front.URL+"/v1/chat/completions", "application/json", strings.NewReader(earlyStreamBody))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("提前交卷后不该再回 5xx，got %d", resp.StatusCode)
	}
	raw, _ := io.ReadAll(resp.Body)
	body := string(raw)
	if !strings.Contains(body, `"type":"upstream_error"`) && !strings.Contains(body, "upstream says no") {
		t.Fatalf("失败应改写成流内 error：%q", body)
	}
	if !strings.Contains(body, "data: ") {
		t.Fatalf("流内 error 必须是 SSE 事件：%q", body)
	}
}

// 非流式请求不该被提前交卷影响：它要的是确定的 JSON + 状态码。
func TestNonStreamKeepsRealStatus(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, `{"error":{"message":"upstream says no"}}`)
	}))
	defer up.Close()

	srv := newEarlyServer(t, up.URL, 40*time.Millisecond, 40*time.Millisecond)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode == http.StatusOK {
		t.Fatalf("非流式请求必须回真状态码，got 200: %s", raw)
	}
	if strings.Contains(string(raw), "keepalive") {
		t.Fatalf("非流式不该有心跳：%s", raw)
	}
}
