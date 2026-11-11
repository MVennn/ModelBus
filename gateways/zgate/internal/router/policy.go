package router

// 本文件收的是「策略与实际链形态对不上」的判据，以及跨跳共享的两个上下文开关：
//
//   - silentErr     判死错误要带上「本次实际生效的窗口」——日志按配置现读会把
//                   25 秒判死写成 0s，2026-11-10 21:19 真踩过。
//   - 链首字节预算   判死权交回上游之后，单跳可以无限挂；只有链层知道用户等多久。
//   - 单跳标记       单跳链不埋静默冷却（没有「下一跳」可说，埋下去等于把模型关掉）。
//   - ValidatePolicies 启动自检：只有在某个渠道**只**服务单跳模型、却又配了对冲字段
//                   时才判死；渠道同时服务多跳模型时不拦（字段在那些链上是有效的）。

import (
	"context"
	"fmt"
	"sort"
	"strings"
	"time"

	"zgate/internal/alias"
	"zgate/internal/config"
)

// silentErr 是「上游收下请求却连响应头都不给」的判死错误。
// wait 必须是**本次实际生效**的窗口（可能被链预算压低），不是配置里的现读数。
// budget=true 表示这次判死是链预算到点，而不是这一跳自己的窗口到点 —— 两者要
// 分开处理：前者不该给这一跳埋静默冷却，也不该继续换跳。
type silentErr struct {
	wait   time.Duration
	budget bool
}

func (e *silentErr) Error() string {
	if e.budget {
		return fmt.Sprintf("%v: chain first-byte budget exhausted", errUpstreamSilent)
	}
	return fmt.Sprintf("%v within %v", errUpstreamSilent, e.wait)
}

// Unwrap 让 errors.Is(err, errUpstreamSilent) 继续成立（老分支全靠它分派）。
func (e *silentErr) Unwrap() error { return errUpstreamSilent }

// chainCtxKey 用结构体做键，避免与别的包在 context 里塞的同名字符串撞车。
type chainCtxKey struct{ name string }

var (
	chainDeadlineKey = chainCtxKey{"chain-first-byte-deadline"}
	singleHopKey     = chainCtxKey{"chain-single-hop"}
)

// chainDeadline 取本条链的首字节截止时刻。
func chainDeadline(ctx context.Context) (time.Time, bool) {
	dl, ok := ctx.Value(chainDeadlineKey).(time.Time)
	return dl, ok
}

// singleHopChain 报告当前请求的链是否只有一跳。
func singleHopChain(ctx context.Context) bool {
	v, _ := ctx.Value(singleHopKey).(bool)
	return v
}

// withChainContext 把「链预算」与「单跳」两个事实放进请求上下文，往下传给
// doForward（预算）与 doForwardWith（沉默埋点）。
func withChainContext(ctx context.Context, budget time.Duration, singleHop bool) context.Context {
	if budget > 0 {
		ctx = context.WithValue(ctx, chainDeadlineKey, time.Now().Add(budget))
	}
	if singleHop {
		ctx = context.WithValue(ctx, singleHopKey, true)
	}
	return ctx
}

// chainBudget 解析整条链的首字节预算。0 = 不限（配置写了负数）。
func (s *Server) chainBudget() time.Duration {
	cfg := s.Config()
	if cfg == nil || cfg.ChainBudgetSec <= 0 {
		return 0
	}
	return time.Duration(cfg.ChainBudgetSec) * time.Second
}

// hopBase 取一跳实际要打的地址：链跳自己写了 base 就用它（同一渠道挂不同地址、
// 或者一个渠道里既有直连又有机场时用得到），没写就回落到渠道配置的 base。
// 2026-11-10 之前只认 hop.Base：别名表里没写 base 的链跳会拿着空地址去请求，
// 两跳瞬间失败、最后报「all upstreams failed」，看着像上游全挂了，实际是配置
// 压根没被读 —— 渠道 base 已经是单一事实来源，跳级 base 只该是覆盖而不是必需。
func (s *Server) hopBase(hop alias.Hop) string {
	if hop.Base != "" {
		return hop.Base
	}
	if cfg := s.Config(); cfg != nil {
		return cfg.Upstreams[hop.Channel].Base
	}
	return ""
}

