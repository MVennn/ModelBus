package router

// 本文件测 2026-11-11 第二批「3.8 优先」改动：
//
//   - retry500Once：上游 500 先原地重试一次，再按老行为（透传）处理；
//   - timeoutCooldownSeconds：504 静默超时的冷却可按渠道调，负数 = 不冷却；
//   - /health.hops：每跳 try/ok/busy/e5xx 计数，用来回答「首选跳最近到底行不行」。
//
// 背景：AIS 按次计费，冷却期就是强制降级期；而 /health.race 只覆盖竞速跳，
// 串行链（AIS）过去一行观测都没有。

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"zgate/internal/config"
)

const okChatBody = `{"id":"x","object":"chat.completion","created":1,"model":"m",` +
	`"choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`

// 500 一次后成功：开了 retry500Once 就该在同一跳上重试，客户端拿到 200。
func TestRetry500OnceStaysOnSameHop(t *testing.T) {
	var calls int32
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if atomic.AddInt32(&calls, 1) == 1 {
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = io.WriteString(w, `{"error":{"message":"internal"}}`)
			return
		}
		_, _ = io.WriteString(w, okChatBody)
	}))
	defer up.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + up.URL + `","protocol":"chat",` +
		`"chain":[{"upstream":"m","base":"` + up.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, up.URL)
	srv.Config().ChannelPolicy = map[string]config.ChannelPolicy{"OC": {Retry500Once: true}}
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}]}`)
	if resp.StatusCode != http.StatusOK || !strings.Contains(string(raw), `"content":"ok"`) {
		t.Fatalf("500 应原地重试并成功，got %d: %s", resp.StatusCode, raw)
	}
	if v := atomic.LoadInt32(&calls); v != 2 {
		t.Fatalf("上游应被调用 2 次，got %d", v)
	}
	if got := srv.hops.view(); !hasHop(got, "OC|m|") {
		t.Fatalf("hops 应记下这一跳：%v", got)
	}
}

// 没开开关时行为必须与老版本一致：500 原样透给客户端，只撞上游一次。
func Test500PassesThroughWithoutSwitch(t *testing.T) {
	var calls int32
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&calls, 1)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, `{"error":{"message":"internal"}}`)
	}))
	defer up.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + up.URL + `","protocol":"chat",` +
		`"chain":[{"upstream":"m","base":"` + up.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, up.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, _ := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}]}`)
	if resp.StatusCode != http.StatusInternalServerError {
		t.Fatalf("没开 retry500Once 时 500 应透传，got %d", resp.StatusCode)
	}
	if v := atomic.LoadInt32(&calls); v != 1 {
		t.Fatalf("不该重试，上游调用次数 got %d", v)
	}
}

// /health.hops 要能同时记下「这次成功」和「之前失败过」两类事。
func TestHopsCounters(t *testing.T) {
	var calls int32
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if atomic.AddInt32(&calls, 1) == 1 {
			w.WriteHeader(http.StatusInternalServerError)
			_, _ = io.WriteString(w, `{"error":{"message":"internal"}}`)
			return
		}
		_, _ = io.WriteString(w, okChatBody)
	}))
	defer up.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + up.URL + `","protocol":"chat",` +
		`"chain":[{"upstream":"m","base":"` + up.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, up.URL)
	srv.Config().ChannelPolicy = map[string]config.ChannelPolicy{"OC": {Retry500Once: true}}
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	postJSON(t, front.URL+"/v1/chat/completions", `{"model":"M","messages":[{"role":"user","content":"hi"}]}`)

	var stat map[string]int64
	for k, v := range srv.hops.view() {
		if strings.HasPrefix(k, "OC|m|") {
			stat = v.(map[string]int64)
		}
	}
	if stat == nil {
		t.Fatalf("hops 里没有这一跳：%v", srv.hops.view())
	}
	if stat["try"] != 2 || stat["e5xx"] != 1 || stat["ok"] != 1 {
		t.Fatalf("计数不对：%v", stat)
	}
}

// 504 冷却要能被渠道单独调小，也要能整个关掉。
func TestTimeoutCooldownFor(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	cases := []struct {
		name string
		v    int
		want time.Duration
	}{
		{"缺省沿用 5 分钟", 0, timeoutCooldown},
		{"正数按秒", 20, 20 * time.Second},
		{"负数不冷却", -1, 0},
	}
	for _, c := range cases {
		srv.Config().ChannelPolicy = map[string]config.ChannelPolicy{"GM": {TimeoutCooldownSeconds: c.v}}
		if got := srv.timeoutCooldownFor("GM"); got != c.want {
			t.Fatalf("%s: got %v, want %v", c.name, got, c.want)
		}
	}
}

func hasHop(view map[string]any, prefix string) bool {
	for k := range view {
		if strings.HasPrefix(k, prefix) {
			return true
		}
	}
	return false
}
