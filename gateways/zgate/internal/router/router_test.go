package router

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"zgate/internal/alias"
	"zgate/internal/config"
	"zgate/internal/keys"
	"zgate/internal/logx"
	"zgate/internal/supervisor"
)

type capture struct {
	mu       sync.Mutex
	requests []map[string]any
	auth     []string
}

func (c *capture) handler(statusFor func(model string) int) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var body map[string]any
		_ = json.Unmarshal(raw, &body)
		model, _ := body["model"].(string)

		c.mu.Lock()
		c.requests = append(c.requests, body)
		c.auth = append(c.auth, r.Header.Get("Authorization"))
		c.mu.Unlock()

		status := 200
		if statusFor != nil {
			status = statusFor(model)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		if status != 200 {
			_, _ = w.Write([]byte(`{"error":{"message":"upstream says no","type":"server_error"}}`))
			return
		}
		_, _ = w.Write([]byte(`{"id":"x","object":"chat.completion","created":1,"model":"` + model +
			`","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`))
	}
}

func newServer(t *testing.T, mapJSON string, upstreamBase string) (*Server, *logx.Logger) {
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
	cfg := &config.Config{
		Session: "test-session",
		Upstreams: map[string]config.Upstream{
			"OC": {Base: upstreamBase},
			"WB": {Base: upstreamBase},
			"QD": {Base: upstreamBase},
		},
	}
	ks := keys.Set{OC: "oc-key", WB: "wb-key", QD: "qd-key"}
	sup := supervisor.New(nil, dir, log)
	return New(cfg, ks, alias.New(mapPath), sup, &http.Client{}, log), log
}

func postJSON(t *testing.T, url string, body string) (*http.Response, []byte) {
	t.Helper()
	resp, err := http.Post(url, "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	return resp, raw
}

func TestAliasRewriteAndAuth(t *testing.T) {
	cap := &capture{}
	upstream := httptest.NewServer(cap.handler(nil))
	defer upstream.Close()

	srv, _ := newServer(t, `{
		"models":{"W/0.03/DeepSeek-41-Fs":{"channel":"WB","upstream":"global:deepseek-v4.1-flash-sg","base":"`+upstream.URL+`","protocol":"chat","fallbacks":["cn:deepseek-v4.1-flash"]}},
		"legacy":{}
	}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"W/0.03/DeepSeek-41-Fs","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("status %d: %s", resp.StatusCode, raw)
	}
	if len(cap.requests) != 1 {
		t.Fatalf("expected 1 upstream call, got %d", len(cap.requests))
	}
	if cap.requests[0]["model"] != "global:deepseek-v4.1-flash-sg" {
		t.Fatalf("upstream model not rewritten: %v", cap.requests[0]["model"])
	}
	if cap.auth[0] != "Bearer wb-key" {
		t.Fatalf("wrong auth header: %q", cap.auth[0])
	}
}

func TestFallbackChainRetriesOn503(t *testing.T) {
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
	if len(cap.requests) != 2 {
		t.Fatalf("expected 2 attempts, got %d", len(cap.requests))
	}
	if cap.requests[1]["model"] != "backup" {
		t.Fatalf("second attempt used %v", cap.requests[1]["model"])
	}
}

func TestPrefixFallbackWhenMapIsEmpty(t *testing.T) {
	cap := &capture{}
	upstream := httptest.NewServer(cap.handler(nil))
	defer upstream.Close()

	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"cn:space-bunny","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("prefix fallback failed: %d %s", resp.StatusCode, raw)
	}
	if cap.requests[0]["model"] != "cn:space-bunny" {
		t.Fatalf("WB prefix must pass through unchanged, got %v", cap.requests[0]["model"])
	}
}

func TestQoderModelOnlySupportsChat(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/messages", `{"model":"qoder:DeepSeek-Flash","messages":[]}`)
	if resp.StatusCode != 400 {
		t.Fatalf("want 400 for non-chat Qoder model, got %d %s", resp.StatusCode, raw)
	}
	if !strings.Contains(string(raw), "only support chat/completions") {
		t.Fatalf("unexpected error body: %s", raw)
	}
}

func TestHealthExposesNoKeys(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, err := http.Get(front.URL + "/health")
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	text := string(raw)
	for _, secret := range []string{"oc-key", "wb-key", "qd-key"} {
		if strings.Contains(text, secret) {
			t.Fatalf("/health leaked a key: %s", secret)
		}
	}
	var body map[string]any
	if err := json.Unmarshal(raw, &body); err != nil {
		t.Fatalf("health is not JSON: %s", raw)
	}
	if body["ok"] != true || body["workbuddy"].(map[string]any)["key"] != true {
		t.Fatalf("health shape wrong: %s", raw)
	}
}

func TestNormalizePath(t *testing.T) {
	cases := map[string]string{
		"/v1/chat/completions": "/chat/completions",
		"/chat/completions":    "/chat/completions",
		"/v1":                  "/",
		"/v1/":                 "/",
	}
	for in, want := range cases {
		r := httptest.NewRequest("POST", in, nil)
		got, _ := normalizePath(r)
		if got != want {
			t.Fatalf("normalizePath(%q)=%q want %q", in, got, want)
		}
	}

	// The query part must keep its "?" so base+path+search stays a valid URL.
	r := httptest.NewRequest("POST", "/v1/chat/completions?stream=1", nil)
	gotPath, gotSearch := normalizePath(r)
	if gotPath != "/chat/completions" || gotSearch != "?stream=1" {
		t.Fatalf("normalizePath with query = (%q,%q), want (/chat/completions,?stream=1)", gotPath, gotSearch)
	}
}

func TestQueryStringIsForwarded(t *testing.T) {
	var gotPath, gotQuery string
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotPath, gotQuery = r.URL.Path, r.URL.RawQuery
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"x","object":"chat.completion","choices":[]}`))
	}))
	defer upstream.Close()

	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, err := http.Post(front.URL+"/v1/chat/completions?stream=1", "application/json",
		strings.NewReader(`{"model":"deepseek-v4.1-flash","stream":true}`))
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if gotPath != "/chat/completions" || gotQuery != "stream=1" {
		t.Fatalf("upstream got path=%q query=%q, want /chat/completions?stream=1", gotPath, gotQuery)
	}
}

