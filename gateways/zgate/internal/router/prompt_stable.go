package router

import (
	"bytes"
	"encoding/json"
	"strings"
)

// volatileInjectionMarkers 是客户端每轮重新生成的 synthetic 注入模板。
//
// 它们在消息序列里的位置固定在历史靠前处（实测 seq=15/19/21/23…），内容却随轮次
// 变化（当前时间、todo 进度、环境更新）。上游的 prefix cache 从第一个 token 起逐块
// 匹配，这条消息一变，从它往后的整段历史每轮都要重新 prefill。
//
// 实测同一段 350 KB 内容（.work/ab-prefix-position.mjs）：
// 完全不变 首字 6.68s 中位 / 变化内容放最前 19.43s / 放最后 10.18s。
var volatileInjectionMarkers = []string{
	"# Environment update",
	"The user hasn't heard from you in a while",
	"The TodoWrite tool hasn't been used recently",
	"Today's date is ",
}

func isVolatileInjection(content string) bool {
	for _, m := range volatileInjectionMarkers {
		if strings.Contains(content, m) {
			return true
		}
	}
	return false
}

// messageText 取出 message 的文本用于匹配：content 可能是字符串，也可能是
// [{type:"text",text:"..."}] 这种多模态数组。
func messageText(m map[string]any) string {
	switch c := m["content"].(type) {
	case string:
		return c
	case []any:
		var b strings.Builder
		for _, it := range c {
			if mm, ok := it.(map[string]any); ok {
				if t, ok := mm["text"].(string); ok {
					b.WriteString(t)
				}
			}
		}
		return b.String()
	}
	return ""
}

func roleOf(m any) string {
	if mm, ok := m.(map[string]any); ok {
		if r, ok := mm["role"].(string); ok {
			return r
		}
	}
	return ""
}

// movableRole 决定哪些 role 的消息允许搬移：只有 user / system。
//
// tool 消息必须紧跟在发起它的 assistant(tool_calls) 之后，assistant 消息本身承载
// tool_calls —— 搬走任何一条都会让序列非法。2026-11-15 实测后果：本会话的 Read 输出
// 里恰好带着这四个标记（读的就是这个文件），旧实现把 tool 消息搬到末尾，下一轮上游
// 直接不认工具调用，模型开始把 <|DSML|> 工具调用标记和思考文本写进正文，工具也不再
// 执行（GUI 截图：正文里整段 DSML 参数块）。
func movableRole(role string) bool { return role == "user" || role == "system" }

// insertionIndex 选注入的落点：紧贴尾部「最新一轮动作」之前，且绝不让注入成为
// 序列最后一条 —— 否则模型会把「The TodoWrite tool hasn't been used recently」这类
// 提醒当成当前诉求去回。
//
//   - 尾部是 tool 结果块（工具调用轮）：插在发起这批调用的 assistant 之前，
//     保持 assistant(tool_calls) 紧跟 tool 结果；
//   - 尾部是 assistant：插在它之前；
//   - 常规轮：插在最后一条 user 提问之前，提问仍在最末。
func insertionIndex(kept []any) int {
	i := len(kept)
	// 1) 尾部 tool 结果块
	for i > 0 && roleOf(kept[i-1]) == "tool" {
		i--
	}
	if i < len(kept) {
		if i > 0 && roleOf(kept[i-1]) == "assistant" {
			i--
		}
		return i
	}
	// 2) 尾部 assistant
	if i > 0 && roleOf(kept[i-1]) == "assistant" {
		return i - 1
	}
	// 3) 常规轮
	if i > 0 && roleOf(kept[i-1]) == "user" {
		return i - 1
	}
	return i
}

// StabilizePromptPrefix 把每轮变化的 synthetic 注入从历史原位搬到「本轮提问之前」，
// 让稳定的系统提示词与历史保持前缀一致，从而复用上游 prefix cache。
//
// 只改顺序、不动内容，也不动 role：只搬 user / system 的注入，tool 与 assistant
// 一律原地保留（见 movableRole）。落点见 insertionIndex。首条 system 是主系统提示词，
// 位置固定不参与搬移。
//
// 返回新 body 与搬移条数。解析失败或没有可搬的消息时原样返回，调用方据此走老路径。
func StabilizePromptPrefix(body []byte) ([]byte, int, error) {
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var raw map[string]any
	if err := dec.Decode(&raw); err != nil {
		return body, 0, err
	}
	msgs, ok := raw["messages"].([]any)
	if !ok || len(msgs) == 0 {
		return body, 0, nil
	}
	kept := make([]any, 0, len(msgs))
	moved := make([]any, 0, 4)
	for i, m := range msgs {
		mm, ok := m.(map[string]any)
		if !ok {
			kept = append(kept, m)
			continue
		}
		if i > 0 && movableRole(roleOf(m)) && isVolatileInjection(messageText(mm)) {
			moved = append(moved, m)
			continue
		}
		kept = append(kept, m)
	}
	if len(moved) == 0 {
		return body, 0, nil
	}
	insertAt := insertionIndex(kept)
	merged := make([]any, 0, len(kept)+len(moved))
	merged = append(merged, kept[:insertAt]...)
	merged = append(merged, moved...)
	merged = append(merged, kept[insertAt:]...)
	raw["messages"] = merged
	out, err := marshalNoEscape(raw)
	if err != nil {
		return body, 0, err
	}
	return out, len(moved), nil
}

// marshalNoEscape 保持 body 字节忠实：默认 json.Marshal 会把 < > & 转成 \u003c 之类
// （实测每次请求凭空涨 2–4 KB），数字也会被统一成 float64 而丢大整数精度。
func marshalNoEscape(v any) ([]byte, error) {
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(v); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}
