// Package config loads zgate.json and applies defaults, env overrides and
// path expansion. Nothing here knows about HTTP or child processes.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// Log says where zgate and its children write.
type Log struct {
	Dir   string `json:"dir"`
	File  string `json:"file"`
	MaxMB int    `json:"maxMB"`
}

// Upstream is one channel: where it lives and which child (if any) serves it.
type Upstream struct {
	Base   string `json:"base"`
	Child  string `json:"child"`
	KeyEnv string `json:"keyEnv"`
}

// Child is a local upstream process zgate supervises.
type Child struct {
	Policy              string   `json:"policy"` // always | ondemand
	IdleSeconds         int      `json:"idleSeconds"`
	Exe                 string   `json:"exe"`
	Args                []string `json:"args"`
	Cwd                 string   `json:"cwd"`
	Port                int      `json:"port"`
	Health              string   `json:"health"`
	StartTimeoutSeconds int      `json:"startTimeoutSeconds"`
	// Windows are local-time "HH:MM-HH:MM" ranges during which the child is
	// treated as policy=always (sign-in / keepalive slots). Empty means never.
	Windows []string `json:"windows"`
}

// ReasoningGuard controls transparent re-drawing of chat SSE streams whose
// upstream backend returned only encrypted reasoning (reasoning_details with
// type "reasoning.encrypted") and no plaintext reasoning_content. The GUI
// cannot render an opaque replay blob, so those turns show an empty thinking
// block. The guard inspects the first SSE deltas before any byte reaches the
// client; when they look like an encrypted-only response it discards the
// buffer and retries the same hop until a plaintext-thinking stream arrives.
// Zero value = disabled, so existing configs are byte-for-byte unchanged.
// Mode 决定守卫圈哪些模型：
//   - "models"：只守 Models 白名单（老行为，配置里显式列模型名才生效）；
//   - "auto"  ：凡是客户端声明要思考（reasoning_effort / thinking=enabled）的流式
//     请求一律探针。新增同类模型不需要改配置——这正是「以后再有模型只回加密
//     思考」时不用二次排障的关键。
//
// 缺省且 Models 非空时按 "models" 走，保持老配置逐字节等效。
type ReasoningGuard struct {
	Enabled       bool     `json:"enabled"`
	Mode          string   `json:"mode"`
	Models        []string `json:"models"`
	MaxRetries    int      `json:"maxRetries"`
	MaxProbeBytes int      `json:"maxProbeBytes"`
	// InjectNotice：达上限放行加密流时，在流首注入一条可读的 reasoning delta，
	// 让宿主至少渲染出「思考被上游加密」而不是一个空块。
	InjectNotice bool `json:"injectNotice"`
	// GiveUpAfter / GiveUpForSeconds：某个模型连续 N 轮「重抽到上限仍是纯加密」
	// 且从未见过明文，就在内存里把它记进跳过表，一段时间内不再白等重抽
	// （上游会切回明文，过期后自动重新探路）。0 = 默认 2 次 / 600 秒。
	GiveUpAfter      int `json:"giveUpAfter"`
	GiveUpForSeconds int `json:"giveUpForSeconds"`
	// ForceEffort / ForceEffortModels：客户端没声明思考档位时，由网关替它补上
	// reasoning_effort（例如 "high"）。2026-11-10 实测：DSH 的模型选择器没有逐模型
	// 默认档位（catalog 里 reasoning.defaultEffort 为空 → 选中的是 "Default" 伪档位），
	// 请求体里根本不带 reasoning_effort，上游于是只下发加密思考；而守卫的触发条件
	// 正是「客户端声明要思考」，于是连重抽都不会发生，思考永远空白。
	// 放在网关补档比反复给前端 minified 代码打补丁稳：profile 重建（实测 11-10 12:35）
	// 会把前端补丁冲掉，网关配置不会。
	// ForceEffortModels 为空时回落到 Models 白名单；两者都空则一律不注入。
	ForceEffort       string   `json:"forceEffort"`
	ForceEffortModels []string `json:"forceEffortModels"`
	// ProbeSeconds：单次尝试里「最多等多久拿到可判定信号」。加密分流那一路上游
	// 在思考阶段整段静默（不给明文 reasoning_content，也不给正文），只有思考结束
	// 吐第一个正文块时才判得出来 —— 实测要等 11 s / 61 s。设上限后到点就换连接
	// 重抽，把「等满一整段思考」压到固定几百毫秒到十几秒。重抽预算花完的最后一发
	// 不再探测，直接放行上游原始流（探测只会再白等一个上限）。0/缺省 = 12 秒；负数 = 不设上限。
	ProbeSeconds int `json:"probeSeconds"`
}

