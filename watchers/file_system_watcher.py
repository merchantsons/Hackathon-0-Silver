"""
watchers/file_system_watcher.py — AI Employee Vault Watcher (Bronze Tier)
==========================================================================
Perception layer of the Perception → Reasoning → Action architecture.

Monitors the Inbox/ folder for new files and routes them into Needs_Action/
with accompanying metadata. Never deletes original files.

When an Inbox file is deleted, all related processing is rolled back:
Needs_Action, Done, Plans, Pending_Approval artifacts and task_catalog.jsonl
entries for that file are removed, and the Dashboard is refreshed.

Silver+ compatibility: Drop-in replaceable with MCP filesystem server.
Ralph Wiggum loop: Not implemented (Gold tier). Hook marked with [RW_HOOK].

Usage:
    python file_system_watcher.py                # Normal mode
    DRY_RUN=true python file_system_watcher.py  # Simulate only

Stop: Ctrl+C (graceful shutdown)
"""

import os
import sys
import re
import json
import shutil
import logging
import hashlib
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

# Load .env so DRY_RUN is available
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Fix Windows console encoding so Unicode symbols render correctly
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 fallback

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("ERROR: watchdog library not installed.")
    print("Run:   pip install watchdog")
    print("Or:    pip install -r requirements.txt")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────────────────────────

VAULT_ROOT           = Path(__file__).parent.parent / "AI_Employee_Vault"
INBOX_DIR            = VAULT_ROOT / "Inbox"
NEEDS_ACTION_DIR     = VAULT_ROOT / "Needs_Action"
PLANS_DIR            = VAULT_ROOT / "Plans"
DONE_DIR             = VAULT_ROOT / "Done"
PENDING_APPROVAL_DIR = VAULT_ROOT / "Pending_Approval"
LOGS_DIR             = VAULT_ROOT / "Logs"
LOG_FILE             = LOGS_DIR / "watcher.log"
CATALOG_FILE         = LOGS_DIR / "task_catalog.jsonl"
DASHBOARD_FILE       = VAULT_ROOT / "Dashboard.md"

WATCHER_VERSION = "1.0.0"
TIER            = "bronze"

# Set DRY_RUN=true in environment to simulate without making any changes
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")

# How long to wait (seconds) for a file to stabilise before copying
FILE_STABILISE_TIMEOUT = 30
FILE_STABILISE_INTERVAL = 0.5

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

_log_handlers = [
    logging.FileHandler(LOG_FILE, encoding="utf-8"),
    logging.StreamHandler(sys.stdout),
]
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_log_handlers,
)
logger = logging.getLogger("VaultWatcher")

# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def compute_md5(filepath: Path) -> str:
    """Return MD5 hex digest of a file for integrity verification."""
    h = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        logger.warning(f"Cannot compute hash for {filepath.name}: {exc}")
        return "unknown"


def sanitize_filename(name: str) -> str:
    """Strip filesystem-unsafe characters from a filename stem."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name


def generate_metadata_md(source_file: Path, dest_file: Path) -> str:
    """
    Build a YAML-frontmatter Markdown task card for a newly detected file.

    This metadata file is the handoff document between the Watcher (Perception)
    and the Claude Agent (Reasoning). It contains all context the agent needs.
    """
    now   = datetime.now()
    stat  = source_file.stat()
    fhash = compute_md5(source_file)

    return f"""---
title: "Task: {source_file.name}"
created: "{now.strftime('%Y-%m-%d %H:%M:%S')}"
source_file: "{source_file.name}"
source_path: "{source_file.as_posix()}"
destination_path: "{dest_file.as_posix()}"
status: "needs_action"
priority: "unset"
file_size_bytes: {stat.st_size}
file_hash_md5: "{fhash}"
watcher_version: "{WATCHER_VERSION}"
tier: "{TIER}"
---

# Task: {source_file.name}

**Received:** {now.strftime('%Y-%m-%d %H:%M:%S')}
**Status:** Needs Action
**Priority:** Unset (pending classification)

## File Details

| Field | Value |
|-------|-------|
| Filename | `{source_file.name}` |
| Destination | `{dest_file.name}` |
| Size | {stat.st_size:,} bytes |
| MD5 Hash | `{fhash}` |
| Detected At | {now.strftime('%Y-%m-%d %H:%M:%S')} |

## Processing Checklist

- [x] File detected in Inbox/
- [x] Copied to Needs_Action/
- [x] Metadata generated
- [ ] Classification pending  ← Claude Agent step
- [ ] Plan generation pending ← Claude Agent step
- [ ] Actions pending         ← Claude Agent step
- [ ] Completion pending      ← Claude Agent step

