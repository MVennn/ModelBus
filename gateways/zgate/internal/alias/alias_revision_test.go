package alias

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

// 本文件只测 alias.go 新加的版本号与只读快照接口（Revision / Targets / Legacy /
// CatalogAt）。既有的 Resolve / Reload 契约由 alias_test.go 负责，这里不重复。

const revisionSample = `{
  "version": 1,
  "models": {
    "W/0.03/DeepSeek-41-Fs": {"channel":"WB","upstream":"global:deepseek-v4.1-flash-sg","base":"http://127.0.0.1:7863/v1","protocol":"chat"},
    "O/0.09/Claude-Haiku-55": {"channel":"OC","upstream":"claude-haiku-5.5","base":"https://opencode.ai/zen/go/v1","protocol":"messages"}
  },
  "legacy": {"global:deepseek-v4.1-flash-sg": "W/0.03/DeepSeek-41-Fs"}
}`

const revisionSampleSmall = `{"models":{"O/0.09/Claude-Haiku-55":{"channel":"OC","upstream":"claude-haiku-5.5"}},"legacy":{}}`

// rewrite 覆写别名文件并把 mtime 推到未来，模拟 tools/model_alias.py 在运行中重写。
// 部分文件系统在同一时钟刻度里看不出 mtime 变化，只靠 mtime 会漏掉一次重写。
func rewrite(t *testing.T, path, body string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		t.Fatal(err)
	}
	future := time.Now().Add(2 * time.Second)
	if err := os.Chtimes(path, future, future); err != nil {
		t.Fatal(err)
	}
}

func catalogIDs(entries []CatalogEntry) []string {
	out := make([]string, 0, len(entries))
	for _, e := range entries {
		out = append(out, e.ID)
	}
	return out
}

func TestRevisionTracksSuccessfulReloads(t *testing.T) {
	path := filepath.Join(t.TempDir(), "map.json") // 故意不创建：文件缺失不是错误
	m := New(path)
	if got := m.Revision(); got != 0 {
		t.Fatalf("missing file: Revision()=%d, want 0", got)
	}
	if got := m.Count(); got != 0 {
		t.Fatalf("missing file: Count()=%d, want 0", got)
	}

	rewrite(t, path, revisionSample)
	m.Reload()
	if got := m.Revision(); got != 1 {
		t.Fatalf("after first good read: Revision()=%d, want 1", got)
	}
	if got := m.Count(); got != 2 {
		t.Fatalf("after first good read: Count()=%d, want 2", got)
	}

	// 文件没动：mtime 与 size 都没变，Reload 必须原地不动。
	m.Reload()
	m.Reload()
	if got := m.Revision(); got != 1 {
		t.Fatalf("unchanged file bumped Revision() to %d", got)
	}

	rewrite(t, path, revisionSampleSmall)
	m.Reload()
	if got := m.Revision(); got != 2 {
		t.Fatalf("changed file: Revision()=%d, want 2", got)
	}
	if got := m.Count(); got != 1 {
		t.Fatalf("changed file: Count()=%d, want 1", got)
	}
}

func TestRevisionUnchangedOnBrokenFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "map.json")
	rewrite(t, path, revisionSample)
	m := New(path)
	if got := m.Revision(); got != 1 {
		t.Fatalf("Revision()=%d, want 1", got)
	}

	rewrite(t, path, "{not json")
	m.Reload()
	if got := m.Revision(); got != 1 {
		t.Fatalf("broken file bumped Revision() to %d; the last good snapshot must stay", got)
	}
	if got := m.Count(); got != 2 {
		t.Fatalf("broken file dropped the snapshot: Count()=%d, want 2", got)
	}
	if target, ok := m.Resolve("W/0.03/DeepSeek-41-Fs"); !ok || target.Channel != "WB" {
		t.Fatalf("broken file lost the route: %+v ok=%v", target, ok)
	}
}

func TestTargetsReturnsCopy(t *testing.T) {
	path := filepath.Join(t.TempDir(), "map.json")
	rewrite(t, path, revisionSample)
	m := New(path)

	targets := m.Targets()
	if len(targets) != 2 {
		t.Fatalf("Targets() len=%d, want 2", len(targets))
	}

	// 调用方随便改返回值：增、删、覆盖都不许影响内部快照。
	targets["Injected/Model"] = Target{Channel: "XX", Upstream: "injected"}
	delete(targets, "W/0.03/DeepSeek-41-Fs")
	targets["O/0.09/Claude-Haiku-55"] = Target{Channel: "XX", Upstream: "hijacked"}

	if _, ok := m.Resolve("Injected/Model"); ok {
		t.Fatalf("adding to the returned map added a live route")
	}
	if _, ok := m.Resolve("W/0.03/DeepSeek-41-Fs"); !ok {
		t.Fatalf("deleting from the returned map removed a live route")
	}
	if target, ok := m.Resolve("O/0.09/Claude-Haiku-55"); !ok || target.Upstream != "claude-haiku-5.5" || target.Channel != "OC" {
		t.Fatalf("overwriting a returned entry leaked into the live snapshot: %+v ok=%v", target, ok)
	}
	if got := m.Count(); got != 2 {
		t.Fatalf("Count()=%d after mutating the copy, want 2", got)
	}
	if got := len(m.Targets()); got != 2 {
		t.Fatalf("second Targets() len=%d, want 2", got)
	}
}

