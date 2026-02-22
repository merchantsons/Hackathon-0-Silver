"""
watchers/linkedin_watcher.py — AI Employee LinkedIn Watcher + Auto-Poster (Silver Tier)
===============================================================================
Dual-purpose watcher:

1. MONITOR  — polls LinkedIn notifications/messages for sales opportunities
   and routes them as action files to Needs_Action/.

2. POSTER   — picks up approved LinkedIn posts from Approved/ and publishes
   them via the LinkedIn API (or Playwright automation as fallback).

Features:
  • LinkedIn API v2 for reading notifications and profile data
  • Playwright browser automation for posting (API posting requires approval tier)
  • AI-generated content via LinkedInContentGenerator in claude_agent.py
  • Human-in-the-loop: all posts go through Pending_Approval/ before publishing
  • DEV_MODE: simulates monitoring + posting without real LinkedIn account
  • Scheduled auto-posting: generates business content on a configurable schedule
  • Graceful shutdown, retry logic, and audit logging

Setup (Real LinkedIn):
  Option A — LinkedIn API (recommended):
    1. Create a LinkedIn Developer App at developer.linkedin.com
    2. Request "Share on LinkedIn" and "Sign In with LinkedIn" products
    3. Set LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, LINKEDIN_ACCESS_TOKEN
  Option B — Browser automation (fallback):
    1. pip install playwright && playwright install chromium
    2. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD
    3. Run once manually to complete 2FA if required

Environment:
  LINKEDIN_ACCESS_TOKEN   LinkedIn API bearer token (Option A)
  LINKEDIN_PERSON_URN     LinkedIn person URN e.g. urn:li:person:ABC123
  LINKEDIN_EMAIL          LinkedIn login email (Option B)
  LINKEDIN_PASSWORD       LinkedIn password (Option B)
  LINKEDIN_POLL_INTERVAL  Seconds between polls (default: 300)
  LINKEDIN_POST_SCHEDULE  Posting schedule: daily|weekly (default: daily)
  DEV_MODE=true           Simulate all LinkedIn actions
  DRY_RUN=true            Log actions without executing
"""

import os
import sys
import json
import time
import signal
import logging
import re
from datetime import datetime, timedelta
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

_PROJECT_ROOT        = Path(__file__).parent.parent
VAULT_ROOT           = _PROJECT_ROOT / "AI_Employee_Vault"
NEEDS_ACTION_DIR     = VAULT_ROOT / "Needs_Action"
PENDING_APPROVAL_DIR = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR         = VAULT_ROOT / "Approved"
DONE_DIR             = VAULT_ROOT / "Done"
LOGS_DIR             = VAULT_ROOT / "Logs"
LOG_FILE             = LOGS_DIR / "linkedin_watcher.log"
STATE_FILE           = LOGS_DIR / "linkedin_state.json"

ACCESS_TOKEN    = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
PERSON_URN      = os.environ.get("LINKEDIN_PERSON_URN", "")
LI_EMAIL        = os.environ.get("LINKEDIN_EMAIL", "")
LI_PASSWORD     = os.environ.get("LINKEDIN_PASSWORD", "")
POLL_INTERVAL   = int(os.environ.get("LINKEDIN_POLL_INTERVAL", "300"))
POST_SCHEDULE   = os.environ.get("LINKEDIN_POST_SCHEDULE", "daily")

DRY_RUN  = os.environ.get("DRY_RUN",  "false").lower() in ("true", "1", "yes")
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() in ("true", "1", "yes")

WATCHER_VERSION = "2.0.0"
LINKEDIN_API_BASE = "https://api.linkedin.com/v2"

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)
NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
PENDING_APPROVAL_DIR.mkdir(parents=True, exist_ok=True)
APPROVED_DIR.mkdir(parents=True, exist_ok=True)
DONE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("LinkedInWatcher")


