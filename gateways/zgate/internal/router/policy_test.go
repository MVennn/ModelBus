package router

// 本文件测的是 2026-11-10 整理书 P0/P1/P2 的落地判据：
//
//   - 竞速参数逐跳取（链上有一跳没配策略，不该把整条链退回串行）；
//   - 链层参数聚合口径（对冲取最急的跳、并发取最宽的跳）；
//   - 单跳链沉默不埋静默冷却（埋了等于把这个模型关掉）；
//   - 链首字节预算到点回 504 且不埋冷却（不是这一跳的错，也不该继续换跳）；
//   - 启动自检只在「渠道只服务单跳模型」时判死；
//   - 守卫 mode=channels 按渠道能力位走。

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"zgate/internal/alias"
	"zgate/internal/config"
)

// 链上有一跳开了对冲、另一跳压根没配 channelPolicy —— 旧口径要求「每跳都配」才
// 竞速，于是 GM+HJ 这种混链会静默退回串行；这正是 2026-11-10 对冲「配了没生效」
// 的成因之一。缺配的跳只该少一个看门狗，不该拖累整条链。
func TestRacePlanDoesNotRequirePolicyOnEveryHop(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"GM": {HedgeAfterMs: 18000, MaxParallel: 2},
	}
	target := alias.Target{Chain: []alias.Hop{
		{Channel: "GM", Upstream: "g1"},
		{Channel: "HJ", Upstream: "h1"}, // 没有任何策略
	}}
	plan, ok := srv.racePlanFor(target, []byte(`{"model":"m","stream":true}`))
	if !ok {
		t.Fatal("链上有一跳要求对冲就该竞速：缺配的跳只是没有看门狗")
	}
	if plan.hedge != 18*time.Second || plan.maxParallel != 2 {
		t.Fatalf("plan = %+v, want hedge=18s maxParallel=2", plan)
	}
}

// 链层聚合：对冲间隔取各跳正值的**最小值**（谁最急按谁），并发上限取最大值。
func TestRacePlanAggregatesAcrossHops(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"GM": {HedgeAfterMs: 18000, MaxParallel: 2},
		"HJ": {HedgeAfterMs: 6000, MaxParallel: 3},
	}
	target := alias.Target{Chain: []alias.Hop{{Channel: "GM", Upstream: "g"}, {Channel: "HJ", Upstream: "h"}}}
	plan, ok := srv.racePlanFor(target, []byte(`{"stream":true}`))
	if !ok {
		t.Fatal("want race plan")
	}
	if plan.hedge != 6*time.Second {
		t.Fatalf("hedge = %v, want 6s（取最急的那跳）", plan.hedge)
	}
	if plan.maxParallel != 3 {
		t.Fatalf("maxParallel = %d, want 3（取最宽的那跳）", plan.maxParallel)
	}
}

// 只开首块看门狗、没配对冲间隔：拿最短的首块窗口当发车间隔 —— 那一跳到点必被判死，
// 早点把下一跳放上路比干等更划算。
func TestRacePlanFallsBackToFirstBlock(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"GM": {FirstBlockMs: 9000},
		"HJ": {FirstBlockMs: 4000},
	}
	target := alias.Target{Chain: []alias.Hop{{Channel: "GM", Upstream: "g"}, {Channel: "HJ", Upstream: "h"}}}
	plan, ok := srv.racePlanFor(target, []byte(`{"stream":true}`))
	if !ok {
		t.Fatal("want race plan（firstBlockMs 也是竞速理由）")
	}
	if plan.hedge != 4*time.Second {
		t.Fatalf("hedge = %v, want 4s（最短首块窗口）", plan.hedge)
	}
}

// 全链没有竞速字段、或客户端要的是非流式：老老实实串行，不占用并发。
func TestRacePlanSerialWhenNothingAsksForIt(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"GM": {HedgeAfterMs: 18000},
		"HJ": {HedgeAfterMs: 18000},
	}
	target := alias.Target{Chain: []alias.Hop{{Channel: "GM", Upstream: "g"}, {Channel: "HJ", Upstream: "h"}}}
	if _, ok := srv.racePlanFor(target, []byte(`{"stream":false}`)); ok {
		t.Fatal("非流式请求不该竞速：它要确定的 JSON 与状态码")
	}
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{"GM": {}, "HJ": {}}
	if _, ok := srv.racePlanFor(target, []byte(`{"stream":true}`)); ok {
		t.Fatal("没有任何跳要求竞速就该走串行")
	}
}

