package router

import (
	"net/http"
	"testing"
	"time"

	"zgate/internal/alias"
	"zgate/internal/logx"
)

func newCoolServer(t *testing.T) *Server {
	t.Helper()
	log, err := logx.Open(t.TempDir(), "test.log", 1)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(log.Close)
	return &Server{cool: map[string]time.Time{}, log: log}
}

// 千问额度烧光：403 + Free quota exhausted。这一跳要回落，但冷却必须是一天量级，
// 否则每 30 分钟就重撞一次，面板上任一请求都能看到一次白付的往返。
func TestQuotaExhaustedCoolsForADay(t *testing.T) {
	hop := alias.Hop{Channel: "QW", Upstream: "deepseek-v4.1-flash"}
	s := newCoolServer(t)
	head := []byte(`{"error":{"type":"AccessDenied","message":"Free quota exhausted, use free tier only"}}`)

	if !hopFatal(http.StatusForbidden, head) {
		t.Fatal("额度耗尽的 403 必须被当成该跳不可用")
	}
	reason, d := s.coolDurationFor(hop, http.StatusForbidden, head)
	if reason != "quota" {
		t.Fatalf("reason = %q，想要 quota", reason)
	}
	if d != quotaCooldown {
		t.Fatalf("冷却 %v，想要 %v", d, quotaCooldown)
	}

	s.markCoolingFor(hop, d)
	if !s.cooling(hop) {
		t.Fatal("冷却后该跳应被判为冷却中")
	}
	if left := time.Until(s.cool[hopKey(hop)]); left < time.Hour {
		t.Fatalf("冷却窗口只剩 %v，额度类必须按天冷却", left)
	}
}

// 普通死跳（模型退役）仍然是默认 30 分钟，不能被额度规则误伤。
func TestFatalWithoutQuotaKeepsDefaultCooldown(t *testing.T) {
	hop := alias.Hop{Channel: "OC", Upstream: "kimi-k3-free"}
	s := newCoolServer(t)
	head := []byte(`{"error":{"message":"Model moonshotai/kimi-k3-free has been retired on 2026-10-27"}}`)

	reason, d := s.coolDurationFor(hop, http.StatusBadRequest, head)
	if reason != "fatal" || d != hopCooldown {
		t.Fatalf("reason=%q d=%v，想要 fatal / %v", reason, d, hopCooldown)
	}
}

// 额度类冷却与普通冷却共用冷却表，键必须区分开：QW 那一跳冷冷不会连累同型号的
// 付费跳（键含 channel/upstream/proxy）。
func TestQuotaCoolingIsPerHop(t *testing.T) {
	s := newCoolServer(t)
	qw := alias.Hop{Channel: "QW", Upstream: "deepseek-v4.1-flash"}
	oc := alias.Hop{Channel: "OC", Upstream: "deepseek-v4.1-flash"}

	s.markCoolingFor(qw, quotaCooldown)
	if !s.cooling(qw) {
		t.Fatal("QW 应处于冷却中")
	}
	if s.cooling(oc) {
		t.Fatal("同型号的 OC 跳不该被 QW 的额度冷却连累")
	}
}