func TestAdminReloadAppliesPolicy(t *testing.T) {
	dir := t.TempDir()
	cfgPath := filepath.Join(dir, "zgate.json")
	writeConfig := func(children string) {
		body := `{"listen":"127.0.0.1:7871","children":` + children + `}`
		if err := os.WriteFile(cfgPath, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	writeConfig(`{"qoder":{"policy":"always"}}`)

	cfg, err := config.Load(cfgPath)
	if err != nil {
		t.Fatal(err)
	}
	log, err := logx.Open(dir, "test.log", 1)
	if err != nil {
		t.Fatal(err)
	}
	defer log.Close()
	sup := supervisor.New(cfg.Children, dir, log)
	srv := New(cfg, keys.Set{}, alias.New(filepath.Join(dir, "missing.json")), sup, &http.Client{}, log)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	writeConfig(`{"qoder":{"policy":"ondemand","idleSeconds":60,"windows":["09:00-09:10"]}}`)
	resp, err := http.Post(front.URL+"/admin/reload", "application/json", nil)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("reload failed: %d %s", resp.StatusCode, raw)
	}
	state := sup.States()["qoder"].(map[string]any)
	if state["policy"] != "ondemand" {
		t.Fatalf("policy not reloaded: %v", state["policy"])
	}

	getResp, err := http.Get(front.URL + "/admin/reload")
	if err != nil {
		t.Fatal(err)
	}
	getResp.Body.Close()
	if getResp.StatusCode != 405 {
		t.Fatalf("GET must be rejected, got %d", getResp.StatusCode)
	}
}

func TestFallbackChainRetriesOnModelUnavailable(t *testing.T) {
	cap := &capture{}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var body map[string]any
		_ = json.Unmarshal(raw, &body)
		model, _ := body["model"].(string)
		cap.mu.Lock()
		cap.requests = append(cap.requests, body)
		cap.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if model == "primary" {
			w.WriteHeader(400)
			_, _ = w.Write([]byte(`{"error":{"code":"model_unavailable","message":"cooling down"}}`))
			return
		}
		_, _ = w.Write([]byte(`{"id":"x","object":"chat.completion","model":"` + model +
			`","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`))
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
		t.Fatalf("model_unavailable should fall back, got %d %s", resp.StatusCode, raw)
	}
	if len(cap.requests) != 2 || cap.requests[1]["model"] != "backup" {
		t.Fatalf("fallback did not run: %v", cap.requests)
	}
}

