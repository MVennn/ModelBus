package router

import (
	"crypto/subtle"
	"io"
	"net"
	"net/http"
	"net/http/pprof"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"zgate/internal/alias"
)

// ---------------------------------------------------------------- 管理面鉴权

// isLoopbackAddr 判断连接来源是不是本机回环（RemoteAddr 可能带端口）。
func isLoopbackAddr(remoteAddr string) bool {
	host := remoteAddr
	if h, _, err := net.SplitHostPort(remoteAddr); err == nil {
		host = h
	}
	host = strings.Trim(host, "[]")
	if host == "" {
		return false
	}
	ip := net.ParseIP(host)
	if ip == nil {
		return false
	}
	return ip.IsLoopback()
}

// isLoopbackOrigin 判断 Origin 头是不是本机来源。
func isLoopbackOrigin(origin string) bool {
	u, err := url.Parse(origin)
	if err != nil {
		return false
	}
	return isLoopbackAddr(u.Host)
}

// adminToken 取管理口令：配置优先，其次环境变量（由 config.applyDefaults 注入）。
// 空值 = 不要求口令，但仍要求「回环 + X-Zgate-Admin 头」。
func (s *Server) adminToken() string {
	if cfg := s.Config(); cfg != nil {
		return strings.TrimSpace(cfg.AdminToken)
	}
	return ""
}

