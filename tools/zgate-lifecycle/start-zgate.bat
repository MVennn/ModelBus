@echo off
REM Compatibility wrapper. Never Start-Process here (session job object reaps it).
schtasks /run /tn "ModelBus-zgate-hidden"
exit /b %ERRORLEVEL%
