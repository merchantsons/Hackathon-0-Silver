@echo off
REM ============================================================
REM  AI Employee — Gmail Watcher Launcher (Windows)
REM  Silver Tier
REM ============================================================
REM  Usage:
REM    run_gmail_watcher.bat          Start Gmail watcher (live mode)
REM    run_gmail_watcher.bat --dev    DEV_MODE: simulated emails (no Gmail needed)
REM    run_gmail_watcher.bat --dry    DRY_RUN: log only, no file writes
REM ============================================================

cd /d "%~dp0"

IF "%1"=="--dev" (
    echo [INFO] Starting Gmail Watcher in DEV_MODE ^(simulated emails^)...
    set DEV_MODE=true
    python watchers\gmail_watcher.py
) ELSE IF "%1"=="--dry" (
    echo [INFO] Starting Gmail Watcher in DRY_RUN mode...
    set DRY_RUN=true
    python watchers\gmail_watcher.py
) ELSE (
    echo [INFO] Starting Gmail Watcher in LIVE mode...
    echo [INFO] Requires: credentials.json in project root
    echo [INFO] Set DEV_MODE=true in .env for offline testing
    python watchers\gmail_watcher.py
)

IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Gmail Watcher exited with error. Check AI_Employee_Vault\Logs\gmail_watcher.log
    pause
)
