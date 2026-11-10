package config

import (
	"encoding/json"
	"testing"
)

// 真实 zgate.json 形态：显式给了 mode 时不能被缺省逻辑改写，
// 而新加的字段必须能通过 JSON 落到结构体上（配置写错时是静默失效，
// 所以这里用一条与线上同形的文档锁住字段名）。
func TestReasoningGuardJSONWiring(t *testing.T) {
	raw := `{
  "session": "unified-router",
  "reasoningGuard": {
    "enabled": true,
    "mode": "auto",
    "models": ["Iceman"],
    "maxRetries": 5,
    "maxProbeBytes": 32768,
    "injectNotice": true,
    "giveUpAfter": 3,
    "giveUpForSeconds": 120,
    "forceEffort": "high",
    "forceEffortModels": ["Iceman", "iceman-contributor-free"]
  },
  "streamIdleHeartbeatSec": 20
}`
	var c Config
	if err := json.Unmarshal([]byte(raw), &c); err != nil {
		t.Fatalf("解析失败：%v", err)
	}
	c.applyDefaults()
	if c.ReasoningGuard.Mode != "auto" {
		t.Fatalf("mode = %q, want auto", c.ReasoningGuard.Mode)
	}
	if !c.ReasoningGuard.InjectNotice {
		t.Fatal("injectNotice 没落到结构体上")
	}
	if c.ReasoningGuard.MaxRetries != 5 || c.ReasoningGuard.GiveUpAfter != 3 || c.ReasoningGuard.GiveUpForSeconds != 120 {
		t.Fatalf("数值字段没落上：%+v", c.ReasoningGuard)
	}
	if c.ReasoningGuard.ForceEffort != "high" || len(c.ReasoningGuard.ForceEffortModels) != 2 {
		t.Fatalf("forceEffort 没落到结构体上：%+v", c.ReasoningGuard)
	}
	if c.StreamIdleHeartbeatSeconds != 20 {
		t.Fatalf("streamIdleHeartbeatSec = %d, want 20", c.StreamIdleHeartbeatSeconds)
	}
}

// 缺省：老配置（只有 enabled+models）必须保持老行为（models 模式），
// 而新增的重抽/心跳参数要有可用默认值；负数明确关闭心跳。
func TestReasoningGuardDefaults(t *testing.T) {
	var c Config
	if err := json.Unmarshal([]byte(`{"reasoningGuard":{"enabled":true,"models":["Iceman"]}}`), &c); err != nil {
		t.Fatalf("解析失败：%v", err)
	}
	c.applyDefaults()
	if c.ReasoningGuard.Mode != "models" {
		t.Fatalf("有白名单时缺省 mode 应为 models，got %q", c.ReasoningGuard.Mode)
	}
	if c.ReasoningGuard.MaxRetries != 5 || c.ReasoningGuard.GiveUpAfter != 2 || c.ReasoningGuard.GiveUpForSeconds != 600 {
		t.Fatalf("缺省值不对：%+v", c.ReasoningGuard)
	}
	if c.StreamIdleHeartbeatSeconds != 15 {
		t.Fatalf("缺省心跳应为 15 秒，got %d", c.StreamIdleHeartbeatSeconds)
	}

	var off Config
	if err := json.Unmarshal([]byte(`{"streamIdleHeartbeatSec":-1}`), &off); err != nil {
		t.Fatalf("解析失败：%v", err)
	}
	off.applyDefaults()
	if off.StreamIdleHeartbeatSeconds != -1 {
		t.Fatalf("负数心跳应保持关闭，got %d", off.StreamIdleHeartbeatSeconds)
	}
}
