@echo off
setlocal
cd /d "%~dp0"

set "BACKEND_DIR=%CD%\backend"
set "FLASK=%BACKEND_DIR%\venv\Scripts\flask.exe"

if not exist "%FLASK%" (
    echo [ERROR] Backend venv not found: %FLASK%
    echo         Please run: backend\venv.bat i
    pause
    exit /b 1
)

echo ============================================================
echo   CyberGuard RQ Worker (scans + agent runs)
echo   Ensure backend\.env has RQ_ASYNC=true and Redis is running.
echo   Close this window to stop the worker.
echo ============================================================
echo.

"%FLASK%" --app run rq-worker
pause