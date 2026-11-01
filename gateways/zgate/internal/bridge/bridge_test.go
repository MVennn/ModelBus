package bridge

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func decode(t *testing.T, raw any) map[string]any {
	t.Helper()
	buf, err := json.Marshal(raw)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var out map[string]any
	if err := json.Unmarshal(buf, &out); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	return out
}

func TestChatToAnthropicMovesSystemAndTools(t *testing.T) {
	body := []byte(`{
		"model":"Claude-Test",
		"max_tokens":64,
		"temperature":0.2,
		"messages":[
			{"role":"system","content":"be terse"},
			{"role":"user","content":"hi"},
			{"role":"assistant","content":"", "tool_calls":[{"id":"c1","type":"function","function":{"name":"f","arguments":"{\"a\":1}"}}]},
			{"role":"tool","tool_call_id":"c1","content":"42"}
		],
		"tools":[{"type":"function","function":{"name":"f","description":"d","parameters":{"type":"object"}}}],
		"tool_choice":"auto"
	}`)
	payload := decode(t, chatToAnthropic(body, "claude-upstream", false))
	if payload["model"] != "claude-upstream" {
		t.Fatalf("model not rewritten: %v", payload["model"])
	}
	if payload["stream"] != false {
		t.Fatalf("bridge must call upstream non-streaming")
	}
	if payload["system"] != "be terse" {
		t.Fatalf("system not extracted: %v", payload["system"])
	}
	msgs := payload["messages"].([]any)
	if len(msgs) != 3 {
		t.Fatalf("want 3 messages, got %d", len(msgs))
	}
	assistant := msgs[1].(map[string]any)
	blocks := assistant["content"].([]any)
	if blocks[0].(map[string]any)["type"] != "tool_use" {
		t.Fatalf("tool_use block missing: %v", blocks)
	}
	toolResult := msgs[2].(map[string]any)
	resultBlock := toolResult["content"].([]any)[0].(map[string]any)
	if resultBlock["tool_use_id"] != "c1" || resultBlock["content"] != "42" {
		t.Fatalf("tool_result malformed: %v", resultBlock)
	}
	tools := payload["tools"].([]any)
	if tools[0].(map[string]any)["name"] != "f" {
		t.Fatalf("tool schema malformed: %v", tools)
	}
	if payload["tool_choice"].(map[string]any)["type"] != "auto" {
		t.Fatalf("tool_choice malformed: %v", payload["tool_choice"])
	}
}

func TestAnthropicToChatKeepsReasoningAndTools(t *testing.T) {
	data := map[string]any{
		"content": []any{
			map[string]any{"type": "thinking", "thinking": "hmm"},
			map[string]any{"type": "text", "text": "ok"},
			map[string]any{"type": "tool_use", "id": "tu1", "name": "f", "input": map[string]any{"a": float64(1)}},
		},
		"stop_reason": "tool_use",
		"usage":       map[string]any{"input_tokens": float64(3), "output_tokens": float64(4)},
	}
	chat := anthropicToChat(data, "display-name")
	if chat["model"] != "display-name" {
		t.Fatalf("display model must be echoed back, got %v", chat["model"])
	}
	choice := chat["choices"].([]any)[0].(map[string]any)
	if choice["finish_reason"] != "tool_calls" {
		t.Fatalf("finish reason: %v", choice["finish_reason"])
	}
	msg := choice["message"].(map[string]any)
	if msg["content"] != "ok" || msg["reasoning_content"] != "hmm" {
		t.Fatalf("text/reasoning wrong: %v", msg)
	}
	calls := msg["tool_calls"].([]any)
	fn := calls[0].(map[string]any)["function"].(map[string]any)
	if fn["arguments"] != `{"a":1}` {
		t.Fatalf("tool arguments not re-encoded: %v", fn["arguments"])
	}
	usage := chat["usage"].(map[string]any)
	if usage["total_tokens"] != 7 {
		t.Fatalf("usage sum wrong: %v", usage)
	}
}

func TestChatToResponses(t *testing.T) {
	body := []byte(`{
		"max_completion_tokens":32,
		"messages":[
			{"role":"system","content":"sys"},
			{"role":"user","content":"hi"},
			{"role":"assistant","content":"yo"},
			{"role":"tool","tool_call_id":"c9","content":"out"}
		],
		"tools":[{"type":"function","function":{"name":"g","parameters":{"type":"object"}}}]
	}`)
	payload := decode(t, chatToResponses(body, "resp-upstream", false))
	if payload["instructions"] != "sys" || payload["max_output_tokens"] != float64(32) {
		t.Fatalf("responses payload wrong: %v", payload)
	}
	input := payload["input"].([]any)
	last := input[len(input)-1].(map[string]any)
	if last["type"] != "function_call_output" || last["call_id"] != "c9" {
		t.Fatalf("function_call_output wrong: %v", last)
	}
}

