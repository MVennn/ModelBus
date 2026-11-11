// Package router is the HTTP front door on 127.0.0.1:7871.
//
// It is a behaviour-preserving port of tools/unified-router.js: the same alias
// map, the same prefix fallback, the same fallback chain for WorkBuddy regions
// and the same error envelopes, so ZCode's four chat providers keep working
// without touching provider_config.json.
package router

import (
	"bytes"
	"context"
	crand "crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"zgate/internal/alias"
	"zgate/internal/bridge"
	"zgate/internal/config"
	"zgate/internal/keys"
	"zgate/internal/logx"
	"zgate/internal/supervisor"
)

// Server holds the long-lived state of the front door.
type Server struct {
	cfgMu   sync.RWMutex
	cfg     *config.Config
	keys    keys.Set
	aliases *alias.Map
	sup     *supervisor.Supervisor
	client  *http.Client
	log     *logx.Logger
	started time.Time
	// 冷却表：一跳被判「这跳现在没用」（模型不存在 / 额度耗尽 / 欠费）后就跳过它一段时间。
	// 集合体的链路有几十跳，不记住这些死跳，每个请求都要先把它们撞一遍。
	coolMu sync.Mutex
	cool   map[string]time.Time
	// silence 是「200 但迟迟不吐正文」的软冷却，和 cool 分开存：它只是「这次先
	// 让别人说」，链上全在静默时可以被整体清掉重试；而 cool 里的 429/5xx/死跳
	// 真冷却绝不能被清，否则会变成「清冷却 → 再撞 429 → 再清」的死循环。
	silence map[string]time.Time
	// offMu/off 是「整渠道禁用」表：403 若是 key 无效/被封类错误（authFatal），
	// 这一渠道的所有跳一起停摆一段时间，不必等每个跳各自撞一遍 403。
	offMu sync.Mutex
	off   map[string]time.Time
	// raceMu/raceStat 记住每个竞速跳最近一次的首块耗时，供 /health 展示。
	// 只是观测，不参与决策；进程重启清空。
	raceMu   sync.Mutex
	raceStat map[string]hopStatSnap
	// guardMu/guardMem 是 reasoningGuard 的按模型学习表：记住哪些模型能拿到明文
	// 思考、哪些模型重抽多少次都只回加密。前者让守卫一直有效，后者在连续几轮
	// 全程加密后自动停手一段时间（省掉每轮白等几十秒），到期再重新探路。
	// 重启进程即清空，不落盘。
	guardMu  sync.Mutex
	guardMem map[string]*guardModelStat
	// headerWait 是流式请求「等上游响应头」的容忍上限；0 = 按配置
	// upstreamHeaderTimeoutSec 解析、再缺省按 upstreamHeaderTimeout 常量。单列成
	// 字段是为了让测试把它压到毫秒级，不必真等十几秒。
	headerWait time.Duration
	// earlyCommit / earlyPing 覆盖「提前交卷窗口」与「心跳间隔」，0 = 按配置。
	// 单列成字段是为了让测试压到毫秒级，不必真等 8 秒 / 10 秒。
	earlyCommit time.Duration
	earlyPing   time.Duration
	// serialMu/serialAt 给「本可对冲却退回串行」的提醒做去重（每链条签名 10 分钟一条）。
	serialMu sync.Mutex
	serialAt map[string]time.Time
	// early 是提前交卷的观测计数（包装数 / 交卷数 / 窗口内回头数 / 心跳数 / 流内报错数）。
	// 提前交卷本身是「对客户端撒谎：先说 200」，没有计数就没人能回答「它到底起了几次作用」
	// —— 这是 2026-11-10 复盘里唯一一项「全量生效却零观测」的功能。
	early *earlyStats
	// hops 是每跳的结果计数（try/ok/busy/e5xx/silent/no_first_block），只供 /health 看。
	// 与 /health.race 的区别：race 只覆盖竞速跳，hops 覆盖所有跳（串行链也有）。
	hops *hopStats
	// sem 是「上游语义」这一层的计数：忙了几次、剥思考参数重发几次、补了几次
	// 截断收口。这些分支都是 2026-11-11 新加的，没有计数就只能靠日志猜。
	sem *upstreamStats
}

// hopCooldown 是死跳的默认冷却时长；与额度窗口同一量级的短周期，够跨过一轮使用。
const hopCooldown = 30 * time.Minute

// rateLimitCooldown 是 429 的冷却时长。比死跳短得多：429 多半是瞬时 QPS 限制，
// 但每次都去撞它会让每个请求白付一次往返（实测 WorkBuddy 一跳今天被限流 182 次，
// 而 OC 只有 16 次），所以退避重试仍失败后先把它摘出一小段时间。
const rateLimitCooldown = 45 * time.Second

// rateLimitBackoff 是收到 429 后的就地退避：先睡一小会儿重试同一跳，
// 限流窗口通常不到 1 秒，这样多数突发根本不会让你看到失败。
const rateLimitBackoff = 700 * time.Millisecond

// statusRetryDelay 是上游回 500 后原地重试同一跳前的等待。
// 500 是上游自己的内部错，不需要像 429 那样等限流窗口过去；800ms 只是让
// 「瞬时抖动」那一类有足够时间恢复，又不至于把首字推后太多。
const statusRetryDelay = 800 * time.Millisecond

// transportRetryDelay 是「传输层失败」后重试同一跳前的等待。
// 这类失败（EOF / TLS 握手超时 / 连接被重置）说明请求多半没被上游受理，
// 换一次同一条腿往往就过了；等待只是给链路一个喘息窗口。
const transportRetryDelay = 300 * time.Millisecond

// upstreamHeaderTimeout 是「请求已经交给上游，但连响应头都不给」的忍耐上限。
// 只作用于流式请求：非流式上游往往要等整段生成完才发头，用同一档会误杀长回答。
// 2026-11-10 18:51 实测：catiecli 的 ais-gemini-3.8-flash 收下请求后 60 秒零字节，
// 客户端看到的就是「一分钟没有任何输出」，反代面板也没有记录（上游那边同样在等）。
// 串行链原本没有首块看门狗（那个只在竞速模式生效），整个请求会无限期挂住；
// 有了这个上限，沉默跳到点就被判死、立刻让位给下一跳。
//
// 2026-11-10 19:45 实测（同一天第二次收敛）：同一跳 ais-gemini-3.8-flash 每次都要
// 等满 60.241 秒才回 503 high demand，而哈基米 [福利]gemini-3.8-flash 直连 2.5-3.1 秒
// 就出首块。45 秒一档等于「每轮白等 45 秒」：8 跳按 maxParallel=2 轮转，
// 单次请求 3-4.5 分钟才有结果（用户实测 4 分 31 秒），期间 DSH 无首字节自动重试，
// 反代后台就出现两条「请求中」。降到 12 秒后同样的链最坏 4 轮 × 12 秒 ≈ 48 秒见分晓，
// 正常情况对冲到第二跳就 3 秒出字。12 秒仍有 4 倍余量（观测到的合法首头 2.5-3.1 秒），
// 也能被 zgate.json 的 upstreamHeaderTimeoutSec 覆盖，不用重新编译。
//
// 2026-11-10 20:05 实测（第三次收敛）：哈基米的同一个 [福利]gemini-3.8-flash 首头从
// 白天的 2.5-3.1 秒漂到 7.5-10.2 秒（同一 key、60KB 与 200KB 系统提示都试过）。
// 12 秒对它是 1.2-1.6 倍余量，赶上抖动就会把唯一能用的兜底跳切掉；而 catiecli 的
// 3.8 是「60 秒后才回 503」，窗口给多长都只是白等。一个全局值必然牺牲其中一边，
// 所以加了按渠道覆盖（channelPolicy[<渠道>].headerTimeoutSec）：GM 用 12 秒，
// HJ 用 25 秒。
// 2026-11-10 21:30（第四次收敛，方向反过来）：按渠道分窗口治不了根 —— 当天 GM 被判死
// 125 次（沉默 79 + 首块 46），其中上游真说过 503 的只有 7 次（5.3%）；HJ 判死 32 次，
// 一大半与 502 同秒返回。网关一判死就回 502 → 客户端 retryPolicy 命中 SERVER 必然重打
// → 上游那边又在跑 token → 用户看到「本地断开、又跑一次」。根因是把「上游慢」当成「上游死」。
// 结论：判死权归上游。HJ（与 QN 同级的普通供应商）headerTimeoutSec = -1 不设看门狗；
// GM 同样 -1，只用 hedgeAfterMs 18s 对冲（对冲不取消前一路，只多开一路）。
// 全局兜底 12s → 45s，只兜住「真的挂了」的渠道。见 docs/MODEL-PROVIDERS.md §4.11.3。
const upstreamHeaderTimeout = 12 * time.Second

// timeoutCooldown 是桥接上游「连上但不说话」超时后的冷却时长。
// 实测 Conatus 会静默到总超时，不冷却就会每个请求都再等一次。
const timeoutCooldown = 5 * time.Minute

// regionCooldown 是「地区受限」403 的冷却时长。这一跳没坏，是这条出口在这个国家
// 进不去（opencode.ai 按出口国拦 beam / gpt / muse）。出口归属地不会在几十秒内变，
// 所以按死跳同档冷却。2026-11-06 实况：beam-free 的链是 [直连, 机场孪生]，
// 直连那跳每次都 403 RegionError —— 10 分钟 359 个请求全先撞一次 403 再回落，
// 面板上就是一片「403 Rejected」。冷却键带 proxy（见 hopKey），同上游的机场孪生跳
// 是另一个键，兜底不会被吃掉；只有链里真有这条孪生跳时才冷却直连跳（proxyTwinAfter）。
const regionCooldown = 30 * time.Minute

// quotaCooldown 是「额度已经烧光」类 4xx 的冷却时长。它比死跳长得多：千问的
// 300 元/一年额度用完就是用完，不会在半小时内自己回来；按 30 分钟冷却，结果是
// 每半小时重撞一次 403 Free quota exhausted，白付一次往返。用 24h 把这一跳摁住，
// 等到额度续上或有人改配置再复活（进程重启会清空冷却表，等于手动复活开关）。
const quotaCooldown = 24 * time.Hour

// softCooldownFor 是「这跳暂时没用」的短冷却：政策没配就返回 0（老行为，
// 只有 504 会按 timeoutCooldown 冷却）。配了才给 5xx 也上冷却。
// 理由：catiecli 的 3.8/3.7 常态 503 high demand，但 503 不在 chainAccept 的
// 冷却名单里，于是每个请求都要先撞一遍、白等 4-14 秒。冷却 90 秒既跨过了
// 上游的需求窗口，又不会把真恢复的跳长期埋掉。
func (s *Server) softCooldownFor(channel string) time.Duration {
	secs := s.channelPolicy(channel).SoftCooldownSeconds
	if secs <= 0 {
		return 0
	}
	return time.Duration(secs) * time.Second
}

// silenceCooldownFor 是「首块静默」的短冷却，0 = 不冷却。
func (s *Server) silenceCooldownFor(channel string) time.Duration {
	secs := s.channelPolicy(channel).SilenceCooldownSeconds
	if secs <= 0 {
		return 0
	}
	return time.Duration(secs) * time.Second
}

// markSilence 记一条「这次静默」的软冷却，只写 silence 表。
func (s *Server) markSilence(hop alias.Hop, d time.Duration) {
	s.coolMu.Lock()
	s.silence[hopKey(hop)] = time.Now().Add(d)
	s.coolMu.Unlock()
}

// clearSilence 抹掉一跳的静默冷却。只在「整条链都在静默」时用作最后兜底：
// 软冷却只是省时间的优化，不能升级成一定失败。真冷却（429/5xx/死跳/额度）不动。
func (s *Server) clearSilence(hop alias.Hop) bool {
	s.coolMu.Lock()
	defer s.coolMu.Unlock()
	key := hopKey(hop)
	if _, ok := s.silence[key]; !ok {
		return false
	}
	delete(s.silence, key)
	return true
}

// poolCooldown 是「中转侧 Gemini key 池空了」的暂停时长。catiecli 池空时对
// 任何模型都回 403「没有可用的 Gemini API Key」，直到有人在它页面上传新 key。
// 这是分钟级的人工修复窗口，按 90 秒暂停足够：既不把渠道埋掉，也不让每个请求
// 都把整条链挨个撞一遍（每跳 1-3 秒）。
const poolCooldown = 90 * time.Second

// markChannelOffFor 按指定时长暂停整渠道；只对配了 channelPolicy 的渠道生效，
// 未配置的渠道行为逐字节不变（返回 0）。
func (s *Server) markChannelOffFor(channel string, d time.Duration) time.Duration {
	if _, ok := s.Config().ChannelPolicy[channel]; !ok {
		return 0
	}
	s.offMu.Lock()
	s.off[channel] = time.Now().Add(d)
	s.offMu.Unlock()
	return d
}

// poolDown 判断上游是不是「中转的 key 池空了」：catiecli 池空时所有模型都回
// 403「没有可用的 Gemini API Key，请先在「Gemini 密钥」页面上传」。这是渠道级
// 故障，换跳换模型都没用，必须按渠道暂停，不能当普通 403 逐跳重试。
func poolDown(status int, head []byte) bool {
	if status != 401 && status != 403 && status != 429 && status != 503 {
		return false
	}
	text := strings.ToLower(string(head))
	for _, marker := range []string{
		"没有可用的 gemini api key", "没有可用的 api key",
		"no available gemini api key", "no available api key",
	} {
		if strings.Contains(text, marker) {
			return true
		}
	}
	return false
}

// channelOff 判断整渠道是否处在「403 自动禁用」窗口里。
func (s *Server) channelOff(channel string) bool {
	s.offMu.Lock()
	defer s.offMu.Unlock()
	until, ok := s.off[channel]
	if !ok {
		return false
	}
	if time.Now().After(until) {
		delete(s.off, channel)
		return false
	}
	return true
}

// markChannelOff 按策略禁用整渠道；返回实际禁用时长（0 = 策略没开，不禁用）。
func (s *Server) markChannelOff(channel string) time.Duration {
	hours := s.channelPolicy(channel).AuthFailCooldownHours
	if hours <= 0 {
		return 0
	}
	d := time.Duration(hours) * time.Hour
	s.offMu.Lock()
	s.off[channel] = time.Now().Add(d)
	s.offMu.Unlock()
	return d
}

