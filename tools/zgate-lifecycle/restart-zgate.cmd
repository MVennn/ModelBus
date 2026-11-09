@echo off
REM Restart zgate via Task Scheduler so it survives CMD / DSH shutdown.
REM Never use Start-Process here: the session job object would reap the gateway.
REM Usage: restart-zgate.cmd            (build candidate + swap)
REM        restart-zgate.cmd -SkipBuild (swap a candidate already built)
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy-zgate.ps1" %*
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
