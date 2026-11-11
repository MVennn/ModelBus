package router

// 本文件测 2026-11-11 加的「上游语义分类」三条判据：
//
//   - 503 high demand 是「忙」不是「坏」：只跳过这一跳，不按整渠道故障处理；
//   - 400 thinking_level 枚举不合法：剥掉思考参数后同一跳重发一次，不透传 400；
//   - 上游在 finish_reason 之前断流：补一帧 error + [DONE]，别让客户端把半截
//     回答当完整回答存下来。
//
// 这三条都来自实测：catiecli 的 Gemini 链高峰期四跳全回 503（每跳 3-22 秒才回），
// 客户端把 high/max/off 这类档位名直接塞进 Gemini 枚举会拿到 400，长回答跑到一半
// 被上游掐断时客户端只看到 socket 安静关闭。

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

func TestBusyExhausted(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
		want   bool
	}{
		{"catiecli 英文原文", 503, `{"error":{"message":"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.","code":503}}`, true},
		{"客户端中文译文", 503, `{"error":{"message":"此模型当前需求量较大。需求高峰通常是暂时的。请稍后再试。","code":503}}`, true},
		{"529 也算忙", 529, `{"error":{"message":"high demand"}}`, true},
		{"普通 503 不当忙", 503, `{"error":{"message":"upstream connect error"}}`, false},
		{"502 是链路问题", 502, `{"error":{"message":"high demand"}}`, false},
		{"429 是限流", 429, `{"error":{"message":"high demand"}}`, false},
	}
	for _, c := range cases {
		if got := busyExhausted(c.status, []byte(c.body)); got != c.want {
			t.Fatalf("%s: busyExhausted = %v, want %v", c.name, got, c.want)
		}
	}
}

func TestInvalidThinkingParam(t *testing.T) {
	google := `{"error":{"code":400,"message":"Invalid value at 'generation_config.thinking_config.thinking_level' (type.googleapis.com/google.ai.generativelanguage.v1beta.ThinkingConfig.ThinkingLevel), \"BOGUS\"","status":"INVALID_ARGUMENT"}}`
	if !invalidThinkingParam(400, []byte(google)) {
		t.Fatal("Google 原文应判成「思考档位不合法」")
	}
	if !invalidThinkingParam(400, []byte(`{"error":{"message":"unknown field thinkingLevel"}}`)) {
		t.Fatal("thinkingLevel 驼峰写法也要认")
	}
	if invalidThinkingParam(400, []byte(`{"error":{"message":"messages: at least one message is required"}}`)) {
		t.Fatal("普通 400 不该被当成思考档位问题")
	}
	if invalidThinkingParam(503, []byte(google)) {
		t.Fatal("只有 400 才走剥参重发")
	}
}

func TestStripThinkingParams(t *testing.T) {
	body := []byte(`{"model":"m","stream":true,"messages":[{"role":"user","content":"hi"}],"reasoning_effort":"BOGUS",` +
		`"extra_body":{"google":{"thinking_config":{"thinking_budget":4096}},"keep":1}}`)
	out, ok := stripThinkingParams(body)
	if !ok {
		t.Fatal("有思考参数就该报告 changed=true")
	}
	s := string(out)
	for _, gone := range []string{"reasoning_effort", "thinking_config", "BOGUS"} {
		if strings.Contains(s, gone) {
			t.Fatalf("应剥掉 %q：%s", gone, s)
		}
	}
	for _, kept := range []string{`"model":"m"`, `"stream":true`, `"messages"`, `"keep":1`} {
		if !strings.Contains(s, kept) {
			t.Fatalf("不该动 %q：%s", kept, s)
		}
	}
	if _, ok := stripThinkingParams([]byte(`{"model":"m","stream":true}`)); ok {
		t.Fatal("没有思考参数时不该报 changed（重发没有意义）")
	}
}

