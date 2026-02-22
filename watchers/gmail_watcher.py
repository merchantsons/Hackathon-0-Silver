"""
watchers/gmail_watcher.py — AI Employee Gmail Watcher (Silver Tier)
===========================================================
Perception layer: monitors Gmail for important unread emails and routes
them as action files into the Obsidian vault for the Claude Agent to process.

Features:
  • OAuth2 authentication via Google Cloud credentials.json
  • Polls for unread, important emails (configurable query)
  • Creates structured .md files in Needs_Action/ with email metadata
  • Processes each email ONLY ONCE (processed_ids tracked in state file)
  • DEV_MODE: generates realistic simulated emails without API calls
  • Retry logic with exponential backoff for transient API errors
  • Graceful shutdown via Ctrl+C / SIGTERM

Setup:
  1. Go to Google Cloud Console → APIs → Gmail API → Enable
  2. Create OAuth 2.0 credentials → download as credentials.json
  3. Place credentials.json in the project root
  4. Run once: python gmail_watcher.py  (will open browser for auth)
  5. Thereafter runs headlessly

Environment:
  GMAIL_CREDENTIALS_PATH  Path to credentials.json (default: credentials.json)
  GMAIL_TOKEN_PATH        Path to store OAuth token (default: gmail_token.json)
  GMAIL_QUERY             Gmail search query (default: is:unread is:important)
  GMAIL_POLL_INTERVAL     Seconds between polls (default: 120)
  DEV_MODE=true           Generate simulated emails (no Google account needed)
  DRY_RUN=true            Log actions without writing files
"""

import os
import sys
import json
import time
import signal
import logging
import random
from datetime import datetime
from pathlib import Path

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

_PROJECT_ROOT    = Path(__file__).parent.parent
VAULT_ROOT       = _PROJECT_ROOT / "AI_Employee_Vault"
NEEDS_ACTION_DIR = VAULT_ROOT / "Needs_Action"
LOGS_DIR         = VAULT_ROOT / "Logs"
LOG_FILE         = LOGS_DIR / "gmail_watcher.log"
STATE_FILE       = LOGS_DIR / "gmail_processed_ids.json"

CREDENTIALS_PATH  = Path(os.environ.get("GMAIL_CREDENTIALS_PATH", str(_PROJECT_ROOT / "credentials.json")))
TOKEN_PATH        = Path(os.environ.get("GMAIL_TOKEN_PATH", str(_PROJECT_ROOT / "gmail_token.json")))
GMAIL_QUERY       = os.environ.get("GMAIL_QUERY", "is:unread is:important")
POLL_INTERVAL     = int(os.environ.get("GMAIL_POLL_INTERVAL", "120"))

DRY_RUN  = os.environ.get("DRY_RUN",  "false").lower() in ("true", "1", "yes")
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() in ("true", "1", "yes")

WATCHER_VERSION = "2.0.0"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)
NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("GmailWatcher")


# ──────────────────────────────────────────────────────────────────────────────
# STATE — track processed message IDs across restarts
# ──────────────────────────────────────────────────────────────────────────────

