package router

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"zgate/internal/config"
)

// sseGuard 把若干条 payload 拼成标准 SSE 流，避免源码里出现反斜杠转义。
func sseGuard(payloads ...string) string {
	var b strings.Builder
	for _, p := range payloads {
		b.WriteString("data: ")
		b.WriteString(p)
		b.WriteByte(10)
		b.WriteByte(10)
	}
	return b.String()
}

// 格式 A：首个有效 delta 就是明文 reasoning_content，宿主能渲染成思考。
func guardPlainSSE() string {
	return sseGuard(
		`{"id":"a","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","reasoning_content":"**"},"finish_reason":null}]}`,
		`{"id":"a","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"reasoning_content":"Considering the task"},"finish_reason":null}]}`,
		`{"id":"a","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"春天来了。"},"finish_reason":"stop"}]}`,
		`[DONE]`,
	)
}

// 格式 B：先吐正文、零明文思考，收尾带加密 reasoning_details。
func guardEncryptedSSE() string {
	return sseGuard(
		`{"id":"b","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"春天是","reasoning":null},"finish_reason":null}]}`,
		`{"id":"b","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"reasoning_details":[{"type":"reasoning.encrypted","data":"o2d2ZXJzaW9u"}]},"finish_reason":"stop"}]}`,
		`[DONE]`,
	)
}

type guardState struct {
	mu       sync.Mutex
	calls    int
	auths    []string
	sessions []string
	closes   []bool
}

func (g *guardState) snapshot() (int, []string, []string) {
	calls, auths, sessions, _ := g.snapshotAll()
	return calls, auths, sessions
}

func (g *guardState) snapshotAll() (int, []string, []string, []bool) {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.calls, append([]string(nil), g.auths...), append([]string(nil), g.sessions...),
		append([]bool(nil), g.closes...)
}

// newGuardFront 起一个第 n 次调用返回 respond(n) 的伪造 opencode 后端，
// 接一条单跳 chat alias，再把 ReasoningGuard 注入运行时配置。
func newGuardFront(t *testing.T, guard config.ReasoningGuard, model, upstreamName string, respond func(n int) string) (*httptest.Server, *guardState) {
	t.Helper()
	st := &guardState{}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		st.mu.Lock()
		st.calls++
		n := st.calls
		st.auths = append(st.auths, r.Header.Get("Authorization"))
		st.sessions = append(st.sessions, r.Header.Get("X-Opencode-Session"))
		st.closes = append(st.closes, r.Close)
		st.mu.Unlock()
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = io.WriteString(w, respond(n))
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
	}))
	t.Cleanup(upstream.Close)

	mapJSON := fmt.Sprintf(`{"models":{"%s":{"channel":"OC","upstream":"%s","base":"%s","protocol":"chat"}}}`, model, upstreamName, upstream.URL)
	srv, _ := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.ReasoningGuard = guard
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)
	return front, st
}

func guardRequest(t *testing.T, front *httptest.Server, body string) string {
	t.Helper()
	resp, raw := postJSON(t, front.URL+"/v1/chat/completions", body)
	if resp.StatusCode != 200 {
		t.Fatalf("前置响应 status %d: %s", resp.StatusCode, raw)
	}
	return string(raw)
}

const guardHighBody = `{"model":"Iceman","messages":[{"role":"user","content":"请用一句话介绍春天。"}],"stream":true,"max_tokens":512,"reasoning_effort":"high"}`

// probeReasoningStream：四种 SSE 形态分别给出正确判定，且缓冲字节一个不少。
func TestProbeReasoningStreamVerdicts(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want streamReasoningVerdict
	}{
		{"明文思考首块", guardPlainSSE(), streamPlaintext},
		{"正文先于思考", guardEncryptedSSE(), streamEncrypted},
		{"加密 detail 兜底", sseGuard(
			`{"choices":[{"delta":{"role":"assistant"}}]}`,
			`{"choices":[{"delta":{"reasoning_details":[{"type":"reasoning.encrypted","data":"x"}]}}]}`,
			`[DONE]`,
		), streamEncrypted},
		{"只有 role 无法判定", sseGuard(
			`{"choices":[{"delta":{"role":"assistant"}}]}`,
			`[DONE]`,
		), streamUndetermined},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, buffered := probeReasoningStream(strings.NewReader(tc.in), 32768)
			if got != tc.want {
				t.Fatalf("verdict = %v, want %v", got, tc.want)
			}
			if string(buffered) != tc.in {
				t.Fatalf("buffered 与原始字节不一致：got %d bytes, want %d bytes", len(buffered), len(tc.in))
			}
		})
	}
}

