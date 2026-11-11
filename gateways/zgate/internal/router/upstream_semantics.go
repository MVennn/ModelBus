package router

import (
	"bytes"
	"encoding/json"
	"net/http"
	"strings"
	"sync/atomic"
	"time"
)

// ── 上游语义分类 ───────────────────────────────────────────────────────────
// 2026-11-11：catiecli 的 Gemini 链有两种「不是这条链坏了」的上游错误，老实现把
// 它们当成普通 4xx/5xx 一视同仁：
//   · 503 high demand（需求量较大）：模型忙，窗口是秒到几十秒，换一跳就有；
//     老实现按 status>=500 走软冷却（GM 的 softCooldownSeconds=60），一个忙跳
//     被埋一分钟，用户看到的是「另外几跳明明空着却一直不派车」。
//   · 400 thinking_level 枚举不合法：请求里带了 Gemini 不认识的思考档位
//     （high/max/off/BOGUS 都算），剥掉这个参数同一跳就能过；老实现原样回给
//     客户端，用户看到的是 INVALID_REQUEST / BAD_REQUEST。
// 这两个都该在网关内部就地处理：上游的实现细节不是用户该看见的东西。

// busyMarkers 是「上游在说它忙」的原文特征。只认 503/529 里的这些句子：
// 429 是限流（有专门的就地退避），502/504 是链路问题；把它们算成忙，会把真正
// 坏掉的跳当成「过一会儿就好」，白白延长故障窗口。
var busyMarkers = []string{
	"high demand",
	"spikes in demand",
	"需求量较大",
	"需求高峰",
	"请稍后再试",
	"please try again later",
}

// busyExhausted 判断这次失败是不是「上游说它忙」。
func busyExhausted(status int, head []byte) bool {
	if status != http.StatusServiceUnavailable && status != 529 {
		return false
	}
	lower := strings.ToLower(string(head))
	for _, m := range busyMarkers {
		if strings.Contains(lower, strings.ToLower(m)) {
			return true
		}
	}
	return false
}

// invalidThinkingParam 判断这次 400 是不是「思考档位枚举不合法」。Google 原文：
//
//	Invalid value at 'generation_config.thinking_config.thinking_level'
//	(type.googleapis.com/google.ai.generativelanguage.v1beta.ThinkingConfig.ThinkingLevel), "BOGUS"
//
// 只要 400 的正文点到 thinking 相关字段，就按「参数可剥」处理：同一跳剥掉参数
// 重发一次，比把 400 冒泡给用户划算得多。
func invalidThinkingParam(status int, head []byte) bool {
	if status != http.StatusBadRequest {
		return false
	}
	lower := strings.ToLower(string(head))
	return strings.Contains(lower, "thinking_level") ||
		strings.Contains(lower, "thinking_config") ||
		strings.Contains(lower, "thinkinglevel")
}

// thinkingParamKeys 是所有「告诉上游想多深」的字段名。它们在 Gemini 原生枚举里
// 并不通用，剥掉只是退回默认档位，比整个请求 400 划算。
var thinkingParamKeys = []string{
	"reasoning_effort", "reasoning", "thinking", "thinking_budget",
	"thinking_level", "thinkingLevel", "thinkingConfig", "thinking_config",
}

