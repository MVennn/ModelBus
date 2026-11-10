package router

import (
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"zgate/internal/config"
)

// probeReasoningStreamDeadline：上游整段静默时必须到点返回，不能挂死。
func TestProbeReasoningStreamDeadlineTimesOut(t *testing.T) {
	pr, pw := io.Pipe()
	defer pw.Close()

	start := time.Now()
	verdict, buffered, timedOut := probeReasoningStreamDeadline(pr, 32768, 80*time.Millisecond)
	elapsed := time.Since(start)
	if !timedOut {
		t.Fatalf("静默流应判 timedOut，got verdict=%v buffered=%d", verdict, len(buffered))
	}
	if verdict != streamUndetermined {
		t.Fatalf("超时判定应为 streamUndetermined，got %v", verdict)
	}
	if buffered != nil {
		t.Fatalf("超时不应保留缓冲字节，got %d 字节", len(buffered))
	}
	if elapsed > time.Second {
		t.Fatalf("超时控制失效，等了 %v", elapsed)
	}
	// 关掉写端，探针 goroutine 才会从 Read 上解开并退出（泄漏会让 -race 报错）。
	_ = pw.CloseWithError(io.EOF)
}

// probeReasoningStreamDeadline：正常流不能因为套了上限就丢字节或改判定。
func TestProbeReasoningStreamDeadlinePassesThrough(t *testing.T) {
	verdict, buffered, timedOut := probeReasoningStreamDeadline(strings.NewReader(guardPlainSSE()), 32768, 2*time.Second)
	if timedOut {
		t.Fatal("明文流不应超时")
	}
	if verdict != streamPlaintext {
		t.Fatalf("判定应为 streamPlaintext，got %v", verdict)
	}
	if !strings.Contains(string(buffered), "Considering the task") {
		t.Fatalf("缓冲字节丢了：%q", string(buffered))
	}
}

// timeoutFront 起一个伪造后端：第 n 次调用交给 write(n, w) 自己决定节奏。
type timeoutFront struct {
	mu    sync.Mutex
	calls int
}

func newTimeoutFront(t *testing.T, guard config.ReasoningGuard, model, upstreamName string,
	write func(n int, w http.ResponseWriter, r *http.Request)) (*httptest.Server, *timeoutFront, string) {
	t.Helper()
	st := &timeoutFront{}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		st.mu.Lock()
		st.calls++
		n := st.calls
		st.mu.Unlock()
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
		write(n, w, r)
	}))
	t.Cleanup(upstream.Close)

	mapJSON := fmt.Sprintf(`{"models":{"%s":{"channel":"OC","upstream":"%s","base":"%s","protocol":"chat"}}}`, model, upstreamName, upstream.URL)
	srv, log := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.ReasoningGuard = guard
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)
	return front, st, log.Path()
}

// 核心回归：上游思考阶段整段静默（加密分流那一路）时，探针到点就换连接重抽，
// 而不是等满一整段思考（真机实测 11 s / 61 s）才判得出来。
func TestReasoningGuardSilentStreamProbesWithDeadline(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, MaxRetries: 1, MaxProbeBytes: 32768,
		ProbeSeconds: 1, GiveUpAfter: 2, GiveUpForSeconds: 600, InjectNotice: true,
	}
	front, st, logPath := newTimeoutFront(t, guard, "Iceman", "iceman-contributor-free",
		func(n int, w http.ResponseWriter, _ *http.Request) {
			body := guardPlainSSE()
			if n == 1 {
				// 第一发：思考阶段完全静默，远超探针上限才吐加密流。
				time.Sleep(1500 * time.Millisecond)
				body = guardEncryptedSSE()
			}
			_, _ = io.WriteString(w, body)
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}
		})

	start := time.Now()
	payload := guardRequest(t, front, guardHighBody)
	elapsed := time.Since(start)

	if !strings.Contains(payload, "Considering the task") {
		t.Fatalf("重抽后没拿到明文思考流：%s", payload)
	}
	if strings.Contains(payload, "春天是") {
		t.Fatalf("第一发的加密正文泄漏到了客户端：%s", payload)
	}
	if elapsed > 2500*time.Millisecond {
		t.Fatalf("探针没有按上限换连接，整轮耗时 %v", elapsed)
	}
	if st.calls != 2 {
		t.Fatalf("上游调用次数 = %d, want 2", st.calls)
	}
	raw, err := os.ReadFile(logPath)
	if err != nil {
		t.Fatalf("读日志失败：%v", err)
	}
	if !strings.Contains(payload, "本次思考探测超时") {
		t.Fatalf("放行时应说明是探测超时而不是「只回加密」：\n%s", payload)
	}
	if !strings.Contains(string(raw), "内没有可判定的思考信号（上游静默）") {
		t.Fatalf("日志里没有静默重抽记录：\n%s", string(raw))
	}
}

