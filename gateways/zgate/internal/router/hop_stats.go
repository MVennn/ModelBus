package router

import (
	"sort"
	"sync"
	"sync/atomic"

	"zgate/internal/alias"
)

// hopCounters 是一跳的调用结果计数。全部用原子类型：这些埋点都在请求热路径上，
// 每跳每请求最多打几次，加锁会让 /health 与转发争同一把锁。
type hopCounters struct {
	try     atomic.Int64
	ok      atomic.Int64
	busy    atomic.Int64
	e5xx    atomic.Int64
	silent  atomic.Int64
	nofirst atomic.Int64
}

// hopStats 是「每一跳最近到底行不行」的观测表。
//
// 为什么需要：/health.race 只记竞速跳（at != nil）的首块耗时，串行链一行都看不到，
// 而 Gemini-AIS 就是串行链（11-11 起 3 跳）。3.8 最近失败了几次、失败是「忙」还是「不发头」，
// 过去只能翻日志；按次计费的链上，这直接决定「还值不值得继续押 3.8 当首选」。
//
// 只做观测，不参与任何决策；进程重启清空，不落盘。
type hopStats struct {
	mu sync.Mutex
	m  map[string]*hopCounters
}

func newHopStats() *hopStats { return &hopStats{m: map[string]*hopCounters{}} }

// get 懒建一跳的计数器。跳数是有限的（几十条），不设上限回收。
func (h *hopStats) get(hop alias.Hop) *hopCounters {
	k := hopKey(hop)
	h.mu.Lock()
	c := h.m[k]
	if c == nil {
		c = &hopCounters{}
		h.m[k] = c
	}
	h.mu.Unlock()
	return c
}

// view 输出可直接塞进 /health 的 JSON：键与 hopKey 一致（渠道|上游|代理），
// 名字排过序，方便人读也方便 diff。
func (h *hopStats) view() map[string]any {
	h.mu.Lock()
	keys := make([]string, 0, len(h.m))
	for k := range h.m {
		keys = append(keys, k)
	}
	h.mu.Unlock()
	sort.Strings(keys)
	out := make(map[string]any, len(keys))
	for _, k := range keys {
		h.mu.Lock()
		c := h.m[k]
		h.mu.Unlock()
		if c == nil {
			continue
		}
		out[k] = map[string]int64{
			"try":            c.try.Load(),
			"ok":             c.ok.Load(),
			"busy":           c.busy.Load(),
			"e5xx":           c.e5xx.Load(),
			"silent":         c.silent.Load(),
			"no_first_block": c.nofirst.Load(),
		}
	}
	return out
}

// 下面五个是热路径入口，nil 表时静默（测试里构造的 Server 可能没装表）。
func (s *Server) hopTry(hop alias.Hop) {
	if s.hops != nil {
		s.hops.get(hop).try.Add(1)
	}
}

func (s *Server) hopOK(hop alias.Hop) {
	if s.hops != nil {
		s.hops.get(hop).ok.Add(1)
	}
}

func (s *Server) hopBusy(hop alias.Hop) {
	if s.hops != nil {
		s.hops.get(hop).busy.Add(1)
	}
}

func (s *Server) hopE5xx(hop alias.Hop) {
	if s.hops != nil {
		s.hops.get(hop).e5xx.Add(1)
	}
}

func (s *Server) hopSilent(hop alias.Hop) {
	if s.hops != nil {
		s.hops.get(hop).silent.Add(1)
	}
}

func (s *Server) hopNoFirstBlock(hop alias.Hop) {
	if s.hops != nil {
		s.hops.get(hop).nofirst.Add(1)
	}
}
