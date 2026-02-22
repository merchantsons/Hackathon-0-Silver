"""
orchestrator.py — AI Employee Master Orchestrator (Silver Tier)
================================================================
The central nervous system that coordinates all Silver-tier components:

  • Watches Approved/ for human-approved actions and dispatches them
  • Watches Needs_Action/ for new tasks and triggers the Claude Agent
  • Schedules periodic tasks: daily briefing, weekly CEO audit, LinkedIn posts
  • Monitors health of all watcher processes
  • Provides consolidated status via Dashboard.md

Scheduled tasks (configurable via .env):
  DAILY_BRIEFING_TIME     HH:MM for daily summary (default: 08:00)
  WEEKLY_BRIEFING_DAY     0=Monday … 6=Sunday (default: 0)
  WEEKLY_BRIEFING_TIME    HH:MM for weekly CEO briefing (default: 07:00)
  LINKEDIN_POST_TIME      HH:MM for scheduled LinkedIn generation (default: 09:00)
  ORCHESTRATOR_POLL       Poll interval in seconds (default: 30)

Approved action dispatch:
  - Files in Approved/ named *email*.md → calls Email MCP server
  - Files in Approved/ named *linkedin*.md → triggers LinkedIn Watcher
  - Files in Approved/ with other names → logs and moves to Done/

Usage:
    python orchestrator.py                  # Start orchestrator
    python orchestrator.py --status         # Print current system status
    python orchestrator.py --dispatch-now   # Force-process all Approved/ items
    python orchestrator.py --briefing       # Generate CEO briefing now

Environment:
    DEV_MODE=true   Simulate all external actions
    DRY_RUN=true    Log intended actions without executing
"""

import os
import sys
import json
import time
import signal
import logging
import subprocess
from datetime import datetime, date
from pathlib import Path
from typing import Optional

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

VAULT_ROOT           = Path(__file__).parent / "AI_Employee_Vault"
NEEDS_ACTION_DIR     = VAULT_ROOT / "Needs_Action"
PENDING_APPROVAL_DIR = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR         = VAULT_ROOT / "Approved"
DONE_DIR             = VAULT_ROOT / "Done"
REJECTED_DIR         = VAULT_ROOT / "Rejected"
LOGS_DIR             = VAULT_ROOT / "Logs"
LOG_FILE             = LOGS_DIR / "orchestrator.log"
STATE_FILE           = LOGS_DIR / "orchestrator_state.json"

DAILY_BRIEFING_TIME  = os.environ.get("DAILY_BRIEFING_TIME",  "08:00")
WEEKLY_BRIEFING_DAY  = int(os.environ.get("WEEKLY_BRIEFING_DAY",  "0"))  # 0=Monday
WEEKLY_BRIEFING_TIME = os.environ.get("WEEKLY_BRIEFING_TIME", "07:00")
LINKEDIN_POST_TIME   = os.environ.get("LINKEDIN_POST_TIME",   "09:00")
POLL_INTERVAL        = int(os.environ.get("ORCHESTRATOR_POLL", "30"))

DRY_RUN  = os.environ.get("DRY_RUN",  "false").lower() in ("true", "1", "yes")
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() in ("true", "1", "yes")

ORCH_VERSION = "2.0.0"

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Orchestrator")


# ──────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR STATE
# ──────────────────────────────────────────────────────────────────────────────

class OrchestratorState:
    """Persists orchestrator run state across restarts."""

    def __init__(self):
        self._data = {
            "last_daily_briefing"  : None,
            "last_weekly_briefing" : None,
            "last_linkedin_gen"    : None,
            "processed_approvals"  : [],
            "total_dispatched"     : 0,
            "start_time"           : datetime.now().isoformat(),
        }
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            try:
                saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                self._data.update(saved)
                logger.info(f"State loaded: {self._data.get('total_dispatched', 0)} total dispatched")
            except Exception as exc:
                logger.warning(f"State load error: {exc}")

    def save(self):
        if DRY_RUN:
            return
        try:
            STATE_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"State save error: {exc}")

    def should_run_daily_briefing(self) -> bool:
        today = date.today().isoformat()
        now_time = datetime.now().strftime("%H:%M")
        return (
            self._data.get("last_daily_briefing") != today
            and now_time >= DAILY_BRIEFING_TIME
        )

    def should_run_weekly_briefing(self) -> bool:
        today     = date.today().isoformat()
        now_time  = datetime.now().strftime("%H:%M")
        weekday   = datetime.now().weekday()
        return (
            self._data.get("last_weekly_briefing") != today
            and weekday == WEEKLY_BRIEFING_DAY
            and now_time >= WEEKLY_BRIEFING_TIME
        )

    def should_generate_linkedin(self) -> bool:
        today    = date.today().isoformat()
        now_time = datetime.now().strftime("%H:%M")
        return (
            self._data.get("last_linkedin_gen") != today
            and now_time >= LINKEDIN_POST_TIME
        )

    def is_approval_processed(self, filename: str) -> bool:
        return filename in self._data.get("processed_approvals", [])

    def mark_approval_processed(self, filename: str):
        ids = self._data.setdefault("processed_approvals", [])
        ids.append(filename)
        self._data["processed_approvals"] = ids[-500:]
        self._data["total_dispatched"] = self._data.get("total_dispatched", 0) + 1


