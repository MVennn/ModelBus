package router

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"zgate/internal/logx"
)

// 这段代码补的是「等上游响应头」那段空窗。
//
// 2026-11-10 的账：客户端（DSH）把「连上了、却迟迟不见首字节」当传输故障，一旦断开会
// 自己重试；而上游此刻其实还在算。zgate 过去是「等 12/25 秒没响应头就判这一跳沉默」，
// 判死的动作是回 502 —— 客户端看到 5xx 又重试一次，同一个问题在上游被算了两遍，
// 用户看到的就是「后台明明在跑 token，本地却断开了又跑一次」。
//
// 判死权已经交回上游（channelPolicy 里 headerTimeoutSec = -1）。剩下这半件：
// 上游要 60 秒才给响应头时，这 60 秒里客户端一个字节都收不到，仍然会自己判死。
//
// earlySSEWriter 就在这段空窗里先交卷：流式请求过了 earlyCommitMs 还没人 WriteHeader，
// 就自己写 200 + text/event-stream，此后每 earlyKeepaliveSec 写一行 SSE 注释心跳
// （": zgate keepalive"，对任何合规 SSE 客户端都是无操作）。等上游真给出结果：
//   - 成功 → 正文接着往这条已经打开的流里写，首字照常到达；
//   - 失败 → 不再回一个客户端早就放弃的状态码，改写一条流内 error 事件再收尾。
//
// 只对流式请求生效：非流式请求要的是一个确定的 JSON + 状态码，提前交卷等于骗人。
// earlyCommitMs 之内上游就回话的（绝大多数情况）完全走老路径，状态码原样透出。

const (
	// sseKeepaliveLine 是心跳行：SSE 注释，任何合规解析器都会忽略，但足以证明连接还活着。
	sseKeepaliveLine = ": zgate keepalive\n\n"
	// sseEarlyMaxTrapped 是被扣下的错误体最多留多少字节 —— 只为从 JSON 里捞出 message
	// 回给客户端，不是要把错误体转发出去。
	sseEarlyMaxTrapped = 4096
)

// earlyStats 是提前交卷的观测计数。为什么要它：提前交卷是当天唯一「全量生效、零观测」
// 的功能 —— 它一旦出错就是「客户端拿到 200 却什么都没有」，而日志里连它有没有开过
// 都查不出来。/health 的 early 段与下面几行日志就是这条链的读数。
//
// 五个计数的语义（互不重叠）：
//
//	wrapped       被包的流式 chat 请求数（分母）
//	passed        窗口内上游就回头，按普通响应透出（说明窗口选得够大）
//	committed     真正提前交卷的次数（上游在窗口内一个头都没给）
//	keepalives    交卷后补的心跳行总数
//	failed_after  交卷后上游失败、被迫改写成流内 error 的次数（交卷的代价）
type earlyStats struct {
	wrapped     atomic.Int64
	passed      atomic.Int64
	committed   atomic.Int64
	keepalives  atomic.Int64
	failedAfter atomic.Int64
}

func newEarlyStats() *earlyStats { return &earlyStats{} }

// view 给 /health 用。window 传「当前实际生效」的窗口（0 = 已关闭），
// 让读数自己说明配置状态，不必再去翻 zgate.json 对照。
func (st *earlyStats) view(window time.Duration, keepalive time.Duration) map[string]any {
	if st == nil {
		return map[string]any{"enabled": false}
	}
	return map[string]any{
		"enabled":           window > 0,
		"window_ms":         window.Milliseconds(),
		"keepalive_s":       int(keepalive.Seconds()),
		"wrapped":           st.wrapped.Load(),
		"passed_in_window":  st.passed.Load(),
		"committed":         st.committed.Load(),
		"keepalives":        st.keepalives.Load(),
		"failed_after_wait": st.failedAfter.Load(),
	}
}

// earlySSEWriter 是个会「提前交卷」的 ResponseWriter 中间层。
// 约定：只有在 handler 正阻塞等上游响应头时才会从后台读 hdr，所以 hdr 不再单独加锁。
type earlySSEWriter struct {
	dst     http.ResponseWriter
	flusher http.Flusher

	mu        sync.Mutex
	hdr       http.Header
	committed bool   // 响应头已经交给 dst
	early     bool   // 是我们提前交的卷（而不是下游自己写的状态码）
	failed    bool   // 已经写过流内 error，后续写入一律丢弃
	swallow   bool   // 下游在提前交卷后又想写错误状态码，body 被扣下
	status    int    // 被扣下的状态码
	trapped   []byte // 被扣下的错误体（截断到 sseEarlyMaxTrapped）

	stop chan struct{}
	once sync.Once

	// 观测：stats 为 nil 时（旧测试直接 newEarlySSEWriter）什么都不记。
	stats *earlyStats
	log   *logx.Logger
	model string
	// window / windowKeepalive 只用于日志文案：交卷那一刻打「等了多久、之后几秒一跳」。
	window          time.Duration
	windowKeepalive time.Duration
}