// ChannelPolicy 是「按渠道」的路由策略，只对显式配置过的渠道生效。
// 零值 = 全关 = 老行为逐字节不变：没有配置 channelPolicy 的渠道完全走原来的
// 串行链 + 30min/45s 冷却逻辑。存在的理由见 docs/MODEL-PROVIDERS.md §4.11：
// catiecli 中转的 Gemini 链首两跳常态化 503、且要 4-14 秒才回话，
// 串行等到死才回落会把「首字速度」压到十几秒。
type ChannelPolicy struct {
	// SoftCooldownSeconds：这一渠道的一跳被判「暂时没用」（HTTP 5xx / 首块超时）
	// 后跳过多久。0 = 老行为（只有 504 冷却 5 分钟）。上游 503 high demand 是
	// 分钟级窗口，90 秒足够跨过去，又不会让恢复的跳被长期埋掉。
	SoftCooldownSeconds int `json:"softCooldownSeconds"`
	// SilenceCooldownSeconds：这一跳「不说话」之后跳过多久。两种情况共用：
	// ① 2xx 但首块超时（上游 200 却十几秒不吐正文）；② 连响应头都不给
	// （errUpstreamSilent，catiecli 的 3.8/3.7 现在就是收下请求、几十秒不发头）。
	// **故意比 SoftCooldownSeconds 短**：静默不等于死，3.6/3.5 常态 9-14 秒
	// 才出正文，判它「死了」会把自己的链饿空。0 = 静默不冷却（老行为）。
	SilenceCooldownSeconds int `json:"silenceCooldownSeconds"`
	// RateLimitBackoffMs：收到 429 后就地退避再重试同一跳的时长。
	// 0/缺省 = 老行为 700ms；负数 = 不就地重试，直接换下一跳（省一次白等）。
	RateLimitBackoffMs int `json:"rateLimitBackoffMs"`
	// FirstBlockMs：2xx 之后等「第一个真内容块」的上限，超时判定该跳失败并换跳。
	// 只对 SSE 生效；0 = 关（老行为：来什么转什么，空流也会一直挂着）。
	// 「真内容块」= SSE data 行里带非空 delta.content 或 delta.reasoning_content，
	// 只有 role 的空帧不算 —— 上游常见「先回 200 + 一帧 role 然后十几秒不说话」。
	FirstBlockMs int `json:"firstBlockMs"`
	// HedgeAfterMs：发出首跳后多久还没见到真首块就并行发出下一跳（对冲）。
	// 两路谁先拿到首块谁赢，另一路立刻取消。0 = 不对冲（老行为）。
	HedgeAfterMs int `json:"hedgeAfterMs"`
	// MaxParallel：同时最多几路在路上。0/缺省 = 2（最多只叠一层，避免计费翻倍）。
	MaxParallel int `json:"maxParallel"`
	// AuthFailCooldownHours：403 若是「key 无效 / 被封 / 无权限」类错误，整渠道禁用多久。
	// 0 = 老行为（403 原样回给客户端）。这是「403 自动禁用」的落点。
	AuthFailCooldownHours int `json:"authFailCooldownHours"`
	// HeaderTimeoutSec：这一渠道「等上游响应头」的容忍上限（秒），覆盖全局
	// upstreamHeaderTimeoutSec。0 = 用全局的那一档；负数 = 这一渠道不设看门狗。
	// 按渠道给窗口的两轮历史：20:05 想让「慢」的哈基米活下来（HJ 25s）、让「死」的
	// catiecli 早让位（GM 12s）；21:30 又全部收回 —— 当天 GM 判死 125 次里上游真说过
	// 503 的只占 5.3%，HJ 判死 32 次有一半与 502 同秒。本地判死 → 502 → 客户端重试 →
	// 上游重跑，这才是「后台在跑 token、本地已断开」的来源。判死权归上游，两个渠道都 -1。
	HeaderTimeoutSec int `json:"headerTimeoutSec"`
}