# ──────────────────────────────────────────────────────────────────────────────
# SUBPROCESS RUNNER
# ──────────────────────────────────────────────────────────────────────────────

PROJECT_DIR = Path(__file__).parent


def run_script(script: str, *args, timeout: int = 120) -> tuple[bool, str]:
    """
    Run a Python script in the project directory.
    Returns (success, output_preview).
    """
    if DRY_RUN:
        logger.info(f"[DRY_RUN] Would run: python {script} {' '.join(args)}")
        return True, "[DRY_RUN]"

    cmd = [sys.executable, PROJECT_DIR / script] + list(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = (result.stdout + result.stderr)[:500]
        if result.returncode == 0:
            return True, output
        else:
            logger.warning(f"Script {script} exited {result.returncode}: {output[:200]}")
            return False, output
    except subprocess.TimeoutExpired:
        logger.warning(f"Script {script} timed out ({timeout}s)")
        return False, "timeout"
    except Exception as exc:
        logger.error(f"Script {script} failed: {exc}")
        return False, str(exc)


# ──────────────────────────────────────────────────────────────────────────────
# LINKEDIN DISPATCHER
# ──────────────────────────────────────────────────────────────────────────────

class LinkedInDispatcher:
    """
    Reads approved LinkedIn post files and publishes them directly.

    Extracts the post text from between the '---' dividers in the approval
    file, then posts via the LinkedIn API or Playwright (same logic as
    watchers/linkedin_watcher.py). Falls back to DEV_MODE simulation.
    """

    @staticmethod
    def dispatch(approval_file: Path) -> bool:
        """Extract post text and publish to LinkedIn."""
        import re
        try:
            content = approval_file.read_text(encoding="utf-8")
            post_text = LinkedInDispatcher._extract_post_text(content)
            if not post_text:
                logger.warning(f"LinkedInDispatcher: could not extract post text from {approval_file.name}")
                return False

            logger.info(f"  Post preview: {post_text[:80]}…")

            if DRY_RUN:
                logger.info(f"  [DRY_RUN] Would publish LinkedIn post ({len(post_text)} chars)")
                return True

            if DEV_MODE:
                logger.info(f"  [DEV_MODE] Simulated LinkedIn post ({len(post_text)} chars)")
                LinkedInDispatcher._write_post_log(post_text, approval_file.name, "simulated")
                return True

            # Try LinkedIn API first
            access_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
            person_urn   = os.environ.get("LINKEDIN_PERSON_URN", "")
            if access_token and person_urn:
                success = LinkedInDispatcher._post_via_api(post_text, access_token, person_urn)
                if success:
                    LinkedInDispatcher._write_post_log(post_text, approval_file.name, "api")
                    return True

            # Fallback: Playwright browser automation
            li_email    = os.environ.get("LINKEDIN_EMAIL", "")
            li_password = os.environ.get("LINKEDIN_PASSWORD", "")
            if li_email and li_password:
                success = LinkedInDispatcher._post_via_playwright(post_text, li_email, li_password)
                if success:
                    LinkedInDispatcher._write_post_log(post_text, approval_file.name, "playwright")
                    return True

            logger.warning(
                "  LinkedIn credentials not configured.\n"
                "  Set LINKEDIN_ACCESS_TOKEN+LINKEDIN_PERSON_URN or\n"
                "  LINKEDIN_EMAIL+LINKEDIN_PASSWORD in .env\n"
                "  Or set DEV_MODE=true for simulation."
            )
            return False

        except Exception as exc:
            logger.error(f"LinkedInDispatcher.dispatch failed: {exc}", exc_info=True)
            return False

    @staticmethod
    def _extract_post_text(md_content: str) -> str | None:
        """Extract post body between '---' dividers after '## Proposed Post'."""
        import re
        match = re.search(
            r"## Proposed Post\s*\n[-]+\s*\n(.*?)\n[-]+",
            md_content, re.DOTALL,
        )
        if match:
            return match.group(1).strip()
        # Fallback: content after the fourth '---'
        parts = md_content.split("---")
        if len(parts) >= 4:
            return parts[3].strip()
        return None

    @staticmethod
    def _post_via_api(text: str, token: str, urn: str) -> bool:
        try:
            import httpx
            payload = {
                "author"         : f"urn:li:person:{urn}",
                "lifecycleState" : "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary"    : {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            }
            resp = httpx.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type" : "application/json",
                    "X-Restli-Protocol-Version": "2.0.0",
                },
                json=payload, timeout=30,
            )
            if resp.status_code in (200, 201):
                logger.info("  ✔ LinkedIn post published via API")
                return True
            logger.error(f"  LinkedIn API error {resp.status_code}: {resp.text[:200]}")
            return False
        except ImportError:
            logger.error("  httpx not installed: pip install httpx")
            return False
        except Exception as exc:
            logger.error(f"  LinkedIn API post failed: {exc}")
            return False

    @staticmethod
    def _post_via_playwright(text: str, email: str, password: str) -> bool:
        session_dir = PROJECT_DIR / "linkedin_session"
        try:
            from playwright.sync_api import sync_playwright
            session_dir.mkdir(exist_ok=True)
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    str(session_dir), headless=True, args=["--no-sandbox"],
                )
                page = browser.new_page()
                page.goto("https://www.linkedin.com/feed/", timeout=30000)
                if "login" in page.url or "signup" in page.url:
                    page.goto("https://www.linkedin.com/login")
                    page.fill("#username", email)
                    page.fill("#password", password)
                    page.click('[type="submit"]')
                    page.wait_for_url("**/feed/**", timeout=30000)
                page.click('[aria-label="Start a post"]', timeout=10000)
                page.wait_for_selector('.ql-editor', timeout=10000)
                page.fill('.ql-editor', text)
                page.wait_for_timeout(1000)
                page.locator('button:has-text("Post")').last.click()
                page.wait_for_timeout(3000)
                browser.close()
            logger.info("  ✔ LinkedIn post published via browser automation")
            return True
        except ImportError:
            logger.error("  Playwright not installed: pip install playwright && playwright install chromium")
            return False
        except Exception as exc:
            logger.error(f"  Playwright post failed: {exc}")
            return False

    @staticmethod
    def _write_post_log(text: str, filename: str, method: str):
        entry = {
            "timestamp"      : datetime.now().isoformat(),
            "action"         : "linkedin_post_published",
            "character_count": len(text),
            "approval_file"  : filename,
            "method"         : method,
            "tier"           : "silver",
        }
        log_file = LOGS_DIR / "linkedin_posts.jsonl"
        try:
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# EMAIL DISPATCHER
# ──────────────────────────────────────────────────────────────────────────────

