# CyberGuard Virtual Environment Manager
# Usage: venv              - Show venv status
#        venv i           - Install dependencies (create venv if needed)
#        venv a           - Activate virtual environment
#        venv d           - Deactivate virtual environment
#        venv r <cmd>    - Run command in venv
#        venv p           - Run Python interpreter
#        venv pi <args>  - Run pip

param(
    [string]$Command,
    [string[]]$Args
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ScriptDir "venv"
$VenvScripts = Join-Path $VenvDir "Scripts"

function Show-Help {
    Write-Host "CyberGuard Virtual Environment Manager"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  venv     - Show venv status"
    Write-Host "  venv i   - Install dependencies from requirements.txt"
    Write-Host "  venv a   - Activate the virtual environment"
    Write-Host "  venv d   - Deactivate the virtual environment"
    Write-Host "  venv r   - Run a command in the virtual environment"
    Write-Host "  venv p   - Run Python interpreter"
    Write-Host "  venv pi  - Run pip"
    Write-Host "  venv h   - Show this help"
}

if ($Command -eq "" -or $Command -eq "h") {
    if ($Command -eq "h") { Show-Help; return }

    # Show status
    if (Test-Path $VenvDir) {
        Write-Host "[OK] Virtual environment exists at: $VenvDir" -ForegroundColor Green
    } else {
        Write-Host "[NOT FOUND] Run 'venv i' to create virtual environment." -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Commands: venv i|a|d|r|p|pi|h"
    return
}

switch ($Command) {
    "i" {
        if (-not (Test-Path $VenvDir)) {
            Write-Host "Creating virtual environment..." -ForegroundColor Yellow
            python -m venv $VenvDir
        }
        Write-Host "Installing dependencies..." -ForegroundColor Yellow
        & (Join-Path $VenvScripts "pip.exe") install -r (Join-Path $ScriptDir "requirements.txt")
        Write-Host "Done!" -ForegroundColor Green
    }

    "a" {
        if (-not (Test-Path $VenvDir)) {
            Write-Host "Creating virtual environment..." -ForegroundColor Yellow
            python -m venv $VenvDir
        }
        & (Join-Path $VenvScripts "Activate.ps1")
    }

    "d" {
        if (Test-Path function:deactivate) {
            deactivate
            Write-Host "Virtual environment deactivated." -ForegroundColor Green
        } else {
            Write-Host "Not in a virtual environment." -ForegroundColor Yellow
        }
    }

    "r" {
        if (-not (Test-Path $VenvDir)) {
            Write-Host "Creating virtual environment..." -ForegroundColor Yellow
            python -m venv $VenvDir
        }
        if ($Args.Count -eq 0) {
            Write-Host "Usage: venv r <command>" -ForegroundColor Red
            return
        }
        $cmd = $Args -join " "
        Write-Host "Running: $cmd" -ForegroundColor Cyan
        Invoke-Expression "& '$(Join-Path $VenvScripts 'python.exe')' $cmd"
    }

    "p" {
        if (-not (Test-Path $VenvDir)) {
            Write-Host "Creating virtual environment..." -ForegroundColor Yellow
            python -m venv $VenvDir
        }
        $pythonArgs = $Args -join " "
        if ($pythonArgs) {
            Invoke-Expression "& '$(Join-Path $VenvScripts 'python.exe')' $pythonArgs"
        } else {
            & (Join-Path $VenvScripts "python.exe")
        }
    }

    "pi" {
        if (-not (Test-Path $VenvDir)) {
            Write-Host "Creating virtual environment..." -ForegroundColor Yellow
            python -m venv $VenvDir
        }
        $pipArgs = $Args -join " "
        if ($pipArgs) {
            Invoke-Expression "& '$(Join-Path $VenvScripts 'pip.exe')' $pipArgs"
        } else {
            & (Join-Path $VenvScripts "pip.exe")
        }
    }

    default {
        Write-Host "Unknown command: $Command" -ForegroundColor Red
        Write-Host "Type 'venv h' for usage information."
    }
}