// adminGuard 把管理面从「谁都能 POST」收紧成三条同时成立：
//
//  1. 连接来自回环地址 —— 网关只绑 127.0.0.1，这条兜住「有人把 listen 改成
//     0.0.0.0 之后管理面跟着暴露」的情况；
//  2. 必须带 X-Zgate-Admin 头 —— 浏览器跨站表单与 <img>/<form> 这类简单请求
//     加不了自定义头，而 2026-11 之前 /admin/reload 没有任何校验，任意网页
//     都能对它发一个 text/plain POST 让网关重读配置；
//  3. 配了 adminToken 时再校验 X-Zgate-Token（或 Authorization: Bearer），
//     常量时间比较，给「同机多用户 / 别的进程也想调」留一道门。
//
// 返回 false 时响应已经写好，调用方直接 return。
func (s *Server) adminGuard(w http.ResponseWriter, r *http.Request) bool {
	if !isLoopbackAddr(r.RemoteAddr) {
		writeJSON(w, 403, errorBody("admin endpoints are loopback-only", "forbidden"))
		return false
	}
	if strings.TrimSpace(r.Header.Get("X-Zgate-Admin")) == "" {
		writeJSON(w, 403, errorBody("missing X-Zgate-Admin header (blocks cross-site POST)", "forbidden"))
		return false
	}
	if origin := strings.TrimSpace(r.Header.Get("Origin")); origin != "" && !isLoopbackOrigin(origin) {
		writeJSON(w, 403, errorBody("cross-origin admin request rejected", "forbidden"))
		return false
	}
	if token := s.adminToken(); token != "" {
		got := strings.TrimSpace(r.Header.Get("X-Zgate-Token"))
		if got == "" {
			got = strings.TrimSpace(strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer "))
		}
		if subtle.ConstantTimeCompare([]byte(got), []byte(token)) != 1 {
			writeJSON(w, 403, errorBody("bad admin token", "forbidden"))
			return false
		}
	}
	return true
}

// ---------------------------------------------------------------- 只读管理端点

// hopState 给一跳的当前状态：整渠道禁用 / 冷却 / 静默 / 正常。
// 排查「为什么这次没走首选」时，/admin/explain 一行就能回答。
func (s *Server) hopState(hop alias.Hop) string {
	if s.channelOff(hop.Channel) {
		return "channel_off"
	}
	key := hopKey(hop)
	now := time.Now()
	s.coolMu.Lock()
	defer s.coolMu.Unlock()
	if until, ok := s.cool[key]; ok && now.Before(until) {
		return "cool_until_" + until.Format("15:04:05")
	}
	if until, ok := s.silence[key]; ok && now.Before(until) {
		return "silent_until_" + until.Format("15:04:05")
	}
	return "ready"
}

// adminRoutes 输出整张路由表：每个模型一条，带链跳、渠道、协议、价格与当前状态。
// 控制台（7872）与排查脚本不必再去解析 model-alias-map.json，也不必猜
// 「这跳现在是不是在冷却」—— 那是进程内状态，文件里没有。
func (s *Server) adminRoutes(w http.ResponseWriter) {
	s.refreshAliases()
	targets := s.aliases.Targets()
	names := make([]string, 0, len(targets))
	for name := range targets {
		names = append(names, name)
	}
	sort.Strings(names)
	models := make([]map[string]any, 0, len(names))
	for _, name := range names {
		t := targets[name]
		protocol := t.Protocol
		if protocol == "" {
			protocol = "chat"
		}
		hops := make([]map[string]any, 0, len(t.Chain)+1)
		if len(t.Chain) == 0 {
			hops = append(hops, map[string]any{
				"channel": t.Channel, "upstream": t.Upstream, "base": t.Base,
				"protocol": protocol, "price": t.Price, "proxy": "",
				"state": s.hopState(alias.Hop{Channel: t.Channel, Upstream: t.Upstream}),
			})
		} else {
			for _, h := range t.Chain {
				hp := h.Protocol
				if hp == "" {
					hp = protocol
				}
				hops = append(hops, map[string]any{
					"channel": h.Channel, "upstream": h.Upstream, "base": h.Base,
					"protocol": hp, "price": h.Price, "proxy": maskProxy(h.Proxy),
					"state": s.hopState(h),
				})
			}
		}
		models = append(models, map[string]any{
			"model": name, "group": t.Group, "protocol": protocol, "price": t.Price,
			"fallbacks": t.Fallbacks, "legacy_ids": t.LegacyIDs, "hops": hops,
		})
	}
	writeJSON(w, 200, map[string]any{
		"ok": true, "revision": s.aliases.Revision(), "total": len(models), "models": models,
	})
}

// adminExplain 回答「这个名字最后会打到哪」：命中别名给链，没命中给前缀兜底，
// 并附上守卫是否覆盖它、当前哪一跳在冷却。
func (s *Server) adminExplain(w http.ResponseWriter, r *http.Request) {
	model := strings.TrimSpace(r.URL.Query().Get("model"))
	s.refreshAliases()
	payload := map[string]any{"ok": true, "model": model}
	guard := s.Config().ReasoningGuard
	payload["guard"] = map[string]any{
		"enabled": guard.Enabled, "force_effort": guard.ForceEffort,
		"models": guard.Models, "force_effort_models": guard.ForceEffortModels,
	}
	if target, ok := s.aliases.Resolve(model); ok {
		payload["resolved"] = true
		payload["target"] = target
		payload["fallback_channel"] = fallbackChannelFor(model, true)
		payload["states"] = s.routeStates(target)
	} else {
		payload["resolved"] = false
		payload["fallback_channel"] = fallbackChannelFor(model, true)
	}
	writeJSON(w, 200, payload)
}

// routeStates 是 adminExplain 用的每跳状态列表（与 adminRoutes 同一口径）。
func (s *Server) routeStates(t alias.Target) []map[string]any {
	out := make([]map[string]any, 0, len(t.Chain)+1)
	if len(t.Chain) == 0 {
		return append(out, map[string]any{
			"channel": t.Channel, "upstream": t.Upstream,
			"state": s.hopState(alias.Hop{Channel: t.Channel, Upstream: t.Upstream}),
		})
	}
	for _, h := range t.Chain {
		out = append(out, map[string]any{
			"channel": h.Channel, "upstream": h.Upstream, "proxy": maskProxy(h.Proxy),
			"state": s.hopState(h),
		})
	}
	return out
}

// adminStats 是进程运行态的一次性快照：请求计数 / 耗时分布 / 慢请求样本 /
// 别名版本 / 子进程状态。与 /health 的分工：/health 是「能不能用」的健康位，
// 这里是「跑得怎么样」的账本。
func (s *Server) adminStats(w http.ResponseWriter) {
	payload := map[string]any{
		"ok":       true,
		"version":  s.version(),
		"draining": s.draining.Load(),
		"stats":    s.stats.view(),
		"alias": map[string]any{
			"path": s.aliases.Path(), "models": s.aliases.Count(), "revision": s.aliases.Revision(),
		},
		"cooling": s.coolingCount(),
	}
	if s.sup != nil {
		payload["children"] = s.sup.States()
	}
	writeJSON(w, 200, payload)
}

// adminDrain 把「换版」变成一次可控的收尾：先标记 draining，再等手上正在跑的
// 请求走完（最多 wait_ms），最后如实返回还差几个。
//
// 为什么需要它：deploy-zgate.ps1 过去直接 Stop-Process -Force，正在流式输出的
// 请求会被硬切，客户端看到的是「连接重置」而不是一次干净的收尾；换成新版之后，
// 换版脚本可以先 POST 这里，等 inflight 归零再停进程。
//
// 注意：这条请求自己也算在 inflight 里，所以判据是「<= 1」。
// 幂等：重复调用只是重复确认，不会拒绝服务，也不会把 draining 撤销。
func (s *Server) adminDrain(w http.ResponseWriter, r *http.Request) {
	wait := 5 * time.Second
	if v := strings.TrimSpace(r.URL.Query().Get("wait_ms")); v != "" {
		if ms, err := strconv.Atoi(v); err == nil && ms >= 0 {
			wait = time.Duration(ms) * time.Millisecond
		}
	}
	if wait > 30*time.Second {
		wait = 30 * time.Second
	}
	s.SetDraining()
	if s.stats == nil {
		writeJSON(w, 200, map[string]any{"ok": true, "draining": true, "inflight": 0, "waited_ms": 0, "timed_out": false})
		return
	}
	startedAt := time.Now()
	deadline := startedAt.Add(wait)
	for {
		inflight := s.stats.inflight.Load()
		if inflight <= 1 {
			writeJSON(w, 200, map[string]any{
				"ok": true, "draining": true, "inflight": 0,
				"waited_ms": time.Since(startedAt).Milliseconds(), "timed_out": false,
			})
			return
		}
		if !time.Now().Before(deadline) {
			writeJSON(w, 200, map[string]any{
				"ok": true, "draining": true, "inflight": inflight - 1,
				"waited_ms": time.Since(startedAt).Milliseconds(), "timed_out": true,
			})
			return
		}
		select {
		case <-r.Context().Done():
			return
		case <-time.After(50 * time.Millisecond):
		}
	}
}

// logTailWindow 是一次最多回看的日志字节数。日志按行切，窗口切在行中间时
// 会丢掉半行，由 tailFileLines 负责对齐到下一个换行。
const logTailWindow = 512 * 1024

// adminLogs 返回日志尾部若干行（GET /admin/logs?lines=200&filter=req）。
//
// 为什么要开这个端点：控制台在别的进程里，过去只能拿到日志路径，读不到内容 ——
// 面板里想看「刚才那次请求怎么失败的」得让人手动开文件。这里让网关自己吐尾部，
// 面板与 grep 看到的是同一份内容。
func (s *Server) adminLogs(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	n := 200
	if v := strings.TrimSpace(q.Get("lines")); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			n = parsed
		}
	}
	if n > 2000 {
		n = 2000
	}
	filter := strings.TrimSpace(q.Get("filter"))
	path := ""
	if s.log != nil {
		path = s.log.Path()
	}
	lines, truncated, err := tailFileLines(path, n, filter)
	if err != nil {
		writeJSON(w, 500, errorBody("read log: "+err.Error(), "proxy_error"))
		return
	}
	writeJSON(w, 200, map[string]any{
		"ok": true, "path": path, "lines": lines, "count": len(lines), "truncated": truncated,
	})
}

