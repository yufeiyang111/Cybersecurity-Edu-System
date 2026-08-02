@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "BACKEND_DIR=%CD%\backend"
set "FRONTEND_DIR=%CD%\frontend"
set "PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"

echo ============================================================
echo   CyberGuard Dev Launcher
echo ============================================================
echo.

REM ---------- Check MySQL service ----------
echo [1/3] Checking MySQL service...
set "MYSQL_OK="
for %%S in (MySQL80 MySQL MySQL57) do (
    sc query "%%S" 2>nul | findstr /i "RUNNING" >nul && set "MYSQL_OK=1" && set "MYSQL_NAME=%%S"
)
if defined MYSQL_OK (
    echo        [OK] MySQL service !MYSQL_NAME! is running
) else (
    echo        [WARN] No running MySQL service detected. Backend may fail to connect.
    echo        Please make sure MySQL is started, otherwise /api/health will fail.
)
echo.

REM ---------- Check backend environment ----------
echo [2/3] Checking backend environment...
if not exist "%PYTHON%" (
    echo        [ERROR] Backend venv not found: %PYTHON%
    echo        Please run: backend\venv.bat i
    pause
    exit /b 1
)
echo        [OK] Python venv ready
if not exist "%BACKEND_DIR%\.env" (
    echo        [HINT] backend\.env not found. Using defaults - copy .env.example if needed.
) else (
    echo        [OK] .env config exists
)
echo.

REM ---------- Check frontend dependencies ----------
echo [3/3] Checking frontend environment...
if not exist "%FRONTEND_DIR%\node_modules" (
    echo        [ERROR] node_modules not found in frontend
    echo        Please run: npm --prefix frontend install
    pause
    exit /b 1
)
echo        [OK] Frontend dependencies ready
echo.

echo ============================================================
echo   Starting services:
echo     - Backend API  http://localhost:5001  (python run.py)
echo     - Frontend     http://localhost:5173  (npm run dev)
echo   Close the corresponding window to stop that service.
echo ============================================================
echo.

REM ---------- Start backend ----------
start "CyberGuard Backend :5001" /D "%BACKEND_DIR%" cmd /k ""!PYTHON!" run.py"

REM ---------- Start frontend ----------
start "CyberGuard Frontend :5173" /D "%FRONTEND_DIR%" cmd /k "npm run dev"

echo Services starting... Frontend will be ready at http://localhost:5173
echo Backend health check: http://localhost:5001/api/health
echo.
pause