// 单跳链沉默判死后不埋静默冷却：埋了等于把这个模型整体关掉（没有下一跳可说）；
// 多跳链同样的沉默必须留下冷却，否则下一次还会挑到这条死跳。
func TestSilenceCoolsMultiHopButNotSingleHop(t *testing.T) {
	unblock := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-unblock
	}))
	defer upstream.Close()
	defer close(unblock)

	srv, _ := newServer(t, `{
		"models":{
			"Solo":{"chain":[{"channel":"WB","upstream":"a"}]},
			"Duo":{"chain":[{"channel":"WB","upstream":"a"},{"channel":"OC","upstream":"b"}]}
		},
		"legacy":{}
	}`, upstream.URL)
	srv.headerWait = 120 * time.Millisecond
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"WB": {SilenceCooldownSeconds: 30},
		"OC": {SilenceCooldownSeconds: 30},
	}
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	death := alias.Hop{Channel: "WB", Upstream: "a"}
	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Solo","stream":true,"messages":[{"role":"user","content":"hi"}]}`)
	if resp.StatusCode < 400 {
		t.Fatalf("上游沉默应当判死，got %d: %s", resp.StatusCode, raw)
	}
	if srv.cooling(death) {
		t.Fatal("单跳链沉默不该埋静默冷却（等于把这个模型关掉）")
	}

	resp2, raw2 := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Duo","stream":true,"messages":[{"role":"user","content":"hi"}]}`)
	if resp2.StatusCode < 400 {
		t.Fatalf("多跳链全死也应当报错，got %d: %s", resp2.StatusCode, raw2)
	}
	if !srv.cooling(death) {
		t.Fatal("多跳链沉默后必须埋冷却，否则下一跳永远挑不到其他跳")
	}
}

// 链首字节预算到点：整条链放弃，回 504 gateway_timeout，并且不给任何一跳埋冷却 ——
// 这是「用户等够了」，不是「这一跳坏了」。
func TestChainBudgetReturns504WithoutCooling(t *testing.T) {
	unblock := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-unblock
	}))
	defer upstream.Close()
	defer close(unblock)

	srv, _ := newServer(t, `{
		"models":{"Duo":{"chain":[{"channel":"WB","upstream":"a"},{"channel":"OC","upstream":"b"}]}},
		"legacy":{}
	}`, upstream.URL)
	srv.headerWait = 30 * time.Second // 单跳窗口很长，只有链预算能救
	srv.cfg.ChainBudgetSec = 1
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"WB": {SilenceCooldownSeconds: 30},
		"OC": {SilenceCooldownSeconds: 30},
	}
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	start := time.Now()
	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Duo","stream":true,"messages":[{"role":"user","content":"hi"}]}`)
	elapsed := time.Since(start)
	if resp.StatusCode != 504 {
		t.Fatalf("预算到点该回 504，got %d: %s", resp.StatusCode, raw)
	}
	if elapsed > 3*time.Second {
		t.Fatalf("链预算没生效，等了 %v", elapsed)
	}
	if !strings.Contains(string(raw), "gateway_timeout") {
		t.Fatalf("错误码该是 gateway_timeout: %s", raw)
	}
	if srv.cooling(alias.Hop{Channel: "WB", Upstream: "a"}) {
		t.Fatal("预算到点不该埋冷却：不是这一跳的错")
	}
}

// 启动自检两档：渠道同时服务多跳模型 → 只提示；只服务单跳模型 → 判死。
func TestValidatePoliciesFatalOnlyWhenChannelServesSingleHopOnly(t *testing.T) {
	cfg := &config.Config{ChannelPolicy: map[string]config.ChannelPolicy{
		"GM": {HedgeAfterMs: 18000, FirstBlockMs: 4000},
	}}

	shared, _ := newServer(t, `{
		"models":{
			"Only":{"chain":[{"channel":"GM","upstream":"g"}]},
			"Both":{"chain":[{"channel":"GM","upstream":"g"},{"channel":"HJ","upstream":"h"}]}
		},
		"legacy":{}
	}`, "http://127.0.0.1:1")
	notes := ValidatePolicies(cfg, shared.aliases)
	if len(notes) != 1 {
		t.Fatalf("notes = %+v, want 1 条提示", notes)
	}
	if notes[0].Fatal {
		t.Fatal("GM 也服务多跳链，字段是有效的，不该判死")
	}
	if len(notes[0].Aliases) != 1 || notes[0].Aliases[0] != "Only" {
		t.Fatalf("影响模型 = %v, want [Only]", notes[0].Aliases)
	}

	single, _ := newServer(t, `{"models":{"Only":{"chain":[{"channel":"GM","upstream":"g"}]}},"legacy":{}}`, "http://127.0.0.1:1")
	notes = ValidatePolicies(cfg, single.aliases)
	if len(notes) != 1 || !notes[0].Fatal {
		t.Fatalf("notes = %+v（对冲字段在这条渠道上永远读不到，应当判死）", notes)
	}
	if !strings.Contains(notes[0].String(), "channel=GM") {
		t.Fatalf("提示文案缺渠道名: %s", notes[0].String())
	}
}

