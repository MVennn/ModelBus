package router

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"zgate/internal/alias"
	"zgate/internal/bridge"
	"zgate/internal/config"
	"zgate/internal/keys"
	"zgate/internal/logx"
	"zgate/internal/supervisor"
)

// 这里测两件事：hop.proxy 真的换出口；地区受限的 403 会落到链上的下一跳。
// 前者用「上游主机名不可解析，只有经代理才通」证，后者用两跳各自的状态码证。

func newEgressServer(t *testing.T, mapJSON string) *Server {
	t.Helper()
	dir := t.TempDir()
	mapPath := filepath.Join(dir, "model-alias-map.json")
	if err := os.WriteFile(mapPath, []byte(mapJSON), 0o644); err != nil {
		t.Fatal(err)
	}
	log, err := logx.Open(dir, "test.log", 1)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(log.Close)
	cfg := &config.Config{Session: "test-session"}
	ks := keys.Set{OC: "oc-key", WB: "wb-key"}
	sup := supervisor.New(nil, dir, log)
	client := &http.Client{Transport: NewEgressRouter(&http.Transport{})}
	return New(cfg, ks, alias.New(mapPath), sup, client, log)
}

func okBody() string {
	return `{"id":"x","object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":"ok"}}]}`
}

func TestHopProxyIsUsed(t *testing.T) {
	var mu sync.Mutex
	var seen []string
	proxy := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		seen = append(seen, r.URL.String())
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(okBody()))
	}))
	defer proxy.Close()

	// 上游主机名故意不可解析：只有真的走了 proxy 才可能拿到 200。
	srv := newEgressServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"m","base":"http://origin.invalid","protocol":"chat",
			"chain":[{"upstream":"m","base":"http://origin.invalid","channel":"OC","protocol":"chat","price":0.1,"proxy":"`+proxy.URL+`"}]}},
		"legacy":{}
	}`)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("status %d: %s", resp.StatusCode, raw)
	}
	mu.Lock()
	defer mu.Unlock()
	if len(seen) != 1 || seen[0] != "http://origin.invalid/chat/completions" {
		t.Fatalf("proxy did not receive the absolute-form request: %v", seen)
	}
}

func TestHopWithoutProxyStaysDirect(t *testing.T) {
	srv := newEgressServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"m","base":"http://origin.invalid","protocol":"chat",
			"chain":[{"upstream":"m","base":"http://origin.invalid","channel":"OC","protocol":"chat","price":0.1}]}},
		"legacy":{}
	}`)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode == 200 {
		t.Fatalf("unresolvable origin without a proxy should fail, got 200: %s", raw)
	}
}

