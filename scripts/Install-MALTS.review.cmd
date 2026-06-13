@echo off
setlocal
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-MALTS.ps1" %*
echo.
echo Review completed. If the command above was a dry run, no files were changed.
pause
