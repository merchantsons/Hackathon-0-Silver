@echo off
REM ============================================================
REM  AI Employee — Vault Watcher Launcher (Windows)
REM  Bronze Tier
REM ============================================================
REM  Usage:
REM    run_watcher.bat          Normal mode
REM    run_watcher.bat --dry    Dry-run (simulate only)
REM ============================================================

cd /d "%~dp0"

IF "%1"=="--dry" (
    echo [INFO] Starting VaultWatcher in DRY-RUN mode...
    set DRY_RUN=true
) ELSE (
    echo [INFO] Starting VaultWatcher in LIVE mode...
    set DRY_RUN=false
)

echo [INFO] Vault Root : %~dp0AI_Employee_Vault
echo [INFO] Watching   : %~dp0AI_Employee_Vault\Inbox
echo [INFO] Logs       : %~dp0AI_Employee_Vault\Logs\watcher.log
echo [INFO] Press Ctrl+C to stop safely.
echo.

python watchers\file_system_watcher.py

IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Watcher exited with error. Check logs above.
    echo [HINT]  If "watchdog not found": run  pip install -r requirements.txt
    pause
)
