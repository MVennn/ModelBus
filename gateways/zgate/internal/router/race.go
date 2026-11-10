package router

// 本文件是「首块对冲」的实现：一条链的前几跳可以同时在路上，谁先给出
// **真实内容首块**谁赢，其余各路立刻取消。它只对 zgate.json 里显式配了
// channelPolicy 的渠道生效（当前只有 GM，见 docs/MODEL-PROVIDERS.md §4.11），
// 没有配置的渠道逐字节保持原来的串行链行为。
//
// 为什么需要：catiecli 中转的 ais-gemini-3.8-flash 常态化返回 503 high demand，
// 而且这条 503 要 4-14 秒才吐出来（2026-11-10 实测）。串行链遇到这种上游，
// 首字时间 = 所有失败跳的耗时之和，用户体验就是「卡住」。对冲把「等死」变成
// 「并行试下一跳」，首字时间回到第一跳真实能出字的那一跳的速度。

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"sort"
	"sync"
	"time"

	"zgate/internal/alias"
	"zgate/internal/config"
)

// raceGate 决定「哪一跳赢了这次请求」。只有赢家能往客户端写字节；
// 其余尝试的写入全部被丢弃，它们的上游请求立刻被取消。
type raceGate struct {
	mu      sync.Mutex
	claimed bool
	winner  int
	cancels []gateCancel
	// lastErr 是链上出现过的最小失败状态码（0 = 没有）。
	lastErr int
}

type gateCancel struct {
	id     int
	cancel context.CancelFunc
}

// register 登记一路尝试的取消函数。登记时已经有赢家的话说明这一路是后补的，
// 直接掐掉，别浪费上游额度。
func (g *raceGate) register(id int, cancel context.CancelFunc) {
	g.mu.Lock()
	g.cancels = append(g.cancels, gateCancel{id: id, cancel: cancel})
	claimed := g.claimed
	g.mu.Unlock()
	if claimed {
		cancel()
	}
}

// claim 抢写端：抢到的那一路负责把响应写完，其余各路被取消。
// 同一个 id 重复调用是幂等的（net/http 只认第一次 WriteHeader）。
func (g *raceGate) claim(id int) bool {
	g.mu.Lock()
	if g.claimed {
		won := g.winner == id
		g.mu.Unlock()
		return won
	}
	g.claimed = true
	g.winner = id
	victims := make([]context.CancelFunc, 0, len(g.cancels))
	for _, c := range g.cancels {
		if c.id != id {
			victims = append(victims, c.cancel)
		}
	}
	g.mu.Unlock()
	for _, cancel := range victims {
		cancel()
	}
	return true
}

func (g *raceGate) isClaimed() bool {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.claimed
}

// winnerID 返回赢家下标；没有赢家时返回 -1。
func (g *raceGate) winnerID() int {
	g.mu.Lock()
	defer g.mu.Unlock()
	if !g.claimed {
		return -1
	}
	return g.winner
}

// raceWriter 是每一路尝试私有的写端。它在 WriteHeader(2xx) 这一瞬间抢闸门：
// 抢到才把头和正文透给真正的 ResponseWriter，抢不到就把所有写入吞掉。
// Header() 返回私有 header，避免输的那一路把自己上游的响应头污染到赢家的响应上。
// noteErr 记下某一路的失败状态码。链全灭时用它决定回 4xx 还是 502：
// 上游明确说「403 key 池空」时，客户端该看到 403 与这句话，而不是笼统的 502。
func (g *raceGate) noteErr(code int) {
	if code < 300 {
		return
	}
	g.mu.Lock()
	if g.lastErr == 0 || code < g.lastErr {
		g.lastErr = code
	}
	g.mu.Unlock()
}

// errorStatus 返回链上出现过的最小失败状态码（0 = 没有）。
func (g *raceGate) errorStatus() int {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.lastErr
}

type raceWriter struct {
	dst     http.ResponseWriter
	gate    *raceGate
	id      int
	hdr     http.Header
	lost    bool
	claimed bool
}

func newRaceWriter(dst http.ResponseWriter, gate *raceGate, id int) *raceWriter {
	return &raceWriter{dst: dst, gate: gate, id: id, hdr: http.Header{}}
}

func (rw *raceWriter) Header() http.Header { return rw.hdr }

func (rw *raceWriter) WriteHeader(code int) {
	if code >= 300 {
		// 失败响应（4xx/5xx）不参与竞争：它既不该抢闸门，也不该写出任何字节，
		// 交给编排器决定下一跳；状态码记进闸门，链全灭时用来回真话。
		rw.gate.noteErr(code)
		rw.lost = true
		return
	}
	if !rw.gate.claim(rw.id) {
		rw.lost = true
		return
	}
	rw.claimed = true
	for key, values := range rw.hdr {
		rw.dst.Header()[key] = values
	}
	rw.dst.WriteHeader(code)
}