func TestRegionBlockedFallsThroughToNextHop(t *testing.T) {
	var mu sync.Mutex
	var calls []string
	blocked := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		calls = append(calls, "blocked")
		mu.Unlock()
		w.WriteHeader(403)
		_, _ = w.Write([]byte(`{"error":{"message":"unsupported_country_region_territory","type":"invalid_request_error"}}`))
	}))
	defer blocked.Close()
	allowed := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		calls = append(calls, "allowed")
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(okBody()))
	}))
	defer allowed.Close()

	srv := newEgressServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"m","base":"`+blocked.URL+`","protocol":"chat",
			"chain":[
				{"upstream":"m","base":"`+blocked.URL+`","channel":"OC","protocol":"chat","price":0.1},
				{"upstream":"m","base":"`+allowed.URL+`","channel":"OC","protocol":"chat","price":0.1}
			]}},
		"legacy":{}
	}`)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	// 第一跳 403 地区受限 → 必须换到第二跳并拿到 200；原样返回 403 就是回归。
	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	mu.Lock()
	defer mu.Unlock()
	if resp.StatusCode != 200 {
		t.Fatalf("region block did not fall through: status %d, calls %v, body %s", resp.StatusCode, calls, raw)
	}
	if len(calls) != 2 || calls[0] != "blocked" || calls[1] != "allowed" {
		t.Fatalf("expected blocked then allowed, got %v", calls)
	}
}

func TestRegionBlockedIsNotHopFatal(t *testing.T) {
	// hopFatal=true 会把这一跳冷却掉，链后面的跳全被跳过 —— 地区受限不能算 hopFatal。
	if hopFatal(403, []byte(`{"error":{"message":"unsupported_country_region_territory"}}`)) {
		t.Fatal("region block must not be hopFatal")
	}
	if hopFatal(403, []byte(`{"error":{"message":"This model is not available in your country"}}`)) {
		t.Fatal("region block must not be hopFatal")
	}
}

func TestChainAcceptRegionMarkers(t *testing.T) {
	// chainAccept 返回 true = 认这一跳的响应；false = 换下一跳。
	region := []byte(`{"error":{"message":"RegionError: This model is not available in your country"}}`)
	if chainAccept(403, region) {
		t.Fatal("region block must fall through to the next hop")
	}
	if !chainAccept(403, []byte(`{"error":{"message":"invalid api key"}}`)) {
		t.Fatal("a plain 403 must not fall through")
	}
	if !chainAccept(400, []byte(`{"error":{"message":"bad request"}}`)) {
		t.Fatal("a plain 400 must not fall through")
	}
	if chainAccept(400, []byte(`{"error":{"code":"model_unavailable"}}`)) {
		t.Fatal("model_unavailable must fall through")
	}
	if chainAccept(429, nil) {
		t.Fatal("429 must fall through")
	}
}

func TestRegionBlockedHelper(t *testing.T) {
	// 两种真实写法（chat 端点 vs responses 端点）都要认。
	for _, body := range []string{
		`{"type":"error","error":{"type":"RegionError","message":"This model is not available in your country"}}`,
		`{"model":"gpt-6-luna","error":{"code":"unsupported_country_region_territory","message":"Country, region, or territory not supported"}}`,
	} {
		if !regionBlocked(403, []byte(body)) {
			t.Fatalf("region block not detected: %s", body)
		}
	}
	if regionBlocked(403, []byte(`{"error":{"message":"invalid api key"}}`)) {
		t.Fatal("plain 403 must not be treated as a region block")
	}
	if regionBlocked(429, []byte(`{"error":{"type":"RegionError"}}`)) {
		t.Fatal("429 is throttling, not a region block")
	}
}

func TestTransportFailureRetriesSameHop(t *testing.T) {
	// 复刻 2026-10-31 凌晨那次：机场节点对 opencode.ai 的大包短暂黑洞，
	// 连接在请求发出后被动断开（EOF）。这一跳只出现一次，没有下一跳可落，
	// 唯一能救的就是「重试同一跳一次」。
	var mu sync.Mutex
	n := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		n++
		cur := n
		mu.Unlock()
		if cur == 1 {
			if hj, ok := w.(http.Hijacker); ok {
				if conn, _, err := hj.Hijack(); err == nil {
					_ = conn.Close() // 不写任何字节就断开 → 客户端拿到 EOF
					return
				}
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(okBody()))
	}))
	defer srv.Close()

	srv2 := newEgressServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"m","base":"`+srv.URL+`","protocol":"chat",
			"chain":[{"upstream":"m","base":"`+srv.URL+`","channel":"OC","protocol":"chat","price":0.1}]}},
		"legacy":{}
	}`)
	front := httptest.NewServer(srv2.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	mu.Lock()
	got := n
	mu.Unlock()
	if resp.StatusCode != 200 {
		t.Fatalf("transport failure was not retried: status %d, body %s", resp.StatusCode, raw)
	}
	if got != 2 {
		t.Fatalf("expected exactly 2 attempts (1 fail + 1 retry), got %d", got)
	}
}