// Config is the whole file.
type Config struct {
	Listen          string         `json:"listen"`
	AliasMap        string         `json:"aliasMap"`
	ProviderConfig  string         `json:"providerConfig"`
	WBGatewayConfig string         `json:"wbGatewayConfig"`
	QoderEnvFile    string         `json:"qoderEnvFile"`
	QwenEnvFile     string         `json:"qwenEnvFile"`
	QiniuEnvFile    string         `json:"qiniuEnvFile"`
	GeminiEnvFile   string         `json:"geminiEnvFile"`
	HajimiEnvFile   string         `json:"hajimiEnvFile"`
	Session         string         `json:"session"`
	ReasoningGuard  ReasoningGuard `json:"reasoningGuard"`
	// StreamIdleHeartbeatSeconds：SSE 转发空闲多久补一条注释心跳（": zgate keepalive"）。
	// 上游思考阶段常静默 30-60 秒（实测 iceman 断 51.9 秒），中间层与客户端都会判空闲。
	// 0/缺省 = 15 秒；负数 = 关闭。
	StreamIdleHeartbeatSeconds int `json:"streamIdleHeartbeatSec"`
	// EarlyCommitMs：流式请求等上游响应头超过这么久，就先对客户端交卷 200 + text/event-stream，
	// 之后按 EarlyKeepaliveSec 补 SSE 注释心跳；上游最终失败时改写成流内 error 事件，
	// 而不是回一个客户端早就放弃的 502。0/缺省 = 8000 毫秒；负数 = 关闭。
	EarlyCommitMs int `json:"earlyCommitMs"`
	// EarlyKeepaliveSec：提前交卷后的心跳间隔（秒），0/缺省 = 10。
	EarlyKeepaliveSec int `json:"earlyKeepaliveSec"`
	// UpstreamHeaderTimeoutSec：流式请求「已经连上上游、却连响应头都不给」的忍耐上限（秒）。
	// 到点判这一跳沉默（errUpstreamSilent）并让位给下一跳。0/缺省 = 12 秒，
	// 负数 = 关掉这个看门狗（老 behavior：谁不回就一直挂着）。
	// 为什么要可配：2026-11-10 实测同一跳 catiecli ais-gemini-3.8-flash 要 60.2 秒才回
	// 503，而哈基米福利跳 3 秒就能出字；一档 45 秒时 8 跳链轮转要 3-4 分钟，
	// 降到 12 秒后 4 轮 ≈ 48 秒见分晓，且不用重新编译就能再调。
	UpstreamHeaderTimeoutSec int                      `json:"upstreamHeaderTimeoutSec"`
	ChannelPolicy            map[string]ChannelPolicy `json:"channelPolicy"`
	Log                      Log                      `json:"log"`
	Upstreams                map[string]Upstream      `json:"upstreams"`
	Children                 map[string]Child         `json:"children"`

	Path string `json:"-"`
	Dir  string `json:"-"`
}

