package router

import (
	"encoding/json"
	"strings"
	"testing"
)

// 本文件只测 bodyfacts.go 的对外行为：顶层事实提取、字节级改写、字段追加，
// 以及它与 encoding/json 的语义一致性。改写类断言一律按字节比对 —— 这套代码
// 存在的理由就是「除目标片段外一个字节都不动」。

// objectOf 用标准库解析同一份 body，作为手写扫描的对照基准。
func objectOf(t *testing.T, body string) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal([]byte(body), &m); err != nil {
		t.Fatalf("fixture is not valid JSON: %v\n%s", err, body)
	}
	return m
}

func TestBodyFactsTopLevelFields(t *testing.T) {
	body := `{"model":"W/0.03/DeepSeek-41-Fs","stream":true,"reasoning_effort":"high","thinking":{"type":"enabled"},"tools":[{"type":"function","function":{"name":"read"}}]}`
	f := parseBodyFacts([]byte(body))
	if !f.ok {
		t.Fatalf("valid object reported as not ok: %+v", f)
	}
	if f.keys != 5 {
		t.Fatalf("keys=%d, want 5", f.keys)
	}
	if f.closeAt != len(body)-1 || body[f.closeAt] != '}' {
		t.Fatalf("closeAt=%d (len=%d), want the final '}'", f.closeAt, len(body))
	}
	if !f.hasModel || !f.modelStr || f.model != "W/0.03/DeepSeek-41-Fs" {
		t.Fatalf("model not extracted: has=%v str=%v val=%q", f.hasModel, f.modelStr, f.model)
	}
	if !f.stream {
		t.Fatalf("stream=true not detected")
	}
	if !f.hasEffort || !f.effortStr || f.effort != "high" {
		t.Fatalf("reasoning_effort not extracted: has=%v str=%v val=%q", f.hasEffort, f.effortStr, f.effort)
	}
	if !f.hasThink || f.thinkType != "enabled" {
		t.Fatalf("thinking.type not extracted: has=%v type=%q", f.hasThink, f.thinkType)
	}
	if !f.hasTools {
		t.Fatalf("tools presence not recorded")
	}
	if !f.expectsThinking() {
		t.Fatalf("reasoning_effort=high must count as expecting thinking")
	}

	// 与标准库对照：手写扫描不能比 encoding/json 多认或少认。
	ref := objectOf(t, body)
	if got := ref["model"].(string); got != f.model {
		t.Fatalf("model mismatch vs encoding/json: %q != %q", f.model, got)
	}
	if got := ref["reasoning_effort"].(string); got != f.effort {
		t.Fatalf("reasoning_effort mismatch vs encoding/json: %q != %q", f.effort, got)
	}
	if got := ref["thinking"].(map[string]any)["type"].(string); got != f.thinkType {
		t.Fatalf("thinking.type mismatch vs encoding/json: %q != %q", f.thinkType, got)
	}
}

func TestBodyFactsToolsPresenceWithoutPayload(t *testing.T) {
	// tools 只记「有没有」，空数组也算给了 tools。
	for _, body := range []string{`{"tools":[]}`, `{"tools":null}`, `{"tools":{}}`} {
		f := parseBodyFacts([]byte(body))
		if !f.ok || !f.hasTools {
			t.Fatalf("hasTools=%v ok=%v for %s", f.hasTools, f.ok, body)
		}
		if f.hasModel {
			t.Fatalf("model must stay absent for %s", body)
		}
	}
}