// stripThinkingParams 尽力剥掉思考相关参数，返回新 body 与「是否真的剥掉了东西」。
// 只在 400 命中 invalidThinkingParam 时调用，剥完必须变短/变形，否则重发没有意义。
func stripThinkingParams(body []byte) ([]byte, bool) {
	if len(body) == 0 {
		return nil, false
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(body, &m); err != nil {
		return nil, false
	}
	changed := false
	for _, k := range thinkingParamKeys {
		if _, ok := m[k]; ok {
			delete(m, k)
			changed = true
		}
	}
	for _, outer := range []string{"extra_body", "generation_config"} {
		raw, ok := m[outer]
		if !ok {
			continue
		}
		var inner map[string]json.RawMessage
		if err := json.Unmarshal(raw, &inner); err != nil {
			continue
		}
		hit := false
		for _, k := range thinkingParamKeys {
			if _, ok := inner[k]; ok {
				delete(inner, k)
				hit = true
			}
		}
		if g, ok := inner["google"]; ok {
			var gm map[string]json.RawMessage
			if err := json.Unmarshal(g, &gm); err == nil {
				if _, ok := gm["thinking_config"]; ok {
					delete(gm, "thinking_config")
					hit = true
					if nb, err := json.Marshal(gm); err == nil {
						inner["google"] = nb
					}
				}
			}
		}
		if hit {
			changed = true
			if nb, err := json.Marshal(inner); err == nil {
				m[outer] = nb
			}
		}
	}
	if !changed {
		return nil, false
	}
	out, err := json.Marshal(m)
	if err != nil {
		return nil, false
	}
	return out, true
}

// ── 观测 ──────────────────────────────────────────────────────────────────

// upstreamStats 是「上游语义」这一层的计数。跟 earlyStats 一样只有观测作用，
// 但它是回答「这些适配到底有没有在干活」的唯一读数（2026-11-10 复盘里
// 提前交卷就吃过「全量生效、零观测」的亏）。
type upstreamStats struct {
	busy      atomic.Int64 // 上游说忙的次数
	busySkip  atomic.Int64 // 因为忙而跳过该跳（含冷却）的次数
	invalid   atomic.Int64 // 思考参数不合法被剥掉重发的次数
	truncated atomic.Int64 // 补了截断收口帧的流数
}

func newUpstreamStats() *upstreamStats { return &upstreamStats{} }

func (st *upstreamStats) view() map[string]any {
	if st == nil {
		return map[string]any{}
	}
	return map[string]any{
		"busy":              st.busy.Load(),
		"busy_skipped":      st.busySkip.Load(),
		"thinking_strip":    st.invalid.Load(),
		"truncated_streams": st.truncated.Load(),
	}
}

// ── 截断收口 ──────────────────────────────────────────────────────────────

// streamTracker 记住「这条 SSE 有没有正常说完」。判据只有两条：见过非 null 的
// finish_reason，或见过 [DONE]。上游中途被掐断时两者都没有，客户端却只会看到
// socket 安静关闭 —— 于是把半截回答当完整回答存进上下文，或者界面一直转圈。
type streamTracker struct {
	tail []byte
	done bool
	any  bool
}

const streamTailCap = 8 << 10

func (t *streamTracker) feed(p []byte) {
	if t == nil || len(p) == 0 {
		return
	}
	t.any = true
	if bytes.Contains(p, []byte("[DONE]")) {
		t.done = true
	}
	t.tail = append(t.tail, p...)
	if len(t.tail) > streamTailCap {
		t.tail = t.tail[len(t.tail)-streamTailCap:]
	}
}

// finished 判定这条流是否正常收尾。一个字节都没写过的不算「截断」—— 那由
// 上游错误路径负责，不该再补一帧空错误。
func (t *streamTracker) finished() bool {
	if t == nil || !t.any {
		return true
	}
	return t.done || hasFinishReason(t.tail)
}

// hasFinishReason 在流尾部找一次非 null 的 finish_reason。
// "finish_reason":null 是上游常见的「先占位后填值」，不能当成说完了。
func hasFinishReason(tail []byte) bool {
	for {
		i := bytes.Index(tail, []byte(`"finish_reason":`))
		if i < 0 {
			return false
		}
		rest := bytes.TrimLeft(tail[i+len(`"finish_reason":`):], " ")
		if !bytes.HasPrefix(rest, []byte("null")) {
			return true
		}
		tail = rest
	}
}

// closeTruncated 给被上游掐断的 SSE 补一帧 error + [DONE]。
// 为什么要补：不补的话客户端拿到的是「200 + 半截正文 + 连接断开」，多数 harness
// 会把它当成功回答写进上下文（用户看到的是一段莫名其妙断掉的话），少数会读到
// EOF 报一个与真实原因无关的错。补一帧把「上游截断」这件事显式说出来，
// 客户端才有机会重试，/health 也才有数可看。
func (s *Server) closeTruncated(w http.ResponseWriter, flusher http.Flusher, model string, wrote bool, t *streamTracker) {
	if !wrote || t.finished() {
		return
	}
	if s.sem != nil {
		s.sem.truncated.Add(1)
	}
	s.log.Warnf("[router] 上游在 finish_reason 之前断流（model=%s），已补一帧 error + [DONE] 收口", model)
	payload := map[string]any{
		"id":      "zgate-truncated",
		"object":  "chat.completion.chunk",
		"created": time.Now().Unix(),
		"model":   model,
		"choices": []any{map[string]any{
			"index":         0,
			"delta":         map[string]any{},
			"finish_reason": "error",
		}},
		"error": map[string]any{
			"type":    "upstream_truncated",
			"message": "上游在 finish_reason 之前断开（多为高峰期的稳定截断），请重试",
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
