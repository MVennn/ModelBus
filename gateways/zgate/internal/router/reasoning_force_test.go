package router

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"

	"zgate/internal/config"
)

// injectThinkingEffort：只在「配置了 forceEffort + 模型命中 + 客户端没声明档位」时补。
// 这个纯函数单测锁死四条边界，避免以后改守卫时把「用户显式关思考」也一起改回去。
func TestInjectThinkingEffort(t *testing.T) {
	cases := []struct {
		name  string
		guard config.ReasoningGuard
		body  string
		want  bool
		eff   string
	}{
		{
			name:  "缺档位时补上",
			guard: config.ReasoningGuard{Enabled: true, ForceEffort: "high", ForceEffortModels: []string{"Iceman"}},
			body:  `{"model":"Iceman","stream":true}`,
			want:  true,
			eff:   "high",
		},
		{
			name:  "客户端显式 off 不动",
			guard: config.ReasoningGuard{Enabled: true, ForceEffort: "high", ForceEffortModels: []string{"Iceman"}},
			body:  `{"model":"Iceman","reasoning_effort":"off"}`,
			want:  false,
		},
		{
			name:  "客户端已声明 high 不重复写",
			guard: config.ReasoningGuard{Enabled: true, ForceEffort: "high", ForceEffortModels: []string{"Iceman"}},
			body:  `{"model":"Iceman","reasoning_effort":"high"}`,
			want:  false,
		},
		{
			name:  "白名单外模型不补",
			guard: config.ReasoningGuard{Enabled: true, ForceEffort: "high", ForceEffortModels: []string{"Iceman"}},
			body:  `{"model":"beam-free"}`,
			want:  false,
		},
		{
			name:  "ForceEffortModels 为空回落 Models",
			guard: config.ReasoningGuard{Enabled: true, ForceEffort: "high", Models: []string{"iceman-contributor-free"}},
			body:  `{"model":"ICEMAN-CONTRIBUTOR-FREE"}`,
			want:  true,
			eff:   "high",
		},
		{
			name:  "未开启守卫不补",
			guard: config.ReasoningGuard{ForceEffort: "high", ForceEffortModels: []string{"Iceman"}},
			body:  `{"model":"Iceman"}`,
			want:  false,
		},
		{
			name:  "没配档位不补",
			guard: config.ReasoningGuard{Enabled: true, ForceEffortModels: []string{"Iceman"}},
			body:  `{"model":"Iceman"}`,
			want:  false,
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			out, ok := injectThinkingEffort(tc.guard, []byte(tc.body))
			if ok != tc.want {
				t.Fatalf("injected = %v, want %v (out=%s)", ok, tc.want, out)
			}
			if !ok {
				if string(out) != tc.body {
					t.Fatalf("未注入时 body 必须逐字节不变：%s", out)
				}
				return
			}
			var probe struct {
				Effort string `json:"reasoning_effort"`
			}
			if err := json.Unmarshal(out, &probe); err != nil {
				t.Fatalf("注入后不是合法 JSON：%v (%s)", err, out)
			}
			if probe.Effort != tc.eff {
				t.Fatalf("reasoning_effort = %q, want %q", probe.Effort, tc.eff)
			}
		})
	}
}

// forceState 记录每次上游请求体，用来断言「网关确实把档位补上了」。
type forceState struct {
	mu    sync.Mutex
	calls int
	bodys []string
}

func (f *forceState) snapshot() (int, []string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.calls, append([]string(nil), f.bodys...)
}

// 全链路回归：客户端压根不带 reasoning_effort（DSH 现在的真实请求形态）
// → 网关补 high → 守卫识别加密分流 → 换连接重抽 → 客户端拿到明文思考流。
func TestReasoningGuardForcesEffortThenRedraws(t *testing.T) {
	st := &forceState{}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		st.mu.Lock()
		st.calls++
		n := st.calls
		st.bodys = append(st.bodys, string(raw))
		st.mu.Unlock()
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(200)
		if n == 1 {
			_, _ = io.WriteString(w, guardEncryptedSSE())
		} else {
			_, _ = io.WriteString(w, guardPlainSSE())
		}
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}
	}))
	t.Cleanup(upstream.Close)

	model, upstreamName := "Iceman", "iceman-contributor-free"
	mapJSON := fmt.Sprintf(`{"models":{"%s":{"channel":"OC","upstream":"%s","base":"%s","protocol":"chat"}}}`, model, upstreamName, upstream.URL)
	srv, log := newServer(t, mapJSON, upstream.URL)
	cfg := *srv.Config()
	cfg.ReasoningGuard = config.ReasoningGuard{
		Enabled: true, MaxRetries: 3, MaxProbeBytes: 32768,
		ForceEffort: "high", ForceEffortModels: []string{upstreamName},
	}
	srv.setRuntime(&cfg, srv.keyset())
	front := httptest.NewServer(srv.Handler())
	t.Cleanup(front.Close)

	// 注意：这里故意不写 reasoning_effort —— 复现 DSH「Default 伪档位」的真实请求。
	body := `{"model":"Iceman","messages":[{"role":"user","content":"请用一句话介绍春天。"}],"stream":true,"max_tokens":512}`
	payload := guardRequest(t, front, body)

	calls, bodys := st.snapshot()
	if calls != 2 {
		t.Fatalf("上游调用次数 = %d, want 2（第一次加密分流应触发重抽）", calls)
	}
	for i, b := range bodys {
		if !strings.Contains(b, `"reasoning_effort":"high"`) {
			t.Fatalf("第 %d 次上游请求没被补上 reasoning_effort：%s", i+1, b)
		}
	}
	if !strings.Contains(payload, "Considering the task") {
		t.Fatalf("客户端没拿到明文思考流：%s", payload)
	}
	if strings.Contains(payload, "春天是") {
		t.Fatalf("加密分流那一次的内容泄漏到了客户端：%s", payload)
	}
	raw, err := os.ReadFile(log.Path())
	if err != nil {
		t.Fatalf("读日志失败：%v", err)
	}
	joined := string(raw)
	if !strings.Contains(joined, "客户端未声明思考档位") {
		t.Fatalf("日志里没有补档记录：\n%s", joined)
	}
	if !strings.Contains(joined, "换连接+换会话重抽 1/3") {
		t.Fatalf("日志里没有重抽记录：\n%s", joined)
	}
}