class ProcessedState:
    """Persists processed email IDs to avoid reprocessing after restarts."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._ids: set[str] = set()
        self._load()

    def _load(self):
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8-sig"))
                self._ids = set(data.get("processed_ids", []))
                logger.info(f"State: loaded {len(self._ids)} processed email IDs")
            except Exception as exc:
                logger.warning(f"State load failed: {exc} — starting fresh")

    def save(self):
        if DRY_RUN:
            return
        try:
            data = {"processed_ids": list(self._ids), "updated": datetime.now().isoformat()}
            self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"State save failed: {exc}")

    def is_processed(self, msg_id: str) -> bool:
        return msg_id in self._ids

    def mark_processed(self, msg_id: str):
        self._ids.add(msg_id)


# ──────────────────────────────────────────────────────────────────────────────
# GMAIL CLIENT
# ──────────────────────────────────────────────────────────────────────────────

class GmailClient:
    """Wraps the Google Gmail API with OAuth2 authentication."""

    def __init__(self):
        self.service = None
        self._init_service()

    def _init_service(self):
        """Initialise Gmail API service with OAuth2."""
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = None
            if TOKEN_PATH.exists():
                creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not CREDENTIALS_PATH.exists():
                        logger.error(
                            f"Gmail credentials not found: {CREDENTIALS_PATH}\n"
                            "  Download from Google Cloud Console → APIs → Gmail → OAuth 2.0 Credentials"
                        )
                        return
                    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
                    # open_browser=True auto-opens Chrome; success even for unverified
                    # apps as long as your Google account is added as a Test User in
                    # Google Cloud Console → APIs & Services → OAuth consent screen → Test users
                    creds = flow.run_local_server(port=0, open_browser=True)

                if not DRY_RUN:
                    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

            self.service = build("gmail", "v1", credentials=creds)
            logger.info("GmailClient: Authenticated successfully")

        except ImportError as exc:
            logger.error(
                f"Gmail libraries not installed: {exc}\n"
                "  Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )
        except Exception as exc:
            logger.error(f"GmailClient init failed: {exc}")

    def is_ready(self) -> bool:
        return self.service is not None

    def fetch_unread_important(self) -> list[dict]:
        """Fetch unread important email metadata."""
        if not self.service:
            return []
        try:
            result = self.service.users().messages().list(
                userId="me", q=GMAIL_QUERY, maxResults=20
            ).execute()
            return result.get("messages", [])
        except Exception as exc:
            logger.warning(f"Gmail list failed: {exc}")
            return []

    def get_message_details(self, msg_id: str) -> dict | None:
        """Get full message details including headers and snippet."""
        if not self.service:
            return None
        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            return {
                "id"      : msg_id,
                "from"    : headers.get("From", "Unknown"),
                "to"      : headers.get("To", ""),
                "subject" : headers.get("Subject", "No Subject"),
                "date"    : headers.get("Date", ""),
                "snippet" : msg.get("snippet", ""),
                "labels"  : msg.get("labelIds", []),
            }
        except Exception as exc:
            logger.warning(f"Gmail get message {msg_id} failed: {exc}")
            return None


# ──────────────────────────────────────────────────────────────────────────────
# DEV MODE — simulated email generator
# ──────────────────────────────────────────────────────────────────────────────

class SimulatedGmail:
    """Generates realistic fake emails for offline demos and testing."""

    _SIMULATED = [
        {
            "from"    : "client.alice@example.com",
            "subject" : "Invoice for January 2026 — urgent",
            "snippet" : "Hi, could you please send me the invoice for January? We need it by EOD.",
        },
        {
            "from"    : "partner.bob@techcorp.com",
            "subject" : "Partnership proposal — collaboration opportunity",
            "snippet" : "I wanted to discuss a potential collaboration that could benefit both our businesses.",
        },
        {
            "from"    : "support@paymentgateway.com",
            "subject" : "Payment received: $2,450.00",
            "snippet" : "Transaction confirmed. Your account has been credited with $2,450.00.",
        },
        {
            "from"    : "leads@salesforce.com",
            "subject" : "New inbound lead: Enterprise Software Inquiry",
            "snippet" : "A new lead has been assigned to you. Company: Acme Corp. Budget: $50K+",
        },
        {
            "from"    : "newsletter@industry.io",
            "subject" : "AI in Business: Weekly Digest",
            "snippet" : "This week: How autonomous agents are reshaping enterprise workflows...",
        },
    ]

    _counter = 0

    @classmethod
    def next_email(cls) -> dict | None:
        """Return next simulated email, cycling through the list."""
        if cls._counter >= len(cls._SIMULATED):
            return None  # No more simulated emails this run
        email = cls._SIMULATED[cls._counter].copy()
        email["id"]   = f"SIM_{cls._counter:04d}_{int(time.time())}"
        email["date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
        cls._counter += 1
        return email


# ──────────────────────────────────────────────────────────────────────────────
# ACTION FILE CREATOR
# ──────────────────────────────────────────────────────────────────────────────

def create_email_action_file(email: dict) -> Path | None:
    """Create a Markdown action file in Needs_Action/ for the given email."""
    now     = datetime.now()
    ts      = now.strftime("%Y%m%d_%H%M%S")
    subject = email.get("subject", "No Subject")
    safe_subject = "".join(c if c.isalnum() or c in " _-" else "_" for c in subject)[:40].strip()
    filename = f"{ts}_EMAIL_{safe_subject}.md"
    filepath = NEEDS_ACTION_DIR / filename

    # Detect priority from subject
    subject_lower = subject.lower()
    priority = "high" if any(kw in subject_lower for kw in ["urgent", "asap", "invoice", "payment"]) else "medium"

    content = f"""---
type: email
source: gmail
email_id: "{email.get('id', 'unknown')}"
from: "{email.get('from', 'Unknown')}"
to: "{email.get('to', '')}"
subject: "{subject}"
date: "{email.get('date', now.strftime('%Y-%m-%d'))}"
received: "{now.isoformat()}"
priority: {priority}
status: pending
tier: silver
simulated: {str(DEV_MODE).lower()}
---

# Email: {subject}

## Headers

| Field | Value |
|-------|-------|
| From | {email.get('from', 'Unknown')} |
| Subject | {subject} |
| Date | {email.get('date', now.strftime('%Y-%m-%d'))} |
| Priority | **{priority.upper()}** |

