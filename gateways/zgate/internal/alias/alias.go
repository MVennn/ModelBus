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
	m.mu.Unlock()
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

// Catalog returns the unified namespace as a deterministic, deduplicated list:
// display names first (sorted), then legacy ids that are not themselves display
// names (sorted). Deterministic order keeps GET /v1/models and GET /models
// byte-identical across calls and map iterations.
func (m *Map) Catalog() []CatalogEntry {
	m.Reload()
	m.mu.RLock()
	defer m.mu.RUnlock()
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
