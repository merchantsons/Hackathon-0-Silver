"""
email_mcp_server.py — AI Employee Email MCP Server (Silver Tier)
=================================================================
A Model Context Protocol (MCP) server that exposes email-sending capabilities
to Claude Code and the orchestrator.

Available tools:
  send_email(to, subject, body)        — Send email via SMTP / Gmail API
  draft_email(to, subject, body)       — Save a draft (no send)
  list_recent_emails(count)            — List recent sent emails from audit log
  check_connection()                   — Verify SMTP/API connectivity

Transport: stdio (JSON-RPC 2.0 over stdin/stdout)
This means Claude Code can use it by adding it to ~/.claude/mcp.json

MCP Config (add to ~/.claude/mcp.json or use --mcp-config flag):
  {
    "servers": [{
      "name": "email",
      "command": "python",
      "args": ["C:/path/to/email_mcp_server.py"],
      "env": {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "your@gmail.com",
        "SMTP_PASSWORD": "your_app_password"
      }
    }]
  }

Environment:
  SMTP_HOST         SMTP server host (default: smtp.gmail.com)
  SMTP_PORT         SMTP server port (default: 587)
  SMTP_USER         SMTP username / Gmail address
  SMTP_PASSWORD     SMTP password / Gmail App Password
  EMAIL_FROM_NAME   Display name in From header (default: AI Employee)
  MAX_EMAILS_PER_HOUR  Rate limit (default: 10)
  DEV_MODE=true     Simulate sends without actual SMTP
  DRY_RUN=true      Log intended actions without executing

Gmail App Password Setup:
  1. Google Account → Security → 2-Step Verification → App Passwords
  2. Create "Mail" app password
  3. Use the 16-char password as SMTP_PASSWORD

Standalone usage (for testing):
  python email_mcp_server.py --test-send to@example.com "Subject" "Body"
  python email_mcp_server.py --test-connection
"""

import os
import sys
import json
import logging
import smtplib
import ssl
import argparse
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import deque

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

VAULT_ROOT = Path(__file__).parent / "AI_Employee_Vault"
LOGS_DIR   = VAULT_ROOT / "Logs"
LOG_FILE   = LOGS_DIR / "email_mcp.log"
AUDIT_FILE = LOGS_DIR / "email_audit.jsonl"

SMTP_HOST          = os.environ.get("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT          = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER          = os.environ.get("SMTP_USER",     "")
SMTP_PASSWORD      = os.environ.get("SMTP_PASSWORD", "")
FROM_NAME          = os.environ.get("EMAIL_FROM_NAME", "AI Employee")
MAX_PER_HOUR       = int(os.environ.get("MAX_EMAILS_PER_HOUR", "10"))

DRY_RUN  = os.environ.get("DRY_RUN",  "false").lower() in ("true", "1", "yes")
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() in ("true", "1", "yes")

SERVER_VERSION = "2.0.0"

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING (to file only — stdout is used for MCP JSON-RPC)
# ──────────────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# When running as MCP server, log to file only (stdout is JSON-RPC channel)
_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if "--test" in sys.argv or "--standalone" in sys.argv:
    _handlers.append(logging.StreamHandler(sys.stderr))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_handlers,
)
logger = logging.getLogger("EmailMCPServer")


# ──────────────────────────────────────────────────────────────────────────────
# RATE LIMITER
# ──────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """Sliding window rate limiter for email sends."""

    def __init__(self, max_per_hour: int):
        self._max = max_per_hour
        self._timestamps: deque = deque()

    def is_allowed(self) -> bool:
        now = datetime.now().timestamp()
        cutoff = now - 3600
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps) < self._max

    def record(self):
        self._timestamps.append(datetime.now().timestamp())

    def remaining(self) -> int:
        now = datetime.now().timestamp()
        cutoff = now - 3600
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return max(0, self._max - len(self._timestamps))


_rate_limiter = RateLimiter(MAX_PER_HOUR)


# ──────────────────────────────────────────────────────────────────────────────
# SMTP EMAIL SENDER
# ──────────────────────────────────────────────────────────────────────────────

