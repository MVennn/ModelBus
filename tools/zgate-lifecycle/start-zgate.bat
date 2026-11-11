@echo off
REM Compatibility wrapper. Never Start-Process here (session job object reaps it).
REM 2026-11-11: single-task design; ModelBus-zgate-hidden was merged into the watchdog.
schtasks /run /tn "ModelBus-zgate-watchdog" >nul 2>&1
if errorlevel 1 schtasks /run /tn "ModelBus-zgate-hidden"
exit /b %ERRORLEVEL%