// hopStatSnap 是一个竞速跳的最近观测值：给 /health 看，也决定发车顺序。
type hopStatSnap struct {
	FirstBlockMs int64  `json:"firstBlockMs"`
	Verdict      string `json:"verdict"`
	At           string `json:"at"`
	// Seen 是这条观测的写入时刻，只在进程内用。观测过期后 rankedChain 会把
	// 这一跳当「没测过」重新给机会，避免一次失败被永远记住。
	Seen time.Time `json:"-"`
}

// 观测保鲜期。失败跳只记 10 分钟：上游 503 多是短时拥挤，过了这段时间要
// 重新试一次强跳，否则 3.8 恢复后也会被一直跳过（实测 21:32-21:47 有 15
// 分钟一次没碰过 3.8）。成功跳记 1 小时：排序靠它压首字时间，太频繁重测
// 会把首字从 2 秒拖回十几秒。
const (
	raceFailTTL = 10 * time.Minute
	raceOKTTL   = time.Hour
)

// stale 判断一条观测是否已经过了保鲜期。Seen 零值（测试里直接构造的
// raceStat）按新鲜处理，保持原有断言的语义。
func (h hopStatSnap) stale(now time.Time) bool {
	if h.Seen.IsZero() {
		return false
	}
	ttl := raceFailTTL
	if h.Verdict == "ok" && h.FirstBlockMs > 0 {
		ttl = raceOKTTL
	}
	return now.Sub(h.Seen) > ttl
}

// noteRaceHop 记一次竞速跳的首块观测。
func (s *Server) noteRaceHop(tag string, d time.Duration, verdict string) {
	now := time.Now()
	s.raceMu.Lock()
	if s.raceStat == nil {
		s.raceStat = map[string]hopStatSnap{}
	}
	s.raceStat[tag] = hopStatSnap{
		FirstBlockMs: d.Milliseconds(),
		Verdict:      verdict,
		At:           now.Format("15:04:05"),
		Seen:         now,
	}
	s.raceMu.Unlock()
}

// disabledChannels 返回「因 403/401 认证类错误被整渠道禁用」的渠道与到期时间，
// 给 /health 的 race 段用。
func (s *Server) disabledChannels() map[string]string {
	s.offMu.Lock()
	defer s.offMu.Unlock()
	out := make(map[string]string, len(s.off))
	now := time.Now()
	for channel, until := range s.off {
		if now.After(until) {
			delete(s.off, channel)
			continue
		}
		out[channel] = until.Format(time.RFC3339)
	}
	return out
}

func (s *Server) raceSnapshot() map[string]hopStatSnap {
	s.raceMu.Lock()
	defer s.raceMu.Unlock()
	out := make(map[string]hopStatSnap, len(s.raceStat))
	for k, v := range s.raceStat {
		out[k] = v
	}
	return out
}

// New wires the server. client is shared with the bridge.
func New(cfg *config.Config, ks keys.Set, am *alias.Map, sup *supervisor.Supervisor, client *http.Client, log *logx.Logger) *Server {
	return &Server{cfg: cfg, keys: ks, aliases: am, sup: sup, client: client, log: log,
		started: time.Now(), cool: map[string]time.Time{}, silence: map[string]time.Time{},
		off: map[string]time.Time{}, raceStat: map[string]hopStatSnap{},
		serialAt: map[string]time.Time{}, early: newEarlyStats(), sem: newUpstreamStats(),
		hops: newHopStats()}
}

// headerTimeout 解析「等上游响应头」的实际容忍上限，优先级：测试/显式字段 >
// 该渠道的 channelPolicy[..].headerTimeoutSec > zgate.json 的 upstreamHeaderTimeoutSec
// > 常量缺省。每次都现读配置，所以 /admin/reload 换了值不必重启进程。
//
// 按渠道分开给的理由见 upstreamHeaderTimeout 注释末段：同一个窗口套在「60 秒才回 503
// 的中转」和「抖动到 10 秒才出首块的兜底站」上，必然有一边是错的。channel 为空
// （桥接路径拿不到渠道）时只看全局。
func (s *Server) headerTimeout(channel string) time.Duration {
	if s.headerWait > 0 {
		return s.headerWait
	}
	if cfg := s.Config(); cfg != nil {
		if pol, ok := cfg.ChannelPolicy[channel]; ok && pol.HeaderTimeoutSec != 0 {
			if pol.HeaderTimeoutSec < 0 {
				return 0 // 这一渠道不要看门狗
			}
			return time.Duration(pol.HeaderTimeoutSec) * time.Second
		}
		if cfg.UpstreamHeaderTimeoutSec < 0 {
			return 0 // 负数 = 关掉看门狗，回到「谁不回就一直挂着」的老行为
		}
		if cfg.UpstreamHeaderTimeoutSec > 0 {
			return time.Duration(cfg.UpstreamHeaderTimeoutSec) * time.Second
		}
	}
	return upstreamHeaderTimeout
}

// earlyCommitWindow 是「流式请求等上游响应头多久就先交卷 200」的窗口（毫秒）。
// 0 = 关闭，回到「等头等到超时再报错」的老行为；负数在 config 层已经当成关闭。
func (s *Server) earlyCommitWindow() time.Duration {
	if s.earlyCommit > 0 {
		return s.earlyCommit
	}
	if cfg := s.Config(); cfg != nil && cfg.EarlyCommitMs > 0 {
		return time.Duration(cfg.EarlyCommitMs) * time.Millisecond
	}
	return 0
}

// earlyKeepalive 是提前交卷后的心跳间隔：0/缺省 10 秒。
func (s *Server) earlyKeepalive() time.Duration {
	if s.earlyPing > 0 {
		return s.earlyPing
	}
	if cfg := s.Config(); cfg != nil && cfg.EarlyKeepaliveSec > 0 {
		return time.Duration(cfg.EarlyKeepaliveSec) * time.Second
	}
	return 10 * time.Second
}

// hopKey 是冷却表的主键。出口也算进去：同一条链里「直连」和「经机场」是同一个
// upstream 的两跳，共用一个 key 会让直连那跳被地区受限的 403 冷却掉，
// 紧接着的机场跳就被当成「冷却中，跳过」—— 恰好把兜底吃掉。
func hopKey(hop alias.Hop) string { return hop.Channel + "|" + hop.Upstream + "|" + hop.Proxy }

// maskProxy 把出口代理串里的 userinfo 凭据掩掉，只用于日志与错误回显：
// 有口令时保留用户名、口令换成 ***（http://user:***@host:port）；只有用户名
// 或没有 userinfo 时原样返回；解析不了的串不回显原文（可能带着读不懂的凭据），
// 给固定占位。当前配置是无凭据的 LAN 地址，这是给「换成带凭据出口」预埋的脱敏。
func maskProxy(proxy string) string {
	if proxy == "" {
		return ""
	}
	u, err := url.Parse(proxy)
	if err != nil {
		return "(proxy unparseable)"
	}
	if _, hasPassword := u.User.Password(); !hasPassword {
		return proxy
	}
	// 不能走 url.UserPassword("***").String()：它会把掩码转义成 %2A%2A%2A，
	// 日志里难以辨认。userinfo 在 u.String() 里是第一个 "username:pass@" 段，
	// 按原文定位替换即可，URL 其余部分保持解析后的原样。
	return strings.Replace(u.String(), u.User.String()+"@", u.User.Username()+":***@", 1)
}

// hopKeyForLog 是 hopKey 的日志形态：proxy 段经 maskProxy 脱敏。
// 冷却表必须继续用原始 hopKey —— 掩码串会让「只差口令」的两跳共用键；
// 所有日志与错误回显一律用这个。
func hopKeyForLog(hop alias.Hop) string {
	return hop.Channel + "|" + hop.Upstream + "|" + maskProxy(hop.Proxy)
}

func (s *Server) cooling(hop alias.Hop) bool {
	if s.channelOff(hop.Channel) {
		// 整渠道被 403 禁用时，这一点对所有跳都成立；早返回省掉一次锁。
		return true
	}
	s.coolMu.Lock()
	defer s.coolMu.Unlock()
	now := time.Now()
	if until, ok := s.cool[hopKey(hop)]; ok {
		if now.After(until) {
			delete(s.cool, hopKey(hop))
		} else {
			return true
		}
	}
	if until, ok := s.silence[hopKey(hop)]; ok {
		if now.After(until) {
			delete(s.silence, hopKey(hop))
		} else {
			return true
		}
	}
	return false
}

// coolDurationFor 决定这一跳该冷却多久：额度烧光用 quotaCooldown（一天），
// 其余不可用的跳用默认的 hopCooldown。返回的 reason 只用于日志。
func (s *Server) coolDurationFor(hop alias.Hop, status int, head []byte) (string, time.Duration) {
	if quotaExhausted(status, head) {
		return "quota", quotaCooldown
	}
	return "fatal", hopCooldown
}

// logQuotaCooling 只在额度类冷却时打一行显式日志，好让人一眼看出「不是坏了，是没钱了」。
func (s *Server) logQuotaCooling(reason string, hop alias.Hop, status int, d time.Duration) {
	if reason != "quota" {
		return
	}
	s.log.Infof("[router] %s 额度已耗尽（HTTP %d），冷却 %v；额度续上或进程重启后自动复活",
		hopKeyForLog(hop), status, d)
}

func (s *Server) markCooling(hop alias.Hop) {
	s.markCoolingFor(hop, hopCooldown)
}

// markCoolingFor 按指定时长冷却一跳（429 用 45s，僵死上游用 5min，死跳用 30min）。
func (s *Server) markCoolingFor(hop alias.Hop, d time.Duration) {
	s.coolMu.Lock()
	s.cool[hopKey(hop)] = time.Now().Add(d)
	s.coolMu.Unlock()
}

// retryBridgeOn429 在桥接跳收到 429 时先就地退避重试一次。
// 只在还没向客户端写过任何 chunk 时重试（写过了就不能重放，会把 SSE 弄乱）。
func (s *Server) retryBridgeOn429(r *http.Request, hop alias.Hop, cw *bridgeChunkWriter, opts bridge.Options, result bridge.Result) bridge.Result {
	if result.Status != 429 || cw.written {
		return result
	}
	s.log.Infof("[router] %s 429，退避 %v 后重试同一跳", hopKeyForLog(hop), rateLimitBackoff)
	select {
	case <-time.After(rateLimitBackoff):
	case <-r.Context().Done():
		return result
	}
	return bridge.Forward(s.client, opts)
}

// coolBridgeFailure 给桥接失败分级冷却：429 短暂摘掉，上游静默超时（504）摘得久一些。
func (s *Server) coolBridgeFailure(ctx context.Context, hop alias.Hop, result bridge.Result) {
	switch result.Status {
	case 429:
		s.coolHop(ctx, hop, rateLimitCooldown, coolWhyRateLimit)
	case 504:
		d := s.timeoutCooldownFor(hop.Channel)
		if d <= 0 {
			return
		}
		s.log.Infof("[router] %s 上游静默超时，冷却 %v", hopKeyForLog(hop), d)
		s.coolHop(ctx, hop, d, "静默超时")
	}
}

func (s *Server) coolingCount() int {
	s.coolMu.Lock()
	defer s.coolMu.Unlock()
	n := 0
	now := time.Now()
	for key, until := range s.cool {
		if now.After(until) {
			delete(s.cool, key)
			continue
		}
		n++
	}
	return n
}

var hopByHop = map[string]bool{
	"connection":          true,
	"proxy-connection":    true,
	"keep-alive":          true,
	"proxy-authenticate":  true,
	"proxy-authorization": true,
	"te":                  true,
	"trailer":             true,
	"transfer-encoding":   true,
	"upgrade":             true,
}

// Config returns the current configuration; it can be swapped by /admin/reload.
func (s *Server) Config() *config.Config {
	s.cfgMu.RLock()
	defer s.cfgMu.RUnlock()
	return s.cfg
}

func (s *Server) setRuntime(cfg *config.Config, ks keys.Set) {
	s.cfgMu.Lock()
	s.cfg = cfg
	s.keys = ks
	s.cfgMu.Unlock()
}

// keyset returns the current credentials; /admin/reload can swap them.
func (s *Server) keyset() keys.Set {
	s.cfgMu.RLock()
	defer s.cfgMu.RUnlock()
	return s.keys
}

// Handler is the whole routing table.
func (s *Server) Handler() http.Handler { return http.HandlerFunc(s.serveHTTP) }

func (s *Server) serveHTTP(w http.ResponseWriter, r *http.Request) {
	var early *earlySSEWriter
	defer func() {
		if rec := recover(); rec != nil {
			s.log.Errorf("panic on %s %s: %v", r.Method, r.URL.Path, rec)
			if early != nil {
				early.fail(502, "unified-router error: panic")
				return
			}
			writeJSON(w, 500, errorBody("unified-router error: panic", "proxy_error"))
		}
	}()

	path, search := normalizePath(r)
	if path == "/health" {
		s.health(w)
		return
	}
	if path == "/models" {
		s.models(w, r)
		return
	}
	if path == "/admin/reload" {
		s.reload(w, r)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSON(w, 400, errorBody("invalid request body", "invalid_request_error"))
		return
	}
	_ = r.Body.Close()

	model := ""
	if len(body) > 0 && strings.Contains(r.Header.Get("Content-Type"), "application/json") {
		var probe struct {
			Model string `json:"model"`
		}
		if err := json.Unmarshal(body, &probe); err == nil {
			model = probe.Model
		}
	}

	isChat := path == "/chat/completions"
	if !isChat && (isQoder(model) || isWorkBuddy(model) || isQwen(model) || isQiniu(model)) {
		writeJSON(w, 400, errorBody("WorkBuddy/Qoder/Qwen models only support chat/completions", "invalid_request_error"))
		return
	}

	// 流式请求先交卷：等上游响应头的空窗里就给客户端 200 + text/event-stream 和心跳，
	// 免得它自己判死重试（判死权归上游，见 docs/TROUBLESHOOTING.md 18.4）。
	// 窗口内上游就回话的走老路径，状态码原样透出；非流式请求不适用（它要确定的 JSON + 状态码）。
	if isChat && wantsStream(body) {
		if window := s.earlyCommitWindow(); window > 0 {
			early = newEarlySSEWriter(w)
			defer early.finish()
			// 观测（计数 + 日志）从这里开始记：交卷了没有、交完上游有没有翻脸，
			// 以前在 /health 和日志里都是空白，看不出它到底在干活还是空转。
			early.attach(s.early, s.log, model)
			early.start(window, s.earlyKeepalive())
			w = early
		}
	}

	// 链层首字节预算：判死权交回上游之后，单跳可以无限挂，只有这里知道用户等多久。
	// 预算到点由 doForward 统一收口（504 + 不埋冷却、不再换跳）。
	r = r.WithContext(withChainContext(r.Context(), s.chainBudget(), false))

	s.aliases.Reload()
	if target, ok := s.aliases.Resolve(model); ok {
		s.routeAlias(w, r, body, model, target, path, search, isChat)
		return
	}
	s.routeFallback(w, r, body, model, path, search, isChat)
}

