@echo off
REM ============================================================
REM  AI Employee — Rollback Launcher (Windows)
REM  Bronze Tier
REM ============================================================
REM  Use when you deleted a file from Inbox/ and want to remove
REM  all related artifacts (Needs_Action, Done, Plans, Pending_Approval,
REM  task_catalog.jsonl). If the watcher is running, it does this
REM  automatically; use this .bat when the watcher was not running.
REM
REM  Usage:
REM    run_rollback.bat "quarterly_report.txt"
REM    run_rollback.bat "urgent_contract.txt"
REM
REM  Argument: exact name of the file you deleted from Inbox/
REM ============================================================

cd /d "%~dp0"

IF "%~1"=="" (
    echo [ERROR] Missing argument: Inbox filename.
    echo.
    echo Usage: run_rollback.bat "filename.ext"
    echo Example: run_rollback.bat "quarterly_report.txt"
    echo.
    pause
    exit /b 1
)

echo [INFO] Rolling back all artifacts for Inbox file: %~1
echo.
python -c "import sys; sys.path.insert(0, r'%~dp0watchers'); from file_system_watcher import rollback_for_deleted_inbox_file; rollback_for_deleted_inbox_file(r'%~1')"
IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Rollback failed. Check logs above.
    pause
    exit /b 1
)
echo.
echo [INFO] Rollback finished.
pause