class EmailSender:
    """Sends emails via SMTP with TLS (Gmail-compatible)."""

    @classmethod
    def send(cls, to: str, subject: str, body: str, html: bool = False) -> dict:
        """
        Send an email. Returns {"success": bool, "message": str}.
        """
        if not to or "@" not in to:
            return {"success": False, "message": f"Invalid recipient: {to}"}

        if DEV_MODE:
            logger.info(f"[DEV_MODE] Simulating email send to {to}: {subject}")
            cls._write_audit(to, subject, body, "simulated")
            return {"success": True, "message": f"[DEV_MODE] Email simulated to {to}"}

        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would send email to {to}: {subject}")
            return {"success": True, "message": f"[DRY_RUN] Email would be sent to {to}"}

        if not SMTP_USER or not SMTP_PASSWORD:
            return {
                "success": False,
                "message": "SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD.",
            }

        if not _rate_limiter.is_allowed():
            return {
                "success": False,
                "message": f"Rate limit exceeded. Max {MAX_PER_HOUR} emails/hour.",
            }

        try:
            msg = MIMEMultipart("alternative")
            msg["From"]    = f"{FROM_NAME} <{SMTP_USER}>"
            msg["To"]      = to
            msg["Subject"] = subject
            msg["X-AI-Employee"] = "silver-tier"

            if html:
                msg.attach(MIMEText(body, "html"))
            else:
                msg.attach(MIMEText(body, "plain"))

            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, to, msg.as_string())

            _rate_limiter.record()
            logger.info(f"✔ Email sent: {to} — {subject}")
            cls._write_audit(to, subject, body, "sent")
            return {"success": True, "message": f"Email sent to {to}"}

        except smtplib.SMTPAuthenticationError:
            msg = "SMTP authentication failed. For Gmail: use App Password, not your account password."
            logger.error(msg)
            return {"success": False, "message": msg}
        except smtplib.SMTPException as exc:
            logger.error(f"SMTP error: {exc}")
            return {"success": False, "message": f"SMTP error: {exc}"}
        except Exception as exc:
            logger.error(f"Send failed: {exc}")
            return {"success": False, "message": f"Send failed: {exc}"}

    @staticmethod
    def _write_audit(to: str, subject: str, body: str, status: str):
        """Append send record to audit log."""
        entry = {
            "timestamp" : datetime.now().isoformat(),
            "action"    : "email_send",
            "actor"     : "email_mcp_server",
            "to"        : to,
            "subject"   : subject,
            "body_chars": len(body),
            "status"    : status,
            "tier"      : "silver",
        }
        try:
            with open(AUDIT_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.warning(f"Audit write failed: {exc}")

    @classmethod
    def check_connection(cls) -> dict:
        """Verify SMTP connectivity."""
        if DEV_MODE:
            return {"success": True, "message": "[DEV_MODE] Connection simulated"}
        if not SMTP_USER or not SMTP_PASSWORD:
            return {"success": False, "message": "SMTP credentials not set"}
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(SMTP_USER, SMTP_PASSWORD)
            return {"success": True, "message": f"SMTP connection OK ({SMTP_HOST}:{SMTP_PORT})"}
        except Exception as exc:
            return {"success": False, "message": f"SMTP connection failed: {exc}"}

    @staticmethod
    def list_recent(count: int = 10) -> dict:
        """Return recent email audit entries."""
        if not AUDIT_FILE.exists():
            return {"success": True, "emails": [], "message": "No emails sent yet"}
        try:
            lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
            entries = []
            for line in reversed(lines[-count:]):
                try:
                    entries.append(json.loads(line))
                except Exception:
                    pass
            return {"success": True, "emails": entries, "count": len(entries)}
        except Exception as exc:
            return {"success": False, "message": f"Log read failed: {exc}"}

    @staticmethod
    def save_draft(to: str, subject: str, body: str) -> dict:
        """Save an email draft to the vault without sending."""
        drafts_dir = VAULT_ROOT / "Drafts"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_draft_to_{to.split('@')[0]}.md"
        content  = f"""---
type: email_draft
to: "{to}"
subject: "{subject}"
created: "{datetime.now().isoformat()}"
status: draft
---

# Email Draft

**To:** {to}
**Subject:** {subject}
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Body

{body}

---
*Saved by EmailMCPServer v{SERVER_VERSION}*
*Move to Pending_Approval/ and approve to send.*
"""
        try:
            (drafts_dir / filename).write_text(content, encoding="utf-8")
            return {"success": True, "message": f"Draft saved: {filename}", "path": str(drafts_dir / filename)}
        except Exception as exc:
            return {"success": False, "message": f"Draft save failed: {exc}"}


# ──────────────────────────────────────────────────────────────────────────────
# MCP JSON-RPC SERVER (stdio transport)
# ──────────────────────────────────────────────────────────────────────────────

MCP_TOOLS = {
    "send_email": {
        "description": "Send an email via SMTP. Requires human approval for new recipients.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to"     : {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body"   : {"type": "string", "description": "Email body (plain text)"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    "draft_email": {
        "description": "Save an email draft to the vault without sending. Safe to call anytime.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to"     : {"type": "string"},
                "subject": {"type": "string"},
                "body"   : {"type": "string"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    "list_recent_emails": {
        "description": "List recent sent emails from the audit log.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of entries to return (default: 10)"},
            },
        },
    },
    "check_connection": {
        "description": "Verify SMTP server connectivity and credentials.",
        "inputSchema": {"type": "object", "properties": {}},
    },
}


def _send_jsonrpc(obj: dict):
    """Write a JSON-RPC response to stdout."""
    line = json.dumps(obj)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle_request(req: dict) -> dict | None:
    """Handle a single JSON-RPC request and return response dict."""
    method  = req.get("method", "")
    params  = req.get("params", {})
    req_id  = req.get("id")

    def ok(result):
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, msg):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}

    # MCP protocol: initialize
    if method == "initialize":
        return ok({
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "email-mcp", "version": SERVER_VERSION},
            "capabilities": {"tools": {}},
        })

    if method == "notifications/initialized":
        return None  # no response needed

    # List tools
    if method == "tools/list":
        tools = [
            {"name": name, "description": info["description"], "inputSchema": info["inputSchema"]}
            for name, info in MCP_TOOLS.items()
        ]
        return ok({"tools": tools})

    # Call tool
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "send_email":
            result = EmailSender.send(
                to      = arguments.get("to", ""),
                subject = arguments.get("subject", ""),
                body    = arguments.get("body", ""),
            )
        elif tool_name == "draft_email":
            result = EmailSender.save_draft(
                to      = arguments.get("to", ""),
                subject = arguments.get("subject", ""),
                body    = arguments.get("body", ""),
            )
        elif tool_name == "list_recent_emails":
            result = EmailSender.list_recent(arguments.get("count", 10))
        elif tool_name == "check_connection":
            result = EmailSender.check_connection()
        else:
            return err(-32601, f"Unknown tool: {tool_name}")

        return ok({
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": not result.get("success", True),
        })

    return err(-32601, f"Method not found: {method}")


