@echo off
REM ============================================================
REM  AI Employee — Windows Task Scheduler Setup (Silver Tier)
REM  Creates scheduled tasks for autonomous operation
REM ============================================================
REM  Run as Administrator for Task Scheduler access
REM  Usage: setup_task_scheduler.bat
REM ============================================================

cd /d "%~dp0"
set PROJECT_DIR=%~dp0

echo ============================================================
echo  AI Employee Silver Tier — Task Scheduler Setup
echo ============================================================
echo.

REM ── 1. Orchestrator: Start on login ────────────────────────
echo [1/4] Creating Orchestrator startup task...
schtasks /create /tn "AIEmployee\Orchestrator" ^
    /tr "\"%PROJECT_DIR%run_orchestrator.bat\"" ^
    /sc onlogon ^
    /delay 0002:00 ^
    /ru "%USERNAME%" ^
    /f

IF ERRORLEVEL 1 (
    echo [WARN] Orchestrator task creation failed. Continuing...
) ELSE (
    echo [OK] Orchestrator task created (starts 2 min after login)
)

REM ── 2. Claude Agent: Every 5 minutes ───────────────────────
echo.
echo [2/4] Creating Claude Agent periodic task (every 5 min)...
schtasks /create /tn "AIEmployee\ClaudeAgent" ^
    /tr "python \"%PROJECT_DIR%claude_agent.py\"" ^
    /sc minute /mo 5 ^
    /ru "%USERNAME%" ^
    /f

IF ERRORLEVEL 1 (
    echo [WARN] Claude Agent task creation failed. Continuing...
) ELSE (
    echo [OK] Claude Agent task created (runs every 5 minutes)
)

REM ── 3. Daily CEO Briefing: 8:00 AM ─────────────────────────
echo.
echo [3/4] Creating Daily Briefing task (8:00 AM)...
schtasks /create /tn "AIEmployee\DailyBriefing" ^
    /tr "python \"%PROJECT_DIR%claude_agent.py\" --update-dashboard" ^
    /sc daily /st 08:00 ^
    /ru "%USERNAME%" ^
    /f

IF ERRORLEVEL 1 (
    echo [WARN] Daily Briefing task creation failed. Continuing...
) ELSE (
    echo [OK] Daily Briefing task created (8:00 AM daily)
)

REM ── 4. Weekly CEO Briefing: Monday 7:00 AM ─────────────────
echo.
echo [4/4] Creating Weekly CEO Briefing task (Monday 7:00 AM)...
schtasks /create /tn "AIEmployee\WeeklyBriefing" ^
    /tr "python \"%PROJECT_DIR%claude_agent.py\" --briefing" ^
    /sc weekly /d MON /st 07:00 ^
    /ru "%USERNAME%" ^
    /f

IF ERRORLEVEL 1 (
    echo [WARN] Weekly Briefing task creation failed. Continuing...
) ELSE (
    echo [OK] Weekly CEO Briefing task created (Monday 7:00 AM)
)

echo.
echo ============================================================
echo  Task Scheduler setup complete!
echo ============================================================
echo.
echo Tasks created under: AIEmployee\ folder in Task Scheduler
echo Manage via: Start ^> Task Scheduler ^> Task Scheduler Library ^> AIEmployee
echo.
echo To view tasks:
echo   schtasks /query /tn "AIEmployee" /fo LIST
echo.
echo To remove all tasks:
echo   schtasks /delete /tn "AIEmployee\Orchestrator"  /f
echo   schtasks /delete /tn "AIEmployee\ClaudeAgent"   /f
echo   schtasks /delete /tn "AIEmployee\DailyBriefing" /f
echo   schtasks /delete /tn "AIEmployee\WeeklyBriefing"/f
echo.
pause
