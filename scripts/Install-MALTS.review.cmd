@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-MALTS.ps1" -Interactive %*
set "MALTS_EXIT=%ERRORLEVEL%"
echo.
if not "%MALTS_EXIT%"=="0" echo MALTS install review stopped with exit code %MALTS_EXIT%.
pause
exit /b %MALTS_EXIT%