// Load reads path (or the default next to the binary) and normalises it.
func Load(path string) (*Config, error) {
	if path == "" {
		path = os.Getenv("ZGATE_CONFIG")
	}
	if path == "" {
		exe, err := os.Executable()
		if err == nil {
			path = filepath.Join(filepath.Dir(exe), "zgate.json")
		}
	}
	if path == "" {
		path = "zgate.json"
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("读不到配置 %s: %w", path, err)
	}
	var cfg Config
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return nil, fmt.Errorf("配置不是合法 JSON（%s）: %w", path, err)
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		abs = path
	}
	cfg.Path = abs
	cfg.Dir = filepath.Dir(abs)
	cfg.applyDefaults()
	if err := cfg.resolvePaths(); err != nil {
		return nil, err
	}
	return &cfg, nil
}

func (c *Config) applyDefaults() {
	if c.Listen == "" {
		c.Listen = "127.0.0.1:7871"
	}
	if v := os.Getenv("ZGATE_LISTEN"); v != "" {
		c.Listen = v
	}
	if c.AliasMap == "" {
		c.AliasMap = "~/.zcode/v2/model-alias-map.json"
	}
	if v := os.Getenv("UNIFIED_MODEL_MAP"); v != "" {
		c.AliasMap = v
	}
	if c.ProviderConfig == "" {
		c.ProviderConfig = "~/.zcode/v2/provider_config.json"
	}
	if v := os.Getenv("ZCODE_PERSONAL_PROVIDER_CONFIG_FILE"); v != "" {
		c.ProviderConfig = v
	}
	if c.WBGatewayConfig == "" {
		c.WBGatewayConfig = "../upstream/workbuddy/config.json"
	}
	if c.QoderEnvFile == "" {
		c.QoderEnvFile = "../../providers/qoder/.env.local"
	}
	if c.QwenEnvFile == "" {
		c.QwenEnvFile = "../../providers/qwen/.env.local"
	}
	if c.QiniuEnvFile == "" {
		c.QiniuEnvFile = "../../providers/qiniu/.env.local"
	}
	if c.GeminiEnvFile == "" {
		c.GeminiEnvFile = "../../providers/gemini/.env.local"
	}
	if c.HajimiEnvFile == "" {
		c.HajimiEnvFile = "../../providers/hajimi/.env.local"
	}
	if c.Session == "" {
		c.Session = os.Getenv("OPENCODE_SESSION")
	}
	if c.Session == "" {
		c.Session = "unified-router"
	}
	if c.ReasoningGuard.MaxRetries <= 0 {
		// 3 次不够：2026-11-10 12:01 实测连续 4 次（1 次首发 + 3 次重抽）全落
		// 同一路加密后端，达上限后放行的仍是加密流，用户白等 49 秒还没思考。
		// 默认给到 5，配合「换连接 + 每跳换会话头」才真正能脱身。
		c.ReasoningGuard.MaxRetries = 5
	}
	if c.ReasoningGuard.MaxProbeBytes <= 0 {
		c.ReasoningGuard.MaxProbeBytes = 32 * 1024
	}
	if c.ReasoningGuard.Mode == "" {
		if len(c.ReasoningGuard.Models) > 0 {
			c.ReasoningGuard.Mode = "models"
		} else {
			c.ReasoningGuard.Mode = "auto"
		}
	}
	c.ReasoningGuard.Mode = strings.ToLower(c.ReasoningGuard.Mode)
	if c.ReasoningGuard.GiveUpAfter <= 0 {
		c.ReasoningGuard.GiveUpAfter = 2
	}
	if c.ReasoningGuard.GiveUpForSeconds <= 0 {
		c.ReasoningGuard.GiveUpForSeconds = 600
	}
	if c.ReasoningGuard.ProbeSeconds == 0 {
		c.ReasoningGuard.ProbeSeconds = 12
	}
	if c.StreamIdleHeartbeatSeconds == 0 {
		c.StreamIdleHeartbeatSeconds = 15
	}
	if c.EarlyCommitMs == 0 {
		c.EarlyCommitMs = 8000
	}
	if c.EarlyKeepaliveSec == 0 {
		c.EarlyKeepaliveSec = 10
	}
	if c.UpstreamHeaderTimeoutSec == 0 {
		c.UpstreamHeaderTimeoutSec = 12
	}
	if c.Log.Dir == "" {
		c.Log.Dir = filepath.Join(os.Getenv("LOCALAPPDATA"), "ZCodeGateway")
	}
	if c.Log.File == "" {
		c.Log.File = "zgate.log"
	}
	if c.Log.MaxMB <= 0 {
		c.Log.MaxMB = 5
	}
	if c.Upstreams == nil {
		c.Upstreams = map[string]Upstream{}
	}
	if _, ok := c.Upstreams["OC"]; !ok {
		c.Upstreams["OC"] = Upstream{Base: "https://opencode.ai/zen/go/v1", KeyEnv: "OPENCODE_GO_KEY"}
	}
	if u, ok := c.Upstreams["WB"]; !ok {
		c.Upstreams["WB"] = Upstream{Base: "http://127.0.0.1:7863/v1", Child: "workbuddy", KeyEnv: "WB_GATEWAY_KEY"}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "WB_GATEWAY_KEY"
		c.Upstreams["WB"] = u
	}
	if u, ok := c.Upstreams["QD"]; !ok {
		c.Upstreams["QD"] = Upstream{Base: "http://127.0.0.1:8790/v1", Child: "qoder", KeyEnv: "QD_API_KEY"}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "QD_API_KEY"
		c.Upstreams["QD"] = u
	}
	// 千问平台只提供 Anthropic Messages 协议，无本地进程；模型经协议桥转发。
	if u, ok := c.Upstreams["QW"]; !ok {
		c.Upstreams["QW"] = Upstream{
			Base:   "https://maas.qianwenaiapi.com/apps/anthropic/v1",
			KeyEnv: "QWEN_API_KEY",
		}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "QWEN_API_KEY"
		c.Upstreams["QW"] = u
	}
	// 七牛云 AI 网关（api.qnaigc.com）同样只提供 Anthropic Messages。
	if u, ok := c.Upstreams["QN"]; !ok {
		c.Upstreams["QN"] = Upstream{
			Base:   "https://api.qnaigc.com/v1",
			KeyEnv: "QINIU_API_KEY",
		}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "QINIU_API_KEY"
		c.Upstreams["QN"] = u
	}
	// 谷歌 Gemini 经 catiecli 中转，OpenAI 兼容直连；无本地进程、无孪生跳。
	if u, ok := c.Upstreams["GM"]; !ok {
		c.Upstreams["GM"] = Upstream{
			Base:   "https://catiecli.sukaka.top/v1",
			KeyEnv: "GEMINI_API_KEY",
		}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "GEMINI_API_KEY"
		c.Upstreams["GM"] = u
	}
	// 哈基米（gemai.cc）是另一家 Gemini 转售站，OpenAI 兼容直连；
	// 无本地进程。它只承载 Gemini-AIS 链里「同代福利档」那一跳（见
	// tools/model_alias.py 的 HOP_PRIORITY），不单独出现在模型目录里。
	if u, ok := c.Upstreams["HJ"]; !ok {
		c.Upstreams["HJ"] = Upstream{
			Base:   "https://api.gemai.cc/v1",
			KeyEnv: "HJM_API_KEY",
		}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "HJM_API_KEY"
		c.Upstreams["HJ"] = u
	}
	for name, child := range c.Children {
		if child.Policy == "" {
			child.Policy = "ondemand"
		}
		if child.Policy != "always" && child.Policy != "ondemand" {
			child.Policy = "ondemand"
		}
		if child.IdleSeconds <= 0 {
			child.IdleSeconds = 900
		}
		if child.StartTimeoutSeconds <= 0 {
			child.StartTimeoutSeconds = 25
		}
		c.Children[name] = child
	}
}