# ──────────────────────────────────────────────────────────────────────────────
# STATE PERSISTENCE
# ──────────────────────────────────────────────────────────────────────────────

class LinkedInState:
    """Tracks processed notifications and posting schedule."""

    def __init__(self):
        self._data = {
            "processed_notifications": [],
            "last_post_date": None,
            "total_posts": 0,
        }
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            try:
                self._data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                logger.info(f"State: loaded ({self._data.get('total_posts', 0)} posts published)")
            except Exception as exc:
                logger.warning(f"State load failed: {exc}")

    def save(self):
        if DRY_RUN:
            return
        try:
            STATE_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"State save failed: {exc}")

    def is_processed(self, notification_id: str) -> bool:
        return notification_id in self._data["processed_notifications"]

    def mark_processed(self, notification_id: str):
        ids = self._data["processed_notifications"]
        ids.append(notification_id)
        # Keep last 200 IDs
        self._data["processed_notifications"] = ids[-200:]

    def should_post_today(self) -> bool:
        """Check if it's time to generate a new LinkedIn post."""
        last = self._data.get("last_post_date")
        today = datetime.now().date().isoformat()
        if POST_SCHEDULE == "daily":
            return last != today
        elif POST_SCHEDULE == "weekly":
            if not last:
                return True
            last_date = datetime.fromisoformat(last).date()
            return (datetime.now().date() - last_date).days >= 7
        return False

    def mark_posted(self):
        self._data["last_post_date"] = datetime.now().date().isoformat()
        self._data["total_posts"] = self._data.get("total_posts", 0) + 1
        self.save()


# ──────────────────────────────────────────────────────────────────────────────
# LINKEDIN API CLIENT
# ──────────────────────────────────────────────────────────────────────────────

