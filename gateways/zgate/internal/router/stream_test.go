package router

import (
	"bufio"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"zgate/internal/alias"
)

// messages 桥接用的固定 SSE 片段（Go 双引号字符串，便于拼进别名表 JSON）。
const (
	testSSEA       = "event: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"index\":0,\"delta\":{\"type\":\"text_delta\",\"text\":\"A\"}}\n\n"
	testSSEB       = "event: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"index\":0,\"delta\":{\"type\":\"text_delta\",\"text\":\"B\"}}\n\n"
	testSSEStop    = "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n"
	testRegionBody = "{\"type\":\"error\",\"error\":{\"type\":\"RegionError\",\"message\":\"This model is not available in your country\"}}"
)

// TestBridgeStreamsOnNonTailHop：messages 桥接的「非链尾跳」也必须边收边发。
// 旧实现只让链尾跳流式，于是首跳就能成活的型号被整段缓冲：客户端 TTFB == 总耗时
// （2026-11-06 实测 Claude-Haiku-5.5 ttfb 1.739s == total 1.739s、只有 4 条 data 行）。
func TestBridgeStreamsOnNonTailHop(t *testing.T) {
	release := make(chan struct{})
	head := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(testSSEA))
		w.(http.Flusher).Flush()
		select {
		case <-release:
		case <-time.After(3 * time.Second):
			return
		}
		_, _ = w.Write([]byte(testSSEB))
		_, _ = w.Write([]byte(testSSEStop))
	}))
	defer head.Close()

	var tailMu sync.Mutex
	tailHit := 0
	tail := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tailMu.Lock()
		tailHit++
		tailMu.Unlock()
		w.WriteHeader(500)
	}))
	defer tail.Close()

	mapJSON := "{\"models\":{\"Claude-H\":{\"channel\":\"OC\",\"upstream\":\"claude-x\",\"protocol\":\"messages\"," +
		"\"chain\":[" +
		"{\"upstream\":\"claude-x\",\"base\":\"" + head.URL + "\",\"channel\":\"OC\",\"protocol\":\"messages\",\"price\":0}," +
		"{\"upstream\":\"claude-x\",\"base\":\"" + tail.URL + "\",\"channel\":\"OC\",\"protocol\":\"messages\",\"price\":0}" +
		"]}},\"legacy\":{}}"
	srv, _ := newServer(t, mapJSON, head.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	req, err := http.NewRequest(http.MethodPost, front.URL+"/v1/chat/completions",
		strings.NewReader("{\"model\":\"Claude-H\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":8}"))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("status %d", resp.StatusCode)
	}

	br := bufio.NewReader(resp.Body)
	got := make(chan string, 1)
	go func() {
		line, _ := br.ReadString(10)
		got <- line
	}()
	select {
	case line := <-got:
		if !strings.Contains(line, "data:") {
			t.Fatalf("first line is not a chat SSE chunk: %q", line)
		}
	case <-time.After(1500 * time.Millisecond):
		t.Fatal("首个 chunk 没有在上游生成完之前到达：非链尾跳仍在整段缓冲")
	}
	close(release)
	rest, _ := io.ReadAll(br)
	if !strings.Contains(string(rest), "B") {
		t.Fatalf("second delta missing: %q", string(rest))
	}
	tailMu.Lock()
	n := tailHit
	tailMu.Unlock()
	if n != 0 {
		t.Fatalf("head hop answered 200, tail must not be touched, got %d hits", n)
	}
}

