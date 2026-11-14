package router

import "sync"

// streamBufSize 是流式转发每块读缓冲的大小。原先每个请求 make([]byte, 32*1024)
// 一次，请求量上来之后这些 32 KB 块全部变成 GC 的短命对象；池化后稳态分配接近 0。
const streamBufSize = 32 * 1024

var streamBufPool = sync.Pool{
	New: func() any {
		b := make([]byte, streamBufSize)
		return &b
	},
}

// getStreamBuf 借一块读缓冲。归还用 putStreamBuf，且只能由「拥有者」还一次：
// 有读者 goroutine 时，块随 streamRead 一起交给写端，由写端还。
func getStreamBuf() *[]byte {
	p, _ := streamBufPool.Get().(*[]byte)
	if p == nil {
		b := make([]byte, streamBufSize)
		return &b
	}
	return p
}

func putStreamBuf(p *[]byte) {
	if p == nil {
		return
	}
	streamBufPool.Put(p)
}
