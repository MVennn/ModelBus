package router

import (
	"encoding/json"
	"testing"
)

func TestStabilizePromptPrefixMovesVolatileToTail(t *testing.T) {
	body := []byte(`{"model":"m","messages":[
		{"role":"user","content":"真实用户输入"},
		{"role":"user","content":"# Environment\nworking dir F:/x"},
		{"role":"assistant","content":"好的"},
		{"role":"user","content":"The user hasn't heard from you in a while. As you continue..."},
		{"role":"assistant","content":"继续"},
		{"role":"user","content":"# Environment update\n - Primary working directory: F:/y"},
		{"role":"user","content":"The TodoWrite tool hasn't been used recently."}
	]}`)

	out, moved, err := StabilizePromptPrefix(body)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if moved != 3 {
		t.Fatalf("moved = %d, want 3", moved)
	}
	var raw map[string]any
	if err := json.Unmarshal(out, &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	msgs := raw["messages"].([]any)
	if len(msgs) != 7 {
		t.Fatalf("len = %d, want 7", len(msgs))
	}
	want := []string{"真实用户输入", "# Environment\nworking dir F:/x", "好的"}
	for i, w := range want {
		if got := messageText(msgs[i].(map[string]any)); got != w {
			t.Fatalf("msgs[%d] = %q, want %q", i, got, w)
		}
	}
	// 尾部是 assistant 时，注入插在它之前，不能成为最后一条
	for i := 3; i <= 5; i++ {
		if !isVolatileInjection(messageText(msgs[i].(map[string]any))) {
			t.Fatalf("msgs[%d] 不是变化注入", i)
		}
	}
	if got := messageText(msgs[6].(map[string]any)); got != "继续" {
		t.Fatalf("msgs[6] = %q, want 继续", got)
	}
}

// 末尾是真实提问时，注入要插在提问之前，不能排在提问后面当最后一条用户指令。
func TestStabilizePromptPrefixInsertsBeforeFinalQuestion(t *testing.T) {
	body := []byte(`{"model":"m","messages":[
		{"role":"system","content":"你是助手"},
		{"role":"user","content":"# Environment update\n - Primary working directory: F:/y"},
		{"role":"user","content":"把上面文档总结成三点"},
		{"role":"user","content":"The TodoWrite tool hasn't been used recently."}
	]}`)

	out, moved, err := StabilizePromptPrefix(body)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if moved != 2 {
		t.Fatalf("moved = %d, want 2", moved)
	}
	var raw map[string]any
	if err := json.Unmarshal(out, &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	msgs := raw["messages"].([]any)
	if len(msgs) != 4 {
		t.Fatalf("len = %d, want 4", len(msgs))
	}
	if got := messageText(msgs[0].(map[string]any)); got != "你是助手" {
		t.Fatalf("msgs[0] = %q", got)
	}
	for i := 1; i <= 2; i++ {
		if !isVolatileInjection(messageText(msgs[i].(map[string]any))) {
			t.Fatalf("msgs[%d] 应是变化注入，实际 %q", i, messageText(msgs[i].(map[string]any)))
		}
	}
	if got := messageText(msgs[3].(map[string]any)); got != "把上面文档总结成三点" {
		t.Fatalf("最后一条应是提问，实际 %q", got)
	}
}

func TestStabilizePromptPrefixNoVolatile(t *testing.T) {
	body := []byte(`{"messages":[{"role":"user","content":"只有稳定内容"}]}`)
	out, moved, err := StabilizePromptPrefix(body)
	if err != nil || moved != 0 {
		t.Fatalf("moved=%d err=%v, want 0/nil", moved, err)
	}
	if string(out) != string(body) {
		t.Fatalf("body 被改动")
	}
}

func TestStabilizePromptPrefixMultimodalContent(t *testing.T) {
	body := []byte(`{"messages":[
		{"role":"user","content":[{"type":"text","text":"稳定"}]},
		{"role":"user","content":[{"type":"text","text":"Today's date is 2026-11-14."}]}
	]}`)
	_, moved, err := StabilizePromptPrefix(body)
	if err != nil || moved != 1 {
		t.Fatalf("moved=%d err=%v, want 1/nil", moved, err)
	}
}

func TestStabilizePromptPrefixBadJSON(t *testing.T) {
	body := []byte("{not json")
	out, moved, err := StabilizePromptPrefix(body)
	if err == nil || moved != 0 {
		t.Fatalf("want err, got moved=%d err=%v", moved, err)
	}
	if string(out) != string(body) {
		t.Fatalf("解析失败应原样返回")
	}
}
