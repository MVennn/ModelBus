package router

import (
	"context"
	"io"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"zgate/internal/alias"
)

// 这些用例钉的是「首块对冲」的三块地基：什么算真内容、谁抢到写端、谁被取消。
// 它们不碰网络，跑起来是毫秒级；网关行为本身由 .work/gemini-ais-accept.py 实测。

func TestHasContentDelta(t *testing.T) {
	cases := []struct {
		name string
		body string
		want bool
	}{
		{"role-only", "data: {\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}\n\n", false},
		{"empty-delta", "data: {\"choices\":[{\"delta\":{}}]}\n\n", false},
		{"done", "data: [DONE]\n\n", false},
		{"content", "data: {\"choices\":[{\"delta\":{\"content\":\"hi\"}}]}\n\n", true},
		{"reasoning", "data: {\"choices\":[{\"delta\":{\"reasoning_content\":\"想\"}}]}\n\n", true},
		{"gemini-parts", "data: {\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"hi\"}]}}]}\n\n", true},
		{"plain-json", "{\"choices\":[]}", false},
	}
	for _, c := range cases {
		if got := hasContentDelta([]byte(c.body)); got != c.want {
			t.Errorf("%s: got %v want %v", c.name, got, c.want)
		}
	}
}

func TestRaceGateCancelsLosers(t *testing.T) {
	gate := &raceGate{}
	var mu sync.Mutex
	cancelled := []int{}
	reg := func(id int) context.CancelFunc {
		return func() {
			mu.Lock()
			cancelled = append(cancelled, id)
			mu.Unlock()
		}
	}
	gate.register(0, reg(0))
	gate.register(1, reg(1))
	if !gate.claim(0) {
		t.Fatal("第一路应当抢到写端")
	}
	if gate.winnerID() != 0 {
		t.Fatalf("赢家应为 0，实际 %d", gate.winnerID())
	}
	if len(cancelled) != 1 || cancelled[0] != 1 {
		t.Fatalf("应当只取消输家 1，实际 %v", cancelled)
	}
	// 抢闸门之后再登记的那一路要立刻被掐掉，不能让它白打一次上游。
	called := false
	gate.register(2, func() { called = true })
	if !called {
		t.Fatal("赢家已定后登记的跳应当立即取消")
	}
	if !gate.claim(0) {
		t.Fatal("同一个赢家重复 claim 应当幂等放行")
	}
	if gate.claim(1) {
		t.Fatal("输家 claim 必须失败")
	}
}

func TestRaceWriterOnlyWinnerWrites(t *testing.T) {
	rec := httptest.NewRecorder()
	gate := &raceGate{}
	winner := newRaceWriter(rec, gate, 0)
	loser := newRaceWriter(rec, gate, 1)
	winner.Header().Set("X-Hop", "winner")
	loser.Header().Set("X-Hop", "loser")

	// 抢闸门的规则是「谁先拿到谁赢」：赢家先到，输家的 WriteHeader 必须被判失败。
	winner.WriteHeader(200)
	loser.WriteHeader(200)
	if _, err := loser.Write([]byte("loser-body")); err != nil {
		t.Fatalf("输家写入应当静默成功: %v", err)
	}
	if _, err := winner.Write([]byte("winner-body")); err != nil {
		t.Fatalf("赢家写入失败: %v", err)
	}
	if rec.Body.String() != "winner-body" {
		t.Fatalf("响应体只应有赢家内容，实际 %q", rec.Body.String())
	}
	if rec.Header().Get("X-Hop") != "winner" {
		t.Fatalf("响应头只应有赢家的，实际 %q", rec.Header().Get("X-Hop"))
	}
}

func TestRaceWriterIgnoresErrorStatus(t *testing.T) {
	rec := httptest.NewRecorder()
	gate := &raceGate{}
	rw := newRaceWriter(rec, gate, 0)
	rw.WriteHeader(503)
	if gate.isClaimed() {
		t.Fatal("5xx 不该抢闸门")
	}
	if rec.Body.Len() != 0 || rec.Code != 200 {
		t.Fatalf("5xx 不该写任何东西，实际 code=%d body=%q", rec.Code, rec.Body.String())
	}
}

func TestPeekFirstContentSkipsRoleFrame(t *testing.T) {
	body := "data: {\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}\n\n" +
		"data: {\"choices\":[{\"delta\":{\"content\":\"hi\"}}]}\n\n"
	buf, ok := peekFirstContent(strings.NewReader(body), time.Second, context.Background())
	if !ok {
		t.Fatal("有内容 delta 的流应当判定成功")
	}
	if string(buf) != body {
		t.Fatalf("已消费的字节必须原样返回供拼回，实际 %q", string(buf))
	}
}

// stallReader 表示「连接还在、但正文不再下发」的上游：读就永久阻塞。
// 不能直接用 io.Pipe 先写一帧再读 —— Pipe 是同步的，Write 会被自己堵死。
type stallReader struct{ ch chan struct{} }