func (c *Config) resolvePaths() error {
	for name, u := range c.Upstreams {
		u.Base = strings.TrimRight(expandEnv(u.Base), "/")
		c.Upstreams[name] = u
	}
	// 七牛云 AI 网关（api.qnaigc.com）同样只提供 Anthropic Messages。
	if u, ok := c.Upstreams["QN"]; !ok {
		c.Upstreams["QN"] = Upstream{
			Base:   "https://api.qnaigc.com/v1",
			KeyEnv: "QINIU_API_KEY",
		}
	} else if u.KeyEnv == "" {
		u.KeyEnv = "QINIU_API_KEY"
		c.Upstreams["QN"] = u
	}
	for name, child := range c.Children {
		child.Exe = c.resolveExe(child.Exe)
		child.Cwd = c.resolve(child.Cwd)
		args := make([]string, len(child.Args))
		for i, a := range child.Args {
			args[i] = c.resolveArg(a)
		}
		child.Args = args
		c.Children[name] = child
	}
	c.AliasMap = c.resolve(c.AliasMap)
	c.ProviderConfig = c.resolve(c.ProviderConfig)
	c.WBGatewayConfig = c.resolve(c.WBGatewayConfig)
	c.QoderEnvFile = c.resolve(c.QoderEnvFile)
	c.QwenEnvFile = c.resolve(c.QwenEnvFile)
	c.QiniuEnvFile = c.resolve(c.QiniuEnvFile)
	c.GeminiEnvFile = c.resolve(c.GeminiEnvFile)
	c.HajimiEnvFile = c.resolve(c.HajimiEnvFile)
	c.Log.Dir = c.resolve(c.Log.Dir)
	return nil
}