func TestLegacyReturnsCopy(t *testing.T) {
	path := filepath.Join(t.TempDir(), "map.json")
	rewrite(t, path, revisionSample)
	m := New(path)

	legacy := m.Legacy()
	if got := legacy["global:deepseek-v4.1-flash-sg"]; got != "W/0.03/DeepSeek-41-Fs" {
		t.Fatalf("Legacy()[global:deepseek-v4.1-flash-sg]=%q", got)
	}

	legacy["global:deepseek-v4.1-flash-sg"] = "Injected/Model"
	legacy["ghost:id"] = "W/0.03/DeepSeek-41-Fs"

	if target, ok := m.Resolve("global:deepseek-v4.1-flash-sg"); !ok || target.Upstream != "global:deepseek-v4.1-flash-sg" {
		t.Fatalf("mutating the returned legacy map leaked into the live snapshot: %+v ok=%v", target, ok)
	}
	if _, ok := m.Resolve("ghost:id"); ok {
		t.Fatalf("added legacy id resolved against the live snapshot")
	}
	if got := m.Legacy()["global:deepseek-v4.1-flash-sg"]; got != "W/0.03/DeepSeek-41-Fs" {
		t.Fatalf("live legacy mapping changed to %q", got)
	}
}

func TestCatalogAtDoesNotReload(t *testing.T) {
	path := filepath.Join(t.TempDir(), "map.json")
	rewrite(t, path, revisionSample)
	m := New(path)
	if got := m.Revision(); got != 1 {
		t.Fatalf("Revision()=%d, want 1", got)
	}

	before, rev := m.CatalogAt()
	if rev != 1 || m.Revision() != 1 {
		t.Fatalf("CatalogAt rev=%d, Revision()=%d, want both 1", rev, m.Revision())
	}
	// 2 个显示名 + 1 个非显示名的 legacy id
	if len(before) != 3 {
		t.Fatalf("catalog len=%d, want 3: %v", len(before), catalogIDs(before))
	}

	// 磁盘上换一份内容，但 CatalogAt 不许碰文件系统。
	rewrite(t, path, revisionSampleSmall)
	stale, rev2 := m.CatalogAt()
	if rev2 != 1 {
		t.Fatalf("CatalogAt moved to rev %d without an explicit Reload", rev2)
	}
	if len(stale) != 3 {
		t.Fatalf("CatalogAt re-read the file: len=%d, want the old 3 rows", len(stale))
	}
	if ids := catalogIDs(stale); ids[0] != "O/0.09/Claude-Haiku-55" || ids[1] != "W/0.03/DeepSeek-41-Fs" {
		t.Fatalf("catalog order/content changed: %v", ids)
	}

	// 显式 Reload 之后才换快照。
	m.Reload()
	after, rev3 := m.CatalogAt()
	if rev3 != 2 || m.Revision() != 2 {
		t.Fatalf("after Reload: CatalogAt rev=%d, Revision()=%d, want 2", rev3, m.Revision())
	}
	if len(after) != 1 {
		t.Fatalf("after Reload: catalog len=%d, want 1: %v", len(after), catalogIDs(after))
	}
	if after[0].ID != "O/0.09/Claude-Haiku-55" || after[0].CanonicalID != "O/0.09/Claude-Haiku-55" {
		t.Fatalf("after Reload: unexpected row %+v", after[0])
	}
}

func TestCatalogAtOnMissingFile(t *testing.T) {
	m := New(filepath.Join(t.TempDir(), "absent.json"))

	cat, rev := m.CatalogAt()
	if rev != 0 || m.Revision() != 0 {
		t.Fatalf("CatalogAt rev=%d, Revision()=%d, want both 0", rev, m.Revision())
	}
	if cat == nil {
		t.Fatalf("CatalogAt must return an empty slice, not nil (JSON must encode as [] not null)")
	}
	if len(cat) != 0 {
		t.Fatalf("catalog len=%d, want 0", len(cat))
	}

	// 空快照也要能安全改：拿到的 map 不是内部状态。
	targets := m.Targets()
	if targets == nil {
		t.Fatalf("Targets() returned nil, want an empty map")
	}
	targets["x"] = Target{Upstream: "y"}
	if _, ok := m.Resolve("x"); ok {
		t.Fatalf("mutating the empty copy added a live route")
	}
	legacy := m.Legacy()
	if legacy == nil {
		t.Fatalf("Legacy() returned nil, want an empty map")
	}
	legacy["x"] = "y"
	if _, ok := m.Resolve("x"); ok {
		t.Fatalf("mutating the empty legacy copy added a live route")
	}
}