// TestBridgeRegionBlockedFallsBackWithStream：流式上行遇到地区受限 403 时，
// 一个字节都还没写出去，仍必须回落到机场孪生跳并冷却这一跳。
func TestBridgeRegionBlockedFallsBackWithStream(t *testing.T) {
	head := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(403)
		_, _ = w.Write([]byte(testRegionBody))
	}))
	defer head.Close()
	tail := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(testSSEB))
		_, _ = w.Write([]byte(testSSEStop))
	}))
	defer tail.Close()

	mapJSON := "{\"models\":{\"Beam\":{\"channel\":\"OC\",\"upstream\":\"beam-free\",\"protocol\":\"messages\"," +
		"\"chain\":[" +
		"{\"upstream\":\"beam-free\",\"base\":\"" + head.URL + "\",\"channel\":\"OC\",\"protocol\":\"messages\",\"price\":0}," +
		"{\"upstream\":\"beam-free\",\"base\":\"" + tail.URL + "\",\"channel\":\"OC\",\"protocol\":\"messages\",\"price\":0,\"proxy\":\"http://10.0.0.1:7896\"}" +
		"]}},\"legacy\":{}}"
	srv, _ := newServer(t, mapJSON, head.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		"{\"model\":\"Beam\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":8}")
	if resp.StatusCode != 200 {
		t.Fatalf("region 403 should fall back to the twin, got %d %s", resp.StatusCode, raw)
	}
	if !strings.Contains(string(raw), "B") {
		t.Fatalf("twin content missing: %s", raw)
	}
	if !srv.cooling(alias.Hop{Channel: "OC", Upstream: "beam-free"}) {
		t.Fatal("region-blocked hop must be cooled")
	}
}

// TestBridgeNoFallbackAfterStreamStarted：流式响应已经写出 chunk 之后上游断流时，
// 必须原地收口 —— 客户端手里已有半截 SSE，再换下一跳写第二个响应体只会得到一条脏流。
// 今天这层由 bridge 自己兜住（写过 chunk 后一律返回 200，见 bridge.go:279-282），本测试锁的
// 是端到端契约：中途断流只收口、不回落、不追加第二个响应体 —— 谁改任一层都得先过这条。
func TestBridgeNoFallbackAfterStreamStarted(t *testing.T) {
	head := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(testSSEA))
		w.(http.Flusher).Flush()
		// 写出一个 delta 后发 RST 断链：普通 Close 会让客户端看到干净的 EOF（Scanner 不报错），
		// 只有 RST 才能制造真实的「流中途读失败」。
		conn, _, err := w.(http.Hijacker).Hijack()
		if err != nil {
			t.Errorf("hijack: %v", err)
			return
		}
		if tc, ok := conn.(*net.TCPConn); ok {
			_ = tc.SetLinger(0)
		}
		_ = conn.Close()
	}))
	defer head.Close()

	var tailMu sync.Mutex
	tailHit := 0
	tail := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tailMu.Lock()
		tailHit++
		tailMu.Unlock()
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(testSSEB))
		_, _ = w.Write([]byte(testSSEStop))
	}))
	defer tail.Close()

	mapJSON := "{\"models\":{\"Claude-H\":{\"channel\":\"OC\",\"upstream\":\"claude-x\",\"protocol\":\"messages\"," +
		"\"chain\":[" +
		"{\"upstream\":\"claude-x\",\"base\":\"" + head.URL + "\",\"channel\":\"OC\",\"protocol\":\"messages\",\"price\":0}," +
		"{\"upstream\":\"claude-x\",\"base\":\"" + tail.URL + "\",\"channel\":\"OC\",\"protocol\":\"messages\",\"price\":0}" +
		"]}},\"legacy\":{}}"
	srv, _ := newServer(t, mapJSON, head.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		"{\"model\":\"Claude-H\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":8}")
	if resp.StatusCode != 200 {
		t.Fatalf("stream already started, status must stay 200, got %d %s", resp.StatusCode, raw)
	}
	if !strings.Contains(string(raw), "bridge stream error") {
		t.Fatalf("mid-stream failure must be closed in place, got %s", raw)
	}
	tailMu.Lock()
	n := tailHit
	tailMu.Unlock()
	if n != 0 {
		t.Fatalf("stream already written, must not fall back to next hop, tail got %d hits", n)
	}
}