func TestPlain400IsNotRetried(t *testing.T) {
	cap := &capture{}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var body map[string]any
		_ = json.Unmarshal(raw, &body)
		cap.mu.Lock()
		cap.requests = append(cap.requests, body)
		cap.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(400)
		_, _ = w.Write([]byte(`{"error":{"code":"invalid_request","message":"bad tool schema"}}`))
	}))
	defer upstream.Close()

	srv, _ := newServer(t, `{
		"models":{"W/0.00/M":{"channel":"WB","upstream":"primary","base":"`+upstream.URL+`","protocol":"chat","fallbacks":["backup"]}},
		"legacy":{}
	}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, _ := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"W/0.00/M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 400 {
		t.Fatalf("plain 400 must pass through, got %d", resp.StatusCode)
	}
	if len(cap.requests) != 1 {
		t.Fatalf("plain 400 must not retry, got %d attempts", len(cap.requests))
	}
}

func TestChainSpansChannels(t *testing.T) {
	var hits []string
	var auth []string
	serve := func(name string, status int) *httptest.Server {
		return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			raw, _ := io.ReadAll(r.Body)
			var body map[string]any
			_ = json.Unmarshal(raw, &body)
			hits = append(hits, name+":"+body["model"].(string))
			auth = append(auth, r.Header.Get("Authorization"))
			w.Header().Set("Content-Type", "application/json")
			if status != 200 {
				w.WriteHeader(status)
				_, _ = w.Write([]byte(`{"error":{"message":"nope","code":"model_unavailable"}}`))
				return
			}
			_, _ = w.Write([]byte(`{"id":"x","object":"chat.completion","model":"m","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`))
		}))
	}
	wb := serve("WB", 400)
	oc := serve("OC", 200)
	defer wb.Close()
	defer oc.Close()

	mapJSON := `{"models":{"DeepSeek-Test":{"channel":"WB","upstream":"wb-a","base":"` + wb.URL + `","protocol":"chat",
		"chain":[
			{"upstream":"wb-a","base":"` + wb.URL + `","channel":"WB","price":0.03},
			{"upstream":"oc-b","base":"` + oc.URL + `","channel":"OC","price":0.11}
		]}},"legacy":{}}`
	srv, _ := newServer(t, mapJSON, wb.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"DeepSeek-Test","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("chain did not fall through: %d %s", resp.StatusCode, raw)
	}
	if len(hits) != 2 || hits[0] != "WB:wb-a" || hits[1] != "OC:oc-b" {
		t.Fatalf("unexpected hops: %v", hits)
	}
	if auth[0] != "Bearer wb-key" || auth[1] != "Bearer oc-key" {
		t.Fatalf("per-hop auth wrong: %v", auth)
	}
}

func TestHopFatal(t *testing.T) {
	cases := []struct {
		name   string
		status int
		body   string
		want   bool
	}{
		{"qwen free quota exhausted (403)", 403,
			`event:error
data:{"code":"AccessDenied","message":"Free quota exhausted. To continue accessing the model on a paid basis, please add funds or disable the \"use free tier only\" mode in the management console."}`, true},
		{"model id missing (400)", 400, `{"code":"InvalidParameter","message":"Model not exist."}`, true},
		{"arrearage (400)", 400, `{"code":"Arrearage","message":"account in arrears"}`, true},
		{"plain auth failure (403) must NOT be skipped", 403, `{"message":"invalid api key"}`, false},
		{"bad request (400) must NOT be skipped", 400, `{"message":"invalid tools schema"}`, false},
		{"rate limit (429) is transient, not fatal", 429, `{"message":"rate limit"}`, false},
	}
	for _, tc := range cases {
		if got := hopFatal(tc.status, []byte(tc.body)); got != tc.want {
			t.Errorf("%s: hopFatal(%d) = %v, want %v", tc.name, tc.status, got, tc.want)
		}
	}
}

func TestChatPath504CoolsTheHop(t *testing.T) {
	// notes 对齐项：桥接路径 504 会把该跳冷却 5min（coolBridgeFailure），
	// chat 链路径原来不冷 —— 静默僵死的 chat 上游每个请求都要先撞一遍再回落。
	// 第一跳 504 → 冷却 + 回落第二跳拿 200；下一个请求必须直接跳过第一跳。
	dead := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(504)
		_, _ = w.Write([]byte(`{"error":{"message":"gateway timeout","type":"server_error"}}`))
	}))
	defer dead.Close()
	cap := &capture{}
	live := httptest.NewServer(cap.handler(nil))
	defer live.Close()

	srv, _ := newServer(t, `{
		"models":{"M":{"channel":"OC","upstream":"dead","base":"`+dead.URL+`","protocol":"chat",
			"chain":[
				{"upstream":"dead","base":"`+dead.URL+`","channel":"OC","protocol":"chat","price":0.1},
				{"upstream":"live","base":"`+live.URL+`","channel":"OC","protocol":"chat","price":0.1}
			]}},
		"legacy":{}
	}`, live.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("504 hop did not fall through: status %d, body %s", resp.StatusCode, raw)
	}
	deadHop := alias.Hop{Channel: "OC", Upstream: "dead"}
	liveHop := alias.Hop{Channel: "OC", Upstream: "live"}
	if !srv.cooling(deadHop) {
		t.Fatal("chat 504 must cool the hop (aligned with the bridge path)")
	}
	if srv.cooling(liveHop) {
		t.Fatal("the healthy hop must not be cooled")
	}
	resp2, raw2 := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"M","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp2.StatusCode != 200 {
		t.Fatalf("second request failed: %d %s", resp2.StatusCode, raw2)
	}
	cap.mu.Lock()
	n := len(cap.requests)
	cap.mu.Unlock()
	if n != 2 {
		t.Fatalf("dead hop must be skipped while cooling, live got %d requests", n)
	}
}

