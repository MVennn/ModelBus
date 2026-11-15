package router

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"zgate/internal/logx"
)

func testDSMLLogger(t *testing.T) *logx.Logger {
	t.Helper()
	log, err := logx.Open(t.TempDir(), "test.log", 1)
	if err != nil {
		t.Fatalf("open log: %v", err)
	}
	t.Cleanup(log.Close)
	return log
}

// sseContentEvent 造一条只带 content 的 OpenAI 兼容增量帧。
func sseContentEvent(content string) []byte {
	return []byte("data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"" + content +
		"\"},\"finish_reason\":null}]}\n\n")
}

func TestDSMLFilterPassesNormalStream(t *testing.T) {
	f := newDSMLFilter("m", testDSMLLogger(t), nil)
	in := sseContentEvent("hello")
	if got := f.feed(in); string(got) != string(in) {
		t.Fatalf("正常流不该被改动，得到 %q", got)
	}
	if f.hit || f.armed {
		t.Fatal("正常流不该命中")
	}
	var out bytes.Buffer
	f.finish(&out, nil)
	if out.Len() != 0 {
		t.Fatalf("没命中就不该补帧，得到 %q", out.String())
	}
}

func TestDSMLFilterHoldsMarkedContent(t *testing.T) {
	stats := newUpstreamStats()
	f := newDSMLFilter("m", testDSMLLogger(t), stats)

	if got := f.feed(sseContentEvent("先分析一下")); len(got) == 0 {
		t.Fatal("命中前的正文应当照常转发")
	}

	mark := dsmlPipe + "DSML" + dsmlPipe + "invoke name=\"pwsh\""
	if got := f.feed(sseContentEvent(mark)); len(got) != 0 {
		t.Fatalf("命中标记的事件不该转发，得到 %q", got)
	}
	if !f.hit || !f.armed {
		t.Fatal("应当进入扣留模式")
	}

	if got := f.feed([]byte("data: [DONE]\n\n")); len(got) != 0 {
		t.Fatalf("收尾帧也该被扣留，得到 %q", got)
	}

	var out bytes.Buffer
	f.finish(&out, nil)
	s := out.String()
	if !strings.Contains(s, "upstream_tool_call_as_text") {
		t.Fatalf("收口帧应当说明原因，得到 %s", s)
	}
	if !strings.Contains(s, "[DONE]") {
		t.Fatalf("收口帧应当补 [DONE]，得到 %s", s)
	}
	if stats.dsml.Load() != 1 {
		t.Fatalf("计数应为 1，实为 %d", stats.dsml.Load())
	}
}

func TestDSMLFilterDetectsSplitMark(t *testing.T) {
	f := newDSMLFilter("m", testDSMLLogger(t), nil)
	full := sseContentEvent(dsmlPipe + "DSML" + dsmlPipe + "invoke")
	cut := len(full) / 2
	if got := f.feed(full[:cut]); len(got) != 0 {
		t.Fatalf("不完整事件不该转发，得到 %q", got)
	}
	if got := f.feed(full[cut:]); len(got) != 0 {
		t.Fatalf("凑齐后应命中并扣留，得到 %q", got)
	}
	if !f.hit {
		t.Fatal("标记被拆到两个读块上也应当命中")
	}
}

func TestDSMLFilterReleasesOnOverflow(t *testing.T) {
	f := newDSMLFilter("m", testDSMLLogger(t), nil)
	f.feed(sseContentEvent(dsmlPipe + "DSML" + dsmlPipe))
	pad := strings.Repeat("x", 8192)
	var out []byte
	for i := 0; i < 64 && len(out) == 0; i++ {
		out = append(out, f.feed(sseContentEvent(pad))...)
	}
	if len(out) == 0 {
		t.Fatal("扣留超过上限后应当原样放行")
	}
	if f.armed || f.hit {
		t.Fatal("兜底放行后应当解除扣留")
	}
}

func TestDSMLFilterNilPassthrough(t *testing.T) {
	var f *dsmlFilter
	in := []byte("abc")
	if got := f.feed(in); string(got) != "abc" {
		t.Fatalf("nil filter 应当原样返回，得到 %q", got)
	}
	f.finish(io.Discard, nil)
}

// TestDSMLStreamIsCappedEndToEnd 走真实 Handler：假上游把工具调用写成正文，
// 断言客户端拿到的是「命中前的正文 + 一帧说明 + [DONE]」，标记本身不落地。
func TestDSMLStreamIsCappedEndToEnd(t *testing.T) {
	mark := dsmlPipe + "DSML" + dsmlPipe + "invoke name=\"pwsh\""
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		fl, _ := w.(http.Flusher)
		_, _ = io.WriteString(w, "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"先看一下\"},\"finish_reason\":null}]}\n\n")
		_, _ = io.WriteString(w, "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\""+mark+"\"},\"finish_reason\":null}]}\n\n")
		_, _ = io.WriteString(w, "data: [DONE]\n\n")
		if fl != nil {
			fl.Flush()
		}
	}))
	defer upstream.Close()

	srv, _ := newServer(t, `{"models":{},"legacy":{}}`, upstream.URL)
	front := httptest.NewServer(srv.Handler())
	defer front.Close()

	req, err := http.NewRequest(http.MethodPost, front.URL+"/v1/chat/completions",
		strings.NewReader(`{"model":"cn:space-bunny","messages":[{"role":"user","content":"hi"}],"stream":true}`))
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(resp.Body)
	s := string(raw)

	if strings.Contains(s, dsmlPipe+"DSML") {
		t.Fatalf("DSML 标记不该出现在客户端流里：%s", s)
	}
	if !strings.Contains(s, "先看一下") {
		t.Fatalf("命中前的正文应当照常到达：%s", s)
	}
	if !strings.Contains(s, "upstream_tool_call_as_text") {
		t.Fatalf("应当补一帧说明原因：%s", s)
	}
	if !strings.Contains(s, "[DONE]") {
		t.Fatalf("收口应当带 [DONE]：%s", s)
	}
}