func (s *Server) routeAlias(w http.ResponseWriter, r *http.Request, body []byte, model string, t alias.Target, path, search string, isChat bool) {
	if len(t.Chain) > 0 {
		s.routeChain(w, r, body, model, t, path, search, isChat)
		return
	}
	channel := t.Channel
	key := s.keyset().For(channel)
	if key == "" {
		writeJSON(w, 502, errorBody(channel+" key not configured", "configuration_error"))
		return
	}
	protocol := t.Protocol
	if protocol == "" {
		protocol = "chat"
	}
	if protocol != "chat" {
		if !isChat {
			writeJSON(w, 400, errorBody(channel+" bridged models only support chat/completions", "invalid_request_error"))
			return
		}
		if err := s.prepare(channel); err != nil {
			writeJSON(w, 503, errorBody("upstream not ready: "+err.Error(), "upstream_error"))
			return
		}
		s.log.Infof("%s %s%s model=%s -> %s:%s", r.Method, path, search, model, channel, protocol)
		streaming := wantsStream(body)
		cw := newBridgeChunkWriter(w)
		result := bridge.Forward(s.client, bridge.Options{
			Protocol:      protocol,
			Base:          t.Base,
			Key:           key,
			Body:          body,
			UpstreamModel: t.Upstream,
			DisplayModel:  model,
			Ctx:           r.Context(),
			Stream:        streaming,
			OnChunk:       cw.write,
		})
		finishBridge(w, cw, result)
		return
	}

	chain := append([]string{t.Upstream}, t.Fallbacks...)
	headers := s.forwardHeaders(r, body, channel, key)
	if err := s.prepare(channel); err != nil {
		writeJSON(w, 503, errorBody("upstream not ready: "+err.Error(), "upstream_error"))
		return
	}
	if len(chain) > 1 {
		s.log.Infof("%s %s%s model=%s -> %s (%s)", r.Method, path, search, model, channel, strings.Join(chain, " -> "))
		s.forwardChain(w, r, body, t.Base, path, search, headers, chain, 0)
		return
	}
	rewritten, ok := rewriteModel(body, t.Upstream)
	if !ok {
		writeJSON(w, 400, errorBody("invalid JSON body", "invalid_request_error"))
		return
	}
	s.log.Infof("%s %s%s model=%s -> %s", r.Method, path, search, model, channel)
	s.forward(w, r, rewritten, t.Base, path, search, headers)
}

func (s *Server) routeFallback(w http.ResponseWriter, r *http.Request, body []byte, model, path, search string, isChat bool) {
	channel := "OC"
	cfg := s.Config()
	base := cfg.Upstreams["OC"].Base
	label := "opencode"
	ks := s.keyset()
	key := ks.OC
	switch {
	case isChat && isQoder(model):
		channel, label, key = "QD", "qoder", ks.QD
		base = cfg.Upstreams["QD"].Base
		if key == "" {
			writeJSON(w, 502, errorBody("Qoder key not configured", "configuration_error"))
			return
		}
		rewritten, ok := rewriteModel(body, trimPrefixFold(model, "qoder:"))
		if !ok {
			writeJSON(w, 400, errorBody("invalid JSON body for Qoder model", "invalid_request_error"))
			return
		}
		body = rewritten
	case isChat && isQwen(model):
		// 千问平台只认 Anthropic Messages；裸 `qwen:` id 还没进 alias map 时
		// （播种后、归一化前）也要能落到正确上游，而不是被当成 OpenCode 模型。
		channel, label, key = "QW", "qwen", ks.QW
		base = cfg.Upstreams["QW"].Base
		if key == "" {
			writeJSON(w, 502, errorBody("Qwen key not configured", "configuration_error"))
			return
		}
		s.log.Infof("%s %s%s model=%s -> QW:messages", r.Method, path, search, model)
		streaming := wantsStream(body)
		cw := newBridgeChunkWriter(w)
		result := bridge.Forward(s.client, bridge.Options{
			Protocol:      "messages",
			Base:          base,
			Key:           key,
			Body:          body,
			UpstreamModel: trimPrefixFold(model, "qwen:"),
			DisplayModel:  model,
			Ctx:           r.Context(),
			Stream:        streaming,
			OnChunk:       cw.write,
		})
		finishBridge(w, cw, result)
		return
	case isChat && isQiniu(model):
		// 七牛云 AI 网关：同样只认 Anthropic Messages，裸 `qn:` id 还没进 alias map
		// 时（播种后、归一化前）也要能落到正确上游。
		channel, label, key = "QN", "qiniu", ks.QN
		base = cfg.Upstreams["QN"].Base
		if key == "" {
			writeJSON(w, 502, errorBody("Qiniu key not configured", "configuration_error"))
			return
		}
		s.log.Infof("%s %s%s model=%s -> QN:messages", r.Method, path, search, model)
		streaming := wantsStream(body)
		cw := newBridgeChunkWriter(w)
		result := bridge.Forward(s.client, bridge.Options{
			Protocol:      "messages",
			Base:          base,
			Key:           key,
			Body:          body,
			UpstreamModel: trimPrefixFold(model, "qn:"),
			DisplayModel:  model,
			Ctx:           r.Context(),
			Stream:        streaming,
			OnChunk:       cw.write,
		})
		finishBridge(w, cw, result)
		return
	case isChat && isWorkBuddy(model):
		channel, label, key = "WB", "workbuddy", ks.WB
		base = cfg.Upstreams["WB"].Base
		if key == "" {
			writeJSON(w, 502, errorBody("WorkBuddy key not configured", "configuration_error"))
			return
		}
	default:
		if key == "" {
			writeJSON(w, 502, errorBody("OpenCode-Go key not configured", "configuration_error"))
			return
		}
	}
	headers := s.forwardHeaders(r, body, channel, key)
	if err := s.prepare(channel); err != nil {
		writeJSON(w, 503, errorBody("upstream not ready: "+err.Error(), "upstream_error"))
		return
	}
	s.log.Infof("%s %s%s model=%s -> %s", r.Method, path, search, orDash(model), label)
	s.forward(w, r, body, base, path, search, headers)
}

// prepare starts an on-demand child and marks the channel as recently used.
func (s *Server) prepare(channel string) error {
	upstream, ok := s.Config().Upstreams[channel]
	if !ok || upstream.Child == "" {
		return nil
	}
	s.sup.Touch(upstream.Child)
	if err := s.sup.Ensure(upstream.Child); err != nil {
		s.log.Warnf("通道 %s 的子进程未就绪: %v", channel, err)
		return err
	}
	return nil
}

func (s *Server) forwardHeaders(r *http.Request, body []byte, channel, key string) http.Header {
	h := http.Header{}
	for name, values := range r.Header {
		if hopByHop[strings.ToLower(name)] || strings.EqualFold(name, "host") ||
			strings.EqualFold(name, "content-length") ||
			// The transport disables transparent decompression, so forwarding
			// Accept-Encoding would hide error bodies from chainAccept.
			strings.EqualFold(name, "accept-encoding") {
			continue
		}
		for _, v := range values {
			h.Add(name, v)
		}
	}
	if h.Get("User-Agent") == "" {
		h.Set("User-Agent", "unified-router/1.0")
	}
	switch channel {
	case "WB", "QD", "QW", "QN", "GM", "HJ":
		// 这些通道一律用 zgate 自己的 key 覆盖 Authorization：
		// QN 是七牛云网关、GM 是 catiecli 中转、HJ 是哈基米（gemai.cc）；
		// 漏掉任一通道都会把客户端原始 Bearer（或空）透传上去被回 401「未提供API Key」。
		h.Set("Authorization", "Bearer "+key)
	case "OC":
		h.Set("Authorization", "Bearer "+key)
		h.Set("User-Agent", "opencode-cli/1.0")
		if h.Get("X-Opencode-Session") == "" && h.Get("x-opencode-session") == "" {
			h.Set("X-Opencode-Session", s.Config().Session)
		}
	}
	return h
}

func (s *Server) forward(w http.ResponseWriter, r *http.Request, body []byte, base, path, search string, headers http.Header) {
	s.doForwardWith(w, r, body, base, path, search, "", headers, nil, nil, nil, nil, nil)
}

func (s *Server) forwardChain(w http.ResponseWriter, r *http.Request, body []byte, base, path, search string, headers http.Header, chain []string, index int) {
	if index >= len(chain) {
		writeJSON(w, 502, errorBody("all upstreams failed: "+strings.Join(chain, " -> "), "proxy_error"))
		return
	}
	rewritten, ok := rewriteModel(body, chain[index])
	if !ok {
		writeJSON(w, 400, errorBody("invalid JSON body", "invalid_request_error"))
		return
	}
	retry := func(reason string) {
		if index+1 < len(chain) {
			s.log.Infof("[router] %s -> %s, fallback %s", chain[index], reason, chain[index+1])
			s.forwardChain(w, r, body, base, path, search, headers, chain, index+1)
			return
		}
		writeJSON(w, 502, errorBody("unified-router upstream error: "+reason, "proxy_error"))
	}
	s.doForwardWith(w, r, rewritten, base, path, search, "", headers, chainAccept, retry, nil, nil, nil)
}

// errUpstreamSilent 表示「连上了上游，但它在 s.headerTimeout() 内一个响应头都没给」。
// 与传输层失败（EOF / 连接重置）区分开：那类失败重试同一跳往往就过，
// 而沉默的上游重试只会再白等一个完整窗口，必须直接换跳。
var errUpstreamSilent = errors.New("upstream silent: no response header")

// cancelOnClose 把「上下文生命周期」绑在上游响应体上：正文读完/关闭时才取消，
// 既不让派发 goroutine 泄漏，又不会在流式传输中途把连接掐掉。
type cancelOnClose struct {
	io.ReadCloser
	cancel context.CancelFunc
}

func (c *cancelOnClose) Close() error {
	err := c.ReadCloser.Close()
	c.cancel()
	return err
}

// doForward 派发一次上游请求。流式请求额外挂「响应头看门狗」：上游接了连接却
// 迟迟不发头时，到点取消并把这一跳判成沉默（errUpstreamSilent），由调用方换跳。
// 非流式请求保持原样 —— 有的上游要等整段生成完才发头，给它设上限会误杀长回答。
func (s *Server) doForward(req *http.Request, body []byte, channel string) (*http.Response, error) {
	wait := s.headerTimeout(channel)
	// 链层「首字节预算」：整条链从收到请求到交出第一个字节的总上限，逐跳只取剩下多少。
	// 为什么必须在这一层做：判死权交回上游之后（headerTimeoutSec = -1）单跳可以无限期
	// 挂着，而 DeepSeek-4.1-Flash 那种四跳链串起来就是四段无上限等待。跳层只能回答
	// 「每跳等多久」，加起来仍无上界；只有链层知道「用户愿意等多久」。
	budgetBound := false
	if dl, ok := chainDeadline(req.Context()); ok {
		remaining := time.Until(dl)
		if remaining <= 0 {
			return nil, &silentErr{budget: true}
		}
		if wait <= 0 || remaining < wait {
			wait = remaining
			budgetBound = true
		}
	}
	if wait <= 0 || !wantsStream(body) {
		return s.client.Do(req)
	}
	ctx, cancel := context.WithCancel(req.Context())
	type outcome struct {
		resp *http.Response
		err  error
	}
	// 缓冲 1：超时分支取消后也要把 goroutine 的结局收回来，否则它永远阻塞在发送上。
	ch := make(chan outcome, 1)
	req = req.WithContext(ctx)
	go func() {
		resp, err := s.client.Do(req)
		ch <- outcome{resp: resp, err: err}
	}()
	timer := time.NewTimer(wait)
	defer timer.Stop()
	select {
	case out := <-ch:
		if out.resp != nil && out.resp.Body != nil {
			out.resp.Body = &cancelOnClose{ReadCloser: out.resp.Body, cancel: cancel}
			return out.resp, nil
		}
		cancel()
		return out.resp, out.err
	case <-timer.C:
		cancel()
		// 取消后 Do 立刻返回；收掉它的结果并把可能已经拿到的响应体关掉。
		out := <-ch
		if out.resp != nil {
			_, _ = io.Copy(io.Discard, io.LimitReader(out.resp.Body, 1<<20))
			_ = out.resp.Body.Close()
		}
		// 带上**本次实际生效**的窗口：日志里若按 s.headerTimeout(channel) 现读配置，
		// 热加载换过值之后会把「25 秒判死」写成「0s 内没给响应头」，排查直接跑偏。
		return nil, &silentErr{wait: wait, budget: budgetBound}
	}
}