// tailFileLines 读文件尾部最多 logTailWindow 字节，按行切，返回最后 n 行。
// filter 非空时只保留包含该子串的行（大小写敏感，够用且不会误伤）。
// truncated 表示「窗口外还有更早的内容」或「过滤后仍有超过 n 行」。
func tailFileLines(path string, n int, filter string) ([]string, bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, false, err
	}
	defer f.Close()
	st, err := f.Stat()
	if err != nil {
		return nil, false, err
	}
	var start int64
	if st.Size() > logTailWindow {
		start = st.Size() - logTailWindow
	}
	if start > 0 {
		if _, err := f.Seek(start, io.SeekStart); err != nil {
			return nil, false, err
		}
	}
	buf, err := io.ReadAll(f)
	if err != nil {
		return nil, false, err
	}
	text := string(buf)
	if start > 0 {
		// 窗口切在行中间：丢掉那半行，否则首行会是半截日志。
		if i := strings.IndexByte(text, '\n'); i >= 0 {
			text = text[i+1:]
		} else {
			text = ""
		}
	}
	out := make([]string, 0, n)
	truncated := start > 0
	for _, ln := range strings.Split(strings.TrimRight(text, "\n"), "\n") {
		if ln == "" {
			continue
		}
		if filter != "" && !strings.Contains(ln, filter) {
			continue
		}
		out = append(out, ln)
	}
	if len(out) > n {
		out = out[len(out)-n:]
		truncated = true
	}
	return out, truncated, nil
}

// metrics 输出 Prometheus 文本（GET /metrics）。
//
// 只做轻校验：必须来自回环、且不是跨站请求。不带 X-Zgate-Admin 是有意的 ——
// 抓取端（Prometheus / 自写脚本）不该为了一个只读指标端去改请求头，
// 而「回环 + 同源」已经挡住了浏览器侧的全部跨站路径。
func (s *Server) metrics(w http.ResponseWriter, r *http.Request) {
	if !isLoopbackAddr(r.RemoteAddr) {
		writeJSON(w, 403, errorBody("metrics is loopback-only", "forbidden"))
		return
	}
	if origin := strings.TrimSpace(r.Header.Get("Origin")); origin != "" && !isLoopbackOrigin(origin) {
		writeJSON(w, 403, errorBody("cross-origin metrics request rejected", "forbidden"))
		return
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
	w.WriteHeader(200)
	_, _ = io.WriteString(w, s.metricsText())
}

// adminPprof 把标准库的 pprof 处理器挂在管理面下（/admin/pprof/*）。
// 排查内存问题必须有堆快照：/admin/pprof/heap 能直接看出 32 KB 流缓冲、
// 别名目录、桥接 map 各占多少，不必再靠估算。
func (s *Server) adminPprof(w http.ResponseWriter, r *http.Request) {
	name := strings.TrimPrefix(r.URL.Path, "/admin/pprof")
	name = strings.Trim(name, "/")
	switch name {
	case "", "index":
		pprof.Index(w, r)
	case "profile":
		pprof.Profile(w, r)
	case "trace":
		pprof.Trace(w, r)
	case "cmdline":
		pprof.Cmdline(w, r)
	case "symbol":
		pprof.Symbol(w, r)
	default:
		pprof.Handler(name).ServeHTTP(w, r)
	}
}