// 冷却理由里只有这两种是「上游明确拒绝服务」，其余都是网关按状态码或时间做的判断。
const (
	coolWhyRateLimit = "限流"
	coolWhyQuota     = "额度"
)

// coolWhyOf 把 coolDurationFor 的理由转成 coolHop 的理由字符串。
func coolWhyOf(reason string) string {
	if reason == "quota" {
		return coolWhyQuota
	}
	return "不可用"
}

// coolHop 是所有「埋冷却」的统一入口，只为一件事：单跳链不许埋软性冷却。
// 单跳链冷却一跳 = 把这个模型整体关掉，而 2026-11-10 的 Gemini-3.8-Flash 就是
// 这么从「偶尔慢」被连续判断死成「连片 502」的 —— 用户看到的是模型挂了，
// 实际是网关自己把唯一的路封了 20 秒。429 与额度耗尽是例外：那是上游明确拒绝
// 继续服务，再打只会被限得更久，且不是猜测，埋了才是对的。
func (s *Server) coolHop(ctx context.Context, hop alias.Hop, d time.Duration, why string) {
	if d <= 0 {
		return
	}
	if singleHopChain(ctx) && why != coolWhyRateLimit && why != coolWhyQuota {
		s.log.Infof("[router] %s 单跳链的%s不埋冷却（%v）：没有下一跳可换，埋下去等于把这个模型关掉",
			hopKeyForLog(hop), why, d)
		return
	}
	s.markCoolingFor(hop, d)
}

// policyRaceFields 列出「只在多跳链上才有意义」的策略字段与它的实际值。
// 单跳模型上这些字段一个都不生效：没有第二跳可说、没有对冲对象。
func policyRaceFields(p config.ChannelPolicy) []string {
	var out []string
	if p.HedgeAfterMs > 0 {
		out = append(out, fmt.Sprintf("hedgeAfterMs=%d", p.HedgeAfterMs))
	}
	if p.FirstBlockMs > 0 {
		out = append(out, fmt.Sprintf("firstBlockMs=%d", p.FirstBlockMs))
	}
	if p.MaxParallel > 0 {
		out = append(out, fmt.Sprintf("maxParallel=%d", p.MaxParallel))
	}
	if p.SilenceCooldownSeconds > 0 {
		out = append(out, fmt.Sprintf("silenceCooldownSeconds=%d", p.SilenceCooldownSeconds))
	}
	if p.SoftCooldownSeconds > 0 {
		out = append(out, fmt.Sprintf("softCooldownSeconds=%d", p.SoftCooldownSeconds))
	}
	if p.RateLimitBackoffMs != 0 {
		out = append(out, fmt.Sprintf("rateLimitBackoffMs=%d", p.RateLimitBackoffMs))
	}
	return out
}

// busyCooldownFor 解析「上游说忙」之后这一跳跳过多久。
// 0 = 沿用 softCooldownSeconds（老行为：503 就是普通 5xx）；负数 = 不冷却。
func (s *Server) busyCooldownFor(channel string) time.Duration {
	cfg := s.Config()
	if cfg == nil {
		return 0
	}
	p := cfg.ChannelPolicy[channel]
	if p.BusyCooldownSeconds < 0 {
		return 0
	}
	if p.BusyCooldownSeconds > 0 {
		return time.Duration(p.BusyCooldownSeconds) * time.Second
	}
	return s.softCooldownFor(channel)
}

