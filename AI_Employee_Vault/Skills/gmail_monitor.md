# Skill: Gmail Monitor

**Class:** `GmailWatcher` / `GmailClient`
**Tier:** Silver
**File:** `gmail_watcher.py`
**Introduced in:** v2.0.0

---

## Purpose

Continuously monitors Gmail for important unread emails and routes them as
action files to `Needs_Action/` for the Claude Agent to process.

Transforms incoming email into structured Markdown task cards, ready for
AI classification and response drafting.

---

## Architecture

```
Gmail API (or DEV_MODE simulation)
    ↓
GmailWatcher polls every 120s
    ↓
New important unread email detected
    ↓
Creates: Needs_Action/TIMESTAMP_EMAIL_SUBJECT.md
    ↓
claude_agent.py classifies as "parse_and_respond"
    ↓
EmailDrafter generates reply draft
    ↓
Human approves → Orchestrator sends via SMTP
```

---

## Output File Format

Each email creates a structured action file:

```markdown
---
type: email
source: gmail
email_id: "MSG_ID"
from: "sender@example.com"
subject: "Subject line"
priority: high
status: pending
---
# Email: Subject line
## Headers ...
## Email Content
[Snippet of email body]
## Suggested Actions
- [ ] Read full email
- [ ] Draft reply via EmailDrafter
- [ ] Send after approval
```

---

## Priority Detection

| Keyword in subject | Assigned Priority |
|-------------------|------------------|
| urgent, asap, invoice, payment | HIGH |
| (default) | MEDIUM |

---

## Setup: Gmail API

### Step 1: Enable Gmail API
1. [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable "Gmail API"
3. APIs & Services → Credentials → Create OAuth 2.0 Client ID (Desktop app)
4. Download as `credentials.json` → place in project root

### Step 2: First Run (browser auth)
```batch
python gmail_watcher.py
# Opens browser for Google login + permission grant
# Token saved to gmail_token.json for subsequent runs
```

### Step 3: Configure
```env
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=gmail_token.json
GMAIL_QUERY=is:unread is:important
GMAIL_POLL_INTERVAL=120
```

---

## DEV_MODE (no Gmail account needed)

```env
DEV_MODE=true
```

Generates 5 realistic simulated emails:
- Client invoice request
- Partnership proposal
- Payment confirmation
- Inbound lead
- Industry newsletter

Perfect for demos and testing.

---

## State Management

Processed email IDs are persisted in `Logs/gmail_processed_ids.json`.
This prevents reprocessing emails after watcher restarts.

---

## Running

```batch
# Live mode
run_gmail_watcher.bat

# DEV_MODE (simulated)
run_gmail_watcher.bat --dev

# DRY_RUN (no files written)
run_gmail_watcher.bat --dry
```

---

*Gmail Monitor Skill — Silver Tier | AI Employee v2.0.0*