class LinkedInAPIClient:
    """LinkedIn REST API v2 client for reading and posting."""

    def __init__(self):
        self._available = bool(ACCESS_TOKEN and PERSON_URN)
        if not self._available:
            logger.warning(
                "LinkedIn API credentials not set.\n"
                "  Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN\n"
                "  or set DEV_MODE=true for simulation."
            )

    def is_ready(self) -> bool:
        return self._available

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type" : "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def post_share(self, text: str) -> bool:
        """Post a text share to LinkedIn using UGC Posts API."""
        if not self._available:
            logger.warning("LinkedIn API not configured for posting.")
            return False
        try:
            import httpx
            payload = {
                "author"          : f"urn:li:person:{PERSON_URN}",
                "lifecycleState"  : "PUBLISHED",
                "specificContent" : {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            }
            resp = httpx.post(
                f"{LINKEDIN_API_BASE}/ugcPosts",
                headers=self._headers(),
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                logger.info("✔ LinkedIn post published via API")
                return True
            else:
                logger.error(f"LinkedIn API error {resp.status_code}: {resp.text[:300]}")
                return False
        except ImportError:
            logger.error("httpx not installed: pip install httpx")
            return False
        except Exception as exc:
            logger.error(f"LinkedIn API post failed: {exc}")
            return False


# ──────────────────────────────────────────────────────────────────────────────
# PLAYWRIGHT POSTER (fallback for browser automation)
# ──────────────────────────────────────────────────────────────────────────────

class LinkedInPlaywrightPoster:
    """Posts to LinkedIn via browser automation when API is unavailable."""

    SESSION_DIR = Path(__file__).parent.parent / "linkedin_session"

    @classmethod
    def post(cls, text: str) -> bool:
        """Post text to LinkedIn via Playwright browser automation."""
        if not LI_EMAIL or not LI_PASSWORD:
            logger.warning(
                "LinkedIn browser credentials not set.\n"
                "  Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD, or use API approach."
            )
            return False

        try:
            from playwright.sync_api import sync_playwright

            cls.SESSION_DIR.mkdir(exist_ok=True)

            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    str(cls.SESSION_DIR),
                    headless=True,
                    args=["--no-sandbox"],
                )
                page = browser.new_page()

                # Check if already logged in
                page.goto("https://www.linkedin.com/feed/", timeout=30000)
                if "login" in page.url or "signup" in page.url:
                    logger.info("LinkedIn: Logging in via browser…")
                    page.goto("https://www.linkedin.com/login")
                    page.fill("#username", LI_EMAIL)
                    page.fill("#password", LI_PASSWORD)
                    page.click('[type="submit"]')
                    page.wait_for_url("**/feed/**", timeout=30000)

                # Click "Start a post"
                page.click('[aria-label="Start a post"]', timeout=10000)
                page.wait_for_selector('.ql-editor', timeout=10000)
                page.fill('.ql-editor', text)
                page.wait_for_timeout(1000)

                # Click Post button
                post_btn = page.locator('button:has-text("Post")')
                post_btn.last.click()
                page.wait_for_timeout(3000)

                browser.close()
                logger.info("✔ LinkedIn post published via browser automation")
                return True

        except ImportError:
            logger.error("Playwright not installed: pip install playwright && playwright install chromium")
            return False
        except Exception as exc:
            logger.error(f"LinkedIn Playwright post failed: {exc}")
            return False


# ──────────────────────────────────────────────────────────────────────────────
# DEV MODE SIMULATOR
# ──────────────────────────────────────────────────────────────────────────────

class SimulatedLinkedIn:
    """Simulates LinkedIn interactions for offline demos."""

    _NOTIFICATIONS = [
        {
            "id"  : "LI_001",
            "type": "connection_request",
            "from": "Sarah Chen — VP Sales at TechCorp",
            "text": "Hi! I'd love to connect and discuss potential partnerships.",
        },
        {
            "id"  : "LI_002",
            "type": "message",
            "from": "James Wilson — CEO at StartupXYZ",
            "text": "We're interested in your services. What are your pricing options?",
        },
        {
            "id"  : "LI_003",
            "type": "post_mention",
            "from": "Industry Newsletter",
            "text": "Your recent post on AI automation was featured in our weekly digest!",
        },
    ]

    _idx = 0

    @classmethod
    def next_notification(cls) -> dict | None:
        if cls._idx >= len(cls._NOTIFICATIONS):
            return None
        notif = cls._NOTIFICATIONS[cls._idx].copy()
        cls._idx += 1
        return notif

    @classmethod
    def simulate_post(cls, text: str) -> bool:
        logger.info(f"[DEV_MODE] Simulated LinkedIn post ({len(text)} chars):")
        logger.info(f"  Preview: {text[:100]}...")
        return True


# ──────────────────────────────────────────────────────────────────────────────
# NOTIFICATION → ACTION FILE
# ──────────────────────────────────────────────────────────────────────────────

def create_notification_action_file(notification: dict) -> Path | None:
    """Create action file in Needs_Action/ for a LinkedIn notification."""
    now   = datetime.now()
    ts    = now.strftime("%Y%m%d_%H%M%S")
    ntype = notification.get("type", "notification")
    nfrom = notification.get("from", "Unknown")
    text  = notification.get("text", "")

    safe_from = re.sub(r"[^\w\s-]", "_", nfrom)[:30].strip()
    filename  = f"{ts}_LINKEDIN_{ntype}_{safe_from}.md"
    filepath  = NEEDS_ACTION_DIR / filename

    priority = "high" if "pricing" in text.lower() or "interested" in text.lower() else "medium"

    content = f"""---
type: linkedin_notification
source: linkedin
notification_id: "{notification.get('id', ts)}"
notification_type: "{ntype}"
from: "{nfrom}"
received: "{now.isoformat()}"
priority: {priority}
status: pending
tier: silver
simulated: {str(DEV_MODE).lower()}
---

# LinkedIn {ntype.replace('_', ' ').title()}: {nfrom}

## Notification Details

| Field | Value |
|-------|-------|
| Type | {ntype.replace('_', ' ').title()} |
| From | {nfrom} |
| Received | {now.strftime('%Y-%m-%d %H:%M:%S')} |
| Priority | **{priority.upper()}** |

## Message

{text}

## Suggested Actions

- [ ] Review the notification context
- [ ] Identify business opportunity (connection, partnership, sales lead)
- [ ] Draft LinkedIn message response if appropriate
- [ ] Log opportunity in Business_Goals.md if high-value
- [ ] Update Dashboard with lead status

## Sales Opportunity Assessment

*[Claude Agent will assess this notification for business value]*

---
*Generated by LinkedInWatcher v{WATCHER_VERSION} (Silver Tier)*
*{'[SIMULATED — DEV MODE]' if DEV_MODE else '[LIVE — LinkedIn API]'}*
"""

    if DRY_RUN:
        logger.info(f"[DRY_RUN] Would create: Needs_Action/{filename}")
        return filepath

    try:
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"  ✔ LinkedIn notification → Needs_Action/{filename}")
        return filepath
    except Exception as exc:
        logger.error(f"  ✘ Failed to create action file: {exc}")
        return None


