package router

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"sync"
	"time"
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
}

func newEarlySSEWriter(dst http.ResponseWriter) *earlySSEWriter {
	f, _ := dst.(http.Flusher)
	return &earlySSEWriter{dst: dst, flusher: f, hdr: http.Header{}, stop: make(chan struct{})}
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
		return false
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