func (s *Server) doForwardWith(w http.ResponseWriter, r *http.Request, body []byte, base, path, search, channel string, headers http.Header,
	accept func(status int, head []byte) bool, retry func(reason string), onThrottled func(), at *attemptCtl, hop *alias.Hop) {

	target := strings.TrimRight(base, "/") + path + search
	// 客户端没声明思考档位时由网关补一档（config.ReasoningGuard.ForceEffort）。
	// 必须在上游请求、requestModel 与 guardApplies 之前替换 body —— 三者用的都是这份字节。
	if injected, ok := injectThinkingEffort(s.Config().ReasoningGuard, body); ok {
		s.log.Infof("[router] %s 客户端未声明思考档位，按配置补 reasoning_effort=%q",
			target, s.Config().ReasoningGuard.ForceEffort)
		body = injected
	}
	// 429 就地退避重试一次：限流窗口通常很短，先等一小会儿再试同一跳，
	// 比立刻回落/直接失败更划算。重试仍 429 时再交给 onThrottled 冷却。
	// txRetry 与 retry429 各自单独计数：传输层失败的重试不能消耗 429 的退避预算，
	// 反之亦然。不能用循环下标判：传输层重试的 continue 也会自增下标，
	// 那样先传输失败一次的请求就吃不到 429 的就地退避了。
	txRetry := 0
	retry429 := 0
	guardRetries := 0 // reasoningGuard：同一跳透明重抽次数（上游加密思考分流）
	// sanitizeTried：思考档位枚举不合法（400）时剥掉参数重发同一跳的次数，最多一次。
	// 剥完还 400 就是别的问题，再剥只会掩盖真错误。
	sanitizeTried := 0
	// guardTimeoutRounds：其中有多少次是「探针到点都没有可判定信号」（上游思考阶段整段静默）。
	// 放行时要按原因给不同提示：加密分流说「只回加密」，静默超时说「探测超时」，别混为一谈。
	guardTimeoutRounds := 0
	// 竞速模式下渠道可以关掉「429 就地退避」：白等 700ms 只把首字往后推，
	// 直接换下一跳更快。非竞速路径 inPlace429 恒为 true，行为与老版本一致。
	inPlace429 := !(at != nil && at.policy.RateLimitBackoffMs < 0)
	// statusRetry：上游 HTTP 500 的原地重试次数。只在渠道开了 retry500Once 时用，
	// 且只重试一次 —— 500 是「上游自己出错」，连撞两次还 500 就说明不是抖动。
	statusRetry := 0
	// 首块看门狗：配了 firstBlockMs 之后，2xx 的 SSE 若在该时长内没出现真实内容
	// delta，就判这一跳失败并把机会让给下一跳。它专治「200 + 空流」——
	// 实测 3.6 有一次 14.24 s 里只有心跳没有正文，串行链会把这种跳当成功干等。
	firstBlock := time.Duration(0)
	if at != nil && at.policy.FirstBlockMs > 0 {
		firstBlock = time.Duration(at.policy.FirstBlockMs) * time.Millisecond
	}
	startedAt := time.Now()
	for {
		req, err := http.NewRequestWithContext(r.Context(), r.Method, target, bytes.NewReader(body))
		if err != nil {
			writeJSON(w, 502, errorBody("unified-router upstream error: "+err.Error(), "proxy_error"))
			return
		}
		if hop != nil {
			s.hopTry(*hop)
		}
		req.Header = headers.Clone()
		if guardRetries > 0 {
			// 重抽必须换「连接 + 会话」两样：2026-11-10 12:01 实测 3 次重抽全部落回
			// 同一路加密后端（同一 keep-alive 连接、同一个写死的 X-Opencode-Session），
			// 上限耗尽后放行的仍是加密流 —— 这就是前两次修完仍看不到思考的原因。
			req.Close = true
			if base := headers.Get("X-Opencode-Session"); base != "" {
				req.Header.Set("X-Opencode-Session", guardRetrySession(base, guardRetries))
			}
		}
		if len(body) > 0 {
			req.ContentLength = int64(len(body))
		}
		resp, err := s.doForward(req, body, channel)
		if err != nil {
			// 客户端已经走了（用户中断 / 切模型 / 页面关掉）：这次请求作废，直接收工。
			// 下面 select 的 Done 分支本来也会返回，但那样得先打出「300ms 后重试同一跳」
			// —— 2026-11-02 实测一次取消风暴里刷了 8 条永远不会发生的重试行，误导排查。
			// 提前判掉还有一个作用：把「不重试」写成显式契约，而不是依赖 select 的副作用。
			if r.Context().Err() != nil {
				return
			}
			if errors.Is(err, errUpstreamSilent) {
				// 上游收下请求却不给头：重试同一跳只会再白等一个窗口，直接换跳。
				// 带上 model：同一个 base 下不同模型表现能差一个量级（2026-11-10 19:45
				// 实测 gemai 的 [福利]gemini-3.8-flash 直连 3 秒出首块，网关内却整段挂住），
				// 只打 base 根本分不清是哪个模型被上游晾着。
				// 窗口打的是**本次实际生效值**（可能被链预算压低），不是配置里的现读数。
				var se *silentErr
				applied := s.headerTimeout(channel)
				budgetHit := false
				if errors.As(err, &se) {
					applied = se.wait
					budgetHit = se.budget
				}
				s.log.Warnf("[router] %s（channel=%s model=%s）上游 %v 内没给响应头，判这一跳沉默并换跳",
					base, channel, requestModel(body), applied)
				if hop != nil && !budgetHit {
					// 只统计「这一跳自己的沉默」：预算耗尽（budgetHit）说明是整条链
					// 的时间用完了，记到最后一跳头上会让人误判它不行。
					s.hopSilent(*hop)
				}
				if budgetHit {
					// 预算耗尽不是这一跳的错：给它静默冷却会让下一个请求又从死跳起手，
					// 而且再换跳也只是把剩下的预算耗在一模一样的等待上。直接收工并说清楚。
					s.log.Warnf("[router] 整条链的首字节预算用完（最后一跳实际等 %v），停止换跳并回 504", applied)
					writeJSON(w, 504, errorBody("gateway gave up waiting for the first byte buffer ("+applied.String()+")", "gateway_timeout"))
					return
				}
				// 沉默也要埋这一跳：catiecli 的 3.8/3.7 现在是「收下请求、几十秒不发头」，
				// 只换跳不冷却的话，下一个请求又从死跳起手，每个请求都白付一个窗口。
				// 冷却时长按渠道的 silenceCooldownSeconds（GM/HJ = 20s），到期自动回链。
				// 单跳链例外：它没有「别人」可说，埋下去等于把这个模型关 20 秒 ——
				// 2026-11-10 21:40 的 Gemini-3.8-Flash 就是这样从「偶尔慢」变成「连片 502」的。
				if hop != nil && !singleHopChain(r.Context()) {
					if d := s.silenceCooldownFor(hop.Channel); d > 0 {
						s.markSilence(*hop, d)
						s.log.Infof("[router] %s 沉默，静默冷却 %v 后再试这一跳", hopKeyForLog(*hop), d)
					}
				} else if hop != nil {
					s.log.Infof("[router] %s 是单跳链，沉默不埋冷却（没有下一跳可说）", hopKeyForLog(*hop))
				}
				if retry != nil {
					retry("上游沉默（无响应头）")
					return
				}
				writeJSON(w, 502, errorBody("unified-router upstream error: "+err.Error(), "proxy_error"))
				return
			}
			// 传输层失败（EOF / TLS 握手超时 / 连接被重置）说明请求大概率没被上游
			// 受理过，重试同一条腿通常就能过 —— 先重试本跳一次，再谈回落。
			// 2026-10-31 实测：机场某节点对 opencode.ai 的大包短暂黑洞，5 KB 以上的
			// POST 全部 5s 超时，而 GET 健康检查一直 200（url-test 看不出来）。
			if txRetry == 0 {
				txRetry++
				s.log.Infof("[router] %s 传输层失败（%v），%v 后重试同一跳", base, err, transportRetryDelay)
				select {
				case <-time.After(transportRetryDelay):
				case <-r.Context().Done():
					return
				}
				continue
			}
			if retry != nil {
				retry(err.Error())
				return
			}
			writeJSON(w, 502, errorBody("unified-router upstream error: "+err.Error(), "proxy_error"))
			return
		}

		var head []byte
		if accept != nil {
			// Peek at error bodies: a 400 can still mean "pool cooling down",
			// which should fall through to the next region. Successful responses
			// stream without buffering, and a bounded ReadAll avoids the
			// single-Read partial-segment trap on error bodies.
			if resp.StatusCode >= 400 {
				head, _ = io.ReadAll(io.LimitReader(resp.Body, 8192))
			}
			if sanitizeTried == 0 && invalidThinkingParam(resp.StatusCode, head) {
				// Gemini 的 ThinkingLevel 只认 minimal/low/medium/high，客户端把
				// high/max/off（甚至占位串 BOGUS）直接塞进 thinking_level 就会 400。
				// 请求体其余部分完全合法，剥掉这个参数同一跳就能过 —— 把 400 原样
				// 冒泡给用户，用户只会看到 INVALID_REQUEST 而不知道自己在哪个档位上出错。
				if stripped, ok := stripThinkingParams(body); ok {
					sanitizeTried++
					if s.sem != nil {
						s.sem.invalid.Add(1)
					}
					s.log.Infof("[router] %s 上游 400 不接受思考档位（%s），剥掉思考参数后重试同一跳",
						base, retryHint(head))
					_, _ = io.Copy(io.Discard, resp.Body)
					resp.Body.Close()
					body = stripped
					continue
				}
			}
			// 500 原地重试一次。老行为里 500 落到 accept 的 default 分支（true），
			// 原样透给客户端 —— 既不重试也不换跳，是全表唯一一处。catiecli 的 500
			// 多是上游瞬时内部错，按次计费下重试一次远便宜于降级到弱模型。
			if resp.StatusCode == 500 && statusRetry == 0 && s.retry500For(channel) {
				statusRetry++
				if hop != nil {
					// 这次 500 没进 accept（直接重试了），但它是实打实的一次上游出错，
					// /health.hops 少记这一笔会让 e5xx/try 的比率偏低。
					s.hopE5xx(*hop)
				}
				s.log.Infof("[router] %s 上游 HTTP 500（%s），%v 后重试同一跳",
					base, retryHint(head), statusRetryDelay)
				_, _ = io.Copy(io.Discard, resp.Body)
				resp.Body.Close()
				select {
				case <-time.After(statusRetryDelay):
				case <-r.Context().Done():
					return
				}
				continue
			}
			if !accept(resp.StatusCode, head) {
				_, _ = io.Copy(io.Discard, resp.Body)
				resp.Body.Close()
				if resp.StatusCode == 429 {
					if retry429 == 0 && inPlace429 {
						retry429++
						s.log.Infof("[router] 429 退避 %v 后重试同一跳", rateLimitBackoff)
						select {
						case <-time.After(rateLimitBackoff):
						case <-r.Context().Done():
							return
						}
						continue
					}
					if onThrottled != nil {
						onThrottled()
					}
				}
				retry(fmt.Sprintf("%s %s", http.StatusText(resp.StatusCode), retryHint(head)))
				return
			}
		}

		// reasoningGuard：上游同别名会随机分流到「只给加密 thinking 的后端」，
		// 宿主把 reasoning.encrypted 当 replay 元数据丢弃、思考块留空，GUI 完全看不到思考。
		// 命中条件（流式 + 白名单模型 + 期待思考 + SSE + 2xx）在写任何字节给客户端前
		// 先判首段 SSE：零明文 thinking delta 且带加密 detail → 丢弃缓冲、重抽同一跳，
		// 直到拿到明文思考流或达上限。重抽绝不调用 retry（不走 fallback），也绝不写 header。
		var streamSrc io.Reader = resp.Body
		guard := s.Config().ReasoningGuard
		model := requestModel(body)
		if resp.StatusCode < 300 && wantsStream(body) && isEventStreamGuard(resp) &&
			s.guardWanted(model, channel, guard, body) {
			// 重抽预算已经花完，或者这个模型正处在「近期拿不到明文思考」的窗口期：都不再探测。
			// 加密那一路探针要么等到整段思考结束才判得出（实测 11 s / 61 s），
			// 要么白等满上限；而窗口期内重抽几乎必然落回同一路后端（12:01 连续 3/3、
			// 13:20 连续 2/2）。直接把上游原始流交给客户端：可读提示先到，
			// 空闲心跳负责证明连接还活着，正文一到就往下流。
			switch {
			case s.guardInSkip(model):
				s.log.Infof("[router] %s 模型 %q 在「近期拿不到明文思考」跳过期内，直接放行（不再探测）", target, model)
				if guard.InjectNotice {
					streamSrc = io.MultiReader(bytes.NewReader(guardSkipNoticeSSE()), resp.Body)
				}
			case guardRetries >= guard.MaxRetries:
				// 重抽预算花完的两种成因分开报：探针超时（静默）和对端明确给了加密思考。
				// 最后一次不探测、直接放行上游原始流 —— 一旦探测，用户就要多等满一个
				// probeSeconds，窗口期里纯属白等。
				s.guardNoteEncryptedOnly(model, guard)
				if guardTimeoutRounds > 0 {
					s.log.Warnf("[router] %s 模型 %q 连续 %d 次探测超时（上游思考阶段静默），放行上游原始流",
						target, model, guardTimeoutRounds)
					if guard.InjectNotice {
						streamSrc = io.MultiReader(bytes.NewReader(guardTimeoutNoticeSSE(guardRetries)), resp.Body)
					}
				} else {
					s.log.Warnf("[router] %s 模型 %q 连续 %d 次没拿到明文思考，放行上游原始流", target, model, guardRetries)
					if guard.InjectNotice {
						streamSrc = io.MultiReader(bytes.NewReader(guardNoticeSSE(guardRetries)), resp.Body)
					}
				}
			default:
				verdict, buffered, timedOut := probeReasoningStreamDeadline(resp.Body,
					guard.MaxProbeBytes, time.Duration(guard.ProbeSeconds)*time.Second)
				if timedOut {
					// 到点没有任何可判定的信号：加密分流那一路在思考阶段整段静默，
					// 既没有明文 reasoning_content 也没有正文。换连接+换会话重抽，
					// 别把「等满一整段思考」的成本摊给用户。
					guardRetries++
					guardTimeoutRounds++
					s.log.Infof("[router] %s 模型 %q %v 内没有可判定的思考信号（上游静默），换连接+换会话重抽 %d/%d",
						target, model, time.Duration(guard.ProbeSeconds)*time.Second, guardRetries, guard.MaxRetries)
					resp.Body.Close()
					select {
					case <-time.After(guardRetryDelay):
					case <-r.Context().Done():
						return
					}
					continue
				}
				if verdict == streamEncrypted && guardRetries < guard.MaxRetries {
					guardRetries++
					s.log.Infof("[router] %s 模型 %q 上游返回加密思考分流（零明文 thinking delta），换连接+换会话重抽 %d/%d",
						target, model, guardRetries, guard.MaxRetries)
					// 首块已判定是加密分流：直接关掉这次响应重抽，不读剩余流，
					// 否则加密后端拖到几十秒才 finish，用户要白等一整轮才看到重抽结果。
					// 重抽之间留一点抖动，避开上游「同一瞬间同一窗口」的分流抖动。
					resp.Body.Close()
					select {
					case <-time.After(guardRetryDelay):
					case <-r.Context().Done():
						return
					}
					continue
				}
				switch verdict {
				case streamEncrypted:
					s.guardNoteEncryptedOnly(model, guard)
					s.log.Warnf("[router] %s 模型 %q 连续 %d 次加密思考，达上限放行最后一次", target, model, guardRetries)
					if guard.InjectNotice {
						buffered = append(guardNoticeSSE(guardRetries), buffered...)
					}
				case streamPlaintext:
					s.guardNotePlaintext(model)
				}
				streamSrc = io.MultiReader(bytes.NewReader(buffered), resp.Body)
			}
		}
		if firstBlock > 0 && resp.StatusCode < 300 && isEventStreamGuard(resp) {
			if at.gate != nil && at.gate.isClaimed() {
				// 已经有别的跳出字并抢到写端了，这一路没必要再等首块：
				// 早点收工，把上游额度让出来。
				resp.Body.Close()
				retry("另一路已出字")
				return
			}
			buffered, ok := peekFirstContent(streamSrc, firstBlock, r.Context())
			if !ok {
				resp.Body.Close()
				s.hopNoFirstBlock(at.hop)
				s.noteRaceHop(at.hopTag, 0, "no-first-block")
				s.log.Infof("[router] %s 模型 %q %v 内没有真实内容首块，判这一跳失败并让位",
					target, model, firstBlock)
				// 200 但迟迟没有真实内容：给它一小段「静默冷却」，下次先说别人。
				// 时长必须短（GM 配 20s）——3.6/3.5 常态 9-14s 才出正文，按 5xx 那种
				// 90 秒去埋，会把整条链饿成「全在冷却 → 直接 502」。
				if d := s.silenceCooldownFor(at.hop.Channel); d > 0 {
					s.markSilence(at.hop, d)
					s.log.Infof("[router] %s 首块超时，静默冷却 %v 后再试", at.hopTag, d)
				}
				retry("首块超时（没有内容 delta）")
				return
			}
			// 读出来的字节必须拼回队首，否则首块被吃掉，客户端少一段正文。
			streamSrc = io.MultiReader(bytes.NewReader(buffered), streamSrc)
			s.noteRaceHop(at.hopTag, time.Since(startedAt), "ok")
		}
		defer resp.Body.Close()
		copyHeaders(w.Header(), resp.Header)
		sse := isEventStreamGuard(resp)
		// tracker 只对事件流有意义：普通 JSON 没有 finish_reason 概念，给它补帧会毁掉响应体。
		var tracker *streamTracker
		if sse {
			tracker = &streamTracker{}
		}
		if sse {
			// 事件流一律交给 net/http 按 chunked 重新分帧。上游 SSE 可能自带
			// Content-Length（实测 200 + CL 的假上游就能打出来），而守卫会丢弃首段、
			// 插入可读提示、掺空闲心跳，长度必然与原值不同 —— 保留旧 CL 会让写端报
			// "http: wrote more than the declared Content-Length" 并直接断流，
			// 客户端收到 200 却 0 字节，表现就是「连上了但什么都没有」。
			w.Header().Del("Content-Length")
		}
		w.WriteHeader(resp.StatusCode)
		if at != nil && firstBlock <= 0 {
			// 没开首块看门狗（例如非 SSE 响应）时，WriteHeader 就是「这一跳赢了」，
			// 直接把首字节耗时记进 /health。
			s.noteRaceHop(at.hopTag, time.Since(startedAt), "ok")
		}
		if len(head) > 0 {
			if _, err := w.Write(head); err != nil {
				return
			}
		}
		flusher, _ := w.(http.Flusher)
		if len(head) > 0 && flusher != nil {
			flusher.Flush()
		}
		buf := make([]byte, 32*1024)
		heartbeat := time.Duration(s.Config().StreamIdleHeartbeatSeconds) * time.Second
		if heartbeat > 0 && !sse {
			// 心跳只对 SSE 有意义：往普通 JSON 报文里插注释行会直接毁掉响应体，
			// 所以非事件流一律走原来的同步转发。
			heartbeat = 0
		}
		if heartbeat <= 0 {
			for {
				n, readErr := streamSrc.Read(buf)
				if n > 0 {
					tracker.feed(buf[:n])
					if _, writeErr := w.Write(buf[:n]); writeErr != nil {
						return
					}
					if flusher != nil {
						flusher.Flush()
					}
				}
				if readErr != nil {
					// 上游断流时先看这条流有没有 finish_reason/[DONE]：没有就补帧收口，
					// 否则客户端拿到的是「200 + 半截正文 + 安静关闭」。
					s.closeTruncated(w, flusher, model, true, tracker)
					return
				}
			}
		}
		// 空闲心跳：上游思考阶段常静默 30-60 秒（2026-11-10 实测 iceman 正文中断
		// 51.9 秒），中间层和宿主都会把这当成「连上了但没说话」。SSE 注释行对任何
		// 合规客户端都是无操作，但足以证明连接还活着，也让用户看到界面还在动。
		type streamRead struct {
			data []byte
			err  error
		}
		ch := make(chan streamRead, 4)
		go func() {
			for {
				n, readErr := streamSrc.Read(buf)
				var data []byte
				if n > 0 {
					// 主循环要立刻写出去，必须复制：buf 会被下一次 Read 覆盖。
					data = append([]byte(nil), buf[:n]...)
				}
				select {
				case ch <- streamRead{data: data, err: readErr}:
				case <-r.Context().Done():
					return
				}
				if readErr != nil {
					return
				}
			}
		}()
		timer := time.NewTimer(heartbeat)
		defer timer.Stop()
		for {
			select {
			case rr := <-ch:
				if len(rr.data) > 0 {
					tracker.feed(rr.data)
					if _, writeErr := w.Write(rr.data); writeErr != nil {
						return
					}
					if flusher != nil {
						flusher.Flush()
					}
				}
				if rr.err != nil {
					s.closeTruncated(w, flusher, model, true, tracker)
					return
				}
				resetTimer(timer, heartbeat)
			case <-timer.C:
				if _, err := io.WriteString(w, ": zgate keepalive\n\n"); err != nil {
					return
				}
				if flusher != nil {
					flusher.Flush()
				}
				resetTimer(timer, heartbeat)
			case <-r.Context().Done():
				return
			}
		}
	}
}