## Email Content

{email.get('snippet', '(No preview available)')}

## Suggested Actions

- [ ] Read full email content
- [ ] Identify required response or action
- [ ] Draft reply via EmailDrafter (will appear in Pending_Approval/)
- [ ] Send after human approval via Email MCP server
- [ ] Log to communication audit trail

## Instructions for Claude Agent

1. Classify this email using `Skills/task_classifier.md`
2. Generate a reply draft using `Skills/email_sender.md`
3. Place draft in `Pending_Approval/` for human review
4. After approval: send via Email MCP server (see `email_mcp_server.py`)

---
*Generated by GmailWatcher v{WATCHER_VERSION} (Silver Tier)*
*{'[SIMULATED — DEV MODE]' if DEV_MODE else '[LIVE — Gmail API]'}*
"""

    if DRY_RUN:
        logger.info(f"[DRY_RUN] Would create: Needs_Action/{filename}")
        return filepath

    try:
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"  ✔ Email → Needs_Action/{filename}")
        return filepath
    except Exception as exc:
        logger.error(f"  ✘ Failed to create action file: {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# RETRY HELPER
# ──────────────────────────────────────────────────────────────────────────────

def with_retry(fn, max_attempts: int = 3, base_delay: float = 2.0):
    """Call fn() with exponential backoff on failure."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            if attempt == max_attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed: {exc}. Retrying in {delay:.0f}s…")
            time.sleep(delay)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN WATCHER LOOP
# ──────────────────────────────────────────────────────────────────────────────

def run_watcher():
    """Main polling loop."""
    logger.info("═" * 62)
    logger.info(f"  GmailWatcher v{WATCHER_VERSION} — Silver Tier")
    logger.info("═" * 62)

    if DRY_RUN:
        logger.info("  *** DRY_RUN MODE — No files will be written ***")
    if DEV_MODE:
        logger.info("  *** DEV_MODE — Using simulated emails (no Gmail API) ***")
    else:
        logger.info(f"  Query: {GMAIL_QUERY}")
        logger.info(f"  Poll interval: {POLL_INTERVAL}s")

    state   = ProcessedState(STATE_FILE)
    client  = None if DEV_MODE else GmailClient()

    if not DEV_MODE and (client is None or not client.is_ready()):
        logger.error("Gmail client not ready. Set DEV_MODE=true or configure credentials.json")
        logger.info("Falling back to DEV_MODE for this session.")
        # Fall back gracefully
        os.environ["DEV_MODE"] = "true"
        globals()["DEV_MODE"] = True

    running = [True]

    def _shutdown(signum, frame):
        logger.info("Shutdown signal — stopping GmailWatcher…")
        running[0] = False

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    logger.info("  Gmail Watcher active. Monitoring for new emails.")
    logger.info("  Press Ctrl+C to stop.")
    logger.info("─" * 62)

    while running[0]:
        try:
            poll_start = datetime.now()

            if DEV_MODE:
                email_data = SimulatedGmail.next_email()
                if email_data:
                    emails_raw = [email_data]
                else:
                    emails_raw = []
                    logger.info(f"[{poll_start.strftime('%H:%M:%S')}] DEV_MODE: All simulated emails delivered. Idling.")
            else:
                msgs = with_retry(lambda: client.fetch_unread_important())
                emails_raw = []
                for m in msgs:
                    if not state.is_processed(m["id"]):
                        detail = with_retry(lambda mid=m["id"]: client.get_message_details(mid))
                        if detail:
                            emails_raw.append(detail)

            new_count = 0
            for email in emails_raw:
                msg_id = email.get("id", "")
                if state.is_processed(msg_id):
                    continue

                logger.info(f"▶ New email: {email.get('subject', '(no subject)')[:60]}")
                logger.info(f"  From: {email.get('from', 'unknown')}")

                filepath = create_email_action_file(email)
                if filepath:
                    state.mark_processed(msg_id)
                    new_count += 1

            if new_count:
                state.save()
                logger.info(f"  ✅ {new_count} email(s) routed to Needs_Action/")
            else:
                if not DEV_MODE:
                    logger.info(f"[{poll_start.strftime('%H:%M:%S')}] No new emails. Next check in {POLL_INTERVAL}s.")

        except Exception as exc:
            logger.error(f"Poll error: {exc}", exc_info=True)

        if not running[0]:
            break

        # Wait for next poll
        for _ in range(POLL_INTERVAL):
            if not running[0]:
                break
            time.sleep(1)

    logger.info("GmailWatcher stopped cleanly. Goodbye.")


if __name__ == "__main__":
    run_watcher()