## Instructions for Claude Agent

1. Read this metadata file and the original: `{dest_file.name}`
2. Classify using `Skills/task_classifier.md`
3. Generate a plan using `Skills/plan_generator.md`
4. Execute safe actions per `Skills/action_processor.md`
5. Update `Dashboard.md` via `Skills/dashboard_updater.md`
6. Move completed items to `Done/`

---
*Auto-generated by VaultWatcher v{WATCHER_VERSION} (Bronze Tier)*
"""


def _read_source_file_from_meta(meta_path: Path) -> str | None:
    """Read meta file and return source_file from YAML frontmatter, or None."""
    try:
        text = meta_path.read_text(encoding="utf-8")
        m = re.search(r'source_file:\s*"([^"]+)"', text)
        return m.group(1) if m else None
    except Exception:
        return None


def _read_destination_path_from_meta(meta_path: Path) -> str | None:
    """Read meta file and return destination_path from YAML frontmatter, or None."""
    try:
        text = meta_path.read_text(encoding="utf-8")
        m = re.search(r'destination_path:\s*"([^"]+)"', text)
        return m.group(1) if m else None
    except Exception:
        return None


def refresh_dashboard() -> None:
    """Run claude_agent.py --update-dashboard to refresh Dashboard.md with current vault state."""
    if DRY_RUN:
        logger.info("  [DRY_RUN] Would refresh Dashboard")
        return
    try:
        subprocess.run(
            [sys.executable, Path(__file__).parent.parent / "claude_agent.py", "--update-dashboard"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        logger.info("  ✔ Dashboard updated")
    except Exception as exc:
        logger.warning(f"  ✘ Dashboard update failed: {exc}")


def run_agent() -> None:
    """Run claude_agent.py to process all pending tasks in Needs_Action/."""
    if DRY_RUN:
        logger.info("  [DRY_RUN] Would run Claude agent")
        return
    try:
        result = subprocess.run(
            [sys.executable, Path(__file__).parent.parent / "claude_agent.py"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("  ✔ Claude agent run complete")
        else:
            logger.warning(f"  ✘ Claude agent exited with code {result.returncode}")
            if result.stderr:
                logger.debug(f"  stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        logger.warning("  ✘ Claude agent timed out (120s)")
    except Exception as exc:
        logger.warning(f"  ✘ Claude agent run failed: {exc}")


def rollback_for_deleted_inbox_file(deleted_inbox_name: str) -> None:
    """
    When an Inbox file is deleted, remove all vault artifacts that were created for it:
    Needs_Action (task + meta), Done (task + meta), Plans, Pending_Approval (task + meta + plan),
    and matching task_catalog.jsonl entries. Then refresh Dashboard.
    """
    deleted_name = deleted_inbox_name
    removed_na_stems: set[str] = set()  # needs_action file stems for catalog filter

    def safe_unlink(p: Path) -> bool:
        if p.exists():
            try:
                p.unlink()
                logger.info(f"  ✔ Removed {p.relative_to(VAULT_ROOT)}")
                return True
            except Exception as exc:
                logger.warning(f"  ✘ Could not remove {p.name}: {exc}")
        return False

    # ── Needs_Action: meta files with matching source_file ────────────────────
    if NEEDS_ACTION_DIR.exists():
        for meta_path in NEEDS_ACTION_DIR.glob("*_meta.md"):
            if _read_source_file_from_meta(meta_path) != deleted_name:
                continue
            dest_path_str = _read_destination_path_from_meta(meta_path)
            if dest_path_str:
                na_name = Path(dest_path_str).name
                na_stem = Path(dest_path_str).stem
                removed_na_stems.add(na_stem)
                task_path = NEEDS_ACTION_DIR / na_name
                safe_unlink(task_path)
            safe_unlink(meta_path)

    # ── Done: meta files with matching source_file → remove meta, task, and plan ─
    if DONE_DIR.exists():
        for meta_path in DONE_DIR.glob("*_meta.md"):
            if _read_source_file_from_meta(meta_path) != deleted_name:
                continue
            dest_path_str = _read_destination_path_from_meta(meta_path)
            if dest_path_str:
                removed_na_stems.add(Path(dest_path_str).stem)
            stem = meta_path.stem.replace("_meta", "")
            safe_unlink(meta_path)
            for task_path in DONE_DIR.glob(f"{stem}.*"):
                if task_path.suffix.lower() != ".md":
                    safe_unlink(task_path)
            plan_path = PLANS_DIR / f"{stem}_plan.md"
            safe_unlink(plan_path)

    # ── Pending_Approval: same as Done ────────────────────────────────────────
    if PENDING_APPROVAL_DIR.exists():
        for meta_path in PENDING_APPROVAL_DIR.glob("*_meta.md"):
            if _read_source_file_from_meta(meta_path) != deleted_name:
                continue
            dest_path_str = _read_destination_path_from_meta(meta_path)
            if dest_path_str:
                removed_na_stems.add(Path(dest_path_str).stem)
            stem = meta_path.stem.replace("_meta", "")
            safe_unlink(meta_path)
            for task_path in PENDING_APPROVAL_DIR.glob(f"{stem}.*"):
                if task_path.suffix.lower() != ".md":
                    safe_unlink(task_path)
            plan_here = PENDING_APPROVAL_DIR / f"{stem}_plan.md"
            safe_unlink(plan_here)
            plan_in_plans = PLANS_DIR / f"{stem}_plan.md"
            safe_unlink(plan_in_plans)

    # ── task_catalog.jsonl: drop lines whose "file" stem is in removed_na_stems ─
    if CATALOG_FILE.exists() and removed_na_stems:
        try:
            lines = CATALOG_FILE.read_text(encoding="utf-8").strip().splitlines()
            kept = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    file_val = obj.get("file", "")
                    stem = Path(file_val).stem
                    if stem in removed_na_stems:
                        logger.info(f"  ✔ Removed catalog entry: {file_val}")
                        continue
                    kept.append(line)
                except json.JSONDecodeError:
                    kept.append(line)
            CATALOG_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"  ✘ Could not update task_catalog.jsonl: {exc}")

    # ── Refresh Dashboard ────────────────────────────────────────────────────
    refresh_dashboard()


# ──────────────────────────────────────────────────────────────────────────────
# EVENT HANDLER
# ──────────────────────────────────────────────────────────────────────────────

class InboxEventHandler(FileSystemEventHandler):
    """
    Handles FileCreated events inside the Inbox/ directory.

    Pipeline per new file:
      detect → validate → wait-stable → copy → generate-metadata → log

    Safety guarantees:
      • Original file is NEVER deleted or modified.
      • Duplicate processing prevented via in-flight tracker.
      • Temp/hidden files are silently ignored.
      • All errors are caught and logged; never crash the observer thread.
    """

    # Files / extensions to silently ignore
    _IGNORE_NAMES = frozenset({".DS_Store", "Thumbs.db", ".gitkeep", ".gitignore"})
    _IGNORE_EXT   = frozenset({".tmp", ".part", ".crdownload", ".swp"})

    def __init__(self):
        super().__init__()
        self._in_flight: set[str] = set()   # Paths currently being processed

    # ── public ──────────────────────────────────────────────────────────────

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        if self._should_ignore(filepath):
            return
        if str(filepath) in self._in_flight:
            return

        self._in_flight.add(str(filepath))
        try:
            self._handle_new_file(filepath)
        except Exception as exc:
            logger.error(f"Unhandled error for {filepath.name}: {exc}", exc_info=True)
        finally:
            self._in_flight.discard(str(filepath))

    def on_deleted(self, event):
        """When an Inbox file is deleted, roll back all processing for that file."""
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        if self._should_ignore(filepath):
            return
        deleted_name = filepath.name
        logger.info(f"▶ Inbox file deleted: {deleted_name} — rolling back all related artifacts")
        try:
            if DRY_RUN:
                logger.info("  [DRY_RUN] Would roll back Needs_Action, Done, Plans, Pending_Approval, catalog")
                return
            rollback_for_deleted_inbox_file(deleted_name)
            logger.info(f"  ✅ Rollback complete for {deleted_name}")
        except Exception as exc:
            logger.error(f"Rollback error for {deleted_name}: {exc}", exc_info=True)

    # ── private ─────────────────────────────────────────────────────────────

    def _should_ignore(self, path: Path) -> bool:
        name = path.name
        if name.startswith("."):
            return True
        if name in self._IGNORE_NAMES:
            return True
        if path.suffix.lower() in self._IGNORE_EXT:
            return True
        # Don't re-process metadata files we ourselves created
        if name.endswith("_meta.md"):
            return True
        return False

    def _wait_for_stable(self, path: Path) -> bool:
        """
        Poll until the file size stops changing, indicating the write is complete.
        Returns True when stable, False on timeout or disappearance.
        """
        prev_size = -1
        elapsed   = 0.0
        while elapsed < FILE_STABILISE_TIMEOUT:
            try:
                size = path.stat().st_size
                if size == prev_size:
                    return True
                prev_size = size
            except FileNotFoundError:
                logger.warning(f"File vanished while waiting: {path.name}")
                return False
            except Exception as exc:
                logger.warning(f"Stability check error: {exc}")
            time.sleep(FILE_STABILISE_INTERVAL)
            elapsed += FILE_STABILISE_INTERVAL

        logger.warning(f"Stability timeout for {path.name}; proceeding anyway")
        return True   # Timeout is non-fatal; try to copy whatever is there

    def _handle_new_file(self, source: Path):
        """Core pipeline: detect → validate → refresh dashboard → copy → metadata → log."""
        logger.info(f"▶ New file detected: {source.name}")

        if not source.exists() or not source.is_file():
            logger.warning(f"  File no longer accessible: {source.name}")
            return

        if not self._wait_for_stable(source):
            logger.error(f"  Aborting unstable file: {source.name}")
            return

        # Update Dashboard immediately upon new Inbox content
        refresh_dashboard()

        # Build collision-safe destination name using timestamp prefix
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_stem = sanitize_filename(source.stem)
        dest_name = f"{ts}_{safe_stem}{source.suffix}"
        meta_name = f"{ts}_{safe_stem}_meta.md"
        dest_file = NEEDS_ACTION_DIR / dest_name
        meta_file = NEEDS_ACTION_DIR / meta_name

        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

        if DRY_RUN:
            logger.info(f"  [DRY_RUN] Would copy  → Needs_Action/{dest_name}")
            logger.info(f"  [DRY_RUN] Would write → Needs_Action/{meta_name}")
            return

        # ── Copy file ───────────────────────────────────────────────────────
        try:
            shutil.copy2(source, dest_file)
            logger.info(f"  ✔ Copied  → Needs_Action/{dest_name}")
        except Exception as exc:
            logger.error(f"  ✘ Copy failed: {exc}")
            return

        # ── Write metadata ──────────────────────────────────────────────────
        try:
            meta_content = generate_metadata_md(source, dest_file)
            meta_file.write_text(meta_content, encoding="utf-8")
            logger.info(f"  ✔ Metadata → Needs_Action/{meta_name}")
        except Exception as exc:
            # Non-fatal: the copy succeeded; metadata failure should not block
            logger.error(f"  ✘ Metadata write failed (non-fatal): {exc}")

        # ── Refresh Dashboard so it reflects new Needs_Action count ──────────
        refresh_dashboard()

        # ── Run Claude agent to process the new task(s) in Needs_Action ───────
        run_agent()

        # ── Update Dashboard after task processing (same as rollback) ──────────
        refresh_dashboard()

        # [RW_HOOK] Gold tier: emit event to Ralph Wiggum loop here
        try:
            size_info = f"[{dest_file.stat().st_size:,} bytes]"
        except OSError:
            # File may have already been moved to Done/ by the agent
            size_info = f"[{source.stat().st_size:,} bytes — processed]"
        logger.info(f"  ✅ Done | {source.name} → Needs_Action/{dest_name} {size_info}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    logger.info("═" * 62)
    logger.info(f"  VaultWatcher v{WATCHER_VERSION} — Bronze Tier")
    logger.info("═" * 62)

    if DRY_RUN:
        logger.info("  *** DRY_RUN MODE — No files will be modified ***")

    for directory in [INBOX_DIR, NEEDS_ACTION_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    logger.info(f"  Vault Root : {VAULT_ROOT.resolve()}")
    logger.info(f"  Watching   : {INBOX_DIR.resolve()}")
    logger.info(f"  Output     : {NEEDS_ACTION_DIR.resolve()}")
    logger.info(f"  Log        : {LOG_FILE.resolve()}")
    logger.info("─" * 62)
    logger.info("  Watcher active. Drop files into Inbox/ to begin.")
    logger.info("  Press Ctrl+C to stop safely.")
    logger.info("─" * 62)

    handler  = InboxEventHandler()
    observer = Observer()
    observer.schedule(handler, str(INBOX_DIR), recursive=False)
    observer.start()

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received — stopping observer…")
        observer.stop()

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except Exception as exc:
        logger.error(f"Observer error: {exc}")
        observer.stop()
        observer.join()

    logger.info("VaultWatcher stopped cleanly. Goodbye.")


if __name__ == "__main__":
    main()