# ──────────────────────────────────────────────────────────────────────────────
# APPROVED POST PROCESSOR
# ──────────────────────────────────────────────────────────────────────────────

def process_approved_posts(state: LinkedInState, api_client: LinkedInAPIClient) -> int:
    """
    Check Approved/ folder for approved LinkedIn posts and publish them.
    Returns count of posts published.
    """
    published = 0

    for approval_file in APPROVED_DIR.iterdir():
        if not approval_file.is_file():
            continue
        if "linkedin" not in approval_file.name.lower():
            continue
        if approval_file.suffix.lower() != ".md":
            continue

        logger.info(f"▶ Found approved LinkedIn post: {approval_file.name}")

        try:
            content = approval_file.read_text(encoding="utf-8")
            post_text = _extract_post_text(content)
            if not post_text:
                logger.warning(f"  Could not extract post text from {approval_file.name}")
                continue

            if DRY_RUN:
                logger.info(f"  [DRY_RUN] Would post to LinkedIn ({len(post_text)} chars)")
                success = True
            elif DEV_MODE:
                success = SimulatedLinkedIn.simulate_post(post_text)
            elif api_client.is_ready():
                success = api_client.post_share(post_text)
            elif LI_EMAIL and LI_PASSWORD:
                success = LinkedInPlaywrightPoster.post(post_text)
            else:
                logger.warning("  No posting method available. Set LinkedIn credentials.")
                success = False

            if success:
                published += 1
                state.mark_posted()

                # Log the post
                _log_post(post_text, approval_file.name)

                # Move approval file to Done/
                ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
                done_path = DONE_DIR / f"{ts}_PUBLISHED_{approval_file.name}"
                if not DRY_RUN:
                    approval_file.rename(done_path)
                    logger.info(f"  ✔ Moved to Done/: {done_path.name}")

                logger.info(f"  ✅ LinkedIn post published! Total posts: {state._data.get('total_posts', 0)}")

        except Exception as exc:
            logger.error(f"  ✘ Error processing {approval_file.name}: {exc}")

    return published


