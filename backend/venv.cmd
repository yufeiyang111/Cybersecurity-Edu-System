@echo off
REM CyberGuard venv wrapper
REM Usage: venv              - Show venv status
REM        venv i           - Install dependencies
REM        venv a           - Activate virtual environment
REM        venv d           - Deactivate virtual environment
REM        venv r <cmd>    - Run command in venv
REM        venv p           - Run Python interpreter
REM        venv pi <args>  - Run pip
REM        venv h           - Show help

set "PROJECT_DIR=%~dp0"
call "%PROJECT_DIR%venv.bat" %*