// retryHint extracts the gateway's error code for the log line.
func retryHint(head []byte) string {
	var probe struct {
		Error struct {
			Code string `json:"code"`
		} `json:"error"`
	}
	if err := json.Unmarshal(head, &probe); err == nil && probe.Error.Code != "" {
		return probe.Error.Code
	}
	return ""
}

// healthSegments 把渠道名映射成 /health 的段名。没登记的渠道退回小写渠道名，
// 所以新增渠道即便忘了写段名也不会漏段；要换人类可读名再加一行。
var healthSegments = map[string]string{
	"OC": "opencode",
	"WB": "workbuddy",
	"QD": "qoder",
	"QW": "qwen",
	"QN": "qiniu",
	"GM": "gemini",
	"HJ": "hajimi",
}

// healthSegmentName 返回渠道在 /health 里的段名。
func healthSegmentName(channel string) string {
	if name, ok := healthSegments[channel]; ok {
		return name
	}
	return strings.ToLower(channel)
}

func (s *Server) health(w http.ResponseWriter) {
	s.aliases.Reload()
	states := s.sup.States()
	upstreamView := func(channel string) map[string]any {
		u := s.Config().Upstreams[channel]
		hasKey := s.keyset().For(channel) != ""
		view := map[string]any{
			"base":       u.Base,
			"key":        hasKey,
			"child":      u.Child,
			"state":      "up",
			"last_error": "",
		}
		if !hasKey {
			view["state"] = "no_key"
		}
		// 本地 child 的 state / last_error / pid 取自 supervisor 实况；
		// 远程上游（无 child）只有 key/base，state 由 key 是否配置推定。
		if u.Child != "" {
			if st, ok := states[u.Child].(map[string]any); ok {
				if v, ok := st["state"]; ok {
					view["state"] = v
				}
				if v, ok := st["last_error"]; ok {
					view["last_error"] = v
				}
				if v, ok := st["pid"]; ok {
					view["pid"] = v
				}
			}
		}
		return view
	}
	payload := map[string]any{
		"ok": true,
		"alias": map[string]any{
			"path":   s.aliases.Path(),
			"models": s.aliases.Count(),
		},
		"children": states,
		"cooling":  s.coolingCount(),
		"uptime_s": int(time.Since(s.started).Seconds()),
	}
	// 段名与渠道的对应关系只由 keys.Channels 驱动：加渠道不用再回来改这里。
	for _, channel := range keys.Channels {
		payload[healthSegmentName(channel)] = upstreamView(channel)
	}
	// race 段：竞速跳最近一次的首块耗时与判定，以及整渠道禁用表。
	// 只看不改 —— 排查「为什么这次又是 3.5 出的字」时，一眼能看出 3.8 最近是不是
	// 全在 no-first-block。空表也要输出 {}，别让消费方拿 null 崩掉。
	race := map[string]any{"hops": s.raceSnapshot(), "disabled": s.disabledChannels()}
	payload["race"] = race
	// early 段：提前交卷到底交了多少次、心跳发了多少、交完上游翻脸几次。
	// 以前这一整块是黑盒（文件里 0 个日志调用、/health 0 个字段），
	// 「它有没有在干活」只能靠用户体感猜。
	payload["early"] = s.early.view(s.earlyCommitWindow(), s.earlyKeepalive())
	// upstream 段：上游语义分类的计数。2026-11-11 起 503 high demand 不再按
	// 普通 5xx 埋软冷却、thinking 参数不合法的 400 会剥参数重发、被截断的流
	// 会补一帧 error 收口 —— 这三件事有没有发生，只能从这里看。
	payload["upstream"] = s.sem.view()
	// chain 段：链层首字节预算（0 = 不限）。判死权交回上游之后，
	// 这是「一次请求最多等多久」的唯一出处。
	payload["chain"] = map[string]any{"budget_s": int(s.chainBudget().Seconds())}
	// guard 段：思考守卫的档位、带能力位的渠道、正在被跳过的模型。
	payload["guard"] = s.guardView()
	if s.hops != nil {
		// hops 是每跳的 try/ok/busy/e5xx/silent/no_first_block 计数，键与冷却表同格式。
		// 回答的是 /health.race 回答不了的问题：串行链（AIS，11-11 起 3 跳）里首选到底行不行。
		payload["hops"] = s.hops.view()
	}
	writeJSON(w, 200, payload)
}

// models 是 zgate 自己的聚合命名空间视图。GET /v1/models 与 GET /models 都落到
// 这里（normalizePath 去掉 /v1），ZCode 看到的是 zgate-owned catalog，不再是
// OpenCode-Go 自家 /models 的逐字节透传。
//
// scope 三档（?scope=canonical|legacy|all，缺省 canonical）：
//
//	canonical  只给 zgate 真正承诺的命名空间（20 条），客户端与面板只需要这些；
//	legacy     73 条历史 id，只为老配置/老会话留着，默认不往客户端倒；
//	all        两拨都给（老行为，排查用）。
//
// 为什么默认收紧：93 条混在一张表里，同一个模型会出现三四次（显示名 + 各上游裸
// id），面板上没法挑；而 legacy id 又不能删——历史会话里还写着它们。分开取用，
// 谁需要谁自己点名要 legacy。
func (s *Server) models(w http.ResponseWriter, r *http.Request) {
	all := s.aliases.Catalog()
	scope := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("scope")))
	if scope == "" {
		scope = "canonical"
	}
	data := all
	switch scope {
	case "all":
	case "canonical", "legacy":
		data = make([]alias.CatalogEntry, 0, len(all))
		for _, e := range all {
			isCanonical := e.CanonicalID == e.ID
			if isCanonical == (scope == "canonical") {
				data = append(data, e)
			}
		}
	default:
		writeJSON(w, 400, errorBody("unknown scope: "+scope+" (want canonical|legacy|all)", "invalid_request_error"))
		return
	}
	// total 是**本次返回**的条数（客户端直接拿来数「我有几个模型」），
	// 全量目录的条数单独放 catalog_total —— 两个数混成一个会让 20 条的响应
	// 写着 93，看起来像分页没给完。
	writeJSON(w, 200, map[string]any{
		"object":        "list",
		"owned_by":      "zgate",
		"scope":         scope,
		"total":         len(data),
		"catalog_total": len(all),
		"data":          data,
	})
}

// routeChain walks a merged chain: every hop carries its own base, channel and
// upstream id, so one display name can span WorkBuddy, Qoder and OpenCode-Go.
func (s *Server) routeChain(w http.ResponseWriter, r *http.Request, body []byte, model string, t alias.Target, path, search string, isChat bool) {
	protocol := t.Protocol
	if protocol == "" {
		protocol = "chat"
	}
	if protocol != "chat" && !isChat {
		writeJSON(w, 400, errorBody("bridged models only support chat/completions", "invalid_request_error"))
		return
	}
	// 每跳按自己的协议派发（chat 直转 / messages·responses 过桥），
	// 所以一条链里可以既有原生 chat 跳也有桥接跳。
	// 链上有跳开了对冲（hedgeAfterMs）或首块看门狗（firstBlockMs）就走「首块对冲」：
	// 前几跳同时在路上，谁先给出真实内容首块谁赢；每跳的看门狗与冷却按**自己**
	// 渠道的策略取。没有任何跳要求竞速就走原来的串行链，一行都不改。
	// 单跳链的标记：沉默时不埋静默冷却（没有「下一跳」可说），只此一处传下去。
	if len(t.Chain) == 1 {
		r = r.WithContext(withChainContext(r.Context(), 0, true))
	}
	if plan, ok := s.racePlanFor(t, body); ok {
		s.raceChain(w, r, body, model, t, path, search, plan)
		return
	}
	s.noteSerialChain(t, body)
	s.attemptChain(w, r, body, model, t, path, search, 0, nil)
}

