package router

import (
	"fmt"
	"math"
	"net/http"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// latBuckets 是请求总耗时（秒）的分桶上界，/metrics 的 le 标签直接用它。
var latBuckets = []float64{0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120, 300}

// slowReq 是「超过 5 秒」的最近若干次请求，供 /admin/stats 回看。
// 网关过去只有 /health 的冷却/计数，没有「刚才那次为什么慢」的原始样本。
type slowReq struct {
	At     string `json:"at"`
	ID     string `json:"id,omitempty"`
	Path   string `json:"path"`
	Model  string `json:"model"`
	Status int    `json:"status"`
	MS     int64  `json:"ms"`
}

// reqStats 是进程级的请求计数与耗时分布。全部原子或单锁短临界区：
// 埋点就在 serveHTTP 的收尾处，不能和转发抢锁。
type reqStats struct {
	started  time.Time
	reqs     atomic.Int64
	errors   atomic.Int64
	inflight atomic.Int64
	bytesIn  atomic.Int64
	bytesOut atomic.Int64
	status   [6]atomic.Int64 // 下标 = status/100（1xx..5xx）

	mu     sync.Mutex
	lat    [latSlots]int64
	sumSec float64 // 全部请求耗时之和（秒），供 histogram 的 _sum
	slow   []slowReq
}

// latSlots 必须等于 len(latBuckets)+1（数组长度得是常量，不能用 len()）。
// 多出来的最后一格是「超过所有上界」的溢出桶。
const latSlots = 14

func newReqStats() *reqStats { return &reqStats{started: time.Now()} }

// begin / done 维护在飞请求数（/health.stats.inflight 与 zgate_inflight_requests）。
// 两个都 nil 安全：测试里裸构造 &Server{cfg: ...} 时不至于空指针。
func (st *reqStats) begin() {
	if st == nil {
		return
	}
	st.inflight.Add(1)
}

func (st *reqStats) done() {
	if st == nil {
		return
	}
	st.inflight.Add(-1)
}

// respRecorder 是包在 ResponseWriter 外面的一层薄壳：只记「最终状态码」与
// 「真实吐给客户端的字节数」，其它能力（Flush / Unwrap）原样透传。
//
// 为什么要包：提前交卷（earlySSEWriter）会把状态码改成 200，直接看上游响应码
// 会漏掉「上游 5xx、客户端拿到 200 流内报错」这一整类；只有出口这一层知道
// 客户端实际拿到什么。Flush 必须实现，否则流式路径 w.(http.Flusher) 断言失败，
// 整条 SSE 会退化成「攒满才发」。
type respRecorder struct {
	http.ResponseWriter
	code  int
	wrote bool
	bytes int64
}

func (r *respRecorder) WriteHeader(code int) {
	if r.wrote {
		return
	}
	r.code, r.wrote = code, true
	r.ResponseWriter.WriteHeader(code)
}

func (r *respRecorder) Write(b []byte) (int, error) {
	if !r.wrote {
		r.code, r.wrote = http.StatusOK, true
	}
	n, err := r.ResponseWriter.Write(b)
	r.bytes += int64(n)
	return n, err
}

func (r *respRecorder) Flush() {
	if !r.wrote {
		r.code, r.wrote = http.StatusOK, true
	}
	if f, ok := r.ResponseWriter.(http.Flusher); ok {
		f.Flush()
	}
}

// Unwrap 让 http.ResponseController 之类的新 API 能拿到原始 writer。
func (r *respRecorder) Unwrap() http.ResponseWriter { return r.ResponseWriter }

// statusCode 返回客户端实际拿到的状态码；什么都没写等于 200（net/http 的隐含语义）。
func (r *respRecorder) statusCode() int {
	if !r.wrote || r.code == 0 {
		return http.StatusOK
	}
	return r.code
}

// observe 记一次已完成的请求：状态码、字节数、耗时落桶，慢请求留样本。
// id 是请求号（可能为空），只进慢请求表：
// 客户端把响应头 X-Zgate-Request-Id 贴出来就能在这里对上同一条记录。
func (st *reqStats) observe(path, model, id string, status int, in, out int64, d time.Duration) {
	if st == nil {
		return
	}
	st.reqs.Add(1)
	st.bytesIn.Add(in)
	st.bytesOut.Add(out)
	if status >= 500 {
		st.errors.Add(1)
	}
	if status >= 100 && status < 600 {
		st.status[status/100].Add(1)
	}
	sec := d.Seconds()
	bucket := sort.SearchFloat64s(latBuckets, sec)
	st.mu.Lock()
	st.lat[bucket]++
	st.sumSec += sec
	if d >= 5*time.Second {
		st.slow = append(st.slow, slowReq{
			At:     time.Now().Format("15:04:05"),
			ID:     id,
			Path:   path,
			Model:  model,
			Status: status,
			MS:     d.Milliseconds(),
		})
		if len(st.slow) > 20 {
			st.slow = st.slow[len(st.slow)-20:]
		}
	}
	st.mu.Unlock()
}

// quantile 从累计桶里取分位（返回毫秒，向上取到桶上界）。
func (st *reqStats) quantile(q float64) int64 {
	st.mu.Lock()
	defer st.mu.Unlock()
	var total int64
	for _, n := range st.lat {
		total += n
	}
	if total == 0 {
		return 0
	}
	// 向上取整：total=3、q=0.5 时 1.5 应当取第 2 个样本，截断会把分位报小。
	want := int64(math.Ceil(float64(total) * q))
	if want < 1 {
		want = 1
	}
	var acc int64
	for i, n := range st.lat {
		acc += n
		if acc >= want {
			if i >= len(latBuckets) {
				return int64(latBuckets[len(latBuckets)-1] * 1000)
			}
			return int64(latBuckets[i] * 1000)
		}
	}
	return 0
}

// view 是 /health.stats 与 /admin/stats 共用的 JSON 视图。
func (st *reqStats) view() map[string]any {
	if st == nil {
		return map[string]any{}
	}
	up := time.Since(st.started).Seconds()
	reqs := st.reqs.Load()
	out := map[string]any{
		"requests":     reqs,
		"errors":       st.errors.Load(),
		"inflight":     st.inflight.Load(),
		"bytes_in":     st.bytesIn.Load(),
		"bytes_out":    st.bytesOut.Load(),
		"uptime_s":     int(up),
		"latency_ms":   map[string]int64{"p50": st.quantile(0.5), "p90": st.quantile(0.9), "p99": st.quantile(0.99)},
		"status_class": map[string]int64{"1xx": st.status[1].Load(), "2xx": st.status[2].Load(), "3xx": st.status[3].Load(), "4xx": st.status[4].Load(), "5xx": st.status[5].Load()},
	}
	if up > 0 {
		out["rps"] = float64(reqs) / up
	}
	st.mu.Lock()
	slow := make([]slowReq, len(st.slow))
	copy(slow, st.slow)
	st.mu.Unlock()
	out["slow"] = slow
	return out
}

// metricLabel 转义 Prometheus 标签值（反斜杠、双引号、换行）。
func metricLabel(v string) string {
	if !strings.ContainsAny(v, "\\\"\n") {
		return v
	}
	r := strings.NewReplacer("\\", "\\\\", "\"", "\\\"", "\n", "\\n")
	return r.Replace(v)
}

// metricsText 把计数器渲染成 Prometheus 文本格式（0.0.4）。
// 目的不是替换 /health，而是让「内存 / 耗时 / 每跳成败」能被外部按时间序列采集 ——
// 在此之前，这些数只存在于 /health 的瞬时快照里，没有任何历史。
func (s *Server) metricsText() string {
	var b strings.Builder
	line := func(format string, args ...any) { fmt.Fprintf(&b, format+"\n", args...) }

	st := s.stats
	line("# HELP zgate_requests_total Requests handled by the front door.")
	line("# TYPE zgate_requests_total counter")
	if st != nil {
		line("zgate_requests_total %d", st.reqs.Load())
		line("# TYPE zgate_request_errors_total counter")
		line("zgate_request_errors_total %d", st.errors.Load())
		line("# TYPE zgate_inflight_requests gauge")
		line("zgate_inflight_requests %d", st.inflight.Load())
		line("# TYPE zgate_request_bytes_in_total counter")
		line("zgate_request_bytes_in_total %d", st.bytesIn.Load())
		line("# TYPE zgate_response_bytes_out_total counter")
		line("zgate_response_bytes_out_total %d", st.bytesOut.Load())
		line("# TYPE zgate_request_duration_seconds histogram")
		st.mu.Lock()
		var cum int64
		for i, n := range st.lat {
			cum += n
			if i >= len(latBuckets) {
				line("zgate_request_duration_seconds_bucket{le=\"+Inf\"} %d", cum)
				continue
			}
			line("zgate_request_duration_seconds_bucket{le=\"%g\"} %d", latBuckets[i], cum)
		}
		sum := st.sumSec
		st.mu.Unlock()
		line("zgate_request_duration_seconds_sum %.6f", sum)
		line("zgate_request_duration_seconds_count %d", st.reqs.Load())
		for i := 1; i < 6; i++ {
			line("zgate_responses_total{class=\"%dxx\"} %d", i, st.status[i].Load())
		}
	}
	if s.hops != nil {
		line("# TYPE zgate_hop_total counter")
		snap := s.hops.snapshot()
		keys := make([]string, 0, len(snap))
		for k := range snap {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			c := snap[k]
			label := metricLabel(k)
			for _, name := range []string{"try", "ok", "busy", "e5xx", "silent", "no_first_block"} {
				line("zgate_hop_total{hop=\"%s\",result=\"%s\"} %d", label, name, c[name])
			}
		}
	}
	if s.aliases != nil {
		line("# TYPE zgate_alias_models gauge")
		line("zgate_alias_models %d", s.aliases.Count())
		line("# TYPE zgate_alias_revision gauge")
		line("zgate_alias_revision %d", s.aliases.Revision())
	}
	if s.sup != nil {
		line("# TYPE zgate_child_up gauge")
		states := s.sup.States()
		names := make([]string, 0, len(states))
		for name := range states {
			names = append(names, name)
		}
		sort.Strings(names) // map 遍历无序，排序后两次抓取可直接 diff
		for _, name := range names {
			up := 0
			if m, ok := states[name].(map[string]any); ok {
				if v, ok := m["state"].(string); ok && (v == "running" || v == "up") {
					up = 1
				}
			}
			line("zgate_child_up{child=\"%s\"} %d", metricLabel(name), up)
		}
	}
	line("# TYPE zgate_draining gauge")
	draining := 0
	if s.draining.Load() {
		draining = 1
	}
	line("zgate_draining %d", draining)
	return b.String()
}