func TestBodyFactsEscapedStringsInModel(t *testing.T) {
	cases := []struct {
		name string
		body string
		want string
	}{
		{"escaped-quote", `{"model":"a\"b","stream":true,"reasoning_effort":"high"}`, `a"b`},
		{"trailing-backslash", `{"model":"a\\","stream":true}`, `a\`},
		{"unicode-escape", `{"model":"m\u00e9","stream":true}`, "mé"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := parseBodyFacts([]byte(c.body))
			if !f.ok || !f.modelStr {
				t.Fatalf("model not read as string: ok=%v str=%v", f.ok, f.modelStr)
			}
			if f.model != c.want {
				t.Fatalf("model=%q, want %q", f.model, c.want)
			}
			// 转义不能把扫描带偏：收尾 '}' 仍是最后一个字节，后面的字段也都还在。
			if f.closeAt != len(c.body)-1 {
				t.Fatalf("closeAt=%d (len=%d): escape handling lost the object end", f.closeAt, len(c.body))
			}
			if !f.stream {
				t.Fatalf("field after the escaped model value was not scanned")
			}
			if c.name == "escaped-quote" && (!f.hasEffort || f.effort != "high") {
				t.Fatalf("reasoning_effort after escaped model value: has=%v val=%q", f.hasEffort, f.effort)
			}
		})
	}
}

func TestBodyFactsIgnoresNestedModelKey(t *testing.T) {
	body := `{"metadata":{"model":"nested"},"messages":[{"role":"user","content":"{\"model\":\"inner\"}"}],"stream":false}`
	f := parseBodyFacts([]byte(body))
	if !f.ok {
		t.Fatalf("valid object reported as not ok")
	}
	if f.hasModel || f.model != "" {
		t.Fatalf("nested model key leaked into top-level facts: has=%v val=%q", f.hasModel, f.model)
	}
	if f.stream {
		t.Fatalf("stream=false misread as true")
	}
	if f.hasTools {
		t.Fatalf("no top-level tools key, yet hasTools is set")
	}
	if _, ok := f.withModel([]byte(body), "upstream/x"); ok {
		t.Fatalf("withModel must refuse when the top level carries no model key")
	}
	if f.hasThink {
		t.Fatalf("no top-level thinking key, yet hasThink is set")
	}
}

func TestBodyFactsRejectsNonObjectAndBrokenJSON(t *testing.T) {
	cases := []struct {
		name string
		body string
	}{
		{"empty", ""},
		{"whitespace-only", " \n\t\r "},
		{"plain-text", "not json at all"},
		{"missing-close-brace", `{"model":"m"`},
		{"missing-value", `{"model":}`},
		{"key-without-colon", `{"model"}`},
		{"top-level-array", `[{"model":"m"}]`},
		{"top-level-null", `null`},
		{"unterminated-string", `{"model":"m}`},
		{"bare-open-brace", `{`},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			// 「不 panic」由测试本身兜住：真 panic 会让整个测试失败。
			f := parseBodyFacts([]byte(c.body))
			if f.ok {
				t.Fatalf("broken body accepted: %+v", f)
			}
			if f.hasModel || f.hasEffort || f.hasThink || f.hasTools || f.stream {
				t.Fatalf("zero-value facts expected, got %+v", f)
			}
			if _, ok := f.withModel([]byte(c.body), "upstream/x"); ok {
				t.Fatalf("withModel accepted a broken body")
			}
			if _, ok := f.withStringField([]byte(c.body), "reasoning_effort", "high"); ok {
				t.Fatalf("withStringField accepted a broken body")
			}
			if f.expectsThinking() {
				t.Fatalf("broken body must not expect thinking")
			}
		})
	}

	if f := parseBodyFacts(nil); f.ok {
		t.Fatalf("nil body accepted: %+v", f)
	}
}

func TestWithModelKeepsEveryOtherByte(t *testing.T) {
	const prompt = "<b>a & b</b> if x < 1 && y > 2"
	body := `{"messages":[{"role":"user","content":"` + prompt + `"}],"model":"alias/x","stream":true,"reasoning_effort":"low","tools":[{"type":"function"}]}`
	out, ok := parseBodyFacts([]byte(body)).withModel([]byte(body), "global:deepseek-v4.1-flash-sg")
	if !ok {
		t.Fatalf("withModel refused a body with a top-level model")
	}
	want := strings.Replace(body, `"alias/x"`, `"global:deepseek-v4.1-flash-sg"`, 1)
	if string(out) != want {
		t.Fatalf("rewrite touched bytes outside the model value:\n got %s\nwant %s", out, want)
	}
	if !json.Valid(out) {
		t.Fatalf("rewritten body is not valid JSON: %s", out)
	}
	for _, esc := range []string{`\u003c`, `\u003e`, `\u0026`} {
		if strings.Contains(string(out), esc) {
			t.Fatalf("HTML escaping %s leaked into the forwarded body: %s", esc, out)
		}
	}
	if !strings.Contains(string(out), prompt) {
		t.Fatalf("prompt bytes changed: %s", out)
	}

	var got map[string]any
	if err := json.Unmarshal(out, &got); err != nil {
		t.Fatalf("rewritten body does not decode: %v", err)
	}
	if got["model"] != "global:deepseek-v4.1-flash-sg" {
		t.Fatalf("model=%v", got["model"])
	}
	if got["stream"] != true || got["reasoning_effort"] != "low" {
		t.Fatalf("sibling fields changed: %v", got)
	}
	msgs, ok := got["messages"].([]any)
	if !ok || len(msgs) != 1 {
		t.Fatalf("messages=%v", got["messages"])
	}
	if content := msgs[0].(map[string]any)["content"]; content != prompt {
		t.Fatalf("prompt content=%q, want %q", content, prompt)
	}
}

func TestWithModelEscapesUpstreamValue(t *testing.T) {
	body := `{"model":"alias/x","stream":true,"prompt":"<tag>&"}`
	for _, upstream := range []string{`we"ird\path`, "<x>&y", "名字/带中文", "up\nstream"} {
		out, ok := parseBodyFacts([]byte(body)).withModel([]byte(body), upstream)
		if !ok {
			t.Fatalf("withModel refused upstream %q", upstream)
		}
		if !json.Valid(out) {
			t.Fatalf("upstream %q produced invalid JSON: %s", upstream, out)
		}
		var got map[string]any
		if err := json.Unmarshal(out, &got); err != nil {
			t.Fatalf("upstream %q produced undecodable JSON: %v (%s)", upstream, err, out)
		}
		if got["model"] != upstream {
			t.Fatalf("model round-trip: %q != %q", got["model"], upstream)
		}
		if got["prompt"] != "<tag>&" {
			t.Fatalf("prompt bytes changed while rewriting model: %v", got["prompt"])
		}
	}
}

func TestWithStringFieldAppendsInsideObject(t *testing.T) {
	cases := []struct {
		name string
		body string
		want string
	}{
		{
			"existing-keys",
			`{"model":"m","messages":[]}`,
			`{"model":"m","messages":[],"reasoning_effort":"high"}`,
		},
		{
			"empty-object",
			`{}`,
			`{"reasoning_effort":"high"}`,
		},
		{
			"trailing-space",
			`{ "model":"m" }`,
			`{ "model":"m" ,"reasoning_effort":"high"}`,
		},
		{
			"brace-inside-string",
			`{"model":"m","prompt":"a}b{c"}`,
			`{"model":"m","prompt":"a}b{c","reasoning_effort":"high"}`,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := parseBodyFacts([]byte(c.body))
			if !f.ok {
				t.Fatalf("fixture reported as not ok: %s", c.body)
			}
			out, ok := f.withStringField([]byte(c.body), "reasoning_effort", "high")
			if !ok {
				t.Fatalf("withStringField refused %s", c.body)
			}
			if string(out) != c.want {
				t.Fatalf("append layout wrong:\n got %s\nwant %s", out, c.want)
			}
			if !json.Valid(out) {
				t.Fatalf("appended body is not valid JSON: %s", out)
			}
			var got map[string]any
			if err := json.Unmarshal(out, &got); err != nil {
				t.Fatalf("appended body does not decode: %v", err)
			}
			if got["reasoning_effort"] != "high" {
				t.Fatalf("reasoning_effort=%v", got["reasoning_effort"])
			}
			// 追加后重新扫描：档位被认出来，且算「期待思考」。
			again := parseBodyFacts(out)
			if !again.hasEffort || again.effort != "high" {
				t.Fatalf("re-scan lost the injected field: %+v", again)
			}
			if !again.expectsThinking() {
				t.Fatalf("reasoning_effort=high must count as expecting thinking")
			}
			// 原有字段不能被顶掉。
			if c.name != "empty-object" && again.model != "m" {
				t.Fatalf("model changed by the append: %q", again.model)
			}
		})
	}
}

