# 🤖 Personal AI Employee — Silver Tier

> **Hackathon:** Personal AI Employee — Building Autonomous FTEs in 2026
> **Tier:** Silver (Functional Assistant)
> **Architecture:** Perception → Reasoning → Action → Orchestration
> **Status:** Production-ready
> **# BY (MERCHANTSONS) GIAIC ROLL # 00037391**

---

## Table of Contents

1. [What This Is](#what-this-is)
2. [Architecture Overview](#architecture-overview)
3. [Silver Tier Features](#silver-tier-features)
4. [Project Structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Quick Start (DEV_MODE)](#quick-start-devmode)
7. [Full Setup Guide](#full-setup-guide)
8. [Running the System](#running-the-system)
9. [Human-in-the-Loop Workflow](#human-in-the-loop-workflow)
10. [Scheduling (Task Scheduler)](#scheduling)
11. [MCP Server Configuration](#mcp-server-configuration)
12. [Agent Skills Reference](#agent-skills-reference)
13. [Security Architecture](#security-architecture)
14. [Credential Management](#credential-management)
15. [Troubleshooting](#troubleshooting)
16. [Upgrade Path](#upgrade-path)

---

## What This Is

A **local-first, privacy-preserving Personal AI Employee** that:

- **Monitors Gmail** for important emails and routes them as structured tasks
- **Drafts email responses** using Claude AI — never sends without your approval
- **Generates LinkedIn posts** to grow your business — never posts without approval
- **Watches LinkedIn** for sales opportunities and leads
- **Creates intelligent plans** using Claude reasoning enriched with your Company Handbook
- **Schedules proactively**: daily dashboard, weekly CEO briefing, LinkedIn content
- **Dispatches approved actions** via Email MCP server (SMTP)
- **Runs on Windows** with Task Scheduler for always-on operation

**Reasoning engine:** Claude Code (Claude API). All data stays local. No cloud services required. Human approval required for every external action.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SOURCES                            │
├──────────────────┬───────────────────┬───────────────────────────┤
│      Gmail       │    LinkedIn        │    File System (Inbox/)   │
└────────┬─────────┴────────┬──────────┴──────────────┬────────────┘
         │                  │                           │
         ▼                  ▼                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                      PERCEPTION LAYER                            │
│  gmail_watcher.py    linkedin_watcher.py    file_system_watcher.py│
│  (OAuth2 / DEV)      (API / Playwright)     (watchdog)           │
└────────────────────────────┬─────────────────────────────────────┘
                             │ .md action files
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    OBSIDIAN VAULT (Local)                        │
│  /Needs_Action/  /Plans/  /Done/  /Logs/  /Briefings/            │
│  Dashboard.md    Company_Handbook.md   Business_Goals.md         │
│  /Pending_Approval/  /Approved/  /Rejected/                      │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│              REASONING LAYER (Claude Code — Silver)               │
│  claude_agent.py                                                 │
│  LLMReasoner → TaskClassifier → PlanGenerator                    │
│  EmailDrafter → LinkedInContentGenerator → CEOBriefingGenerator  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
┌─────────────────────┐         ┌───────────────────────────┐
│  HUMAN-IN-THE-LOOP  │         │       ACTION LAYER        │
│  Review in Obsidian │──────▶  │  email_mcp_server.py      │
│  Move to /Approved/ │         │  linkedin_watcher.py      │
└─────────────────────┘         │  (SMTP / LinkedIn API)    │
                                └───────────────────────────┘
                             ▲
                             │ schedule + approval dispatch
┌────────────────────────────┴─────────────────────────────────────┐
│                    ORCHESTRATION LAYER                           │
│  orchestrator.py                                                 │
│  • Watches /Approved/ → dispatches actions                       │
│  • Daily 8 AM: Dashboard update                                  │
│  • Monday 7 AM: CEO Briefing                                     │
│  • Daily 9 AM: LinkedIn post generation                          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Silver Tier Features

### ✅ All Bronze Requirements
- Obsidian vault with Dashboard.md and Company_Handbook.md
- File system watcher (file_system_watcher.py)
- Claude agent reading/writing vault
- Basic folder structure
- All AI as Agent Skills

### ✅ Silver Additions (New in This Tier)

| Feature | Implementation | Status |
|---------|---------------|--------|
| **Gmail Watcher** | `gmail_watcher.py` | ✅ Complete |
| **LinkedIn Watcher** | `linkedin_watcher.py` | ✅ Complete |
| **Auto-post LinkedIn** | `LinkedInContentGenerator` | ✅ Complete (HITL) |
| **Claude Reasoning Loop** | `LLMReasoner` → Plan.md | ✅ Complete |
| **Email MCP Server** | `email_mcp_server.py` | ✅ Complete |
| **HITL Approval Workflow** | `Pending_Approval/` → `Approved/` | ✅ Complete |
| **Windows Task Scheduler** | `setup_task_scheduler.bat` | ✅ Complete |
| **CEO Briefing** | `CEOBriefingGenerator` | ✅ Complete |
| **Business_Goals.md** | Vault context document | ✅ Complete |
| **Orchestrator** | `orchestrator.py` | ✅ Complete |

---

## Project Structure

```
Hackathon-0-Silver/
│
├── watchers/
│   ├── file_system_watcher.py ← Perception: filesystem Inbox/ monitor
│   ├── gmail_watcher.py       ← Perception: Gmail email monitor (Silver)
│   └── linkedin_watcher.py   ← Perception + Action: LinkedIn monitor + poster
├── claude_agent.py         ← Reasoning + Action: LLM-powered task processor
├── email_mcp_server.py     ← Action: MCP email sending server (SMTP)
├── orchestrator.py         ← Orchestration: scheduler + approval dispatcher
│
├── requirements.txt        ← Python dependencies
├── .env.example            ← Environment variable template
│
├── setup.bat               ← One-time setup
├── setup_task_scheduler.bat← Windows Task Scheduler configuration
│
├── run_watcher.bat         ← Launch file system watcher
├── run_gmail_watcher.bat   ← Launch Gmail watcher
├── run_linkedin_watcher.bat← Launch LinkedIn watcher
├── run_agent.bat           ← Launch Claude agent (manual)
├── run_orchestrator.bat    ← Launch master orchestrator
├── run_rollback.bat        ← Roll back artifacts
│
└── AI_Employee_Vault/
    │
    ├── Dashboard.md            ← Live system dashboard (Silver metrics)
    ├── Company_Handbook.md     ← Rules of engagement (NEW)
    ├── Business_Goals.md       ← Q1 targets + LinkedIn content strategy (NEW)
    │
    ├── Inbox/                  ← Drop files here
    ├── Needs_Action/           ← Watcher routes files here
    ├── Done/                   ← Completed tasks
    │
    ├── Plans/                  ← Claude-generated execution plans
    ├── Pending_Approval/       ← Email drafts + LinkedIn posts awaiting review
    ├── Approved/               ← Human-approved items (Orchestrator dispatches)
    ├── Rejected/               ← Rejected items
    │
    ├── Briefings/              ← Weekly CEO Briefings (NEW)
    │
    ├── Logs/
    │   ├── activity.log
    │   ├── watcher.log
    │   ├── agent.log
    │   ├── gmail_watcher.log       ← Gmail watcher logs (NEW)
    │   ├── linkedin_watcher.log    ← LinkedIn watcher logs (NEW)
    │   ├── orchestrator.log        ← Orchestrator logs (NEW)
    │   ├── email_mcp.log           ← Email MCP server logs (NEW)
    │   ├── task_catalog.jsonl      ← Append-only audit trail
    │   ├── email_audit.jsonl       ← Email send audit (NEW)
    │   └── linkedin_posts.jsonl    ← LinkedIn post audit (NEW)
    │
    └── Skills/
        ├── INDEX.md                ← Skills registry (12 skills)
        ├── vault_reader.md
        ├── vault_writer.md
        ├── task_classifier.md
        ├── plan_generator.md
        ├── file_mover.md
        ├── action_processor.md
        ├── dashboard_updater.md
        ├── llm_reasoner.md         ← NEW (Silver)
        ├── email_sender.md         ← NEW (Silver)
        ├── gmail_monitor.md        ← NEW (Silver)
        ├── linkedin_poster.md      ← NEW (Silver)
        └── scheduler.md            ← NEW (Silver)
```

---

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.10+ | `python --version` |
| pip | any | `pip --version` |
| Obsidian | any | Optional (vault viewing) |

**For LLM reasoning (Claude Code):**
- Claude API key → [console.anthropic.com](https://console.anthropic.com) (use as `ANTHROPIC_API_KEY` in .env)

**For Gmail integration:**
- Google Cloud credentials.json → [console.cloud.google.com](https://console.cloud.google.com)

**For LinkedIn integration:**
- LinkedIn Developer App (Option A) or LinkedIn credentials (Option B)

---

## Quick Start (DEV_MODE)

**Zero configuration — no API keys needed!**

```batch
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment template
copy .env.example .env

# 3. Enable DEV_MODE (simulated APIs)
# Edit .env: set DEV_MODE=true

# 4. Start the Gmail watcher (simulated emails)
run_gmail_watcher.bat --dev

# 5. In another terminal: start the LinkedIn watcher
run_linkedin_watcher.bat --dev

# 6. In another terminal: start the orchestrator
run_orchestrator.bat

# 7. Watch the vault fill up with action items!
# Open AI_Employee_Vault/ in Obsidian to see Dashboard.md
```

In DEV_MODE:
- Gmail Watcher generates 5 realistic simulated emails
- LinkedIn Watcher generates 3 simulated notifications
- Orchestrator dispatches approvals (simulated)
- All LLM calls use template responses
- No external services are called

---

## Full Setup Guide

### Step 1 — Install Dependencies

```batch
pip install -r requirements.txt
playwright install chromium  # For LinkedIn browser automation
```

### Step 2 — Configure Environment

```batch
copy .env.example .env
```

Edit `.env`:

```env
# Claude Code / LLM Reasoning (get key from console.anthropic.com)
ANTHROPIC_API_KEY=sk-ant-...

# Gmail Integration
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_QUERY=is:unread is:important

# Email Sending (Gmail App Password)
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password_16chars

# LinkedIn Integration (Option A: API)
LINKEDIN_ACCESS_TOKEN=your_bearer_token
LINKEDIN_PERSON_URN=urn:li:person:YOUR_ID

# LinkedIn (Option B: Browser automation)
LINKEDIN_EMAIL=your@linkedin.com
LINKEDIN_PASSWORD=your_password

# Schedule
DAILY_BRIEFING_TIME=08:00
LINKEDIN_POST_TIME=09:00

# Safety
DRY_RUN=false
DEV_MODE=false
```

### Step 3 — Personalise the Vault

1. Open `AI_Employee_Vault/Company_Handbook.md`
   - Replace `[YOUR_COMPANY_NAME]` and `[YOUR_NAME]`
   - Add your known contacts to section 7
   - Adjust approval thresholds to your preferences

2. Open `AI_Employee_Vault/Business_Goals.md`
   - Update Q1 2026 revenue targets
   - Add your active projects
   - Customise LinkedIn content strategy

### Step 4 — Set Up Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable **Gmail API**
3. Create OAuth 2.0 credentials (Desktop App type)
4. Download as `credentials.json` to project root
5. First run: `run_gmail_watcher.bat` or `python watchers/gmail_watcher.py` (browser auth flow)

### Step 5 — Set Up Task Scheduler

```batch
# Run as Administrator
setup_task_scheduler.bat
```

### Step 6 — Open Obsidian

1. Open Obsidian → "Open folder as vault"
2. Select `AI_Employee_Vault/`
3. Set `Dashboard.md` as your home note

---

## Running the System

### Recommended: 3-Terminal Setup

**Terminal 1 — File System Watcher**
```batch
run_watcher.bat
```

**Terminal 2 — Gmail + LinkedIn Watchers** (now in `watchers/`, launched from project root)
```batch
run_gmail_watcher.bat --dev   # or without --dev for live Gmail
run_linkedin_watcher.bat --dev  # or without --dev for live LinkedIn
```

**Terminal 3 — Master Orchestrator**
```batch
run_orchestrator.bat
```

The Orchestrator handles:
- Processing items in `Approved/` automatically
- Daily Dashboard updates at 8:00 AM
- Weekly CEO Briefing every Monday at 7:00 AM
- LinkedIn post generation daily at 9:00 AM

### Manual Commands

```batch
# Process all pending tasks
python claude_agent.py

# Refresh Dashboard only
python claude_agent.py --update-dashboard

# Generate CEO Briefing
python claude_agent.py --briefing

# Generate LinkedIn post from Business_Goals
python claude_agent.py --linkedin-post

# Check orchestrator status
run_orchestrator.bat --status

# Force-dispatch all Approved/ items
run_orchestrator.bat --dispatch

# Test email connection
python email_mcp_server.py --test-connection --standalone

# Scan pending tasks
python claude_agent.py --scan
```

---

## Human-in-the-Loop Workflow

Every sensitive action follows this mandatory approval workflow:

```
AI generates draft/plan
    ↓
File written to Pending_Approval/
    ↓
You review in Obsidian
    ↓
    ├── Approve → move file to Approved/
    ├── Reject  → move file to Rejected/
    └── Modify  → edit the file, then move to Approved/
         ↓
Orchestrator detects Approved/ file
    ↓
Dispatches action (email send / LinkedIn post)
    ↓
Audit log entry written
    ↓
File moved to Done/
```

### What Always Requires Approval

- All outgoing emails (including auto-drafted replies)
- All LinkedIn posts (including scheduled ones)
- Any file classified as URGENT priority
- Any code files

### Dashboard Visibility

`Dashboard.md` always shows:
- Count of pending approvals
- Breakdown: N email drafts, N LinkedIn posts
- Table of specific files awaiting your decision

---

## Scheduling

### Windows Task Scheduler (run `setup_task_scheduler.bat` as Admin)

| Task | Schedule |
|------|----------|
| Orchestrator | On login (with 2-min delay) |
| Claude Agent | Every 5 minutes |
| Daily Briefing | 8:00 AM daily |
| Weekly CEO Briefing | Monday 7:00 AM |

### Orchestrator Built-in Schedule

```batch
run_orchestrator.bat
# Runs continuously, checking every 30 seconds
# Automatically fires daily/weekly tasks at configured times
```

---

## MCP Server Configuration

Add to `~/.claude/mcp.json` or `~/.config/claude-code/mcp.json`:

```json
{
  "servers": [
    {
      "name": "email",
      "command": "python",
      "args": ["D:/path/to/Hackathon-0-Silver/email_mcp_server.py"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your@gmail.com",
        "SMTP_PASSWORD": "your_app_password"
      }
    }
  ]
}
```

Claude Code can then use `send_email`, `draft_email`, `list_recent_emails`, and `check_connection` tools directly.

---

## Agent Skills Reference

| Skill | Class | Tier | Purpose |
|-------|-------|------|---------|
| LLM Reasoner | `LLMReasoner` | Silver | Claude API reasoning engine |
| Vault Reader | `VaultReader` | Bronze | Read vault files and directories |
| Vault Writer | `VaultWriter` | Bronze | Write vault files |
| Task Classifier | `TaskClassifier` | Silver | LLM-enhanced classification |
| Plan Generator | `PlanGenerator` | Silver | LLM-powered plan creation |
| Email Drafter | `EmailDrafter` | Silver | AI email draft generation |
| Email Sender | `EmailSender` (MCP) | Silver | SMTP email dispatch |
| LinkedIn Generator | `LinkedInContentGenerator` | Silver | AI LinkedIn post creation |
| File Mover | `FileMover` | Bronze | Safe copy-verify-delete moves |
| Action Processor | `ActionProcessor` | Silver | Full pipeline orchestration |
| Dashboard Updater | `DashboardUpdater` | Silver | Silver metrics dashboard |
| CEO Briefing | `CEOBriefingGenerator` | Silver | Executive summary generation |
| Scheduler | `OrchestratorState` | Silver | Time-based task triggering |

Full documentation: `AI_Employee_Vault/Skills/`

---

## Security Architecture

### Credential Management
- All secrets in `.env` (never committed to Git)
- Gmail OAuth token stored in `gmail_token.json` (add to `.gitignore`)
- LinkedIn session stored in `linkedin_session/` (add to `.gitignore`)
- SMTP uses App Passwords, not account passwords

### Permission Boundaries

| Action | Auto-Approve | Always Require Human |
|--------|-------------|---------------------|
| Email reply | Never | Always |
| LinkedIn post | Never | Always |
| File create in vault | Yes | — |
| File delete | Never | Always |
| Payment | Never | Always |

### Audit Logging

Every action is logged:
- `Logs/task_catalog.jsonl` — task processing log
- `Logs/email_audit.jsonl` — email send audit
- `Logs/linkedin_posts.jsonl` — LinkedIn post audit
- `Logs/dispatch_audit.jsonl` — orchestrator dispatch audit

All logs include: timestamp, action_type, actor, target, approval_status, result.
Retain for minimum 90 days.

### Rate Limits
- Email: maximum 10 sends per hour
- LinkedIn: maximum 1 post per day

---

## Credential Management

### .gitignore (already configured)
```gitignore
.env
credentials.json
gmail_token.json
linkedin_session/
*.pyc
__pycache__/
```

### Required .env Variables

```env
# Required for Claude Code reasoning
ANTHROPIC_API_KEY=

# Required for email sending
SMTP_USER=
SMTP_PASSWORD=

# Optional: Gmail monitoring
GMAIL_CREDENTIALS_PATH=credentials.json

# Optional: LinkedIn
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_PERSON_URN=

# Safety flags
DRY_RUN=false
DEV_MODE=false
```

---

## Troubleshooting

### "anthropic not installed" (Claude API SDK)
```batch
pip install anthropic
```

### LLM not working (using rule-based mode)
- Check Claude API key is set in `.env` as `ANTHROPIC_API_KEY`
- Run: `python -c "import anthropic; print('OK')"`
- Check `AI_Employee_Vault/Logs/agent.log` for API errors

### Gmail 403 Forbidden
- Enable Gmail API in Google Cloud Console
- Check OAuth consent screen is configured
- Delete `gmail_token.json` and re-authenticate

### LinkedIn posting fails
- Option A: Check `LINKEDIN_ACCESS_TOKEN` is valid (tokens expire)
- Option B: Run once headlessly to complete 2FA setup
- Use `DEV_MODE=true` for demos

### Email not sending
```batch
python email_mcp_server.py --test-connection --standalone
```
- Check SMTP_PASSWORD is the App Password (not account password)
- Ensure 2-Step Verification is enabled on Gmail
- Check firewall allows port 587

### Orchestrator not dispatching approvals
```batch
run_orchestrator.bat --status
```
- Verify files are in `Approved/` (not `Pending_Approval/`)
- Check `Logs/orchestrator.log` for errors
- Try: `run_orchestrator.bat --dispatch`

### Watcher stops running overnight
- Use `setup_task_scheduler.bat` to create auto-restart tasks
- Check Windows Event Viewer for scheduler errors

---

## Upgrade Path

### Silver → Gold
1. Implement Ralph Wiggum continuous loop `[RW_HOOK]`
2. Add Odoo Community accounting integration via MCP
3. Add Facebook/Instagram post support
4. Add Twitter/X integration
5. Full cross-domain integration (Personal + Business)
6. Error recovery and graceful degradation with automatic restart
7. Comprehensive audit logging with 90-day retention enforcement

### Gold → Platinum
1. Deploy on Oracle Cloud VM (24/7 always-on)
2. Cloud/Local agent separation with vault sync
3. A2A messaging protocol
4. Self-improving skill library

---

## Safety Checklist

Before deploying live:
- [ ] Tested with `DEV_MODE=true` — full demo flow works
- [ ] Tested with `DRY_RUN=true` — no unintended writes
- [ ] `.env` created with all required keys
- [ ] `credentials.json` and `gmail_token.json` in `.gitignore`
- [ ] `Company_Handbook.md` personalised with your rules
- [ ] `Business_Goals.md` updated with your actual goals
- [ ] Email SMTP tested: `python email_mcp_server.py --test-connection`
- [ ] At least one full HITL cycle tested (approve an email draft)
- [ ] Dashboard.md rendering correctly in Obsidian

---

*AI Employee — Silver Tier | Personal AI Employee Hackathon 2026*
*Architecture: Perception → Reasoning → Action → Orchestration*
*Local-first | Privacy-preserving | Human-in-the-loop*
*BY (MERCHANTSONS) GIAIC ROLL # 00037391*