func newEarlySSEWriter(dst http.ResponseWriter) *earlySSEWriter {
	f, _ := dst.(http.Flusher)
	return &earlySSEWriter{dst: dst, flusher: f, hdr: http.Header{}, stop: make(chan struct{})}
}

// attach 接上观测与日志。刻意不做进构造函数：早先的测试按两参数构 writer，
// 加参数会把它们一起改掉，而这些测试验的是「流语义」不是「观测」。
func (e *earlySSEWriter) attach(stats *earlyStats, log *logx.Logger, model string) {
	e.stats = stats
	e.log = log
	e.model = model
	if stats != nil {
		stats.wrapped.Add(1)
	}
}

func (e *earlySSEWriter) Header() http.Header { return e.hdr }

func (e *earlySSEWriter) WriteHeader(code int) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.failed {
		return
	}
	if !e.committed {
		// 空窗内上游就回了话：完全按老样子透出，状态码不打折。
		e.commitLocked(code, false)
		return
	}
	// 已经交过 200（无论谁交的），再想改状态码只能走流内 error。
	if code >= 300 {
		if !e.swallow || code > e.status {
			e.status = code
		}
		e.swallow = true
	}
}

func (e *earlySSEWriter) Write(b []byte) (int, error) {
	n := len(b)
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.failed {
		return n, nil
	}
	if e.swallow {
		if room := sseEarlyMaxTrapped - len(e.trapped); room > 0 {
			if len(b) > room {
				b = b[:room]
			}
			e.trapped = append(e.trapped, b...)
		}
		return n, nil
	}
	if !e.committed {
		e.commitLocked(http.StatusOK, false)
	}
	return e.dst.Write(b)
}

// Flush 让 earlySSEWriter 继续满足 http.Flusher：doForwardWith / bridgeChunkWriter
// 都会按接口断言拿 flusher。还没交卷时调 Flush 等于隐式 200，与 net/http 的语义一致。
func (e *earlySSEWriter) Flush() {
	e.mu.Lock()
	if e.failed {
		e.mu.Unlock()
		return
	}
	if !e.committed {
		e.commitLocked(http.StatusOK, false)
	}
	f := e.flusher
	e.mu.Unlock()
	if f != nil {
		f.Flush()
	}
}

func (e *earlySSEWriter) commitLocked(code int, early bool) {
	if !early && !e.committed && e.stats != nil {
		// 走这里 = 窗口内上游就回头了，说明窗口没白等，也没交虚假的 200。
		e.stats.passed.Add(1)
	}
	for k, vs := range e.hdr {
		for _, v := range vs {
			e.dst.Header().Add(k, v)
		}
	}
	if early {
		// 交卷时下游还没设过头，这里必须自己把 SSE 三件套立起来；
		// Content-Length 要删掉 —— 后面写多少字节只有上游知道，留着会让写端报
		// "wrote more than the declared Content-Length" 并直接断流。
		h := e.dst.Header()
		h.Set("Content-Type", "text/event-stream; charset=utf-8")
		h.Set("Cache-Control", "no-cache")
		h.Set("Connection", "keep-alive")
		h.Set("X-Accel-Buffering", "no")
		h.Del("Content-Length")
		h.Del("Content-Encoding")
	}
	e.dst.WriteHeader(code)
	e.committed = true
	e.early = early
}

// start 起看门狗：commitAfter 到点还没交卷就自己交；之后按 keepalive 补心跳。
func (e *earlySSEWriter) start(commitAfter, keepalive time.Duration) {
	if commitAfter <= 0 {
		return
	}
	if keepalive <= 0 {
		keepalive = 10 * time.Second
	}
	e.window = commitAfter
	e.windowKeepalive = keepalive
	go func() {
		timer := time.NewTimer(commitAfter)
		defer timer.Stop()
		select {
		case <-e.stop:
			return
		case <-timer.C:
		}
		if !e.commitEarly() {
			return
		}
		ticker := time.NewTicker(keepalive)
		defer ticker.Stop()
		for {
			select {
			case <-e.stop:
				return
			case <-ticker.C:
				if !e.ping() {
					return
				}
			}
		}
	}()
}

