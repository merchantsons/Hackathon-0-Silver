@echo off
REM ============================================================
REM  AI Employee — LinkedIn Watcher Launcher (Windows)
REM  Silver Tier
REM ============================================================
REM  Usage:
REM    run_linkedin_watcher.bat          Start LinkedIn watcher (live mode)
REM    run_linkedin_watcher.bat --dev    DEV_MODE: simulated (no LinkedIn needed)
REM    run_linkedin_watcher.bat --dry    DRY_RUN: log only, no posts published
REM
REM  For real LinkedIn, configure in .env:
REM    Option A (API):
REM      LINKEDIN_ACCESS_TOKEN=...
REM      LINKEDIN_PERSON_URN=...
REM    Option B (Browser):
REM      LINKEDIN_EMAIL=your@email.com
REM      LINKEDIN_PASSWORD=yourpassword
REM ============================================================

cd /d "%~dp0"

IF "%1"=="--dev" (
    echo [INFO] Starting LinkedIn Watcher in DEV_MODE ^(simulated^)...
    set DEV_MODE=true
    python watchers\linkedin_watcher.py
) ELSE IF "%1"=="--dry" (
    echo [INFO] Starting LinkedIn Watcher in DRY_RUN mode...
    set DRY_RUN=true
    python watchers\linkedin_watcher.py
) ELSE (
    echo [INFO] Starting LinkedIn Watcher in LIVE mode...
    echo [INFO] Configure LINKEDIN_ACCESS_TOKEN or LINKEDIN_EMAIL in .env
    echo [INFO] Set DEV_MODE=true in .env for offline testing
    python watchers\linkedin_watcher.py
)

IF ERRORLEVEL 1 (
    echo.
    echo [ERROR] LinkedIn Watcher exited with error. Check AI_Employee_Vault\Logs\linkedin_watcher.log
    pause
)