func TestClientCancelDoesNotRetry(t *testing.T) {
	// 客户端中途取消（用户点停止 / 切模型 / 关页面）不是「上游黑洞」：
	// 那次请求本身已作废，重试只是多打一次上游。2026-11-02 实测一次取消风暴
	// 在半秒内被放大成 8 条「传输层失败 context canceled，300ms 后重试」。
	var mu sync.Mutex
	attempts := 0
	release := make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		attempts++
		mu.Unlock()
		<-release // 挂住，等测试取消客户端请求
	}))
	defer srv.Close()
	defer close(release)

	front := httptest.NewServer(newEgressServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"m","base":"`+srv.URL+`","protocol":"chat",
			"chain":[{"upstream":"m","base":"`+srv.URL+`","channel":"OC","protocol":"chat","price":0.1}]}},
		"legacy":{}
	}`).Handler())
	defer front.Close()

	ctx, cancel := context.WithCancel(context.Background())
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, front.URL+"/v1/chat/completions",
		strings.NewReader(`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`))
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	go func() {
		time.Sleep(100 * time.Millisecond)
		cancel()
	}()
	if resp, err := http.DefaultClient.Do(req); err == nil {
		_ = resp.Body.Close()
		t.Fatal("expected the cancelled request to fail client-side")
	}
	// 等过重试窗口再看：修好之后不会出现第二次上游调用。
	time.Sleep(2 * transportRetryDelay)
	mu.Lock()
	got := attempts
	mu.Unlock()
	if got != 1 {
		t.Fatalf("client cancel must not trigger a retry: want 1 upstream attempt, got %d", got)
	}
}

func TestTransportFailureDoesNotConsume429Backoff(t *testing.T) {
	// PITFALLS §34 的口径：txRetry 与 429 的退避预算互不吃。
	// 先传输层失败一次，再吃 429：429 仍必须先就地退避重试同一跳，
	// 而不是直接冷却+回落（一跳链没有下一跳，那样就是 502）。
	var mu sync.Mutex
	n := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		n++
		cur := n
		mu.Unlock()
		switch cur {
		case 1:
			if hj, ok := w.(http.Hijacker); ok {
				if conn, _, err := hj.Hijack(); err == nil {
					_ = conn.Close() // EOF：请求没被上游受理
					return
				}
			}
			t.Error("hijack failed")
			return
		case 2:
			w.WriteHeader(429)
			_, _ = w.Write([]byte(`{"error":{"message":"rate limited"}}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(okBody()))
	}))
	defer srv.Close()

	srv2 := newEgressServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"m","base":"`+srv.URL+`","protocol":"chat",
			"chain":[{"upstream":"m","base":"`+srv.URL+`","channel":"OC","protocol":"chat","price":0.1}]}},
		"legacy":{}
	}`)
	front := httptest.NewServer(srv2.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	mu.Lock()
	got := n
	mu.Unlock()
	if resp.StatusCode != 200 {
		t.Fatalf("429 after a transport blip must still back off in place: status %d, body %s", resp.StatusCode, raw)
	}
	if got != 3 {
		t.Fatalf("expected exactly 3 attempts (EOF + 429 + backoff retry), got %d", got)
	}
}

func TestTransportFailedMarkers(t *testing.T) {
	cases := []struct {
		status int
		body   string
		want   bool
	}{
		{502, `Post "https://x/y": EOF`, true},
		{502, `Post "https://x/y": net/http: TLS handshake timeout`, true},
		{502, `read tcp 1.2.3.4: connection reset by peer`, true},
		{502, `dial tcp 1.2.3.4: connection refused`, true},
		{502, `bridge upstream error: boom`, false}, // 普通 5xx，重试没有意义
		{200, `EOF`, false}, // 成功响应里出现 EOF 字样不算
	}
	for _, c := range cases {
		if got := transportFailed(bridge.Result{Status: c.status, Body: []byte(c.body)}); got != c.want {
			t.Fatalf("transportFailed(%d, %q) = %v, want %v", c.status, c.body, got, c.want)
		}
	}
}

func TestHopKeySeparatesEgress(t *testing.T) {
	direct := alias.Hop{Channel: "OC", Upstream: "gpt-6-luna"}
	viaAirport := alias.Hop{Channel: "OC", Upstream: "gpt-6-luna", Proxy: "http://10.0.0.1:7896"}
	if hopKey(direct) == hopKey(viaAirport) {
		t.Fatal("直连与机场必须是两个冷却键，否则直连的 403 会把兜底跳冷却掉")
	}
}

func TestMaskProxyMasksUserinfo(t *testing.T) {
	// 有凭据：保留用户名，口令换 ***
	if got := maskProxy("http://alice:s3cret@10.0.0.1:7896"); got != "http://alice:***@10.0.0.1:7896" {
		t.Fatalf("maskProxy = %q", got)
	}
	// 只有用户名没有口令：原样返回（没有可掩的口令）
	if got := maskProxy("http://alice@10.0.0.1:7896"); got != "http://alice@10.0.0.1:7896" {
		t.Fatalf("maskProxy = %q", got)
	}
	// 无凭据（当前配置的形态）：原样返回
	if got := maskProxy("http://10.0.0.1:7896"); got != "http://10.0.0.1:7896" {
		t.Fatalf("maskProxy = %q", got)
	}
	if got := maskProxy(""); got != "" {
		t.Fatalf(`maskProxy("") = %q`, got)
	}
	// 畸形串：不回显原文 —— 解析失败的串可能带着读不懂的凭据，给固定占位
	bad := "http://[::1"
	if got := maskProxy(bad); got == bad || got == "" {
		t.Fatalf("malformed proxy must not be echoed raw, got %q", got)
	}
}

func TestHopKeyForLogMasksCredentials(t *testing.T) {
	hop := alias.Hop{Channel: "OC", Upstream: "m", Proxy: "http://alice:s3cret@10.0.0.1:7896"}
	// 日志形态必须脱敏
	if got := hopKeyForLog(hop); got != "OC|m|http://alice:***@10.0.0.1:7896" {
		t.Fatalf("hopKeyForLog = %q", got)
	}
	// 冷却键保持原始串：掩码串会让「只差口令」的两跳共用键
	if got := hopKey(hop); got != "OC|m|http://alice:s3cret@10.0.0.1:7896" {
		t.Fatalf("cooldown key must stay raw, got %q", got)
	}
	// 无凭据时两个形态一致（当前配置的实际取值）
	plain := alias.Hop{Channel: "OC", Upstream: "m", Proxy: "http://10.0.0.1:7896"}
	if hopKeyForLog(plain) != hopKey(plain) {
		t.Fatalf("plain proxy must log unchanged: %q vs %q", hopKeyForLog(plain), hopKey(plain))
	}
}

func TestProxyOfRoundTrip(t *testing.T) {
	ctx := WithProxy(context.Background(), "http://127.0.0.1:7896")
	if got := ProxyOf(ctx); got != "http://127.0.0.1:7896" {
		t.Fatalf("ProxyOf = %q", got)
	}
	// 空代理表示直连：必须覆盖外层值，否则链上「机场跳后面跟直连跳」时，
	// 直连跳会悄悄沿用上一跳的机场出口（每跳出自己的口，见 alias.Hop 注释）。
	if got := ProxyOf(WithProxy(ctx, "")); got != "" {
		t.Fatalf("empty proxy must clear the outer value (per-hop egress), got %q", got)
	}
	if got := ProxyOf(context.Background()); got != "" {
		t.Fatalf("no proxy expected, got %q", got)
	}
}