func (e *earlySSEWriter) commitEarly() bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.committed || e.failed {
		return false
	}
	e.commitLocked(http.StatusOK, true)
	if e.flusher != nil {
		e.flusher.Flush()
	}
	if e.stats != nil {
		e.stats.committed.Add(1)
	}
	if e.log != nil {
		// 这一行是「提前交卷真的发生了」的唯一现场证据：后面若客户端报
		// 「200 但没内容」，按这条的时间戳去查上游那一跳的结局即可。
		e.log.Infof("[early] 上游 %v 内没给响应头，先对客户端交卷 200（model=%s，心跳 %v）",
			e.window, e.model, e.windowKeepalive)
	}
	return true
}

func (e *earlySSEWriter) ping() bool {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.failed {
		return false
	}
	if !e.committed {
		return true
	}
	if _, err := io.WriteString(e.dst, sseKeepaliveLine); err != nil {
		if e.log != nil {
			e.log.Warnf("[early] 交卷后写心跳失败，客户端大概已经走了（model=%s）：%v", e.model, err)
		}
		return false
	}
	if e.stats != nil {
		e.stats.keepalives.Add(1)
	}
	if e.flusher != nil {
		e.flusher.Flush()
	}
	return true
}

// finish 由 serveHTTP 在返回前调用：提前交过卷、且下游最后想说的是错误，
// 这时把错误改写成流内事件 —— 客户端要的是「这条流怎么了」，不是一个它等不到的状态码。
func (e *earlySSEWriter) finish() {
	e.stopPings()
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.failed || !e.committed || !e.early || !e.swallow {
		return
	}
	if e.stats != nil {
		e.stats.failedAfter.Add(1)
	}
	if e.log != nil {
		// 这是提前交卷的代价：客户端早已收到 200，只剩流内 error 能说话。
		e.log.Warnf("[early] 交卷后上游才失败，收尾改写成流内 error（model=%s status=%d）：%s",
			e.model, e.status, e.errorMessageLocked())
	}
	e.writeErrorLocked(e.errorMessageLocked(), e.status)
}

// fail 给 panic 兜底用：提前交过卷就写流内 error，否则回一个正常的状态码。
func (e *earlySSEWriter) fail(status int, msg string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.failed {
		return
	}
	if !e.committed {
		body, _ := json.Marshal(errorBody(msg, "proxy_error"))
		e.dst.Header().Set("Content-Type", "application/json; charset=utf-8")
		e.dst.Header().Set("Content-Length", strconv.Itoa(len(body)))
		e.dst.WriteHeader(status)
		_, _ = e.dst.Write(body)
		if e.flusher != nil {
			e.flusher.Flush()
		}
		e.failed = true
		return
	}
	if !e.early {
		return
	}
	if msg == "" {
		msg = "upstream failed with status " + strconv.Itoa(status)
	}
	e.writeErrorLocked(msg, status)
}

func (e *earlySSEWriter) stopPings() { e.once.Do(func() { close(e.stop) }) }

func (e *earlySSEWriter) errorMessageLocked() string {
	if len(e.trapped) > 0 {
		var probe struct {
			Error struct {
				Message string `json:"message"`
			} `json:"error"`
			Message string `json:"message"`
		}
		if err := json.Unmarshal(e.trapped, &probe); err == nil {
			if probe.Error.Message != "" {
				return probe.Error.Message
			}
			if probe.Message != "" {
				return probe.Message
			}
		}
	}
	return "upstream failed with status " + strconv.Itoa(e.status)
}

func (e *earlySSEWriter) writeErrorLocked(msg string, status int) {
	if msg == "" {
		msg = "upstream failed with status " + strconv.Itoa(status)
	}
	payload, err := json.Marshal(map[string]any{"error": map[string]any{
		"message": msg,
		"type":    "upstream_error",
		"code":    status,
	}})
	if err != nil {
		payload = []byte(`{"error":{"message":"upstream failed","type":"upstream_error"}}`)
	}
	_, _ = io.WriteString(e.dst, "data: "+string(payload)+"\n\n")
	_, _ = io.WriteString(e.dst, "data: [DONE]\n\n")
	if e.flusher != nil {
		e.flusher.Flush()
	}
	e.failed = true
}
