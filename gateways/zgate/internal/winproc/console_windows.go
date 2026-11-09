//go:build windows

package winproc

import (
	"os"
	"syscall"
)

const (
	attachParentProcess = ^uintptr(0) // (DWORD)-1

	stdOutputHandle = ^uintptr(10) // (DWORD)-11, STD_OUTPUT_HANDLE

	fileTypeUnknown = 0 // invalid handle
	fileTypeDisk    = 1 // redirection to a file
	fileTypeChar    = 2 // console screen buffer
	fileTypePipe    = 3 // mintty / CI / child_process
)

var (
	procAttachConsole = kernel32.NewProc("AttachConsole")
	procGetStdHandle  = kernel32.NewProc("GetStdHandle")
	procGetFileType   = kernel32.NewProc("GetFileType")
	procFreeConsole   = kernel32.NewProc("FreeConsole")
)

// AttachParentConsole rebinds stdout/stderr to the terminal that launched us.
//
// zgate is built as a GUI-subsystem binary so autostart never flashes a console
// window. Inherited handles that already work — pipes (mintty, CI, scripts) and
// file redirections — must be left alone, or output would be swallowed by a
// hidden conhost and `zgate status > file` would be empty. Only when stdout is
// unusable or a raw console handle do we attach to the parent's console, so
// running from cmd / PowerShell still prints.
//
// The catch: a Windows console window closes with its last attached process.
// Since zgate survives the shell that started it (closing the console does not
// kill it — only Ctrl+C or taskkill does), an attached console would sit there
// half-dead for as long as the gateway runs. DetachConsole undoes the attach
// once the boot banner is out, which keeps the terminal readable and gives the
// console window back to its shell.
func AttachParentConsole() bool {
	if keepInheritedStdio() {
		return true
	}
	ok, _, _ := procAttachConsole.Call(attachParentProcess)
	if ok == 0 {
		return false
	}
	if out, err := os.OpenFile("CONOUT$", os.O_WRONLY, 0); err == nil {
		os.Stdout = out
		os.Stderr = out
	}
	return true
}

// DetachConsole releases a console taken by AttachParentConsole: output keeps
// going to the zgate log file, and the shell's window is free to close.
//
// Handles we inherited (pipe / file) are left alone — detaching would break a
// caller that deliberately captured our output. A failed detach is harmless:
// the process keeps running, the console simply stays shared.
func DetachConsole() bool {
	if keepInheritedStdio() {
		return false
	}
	ok, _, _ := procFreeConsole.Call()
	return ok != 0
}

func keepInheritedStdio() bool {
	out, _, _ := procGetStdHandle.Call(stdOutputHandle)
	if out == 0 {
		return false
	}
	ft, _, _ := procGetFileType.Call(out)
	switch uintptr(ft) {
	case fileTypeDisk, fileTypePipe:
		return true
	default: // unknown (invalid) or char (console): try attaching instead
		return false
	}
}

var _ = syscall.Handle(0)