func TestResponsesToChat(t *testing.T) {
	data := map[string]any{
		"status": "incomplete",
		"output": []any{
			map[string]any{"type": "reasoning", "summary": []any{map[string]any{"text": "why"}}},
			map[string]any{"type": "message", "content": []any{map[string]any{"type": "output_text", "text": "hi"}}},
			map[string]any{"type": "function_call", "call_id": "fc1", "name": "f", "arguments": `{"x":2}`},
		},
	}
	chat := responsesToChat(data, "m")
	choice := chat["choices"].([]any)[0].(map[string]any)
	if choice["finish_reason"] != "tool_calls" {
		t.Fatalf("tool calls should win over incomplete: %v", choice["finish_reason"])
	}
	msg := choice["message"].(map[string]any)
	if msg["reasoning_content"] != "why" || msg["content"] != "hi" {
		t.Fatalf("content wrong: %v", msg)
	}
}

func TestSSEShape(t *testing.T) {
	chat := map[string]any{
		"id":      "chatcmpl-x",
		"object":  "chat.completion",
		"created": float64(1),
		"model":   "m",
		"choices": []any{map[string]any{
			"index":         float64(0),
			"message":       map[string]any{"role": "assistant", "content": "ok", "reasoning_content": "r"},
			"finish_reason": "stop",
		}},
	}
	sse := string(sseOf(chat))
	if !strings.HasSuffix(sse, "data: [DONE]\n\n") {
		t.Fatalf("[DONE] missing:\n%s", sse)
	}
	for _, want := range []string{`"role":"assistant"`, `"reasoning_content":"r"`, `"content":"ok"`, `"finish_reason":"stop"`} {
		if !strings.Contains(sse, want) {
			t.Fatalf("SSE missing %s:\n%s", want, sse)
		}
	}
	if strings.Contains(sse, "tool_calls") {
		t.Fatalf("unexpected tool_calls chunk")
	}
}

func TestForwardTimesOut(t *testing.T) {
	slow := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(300 * time.Millisecond)
		_, _ = w.Write([]byte(`{"content":[{"type":"text","text":"late"}]}`))
	}))
	defer slow.Close()

	start := time.Now()
	res := Forward(slow.Client(), Options{
		Protocol:      "messages",
		Base:          slow.URL,
		Key:           "k",
		Body:          []byte(`{"model":"m","messages":[{"role":"user","content":"hi"}]}`),
		UpstreamModel: "m",
		DisplayModel:  "m",
		Timeout:       50 * time.Millisecond,
	})
	if res.Status != 502 {
		t.Fatalf("want 502 on timeout, got %d %s", res.Status, res.Body)
	}
	if elapsed := time.Since(start); elapsed > 250*time.Millisecond {
		t.Fatalf("timeout did not cut the call short: %v", elapsed)
	}
	if !strings.Contains(string(res.Body), "upstream_error") {
		t.Fatalf("unexpected body: %s", res.Body)
	}
}
func TestForwardStreamAnthropicToolCall(t *testing.T) {
	// 流式路径必须把 tool_use 翻译成 chat tool_calls，并以 tool_calls 收尾。
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		fl, _ := w.(http.Flusher)
		write := func(s string) {
			w.Write([]byte(s))
			if fl != nil {
				fl.Flush()
			}
		}
		write(`event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"toolu_1","name":"read_file"}}

`)
		write(`event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\"path\":"}}

`)
		write(`event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"\"/tmp/x\"}"}}

`)
		write(`event: message_stop
data: {"type":"message_stop"}

`)
	}))
	defer up.Close()

	var chunks []string
	res := Forward(up.Client(), Options{
		Protocol:      "messages",
		Base:          up.URL,
		Key:           "k",
		Body:          []byte(`{"model":"m","messages":[{"role":"user","content":"hi"}]}`),
		UpstreamModel: "m",
		DisplayModel:  "Display-M",
		Stream:        true,
		OnChunk: func(b []byte) error {
			chunks = append(chunks, string(b))
			return nil
		},
	})
	if res.Status != 200 {
		t.Fatalf("status=%d", res.Status)
	}
	joined := strings.Join(chunks, "")
	if !strings.Contains(joined, "tool_calls") {
		t.Fatalf("tool_calls missing from stream: %q", joined)
	}
	if !strings.Contains(joined, "read_file") {
		t.Fatalf("tool name missing: %q", joined)
	}
	if !strings.Contains(joined, `"finish_reason":"tool_calls"`) {
		t.Fatalf("finish_reason should be tool_calls: %q", joined)
	}
}
func TestForwardStreamIdleTimeout(t *testing.T) {
	// 上游接受连接后一个字节都不发（七牛 Conatus 的实测行为）：
	// 必须按 idle 上限返回 504，而不是干等 DefaultTimeout，也不许提前写 SSE 头。
	up := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		if fl, ok := w.(http.Flusher); ok {
			fl.Flush()
		}
		time.Sleep(1 * time.Second)
	}))
	defer up.Close()

	wrote := false
	start := time.Now()
	res := Forward(up.Client(), Options{
		Protocol:      "messages",
		Base:          up.URL,
		Key:           "k",
		Body:          []byte(`{"model":"m","messages":[{"role":"user","content":"hi"}]}`),
		UpstreamModel: "m",
		DisplayModel:  "Display-M",
		Stream:        true,
		Idle:          200 * time.Millisecond,
		OnChunk: func(b []byte) error {
			wrote = true
			return nil
		},
	})
	elapsed := time.Since(start)
	if res.Status != 504 {
		t.Fatalf("want 504 on silent upstream, got %d %s", res.Status, res.Body)
	}
	if wrote {
		t.Fatalf("must not write any chunk when nothing was produced")
	}
	if elapsed > 2*time.Second {
		t.Fatalf("idle watchdog did not fire early: %v", elapsed)
	}
	if !strings.Contains(string(res.Body), "upstream_timeout") {
		t.Fatalf("unexpected body: %s", res.Body)
	}
}