// 白名单按 rewriteModel 之后的 upstream 名匹配；off/disabled 显式关思考跳过守卫。
func TestReasoningGuardPredicates(t *testing.T) {
	models := []string{"Iceman", "iceman-contributor-free"}
	if !reasoningGuardMatches(models, []byte(`{"model":"ICEMAN-CONTRIBUTOR-FREE"}`)) {
		t.Fatal("upstream 名忽略大小写应该命中白名单")
	}
	if reasoningGuardMatches(models, []byte(`{"model":"beam-free"}`)) {
		t.Fatal("白名单外模型不应该命中")
	}
	if reasoningGuardMatches(nil, []byte(`{"model":"iceman-contributor-free"}`)) {
		t.Fatal("空白名单应该一律不命中")
	}
	expects := []struct {
		body string
		want bool
	}{
		{`{"reasoning_effort":"high"}`, true},
		{`{"reasoning_effort":"low"}`, true},
		{`{"reasoning_effort":"off"}`, false},
		{`{"reasoning_effort":""}`, false},
		{`{"thinking":{"type":"enabled"}}`, true},
		{`{"thinking":{"type":"disabled"}}`, false},
		{`{}`, false},
	}
	for _, tc := range expects {
		if got := reasoningExpectsThinking([]byte(tc.body)); got != tc.want {
			t.Fatalf("reasoningExpectsThinking(%s) = %v, want %v", tc.body, got, tc.want)
		}
	}
}

// 核心回归：第一次命中加密 B 分流 → 丢弃、重抽同一跳 → 客户端只拿到明文 A 思考流。
func TestReasoningGuardRedrawsEncryptedOnlyStream(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, Models: []string{"iceman-contributor-free"},
		MaxRetries: 3, MaxProbeBytes: 32768,
	}
	front, st := newGuardFront(t, guard, "Iceman", "iceman-contributor-free", func(n int) string {
		if n == 1 {
			return guardEncryptedSSE()
		}
		return guardPlainSSE()
	})
	raw := guardRequest(t, front, guardHighBody)
	if !strings.Contains(raw, "reasoning_content") {
		t.Fatalf("客户端没有拿到明文思考流：%s", raw)
	}
	if strings.Contains(raw, "春天是") {
		t.Fatalf("第一次加密响应漏给了客户端：%s", raw)
	}
	calls, auths, sessions, closes := st.snapshotAll()
	if calls != 2 {
		t.Fatalf("期望 2 次上游调用（1 次丢弃 + 1 次放行），got %d", calls)
	}
	for i := 0; i < len(auths); i++ {
		if auths[i] != "Bearer oc-key" {
			t.Fatalf("重抽丢了鉴权头：call %d = %q", i+1, auths[i])
		}
	}
	// 2026-11-10 12:01 的实测根因：重抽沿用同一 keep-alive 连接 + 同一个写死的
	// X-Opencode-Session，3 次重抽全部落回同一路「只回加密思考」的后端。
	if sessions[0] != "test-session" {
		t.Fatalf("首跳应沿用原会话标识，got %q", sessions[0])
	}
	for i := 1; i < len(sessions); i++ {
		if sessions[i] == sessions[0] {
			t.Fatalf("重抽没有换会话：call %d 仍是 %q", i+1, sessions[i])
		}
		if !strings.HasPrefix(sessions[i], "test-session#r") {
			t.Fatalf("重抽会话标识应保留原前缀便于排障，call %d = %q", i+1, sessions[i])
		}
		if !closes[i] {
			t.Fatalf("重抽必须换新连接（req.Close=true），call %d 复用了旧连接", i+1)
		}
	}
}

// 守卫关闭：即使上游返回加密 B，也只调一次、原样放行。
func TestReasoningGuardDisabledPassesThrough(t *testing.T) {
	front, st := newGuardFront(t, config.ReasoningGuard{}, "Iceman", "iceman-contributor-free",
		func(int) string { return guardEncryptedSSE() })
	raw := guardRequest(t, front, guardHighBody)
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("关闭守卫时应原样放行上游字节：%s", raw)
	}
	if calls, _, _ := st.snapshot(); calls != 1 {
		t.Fatalf("守卫关闭时不应重抽，got %d 次上游调用", calls)
	}
}

// 连续加密：达到 MaxRetries 后放行最后一次，避免无限循环。
func TestReasoningGuardMaxRetriesCapsRedraw(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, Models: []string{"iceman-contributor-free"},
		MaxRetries: 2, MaxProbeBytes: 32768,
	}
	front, st := newGuardFront(t, guard, "Iceman", "iceman-contributor-free",
		func(int) string { return guardEncryptedSSE() })
	raw := guardRequest(t, front, guardHighBody)
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("达上限后应放行最后一次响应：%s", raw)
	}
	if calls, _, _ := st.snapshot(); calls != 3 {
		t.Fatalf("MaxRetries=2 期望 3 次上游调用，got %d", calls)
	}
}