func (s *Server) attemptChain(w http.ResponseWriter, r *http.Request, body []byte, model string, t alias.Target, path, search string, index int, at *attemptCtl) {
	if at != nil && index >= len(t.Chain) {
		// 竞争模式下「链走完了」由编排器统一回 502，这里直接收工，
		// 否则每一路都会往闸门里塞一份 error body。
		return
	}
	if index >= len(t.Chain) {
		writeJSON(w, 502, errorBody("all upstreams failed: "+chainNames(t.Chain), "proxy_error"))
		return
	}
	hop := t.Chain[index]
	// 这一跳的出口交给 context（EgressRouter 按它挑 Transport），
	// 往下传的 r 也带着它，回落到下一跳时会被下一跳覆盖。
	r = r.WithContext(WithProxy(r.Context(), hop.Proxy))
	// fail 是「这一路不行了」的统一出口：串行模式下它就是回落到下一跳；
	// 竞争模式下 at != nil，此时绝不能自己往上冲 —— 该由 raceChain 决定补哪一跳，
	// 否则每一路都会各自续一条链，同一个响应被写好几份。
	fail := func(reason string) {
		if at != nil {
			s.log.Infof("[race] %s 本路放弃：%s", hopKeyForLog(hop), reason)
			return
		}
		s.attemptChain(w, r, body, model, t, path, search, index+1, nil)
	}
	if s.cooling(hop) {
		s.log.Infof("[router] %s 冷却中，跳过", hopKeyForLog(hop))
		fail("冷却中")
		return
	}
	key := s.keyset().For(hop.Channel)
	if key == "" {
		s.log.Warnf("通道 %s 缺少 key，跳过 %s", hop.Channel, hop.Upstream)
		fail("缺少 key")
		return
	}
	if err := s.prepare(hop.Channel); err != nil {
		s.log.Warnf("通道 %s 的子进程未就绪: %v", hop.Channel, err)
		fail("子进程未就绪")
		return
	}
	proto := hop.Protocol
	if proto == "" {
		proto = t.Protocol
	}
	if proto == "" {
		proto = "chat"
	}
	if proto != "chat" {
		// 这一跳是桥接上游（千问）。链里可以混协议：前面几跳原生 chat，
		// 尾巴这一跳走 Messages 桥，失败照样换下一跳。
		s.log.Infof("%s %s%s model=%s -> %s:%s [%s] (%d/%d)", r.Method, path, search,
			model, hop.Channel, hop.Upstream, proto, index+1, len(t.Chain))
		// 每一跳都按流式转发。旧实现只允许链尾跳流式（怕非尾跳写出半截 SSE 后无法回落），
		// 代价是所有「首跳就能成」的 messages 型号都被整段缓冲：客户端要等整段生成完才见到
		// 第一个字（2026-11-06 实测 Claude-Haiku-5.5 首字节 1.739s = 总耗时 1.739s、只有 4 条
		// data 行；同期 Beam 因首跳被地区受限冷却、落到链尾跳，首字节 0.670s / 总 4.280s、88 条 data 行）。
		// 安全性没有损失：非 2xx 在任何字节写出之前就以 Result 返回，回落照旧；
		// 真要在 200 之后断流，链尾跳同样回不了落。
		streaming := wantsStream(body)
		cw := newBridgeChunkWriter(w)
		opts := bridge.Options{
			Protocol:      proto,
			Base:          s.hopBase(hop),
			Key:           key,
			Body:          body,
			UpstreamModel: hop.Upstream,
			DisplayModel:  model,
			Ctx:           r.Context(),
			Stream:        streaming,
			OnChunk:       cw.write,
		}
		result := bridge.Forward(s.client, opts)
		// 传输层失败且还没写出任何 chunk：重试同一跳一次（理由见 transportFailed）。
		if !cw.written && transportFailed(result) {
			s.log.Infof("[router] %s 传输层失败，%v 后重试同一跳", hopKeyForLog(hop), transportRetryDelay)
			select {
			case <-time.After(transportRetryDelay):
			case <-r.Context().Done():
				return
			}
			result = bridge.Forward(s.client, opts)
		}
		result = s.retryBridgeOn429(r, hop, cw, opts, result)
		if hopFatal(result.Status, result.Body) {
			m, d := s.coolDurationFor(hop, result.Status, result.Body)
			s.coolHop(r.Context(), hop, d, coolWhyOf(m))
			s.logQuotaCooling(m, hop, result.Status, d)
			if index+1 < len(t.Chain) {
				s.attemptChain(w, r, body, model, t, path, search, index+1, nil)
				return
			}
		}
		s.coolBridgeFailure(r.Context(), hop, result)
		// 地区受限按失败处理：桥接路径不走 chainAccept，必须单独判，
		// 否则 gpt-6-luna 这类 responses 模型会拿 403 直接返回给客户端。
		// 冷却规则与 chat 路径一致：有同上游的出口孪生跳才冷却这一跳。
		if regionBlocked(result.Status, result.Body) && proxyTwinAfter(t.Chain, index) {
			s.log.Infof("[router] %s 地区受限（HTTP %d），冷却 %v；同上游机场孪生跳继续可用",
				hopKeyForLog(hop), result.Status, regionCooldown)
			s.coolHop(r.Context(), hop, regionCooldown, "地区受限")
		}
		// 流里已经写过 chunk 就不能再换跳：客户端手里已经有半截 SSE，再写第二个响应体
		// 只会得到一条脏流。bridge 目前保证「写过 chunk 之后一律返回 200」（bridge.go:279-282），
		// 所以这条分支今天是防御性的；护栏留着，防止将来桥接改动把两份响应写进同一条流。
		// 真要走到这里，finishBridge 见 cw.written 也不会再补写任何字节。
		if cw.written && (result.Status >= 500 || regionBlocked(result.Status, result.Body)) {
			s.log.Infof("[router] %s 流式已开始后上游失败（HTTP %d），直接收口，不再回落", hopKeyForLog(hop), result.Status)
		}
		if !cw.written && (result.Status >= 500 || result.Status == 429 || regionBlocked(result.Status, result.Body)) && index+1 < len(t.Chain) {
			s.log.Infof("[router] %s -> HTTP %d, fallback %s", hop.Upstream, result.Status, nextHopName(t.Chain, index))
			s.attemptChain(w, r, body, model, t, path, search, index+1, nil)
			return
		}
		finishBridge(w, cw, result)
		return
	}
	rewritten, ok := rewriteModel(body, hop.Upstream)
	if !ok {
		writeJSON(w, 400, errorBody("invalid JSON body", "invalid_request_error"))
		return
	}
	headers := s.forwardHeaders(r, body, hop.Channel, key)
	s.log.Infof("%s %s%s model=%s -> %s:%s (%d/%d)", r.Method, path, search, model, hop.Channel, hop.Upstream, index+1, len(t.Chain))
	accept := func(status int, head []byte) bool {
		if poolDown(status, head) {
			// 池空是渠道级故障：暂停渠道，并把上游这句原文直接回给客户端
			// （不然客户端只能看到整条链撞完后的 502，不知道到底为什么）。
			if d := s.markChannelOffFor(hop.Channel, poolCooldown); d > 0 {
				s.log.Warnf("[router] %s 上游 key 池为空（HTTP %d），渠道 %s 暂停 %v",
					hopKeyForLog(hop), status, hop.Channel, d)
			}
			return true
		}
		if busyExhausted(status, head) {
			// 上游说「忙」不是这条链坏了：只跳过这一跳，绝不按整渠道故障处理。
			s.hopBusy(hop)
			// 冷却取 busyCooldownSeconds（GM 20s），比 softCooldownSeconds（60s）
			// 短得多 —— 高峰窗口本来就是秒级到几十秒，埋一分钟等于把空档期也封了。
			if s.sem != nil {
				s.sem.busy.Add(1)
			}
			if d := s.busyCooldownFor(hop.Channel); d > 0 {
				if s.sem != nil {
					s.sem.busySkip.Add(1)
				}
				s.log.Infof("[router] %s 上游 HTTP %d 表示需求量高峰（busy），跳过该跳 %v 后自动回链",
					hopKeyForLog(hop), status, d)
				s.coolHop(r.Context(), hop, d, "需求高峰")
			} else {
				s.log.Infof("[router] %s 上游 HTTP %d 表示需求量高峰（busy），不埋冷却直接换跳",
					hopKeyForLog(hop), status)
			}
			return false
		}
		if s.disableOnAuthFailure(hop, status, head) {
			return false
		}
		if hopFatal(status, head) {
			m, d := s.coolDurationFor(hop, status, head)
			s.coolHop(r.Context(), hop, d, coolWhyOf(m))
			s.logQuotaCooling(m, hop, status, d)
			return false
		}
		if regionBlocked(status, head) && proxyTwinAfter(t.Chain, index) {
			// 地区受限不是这跳坏了，是这条出口进不去。不冷却就会每个请求都先撞一遍
			// 直连跳的 403 再走机场孪生跳，白付一次往返。
			s.log.Infof("[router] %s 地区受限（HTTP %d），冷却 %v；同上游机场孪生跳继续可用",
				hopKeyForLog(hop), status, regionCooldown)
			s.coolHop(r.Context(), hop, regionCooldown, "地区受限")
		}
		if status == 504 {
			// 与桥接路径的 coolBridgeFailure 对齐：上游静默超时（连上不说话）
			// 也冷却这一跳，否则链上后续每个请求都要先撞一遍这个僵死上游再回落。
			s.log.Infof("[router] %s 上游静默超时，冷却 %v", hopKeyForLog(hop), timeoutCooldown)
			s.coolHop(r.Context(), hop, timeoutCooldown, "静默超时")
		}
		if status >= 500 {
			// 5xx 单独计一次（含 503/504）：busy 已单独计过，这里再计一次是刻意的 ——
			// 「上游出错几次」和「其中几次是忙」是两个不同的问题，除以 try 就是比率。
			s.hopE5xx(hop)
		}
		if d := s.softCooldownFor(hop.Channel); d > 0 && status >= 500 {
			// 5xx 不在 chainAccept 的冷却名单里：老行为是「每个请求都先撞一遍」。
			// 对 503 high demand 这种分钟级窗口，冷却 d 让后续请求直接跳过它，
			// 到期自动回链，不需要人工介入。
			s.log.Infof("[router] %s 上游 HTTP %d（暂时不可用），冷却 %v 后自动回链", hopKeyForLog(hop), status, d)
			s.coolHop(r.Context(), hop, d, "软冷却")
		}
		if status < 400 {
			s.hopOK(hop)
		}
		return chainAccept(status, head)
	}
	s.doForwardWith(w, r, rewritten, s.hopBase(hop), path, search, hop.Channel, headers, accept, func(reason string) {
		s.log.Infof("[router] %s -> %s, fallback %s", hop.Upstream, reason, nextHopName(t.Chain, index))
		if at != nil {
			s.noteRaceHop(at.hopTag, 0, reason)
			fail(reason)
			return
		}
		s.attemptChain(w, r, body, model, t, path, search, index+1, nil)
	}, func() {
		s.log.Infof("[router] %s 退避后仍 429，冷却 %v", hopKeyForLog(hop), rateLimitCooldown)
		s.coolHop(r.Context(), hop, rateLimitCooldown, coolWhyRateLimit)
	}, at, &hop)
}

// authFatal 判断 401/403 是不是「这个 key 本身不能用了」：key 无效 / 被撤销 /
// 过期 / 账号被封 / 认证失败。这类错误换跳没用 —— 同一渠道用的是同一个 key，
// 所以要把整渠道禁用（用户口径的「403 自动禁用」）。
// 与之相对的是「地区受限」（换出口能解）和「模型不可用」（换模型能解），
// 那两类只动单跳，绝不能升级成整渠道禁用。
// 触发条件里还要求渠道配了 channelPolicy.authFailCooldownHours > 0，
// 所以没有显式开启的渠道行为完全不变。
func authFatal(status int, head []byte) bool {
	if status != 401 && status != 403 {
		return false
	}
	text := strings.ToLower(string(head))
	for _, marker := range []string{
		"invalid api key", "api key not valid", "api_key_invalid", "incorrect api key",
		"api key expired", "api key revoked", "key disabled", "key has been disabled",
		"account suspended", "account has been suspended", "unauthenticated",
		"invalid authentication", "authentication failed", "invalid bearer",
	} {
		if strings.Contains(text, marker) {
			return true
		}
	}
	return false
}

// disableOnAuthFailure 在「认证类错误 + 渠道配了禁用时长」时禁用整渠道，返回是否已禁用。
func (s *Server) disableOnAuthFailure(hop alias.Hop, status int, head []byte) bool {
	if !authFatal(status, head) {
		return false
	}
	d := s.markChannelOff(hop.Channel)
	if d == 0 {
		return false
	}
	s.log.Warnf("[router] %s 认证类错误（HTTP %d），禁用渠道 %s %v；换 key 或重启进程后复活",
		hopKeyForLog(hop), status, hop.Channel, d)
	return true
}

// hopFatal 标记「这一跳现在就是不能用」的响应：模型 id 不存在、免费额度耗尽、欠费。
// 这类 4xx 与请求本身无关，换下一跳大概率能成，所以要回落并把该跳冷却一段时间。
// quotaExhausted 判断这一跳是不是「额度已经烧光」，而不是「这一跳坏了」。
// 两者都要回落 + 冷却，但时长差三个数量级：坏跳 30 分钟就够，额度用完要等续费。
func quotaExhausted(status int, head []byte) bool {
	if !hopFatal(status, head) {
		return false
	}
	for _, marker := range [][]byte{
		[]byte("Free quota exhausted"), []byte("use free tier only"),
		[]byte("AllocationQuota"), []byte("insufficient_quota"),
		[]byte("quota exhausted"), []byte("Arrearage"),
	} {
		if bytes.Contains(head, marker) {
			return true
		}
	}
	return false
}

