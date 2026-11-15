package router

import (
	"encoding/json"
	"strings"
	"testing"
)

// 本会话就在调这个功能：Read 出来的 prompt_stable.go 正文里四个标记全有，
// 工具输出里天然带标记。搬 tool 消息会把它从 assistant(tool_calls) 后面撕下来，
// 序列非法 —— 上游要么 400，要么把工具调用当正文文本吐出来（实测 DSML 标记）。
func TestStabilizeKeepsToolPairing(t *testing.T) {
	msgs := []map[string]any{
		{"role": "user", "content": "看看这个功能"},
		{"role": "assistant", "content": "", "tool_calls": []any{map[string]any{
			"id": "call_1", "type": "function",
			"function": map[string]any{"name": "Read", "arguments": "{\"file_path\":\"prompt_stable.go\"}"},
		}}},
		{"role": "tool", "tool_call_id": "call_1", "content": "var markers = []string{\"# Environment update\", \"The user hasn't heard from you in a while\"}"},
		{"role": "user", "content": "继续"},
	}
	out, moved, err := StabilizePromptPrefix(mustBody(t, msgs))
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if moved != 0 {
		t.Fatalf("tool 消息不该被搬，moved=%d", moved)
	}
	roles := rolesOf(t, out)
	want := []string{"user", "assistant", "tool", "user"}
	if strings.Join(roles, ",") != strings.Join(want, ",") {
		t.Fatalf("顺序被破坏: %v", roles)
	}
}

// 工具调用轮：末尾是 assistant(tool_calls) + tool(...)，注入必须落在 assistant 之前，
// 否则它成了「最新用户指令」，模型会去回那条提醒。
func TestStabilizeToolTailInsertion(t *testing.T) {
	msgs := []map[string]any{
		{"role": "system", "content": "sys"},
		{"role": "user", "content": "# Environment update\n今天是 11-15"},
		{"role": "user", "content": "跑测试"},
		{"role": "assistant", "content": "", "tool_calls": []any{map[string]any{
			"id": "call_1", "type": "function",
			"function": map[string]any{"name": "Bash", "arguments": "{\"command\":\"go test\"}"},
		}}},
		{"role": "tool", "tool_call_id": "call_1", "content": "ok"},
	}
	out, moved, err := StabilizePromptPrefix(mustBody(t, msgs))
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if moved != 1 {
		t.Fatalf("应搬 1 条注入，moved=%d", moved)
	}
	roles := rolesOf(t, out)
	if roles[len(roles)-1] != "tool" || roles[len(roles)-2] != "assistant" {
		t.Fatalf("末尾必须是 assistant+tool，实际 %v", roles)
	}
}

// 常规轮：最后一条是提问，注入插在它之前，提问仍在最末。
func TestStabilizeNormalTurn(t *testing.T) {
	msgs := []map[string]any{
		{"role": "system", "content": "sys"},
		{"role": "user", "content": "Today's date is 2026-11-15"},
		{"role": "user", "content": "问题一"},
		{"role": "assistant", "content": "答一"},
		{"role": "user", "content": "问题二"},
	}
	out, moved, err := StabilizePromptPrefix(mustBody(t, msgs))
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if moved != 1 {
		t.Fatalf("moved=%d", moved)
	}
	roles := rolesOf(t, out)
	if roles[len(roles)-1] != "user" {
		t.Fatalf("最末应是提问: %v", roles)
	}
}

// 内容一字不改：< > & 不能被转成 \u003c，大整数不能变成浮点。
func TestStabilizeKeepsBytesFaithful(t *testing.T) {
	raw := []byte("{\"model\":\"m\",\"seed\":1234567890123456789,\"messages\":[{\"role\":\"system\",\"content\":\"sys\"},{\"role\":\"user\",\"content\":\"# Environment update <tag> & x\"},{\"role\":\"user\",\"content\":\"q\"}]}")
	out, moved, err := StabilizePromptPrefix(raw)
	if err != nil || moved != 1 {
		t.Fatalf("moved=%d err=%v", moved, err)
	}
	if !strings.Contains(string(out), "<tag> & x") {
		t.Fatalf("HTML 被转义: %s", out)
	}
	if !strings.Contains(string(out), "1234567890123456789") {
		t.Fatalf("大整数精度丢了: %s", out)
	}
}

func mustBody(t *testing.T, msgs []map[string]any) []byte {
	t.Helper()
	b, err := json.Marshal(map[string]any{"model": "m", "stream": true, "messages": msgs})
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func rolesOf(t *testing.T, body []byte) []string {
	t.Helper()
	var raw struct {
		Messages []struct {
			Role string `json:"role"`
		} `json:"messages"`
	}
	if err := json.Unmarshal(body, &raw); err != nil {
		t.Fatal(err)
	}
	out := make([]string, 0, len(raw.Messages))
	for _, m := range raw.Messages {
		out = append(out, m.Role)
	}
	return out
}