// 用户显式关思考（off）：守卫跳过，不重抽。
func TestReasoningGuardSkipsOffEffort(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, Models: []string{"iceman-contributor-free"},
		MaxRetries: 3, MaxProbeBytes: 32768,
	}
	front, st := newGuardFront(t, guard, "Iceman", "iceman-contributor-free",
		func(int) string { return guardEncryptedSSE() })
	raw := guardRequest(t, front, strings.Replace(guardHighBody, `"high"`, `"off"`, 1))
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("off 档位应原样放行：%s", raw)
	}
	if calls, _, _ := st.snapshot(); calls != 1 {
		t.Fatalf("off 档位不应触发重抽，got %d 次", calls)
	}
}

// 白名单外模型：守卫跳过，一次调用原样放行。
func TestReasoningGuardSkipsNonWhitelistedModel(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, Mode: "models", Models: []string{"iceman-contributor-free"},
		MaxRetries: 3, MaxProbeBytes: 32768,
	}
	front, st := newGuardFront(t, guard, "Beam", "beam-free",
		func(int) string { return guardEncryptedSSE() })
	body := strings.Replace(guardHighBody, `"Iceman"`, `"Beam"`, 1)
	raw := guardRequest(t, front, body)
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("白名单外模型应原样放行：%s", raw)
	}
	if calls, _, _ := st.snapshot(); calls != 1 {
		t.Fatalf("白名单外模型不应触发重抽，got %d 次", calls)
	}
}

// auto 模式：配置里不写任何模型名，陌生模型（以后新增的同类匿名代号）也自动守卫。
// 这是「以后同类模型直接适配」的核心承诺 —— 不需要再改 zgate.json 就能用。
func TestReasoningGuardAutoModeCoversUnknownModel(t *testing.T) {
	guard := config.ReasoningGuard{Enabled: true, MaxRetries: 3, MaxProbeBytes: 32768}
	front, st := newGuardFront(t, guard, "Beam", "beam-free", func(n int) string {
		if n == 1 {
			return guardEncryptedSSE()
		}
		return guardPlainSSE()
	})
	body := strings.Replace(guardHighBody, `"Iceman"`, `"Beam"`, 1)
	raw := guardRequest(t, front, body)
	if !strings.Contains(raw, "reasoning_content") {
		t.Fatalf("auto 模式下陌生模型也应重抽拿到明文思考：%s", raw)
	}
	if strings.Contains(raw, "春天是") {
		t.Fatalf("加密首跳漏给了客户端：%s", raw)
	}
	if calls, _, _ := st.snapshot(); calls != 2 {
		t.Fatalf("auto 模式应重抽一次，got %d 次上游调用", calls)
	}
}

// 达上限放行时要注入可读提示：否则宿主只拿到加密 detail，思考块是空的，
// 用户看到的就是「模型没思考」—— 这正是这轮要修的用户可见症状。
func TestReasoningGuardInjectsNoticeOnGiveUp(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, MaxRetries: 2, MaxProbeBytes: 32768, InjectNotice: true,
	}
	front, st := newGuardFront(t, guard, "Iceman", "iceman-contributor-free",
		func(int) string { return guardEncryptedSSE() })
	raw := guardRequest(t, front, guardHighBody)
	if !strings.Contains(raw, "上游本次只下发加密思考") {
		t.Fatalf("放行时应注入可读提示：%s", raw)
	}
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("注入提示不能吞掉上游正文：%s", raw)
	}
	if calls, _, _ := st.snapshot(); calls != 3 {
		t.Fatalf("MaxRetries=2 期望 3 次上游调用，got %d", calls)
	}
}

// 学习表：连续 giveUpAfter 轮都拿不到明文的模型，跳过期内不再重抽（省掉每轮几十秒），
// 到期自动复探。避免「天生只给加密」的模型把每个请求都拖满重抽预算。
func TestReasoningGuardGivesUpAfterLearned(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, MaxRetries: 1, MaxProbeBytes: 32768,
		GiveUpAfter: 1, GiveUpForSeconds: 600,
	}
	front, st := newGuardFront(t, guard, "Iceman", "iceman-contributor-free",
		func(int) string { return guardEncryptedSSE() })
	guardRequest(t, front, guardHighBody)
	if calls, _, _ := st.snapshot(); calls != 2 {
		t.Fatalf("首轮应重抽 1 次，got %d 次上游调用", calls)
	}
	guardRequest(t, front, guardHighBody)
	if calls, _, _ := st.snapshot(); calls != 3 {
		t.Fatalf("跳过期内不应再重抽，累计期望 3 次，got %d", calls)
	}
}

