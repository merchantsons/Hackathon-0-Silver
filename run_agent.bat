@echo off
REM ============================================================
REM  AI Employee — Claude Agent Launcher (Windows)
REM  Bronze Tier
REM ============================================================
REM  Usage:
REM    run_agent.bat                 Process all pending tasks
REM    run_agent.bat --dry           Dry-run (simulate only)
REM    run_agent.bat --dashboard     Refresh dashboard only
REM    run_agent.bat --scan          List pending tasks
REM ============================================================

cd /d "%~dp0"

IF "%1"=="--dry" (
    echo [INFO] Running Claude Agent in DRY-RUN mode...
    python claude_agent.py --dry-run
) ELSE IF "%1"=="--dashboard" (
    echo [INFO] Refreshing Dashboard.md only...
    python claude_agent.py --update-dashboard
) ELSE IF "%1"=="--scan" (
    echo [INFO] Scanning Needs_Action/...
    python claude_agent.py --scan
) ELSE (
    echo [INFO] Running Claude Agent in LIVE mode...
    python claude_agent.py
)

IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Agent exited with error. Check logs above.
    pause
)