class EmailDispatcher:
    """Reads approved email drafts and sends them via the Email MCP server."""

    @staticmethod
    def dispatch(approval_file: Path) -> bool:
        """Parse approval file, extract email details, and call EmailSender."""
        try:
            content = approval_file.read_text(encoding="utf-8")

            import re
            to_match      = re.search(r'to:\s*"([^"]+)"',      content)
            subject_match = re.search(r'subject:\s*"([^"]+)"', content)
            body_match    = re.search(
                r'## Proposed Reply\s*\n+> (.*?)(?:\n---|\Z)',
                content, re.DOTALL
            )

            to      = to_match.group(1).strip()      if to_match      else ""
            subject = subject_match.group(1).strip() if subject_match else "Re: (no subject)"
            body    = body_match.group(1).strip()    if body_match    else "(see attached draft)"

            if not to or "@" not in to:
                logger.warning(f"EmailDispatcher: invalid/missing 'to' in {approval_file.name}")
                return False

            # Import and use EmailSender directly
            sys.path.insert(0, str(PROJECT_DIR))
            from email_mcp_server import EmailSender
            result = EmailSender.send(to=to, subject=subject, body=body)

            if result.get("success"):
                logger.info(f"  ✔ Email sent: {to} — {subject}")
                return True
            else:
                logger.error(f"  ✘ Email send failed: {result.get('message')}")
                return False

        except Exception as exc:
            logger.error(f"EmailDispatcher.dispatch failed: {exc}", exc_info=True)
            return False