func TestEqualFoldASCII(t *testing.T) {
	cases := []struct {
		s, want string
		ok      bool
	}{
		{"off", "off", true},
		{"OFF", "off", true},
		{"Off", "off", true},
		{"enabled", "enabled", true},
		{"ENABLED", "enabled", true},
		{"on", "off", false},
		{"of", "off", false},
		{"offf", "off", false},
		{"", "", true},
		{"", "off", false},
		{"0ff", "off", false},
		{"of f", "off", false},
	}
	for _, c := range cases {
		if got := equalFoldASCII(c.s, c.want); got != c.ok {
			t.Fatalf("equalFoldASCII(%q, %q)=%v, want %v", c.s, c.want, got, c.ok)
		}
	}
}

func TestExpectsThinkingBoundaries(t *testing.T) {
	cases := []struct {
		name string
		body string
		want bool
	}{
		{"no-signal", `{"model":"m"}`, false},
		{"empty-object", `{}`, false},
		{"effort-high", `{"reasoning_effort":"high"}`, true},
		{"effort-medium", `{"reasoning_effort":"medium"}`, true},
		{"effort-off", `{"reasoning_effort":"off"}`, false},
		{"effort-OFF-uppercase", `{"reasoning_effort":"OFF"}`, false},
		{"effort-empty", `{"reasoning_effort":""}`, false},
		{"effort-not-a-string", `{"reasoning_effort":3}`, false},
		{"thinking-enabled", `{"thinking":{"type":"enabled"}}`, true},
		{"thinking-Enabled-mixed-case", `{"thinking":{"type":"Enabled"}}`, true},
		{"thinking-disabled", `{"thinking":{"type":"disabled"}}`, false},
		{"thinking-not-an-object", `{"thinking":true}`, false},
		{"broken-body", `{"reasoning_effort":"high"`, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := parseBodyFacts([]byte(c.body)).expectsThinking(); got != c.want {
				t.Fatalf("expectsThinking(%s)=%v, want %v", c.body, got, c.want)
			}
			// 旧签名走同一条路径，两个入口必须给同一个答案。
			if got := reasoningExpectsThinking([]byte(c.body)); got != c.want {
				t.Fatalf("reasoningExpectsThinking(%s)=%v, want %v", c.body, got, c.want)
			}
		})
	}
}

func TestBodyFactsStreamIsStrictlyBoolean(t *testing.T) {
	// 旧实现把 stream 解进 bool，非布尔值会让整段 Unmarshal 失败、返回 false；
	// 手写扫描按字节比 "true"，行为保持一致。
	cases := []struct {
		body string
		want bool
	}{
		{`{"stream":true}`, true},
		{`{"stream":false}`, false},
		{`{"stream":"true"}`, false},
		{`{"stream":1}`, false},
		{`{"model":"m"}`, false},
	}
	for _, c := range cases {
		f := parseBodyFacts([]byte(c.body))
		if !f.ok {
			t.Fatalf("fixture reported as not ok: %s", c.body)
		}
		if f.stream != c.want {
			t.Fatalf("stream(%s)=%v, want %v", c.body, f.stream, c.want)
		}
	}
}