// 窗口期：重抽预算花完且连续给不出明文思考的模型进跳过表，后续请求不再探测，
// 直接放行原始流 + 可读提示（思考看不到，但正文照常流）。
func TestReasoningGuardSkipWindowPassesThroughFast(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, MaxRetries: 1, MaxProbeBytes: 32768,
		ProbeSeconds: 1, GiveUpAfter: 1, GiveUpForSeconds: 600, InjectNotice: true,
	}
	front, st, _ := newTimeoutFront(t, guard, "Iceman", "iceman-contributor-free",
		func(n int, w http.ResponseWriter, _ *http.Request) {
			if n == 1 {
				time.Sleep(1500 * time.Millisecond)
			} else {
				time.Sleep(100 * time.Millisecond)
			}
			_, _ = io.WriteString(w, guardEncryptedSSE())
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}
		})

	// 第一轮：探针超时 → 重抽一次（达上限，直接放行原始流）→ 记入跳过表。
	first := guardRequest(t, front, guardHighBody)
	if !strings.Contains(first, "本次思考探测超时") {
		t.Fatalf("放行时应注入可读提示：%s", first)
	}
	if !strings.Contains(first, "春天是") {
		t.Fatalf("放行时不能吞掉上游正文：%s", first)
	}

	// 第二轮：应在跳过期内直接放行，不再等探针上限。
	start := time.Now()
	second := guardRequest(t, front, guardHighBody)
	elapsed := time.Since(start)
	if elapsed > 800*time.Millisecond {
		t.Fatalf("跳过期内不该再探测，整轮耗时 %v", elapsed)
	}
	if st.calls != 3 {
		t.Fatalf("跳过期内只应发一次上游请求，累计期望 3 次，got %d", st.calls)
	}
	if !strings.Contains(second, "该模型近期思考拿不到明文") {
		t.Fatalf("跳过期内也要给可读提示：%s", second)
	}
}

// 跳过期必须能自己恢复：到期后要重新探测，一旦上游切回明文就正常放行并清掉计数，
// 否则一次窗口期会把该模型永久降级成「不探测」。
func TestReasoningGuardSkipWindowExpiresAndReprobes(t *testing.T) {
	guard := config.ReasoningGuard{
		Enabled: true, MaxRetries: 1, MaxProbeBytes: 32768,
		ProbeSeconds: 2, GiveUpAfter: 1, GiveUpForSeconds: 1, InjectNotice: true,
	}
	front, st, _ := newTimeoutFront(t, guard, "Iceman", "iceman-contributor-free",
		func(n int, w http.ResponseWriter, _ *http.Request) {
			if n <= 3 {
				_, _ = io.WriteString(w, guardEncryptedSSE())
			} else {
				_, _ = io.WriteString(w, guardPlainSSE())
			}
			if f, ok := w.(http.Flusher); ok {
				f.Flush()
			}
		})

	// 第一轮：加密判定 → 重抽到上限 → 放行并进跳过表。
	if got := guardRequest(t, front, guardHighBody); !strings.Contains(got, "春天是") {
		t.Fatalf("放行时不能吞掉上游正文：%s", got)
	}
	// 第二轮：跳过期内直接放行。
	if got := guardRequest(t, front, guardHighBody); !strings.Contains(got, "该模型近期思考拿不到明文") {
		t.Fatalf("跳过期内应给可读提示：%s", got)
	}
	// 等跳过期到点，第三轮应重新探测并拿到明文。
	time.Sleep(1100 * time.Millisecond)
	start := time.Now()
	third := guardRequest(t, front, guardHighBody)
	if !strings.Contains(third, "Considering the task") {
		t.Fatalf("跳过期到期后应重新探测并拿到明文思考：%s", third)
	}
	if strings.Contains(third, "该模型近期思考拿不到明文") {
		t.Fatalf("到期后不该再提示跳过：%s", third)
	}
	if st.calls != 4 {
		t.Fatalf("期望 4 次上游请求（1+1+2），got %d（整轮 %v）", st.calls, time.Since(start))
	}
}
