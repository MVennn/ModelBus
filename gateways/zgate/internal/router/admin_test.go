package router

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func adminPost(t *testing.T, url string) (*http.Response, []byte) {
	t.Helper()
	return adminPostRaw(t, url, map[string]string{"X-Zgate-Admin": "1"})
}

func adminPostRaw(t *testing.T, url string, headers map[string]string) (*http.Response, []byte) {
	t.Helper()
	req, err := http.NewRequest(http.MethodPost, url, strings.NewReader("{}"))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	return resp, raw
}

func adminGet(t *testing.T, url string) (*http.Response, []byte) {
	t.Helper()
	return adminGetRaw(t, url, map[string]string{"X-Zgate-Admin": "1"})
}

func adminGetRaw(t *testing.T, url string, headers map[string]string) (*http.Response, []byte) {
	t.Helper()
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		t.Fatal(err)
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	return resp, raw
}

func TestAdminGuardMatrix(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	cases := []struct {
		name    string
		headers map[string]string
		status  int
	}{
		// 浏览器跨站表单发不出自定义头，这条是挡 CSRF 的主力。
		{"no-header", map[string]string{}, 403},
		{"with-header", map[string]string{"X-Zgate-Admin": "1"}, 200},
		{"cross-origin", map[string]string{"X-Zgate-Admin": "1", "Origin": "http://evil.example"}, 403},
		{"loopback-origin", map[string]string{"X-Zgate-Admin": "1", "Origin": "http://127.0.0.1:7872"}, 200},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			// 用只读的 /admin/stats 验门禁：/admin/reload 会真去读配置，
			// 这里只关心「拦不拦」，不关心 reload 本身。
			resp, raw := adminGetRaw(t, front.URL+"/admin/stats", tc.headers)
			if resp.StatusCode != tc.status {
				t.Fatalf("want %d, got %d: %s", tc.status, resp.StatusCode, raw)
			}
		})
	}
}

func TestAdminTokenRequired(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.Config().AdminToken = "s3cret"
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := adminGetRaw(t, front.URL+"/admin/stats", map[string]string{"X-Zgate-Admin": "1"})
	if resp.StatusCode != 403 {
		t.Fatalf("missing token must be rejected, got %d: %s", resp.StatusCode, raw)
	}
	resp, raw = adminGetRaw(t, front.URL+"/admin/stats", map[string]string{
		"X-Zgate-Admin": "1", "X-Zgate-Token": "wrong",
	})
	if resp.StatusCode != 403 {
		t.Fatalf("bad token must be rejected, got %d: %s", resp.StatusCode, raw)
	}
	resp, raw = adminGetRaw(t, front.URL+"/admin/stats", map[string]string{
		"X-Zgate-Admin": "1", "Authorization": "Bearer s3cret",
	})
	if resp.StatusCode != 200 {
		t.Fatalf("good token must pass, got %d: %s", resp.StatusCode, raw)
	}
}

