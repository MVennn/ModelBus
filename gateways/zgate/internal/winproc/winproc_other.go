//go:build !windows

package winproc

import (
	"net"
	"os"
	"os/exec"
	"syscall"
	"time"
)

func (p *Process) start() error {
	p.cmd.SysProcAttr = nil
	return p.cmd.Start()
}

func (p *Process) kill() error {
	if p == nil || p.cmd.Process == nil {
		return nil
	}
	return p.cmd.Process.Kill()
}

func (p *Process) release() {}

// PortBusy reports whether something accepts connections on the loopback port.
func PortBusy(port int) bool {
	conn, err := net.DialTimeout("tcp", listenAddr(port), 300*time.Millisecond)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

// detachedAttr has no effect outside Windows; the child simply inherits.
func DetachedAttr() *syscall.SysProcAttr { return nil }

var _ = exec.Command

// ProcessAlive reports whether pid still names a running process.
func ProcessAlive(pid uint32) bool {
	if pid == 0 {
		return false
	}
	p, err := os.FindProcess(int(pid))
	if err != nil {
		return false
	}
	return p.Signal(syscall.Signal(0)) == nil
}
