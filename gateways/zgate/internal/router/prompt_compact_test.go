package router

import (
	"encoding/json"
	"strings"
	"testing"
)

func foldBody() []byte {
	return []byte(`{"model":"m","messages":[
		{"role":"user","content":"第一轮"},
		{"role":"assistant","content":"","tool_calls":[{"id":"c1","type":"function","function":{"name":"Read","arguments":"{\"file_path\":\"F:/a/big.go\"}"}}]},
		{"role":"tool","tool_call_id":"c1","content":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
		{"role":"assistant","content":"读完了"},
		{"role":"user","content":"第二轮"},
		{"role":"assistant","content":"","tool_calls":[{"id":"c2","type":"function","function":{"name":"Read","arguments":"{\"file_path\":\"F:/a/other.go\"}"}}]},
		{"role":"tool","tool_call_id":"c2","content":"BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"},
		{"role":"assistant","content":"也读完了"},
		{"role":"user","content":"第三轮"}
	]}`)
}

func TestFoldOldToolOutputs(t *testing.T) {
	out, moved, err := FoldOldToolOutputs(foldBody(), 2, 10)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if moved != 1 {
		t.Fatalf("moved = %d, want 1", moved)
	}
	var raw map[string]any
	if err := json.Unmarshal(out, &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	msgs := raw["messages"].([]any)
	early := msgs[2].(map[string]any)["content"].(string)
	if !strings.Contains(early, "已折叠") || !strings.Contains(early, "big.go") {
		t.Fatalf("早期输出未按预期折叠: %q", early)
	}
	late := msgs[6].(map[string]any)["content"].(string)
	if late != "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB" {
		t.Fatalf("最近一轮被误改: %q", late)
	}
}

func TestFoldOldToolOutputsKeepsShort(t *testing.T) {
	body := []byte(`{"messages":[
		{"role":"user","content":"a"},
		{"role":"tool","tool_call_id":"x","content":"short"},
		{"role":"user","content":"b"},
		{"role":"user","content":"c"}
	]}`)
	out, moved, err := FoldOldToolOutputs(body, 1, 100)
	if err != nil || moved != 0 {
		t.Fatalf("moved=%d err=%v, want 0/nil", moved, err)
	}
	if string(out) != string(body) {
		t.Fatalf("没有可折叠项时应原样返回")
	}
}

func TestFoldOldToolOutputsNoTools(t *testing.T) {
	body := []byte(`{"messages":[{"role":"user","content":"hi"}]}`)
	out, moved, err := FoldOldToolOutputs(body, 1, 10)
	if err != nil || moved != 0 || string(out) != string(body) {
		t.Fatalf("moved=%d err=%v", moved, err)
	}
}

func TestFoldOldToolOutputsBadJSON(t *testing.T) {
	body := []byte("{oops")
	out, moved, err := FoldOldToolOutputs(body, 1, 10)
	if err == nil || moved != 0 || string(out) != string(body) {
		t.Fatalf("want err and原样返回, got moved=%d err=%v", moved, err)
	}
}

func TestShortToolPath(t *testing.T) {
	if got := shortToolPath(`F:\a\b\main.go`); got != "main.go" {
		t.Fatalf("got %q", got)
	}
	long := strings.Repeat("x", 100) + "/tail.go"
	if got := shortToolPath(long); len(got) > 64 {
		t.Fatalf("too long: %d", len(got))
	}
}