func hopFatal(status int, head []byte) bool {
	switch status {
	case 400, 402, 403:
	default:
		return false
	}
	for _, marker := range [][]byte{
		[]byte("model_unavailable"), []byte("Model not exist"),
		[]byte("Arrearage"), []byte("AllocationQuota"), []byte("FreeTierOnly"),
		[]byte("insufficient_quota"), []byte("quota exhausted"),
		// 千问：`403 AccessDenied` + 这句表示免费额度用完且「用完即停」开着
		[]byte("Free quota exhausted"), []byte("use free tier only"),
	} {
		if bytes.Contains(head, marker) {
			return true
		}
	}
	return false
}

// transportFailed 判断桥接结果是不是「请求根本没被上游受理」的传输层失败。
// 桥接把 client.Do 的错误包成 502 + 原始错误文本，只能按文本认。
// 只有这种情况重试同一跳才安全：上游已经读过请求再断开的，重试会重复计费。
func transportFailed(result bridge.Result) bool {
	if result.Status < 500 {
		return false
	}
	body := string(result.Body)
	for _, marker := range []string{
		"EOF", "TLS handshake timeout", "connection reset", "i/o timeout",
		"broken pipe", "server closed idle connection", "connection refused",
	} {
		if strings.Contains(body, marker) {
			return true
		}
	}
	return false
}

// regionBlocked 判断这一跳是不是「地区受限」：不是跳坏了，是这条出口进不去。
// opencode 转发上游时原样带回（2026-10-30 实测里两种写法都出现过）：
//
//	chat 端点  {"type":"error","error":{"type":"RegionError",...}}
//	responses {"error":{"code":"unsupported_country_region_territory",...}}
//
// 桥接路径（messages / responses）不走 chainAccept，必须单独问这个，
// 否则 403 会原样返回给客户端，链上的机场跳永远轮不到。
//
// 2026-11-10 补第五个 marker：opencode 的 messages 端点对进不去的出口只回一句
// "Upstream request failed: Endpoint is unavailable."，bridge 再包一层
// "bridge upstream error: "（见 internal/bridge/bridge.go 的 upstreamMessage）。
// 这句既没有 RegionError 也没有 country 字样，只认前四串时 Claude-Haiku-5.5 的
// 403 会直接漏给客户端，链尾的机场孪生跳永远轮不到。按大小写不敏感匹配，
// 且仍受 403/400 门槛约束，真正的客户端 4xx（invalid_request 之类）不在此列。
func regionBlocked(status int, head []byte) bool {
	if status != 403 && status != 400 {
		return false
	}
	for _, marker := range [][]byte{
		[]byte("unsupported_country_region_territory"),
		[]byte("RegionError"),
		[]byte("not available in your country"),
		[]byte("region, or territory not supported"),
	} {
		if bytes.Contains(head, marker) {
			return true
		}
	}
	return bytes.Contains(bytes.ToLower(head), []byte("endpoint is unavailable"))
}

// proxyTwinAfter 判断 index 之后还有没有「同 channel、同上游、带出口」的孪生跳。
// 只有存在这条兜底跳，冷却一个地区受限的直连跳才是纯收益：下一个请求直接落到机场
// 孪生跳上。否则（唯一一跳、或后面没有同上游出口跳）冷却会把真实的 403 变成
// 「all upstreams failed」502 —— 连尝试都省掉，用户看到的错误还变了。
func proxyTwinAfter(chain []alias.Hop, index int) bool {
	if index >= len(chain) {
		return false
	}
	hop := chain[index]
	if hop.Proxy != "" {
		return false
	}
	for _, next := range chain[index+1:] {
		if next.Channel == hop.Channel && next.Upstream == hop.Upstream && next.Proxy != "" {
			return true
		}
	}
	return false
}

// chainAccept decides whether a chain attempt should fall through to the next hop.
func chainAccept(status int, head []byte) bool {
	switch status {
	case 429, 502, 503, 504:
		return false
	case 403, 400:
		if regionBlocked(status, head) {
			return false
		}
		if status == 400 {
			return !bytes.Contains(head, []byte(`"model_unavailable"`))
		}
	}
	return true
}

func chainNames(chain []alias.Hop) string {
	names := make([]string, 0, len(chain))
	for _, hop := range chain {
		names = append(names, hop.Channel+":"+hop.Upstream)
	}
	return strings.Join(names, " -> ")
}

func nextHopName(chain []alias.Hop, index int) string {
	if index+1 < len(chain) {
		return chain[index+1].Channel + ":" + chain[index+1].Upstream
	}
	return "(none)"
}

// reload re-reads zgate.json and applies the parts that can change at runtime:
// config values, upstream bases, credentials, child policies, idle thresholds
// and windows. The listen address, newly added children and a changed alias-map
// path still need a restart.
func (s *Server) reload(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, 405, errorBody("use POST", "invalid_request_error"))
		return
	}
	old := s.Config()
	next, err := config.Load(old.Path)
	if err != nil {
		writeJSON(w, 400, errorBody("配置读取失败: "+err.Error(), "configuration_error"))
		return
	}
	ks := keys.Load(next.ProviderConfig, next.WBGatewayConfig, next.QoderEnvFile, next.QwenEnvFile, next.QiniuEnvFile, next.GeminiEnvFile, next.HajimiEnvFile)
	applied, stale, added := s.sup.ApplyConfig(next.Children)
	s.setRuntime(next, ks)
	s.aliases.Reload()
	s.log.Infof("配置已热加载: %s（生效 %v）", next.Path, applied)
	writeJSON(w, 200, map[string]any{
		"ok":      true,
		"applied": applied,
		"stale":   stale,
		"added":   added,
		"note":    "监听地址、新增子进程与 alias map 路径仍需重启 zgate；配置、上游 base 与 key 已热加载",
	})
}

// trimPrefixFold removes a prefix case-insensitively.
func trimPrefixFold(s, prefix string) string {
	if len(s) >= len(prefix) && strings.EqualFold(s[:len(prefix)], prefix) {
		return s[len(prefix):]
	}
	return s
}

// ---------------------------------------------------------------- helpers

func normalizePath(r *http.Request) (string, string) {
	path := r.URL.Path
	if strings.HasPrefix(path, "/v1") && (len(path) == 3 || path[3] == '/') {
		path = path[3:]
	}
	if !strings.HasPrefix(path, "/") {
		path = "/" + path
	}
	if path == "" {
		path = "/"
	}
	// RawQuery does not include the "?", while the JS router's url.search does.
	// Callers concatenate base+path+search, so keep the separator here.
	if r.URL.RawQuery != "" {
		return path, "?" + r.URL.RawQuery
	}
	return path, ""
}

func rewriteModel(body []byte, upstream string) ([]byte, bool) {
	if len(body) == 0 {
		return body, true
	}
	var obj map[string]any
	if err := json.Unmarshal(body, &obj); err != nil {
		return nil, false
	}
	obj["model"] = upstream
	out, err := json.Marshal(obj)
	if err != nil {
		return nil, false
	}
	return out, true
}

// wantsStream 返回客户端（ZCode）是否请求了 SSE 流式输出。桥接模型上游也按流式请求，
// 让首字即时到达；非流式时桥接器退化为「整段合成一个 chunk」。
func wantsStream(body []byte) bool {
	var probe struct {
		Stream bool `json:"stream"`
	}
	if err := json.Unmarshal(body, &probe); err != nil {
		return false
	}
	return probe.Stream
}

// ---- reasoningGuard：上游加密思考分流的透明重抽 ----------------------------

type streamReasoningVerdict int

const (
	streamPlaintext    streamReasoningVerdict = iota // 见到明文 thinking delta，思考可见
	streamEncrypted                                  // 零明文 thinking delta + 加密 reasoning_details
	streamUndetermined                               // 缓冲超限 / 未判定，按原样放行
)

// reasoningGuardMatches 判断请求体里的 model 是否落在守卫白名单。
// doForwardWith 拿到的是 rewriteModel 之后的 body，model 已是 upstream 名，
// 因此白名单同时写别名（Iceman）与 upstream（iceman-contributor-free）。
func reasoningGuardMatches(models []string, body []byte) bool {
	if len(models) == 0 {
		return false
	}
	var probe struct {
		Model string `json:"model"`
	}
	if json.Unmarshal(body, &probe) != nil {
		return false
	}
	for _, m := range models {
		if m != "" && strings.EqualFold(m, probe.Model) {
			return true
		}
	}
	return false
}

// reasoningExpectsThinking 判断这次请求是否声明要思考。用户显式关思考
// （reasoning_effort=off / thinking.type=disabled）时守卫跳过，不重抽。
func reasoningExpectsThinking(body []byte) bool {
	var probe struct {
		ReasoningEffort *string `json:"reasoning_effort"`
		Thinking        *struct {
			Type string `json:"type"`
		} `json:"thinking"`
	}
	if json.Unmarshal(body, &probe) != nil {
		return false
	}
	if probe.ReasoningEffort != nil && *probe.ReasoningEffort != "" &&
		!strings.EqualFold(*probe.ReasoningEffort, "off") {
		return true
	}
	return probe.Thinking != nil && strings.EqualFold(probe.Thinking.Type, "enabled")
}

// injectThinkingEffort 在客户端没声明思考档位时替它补上 reasoning_effort。
// 只对 ForceEffort 命中的模型生效（ForceEffortModels，空则回落 Models 白名单），
// 客户端自带 reasoning_effort / thinking.type 时一律不动它 —— 用户显式关思考（off）
// 也要原样保留，否则「关掉思考」这个操作会被网关偷偷改回去。
func injectThinkingEffort(g config.ReasoningGuard, body []byte) ([]byte, bool) {
	if !g.Enabled || g.ForceEffort == "" || len(body) == 0 {
		return body, false
	}
	models := g.ForceEffortModels
	if len(models) == 0 {
		models = g.Models
	}
	if !reasoningGuardMatches(models, body) {
		return body, false
	}
	var raw map[string]json.RawMessage
	if json.Unmarshal(body, &raw) != nil {
		return body, false
	}
	if _, ok := raw["model"]; !ok {
		return body, false
	}
	// 客户端自己带了档位就一律不动 —— 注意不能只看 reasoningExpectsThinking：
	// 那个函数把 "off" 判成「不期待思考」，照它来的话用户点「关掉思考」会被悄悄改回 high。
	if v, ok := raw["reasoning_effort"]; ok {
		var s string
		if json.Unmarshal(v, &s) != nil || s != "" {
			return body, false
		}
	}
	if _, ok := raw["thinking"]; ok {
		return body, false
	}
	effort, err := json.Marshal(g.ForceEffort)
	if err != nil {
		return body, false
	}
	raw["reasoning_effort"] = effort
	out, err := json.Marshal(raw)
	if err != nil {
		return body, false
	}
	return out, true
}

func isEventStreamGuard(resp *http.Response) bool {
	return strings.Contains(strings.ToLower(resp.Header.Get("Content-Type")), "event-stream")
}

// probeReasoningStream 在写给客户端之前按 SSE 行顺序即时判定明文 / 加密思考分流。
// 返回的 buffered 是全部已读原始字节，放行时用 io.MultiReader 原样续上，
// 保证一个字节都不丢、也不重复。
//
// 实测两种上游后端（同一别名 iceman-contributor-free 随机分流）：
//   - 格式 A：首个有效 delta 就是 reasoning_content（明文思考逐块流式），思考可见；
//   - 格式 B：首个有效 delta 是 content（正文），全程零明文思考，收尾带
//     reasoning.encrypted（宿主当 replay 元数据丢弃、思考块留空）。
//
// 因为守卫只圈「声明要思考的 deepseek 模型」，格式 A 思考必然领先正文，
// 所以「正文先于思考」就是加密分流的可靠标志：首个正文块立即判 B 并透明重抽，
// 不必读完整个响应（否则用户要白等一次完整生成才看到重抽结果）。
func probeReasoningStream(r io.Reader, maxBytes int) (streamReasoningVerdict, []byte) {
	type detail struct {
		Type string `json:"type"`
	}
	type deltaFields struct {
		Content          string   `json:"content"`
		ReasoningContent string   `json:"reasoning_content"`
		Reasoning        string   `json:"reasoning"`
		ReasoningText    string   `json:"reasoning_text"`
		Thinking         string   `json:"thinking"`
		ThinkingContent  string   `json:"thinking_content"`
		ReasoningDetails []detail `json:"reasoning_details"`
	}
	type chunk struct {
		Choices []struct {
			Delta deltaFields `json:"delta"`
		} `json:"choices"`
	}
	buffered := make([]byte, 0, 4096)
	sawEncrypted := false
	scanned := 0
	tmp := make([]byte, 4096)
	for len(buffered) < maxBytes {
		n, err := r.Read(tmp)
		if n > 0 {
			buffered = append(buffered, tmp[:n]...)
		}
		for {
			idx := bytes.IndexByte(buffered[scanned:], '\n')
			if idx < 0 {
				break
			}
			line := bytes.TrimSuffix(buffered[scanned:scanned+idx], []byte("\r"))
			scanned += idx + 1
			trimmed := bytes.TrimSpace(line)
			if !bytes.HasPrefix(trimmed, []byte("data:")) {
				continue
			}
			payload := bytes.TrimSpace(trimmed[5:])
			if len(payload) == 0 || bytes.Equal(payload, []byte("[DONE]")) {
				continue
			}
			var c chunk
			if json.Unmarshal(payload, &c) != nil {
				continue
			}
			for _, ch := range c.Choices {
				d := ch.Delta
				// 格式 A：明文思考字段先于正文 → 思考可见，立即放行。
				if d.ReasoningContent != "" || d.Reasoning != "" || d.ReasoningText != "" ||
					d.Thinking != "" || d.ThinkingContent != "" {
					return streamPlaintext, buffered
				}
				// 格式 B：期待思考却先吐正文、零明文思考 → 加密分流，首块即重抽。
				if d.Content != "" {
					return streamEncrypted, buffered
				}
				for _, det := range d.ReasoningDetails {
					if strings.EqualFold(det.Type, "reasoning.encrypted") {
						sawEncrypted = true
					}
				}
			}
		}
		if err != nil {
			break
		}
	}
	if sawEncrypted {
		return streamEncrypted, buffered
	}
	return streamUndetermined, buffered
}