// 空闲心跳：上游思考阶段静默超过阈值时补 SSE 注释行，客户端不会以为连接死了。
// 用 1 秒阈值 + 1.5 秒静默验证，真机默认 15 秒。
func TestStreamIdleHeartbeatWritesComment(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		f, _ := w.(http.Flusher)
		_, _ = io.WriteString(w, guardPlainSSE())
		if f != nil {
			f.Flush()
		}
		time.Sleep(1500 * time.Millisecond)
		_, _ = io.WriteString(w, guardEncryptedSSE())
	}))
	t.Cleanup(upstream.Close)

	mapJSON := fmt.Sprintf(`{"models":{"Iceman":{"channel":"OC","upstream":"iceman-contributor-free","base":"%s","protocol":"chat"}}}`, upstream.URL)
	srv, _ := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.StreamIdleHeartbeatSeconds = 1
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)

	raw := guardRequest(t, front, guardHighBody)
	if !strings.Contains(raw, ": zgate keepalive") {
		t.Fatalf("静默超过阈值时应写心跳注释行：%s", raw)
	}
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("心跳不能吞掉后续正文：%s", raw)
	}
}

// 心跳不能污染非流式响应：普通 JSON 报文里插注释行会直接毁掉客户端解析。
func TestHeartbeatSkipsNonStreamResponse(t *testing.T) {
	const payload = `{"id":"j","object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":"春天来了。"},"finish_reason":"stop"}]}`
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(1200 * time.Millisecond)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(200)
		_, _ = io.WriteString(w, payload)
	}))
	t.Cleanup(upstream.Close)

	mapJSON := fmt.Sprintf(`{"models":{"Iceman":{"channel":"OC","upstream":"iceman-contributor-free","base":"%s","protocol":"chat"}}}`, upstream.URL)
	srv, _ := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.StreamIdleHeartbeatSeconds = 1
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)

	raw := guardRequest(t, front, `{"model":"Iceman","messages":[{"role":"user","content":"hi"}],"stream":false,"reasoning_effort":"high"}`)
	if strings.Contains(raw, "zgate keepalive") {
		t.Fatalf("非流式响应不应插入心跳：%s", raw)
	}
	if strings.TrimSpace(raw) != payload {
		t.Fatalf("非流式响应体被改动：%s", raw)
	}
}

// 回归：心跳开启（真机默认 15 秒）时，达上限放行路径同样要完整吐出提示 + 上游字节。
// 隔离实例上实测过：带心跳时该路径把连接直接掐断（客户端 terminated、0 字节）。
func TestGuardGiveUpWithHeartbeatEnabled(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		_, _ = io.WriteString(w, guardEncryptedSSE())
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
	}))
	t.Cleanup(upstream.Close)

	mapJSON := fmt.Sprintf(`{"models":{"Iceman":{"channel":"OC","upstream":"iceman-contributor-free","base":"%s","protocol":"chat"}}}`, upstream.URL)
	srv, _ := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.StreamIdleHeartbeatSeconds = 15
	cfg.ReasoningGuard = config.ReasoningGuard{
		Enabled: true, MaxRetries: 2, MaxProbeBytes: 32768, InjectNotice: true,
	}
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)

	raw := guardRequest(t, front, guardHighBody)
	if !strings.Contains(raw, "上游本次只下发加密思考") {
		t.Fatalf("带心跳时放行路径没写提示：%q", raw)
	}
	if !strings.Contains(raw, "春天是") {
		t.Fatalf("带心跳时放行路径丢了上游正文：%q", raw)
	}
}

// 复现真实上游形态：SSE 响应带 Content-Length（不是 chunked）、一次写完。
// 隔离实例上「达上限放行」路径在这个形态下会 200 之后 0 字节断连。
func TestGuardGiveUpWithContentLengthBody(t *testing.T) {
	payload := guardEncryptedSSE()
	var mu sync.Mutex
	attempts := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		attempts++
		mu.Unlock()
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Content-Length", fmt.Sprint(len(payload)))
		w.WriteHeader(200)
		_, _ = io.WriteString(w, payload)
	}))
	t.Cleanup(upstream.Close)

	mapJSON := fmt.Sprintf(`{"models":{"Iceman":{"channel":"OC","upstream":"iceman-contributor-free","base":"%s","protocol":"chat"}}}`, upstream.URL)
	srv, _ := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.StreamIdleHeartbeatSeconds = 15
	cfg.ReasoningGuard = config.ReasoningGuard{
		Enabled: true, MaxRetries: 2, MaxProbeBytes: 32768, InjectNotice: true,
	}
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)

	raw := guardRequest(t, front, guardHighBody)
	mu.Lock()
	n := attempts
	mu.Unlock()
	t.Logf("upstream calls=%d len=%d body=%q", n, len(raw), raw)
	if !strings.Contains(raw, "上游本次只下发加密思考") || !strings.Contains(raw, "春天是") {
		t.Fatalf("Content-Length 形态下放行路径不完整：%q", raw)
	}
}