# ──────────────────────────────────────────────────────────────────────────────
# APPROVAL WATCHER
# ──────────────────────────────────────────────────────────────────────────────

def process_approved_items(state: OrchestratorState) -> int:
    """
    Scan Approved/ folder and dispatch approved actions.
    Returns count of items dispatched.
    """
    dispatched = 0
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)

    for approval_file in sorted(APPROVED_DIR.iterdir()):
        if not approval_file.is_file():
            continue
        if state.is_approval_processed(approval_file.name):
            continue

        logger.info(f"▶ Approved item: {approval_file.name}")
        name_lower = approval_file.name.lower()
        success    = False

        try:
            if "email" in name_lower and approval_file.suffix == ".md":
                logger.info("  → Dispatching via Email MCP server…")
                success = EmailDispatcher.dispatch(approval_file)

            elif "linkedin" in name_lower and approval_file.suffix == ".md":
                logger.info("  → Dispatching LinkedIn post…")
                success = LinkedInDispatcher.dispatch(approval_file)

            elif "payment" in name_lower:
                logger.warning("  → Payment approval detected — requires manual execution (security policy)")
                success = False  # Payments are never auto-dispatched

            else:
                logger.info(f"  → Generic approval: logging and archiving")
                success = True

            if success:
                # Move to Done/
                ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
                done_path = DONE_DIR / f"{ts}_DISPATCHED_{approval_file.name}"
                DONE_DIR.mkdir(parents=True, exist_ok=True)

                if not DRY_RUN:
                    approval_file.rename(done_path)
                    logger.info(f"  ✔ → Done/{done_path.name}")

                # Audit log
                _write_dispatch_log(approval_file.name, success)
                state.mark_approval_processed(approval_file.name)
                state.save()
                dispatched += 1
            else:
                logger.warning(f"  ✘ Dispatch failed for {approval_file.name}")

        except Exception as exc:
            logger.error(f"  ✘ Error processing {approval_file.name}: {exc}")

    return dispatched


def _write_dispatch_log(filename: str, success: bool):
    log_entry = {
        "timestamp"    : datetime.now().isoformat(),
        "action"       : "approval_dispatched",
        "filename"     : filename,
        "success"      : success,
        "simulated"    : DEV_MODE,
        "tier"         : "silver",
    }
    log_file = LOGS_DIR / "dispatch_audit.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# SCHEDULED TASKS
# ──────────────────────────────────────────────────────────────────────────────

def run_daily_briefing(state: OrchestratorState):
    """Generate a daily task summary and update Dashboard."""
    logger.info("▶ Running scheduled daily briefing…")
    ok, _ = run_script("claude_agent.py", "--update-dashboard")
    if ok:
        state._data["last_daily_briefing"] = date.today().isoformat()
        state.save()
        logger.info("  ✔ Daily briefing complete")


def run_weekly_ceo_briefing(state: OrchestratorState):
    """Generate the Monday CEO Briefing."""
    logger.info("▶ Running scheduled weekly CEO Briefing…")
    ok, output = run_script("claude_agent.py", "--briefing")
    if ok:
        state._data["last_weekly_briefing"] = date.today().isoformat()
        state.save()
        logger.info("  ✔ CEO Briefing generated")
    else:
        logger.warning(f"  ✘ CEO Briefing failed: {output[:100]}")


def run_linkedin_generation(state: OrchestratorState):
    """Trigger LinkedIn post generation from Business_Goals."""
    logger.info("▶ Scheduled LinkedIn post generation…")
    ok, _ = run_script("claude_agent.py", "--linkedin-post")
    if ok:
        state._data["last_linkedin_gen"] = date.today().isoformat()
        state.save()
        logger.info("  ✔ LinkedIn post draft → Pending_Approval/")


# ──────────────────────────────────────────────────────────────────────────────
# PROCESS HEALTH MONITOR
# ──────────────────────────────────────────────────────────────────────────────

def check_process_health():
    """
    Log status of watcher processes.
    Silver tier: passive check (no restart). Watchdog restart available for Gold+.
    """
    processes = {
        "Vault Watcher (watchers/file_system_watcher.py)": "watcher.log",
        "Gmail Watcher (watchers/gmail_watcher.py)": "gmail_watcher.log",
        "LinkedIn Watcher (watchers/linkedin_watcher.py)": "linkedin_watcher.log",
    }

    for name, log_name in processes.items():
        log_path = LOGS_DIR / log_name
        if log_path.exists():
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            age_min = (datetime.now() - mtime).total_seconds() / 60
            status = "🟢 Active" if age_min < 5 else f"🟡 Last seen {age_min:.0f}m ago"
        else:
            status = "⚫ Not started"
        logger.debug(f"  Health: {name}: {status}")