func TestMetricsEndpoint(t *testing.T) {
	srv, _ := newServer(t, `{"models":{"W/0.03/M":{"channel":"WB","upstream":"u","base":"http://127.0.0.1:1","protocol":"chat"}},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := adminGet(t, front.URL+"/metrics")
	if resp.StatusCode != 200 {
		t.Fatalf("metrics status %d: %s", resp.StatusCode, raw)
	}
	if ct := resp.Header.Get("Content-Type"); !strings.HasPrefix(ct, "text/plain") {
		t.Fatalf("metrics content-type = %q", ct)
	}
	body := string(raw)
	for _, want := range []string{
		"# TYPE zgate_requests_total counter",
		"zgate_inflight_requests",
		"zgate_request_duration_seconds_bucket",
		"zgate_alias_models",
		"zgate_child_up",
	} {
		if !strings.Contains(body, want) {
			t.Fatalf("metrics missing %q", want)
		}
	}

	// 跨站来源不许读指标（同 /admin/* 的口径）。
	req, _ := http.NewRequest(http.MethodGet, front.URL+"/metrics", nil)
	req.Header.Set("Origin", "http://evil.example")
	xresp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	xresp.Body.Close()
	if xresp.StatusCode != 403 {
		t.Fatalf("cross-origin metrics must be rejected, got %d", xresp.StatusCode)
	}
}

func TestAdminRoutesAndExplain(t *testing.T) {
	mapJSON := "{\"models\":{\"W/0.03/Alpha\":{\"channel\":\"WB\",\"upstream\":\"global:alpha\",\"base\":\"http://127.0.0.1:1\",\"protocol\":\"chat\",\"fallbacks\":[\"cn:alpha\"]},\"Q/0.01/Beta\":{\"channel\":\"QD\",\"upstream\":\"cn:beta\",\"base\":\"http://127.0.0.1:1\",\"protocol\":\"chat\"}},\"legacy\":{\"old-alpha\":\"W/0.03/Alpha\"}}"
	srv, _ := newServer(t, mapJSON, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := adminGet(t, front.URL+"/admin/routes")
	if resp.StatusCode != 200 {
		t.Fatalf("routes status %d: %s", resp.StatusCode, raw)
	}
	var routes map[string]any
	if err := json.Unmarshal(raw, &routes); err != nil {
		t.Fatalf("routes json: %v: %s", err, raw)
	}
	if routes["ok"] != true {
		t.Fatalf("routes ok = %v: %s", routes["ok"], raw)
	}
	if total, _ := routes["total"].(float64); total != 2 {
		t.Fatalf("routes total = %v: %s", routes["total"], raw)
	}
	entries, _ := routes["models"].([]any)
	found := false
	for _, item := range entries {
		if m, ok := item.(map[string]any); ok && m["model"] == "W/0.03/Alpha" {
			found = true
			hops, _ := m["hops"].([]any)
			if len(hops) != 1 {
				t.Fatalf("Alpha hops = %d: %s", len(hops), raw)
			}
		}
	}
	if !found {
		t.Fatalf("routes missing Alpha: %s", raw)
	}

	resp, raw = adminGet(t, front.URL+"/admin/explain?model=Q/0.01/Beta")
	if resp.StatusCode != 200 {
		t.Fatalf("explain status %d: %s", resp.StatusCode, raw)
	}
	var explain map[string]any
	if err := json.Unmarshal(raw, &explain); err != nil {
		t.Fatalf("explain json: %v: %s", err, raw)
	}
	if explain["model"] != "Q/0.01/Beta" {
		t.Fatalf("explain model = %v: %s", explain["model"], raw)
	}
}

func TestModelsETagCaching(t *testing.T) {
	mapJSON := "{\"models\":{\"W/0.03/M\":{\"channel\":\"WB\",\"upstream\":\"u\",\"base\":\"http://127.0.0.1:1\",\"protocol\":\"chat\"}},\"legacy\":{}}"
	srv, _ := newServer(t, mapJSON, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := adminGet(t, front.URL+"/v1/models")
	if resp.StatusCode != 200 {
		t.Fatalf("models status %d: %s", resp.StatusCode, raw)
	}
	etag := resp.Header.Get("ETag")
	if etag == "" {
		t.Fatal("models response must carry an ETag")
	}

	req, _ := http.NewRequest(http.MethodGet, front.URL+"/v1/models", nil)
	req.Header.Set("If-None-Match", etag)
	resp2, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	resp2.Body.Close()
	if resp2.StatusCode != http.StatusNotModified {
		t.Fatalf("conditional GET must be 304, got %d", resp2.StatusCode)
	}
}

func TestRequestBodyLimit(t *testing.T) {
	srv, _ := newServer(t, "{\"models\":{},\"legacy\":{}}", "http://127.0.0.1:1")
	srv.Config().MaxRequestBodyBytes = 256
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	big := strings.Repeat("a", 4096)
	resp, raw := postJSON(t, front.URL+"/v1/chat/completions", "{\"model\":\"x\",\"messages\":[{\"role\":\"user\",\"content\":\""+big+"\"}]}")
	if resp.StatusCode != http.StatusRequestEntityTooLarge {
		t.Fatalf("oversized body must be 413, got %d: %s", resp.StatusCode, raw)
	}
}

func TestReadBodyLimited(t *testing.T) {
	payload := strings.Repeat("x", 5000)
	// 有 Content-Length 提示：一次分配到位，内容与提示无关地完整读出。
	got, err := readBodyLimited(strings.NewReader(payload), int64(len(payload)))
	if err != nil {
		t.Fatalf("readBodyLimited: %v", err)
	}
	if string(got) != payload {
		t.Fatalf("body mismatch: got %d bytes", len(got))
	}
	if cap(got) < len(payload) {
		t.Fatalf("cap = %d, want >= %d（应当按提示预分配）", cap(got), len(payload))
	}
	// 没有提示（chunked）：退回 io.ReadAll，内容仍然完整。
	got, err = readBodyLimited(strings.NewReader(payload), -1)
	if err != nil || string(got) != payload {
		t.Fatalf("chunked body: %v len=%d", err, len(got))
	}
	// 离谱的提示值不被采信，但内容照读。
	got, err = readBodyLimited(strings.NewReader(payload), 1<<40)
	if err != nil || string(got) != payload {
		t.Fatalf("absurd hint: %v len=%d", err, len(got))
	}
}

func TestAdminDrainWaitsForInflight(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	// 手动占住一个 inflight，模拟「还有请求在跑」。
	srv.stats.begin()
	defer srv.stats.done()

	resp, raw := adminPost(t, front.URL+"/admin/drain?wait_ms=0")
	if resp.StatusCode != 200 {
		t.Fatalf("drain status %d: %s", resp.StatusCode, raw)
	}
	var payload struct {
		OK       bool  `json:"ok"`
		Draining bool  `json:"draining"`
		Inflight int64 `json:"inflight"`
		TimedOut bool  `json:"timed_out"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		t.Fatalf("drain json: %v: %s", err, raw)
	}
	if !payload.OK || !payload.Draining {
		t.Fatalf("drain payload = %s", raw)
	}
	if !payload.TimedOut || payload.Inflight != 1 {
		t.Fatalf("wait_ms=0 且还有一个在跑时应当超时并报 1，got %s", raw)
	}

	// 健康检查要能看出「正在收尾」：换版脚本靠这个判断能不能停进程。
	resp, raw = adminGet(t, front.URL+"/health")
	if resp.StatusCode != 200 {
		t.Fatalf("health status %d: %s", resp.StatusCode, raw)
	}
	var health struct {
		Draining bool `json:"draining"`
	}
	if err := json.Unmarshal(raw, &health); err != nil {
		t.Fatalf("health json: %v: %s", err, raw)
	}
	if !health.Draining {
		t.Fatalf("health.draining must be true after /admin/drain: %s", raw)
	}
}