def run_mcp_server():
    """Run MCP server over stdio (JSON-RPC 2.0)."""
    logger.info(f"EmailMCPServer v{SERVER_VERSION} starting (stdio transport)")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req      = json.loads(line)
            response = _handle_request(req)
            if response is not None:
                _send_jsonrpc(response)
        except json.JSONDecodeError as exc:
            _send_jsonrpc({
                "jsonrpc": "2.0",
                "id"     : None,
                "error"  : {"code": -32700, "message": f"Parse error: {exc}"},
            })
        except Exception as exc:
            logger.error(f"Request handler error: {exc}", exc_info=True)
            _send_jsonrpc({
                "jsonrpc": "2.0",
                "id"     : None,
                "error"  : {"code": -32603, "message": f"Internal error: {exc}"},
            })


# ──────────────────────────────────────────────────────────────────────────────
# CLI (standalone testing)
# ──────────────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="email_mcp_server",
        description="AI Employee Email MCP Server (Silver Tier)",
    )
    p.add_argument("--test-connection", action="store_true",
                   help="Test SMTP connection and exit")
    p.add_argument("--test-send", nargs=3, metavar=("TO", "SUBJECT", "BODY"),
                   help="Send a test email and exit")
    p.add_argument("--list-recent", type=int, default=None, metavar="N",
                   help="List N recent emails from audit log")
    p.add_argument("--standalone", action="store_true",
                   help="Add console output (use when not running as MCP server)")
    return p


def main():
    args = build_parser().parse_args()

    if args.standalone:
        logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    if args.test_connection:
        result = EmailSender.check_connection()
        print(json.dumps(result, indent=2))
        return

    if args.test_send:
        to, subject, body = args.test_send
        result = EmailSender.send(to, subject, body)
        print(json.dumps(result, indent=2))
        return

    if args.list_recent is not None:
        result = EmailSender.list_recent(args.list_recent or 10)
        print(json.dumps(result, indent=2))
        return

    # Default: run as MCP server
    run_mcp_server()


if __name__ == "__main__":
    main()
