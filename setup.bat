@echo off
REM ============================================================
REM  AI Employee — One-Time Setup Script (Windows)
REM  Silver Tier
REM ============================================================
REM  Run this ONCE before first use.
REM  What it does:
REM    1. Checks Python version (3.10+ required)
REM    2. Installs all Silver-tier dependencies
REM    3. Creates .env from .env.example
REM    4. Verifies and creates full vault structure
REM    5. Runs a DRY_RUN agent pass to verify installation
REM    6. Checks for optional Silver-tier credentials
REM ============================================================

cd /d "%~dp0"
echo.
echo ============================================================
echo   AI Employee — Silver Tier Setup
echo ============================================================
echo.

REM ── Step 1: Check Python ─────────────────────────────────────
echo [1/6] Checking Python version...
python --version 2>NUL
IF ERRORLEVEL 1 (
    echo [ERROR] Python not found. Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
python -c "import sys; v=sys.version_info; exit(0 if v>=(3,10) else 1)" 2>NUL
IF ERRORLEVEL 1 (
    echo [ERROR] Python 3.10 or higher is required. Please upgrade Python.
    pause
    exit /b 1
)
echo       OK
echo.

REM ── Step 2: Install dependencies ────────────────────────────
echo [2/6] Installing Silver-tier dependencies...
pip install -r requirements.txt
IF ERRORLEVEL 1 (
    echo [ERROR] pip install failed. Check internet connection and try again.
    pause
    exit /b 1
)
echo.
echo       Installing Playwright browser (used by LinkedIn watcher)...
python -m playwright install chromium --with-deps 2>NUL
IF ERRORLEVEL 1 (
    echo       [WARN] Playwright install failed. LinkedIn browser fallback unavailable.
    echo             This is OK if you will use LinkedIn API tokens instead.
)
echo       OK
echo.

REM ── Step 3: Create .env ──────────────────────────────────────
echo [3/6] Configuring environment...
IF NOT EXIST ".env" (
    IF EXIST ".env.example" (
        copy ".env.example" ".env" >NUL
        echo       Created .env from .env.example
    ) ELSE (
        echo       [WARN] .env.example not found, creating minimal .env...
        echo DEV_MODE=true > .env
        echo DRY_RUN=false >> .env
        echo ANTHROPIC_API_KEY=sk-ant-REPLACE_ME >> .env
    )
    echo.
    echo   *** IMPORTANT ***
    echo   Edit .env and fill in your API keys before running:
    echo     - ANTHROPIC_API_KEY (Claude Code / Claude API key for LLM reasoning)
    echo     - SMTP_USER / SMTP_PASSWORD (for email sending)
    echo     - LINKEDIN_ACCESS_TOKEN / LINKEDIN_PERSON_URN (for LinkedIn posting)
    echo     - GMAIL credentials (for Gmail monitoring)
    echo.
) ELSE (
    echo       .env already exists — skipping.
)
echo.

REM ── Step 4: Create vault structure ──────────────────────────
echo [4/6] Creating vault structure...
python -c "
from pathlib import Path
dirs = [
    'AI_Employee_Vault/Inbox',
    'AI_Employee_Vault/Needs_Action',
    'AI_Employee_Vault/Done',
    'AI_Employee_Vault/Plans',
    'AI_Employee_Vault/Pending_Approval',
    'AI_Employee_Vault/Approved',
    'AI_Employee_Vault/Rejected',
    'AI_Employee_Vault/Logs',
    'AI_Employee_Vault/Skills',
    'AI_Employee_Vault/Briefings',
]
for d in dirs:
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    print(f'  OK: {d}')
print()
print('  Vault structure ready.')
"
echo.

REM ── Step 5: Dry-run verification ────────────────────────────
echo [5/6] Running DRY_RUN verification pass...
set DRY_RUN=true
set DEV_MODE=true
python claude_agent.py --update-dashboard
IF ERRORLEVEL 1 (
    echo [ERROR] Agent dry-run failed. Check your Claude API key in .env
    echo         (DEV_MODE=true allows running without a valid key)
    pause
    exit /b 1
)
echo       Dashboard.md generated successfully.
echo.

REM ── Step 6: Summary ─────────────────────────────────────────
echo [6/6] Silver-tier component status:
echo.
python -c "
from pathlib import Path
import os

checks = [
    ('.env',                        'Environment config'),
    ('claude_agent.py',             'AI Agent (LLM reasoning)'),
    ('email_mcp_server.py',         'Email MCP Server'),
    ('orchestrator.py',             'Master Orchestrator'),
    ('watchers/file_system_watcher.py', 'File System Watcher'),
    ('watchers/gmail_watcher.py',   'Gmail Watcher'),
    ('watchers/linkedin_watcher.py','LinkedIn Watcher'),
    ('AI_Employee_Vault/Company_Handbook.md', 'Company Handbook'),
    ('AI_Employee_Vault/Business_Goals.md',   'Business Goals'),
    ('AI_Employee_Vault/Skills',              'Agent Skills'),
]
all_ok = True
for path, label in checks:
    p = Path(path)
    ok = p.exists()
    status = 'OK' if ok else 'MISSING'
    marker = '' if ok else ' <-- ACTION REQUIRED'
    print(f'  [{status:7s}] {label}{marker}')
    if not ok:
        all_ok = False
print()
if all_ok:
    print('  All Silver-tier components present!')
else:
    print('  Some components missing — check above.')
"
echo.
echo ============================================================
echo   Setup Complete — Silver Tier
echo ============================================================
echo.
echo   Quick-start commands:
echo     run_watcher.bat           — File system watcher (always-on)
echo     run_gmail_watcher.bat     — Gmail monitor (always-on)
echo     run_linkedin_watcher.bat  — LinkedIn poster (always-on)
echo     run_orchestrator.bat      — Master orchestrator (recommended)
echo.
echo   For Task Scheduler (always-on on Windows startup):
echo     setup_task_scheduler.bat
echo.
echo   For demo / testing (with DEV_MODE simulation):
echo     set DEV_MODE=true
echo     python claude_agent.py --update-dashboard
echo     python claude_agent.py --generate-briefing
echo     python claude_agent.py --linkedin-post
echo.
echo   Documentation: README.md
echo.
pause