func (rw *raceWriter) Write(b []byte) (int, error) {
	if rw.lost || !rw.claimed {
		return len(b), nil
	}
	return rw.dst.Write(b)
}

// Flush 让 raceWriter 满足 http.Flusher：doForwardWith 会按接口断言拿 flusher。
func (rw *raceWriter) Flush() {
	if rw.lost || !rw.claimed {
		return
	}
	if f, ok := rw.dst.(http.Flusher); ok {
		f.Flush()
	}
}

// hasContentDelta 判断一段 SSE 缓冲里是否已经出现「真实内容」。
//
// 只看 data 行里 choice.delta.content / reasoning_content 非空，或者 Gemini 原生
// candidates[].content.parts[].text 非空。只有 role、只有 usage、"[DONE]"、
// 空 delta 一律不算 —— 上游常见「先回 200 + 一帧 role 然后十几秒不说话」，
// 把这种帧当首块就会把「空流」当成功，客户端干等（实测 3.6 有一次 14.24 秒）。
func hasContentDelta(buf []byte) bool {
	for {
		i := bytes.IndexByte(buf, '\n')
		if i < 0 {
			return false
		}
		line := bytes.TrimSpace(buf[:i])
		buf = buf[i+1:]
		if !bytes.HasPrefix(line, []byte("data:")) {
			continue
		}
		payload := bytes.TrimSpace(line[len("data:"):])
		if len(payload) == 0 || bytes.Equal(payload, []byte("[DONE]")) {
			continue
		}
		var probe struct {
			Choices []struct {
				Delta struct {
					Content   string `json:"content"`
					Reasoning string `json:"reasoning_content"`
				} `json:"delta"`
			} `json:"choices"`
			Candidates []struct {
				Content struct {
					Parts []struct {
						Text string `json:"text"`
					} `json:"parts"`
				} `json:"content"`
			} `json:"candidates"`
		}
		if err := json.Unmarshal(payload, &probe); err != nil {
			continue
		}
		for _, c := range probe.Choices {
			if c.Delta.Content != "" || c.Delta.Reasoning != "" {
				return true
			}
		}
		for _, c := range probe.Candidates {
			for _, part := range c.Content.Parts {
				if part.Text != "" {
					return true
				}
			}
		}
	}
}

// peekFirstContent 从流里读到「第一个真实内容块」为止，返回已经消费掉的字节
// （调用方要用 MultiReader 拼回去）以及是否读到。d <= 0 表示不等，直接放行。
//
// 为什么必须复制：读出来的是上游 body，之后要继续转发，不能丢。
func peekFirstContent(src io.Reader, d time.Duration, ctx context.Context) ([]byte, bool) {
	if d <= 0 {
		return nil, true
	}
	type readResult struct {
		data []byte
		err  error
	}
	ch := make(chan readResult, 8)
	stop := make(chan struct{})
	var stopOnce sync.Once
	defer stopOnce.Do(func() { close(stop) })
	go func() {
		buf := make([]byte, 16*1024)
		for {
			n, err := src.Read(buf)
			var data []byte
			if n > 0 {
				data = append([]byte(nil), buf[:n]...)
			}
			select {
			case ch <- readResult{data: data, err: err}:
			case <-stop:
				return
			case <-ctx.Done():
				return
			}
			if err != nil {
				return
			}
		}
	}()
	timer := time.NewTimer(d)
	defer timer.Stop()
	acc := make([]byte, 0, 8*1024)
	for {
		select {
		case rr := <-ch:
			if len(rr.data) > 0 {
				acc = append(acc, rr.data...)
				if hasContentDelta(acc) {
					return acc, true
				}
			}
			if rr.err != nil {
				return acc, false
			}
		case <-timer.C:
			return acc, false
		case <-ctx.Done():
			return acc, false
		}
	}
}

// attemptCtl 是一次「跳尝试」在竞争模式下的控制块；nil 表示老的非竞争路径。
type attemptCtl struct {
	// gate 为 nil 时表示「有首块看门狗但不竞争」（当前没有这种用法，保留位）。
	gate   *raceGate
	id     int
	policy config.ChannelPolicy
	hopTag string
	// hop 是这一路对应的跳，doForwardWith 判死时要用它上冷却。
	hop alias.Hop
}

// channelPolicy 取某渠道的策略；没配就返回零值（= 全关 = 老行为）。
func (s *Server) channelPolicy(channel string) config.ChannelPolicy {
	cfg := s.Config()
	if cfg == nil || cfg.ChannelPolicy == nil {
		return config.ChannelPolicy{}
	}
	return cfg.ChannelPolicy[channel]
}

