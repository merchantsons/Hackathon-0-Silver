@echo off
REM ============================================================
REM  AI Employee — Master Orchestrator Launcher (Windows)
REM  Silver Tier
REM ============================================================
REM  Usage:
REM    run_orchestrator.bat             Start orchestrator (continuous)
REM    run_orchestrator.bat --status    Print status and exit
REM    run_orchestrator.bat --dispatch  Force-dispatch Approved/ items
REM    run_orchestrator.bat --briefing  Generate CEO Briefing now
REM    run_orchestrator.bat --dry       DRY_RUN mode
REM ============================================================

cd /d "%~dp0"

IF "%1"=="--status" (
    echo [INFO] Checking system status...
    python orchestrator.py --status
    pause
    goto :EOF
)

IF "%1"=="--dispatch" (
    echo [INFO] Dispatching approved items...
    python orchestrator.py --dispatch-now
    pause
    goto :EOF
)

IF "%1"=="--briefing" (
    echo [INFO] Generating CEO Briefing...
    python orchestrator.py --briefing
    pause
    goto :EOF
)

IF "%1"=="--dry" (
    echo [INFO] Starting Orchestrator in DRY_RUN mode...
    set DRY_RUN=true
    python orchestrator.py
    goto :end
)

echo [INFO] Starting Master Orchestrator (Silver Tier)...
echo [INFO] Schedule:
echo   - Daily briefing: %DAILY_BRIEFING_TIME%
echo   - Weekly CEO briefing: Monday 07:00
echo   - LinkedIn post generation: %LINKEDIN_POST_TIME%
echo.
echo [INFO] The orchestrator monitors:
echo   - Approved\     for human-approved actions to dispatch
echo   - Needs_Action\ for tasks to trigger Claude Agent
echo.
python orchestrator.py

:end
IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] Orchestrator exited with error. Check AI_Employee_Vault\Logs\orchestrator.log
    pause
)
