//go:build windows

package winproc

import (
	"net"
	"syscall"
	"time"
	"unsafe"
)

const (
	createNoWindow  = 0x08000000
	createNewGroup  = 0x00000200
	detachedProcess = 0x00000008

	jobObjectExtendedLimitInformation = 9
	jobObjectLimitKillOnJobClose      = 0x00002000

	processAllAccess = 0x1F0FFF
)

var (
	kernel32                 = syscall.NewLazyDLL("kernel32.dll")
	procCreateJobObjectW     = kernel32.NewProc("CreateJobObjectW")
	procSetInformationJobObj = kernel32.NewProc("SetInformationJobObject")
	procAssignProcessToJob   = kernel32.NewProc("AssignProcessToJobObject")
	procTerminateJobObject   = kernel32.NewProc("TerminateJobObject")
	procCloseHandle          = kernel32.NewProc("CloseHandle")
	procOpenProcess          = kernel32.NewProc("OpenProcess")
	procGetExitCodeProcess   = kernel32.NewProc("GetExitCodeProcess")
)

type jobBasicLimit struct {
	PerProcessUserTimeLimit int64
	PerJobUserTimeLimit     int64
	LimitFlags              uint32
	MinimumWorkingSetSize   uintptr
	MaximumWorkingSetSize   uintptr
	ActiveProcessLimit      uint32
	Affinity                uintptr
	PriorityClass           uint32
	SchedulingClass         uint32
}

type ioCounters struct {
	ReadOperationCount  uint64
	WriteOperationCount uint64
	OtherOperationCount uint64
	ReadTransferCount   uint64
	WriteTransferCount  uint64
	OtherTransferCount  uint64
}

type jobExtendedLimit struct {
	BasicLimitInformation jobBasicLimit
	IOInfo                ioCounters
	ProcessMemoryLimit    uintptr
	JobMemoryLimit        uintptr
	PeakProcessMemoryUsed uintptr
	PeakJobMemoryUsed     uintptr
}

func (p *Process) start() error {
	p.cmd.SysProcAttr = &syscall.SysProcAttr{
		CreationFlags: createNoWindow | createNewGroup,
		HideWindow:    true,
	}
	if err := p.cmd.Start(); err != nil {
		return err
	}

	job, _, _ := procCreateJobObjectW.Call(0, 0)
	if job == 0 {
		return nil
	}
	info := jobExtendedLimit{}
	info.BasicLimitInformation.LimitFlags = jobObjectLimitKillOnJobClose
	procSetInformationJobObj.Call(
		job,
		uintptr(jobObjectExtendedLimitInformation),
		uintptr(unsafe.Pointer(&info)),
		unsafe.Sizeof(info),
	)
	// Assigning can fail if the child already exited; that is not fatal.
	if ph, err := syscall.OpenProcess(processAllAccess, false, uint32(p.cmd.Process.Pid)); err == nil {
		procAssignProcessToJob.Call(job, uintptr(ph))
		procCloseHandle.Call(uintptr(ph))
	}
	p.job = job
	return nil
}

func (p *Process) kill() error {
	if p == nil || p.cmd.Process == nil {
		return nil
	}
	if p.job != 0 {
		procTerminateJobObject.Call(p.job, 1)
	}
	return p.cmd.Process.Kill()
}

func (p *Process) release() {
	if p.job != 0 {
		procCloseHandle.Call(p.job)
		p.job = 0
	}
}

// PortBusy reports whether something accepts connections on the loopback port.
//
// A plain bind() is not enough on Windows: the gateway binds 0.0.0.0:7863 and a
// second listen on 127.0.0.1:7863 still succeeds, which made zgate think the
// port was free while wb2api was serving on it.
func PortBusy(port int) bool {
	conn, err := net.DialTimeout("tcp", listenAddr(port), 300*time.Millisecond)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

// detachedAttr keeps a child alive after the launching console disappears:
// the child gets no console at all, so a console-window close cannot send it
// CTRL_CLOSE_EVENT, and the parent may exit immediately after Start.
func DetachedAttr() *syscall.SysProcAttr {
	return &syscall.SysProcAttr{
		CreationFlags: detachedProcess | createNewGroup | createNoWindow,
		HideWindow:    true,
	}
}

const (
	processQueryLimitedInformation = 0x1000
	stillActive                    = 259
)

// ProcessAlive reports whether pid still names a running process.
//
// OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION) works for processes in any
// session, which is what the -tray launcher needs: its parent may be a
// terminal in another session. A PID can be reused, but the launcher is our
// direct parent and the check runs every two seconds, so the window is tiny.
func ProcessAlive(pid uint32) bool {
	if pid == 0 {
		return false
	}
	h, _, _ := procOpenProcess.Call(processQueryLimitedInformation, 0, uintptr(pid))
	if h == 0 {
		return false
	}
	defer procCloseHandle.Call(h)
	var code uint32
	ok, _, _ := procGetExitCodeProcess.Call(h, uintptr(unsafe.Pointer(&code)))
	if ok == 0 {
		return true // handle valid but query failed: assume alive, do not kill
	}
	return code == stillActive
}