func TestAdminDrainCleanWhenIdle(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := adminPost(t, front.URL+"/admin/drain?wait_ms=3000")
	if resp.StatusCode != 200 {
		t.Fatalf("drain status %d: %s", resp.StatusCode, raw)
	}
	var payload struct {
		TimedOut bool  `json:"timed_out"`
		Inflight int64 `json:"inflight"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		t.Fatalf("drain json: %v: %s", err, raw)
	}
	if payload.TimedOut || payload.Inflight != 0 {
		t.Fatalf("空闲时应当立刻干净返回，got %s", raw)
	}

	// 门禁对它同样生效：不带自定义头就是 403。
	anon, anonRaw := adminPostRaw(t, front.URL+"/admin/drain", map[string]string{})
	if anon.StatusCode != http.StatusForbidden {
		t.Fatalf("anonymous drain must be 403, got %d: %s", anon.StatusCode, anonRaw)
	}
}

func TestAdminLogsTail(t *testing.T) {
	srv, log := newServer(t, "{\"models\":{},\"legacy\":{}}", "http://127.0.0.1:1")
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	for i := 0; i < 5; i++ {
		log.Infof("marker-%d", i)
	}

	resp, raw := adminGet(t, front.URL+"/admin/logs?lines=3&filter=marker")
	if resp.StatusCode != 200 {
		t.Fatalf("logs status %d: %s", resp.StatusCode, raw)
	}
	var payload struct {
		Lines     []string `json:"lines"`
		Count     int      `json:"count"`
		Truncated bool     `json:"truncated"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		t.Fatalf("logs json: %v: %s", err, raw)
	}
	if payload.Count != 3 || len(payload.Lines) != 3 {
		t.Fatalf("want 3 tail lines, got %d: %s", payload.Count, raw)
	}
	if !strings.Contains(payload.Lines[2], "marker-4") {
		t.Fatalf("last line must be marker-4: %q", payload.Lines[2])
	}
	if !payload.Truncated {
		t.Fatal("older lines exist, truncated must be true")
	}

	// 管理面闸门对它同样生效。
	anon, anonRaw := adminGetRaw(t, front.URL+"/admin/logs", map[string]string{})
	if anon.StatusCode != http.StatusForbidden {
		t.Fatalf("anonymous /admin/logs must be 403, got %d: %s", anon.StatusCode, anonRaw)
	}
}