// TestRegionBlocked403CoolsTheDirectHopOnly 复刻 2026-11-06 的 beam-free 实况：
// 直连出口 403 RegionError（"This model is not available in your country"），
// 机场孪生跳出 200。链序是 [直连, 机场孪生]，原来每个请求都先撞一次 403 再回落
// （10 分钟 359 次，面板一片 403 Rejected）。地区受限必须把直连那一跳冷却掉，
// 让下一个请求直接落到孪生跳；孪生跳是另一个冷却键，不能被顺手吃掉。
func TestRegionBlocked403CoolsTheDirectHopOnly(t *testing.T) {
	var mu sync.Mutex
	directHits := 0
	blocked := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		directHits++
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(403)
		_, _ = w.Write([]byte(`{"type":"error","error":{"type":"RegionError","message":"This model is not available in your country"}}`))
	}))
	defer blocked.Close()
	cap := &capture{}
	airport := httptest.NewServer(cap.handler(nil))
	defer airport.Close()

	srv, _ := newServer(t, `{
		"models":{"Beam":{"channel":"OC","upstream":"beam-free","protocol":"chat",
			"chain":[
				{"upstream":"beam-free","base":"`+blocked.URL+`","channel":"OC","protocol":"chat","price":0},
				{"upstream":"beam-free","base":"`+airport.URL+`","channel":"OC","protocol":"chat","price":0,"proxy":"http://10.0.0.1:7896"}
			]}},
		"legacy":{}
	}`, airport.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Beam","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp.StatusCode != 200 {
		t.Fatalf("region 403 should fall back to the airport twin, got %d %s", resp.StatusCode, raw)
	}

	direct := alias.Hop{Channel: "OC", Upstream: "beam-free"}
	twin := alias.Hop{Channel: "OC", Upstream: "beam-free", Proxy: "http://10.0.0.1:7896"}
	if !srv.cooling(direct) {
		t.Fatal("region-blocked direct hop must be cooled")
	}
	if srv.cooling(twin) {
		t.Fatal("the airport twin must stay usable (its hopKey carries the proxy)")
	}

	resp2, raw2 := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Beam","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
	if resp2.StatusCode != 200 {
		t.Fatalf("second request failed: %d %s", resp2.StatusCode, raw2)
	}
	mu.Lock()
	n := directHits
	mu.Unlock()
	cap.mu.Lock()
	m := len(cap.requests)
	cap.mu.Unlock()
	if n != 1 {
		t.Fatalf("cooled direct hop must be skipped, it got %d requests", n)
	}
	if m != 2 {
		t.Fatalf("airport twin should serve both requests, got %d", m)
	}
}

// TestRegionBlockedDoesNotCoolALoneHop：链里没有同上游的出口孪生跳时不能冷却。
// 冷却唯一一跳会让后续请求连尝试都省掉，把真实的 403 变成「all upstreams failed」502。
func TestRegionBlockedDoesNotCoolALoneHop(t *testing.T) {
	var mu sync.Mutex
	hits := 0
	blocked := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		hits++
		mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(403)
		_, _ = w.Write([]byte(`{"type":"error","error":{"type":"RegionError","message":"This model is not available in your country"}}`))
	}))
	defer blocked.Close()

	srv, _ := newServer(t, `{
		"models":{"Beam":{"channel":"OC","upstream":"beam-free","protocol":"chat",
			"chain":[{"upstream":"beam-free","base":"`+blocked.URL+`","channel":"OC","protocol":"chat","price":0}]}},
		"legacy":{}
	}`, blocked.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	for i := 0; i < 2; i++ {
		// 单跳链的 403 本来就会走到链耗尽（502 all upstreams failed），这与本次改动无关；
		// 这里只钉住「每次都要真的再试一遍」，不被冷却省掉。
		resp, _ := postJSON(t, front.URL+"/v1/chat/completions",
			`{"model":"Beam","messages":[{"role":"user","content":"hi"}],"max_tokens":8}`)
		if resp.StatusCode == 200 {
			t.Fatalf("attempt %d: region-blocked upstream must not answer 200", i+1)
		}
	}
	if srv.cooling(alias.Hop{Channel: "OC", Upstream: "beam-free"}) {
		t.Fatal("a lone hop must not be cooled: it would turn the real 403 into an instant 502")
	}
	mu.Lock()
	n := hits
	mu.Unlock()
	if n != 2 {
		t.Fatalf("lone hop must still be attempted every time, got %d hits", n)
	}
}
