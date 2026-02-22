# Skill: Email Sender

**Class:** `EmailDrafter` + `EmailSender` (MCP)
**Tier:** Silver
**Files:** `claude_agent.py`, `email_mcp_server.py`
**Introduced in:** v2.0.0

---

## Purpose

Two-stage email capability:

1. **Draft** — `EmailDrafter` generates AI-written reply drafts and places
   them in `Pending_Approval/` for human review.

2. **Send** — After human approval, `EmailSender` (via `email_mcp_server.py`)
   sends the email via SMTP with full audit logging.

This separation enforces the Human-in-the-Loop safety pattern for all outgoing
communications.

---

## Stage 1: Draft (claude_agent.py)

```python
# Generate email draft from a task dict containing email context
approval_path: Path = EmailDrafter.draft_response(task)
# → Writes to Pending_Approval/TIMESTAMP_email_reply_STEM.md
```

### Draft file format

```markdown
---
type: approval_request
action: send_email
to: "sender@example.com"
subject: "Re: Original Subject"
---
## Proposed Reply
> [AI-generated reply body here]

Move to Approved/ to send, Rejected/ to discard.
```

---

## Stage 2: Send (email_mcp_server.py)

The Orchestrator reads approved email files and calls:

```python
from email_mcp_server import EmailSender
result = EmailSender.send(to=..., subject=..., body=...)
```

### MCP tool call (from Claude Code)

```json
{
  "tool": "send_email",
  "arguments": {
    "to": "client@example.com",
    "subject": "Re: Invoice Request",
    "body": "Thank you for your message..."
  }
}
```

---

## SMTP Setup (Gmail)

1. Google Account → Security → 2-Step Verification → App Passwords
2. Generate a "Mail" app password (16 characters)
3. Add to `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password
```

---

## Security Controls

| Control | Value |
|---------|-------|
| New recipients | Always require approval |
| Rate limit | 10 emails / hour |
| Bulk sends | Blocked (max 1 recipient) |
| Audit log | `Logs/email_audit.jsonl` |
| DRY_RUN | Logs without sending |
| DEV_MODE | Simulates SMTP call |

---

## Approval Workflow

```
Email arrives (Gmail Watcher)
    ↓
claude_agent.py classifies as parse_and_respond
    ↓
EmailDrafter generates draft → Pending_Approval/
    ↓
Human reviews draft in Obsidian
    ↓
Move to Approved/ (send) or Rejected/ (discard)
    ↓
Orchestrator detects Approved/ file
    ↓
EmailSender.send() via SMTP
    ↓
Audit log → Logs/email_audit.jsonl
    ↓
File moved to Done/
```

---

*Email Sender Skill — Silver Tier | AI Employee v2.0.0*
