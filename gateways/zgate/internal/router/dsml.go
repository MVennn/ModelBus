package router

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"time"

	"zgate/internal/logx"
)

// 这段代码补的是「上游把工具调用写成正文」那条缝。
//
// 2026-11-15 的账：DeepSeek 走 OC 渠道时偶发不返回结构化 tool_calls，而是把
// 调用序列化成自家的 special token 文本吐进 content —— 用全角竖线 U+FF5C 包住
// DSML 字样，后面跟 invoke / parameter / calls 三个关键字。客户端只认结构化字段，
// 于是这一轮既没有工具可执行，又把这段标记当正文写进上下文；用户看到的是
// 「模型分析了一大段，然后对话中断」。
//
// 这里不尝试还原 tool_calls：参数格式上游从来没给全（实测只漏出 parameter 段和
// 闭合标签，开标签被吞），按猜出来的格式造 tool_call 比不造更糟。只做三件事：
//  1. 命中标记后停止把这段正文转发给客户端，别让它进上下文；
//  2. 流结束时补一帧 finish_reason=error 显式说明原因，别让客户端以为正常结束；
//  3. 计数进 /health，让它有数可看，而不是只能翻会话存档。

const (
	// dsmlPipe 是全角竖线 U+FF5C，DeepSeek special token 的分隔符。
	dsmlPipe = "\uFF5C"
	// dsmlHoldCap 是扣留上限：超过就按误判处理、原样放行，
	// 避免正文里恰好提到这个标记时把后面几万字全吞掉。
	dsmlHoldCap = 256 << 10
)

var dsmlMark = []byte(dsmlPipe + "DSML" + dsmlPipe)

// dsmlFilter 坐在上游 SSE 与客户端写端之间。它只认完整事件（以空行分隔），
// 不完整的那截留在 line 里等下一个读块，所以标记被拆到两个 TCP 段上也认得出。
type dsmlFilter struct {
	model string
	log   *logx.Logger
	stats *upstreamStats

	line  []byte // 未凑成完整 SSE 事件的残留
	hold  []byte // 已扣留、不再转发的正文
	armed bool   // 已命中标记，后续正文一律扣留
	hit   bool   // 本流命中过（日志与计数用）
}

func newDSMLFilter(model string, log *logx.Logger, stats *upstreamStats) *dsmlFilter {
	return &dsmlFilter{model: model, log: log, stats: stats}
}

// feed 吃上游原始字节，返回应当转发给客户端的字节（可能为空）。
func (f *dsmlFilter) feed(p []byte) []byte {
	if f == nil || len(p) == 0 {
		return p
	}
	f.line = append(f.line, p...)
	var out []byte
	for {
		i := bytes.Index(f.line, []byte("\n\n"))
		if i < 0 {
			break
		}
		ev := f.line[:i+2]
		f.line = f.line[i+2:]
		if !f.armed && bytes.Contains(ev, dsmlMark) {
			f.armed = true
			f.hit = true
			f.log.Warnf("[router] 上游把工具调用写成了正文（DSML 标记），后续正文扣留不转发（model=%s）", f.model)
		}
		if f.armed {
			f.hold = append(f.hold, ev...)
			if len(f.hold) > dsmlHoldCap {
				f.log.Warnf("[router] DSML 扣留超过 %d 字节，按误判处理原样放行（model=%s）", dsmlHoldCap, f.model)
				out = append(out, f.hold...)
				f.hold = nil
				f.armed = false
				f.hit = false
			}
			continue
		}
		out = append(out, ev...)
	}
	return out
}

// finish 在流结束时收口。命中过就丢掉扣留内容、补一帧 error + [DONE]：
// 客户端拿到的是「这一轮上游坏了，重试」，而不是「200 + 半截正文 + 安静结束」。
func (f *dsmlFilter) finish(w io.Writer, flusher http.Flusher) {
	if f == nil {
		return
	}
	if len(f.line) > 0 && !f.armed {
		_, _ = w.Write(f.line)
		f.line = nil
	}
	if !f.hit {
		return
	}
	if f.stats != nil {
		f.stats.dsml.Add(1)
	}
	payload := map[string]any{
		"id":      "zgate-dsml",
		"object":  "chat.completion.chunk",
		"created": time.Now().Unix(),
		"model":   f.model,
		"choices": []any{map[string]any{
			"index":         0,
			"delta":         map[string]any{},
			"finish_reason": "error",
		}},
		"error": map[string]any{
			"type":    "upstream_tool_call_as_text",
			"message": "上游把工具调用降级成了正文文本（DSML 标记），本轮没有可执行的 tool_call，请重试",
		},
	}
	b, err := json.Marshal(payload)
	if err != nil {
		return
	}
	_, _ = w.Write([]byte("data: " + string(b) + "\n\ndata: [DONE]\n\n"))
	if flusher != nil {
		flusher.Flush()
	}
}