# ──────────────────────────────────────────────────────────────────────────────
# STATUS PRINTER
# ──────────────────────────────────────────────────────────────────────────────

def print_status():
    """Print a formatted system status to the console."""
    print("\n" + "═" * 62)
    print(f"  AI Employee Orchestrator v{ORCH_VERSION} — Silver Tier")
    print("═" * 62)

    # Vault counts
    dirs = {
        "Needs Action"    : NEEDS_ACTION_DIR,
        "Pending Approval": PENDING_APPROVAL_DIR,
        "Approved"        : APPROVED_DIR,
        "Done"            : DONE_DIR,
        "Rejected"        : REJECTED_DIR,
    }
    for label, d in dirs.items():
        count = sum(1 for f in d.iterdir() if f.is_file()) if d.exists() else 0
        print(f"  {label:20s}: {count}")

    print()

    # Schedule config
    print(f"  Daily briefing  : {DAILY_BRIEFING_TIME}")
    print(f"  Weekly briefing : {'Mon' if WEEKLY_BRIEFING_DAY == 0 else str(WEEKLY_BRIEFING_DAY)} @ {WEEKLY_BRIEFING_TIME}")
    print(f"  LinkedIn post   : {LINKEDIN_POST_TIME} ({os.environ.get('LINKEDIN_POST_SCHEDULE', 'daily')})")
    print()

    # Mode
    print(f"  DRY_RUN  : {'Yes' if DRY_RUN  else 'No'}")
    print(f"  DEV_MODE : {'Yes' if DEV_MODE else 'No'}")
    print("═" * 62 + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION LOOP
# ──────────────────────────────────────────────────────────────────────────────

def run_orchestrator():
    logger.info("═" * 62)
    logger.info(f"  Orchestrator v{ORCH_VERSION} — Silver Tier")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Poll interval: {POLL_INTERVAL}s")
    logger.info("═" * 62)

    if DRY_RUN:
        logger.info("  *** DRY_RUN MODE ***")
    if DEV_MODE:
        logger.info("  *** DEV_MODE ***")

    state   = OrchestratorState()
    running = [True]

    def _shutdown(signum, frame):
        logger.info("Shutdown signal — stopping Orchestrator…")
        running[0] = False

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    logger.info("  Orchestrator active. Monitoring Approved/ and schedule.")
    logger.info("  Press Ctrl+C to stop.")
    logger.info("─" * 62)

    while running[0]:
        try:
            # ── 1. Process approved items ────────────────────────────────────
            dispatched = process_approved_items(state)
            if dispatched:
                logger.info(f"  📤 {dispatched} approved item(s) dispatched")
                # Re-run agent to update dashboard
                run_script("claude_agent.py", "--update-dashboard", timeout=30)

            # ── 2. Scheduled tasks ───────────────────────────────────────────
            if state.should_run_daily_briefing():
                run_daily_briefing(state)

            if state.should_run_weekly_briefing():
                run_weekly_ceo_briefing(state)

            if state.should_generate_linkedin():
                run_linkedin_generation(state)

            # ── 3. Health check (passive) ────────────────────────────────────
            check_process_health()

        except Exception as exc:
            logger.error(f"Orchestrator loop error: {exc}", exc_info=True)

        if not running[0]:
            break

        for _ in range(POLL_INTERVAL):
            if not running[0]:
                break
            time.sleep(1)

    logger.info("Orchestrator stopped cleanly. Goodbye.")


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="orchestrator",
        description="AI Employee Master Orchestrator (Silver Tier)",
    )
    p.add_argument("--status",       action="store_true", help="Print current status and exit")
    p.add_argument("--dispatch-now", action="store_true", help="Process all Approved/ items and exit")
    p.add_argument("--briefing",     action="store_true", help="Generate CEO briefing and exit")
    return p


import argparse

def main():
    args = build_parser().parse_args()

    if args.status:
        print_status()
        return

    if args.dispatch_now:
        state = OrchestratorState()
        count = process_approved_items(state)
        print(f"\n✅ Dispatched {count} item(s)")
        return

    if args.briefing:
        logger.info("Generating CEO Briefing on demand…")
        ok, output = run_script("claude_agent.py", "--briefing")
        print("✅ Briefing generated" if ok else f"✘ Failed: {output}")
        return

    run_orchestrator()


if __name__ == "__main__":
    main()
