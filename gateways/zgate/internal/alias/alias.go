// Package alias reads ~/.zcode/v2/model-alias-map.json and resolves a display
// name (or a legacy id) to the upstream target it stands for.
//
// The file is rewritten by tools/model_alias.py while ZCode is running, so it is
// re-read whenever its mtime changes; a broken file keeps the previous snapshot
// instead of dropping every route.
package alias

import (
	"encoding/json"
	"os"
	"sort"
	"sync"
	"time"
)

// Hop is one step of a merged chain: its own upstream id, host and channel.
type Hop struct {
	Upstream  string  `json:"upstream"`
	Base      string  `json:"base"`
	Channel   string  `json:"channel"`
	Price     float64 `json:"price"`
	Original  string  `json:"original"`
	BaseModel string  `json:"base_model"`
	// Protocol 是这一跳自己的线路协议（chat / messages / responses）。
	// 同一型号可以把 chat 与 messages 合成一条链，所以协议必须按跳记；
	// 空值表示沿用条目级 Target.Protocol。
	Protocol string `json:"protocol"`
	// Proxy 是这一跳专属的出口（"http://host:port"），空值表示按直连走。
	// 同一个 upstream 允许在链里出现两次、只差出口：一次直连、一次经机场。
	// 地区受限的模型（gpt / beam / muse）就靠这第二跳兜住，机型写在
	// alias map 里，不改代码。
	Proxy string `json:"proxy,omitempty"`
}

// Target is one upstream behind a display name.
type Target struct {
	Channel   string   `json:"channel"`
	Region    string   `json:"region"`
	Upstream  string   `json:"upstream"`
	BaseModel string   `json:"base_model"`
	Base      string   `json:"base"`
	Protocol  string   `json:"protocol"`
	Original  string   `json:"original"`
	Price     float64  `json:"price"`
	Group     string   `json:"group"`
	Fallbacks []string `json:"fallbacks"`
	Chain     []Hop    `json:"chain"`
	LegacyIDs []string `json:"legacy_ids"`
}

type file struct {
	Version     int               `json:"version"`
	GeneratedAt string            `json:"generated_at"`
	Slot        string            `json:"slot"`
	Models      map[string]Target `json:"models"`
	Legacy      map[string]string `json:"legacy"`
}

// Map is a hot-reloading view of the alias file.
type Map struct {
	path  string
	mu    sync.RWMutex
	mtime time.Time
	size  int64
	data  *file
	// rev 是快照版本号：每次成功换快照 +1，进程内单调递增。
	// 路由层靠它判断「目录视图要不要重建」，比每次都排序一遍 93 条便宜得多。
	rev uint64
}

// New returns a Map bound to path; a missing file is not an error.
func New(path string) *Map {
	m := &Map{path: path}
	m.Reload()
	return m
}

// Path is the file this map watches.
func (m *Map) Path() string { return m.path }

// Reload re-reads the file when it changed. It is cheap enough to call per request.
func (m *Map) Reload() {
	stat, err := os.Stat(m.path)
	if err != nil {
		return
	}
	m.mu.RLock()
	// mtime alone misses a rewrite within the filesystem timestamp granularity
	// (or a writer that preserves mtime); the size catches those.
	same := m.data != nil && stat.ModTime().Equal(m.mtime) && stat.Size() == m.size
	m.mu.RUnlock()
	if same {
		return
	}
	raw, err := os.ReadFile(m.path)
	if err != nil {
		return
	}
	var next file
	if err := json.Unmarshal(raw, &next); err != nil {
		return
	}
	m.mu.Lock()
	m.data = &next
	m.mtime = stat.ModTime()
	m.size = stat.Size()
	m.rev++
	m.mu.Unlock()
}

// Revision 是当前快照的版本号（0 = 还没成功读过文件）。
func (m *Map) Revision() uint64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.rev
}

// Targets 返回别名表的浅拷贝（map 值类型，Hop 切片仍共享底层数组但只读）。
// 给管理面 dump 路由用：调用方拿不到 *Map，也就改不了内部状态。
func (m *Map) Targets() map[string]Target {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.data == nil {
		return map[string]Target{}
	}
	out := make(map[string]Target, len(m.data.Models))
	for k, v := range m.data.Models {
		out[k] = v
	}
	return out
}

// Legacy 返回 legacy id → 显示名的映射拷贝。
func (m *Map) Legacy() map[string]string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.data == nil {
		return map[string]string{}
	}
	out := make(map[string]string, len(m.data.Legacy))
	for k, v := range m.data.Legacy {
		out[k] = v
	}
	return out
}

