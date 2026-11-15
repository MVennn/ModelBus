package router

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strings"
)

// toolCallInfo 记录一次工具调用的名字与关键参数，折叠时用来写回可读的占位符。
type toolCallInfo struct {
	Name string
	Path string
}

// FoldOldToolOutputs 把较早轮次的工具输出折叠成一行占位符，最近 keepTurns 轮保持完整。
//
// 动机：单轮请求体 p50 331 KB 里工具输出占 44–84%（代码审查类会话实测），但一次工具
// 输出只在被读的那一轮有用，之后每一轮都要重发。保留最近 3 轮、更早的压到 200 字节，
// 8 个最大会话实测窗口平均降 28.1%（min 5.3%，max 43.8%）。
//
// 只改 role=="tool" 消息的 content，其余字段不动；没有可折叠项或解析失败时原样返回。
// 占位符带上工具名与文件路径，模型据此知道「这里原本是什么、需要时重读」。
func FoldOldToolOutputs(body []byte, keepTurns, keepBytes int) ([]byte, int, error) {
	if keepTurns < 0 {
		keepTurns = 0
	}
	if keepBytes < 0 {
		keepBytes = 0
	}
	dec := json.NewDecoder(bytes.NewReader(body))
	dec.UseNumber()
	var raw map[string]any
	if err := dec.Decode(&raw); err != nil {
		return body, 0, err
	}
	msgsAny, ok := raw["messages"].([]any)
	if !ok || len(msgsAny) == 0 {
		return body, 0, nil
	}
	msgs := make([]map[string]any, 0, len(msgsAny))
	for _, m := range msgsAny {
		mm, ok := m.(map[string]any)
		if !ok {
			return body, 0, fmt.Errorf("message is not an object")
		}
		msgs = append(msgs, mm)
	}

	// 1) tool_call_id -> 调用信息，供折叠时还原「哪个工具、读了哪个文件」
	infos := map[string]toolCallInfo{}
	for _, m := range msgs {
		calls, ok := m["tool_calls"].([]any)
		if !ok {
			continue
		}
		for _, c := range calls {
			cm, ok := c.(map[string]any)
			if !ok {
				continue
			}
			id, _ := cm["id"].(string)
			fn, _ := cm["function"].(map[string]any)
			if id == "" || fn == nil {
				continue
			}
			name, _ := fn["name"].(string)
			args, _ := fn["arguments"].(string)
			info := toolCallInfo{Name: name}
			if args != "" {
				var a map[string]any
				if json.Unmarshal([]byte(args), &a) == nil {
					if p, ok := a["file_path"].(string); ok {
						info.Path = p
					}
				}
			}
			infos[id] = info
		}
	}

	// 2) 最近 keepTurns 轮 user 消息的起点，之前的一律折叠
	userIdx := []int{}
	for i, m := range msgs {
		if r, _ := m["role"].(string); r == "user" {
			userIdx = append(userIdx, i)
		}
	}
	cut := 0
	if len(userIdx) > keepTurns {
		cut = userIdx[len(userIdx)-keepTurns]
	}

	// 3) 折叠
	moved := 0
	for i := 0; i < cut; i++ {
		m := msgs[i]
		if r, _ := m["role"].(string); r != "tool" {
			continue
		}
		content, ok := m["content"].(string)
		if !ok || len(content) <= keepBytes {
			continue
		}
		id, _ := m["tool_call_id"].(string)
		info := infos[id]
		label := info.Name
		if label == "" {
			label = "tool"
		}
		if info.Path != "" {
			label += " " + shortToolPath(info.Path)
		}
		m["content"] = fmt.Sprintf("[已折叠: %s, 原 %d 字节]", label, len(content))
		moved++
	}
	if moved == 0 {
		return body, 0, nil
	}
	out, err := marshalNoEscape(raw)
	if err != nil {
		return body, 0, err
	}
	return out, moved, nil
}

// shortToolPath 只留文件名，路径太长时从尾部截断，避免占位符本身又变长。
func shortToolPath(p string) string {
	p = strings.ReplaceAll(p, "\\", "/")
	if i := strings.LastIndex(p, "/"); i >= 0 && len(p)-i <= 60 {
		return p[i+1:]
	}
	if len(p) > 60 {
		return "..." + p[len(p)-57:]
	}
	return p
}