// probeReasoningStreamDeadline 给 probeReasoningStream 套一个上限：到点返回
// timedOut=true，由调用方关闭响应体后换连接重抽。探针 goroutine 会阻塞在
// Read 上，直到调用方 Close 掉 Body 才退出，所以超时分支必须先关 Body 再走。
// d<=0 表示不设上限，等价于直接调 probeReasoningStream。
func probeReasoningStreamDeadline(r io.Reader, maxBytes int, d time.Duration) (streamReasoningVerdict, []byte, bool) {
	if d <= 0 {
		v, b := probeReasoningStream(r, maxBytes)
		return v, b, false
	}
	type outcome struct {
		verdict  streamReasoningVerdict
		buffered []byte
	}
	// 缓冲 1：超时后 goroutine 仍会把结果塞进来，不能让它永久阻塞。
	ch := make(chan outcome, 1)
	go func() {
		v, b := probeReasoningStream(r, maxBytes)
		ch <- outcome{v, b}
	}()
	timer := time.NewTimer(d)
	defer timer.Stop()
	select {
	case o := <-ch:
		return o.verdict, o.buffered, false
	case <-timer.C:
		return streamUndetermined, nil, true
	}
}

// guardRetryDelay 是两次重抽之间的抖动间隔。不是为了省资源，而是把重抽错开到
// 上游分流的另一个时间窗口上；实测同步重抽更容易连续落回同一路加密后端。
const guardRetryDelay = 250 * time.Millisecond

// guardModelStat 是守卫的「按模型学习表」：一个模型能不能拿到明文思考，
// 由实况累积决定，不靠人肉维护白名单。
type guardModelStat struct {
	plaintext     int       // 拿到过多少次明文思考流
	encryptedOnly int       // 连续多少轮「重抽到上限仍是纯加密」
	skipUntil     time.Time // 跳过守卫的截止时间（零值 = 不跳过）
}

// requestModel 取请求体里的 model（此时已是 rewriteModel 之后的 upstream 名）。
func requestModel(body []byte) string {
	var probe struct {
		Model string `json:"model"`
	}
	if json.Unmarshal(body, &probe) != nil {
		return ""
	}
	return probe.Model
}

// guardRetrySession 给第 attempt 次重抽造一个新的会话标识。
// 前缀保留原值，便于日志里认人；后缀带序号与随机数，确保每次都不同 ——
// 上游若按会话粘连后端，只有换掉它才可能脱身。
func guardRetrySession(base string, attempt int) string {
	var b [4]byte
	if _, err := crand.Read(b[:]); err != nil {
		return base + "#r" + strconv.Itoa(attempt) + "-" + strconv.FormatInt(time.Now().UnixNano()%0xffff, 16)
	}
	return base + "#r" + strconv.Itoa(attempt) + "-" + hex.EncodeToString(b[:])
}

func (s *Server) guardStat(model string) *guardModelStat {
	s.guardMu.Lock()
	defer s.guardMu.Unlock()
	if s.guardMem == nil {
		s.guardMem = map[string]*guardModelStat{}
	}
	st, ok := s.guardMem[model]
	if !ok {
		st = &guardModelStat{}
		s.guardMem[model] = st
	}
	return st
}

// guardApplies 决定这一跳要不要跑守卫。
//
// mode=auto（默认，配置里不写 models 也生效）时不再看模型名：只要客户端声明了要思考、
// 又是 SSE 流，就先把首段判一遍。这样以后任何同类模型（Conatus / 新的匿名代号）
// 出现「只回加密思考」都不需要改配置或重新排障 —— 探针只多读一个首块，代价极小。
// 反过来，某个模型连续 giveUpAfter 轮重抽都没拿到明文时会被记进跳过表：
// 它本来就是「天生只给加密」，再重抽只是让用户白等，跳过更划算；到期自动复探。
func (s *Server) guardApplies(model, channel string, g config.ReasoningGuard, body []byte) bool {
	return s.guardWanted(model, channel, g, body) && !s.guardInSkip(model)
}

// guardWanted 只回答「这一跳的形态是否命中守卫条件」，不看跳过表。
// 跳过期照样要注入可读提示，所以调用方需要把这两件事分开问。
//
// 三档 mode（channel 是这一跳所属渠道）：
//
//	auto      不看名字，也不看渠道：只要客户端声明要思考、又是 SSE 流就探一遍。
//	          新出现的匿名代号模型（Conatus 之类）不需要改配置也能被覆盖。
//	channels  按**渠道能力位**判：只有 Upstream.GuardReasoning=true 的渠道才探。
//	          这是在「auto 太宽」与「models 名单要人工维护」之间取的中间档 ——
//	          上游把思考分到加密后端是**渠道级**事实，写在渠道上最不容易失配；
//	          名单非空时再叠一层收窄（谁写了名单就是想只盯这些名字）。
//	models    老口径：只看 Models 白名单。
func (s *Server) guardWanted(model, channel string, g config.ReasoningGuard, body []byte) bool {
	if !g.Enabled || !reasoningExpectsThinking(body) {
		return false
	}
	switch {
	case strings.EqualFold(g.Mode, "models"):
		return reasoningGuardMatches(g.Models, body)
	case strings.EqualFold(g.Mode, "channels"):
		if !s.Config().Upstreams[channel].GuardReasoning {
			return false
		}
		if len(g.Models) > 0 {
			return reasoningGuardMatches(g.Models, body)
		}
		return true
	default:
		return true
	}
}

// guardView 是 /health 的守卫段：开着没有、哪一档、哪些渠道带能力位、哪些模型正被跳过。
// 以前这一段在 /health 里是零字段 —— 守卫到底在不在工作只能靠翻日志。
func (s *Server) guardView() map[string]any {
	g := s.Config().ReasoningGuard
	channels := make([]string, 0, len(s.Config().Upstreams))
	for name, u := range s.Config().Upstreams {
		if u.GuardReasoning {
			channels = append(channels, name)
		}
	}
	sort.Strings(channels)
	s.guardMu.Lock()
	skipping := make([]string, 0, len(s.guardMem))
	for name, st := range s.guardMem {
		if !st.skipUntil.IsZero() && time.Now().Before(st.skipUntil) {
			skipping = append(skipping, name)
		}
	}
	s.guardMu.Unlock()
	sort.Strings(skipping)
	return map[string]any{
		"enabled":  g.Enabled,
		"mode":     g.Mode,
		"channels": channels,
		"skipping": skipping,
	}
}

// guardInSkip 报告该模型是否正处在「只回加密思考」的跳过期。到期当场清空计数，
// 让下一轮重新探路（上游可能已经切回明文后端）；跳过期内不滑动续期，
// 否则窗口会被一次次续上、永远探不到恢复。
func (s *Server) guardInSkip(model string) bool {
	s.guardMu.Lock()
	defer s.guardMu.Unlock()
	st := s.guardMem[model]
	if st == nil || st.skipUntil.IsZero() {
		return false
	}
	if time.Now().Before(st.skipUntil) {
		return true
	}
	st.skipUntil = time.Time{}
	st.encryptedOnly = 0
	return false
}

func (s *Server) guardNotePlaintext(model string) {
	st := s.guardStat(model)
	s.guardMu.Lock()
	st.plaintext++
	st.encryptedOnly = 0
	s.guardMu.Unlock()
}

// guardNoteEncryptedOnly 记录一次「重抽到上限仍是纯加密」，必要时把该模型记进跳过表。
func (s *Server) guardNoteEncryptedOnly(model string, g config.ReasoningGuard) {
	st := s.guardStat(model)
	s.guardMu.Lock()
	st.encryptedOnly++
	// encryptedOnly 本身就是「自上一条明文思考以来连续失败」的计数，
	// 不再要求「从未见过明文」——真机 iceman 天天能拿到明文，按旧条件跳过表永远进不去，
	// 于是每个窗口期的第一条请求都要白等满重抽预算。
	enter := st.encryptedOnly >= g.GiveUpAfter
	if enter {
		st.skipUntil = time.Now().Add(time.Duration(g.GiveUpForSeconds) * time.Second)
	}
	count := st.encryptedOnly
	s.guardMu.Unlock()
	if enter {
		s.log.Warnf("[router] 模型 %q 连续 %d 轮没有拿到明文思考（加密分流或思考阶段静默），%d 秒内跳过守卫（到期自动复探）",
			model, count, g.GiveUpForSeconds)
	}
}

// guardSkipNoticeSSE 是跳过期内的提示：这一轮压根没探测，所以不能说「已重抽 N 次」，
// 只能说「近期拿不到明文思考、本次直接放行」。上游其实已切回明文时，这条提示
// 只是思考块开头多一行说明，不影响正文。文案不写死「只回加密」：进跳过表的成因
// 也可能是探针超时（上游思考阶段整段静默），两种成因对用户是同一个观感。
func guardSkipNoticeSSE() []byte {
	note := "ⓘ 该模型近期思考拿不到明文（上游加密或思考阶段静默），本次已跳过重抽直接放行；正文照常输出。"
	payload, err := json.Marshal(map[string]any{
		"id":     "zgate-guard-skip",
		"object": "chat.completion.chunk",
		"choices": []any{map[string]any{
			"index":         0,
			"delta":         map[string]any{"reasoning_content": note},
			"finish_reason": nil,
		}},
	})
	if err != nil {
		return nil
	}
	return []byte("data: " + string(payload) + "\n\n")
}

// guardTimeoutNoticeSSE 是「探测到点没信号」那一路的提示。它不能说「上游只回加密思考」——
// 探针超时只证明上游在思考阶段静默，成因可能是加密分流，也可能是首字节就是慢。
func guardTimeoutNoticeSSE(retries int) []byte {
	note := fmt.Sprintf("ⓘ 本次思考探测超时（上游思考阶段静默，已重抽 %d 次），已直接放行上游流；思考可能不可见或稍后出现，正文照常输出。", retries)
	payload, err := json.Marshal(map[string]any{
		"id":     "zgate-guard-timeout",
		"object": "chat.completion.chunk",
		"choices": []any{map[string]any{
			"index":         0,
			"delta":         map[string]any{"reasoning_content": note},
			"finish_reason": nil,
		}},
	})
	if err != nil {
		return nil
	}
	return []byte("data: " + string(payload) + "\n\n")
}

// guardNoticeSSE 生成一条可读的 reasoning delta，插在放行流的最前面：
// 宿主会把它渲染进思考块，用户看到的是「思考被上游加密」而不是一片空白。
func guardNoticeSSE(retries int) []byte {
	note := fmt.Sprintf("ⓘ 上游本次只下发加密思考（已重抽 %d 次仍未拿到明文），思考内容不可见，正文照常输出。", retries)
	payload, err := json.Marshal(map[string]any{
		"id":     "zgate-guard-notice",
		"object": "chat.completion.chunk",
		"choices": []any{map[string]any{
			"index":         0,
			"delta":         map[string]any{"reasoning_content": note},
			"finish_reason": nil,
		}},
	})
	if err != nil {
		return nil
	}
	return []byte("data: " + string(payload) + "\n\n")
}

// resetTimer 重置一个可能已经触发的定时器（time.Timer.Reset 的常见坑）。
func resetTimer(t *time.Timer, d time.Duration) {
	if !t.Stop() {
		select {
		case <-t.C:
		default:
		}
	}
	t.Reset(d)
}

func copyHeaders(dst, src http.Header) {
	for name, values := range src {
		if hopByHop[strings.ToLower(name)] {
			continue
		}
		for _, v := range values {
			dst.Add(name, v)
		}
	}
}

func writeResult(w http.ResponseWriter, r bridge.Result) {
	ct := r.ContentType
	if ct == "" {
		ct = "application/json; charset=utf-8"
	}
	w.Header().Set("Content-Type", ct)
	if strings.HasPrefix(ct, "text/event-stream") {
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")
	}
	w.Header().Set("Content-Length", itoa(len(r.Body)))
	w.WriteHeader(r.Status)
	_, _ = w.Write(r.Body)
}

// bridgeChunkWriter 把桥接流式响应的每个 chat SSE chunk 直接写给客户端并 flush，
// 让首字随上游 delta 即时到达（不再等整段生成完）。首次写入时落 SSE 头。
type bridgeChunkWriter struct {
	w       http.ResponseWriter
	flusher http.Flusher
	once    bool
	written bool
}

func (b *bridgeChunkWriter) write(chunk []byte) error {
	if !b.once {
		b.w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
		b.w.Header().Set("Cache-Control", "no-cache")
		b.w.Header().Set("Connection", "keep-alive")
		b.w.WriteHeader(200)
		b.once = true
	}
	if _, err := b.w.Write(chunk); err != nil {
		return err
	}
	b.written = true
	if b.flusher != nil {
		b.flusher.Flush()
	}
	return nil
}

func newBridgeChunkWriter(w http.ResponseWriter) *bridgeChunkWriter {
	f, _ := w.(http.Flusher)
	return &bridgeChunkWriter{w: w, flusher: f}
}

// finishBridge 收口桥接响应：流式且已写出过 chunk 时，SSE 已结束，无需再写；
// 流式但尚未写出任何 chunk（上游直接返回错误）时，仍要把真实错误码经 writeResult 透出，
// 否则客户端会一直挂起。非流式则一律走 writeResult（与旧行为一致）。
func finishBridge(w http.ResponseWriter, cw *bridgeChunkWriter, result bridge.Result) {
	if cw.written {
		return
	}
	writeResult(w, result)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	body, err := json.Marshal(payload)
	if err != nil {
		body = []byte(`{"error":{"message":"encode failed","type":"proxy_error"}}`)
	}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Content-Length", itoa(len(body)))
	w.WriteHeader(status)
	_, _ = w.Write(body)
}

func errorBody(message, kind string) map[string]any {
	return map[string]any{"error": map[string]any{"message": message, "type": kind}}
}

func itoa(n int) string { return strconv.Itoa(n) }

func isWorkBuddy(model string) bool {
	m := strings.ToLower(model)
	return strings.HasPrefix(m, "cn:") || strings.HasPrefix(m, "global:")
}

func isQoder(model string) bool {
	return strings.HasPrefix(strings.ToLower(model), "qoder:")
}

func isQwen(model string) bool {
	return strings.HasPrefix(strings.ToLower(model), "qwen:")
}

func isQiniu(model string) bool {
	return strings.HasPrefix(strings.ToLower(model), "qn:")
}

func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}