// Count is how many display names the file carries (0 when it is missing).
func (m *Map) Count() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.data == nil {
		return 0
	}
	return len(m.data.Models)
}

// Resolve maps a display name or a legacy id to its target.
func (m *Map) Resolve(model string) (Target, bool) {
	if model == "" {
		return Target{}, false
	}
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.data == nil {
		return Target{}, false
	}
	if t, ok := m.data.Models[model]; ok {
		return t, true
	}
	if display, ok := m.data.Legacy[model]; ok {
		if t, ok := m.data.Models[display]; ok {
			return t, true
		}
	}
	return Target{}, false
}

// CatalogEntry is one row of the aggregated GET /v1/models view. zgate owns the
// namespace: a display name is its own canonical id, while a legacy id points
// back to the display name it resolves to.
type CatalogEntry struct {
	ID          string `json:"id"`
	Object      string `json:"object"`
	OwnedBy     string `json:"owned_by"`
	CanonicalID string `json:"canonical_id"`
	Group       string `json:"group"`
	ChainHops   int    `json:"chain_hops"`
}

// ChainView 是一条模型链的只读快照，供启动自检与 /health 用：名字 + 渠道序列。
// Direct 表示这个模型没有链（老式单上游目标），Channels 只有一项。
type ChainView struct {
	Name     string
	Channels []string
	Direct   bool
}

// Chains 返回所有模型的渠道序列（按名字排序，确定性顺序便于日志与自检对读）。
// 只读快照，不暴露内部 map；调用方拿不到 Hop 的其它字段，避免自检代码顺手改路由。
func (m *Map) Chains() []ChainView {
	m.Reload()
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.data == nil {
		return nil
	}
	names := make([]string, 0, len(m.data.Models))
	for name := range m.data.Models {
		names = append(names, name)
	}
	sort.Strings(names)
	out := make([]ChainView, 0, len(names))
	for _, name := range names {
		t := m.data.Models[name]
		view := ChainView{Name: name}
		if len(t.Chain) == 0 {
			view.Direct = true
			if t.Channel != "" {
				view.Channels = []string{t.Channel}
			}
		} else {
			for _, hop := range t.Chain {
				view.Channels = append(view.Channels, hop.Channel)
			}
		}
		out = append(out, view)
	}
	return out
}

// Catalog returns the unified namespace as a deterministic, deduplicated list:
// display names first (sorted), then legacy ids that are not themselves display
// names (sorted). Deterministic order keeps GET /v1/models and GET /models
// byte-identical across calls and map iterations.
func (m *Map) Catalog() []CatalogEntry {
	m.Reload()
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.catalogLocked()
}

// CatalogAt 返回当前快照的目录与版本号，不碰文件系统。
// 路由层的 /models 缓存用它：先按节流刷新别名，再取一次快照，版本没变就直接
// 复用上一次序列化好的字节。
func (m *Map) CatalogAt() ([]CatalogEntry, uint64) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.catalogLocked(), m.rev
}

func (m *Map) catalogLocked() []CatalogEntry {
	if m.data == nil {
		return []CatalogEntry{}
	}
	group := func(name string) (string, int) {
		t, ok := m.data.Models[name]
		if !ok {
			return "", 0
		}
		hops := len(t.Chain)
		if hops == 0 {
			hops = 1 // a direct single-upstream target is one hop
		}
		return t.Group, hops
	}
	names := make([]string, 0, len(m.data.Models))
	for name := range m.data.Models {
		names = append(names, name)
	}
	sort.Strings(names)
	out := make([]CatalogEntry, 0, len(m.data.Models)+len(m.data.Legacy))
	for _, name := range names {
		g, hops := group(name)
		out = append(out, CatalogEntry{
			ID: name, Object: "model", OwnedBy: "zgate",
			CanonicalID: name, Group: g, ChainHops: hops,
		})
	}
	legacy := make([]string, 0, len(m.data.Legacy))
	for id := range m.data.Legacy {
		if _, isName := m.data.Models[id]; isName {
			continue // already emitted as a display name
		}
		legacy = append(legacy, id)
	}
	sort.Strings(legacy)
	for _, id := range legacy {
		canonical := m.data.Legacy[id]
		g, hops := group(canonical)
		out = append(out, CatalogEntry{
			ID: id, Object: "model", OwnedBy: "zgate",
			CanonicalID: canonical, Group: g, ChainHops: hops,
		})
	}
	return out
}