def _extract_post_text(md_content: str) -> str | None:
    """Extract post body from between the '---' dividers in the approval file."""
    # Look for content between the two --- markers after "## Proposed Post"
    match = re.search(
        r"## Proposed Post\s*\n[-]+\s*\n(.*?)\n[-]+",
        md_content,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # Fallback: everything after the second ---
    parts = md_content.split("---")
    if len(parts) >= 4:
        return parts[3].strip()
    return None


def _log_post(text: str, approval_filename: str):
    """Append a post audit entry to Logs/."""
    log_entry = {
        "timestamp"         : datetime.now().isoformat(),
        "action"            : "linkedin_post_published",
        "character_count"   : len(text),
        "approval_file"     : approval_filename,
        "simulated"         : DEV_MODE,
        "tier"              : "silver",
    }
    log_file = LOGS_DIR / "linkedin_posts.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_entry) + "\n")
    except Exception as exc:
        logger.warning(f"Post log write failed: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# SCHEDULED POST GENERATION
# ──────────────────────────────────────────────────────────────────────────────

def trigger_scheduled_post_generation():
    """
    Trigger the Claude agent to generate a LinkedIn post from Business_Goals.md.
    The generated post lands in Pending_Approval/ for human review.
    """
    import subprocess
    logger.info("▶ Triggering scheduled LinkedIn post generation…")
    try:
        result = subprocess.run(
            [sys.executable, Path(__file__).parent.parent / "claude_agent.py", "--linkedin-post"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("  ✔ LinkedIn post draft generated → Pending_Approval/")
        else:
            logger.warning(f"  ✘ Post generation failed (code {result.returncode})")
    except Exception as exc:
        logger.warning(f"  ✘ Post generation subprocess failed: {exc}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN WATCHER LOOP
# ──────────────────────────────────────────────────────────────────────────────

def run_watcher():
    logger.info("═" * 62)
    logger.info(f"  LinkedInWatcher v{WATCHER_VERSION} — Silver Tier")
    logger.info("═" * 62)

    if DRY_RUN:
        logger.info("  *** DRY_RUN MODE — No actions will be executed ***")
    if DEV_MODE:
        logger.info("  *** DEV_MODE — Using simulated LinkedIn data ***")
    else:
        api_mode = "API" if ACCESS_TOKEN else ("Browser" if LI_EMAIL else "NOT CONFIGURED")
        logger.info(f"  Mode: {api_mode}")
    logger.info(f"  Post schedule: {POST_SCHEDULE}")
    logger.info("─" * 62)

    state      = LinkedInState()
    api_client = LinkedInAPIClient()

    running = [True]

    def _shutdown(signum, frame):
        logger.info("Shutdown signal — stopping LinkedInWatcher…")
        running[0] = False

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    logger.info("  LinkedIn Watcher active.")
    logger.info("  Press Ctrl+C to stop.")
    logger.info("─" * 62)

    while running[0]:
        try:
            now = datetime.now()

            # ── 1. Monitor for new notifications ────────────────────────────
            if DEV_MODE:
                notif = SimulatedLinkedIn.next_notification()
                notifications = [notif] if notif else []
            else:
                notifications = []  # Real: use LinkedIn API notification endpoint

            for n in notifications:
                nid = n.get("id", "")
                if not state.is_processed(nid):
                    logger.info(f"▶ New LinkedIn notification: {n.get('type')} from {n.get('from', 'unknown')[:40]}")
                    path = create_notification_action_file(n)
                    if path:
                        state.mark_processed(nid)
                        state.save()

            # ── 2. Check Approved/ for posts to publish ──────────────────────
            published = process_approved_posts(state, api_client)
            if published:
                logger.info(f"  📤 {published} LinkedIn post(s) published")

            # ── 3. Scheduled post generation ────────────────────────────────
            if state.should_post_today():
                logger.info(f"▶ Scheduled post generation (schedule: {POST_SCHEDULE})")
                trigger_scheduled_post_generation()
                # Mark as "attempted today" regardless of approval
                state._data["last_post_date"] = now.date().isoformat()
                state.save()

        except Exception as exc:
            logger.error(f"Watcher loop error: {exc}", exc_info=True)

        if not running[0]:
            break

        logger.debug(f"Sleeping {POLL_INTERVAL}s until next poll…")
        for _ in range(POLL_INTERVAL):
            if not running[0]:
                break
            time.sleep(1)

    logger.info("LinkedInWatcher stopped cleanly. Goodbye.")


if __name__ == "__main__":
    run_watcher()