// timeoutCooldownFor 解析「上游判静默超时（504）」之后这一跳要冷藏多久。
// 0/缺省 = 老行为 timeoutCooldown（5 分钟）；正数 = 该秒数；负数 = 不冷却。
//
// 按次计费的链上，冷却期就是强制降级期：3.8 被 5 分钟冷却时，所有请求都会落到
// 3.7/3.6 上还照付一次额度。所以这条要能被渠道单独调小（GM 配 20 秒）。
func (s *Server) timeoutCooldownFor(channel string) time.Duration {
	cfg := s.Config()
	if cfg == nil {
		return timeoutCooldown
	}
	p := cfg.ChannelPolicy[channel]
	if p.TimeoutCooldownSeconds < 0 {
		return 0
	}
	if p.TimeoutCooldownSeconds > 0 {
		return time.Duration(p.TimeoutCooldownSeconds) * time.Second
	}
	return timeoutCooldown
}

// retry500For 报告这个渠道是否要在上游 500 时先原地重试一次。
// 默认关：多数渠道的 500 就是真错，透给客户端比连撞两次更快。
func (s *Server) retry500For(channel string) bool {
	cfg := s.Config()
	if cfg == nil {
		return false
	}
	return cfg.ChannelPolicy[channel].Retry500Once
}

// PolicyNote 是一条启动自检结论。Fatal=true 表示这条配置一定是废话且会误导人，
// 进程不该带着它起来；否则只是「在这些模型上不生效」的提示。
type PolicyNote struct {
	Fatal   bool
	Channel string
	Aliases []string
	Fields  []string
}

func (n PolicyNote) String() string {
	kind := "策略在单跳模型上不生效"
	if n.Fatal {
		kind = "策略完全无效（渠道只服务单跳模型，多跳字段永远读不到）"
	}
	return fmt.Sprintf("%s channel=%s 字段=[%s] 影响模型=[%s]",
		kind, n.Channel, strings.Join(n.Fields, ","), strings.Join(capNames(n.Aliases, 6), ","))
}

// capNames 把名字列表压到 n 个，超出部分折成「等 N 个」—— 启动日志一行能读完才有用。
func capNames(names []string, n int) []string {
	if len(names) <= n {
		return names
	}
	return append(append([]string{}, names[:n]...), fmt.Sprintf("等 %d 个", len(names)))
}

// ValidatePolicies 对照实际 alias 链检查 channelPolicy：
//
//   - 渠道**只**服务单跳模型、却配了对冲/冷却类字段 → Fatal（这些字段永远不会被读到，
//     留着的人会以为「对冲已经开了」，2026-11-10 的 noteSerialFallback 就是为这种
//     静默失效留的告警）；
//   - 渠道同时服务多跳模型 → 只提示，不拦：同一份策略在多跳链上确实生效，
//     单跳模型只是用不上（运行期也已经跳过向单跳链埋静默冷却）。
func ValidatePolicies(cfg *config.Config, am *alias.Map) []PolicyNote {
	if cfg == nil || am == nil || len(cfg.ChannelPolicy) == 0 {
		return nil
	}
	chains := am.Chains()
	single := map[string][]string{} // channel -> 单跳模型名
	multi := map[string]bool{}      // channel 是否被多跳链用过
	for _, c := range chains {
		if len(c.Channels) == 0 {
			continue
		}
		if len(c.Channels) == 1 {
			single[c.Channels[0]] = append(single[c.Channels[0]], c.Name)
			continue
		}
		for _, ch := range c.Channels {
			multi[ch] = true
		}
	}
	channels := make([]string, 0, len(cfg.ChannelPolicy))
	for ch := range cfg.ChannelPolicy {
		channels = append(channels, ch)
	}
	sort.Strings(channels)
	var notes []PolicyNote
	for _, ch := range channels {
		fields := policyRaceFields(cfg.ChannelPolicy[ch])
		if len(fields) == 0 {
			continue
		}
		names := single[ch]
		if len(names) == 0 {
			continue // 这个渠道没有单跳模型，字段全部有意义
		}
		sort.Strings(names)
		notes = append(notes, PolicyNote{
			Fatal:   !multi[ch],
			Channel: ch,
			Aliases: names,
			Fields:  fields,
		})
	}
	return notes
}