func (c *Config) resolve(p string) string {
	if p == "" {
		return ""
	}
	p = expandEnv(p)
	if strings.HasPrefix(p, "~") {
		if home, err := os.UserHomeDir(); err == nil {
			p = filepath.Join(home, strings.TrimPrefix(strings.TrimPrefix(p, "~"), string(os.PathSeparator)))
		}
	}
	if !filepath.IsAbs(p) {
		p = filepath.Join(c.Dir, p)
	}
	return filepath.Clean(p)
}

// resolveExe resolves a path, but leaves a bare command name ("python") alone so
// the OS keeps doing PATH lookup for it.
func (c *Config) resolveExe(p string) string {
	p = expandEnv(p)
	if p == "" {
		return ""
	}
	if filepath.Base(p) == p && !strings.HasPrefix(p, "~") {
		return p
	}
	return c.resolve(p)
}

// resolveArg resolves path-looking arguments and leaves flags alone.
//
// Flags are skipped (leading "-", and also Windows-style "/c"), and so are bare
// words: a path argument must be absolute, start with "." or contain a
// separator. That keeps "../upstream/qoder/qoder_proxy.py" working without
// turning cmd's "/c" into a drive-relative path.
func (c *Config) resolveArg(a string) string {
	a = expandEnv(a)
	if a == "" || strings.HasPrefix(a, "-") || strings.HasPrefix(a, "/") || strings.ContainsAny(a, " 	") {
		return a
	}
	if filepath.IsAbs(a) || strings.HasPrefix(a, ".") || strings.ContainsAny(a, "/\\") {
		return c.resolve(a)
	}
	return a
}

var rePercentVar = regexp.MustCompile(`%([A-Za-z_][A-Za-z0-9_]*)%`)

func expandEnv(s string) string {
	if strings.Contains(s, "%") {
		s = rePercentVar.ReplaceAllStringFunc(s, func(m string) string {
			name := strings.Trim(m, "%")
			if v, ok := os.LookupEnv(name); ok {
				return v
			}
			for _, kv := range os.Environ() {
				if i := strings.IndexByte(kv, '='); i > 0 && strings.EqualFold(kv[:i], name) {
					return kv[i+1:]
				}
			}
			return ""
		})
	}
	return os.Expand(s, func(key string) string {
		if v, ok := os.LookupEnv(key); ok {
			return v
		}
		// Windows keeps these upper-cased; accept the case-insensitive spelling too.
		for _, kv := range os.Environ() {
			if i := strings.IndexByte(kv, '='); i > 0 && strings.EqualFold(kv[:i], key) {
				return kv[i+1:]
			}
		}
		return ""
	})
}
