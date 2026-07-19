@echo off
REM CyberGuard Virtual Environment Manager
REM Usage: venv              - Show venv status
REM        venv i           - Install dependencies (create venv if needed)
REM        venv a           - Activate virtual environment
REM        venv d           - Deactivate virtual environment
REM        venv r <cmd>     - Run command in venv
REM        venv p           - Run Python interpreter
REM        venv pi <args>   - Run pip

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%venv"
set "VENV_SCRIPTS=%VENV_DIR%\Scripts"

REM Get command
set "COMMAND=%1"

if "%COMMAND%"=="" (
    if exist "%VENV_DIR%" (
        echo [OK] Virtual environment exists at: %VENV_DIR%
    ) else (
        echo [NOT FOUND] Run 'venv i' to create virtual environment.
    )
    echo.
    echo Commands:
    echo   venv i    - Install dependencies (create venv if needed)
    echo   venv a    - Activate virtual environment
    echo   venv d    - Deactivate virtual environment
    echo   venv r    - Run command in venv
    echo   venv p    - Run Python interpreter
    echo   venv pi   - Run pip
    echo   venv h    - Show help
    goto :end
)

if "%COMMAND%"=="i" (
    if not exist "%VENV_DIR%" (
        echo Creating virtual environment...
        python -m venv "%VENV_DIR%"
    )
    echo Installing dependencies...
    call "%VENV_SCRIPTS%\pip.exe" install -r "%SCRIPT_DIR%requirements.txt"
    goto :end
)

if "%COMMAND%"=="a" (
    if not exist "%VENV_DIR%" (
        echo Creating virtual environment...
        python -m venv "%VENV_DIR%"
    )
    call "%VENV_SCRIPTS%\activate.bat"
    echo Virtual environment activated!
    goto :end
)

if "%COMMAND%"=="d" (
    call "%VENV_SCRIPTS%\deactivate.bat" 2>nul || echo Not in virtual environment.
    goto :end
)

if "%COMMAND%"=="r" (
    if not exist "%VENV_DIR%" (
        echo Virtual environment not found. Creating...
        python -m venv "%VENV_DIR%"
    )
    if "%2"=="" (
        echo Usage: venv r ^<command^>
        goto :end
    )
    shift
    call "%VENV_SCRIPTS%\python.exe" %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if "%COMMAND%"=="p" (
    if not exist "%VENV_DIR%" (
        echo Virtual environment not found. Creating...
        python -m venv "%VENV_DIR%"
    )
    call "%VENV_SCRIPTS%\python.exe" %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if "%COMMAND%"=="pi" (
    if not exist "%VENV_DIR%" (
        echo Virtual environment not found. Creating...
        python -m venv "%VENV_DIR%"
    )
    call "%VENV_SCRIPTS%\pip.exe" %2 %3 %4 %5 %6 %7 %8 %9
    goto :end
)

if "%COMMAND%"=="h" (
    echo CyberGuard Virtual Environment Manager
    echo.
    echo Commands:
    echo   venv     - Show venv status
    echo   venv i   - Install dependencies from requirements.txt
    echo   venv a   - Activate the virtual environment
    echo   venv d   - Deactivate the virtual environment
    echo   venv r   - Run a command in the virtual environment
    echo   venv p   - Run Python interpreter
    echo   venv pi  - Run pip
    echo   venv h   - Show this help
    goto :end
)

echo Unknown command: %COMMAND%
echo Type "venv h" for usage information.

:end
endlocal
