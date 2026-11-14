package router

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"sync/atomic"
)

// 请求号：把一次请求的所有线索（响应头、/admin/stats 的慢请求表、日志）串起来。
//
// 为什么要有：网关一次请求可能跨 8 跳、重抽若干次，出问题时客户端手里只有一个
// 时间点。带上请求号之后，客户端把响应头里的 X-Zgate-Request-Id 贴出来，
// 就能在 /admin/stats 的 slow 列表里直接对上同一条记录，不必按时间去猜。

type reqIDKey struct{}

// newReqID 生成 8 字节随机十六进制串（16 个字符）。
func newReqID() string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		// 拿不到随机数也不能让请求失败：退化成空串，响应头会留空，
		// 排查时最多丢一层关联，不影响转发。
		return ""
	}
	return hex.EncodeToString(b[:])
}

func withReqID(ctx context.Context, id string) context.Context {
	if id == "" {
		return ctx
	}
	return context.WithValue(ctx, reqIDKey{}, id)
}

// reqIDFrom 取请求号；没有就返回空串（测试直接调内部函数时就是这种情况）。
func reqIDFrom(ctx context.Context) string {
	id, _ := ctx.Value(reqIDKey{}).(string)
	return id
}

// reqCounter 累计「这条请求一共打过几次上游」，跨跳共享。
//
// 为什么不能只数单跳：回落（forwardChain）是逐跳递归进 doForwardWith 的，
// 每一跳都有自己的局部计数，客户端看到的 X-Zgate-Attempt 就会永远显示 1 ——
// 而那正是最需要看出来「前面失败过几次」的时候。用 context 里一个原子计数器，
// 竞速模式下多路并发也不会互相覆盖。
type reqCounter struct{ n atomic.Int32 }

type reqCounterKey struct{}

func withReqCounter(ctx context.Context) context.Context {
	return context.WithValue(ctx, reqCounterKey{}, &reqCounter{})
}

func reqCounterFrom(ctx context.Context) *reqCounter {
	c, _ := ctx.Value(reqCounterKey{}).(*reqCounter)
	return c
}

// bumpAttempt 返回「这是第几次打上游」；没有计数器时退化成 0，由调用方自己计数。
func bumpAttempt(ctx context.Context) int {
	if c := reqCounterFrom(ctx); c != nil {
		return int(c.n.Add(1))
	}
	return 0
}
