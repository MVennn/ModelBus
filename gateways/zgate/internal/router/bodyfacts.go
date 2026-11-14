package router

import (
	"bytes"
	"encoding/json"
)

// bodyFacts 是一次线性扫描得到的请求体事实。
//
// 为什么要它：同一份 body 在热路径上原本要被反序列化六遍 ——
// wantsStream / requestModel / reasoningGuardMatches / reasoningExpectsThinking /
// injectThinkingEffort / rewriteModel 各自 json.Unmarshal 一次，其中 rewriteModel
// 和 injectThinkingEffort 还要 map[string]any 往返再 Marshal。一份 200 KB 的
// 系统提示进来，这条路上会造出几十万个临时节点，GC 压力全落在转发首字之前。
//
// 这里改成手写扫描：只认顶层键，字符串与嵌套结构只数括号不建对象，除了
// model / reasoning_effort 两个短字符串外零分配，顺带记下「model 值在哪」和
// 「顶层 '}' 在哪」，于是改写模型名与插入字段都退化成一次字节拼接。
type bodyFacts struct {
	ok      bool // 顶层是合法 JSON 对象
	keys    int  // 顶层键数量（插入新字段时决定要不要前导逗号）
	closeAt int  // 顶层 '}' 的下标（插入新字段的位置）

	hasModel bool
	modelStr bool
	model    string
	modelAt  int // model 值（含引号）在 body 里的起止
	modelEnd int

	stream bool

	hasEffort bool
	effortStr bool
	effort    string

	hasThink  bool
	thinkType string

	hasTools bool
}

// span 是顶层一个键值对在 body 里的位置。
type span struct {
	keyAt, keyEnd int
	valAt, valEnd int
}

func skipWS(b []byte, i int) int {
	for i < len(b) {
		switch b[i] {
		case ' ', '\t', '\n', '\r':
			i++
		default:
			return i
		}
	}
	return i
}

// scanString 从 b[i] == '"' 开始扫到收尾引号之后。转义按两字节跳，不校验合法性。
func scanString(b []byte, i int) (int, bool) {
	i++
	for i < len(b) {
		switch b[i] {
		case '\\':
			i += 2
		case '"':
			return i + 1, true
		default:
			i++
		}
	}
	return i, false
}

// skipValue 返回一个 JSON 值的结束下标（不含）。对象与数组只数括号，
// 字符串走 scanString，其余（数字 / true / false / null）扫到分隔符。
func skipValue(b []byte, i int) (int, bool) {
	if i >= len(b) {
		return i, false
	}
	switch b[i] {
	case '"':
		return scanString(b, i)
	case '{', '[':
		depth := 0
		for i < len(b) {
			switch b[i] {
			case '"':
				end, ok := scanString(b, i)
				if !ok {
					return i, false
				}
				i = end
				continue
			case '{', '[':
				depth++
			case '}', ']':
				depth--
				if depth == 0 {
					return i + 1, true
				}
			}
			i++
		}
		return i, false
	default:
		start := i
		for i < len(b) {
			switch b[i] {
			case ',', '}', ']', ' ', '\t', '\n', '\r':
				if i == start {
					return i, false
				}
				return i, true
			}
			i++
		}
		if i == start {
			return i, false
		}
		return i, true
	}
}

// topLevel 扫出顶层对象的所有键值 span，以及收尾 '}' 的下标。
func topLevel(b []byte) ([]span, int, bool) {
	i := skipWS(b, 0)
	if i >= len(b) || b[i] != '{' {
		return nil, 0, false
	}
	i++
	var spans []span
	for {
		i = skipWS(b, i)
		if i >= len(b) {
			return nil, 0, false
		}
		switch b[i] {
		case '}':
			return spans, i, true
		case ',':
			i++
			continue
		case '"':
		default:
			return nil, 0, false
		}
		keyStart := i
		keyEnd, ok := scanString(b, i)
		if !ok {
			return nil, 0, false
		}
		i = skipWS(b, keyEnd)
		if i >= len(b) || b[i] != ':' {
			return nil, 0, false
		}
		i = skipWS(b, i+1)
		valStart := i
		valEnd, ok := skipValue(b, i)
		if !ok {
			return nil, 0, false
		}
		spans = append(spans, span{keyAt: keyStart, keyEnd: keyEnd, valAt: valStart, valEnd: valEnd})
		i = valEnd
	}
}

// objectString 在 obj（一个对象字面量）里找 key 的字符串值，找不到返回空串。
func objectString(obj []byte, key string) string {
	spans, _, ok := topLevel(obj)
	if !ok {
		return ""
	}
	for _, sp := range spans {
		if bytes.Equal(obj[sp.keyAt+1:sp.keyEnd-1], []byte(key)) {
			v := obj[sp.valAt:sp.valEnd]
			if len(v) > 0 && v[0] == '"' {
				var s string
				if json.Unmarshal(v, &s) == nil {
					return s
				}
			}
			return ""
		}
	}
	return ""
}