func (s *stallReader) Read([]byte) (int, error) {
	<-s.ch
	return 0, io.EOF
}

func TestPeekFirstContentTimesOutOnSilentStream(t *testing.T) {
	// 只给一帧 role，然后整段静默：这正是 3.6 那种「200 但十几秒没有正文」的形态。
	r := &stallReader{ch: make(chan struct{})}
	defer close(r.ch)
	pr := io.MultiReader(strings.NewReader("data: {\"choices\":[{\"delta\":{\"role\":\"assistant\"}}]}\n\n"), r)
	start := time.Now()
	_, ok := peekFirstContent(pr, 300*time.Millisecond, context.Background())
	elapsed := time.Since(start)
	if ok {
		t.Fatal("只有 role 帧不该判定成功")
	}
	if elapsed > 2*time.Second {
		t.Fatalf("看门狗应当在 300ms 量级返回，实际 %v", elapsed)
	}
}

// 静默冷却和真冷却是两张表：前者可以被「全链静默」的兜底整体清掉，
// 后者（429 / 5xx / 死跳 / 额度）绝不能被清 —— 清了就会变成
// 「清冷却 → 再撞 429 → 再清」的死循环，2026-11-10 实测把整条链打成连片 502。
func TestSilenceCoolingClearedButRealCoolingKept(t *testing.T) {
	s := &Server{cool: map[string]time.Time{}, silence: map[string]time.Time{}}
	silentHop := alias.Hop{Channel: "GM", Upstream: "ais-gemini-3.6-flash"}
	limitedHop := alias.Hop{Channel: "GM", Upstream: "ais-gemini-3.8-flash"}

	s.markSilence(silentHop, time.Minute)
	s.markCoolingFor(limitedHop, time.Minute)
	if !s.cooling(silentHop) || !s.cooling(limitedHop) {
		t.Fatal("两张表都该让 cooling() 判真")
	}
	if !s.clearSilence(silentHop) {
		t.Fatal("静默冷却应当可被兜底清掉")
	}
	if s.cooling(silentHop) {
		t.Fatal("清掉之后不该再算冷却")
	}
	if s.clearSilence(limitedHop) {
		t.Fatal("真冷却不该被静默兜底清掉")
	}
	if !s.cooling(limitedHop) {
		t.Fatal("429/5xx 冷却必须保留")
	}
}

// rankedChain 决定「谁先发车」：真出过首块的跳按毫秒升序在前，没观测过的
// 保持声明顺序（3.8 优先的口径），有失败记录的排最后。这条规则直接决定
// 第二次请求的首字是 2 秒还是 15 秒，所以用断言钉死。
func TestRankedChainPrefersProvenFastHop(t *testing.T) {
	chain := []alias.Hop{
		{Channel: "GM", Upstream: "ais-gemini-3.8-flash"},
		{Channel: "GM", Upstream: "ais-gemini-3.6-flash"},
		{Channel: "GM", Upstream: "ais-gemini-3.5-flash-lite"},
		{Channel: "GM", Upstream: "ais-gemini-3-flash-preview"},
	}
	s := &Server{raceStat: map[string]hopStatSnap{
		hopKeyForLog(chain[0]): {FirstBlockMs: 0, Verdict: "Service Unavailable 503"},
		hopKeyForLog(chain[1]): {FirstBlockMs: 0, Verdict: "首块超时（没有内容 delta）"},
		hopKeyForLog(chain[2]): {FirstBlockMs: 2910, Verdict: "ok"},
	}}
	got := s.rankedChain(chain)
	// lite 有实测首块 → 第一；preview 无观测 → 按声明顺序排在「无观测」档；
	// 3.8/3.6 有失败记录 → 最后，且两者之间保持声明顺序。
	want := []int{2, 3, 0, 1}
	if len(got) != len(want) {
		t.Fatalf("rankedChain 长度不对: %v", got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("发车顺序不对: got %v want %v", got, want)
		}
	}
}

// 两个都有实测首块时，快的那个必须排在前面。
func TestRankedChainOrdersProvenHopsByLatency(t *testing.T) {
	chain := []alias.Hop{
		{Channel: "GM", Upstream: "ais-gemini-3.5-flash-lite"},
		{Channel: "GM", Upstream: "ais-gemini-3-flash-preview"},
	}
	s := &Server{raceStat: map[string]hopStatSnap{
		hopKeyForLog(chain[0]): {FirstBlockMs: 2910, Verdict: "ok"},
		hopKeyForLog(chain[1]): {FirstBlockMs: 1500, Verdict: "ok"},
	}}
	got := s.rankedChain(chain)
	if got[0] != 1 || got[1] != 0 {
		t.Fatalf("应当 preview 先发车: %v", got)
	}
}