// racePolicyFor 判断这条链要不要走对冲。要求：全链同属配置了 channelPolicy 的
// 渠道、全是原生 chat 协议（桥接跳有自己的写端，不参与竞争）、客户端要流式、
// 至少两跳、且策略里开了对冲或首块看门狗。
func (s *Server) racePolicyFor(t alias.Target, body []byte) (config.ChannelPolicy, bool) {
	if len(t.Chain) < 2 || !wantsStream(body) {
		return config.ChannelPolicy{}, false
	}
	cfg := s.Config()
	if cfg == nil || len(cfg.ChannelPolicy) == 0 {
		return config.ChannelPolicy{}, false
	}
	for _, hop := range t.Chain {
		proto := hop.Protocol
		if proto == "" {
			proto = t.Protocol
		}
		if proto == "" {
			proto = "chat"
		}
		if proto != "chat" {
			return config.ChannelPolicy{}, false
		}
		if _, ok := cfg.ChannelPolicy[hop.Channel]; !ok {
			return config.ChannelPolicy{}, false
		}
	}
	pol := cfg.ChannelPolicy[t.Chain[0].Channel]
	if pol.HedgeAfterMs <= 0 && pol.FirstBlockMs <= 0 {
		return config.ChannelPolicy{}, false
	}
	return pol, true
}

// rankedChain 决定竞速的**发车顺序**（不是降级链本身的顺序）。
//
// 为什么需要：catiecli 上 3.8/3.7 常态 503、3.6/3.5 常态「200 但十几秒不说话」，
// 真正能给首块的往往排在第五、第七跳。按声明顺序发车，用户每次都要先等前几跳
// 失败；按「上一轮实测谁真的秒出字」发车，第二次请求就能直接拿到 2-3 秒的首字。
//
// 分类（同级保持声明顺序）：
//
//	A. 最近一轮真出过首块（verdict=ok）—— 按首块毫秒升序，谁快谁先；
//	B. 没有任何观测 —— 信任声明顺序（3.8 优先的口径就体现在这里）；
//	C. 最近一轮是失败（503 / 首块超时 / 其他退回原因）—— 排最后，只在对冲余量里试。
func (s *Server) rankedChain(chain []alias.Hop) []int {
	stats := s.raceSnapshot()
	type entry struct {
		idx   int
		class int
		ms    int64
	}
	entries := make([]entry, 0, len(chain))
	for i, hop := range chain {
		snap, ok := stats[hopKeyForLog(hop)]
		switch {
		case !ok:
			entries = append(entries, entry{idx: i, class: 1})
		case snap.Verdict == "ok" && snap.FirstBlockMs > 0:
			entries = append(entries, entry{idx: i, class: 0, ms: snap.FirstBlockMs})
		default:
			entries = append(entries, entry{idx: i, class: 2})
		}
	}
	sort.SliceStable(entries, func(a, b int) bool {
		if entries[a].class != entries[b].class {
			return entries[a].class < entries[b].class
		}
		return entries[a].ms < entries[b].ms
	})
	out := make([]int, len(entries))
	for i, e := range entries {
		out[i] = e.idx
	}
	return out
}

// sameChannel 判断整条链是不是都落在同一个渠道上。
func sameChannel(chain []alias.Hop, channel string) bool {
	for _, hop := range chain {
		if hop.Channel != channel {
			return false
		}
	}
	return true
}

// firstLiveHop 找到链上第一个「现在真的能打」的跳：渠道没被禁用、这一跳不在
// 冷却里、有 key。竞赛从这里开始，避免把名额浪费在已知死跳上。
func (s *Server) firstLiveHop(chain []alias.Hop) int {
	for i, hop := range chain {
		if s.channelOff(hop.Channel) {
			continue
		}
		if s.cooling(hop) {
			continue
		}
		if s.keyset().For(hop.Channel) == "" {
			continue
		}
		return i
	}
	return -1
}

