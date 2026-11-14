package router

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"sync"
	"testing"
)

// 请求号与跳头的对外契约：客户端只凭响应头就能定位这次请求。
func TestRequestIDGeneratedAndEchoed(t *testing.T) {
	cap := &capture{}
	upstream := httptest.NewServer(cap.handler(nil))
	defer upstream.Close()

	srv, _ := newServer(t, `{
		"models":{"W/0.03/DeepSeek-41-Fs":{"channel":"WB","upstream":"global:deepseek-v4.1-flash-sg","base":"`+upstream.URL+`","protocol":"chat","fallbacks":[]}},
		"legacy":{}
	}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	// 没带请求号：网关自己生成 16 位十六进制。
	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"W/0.03/DeepSeek-41-Fs","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("status %d: %s", resp.StatusCode, raw)
	}
	id := resp.Header.Get("X-Zgate-Request-Id")
	if !regexp.MustCompile(`^[0-9a-f]{16}$`).MatchString(id) {
		t.Fatalf("X-Zgate-Request-Id = %q, want 16 hex chars", id)
	}
	if got := resp.Header.Get("X-Zgate-Channel"); got != "WB" {
		t.Fatalf("X-Zgate-Channel = %q, want WB", got)
	}
	if got := resp.Header.Get("X-Zgate-Model"); got != "global:deepseek-v4.1-flash-sg" {
		t.Fatalf("X-Zgate-Model = %q", got)
	}
	if got := resp.Header.Get("X-Zgate-Attempt"); got != "1" {
		t.Fatalf("X-Zgate-Attempt = %q, want 1", got)
	}

	// 带了请求号：原样沿用，方便客户端把自己的 trace id 串起来。
	req, err := http.NewRequest(http.MethodPost, front.URL+"/v1/chat/completions",
		strings.NewReader(`{"model":"W/0.03/DeepSeek-41-Fs","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-Id", "client-trace-42")
	r2, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer r2.Body.Close()
	_, _ = io.ReadAll(r2.Body)
	if got := r2.Header.Get("X-Zgate-Request-Id"); got != "client-trace-42" {
		t.Fatalf("client request id not echoed: %q", got)
	}
}

// 回落一次之后 Attempt 要能看出「这不是第一次打上游」。
func TestRequestIDAttemptCountsHops(t *testing.T) {
	cap := &capture{}
	upstream := httptest.NewServer(cap.handler(func(model string) int {
		if model == "primary" {
			return 503
		}
		return 200
	}))
	defer upstream.Close()

	srv, _ := newServer(t, `{
		"models":{"W/0.00/M":{"channel":"WB","upstream":"primary","base":"`+upstream.URL+`","protocol":"chat","fallbacks":["backup"]}},
		"legacy":{}
	}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"W/0.00/M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("fallback did not recover: %d %s", resp.StatusCode, raw)
	}
	if got := resp.Header.Get("X-Zgate-Attempt"); got != "2" {
		t.Fatalf("X-Zgate-Attempt = %q, want 2", got)
	}
	if got := resp.Header.Get("X-Zgate-Model"); got != "backup" {
		t.Fatalf("X-Zgate-Model = %q, want backup", got)
	}
}

// /health 这类旁路也要带请求号：面板轮询健康时同样能对上日志。
func TestRequestIDOnHealth(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, err := http.Get(front.URL + "/health")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	_, _ = io.ReadAll(resp.Body)
	if resp.Header.Get("X-Zgate-Request-Id") == "" {
		t.Fatal("/health must carry X-Zgate-Request-Id")
	}
}

// 请求号要一路带到上游：上游日志里能对上同一次调用。
func TestRequestIDForwardedUpstream(t *testing.T) {
	var mu sync.Mutex
	var got string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		got = r.Header.Get("X-Request-Id")
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"x","object":"chat.completion","created":1,"model":"m","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`))
	}))
	defer upstream.Close()

	srv, _ := newServer(t, `{"models":{"W/0.00/M":{"channel":"WB","upstream":"u","base":"`+upstream.URL+`","protocol":"chat"}},"legacy":{}}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	req, err := http.NewRequest(http.MethodPost, front.URL+"/v1/chat/completions",
		strings.NewReader(`{"model":"W/0.00/M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Request-Id", "trace-77")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	_, _ = io.ReadAll(resp.Body)

	mu.Lock()
	defer mu.Unlock()
	if got != "trace-77" {
		t.Fatalf("upstream X-Request-Id = %q, want trace-77", got)
	}
}

// 收尾期间要主动告诉客户端「别再复用这条连接」，否则退出瞬间是连接重置而不是干净关闭。
func TestDrainingSetsConnectionClose(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.SetDraining()
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := adminGet(t, front.URL+"/health")
	if resp.StatusCode != 200 {
		t.Fatalf("health status %d: %s", resp.StatusCode, raw)
	}
	// net/http 客户端会把 hop-by-hop 的 Connection 头吃掉，转成 Response.Close。
	if !resp.Close {
		t.Fatalf("draining /health must close the connection (resp.Close=false)")
	}
	var payload struct {
		Draining bool `json:"draining"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		t.Fatalf("health json: %v: %s", err, raw)
	}
	if !payload.Draining {
		t.Fatalf("health must report draining=true: %s", raw)
	}
}