func TestIdleReaderTripsOnSilence(t *testing.T) {
	// 上游一个字节都不发：idle 窗口一到必须关流返回读错误（504 的来源）。
	pr, pw := io.Pipe()
	ir := newIdleReader(pr, 100*time.Millisecond)
	defer ir.stop()
	defer pw.Close()

	buf := make([]byte, 16)
	start := time.Now()
	_, err := ir.Read(buf)
	if err == nil {
		t.Fatal("silent stream must error once the idle watchdog fires")
	}
	if !ir.timedOut() {
		t.Fatal("expected tripped after a full idle window of silence")
	}
	if elapsed := time.Since(start); elapsed > 2*time.Second {
		t.Fatalf("watchdog fired late: %v", elapsed)
	}
}

func TestIdleReaderFlowingDataStaysAlive(t *testing.T) {
	// 字节持续到达（间隔 < idle）：窗口不断重排，绝不判超时。
	pr, pw := io.Pipe()
	ir := newIdleReader(pr, 200*time.Millisecond)
	defer ir.stop()
	defer pr.Close()

	stop := make(chan struct{})
	go func() {
		tick := time.NewTicker(50 * time.Millisecond)
		defer tick.Stop()
		for {
			select {
			case <-tick.C:
				if _, err := pw.Write([]byte("x")); err != nil {
					return
				}
			case <-stop:
				return
			}
		}
	}()

	buf := make([]byte, 16)
	for i := 0; i < 8; i++ { // 8 × 50ms ≈ 400ms > 2× 窗口
		if _, err := ir.Read(buf); err != nil {
			t.Fatalf("read %d failed: %v (tripped=%v)", i, err, ir.timedOut())
		}
	}
	if ir.timedOut() {
		t.Fatal("flowing data must not trip the watchdog")
	}
	close(stop)
	_ = pw.Close()
}

func TestIdleReaderBoundaryByteIsNotKilled(t *testing.T) {
	// 竞态修复的核心用例：字节在 idle 窗口边缘到达（Reset 与看门狗触发在
	// 同一线竞争交错）。旧实现无条件判超时并关流 —— 还在传输的流被误判成
	// 504 静默，链路白付一次 5min 冷却。新口径按「距上一个字节是否空满
	// idle」判定：窗口边缘的字节不算超时，看门狗按剩余窗口重排，流继续。
	const idle = 400 * time.Millisecond
	pr, pw := io.Pipe()
	ir := newIdleReader(pr, idle)
	defer ir.stop()
	defer pw.Close()

	go func() {
		time.Sleep(idle * 3 / 4) // 0.75×idle：窗口边缘
		_, _ = pw.Write([]byte("a"))
		time.Sleep(idle * 3 / 10) // 1.05×idle：已越过旧实现的开刀点
		_, _ = pw.Write([]byte("b"))
	}()

	buf := make([]byte, 8)
	if _, err := ir.Read(buf); err != nil {
		t.Fatalf("boundary byte must survive: %v", err)
	}
	// 旧实现在 1.0×idle 已把连接关掉，这个字节只会读到错误。
	if _, err := ir.Read(buf); err != nil {
		t.Fatalf("stream was killed at the old deadline despite a boundary byte: %v", err)
	}
	// 此后彻底沉默：再空满一个窗口必须判超时（连接由看门狗关闭）。
	start := time.Now()
	if _, err := ir.Read(buf); err == nil {
		t.Fatal("continued silence must eventually trip the watchdog")
	}
	if !ir.timedOut() {
		t.Fatal("expected tripped after a full idle window of silence")
	}
	if elapsed := time.Since(start); elapsed > 2*idle {
		t.Fatalf("watchdog fired late: %v", elapsed)
	}
}