// 守卫 mode=channels：只有带能力位的渠道才探，白名单非空时再收一层。
func TestGuardWantedChannelsMode(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:1")
	srv.cfg.Upstreams["WB"] = config.Upstream{Base: "x", GuardReasoning: true}
	g := config.ReasoningGuard{Enabled: true, Mode: "channels"}
	body := []byte(`{"model":"m","stream":true,"reasoning_effort":"high"}`)
	if !srv.guardWanted("m", "WB", g, body) {
		t.Fatal("WB 带能力位就该探")
	}
	if srv.guardWanted("m", "OC", g, body) {
		t.Fatal("OC 没能力位不该探")
	}
	g.Models = []string{"other"}
	if srv.guardWanted("m", "WB", g, body) {
		t.Fatal("写了白名单就再收一层：m 不在名单里，不该探")
	}
	if !srv.guardWanted("m", "WB", config.ReasoningGuard{Enabled: true}, body) {
		t.Fatal("mode=auto 不看渠道与名字")
	}
}

// 链跳没写 base 时回落到渠道配置的 base：别名表只该管「哪个模型走哪几跳」，
// 地址归渠道配置。旧实现只认 hop.Base，没写 = 拿空地址去请求，两跳瞬间失败后
// 报「all upstreams failed」，看着像上游全挂了。
func TestHopBaseFallsBackToChannelConfig(t *testing.T) {
	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, "http://127.0.0.1:9")
	if got := srv.hopBase(alias.Hop{Channel: "WB", Upstream: "a"}); got != "http://127.0.0.1:9" {
		t.Fatalf("hopBase = %q, want 渠道配置里的 base", got)
	}
	if got := srv.hopBase(alias.Hop{Channel: "WB", Upstream: "a", Base: "http://127.0.0.1:7"}); got != "http://127.0.0.1:7" {
		t.Fatalf("hopBase = %q, want 跳级 base 覆盖渠道配置", got)
	}
}

// 单跳链的软冷却不落表：单跳链冷却一跳 = 把这个模型整体关掉。多跳链照旧冷却。
func TestSingleHopSkipsSoftCooling(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(503)
	}))
	defer upstream.Close()

	srv, _ := newServer(t, `{
		"models":{
			"Solo":{"chain":[{"channel":"WB","upstream":"a"}]},
			"Duo":{"chain":[{"channel":"WB","upstream":"a"},{"channel":"OC","upstream":"b"}]}
		},
		"legacy":{}
	}`, upstream.URL)
	srv.cfg.ChannelPolicy = map[string]config.ChannelPolicy{
		"WB": {SoftCooldownSeconds: 60},
		"OC": {SoftCooldownSeconds: 60},
	}
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	resp, raw := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Solo","stream":true,"messages":[{"role":"user","content":"hi"}]}`)
	if resp.StatusCode < 400 {
		t.Fatalf("上游 503 应当报错，got %d: %s", resp.StatusCode, raw)
	}
	if srv.cooling(alias.Hop{Channel: "WB", Upstream: "a"}) {
		t.Fatal("单跳链不该给唯一的跳埋软冷却（等于把这个模型关 60 秒）")
	}

	resp2, raw2 := postJSON(t, front.URL+"/v1/chat/completions",
		`{"model":"Duo","stream":true,"messages":[{"role":"user","content":"hi"}]}`)
	if resp2.StatusCode < 400 {
		t.Fatalf("多跳链全 503 应当报错，got %d: %s", resp2.StatusCode, raw2)
	}
	if !srv.cooling(alias.Hop{Channel: "WB", Upstream: "a"}) {
		t.Fatal("多跳链的 503 仍要埋软冷却，否则每个请求都先撞一遍坏跳")
	}
}