// raceChain 是竞争模式的编排器：先发第一跳，此后「一出失败就补下一跳」，
// 同时按 HedgerAfterMs 对冲；任何时候最多 MaxParallel 路在路上。
func (s *Server) raceChain(w http.ResponseWriter, r *http.Request, body []byte, model string, t alias.Target, path, search string, pol config.ChannelPolicy) {
	maxParallel := pol.MaxParallel
	if maxParallel <= 0 {
		maxParallel = 2
	}
	start := s.firstLiveHop(t.Chain)
	if start < 0 {
		// 全链都在冷却：软冷却（首块静默）只是省时间的优化，不该升级成「一定失败」，
		// 清掉再试一次。真冷却（429 / 5xx / 死跳 / 额度）一律保留 —— 清了会变成
		// 「清冷却 → 再撞 429 → 再清」的死循环，实测把整条链打成连片 502。
		cleared := 0
		for _, hop := range t.Chain {
			if s.clearSilence(hop) {
				cleared++
			}
		}
		if cleared > 0 {
			s.log.Infof("[race] 链上 %d 跳都在短冷却里，清掉后重试：%s", cleared, chainNames(t.Chain))
			start = s.firstLiveHop(t.Chain)
		}
	}
	if start < 0 {
		if ch := t.Chain[0].Channel; s.channelOff(ch) {
			// 渠道级故障（key 池空 / key 失效）已经摁住整条链：这时再判 502 会骗人，
			// 上游明确说的话（403 池空）才是用户该看到的。
			s.log.Warnf("[race] 渠道 %s 处于禁用窗口，直接回 503：%s", ch, chainNames(t.Chain))
			writeJSON(w, 503, errorBody("channel "+ch+" is paused after an upstream auth/pool error; retry shortly", "channel_paused"))
			return
		}
		s.log.Warnf("[race] 链上没有任何可用跳：%s", chainNames(t.Chain))
		writeJSON(w, 502, errorBody("all upstreams failed: "+chainNames(t.Chain), "proxy_error"))
		return
	}
	gate := &raceGate{}
	baseCtx, cancelAll := context.WithCancel(r.Context())
	defer cancelAll()

	resCh := make(chan int, len(t.Chain))
	launch := func(idx int) {
		ctx, cancel := context.WithCancel(baseCtx)
		gate.register(idx, cancel)
		rw := newRaceWriter(w, gate, idx)
		at := &attemptCtl{gate: gate, id: idx, policy: pol, hopTag: hopKeyForLog(t.Chain[idx]), hop: t.Chain[idx]}
		rr := r.WithContext(WithProxy(ctx, t.Chain[idx].Proxy))
		s.log.Infof("[race] 发出 %d/%d %s", idx+1, len(t.Chain), hopKeyForLog(t.Chain[idx]))
		go func() {
			s.attemptChain(rw, rr, body, model, t, path, search, idx, at)
			resCh <- idx
		}()
	}

	hedge := time.Duration(pol.HedgeAfterMs) * time.Millisecond
	if hedge <= 0 {
		hedge = time.Duration(pol.FirstBlockMs) * time.Millisecond
	}
	if hedge <= 0 {
		hedge = 1200 * time.Millisecond
	}

	// 发车顺序按「上一轮谁真的秒出字」排（rankedChain），不是降级链的声明顺序：
	// 没有观测过的跳仍按声明顺序（3.8 优先），有失败记录的跳排到最后。
	order := s.rankedChain(t.Chain)
	pos := 0
	live := 0
	launch(order[pos])
	pos++
	live++
	timer := time.NewTimer(hedge)
	defer timer.Stop()

	for {
		select {
		case idx := <-resCh:
			live--
			if gate.winnerID() == idx {
				// 赢家把整个响应写完了，这条请求结束。
				return
			}
			if gate.isClaimed() {
				// 已经有别的路在写；等它收工（它的 goroutine 回来时会命中上面的分支）。
				continue
			}
			if ch := t.Chain[idx].Channel; s.channelOff(ch) && sameChannel(t.Chain, ch) {
				// 这一跳把整条链（同一渠道）摁停了：剩下的跳没有意义，
				// 别让还在路上的那一路把首字拖到几十秒后才回错。
				cancelAll()
				if st := gate.errorStatus(); st >= 400 && st < 500 {
					writeJSON(w, st, errorBody("all upstreams failed: "+chainNames(t.Chain), "upstream_error"))
					return
				}
				writeJSON(w, 502, errorBody("all upstreams failed: "+chainNames(t.Chain), "proxy_error"))
				return
			}
			if live < maxParallel && pos < len(order) {
				launch(order[pos])
				pos++
				live++
				resetTimer(timer, hedge)
				continue
			}
			if live == 0 {
				if pos < len(order) {
					launch(order[pos])
					pos++
					live++
					resetTimer(timer, hedge)
					continue
				}
				s.log.Warnf("[race] 全部 %d 跳都没给出可用的首块：%s", len(t.Chain), chainNames(t.Chain))
				// 上游明确回过 4xx（例如 key 池空 403）就照原状态回，别把用户
				// 能看懂的「为什么」压成笼统 502。
				if st := gate.errorStatus(); st >= 400 && st < 500 {
					writeJSON(w, st, errorBody("all upstreams failed: "+chainNames(t.Chain), "upstream_error"))
					return
				}
				writeJSON(w, 502, errorBody("all upstreams failed: "+chainNames(t.Chain), "proxy_error"))
				return
			}
		case <-timer.C:
			if !gate.isClaimed() && live < maxParallel && pos < len(order) {
				launch(order[pos])
				pos++
				live++
			}
			resetTimer(timer, hedge)
		case <-r.Context().Done():
			return
		}
	}
}