// 网关级：上游对带 reasoning_effort 的请求回 400（thinking_level 枚举不合法），
// 剥参后同一跳重发必须成功，客户端看到 200 而不是 INVALID_REQUEST。
func TestGatewayRetriesWithoutThinkingParam(t *testing.T) {
	var calls int32
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		atomic.AddInt32(&calls, 1)
		if strings.Contains(string(raw), "reasoning_effort") {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			_, _ = io.WriteString(w, `{"error":{"code":400,"message":"Invalid value at 'generation_config.thinking_config.thinking_level' (type.googleapis.com/google.ai.generativelanguage.v1beta.ThinkingConfig.ThinkingLevel), \"BOGUS\""}}`)
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "data: {\"choices\":[{\"delta\":{\"content\":\"hi\"},\"finish_reason\":\"stop\"}]}\n\ndata: [DONE]\n\n")
	}))
	defer up.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + up.URL + `","protocol":"chat",
		"chain":[{"upstream":"m","base":"` + up.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, up.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","stream":true,"messages":[{"role":"user","content":"hi"}],"reasoning_effort":"BOGUS"}`)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("剥参后应 200，got %d: %s", resp.StatusCode, raw)
	}
	if !strings.Contains(string(raw), `"content":"hi"`) {
		t.Fatalf("应拿到上游正文：%s", raw)
	}
	if got := atomic.LoadInt32(&calls); got != 2 {
		t.Fatalf("上游应被请求两次（400 + 剥参重发），实测 %d", got)
	}
	if v := srv.sem.view()["thinking_strip"].(int64); v != 1 {
		t.Fatalf("/health.upstream.thinking_strip = %d, want 1", v)
	}
}

// 网关级：上游写了一段正文就断流（没有 finish_reason、没有 [DONE]），
// 网关必须补一帧 error + [DONE]，并计入 /health。
func TestGatewayClosesTruncatedStream(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "data: {\"choices\":[{\"delta\":{\"content\":\"half\"},\"finish_reason\":null}]}\n\n")
	}))
	defer up.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + up.URL + `","protocol":"chat",
		"chain":[{"upstream":"m","base":"` + up.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, up.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","stream":true,"messages":[{"role":"user","content":"hi"}]}`)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("status %d: %s", resp.StatusCode, raw)
	}
	body := string(raw)
	if !strings.Contains(body, "upstream_truncated") {
		t.Fatalf("应补一帧 upstream_truncated：%q", body)
	}
	if !strings.HasSuffix(strings.TrimSpace(body), "data: [DONE]") {
		t.Fatalf("收口帧之后必须跟 [DONE]：%q", body)
	}
	if v := srv.sem.view()["truncated_streams"].(int64); v != 1 {
		t.Fatalf("/health.upstream.truncated_streams = %d, want 1", v)
	}
}

// 正常说完的流不该被补帧：[DONE] 或非 null finish_reason 都算说完了。
func TestNormalStreamIsNotPatched(t *testing.T) {
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, "data: {\"choices\":[{\"delta\":{\"content\":\"ok\"},\"finish_reason\":\"stop\"}]}\n\ndata: [DONE]\n\n")
	}))
	defer up.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"m","base":"` + up.URL + `","protocol":"chat",
		"chain":[{"upstream":"m","base":"` + up.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, up.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	if _, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","stream":true,"messages":[{"role":"user","content":"hi"}]}`); strings.Contains(string(raw), "upstream_truncated") {
		t.Fatalf("正常流不该被补帧：%q", raw)
	}
	if v := srv.sem.view()["truncated_streams"].(int64); v != 0 {
		t.Fatalf("正常流不该计数，got %d", v)
	}
}

// 网关级：第一跳 503 high demand，第二跳正常 —— 必须立刻换跳拿到 200，
// 而不是按 5xx 给第一跳埋 60 秒软冷却（更不该整渠道禁用）。
func TestBusyHopIsSkippedNotBanned(t *testing.T) {
	busy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = io.WriteString(w, `{"error":{"message":"This model is currently experiencing high demand.","code":503}}`)
	}))
	defer busy.Close()
	good := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"id":"x","object":"chat.completion","created":1,"model":"g","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`)
	}))
	defer good.Close()

	mapJSON := `{"models":{"M":{"channel":"OC","upstream":"busy","base":"` + busy.URL + `","protocol":"chat","chain":[
		{"upstream":"busy","base":"` + busy.URL + `","channel":"OC","protocol":"chat","price":0.1},
		{"upstream":"good","base":"` + good.URL + `","channel":"OC","protocol":"chat","price":0.1}]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, busy.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","stream":false,"messages":[{"role":"user","content":"hi"}]}`)
	if resp.StatusCode != http.StatusOK || !strings.Contains(string(raw), `"content":"ok"`) {
		t.Fatalf("忙跳应被跳过、第二跳接手，got %d: %s", resp.StatusCode, raw)
	}
	if v := srv.sem.view()["busy"].(int64); v != 1 {
		t.Fatalf("/health.upstream.busy = %d, want 1", v)
	}
}