// parseBodyFacts 扫一遍 body。空 body / 非对象一律返回零值（ok=false），
// 调用方据此回落到老行为（不注入、不改写、当非流式处理）。
func parseBodyFacts(body []byte) bodyFacts {
	if len(body) == 0 {
		return bodyFacts{}
	}
	spans, closeAt, ok := topLevel(body)
	if !ok {
		return bodyFacts{}
	}
	f := bodyFacts{ok: true, keys: len(spans), closeAt: closeAt}
	for _, sp := range spans {
		key := body[sp.keyAt+1 : sp.keyEnd-1]
		val := body[sp.valAt:sp.valEnd]
		switch {
		case bytes.Equal(key, []byte("model")):
			f.hasModel = true
			f.modelAt, f.modelEnd = sp.valAt, sp.valEnd
			if len(val) > 0 && val[0] == '"' {
				var s string
				if json.Unmarshal(val, &s) == nil {
					f.model, f.modelStr = s, true
				}
			}
		case bytes.Equal(key, []byte("stream")):
			f.stream = bytes.Equal(val, []byte("true"))
		case bytes.Equal(key, []byte("reasoning_effort")):
			f.hasEffort = true
			if len(val) > 0 && val[0] == '"' {
				var s string
				if json.Unmarshal(val, &s) == nil {
					f.effort, f.effortStr = s, true
				}
			}
		case bytes.Equal(key, []byte("thinking")):
			f.hasThink = true
			if len(val) > 0 && val[0] == '{' {
				f.thinkType = objectString(val, "type")
			}
		case bytes.Equal(key, []byte("tools")):
			f.hasTools = true
		}
	}
	return f
}

// withModel 把 model 值换成 upstream，其余字节原样保留。
// 老实现是 map[string]any 往返：既把整个 body 重新序列化（大 body 下等于把
// 提示词完整复制一遍），又会被 json.Marshal 的 HTML 转义把 < > & 改成 \u003c，
// 上游看到的提示词与客户端发出的不再逐字节一致。
func (f bodyFacts) withModel(body []byte, upstream string) ([]byte, bool) {
	if !f.ok || !f.hasModel || f.modelAt < 0 || f.modelEnd <= f.modelAt || f.modelEnd > len(body) {
		return nil, false
	}
	enc, err := json.Marshal(upstream)
	if err != nil {
		return nil, false
	}
	out := make([]byte, 0, len(body)-(f.modelEnd-f.modelAt)+len(enc))
	out = append(out, body[:f.modelAt]...)
	out = append(out, enc...)
	out = append(out, body[f.modelEnd:]...)
	return out, true
}

// withStringField 在顶层插入一个字符串字段（客户端没给 reasoning_effort 时补档位）。
func (f bodyFacts) withStringField(body []byte, key, value string) ([]byte, bool) {
	if !f.ok || f.closeAt <= 0 || f.closeAt >= len(body) || body[f.closeAt] != '}' {
		return nil, false
	}
	k, err := json.Marshal(key)
	if err != nil {
		return nil, false
	}
	v, err := json.Marshal(value)
	if err != nil {
		return nil, false
	}
	out := make([]byte, 0, len(body)+len(k)+len(v)+3)
	out = append(out, body[:f.closeAt]...)
	if f.keys > 0 {
		out = append(out, ',')
	}
	out = append(out, k...)
	out = append(out, ':')
	out = append(out, v...)
	out = append(out, body[f.closeAt:]...)
	return out, true
}

// expectsThinking 对应老的 reasoningExpectsThinking：客户端显式声明要思考。
// reasoning_effort 不是字符串时老实现整段 Unmarshal 失败、返回 false，这里保持一致。
func (f bodyFacts) expectsThinking() bool {
	if f.hasEffort && !f.effortStr {
		return false
	}
	if f.effortStr && f.effort != "" && !equalFoldASCII(f.effort, "off") {
		return true
	}
	return f.hasThink && equalFoldASCII(f.thinkType, "enabled")
}

// equalFoldASCII 是 strings.EqualFold 的零分配版：这些字段只可能是 ASCII
// 档位名（low / medium / high / off / enabled / disabled）。
func equalFoldASCII(s, want string) bool {
	if len(s) != len(want) {
		return false
	}
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c >= 'A' && c <= 'Z' {
			c += 'a' - 'A'
		}
		if c != want[i] {
			return false
		}
	}
	return true
}
