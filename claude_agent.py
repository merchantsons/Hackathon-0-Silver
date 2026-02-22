"""
claude_agent.py — AI Employee Claude Agent (Silver Tier)
=========================================================
Reasoning + Action layers of the Perception → Reasoning → Action architecture.

Silver Tier upgrades over Bronze:
  • LLMReasoner — Claude Code reasoning (Claude API) for intelligent task analysis
  • EmailDrafter — AI-generated email draft responses
  • LinkedInContentGenerator — AI-generated LinkedIn posts for business
  • Enhanced TaskClassifier — detects email, LinkedIn, and external-action tasks
  • Enhanced PlanGenerator — LLM-powered contextual plans
  • Enhanced DashboardUpdater — Silver metrics + AI summaries
  • ActionProcessor — handles email/LinkedIn via approval workflow
  • All AI logic exposed as Agent Skills

Usage:
    python claude_agent.py                    # Process all pending tasks
    python claude_agent.py --dry-run          # Simulate; no file changes
    python claude_agent.py --update-dashboard # Dashboard refresh only
    python claude_agent.py --scan             # List tasks without processing
    python claude_agent.py --briefing         # Generate Monday CEO Briefing

Environment:
    CLAUDE_API_KEY / ANTHROPIC_API_KEY   Claude Code reasoning (Silver LLM)
    DRY_RUN=true        Enable dry-run mode
    DEV_MODE=true       Use simulated LLM responses (no API key needed)
"""

import os
import sys
import json
import shutil
import logging
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Optional

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Fix Windows console encoding
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
INBOX_DIR            = VAULT_ROOT / "Inbox"
NEEDS_ACTION_DIR     = VAULT_ROOT / "Needs_Action"
DONE_DIR             = VAULT_ROOT / "Done"
PLANS_DIR            = VAULT_ROOT / "Plans"
PENDING_APPROVAL_DIR = VAULT_ROOT / "Pending_Approval"
APPROVED_DIR         = VAULT_ROOT / "Approved"
REJECTED_DIR         = VAULT_ROOT / "Rejected"
LOGS_DIR             = VAULT_ROOT / "Logs"
SKILLS_DIR           = VAULT_ROOT / "Skills"
BRIEFINGS_DIR        = VAULT_ROOT / "Briefings"
DASHBOARD_FILE       = VAULT_ROOT / "Dashboard.md"
HANDBOOK_FILE        = VAULT_ROOT / "Company_Handbook.md"
GOALS_FILE           = VAULT_ROOT / "Business_Goals.md"
CATALOG_FILE         = LOGS_DIR / "task_catalog.jsonl"

AGENT_VERSION = "2.0.0"
TIER          = "silver"

DRY_RUN  = os.environ.get("DRY_RUN",  "false").lower() in ("true", "1", "yes")
DEV_MODE = os.environ.get("DEV_MODE", "false").lower() in ("true", "1", "yes")

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────────────────────

LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOGS_DIR / "agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ClaudeAgent")


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 0 — LLM REASONER  (Silver Tier)
# See: Skills/llm_reasoner.md
# ══════════════════════════════════════════════════════════════════════════════

class LLMReasoner:
    """
    Claude Code reasoning engine — Silver-tier intelligent reasoning via Claude API.

    Falls back to rule-based responses when:
      • Claude API key (ANTHROPIC_API_KEY) is not set, or
      • DEV_MODE=true is set (useful for offline demos)

    All prompts are context-enriched with Company_Handbook.md and
    Business_Goals.md so Claude acts as a true company employee.
    """

    _client   = None
    _handbook = None
    _goals    = None

    @classmethod
    def _get_client(cls):
        if cls._client is not None:
            return cls._client
        api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("CLAUDE_API_KEY", "")
        if not api_key or DEV_MODE:
            return None
        try:
            import anthropic  # Claude Code uses this API for reasoning
            cls._client = anthropic.Anthropic(api_key=api_key)
            logger.info("LLMReasoner: Claude Code reasoning engine ready")
            return cls._client
        except ImportError:
            logger.warning("LLMReasoner: pip install anthropic (Claude API SDK)")
            return None
        except Exception as exc:
            logger.warning(f"LLMReasoner: init failed: {exc}")
            return None

    @classmethod
    def _load_context(cls) -> str:
        """Load Company_Handbook + Business_Goals as system context."""
        if cls._handbook is None:
            try:
                cls._handbook = HANDBOOK_FILE.read_text(encoding="utf-8") if HANDBOOK_FILE.exists() else ""
            except Exception:
                cls._handbook = ""
        if cls._goals is None:
            try:
                cls._goals = GOALS_FILE.read_text(encoding="utf-8") if GOALS_FILE.exists() else ""
            except Exception:
                cls._goals = ""
        parts = []
        if cls._handbook:
            parts.append(f"=== COMPANY HANDBOOK ===\n{cls._handbook}")
        if cls._goals:
            parts.append(f"=== BUSINESS GOALS ===\n{cls._goals}")
        return "\n\n".join(parts)

    @classmethod
    def complete(cls, prompt: str, system_extra: str = "", max_tokens: int = 1024) -> str:
        """
        Send a prompt to Claude and return the text response.
        Falls back to a placeholder string if Claude is unavailable.
        """
        client = cls._get_client()
        if client is None:
            return cls._fallback(prompt)

        context = cls._load_context()
        system  = (
            "You are an AI Employee assistant. You help process tasks, draft communications, "
            "and generate business content. Be concise, professional, and actionable.\n\n"
            f"{context}\n\n{system_extra}".strip()
        )
        try:
            msg = client.messages.create(
                model   ="claude-opus-4-5",
                max_tokens=max_tokens,
                system  =system,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        except Exception as exc:
            logger.warning(f"LLMReasoner.complete failed: {exc}")
            return cls._fallback(prompt)

    @classmethod
    def _fallback(cls, prompt: str) -> str:
        """Rule-based fallback when Claude API is unavailable."""
        return f"[DEV_MODE/OFFLINE] Simulated AI response for prompt: {prompt[:100]}..."

    @classmethod
    def is_available(cls) -> bool:
        """True if Claude API key is set and reasoning engine is available."""
        return cls._get_client() is not None


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 1 — VAULT READER
# See: Skills/vault_reader.md
# ══════════════════════════════════════════════════════════════════════════════

class VaultReader:
    """Reads content and lists files from the vault."""

    @staticmethod
    def read_file(path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error(f"VaultReader.read_file({path.name}): {exc}")
            return None

    @staticmethod
    def list_files(directory: Path, suffix: str = None) -> list[Path]:
        if not directory.exists():
            return []
        try:
            files = [f for f in directory.iterdir() if f.is_file()]
            if suffix:
                files = [f for f in files if f.suffix.lower() == suffix.lower()]
            return sorted(files, key=lambda f: f.stat().st_mtime)
        except Exception as exc:
            logger.error(f"VaultReader.list_files({directory.name}): {exc}")
            return []

    @staticmethod
    def scan_needs_action() -> list[dict]:
        """
        Scan Needs_Action/ and return task descriptors.

        Handles two file categories:
        1. Non-.md files (Bronze: from watchers/file_system_watcher.py) — paired with _meta.md
        2. .md action files (Silver: from gmail_watcher, linkedin_watcher)
           These are identified by YAML frontmatter with type: email or
           type: linkedin_notification.
        """
        import re

        all_files = VaultReader.list_files(NEEDS_ACTION_DIR)
        meta_names = {f.name for f in all_files if f.stem.endswith("_meta")}

        # Non-.md task files (Bronze pattern)
        non_md_tasks = [
            f for f in all_files
            if f.name not in meta_names and f.suffix.lower() != ".md"
        ]

        # .md action files from Silver watchers (email, LinkedIn)
        ACTION_TYPES = {"email", "linkedin_notification"}
        silver_action_files = []
        for f in all_files:
            if f.suffix.lower() != ".md":
                continue
            if f.stem.endswith("_meta"):
                continue
            # Peek at frontmatter to identify action type
            try:
                first_lines = f.read_text(encoding="utf-8")[:300]
                m = re.search(r'^type:\s*(\w+)', first_lines, re.MULTILINE)
                if m and m.group(1) in ACTION_TYPES:
                    silver_action_files.append(f)
            except Exception:
                pass

        tasks = []

        # Process Bronze-pattern files
        for tf in non_md_tasks:
            meta_name = tf.stem + "_meta.md"
            meta_path = NEEDS_ACTION_DIR / meta_name
            content   = VaultReader.read_file(tf) if tf.suffix.lower() == ".txt" else None
            tasks.append({
                "task_file"   : tf,
                "meta_file"   : meta_path if meta_path.exists() else None,
                "meta_content": VaultReader.read_file(meta_path) if meta_path.exists() else None,
                "file_content": content,
                "name"        : tf.name,
                "stem"        : tf.stem,
                "extension"   : tf.suffix.lower(),
                "size"        : tf.stat().st_size,
                "modified"    : datetime.fromtimestamp(tf.stat().st_mtime),
            })

        # Process Silver-pattern .md action files
        for tf in silver_action_files:
            content = VaultReader.read_file(tf)
            tasks.append({
                "task_file"   : tf,
                "meta_file"   : None,
                "meta_content": None,
                "file_content": content,
                "name"        : tf.name,
                "stem"        : tf.stem,
                "extension"   : ".md",
                "size"        : tf.stat().st_size,
                "modified"    : datetime.fromtimestamp(tf.stat().st_mtime),
                "is_action_md": True,  # Flag: this IS the action file
            })

        return tasks

    @staticmethod
    def scan_approved() -> list[dict]:
        """Scan Approved/ folder for human-approved action files."""
        all_files = VaultReader.list_files(APPROVED_DIR)
        approved = []
        for f in all_files:
            if f.suffix.lower() == ".md":
                content = VaultReader.read_file(f)
                approved.append({
                    "path"    : f,
                    "name"    : f.name,
                    "content" : content or "",
                })
        return approved


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 2 — VAULT WRITER
# See: Skills/vault_writer.md
# ══════════════════════════════════════════════════════════════════════════════

class VaultWriter:
    """Writes and appends files in the vault."""

    @staticmethod
    def write(path: Path, content: str, overwrite: bool = True) -> bool:
        if path.exists() and not overwrite:
            logger.warning(f"VaultWriter.write: exists, overwrite=False: {path.name}")
            return False
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would write {len(content):,} bytes → {path}")
            return True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.debug(f"Written: {path.name} ({len(content):,} bytes)")
            return True
        except Exception as exc:
            logger.error(f"VaultWriter.write({path.name}): {exc}")
            return False

    @staticmethod
    def append(path: Path, content: str) -> bool:
        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would append to: {path.name}")
            return True
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(content)
            return True
        except Exception as exc:
            logger.error(f"VaultWriter.append({path.name}): {exc}")
            return False


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 3 — TASK CLASSIFIER  (Silver: LLM-enhanced)
# See: Skills/task_classifier.md
# ══════════════════════════════════════════════════════════════════════════════

class TaskClassifier:
    """
    Classifies tasks by type, priority, required action, and approval need.

    Silver: Uses LLMReasoner for uncertain/mixed signals; falls back to
    rule-based classification when Claude is unavailable.
    """

    _TYPE_MAP: dict[str, list[str]] = {
        "document"   : [".pdf", ".docx", ".doc", ".rtf", ".odt"],
        "spreadsheet": [".xlsx", ".xls", ".ods"],
        "image"      : [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
        "code"       : [".py", ".js", ".ts", ".html", ".css", ".json", ".yaml",
                        ".yml", ".sh", ".bat", ".ps1", ".rb", ".go"],
        "email"      : [".eml", ".msg"],
        "archive"    : [".zip", ".tar", ".gz", ".7z", ".rar"],
        "note"       : [".txt", ".md"],
        "data"       : [".csv", ".tsv", ".xml"],
    }

    _PRIORITY_KEYWORDS: dict[str, list[str]] = {
        "urgent": ["urgent", "asap", "critical", "emergency", "immediate"],
        "high"  : ["important", "high", "priority", "deadline", "needed"],
        "low"   : ["low", "minor", "optional", "sometime", "fyi"],
    }

    _ACTION_MAP: dict[str, str] = {
        "document"   : "read_and_classify",
        "spreadsheet": "analyze_and_report",
        "image"      : "catalog_and_archive",
        "code"       : "review_code",
        "email"      : "parse_and_respond",
        "archive"    : "extract_and_catalog",
        "note"       : "read_and_classify",
        "data"       : "analyze_and_report",
        "unknown"    : "general_processing",
    }

    _KEYWORD_ACTIONS: dict[str, str] = {
        "review"  : "read_and_classify",
        "report"  : "generate_summary",
        "summary" : "generate_summary",
        "task"    : "process_task_list",
        "todo"    : "process_task_list",
        "meeting" : "generate_summary",
        "invoice" : "generate_summary",
        "email"   : "parse_and_respond",
        "gmail"   : "parse_and_respond",
        "linkedin": "linkedin_content",
        "post"    : "linkedin_content",
        "social"  : "linkedin_content",
    }

    @classmethod
    def classify(cls, task: dict) -> dict:
        """Classify a task. Silver tier: attempts LLM classification first."""
        import re

        name_lower = task["name"].lower()
        ext        = task["extension"]

        # For .md action files from Silver watchers, read type from frontmatter
        if task.get("is_action_md") and task.get("file_content"):
            m = re.search(r'^type:\s*(\w+)', task["file_content"][:200], re.MULTILINE)
            if m:
                ftype = m.group(1)
                if ftype == "email":
                    ext = ".eml"  # Force email type
                elif ftype == "linkedin_notification":
                    name_lower = "linkedin " + name_lower  # Force linkedin detection

        # For plain .txt/.md files, peek at content to detect email format
        # (handles files exported/saved as .txt with standard email headers)
        if ext in (".txt", ".md") and task.get("file_content"):
            content_head = task["file_content"][:400]
            email_header_re = re.compile(
                r'^(From|To|Subject|Date|Reply-To|Cc|Bcc)\s*:',
                re.MULTILINE | re.IGNORECASE,
            )
            if len(email_header_re.findall(content_head)) >= 2:
                ext = ".eml"  # Treat as email

        # Rule-based classification (fast path)
        task_type = "unknown"
        for tname, exts in cls._TYPE_MAP.items():
            if ext in exts:
                task_type = tname
                break

        priority = "medium"
        for level, keywords in cls._PRIORITY_KEYWORDS.items():
            if any(kw in name_lower for kw in keywords):
                priority = level
                break

        action = cls._ACTION_MAP.get(task_type, "general_processing")
        # Email and LinkedIn types always use their canonical actions (no keyword override)
        if task_type not in {"email"} and "linkedin" not in name_lower:
            for kw, kw_action in cls._KEYWORD_ACTIONS.items():
                if kw in name_lower:
                    action = kw_action
                    break

        requires_approval = (
            priority == "urgent"
            or task_type in {"email", "code"}
            or action in {"parse_and_respond", "linkedin_content"}
        )

        base_classification = {
            **task,
            "task_type"        : task_type,
            "priority"         : priority,
            "action"           : action,
            "requires_approval": requires_approval,
        }

        # Silver: enrich with LLM when file content is available
        if LLMReasoner.is_available() and task.get("file_content"):
            try:
                enriched = cls._llm_classify(base_classification)
                base_classification.update(enriched)
            except Exception as exc:
                logger.warning(f"LLM classification failed, using rule-based: {exc}")

        base_classification["classifier_version"] = f"{AGENT_VERSION}-silver"
        return base_classification

    @classmethod
    def _llm_classify(cls, task: dict) -> dict:
        """Use LLM to refine classification based on file content."""
        content_preview = (task.get("file_content") or "")[:500]
        prompt = f"""Classify this task file for an AI Employee system.

File: {task['name']}
Type: {task['task_type']}
Content preview: {content_preview}

Return JSON with ONLY these fields:
{{
  "priority": "urgent|high|medium|low",
  "action": "read_and_classify|generate_summary|process_task_list|analyze_and_report|parse_and_respond|linkedin_content|review_code|general_processing",
  "requires_approval": true/false,
  "ai_summary": "one sentence describing what this task is about"
}}"""
        response = LLMReasoner.complete(prompt, max_tokens=256)
        try:
            import re
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return {"ai_summary": response[:200]}


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 4 — PLAN GENERATOR  (Silver: LLM-powered)
# See: Skills/plan_generator.md
# ══════════════════════════════════════════════════════════════════════════════

class PlanGenerator:
    """
    Generates Plan.md checklists for classified tasks.

    Silver: LLM generates contextual, business-aware plans.
    Falls back to template-based plans when LLM unavailable.
    """

    _STEPS: dict[str, list[str]] = {
        "read_and_classify": [
            "Open and read the file content in full",
            "Identify the document type and primary subject",
            "Extract key information (who, what, when, why)",
            "Summarise in 3–5 bullet points",
            "Tag with relevant labels and categories",
            "Determine if any action items are present",
            "Archive or route to the appropriate folder",
            "Update Dashboard.md with findings",
        ],
        "generate_summary": [
            "Read the full document",
            "Identify main topics and key findings",
            "Write executive summary (≤ 200 words)",
            "List concrete action items and owners",
            "Note any deadlines or hard dependencies",
            "Save summary to Plans/",
            "Update Dashboard.md with summary link",
        ],
        "process_task_list": [
            "Parse all task items from the file",
            "Sort by urgency × importance (Eisenhower matrix)",
            "Identify dependencies between tasks",
            "Assign effort estimate (S / M / L)",
            "Flag tasks that require human decision",
            "Create structured breakdown in Plans/",
            "Update Dashboard.md task queue",
        ],
        "analyze_and_report": [
            "Open file and validate its structure",
            "Identify schema, column types, and row count",
            "Check for missing values or anomalies",
            "Compute basic summary statistics",
            "Identify patterns or trends",
            "Generate insight report in Plans/",
            "Update Dashboard.md with findings",
        ],
        "parse_and_respond": [
            "Parse headers: sender, recipient, date, subject",
            "Extract body content and attachments list",
            "Identify urgency indicators",
            "Extract action items from body",
            "Generate AI draft response via EmailDrafter",
            "Write draft to Pending_Approval/ for human review",
            "After approval: send via Email MCP server",
            "Log to Logs/ audit trail",
        ],
        "linkedin_content": [
            "Analyse business context from Business_Goals.md",
            "Generate 3 LinkedIn post variations via LinkedInContentGenerator",
            "Score each for engagement potential",
            "Write best post draft to Pending_Approval/",
            "After human approval: post via LinkedIn Watcher",
            "Log post timestamp and engagement metrics",
            "Update Dashboard.md with latest post info",
        ],
        "review_code": [
            "Read and understand the code structure",
            "Check for syntax and obvious logic errors",
            "Review algorithms for correctness",
            "Identify potential security concerns",
            "Note test coverage gaps",
            "Generate code-review summary in Plans/",
            "Flag items requiring developer follow-up",
        ],
        "catalog_and_archive": [
            "Verify file integrity (size / hash check)",
            "Determine file type and intended purpose",
            "Generate descriptive canonical filename",
            "Add entry to asset catalog",
            "Move to appropriate archive subfolder",
            "Update asset index in Plans/",
        ],
        "extract_and_catalog": [
            "Verify archive is not corrupted",
            "List archive contents without extracting",
            "Assess safety of contents",
            "Extract to a sandboxed staging folder",
            "Catalog extracted files",
            "Route individual files to appropriate folders",
            "Update asset index",
        ],
        "general_processing": [
            "Read and understand the file",
            "Determine the most appropriate handling approach",
            "Apply standard processing rules",
            "Document key findings in a note",
            "Route to appropriate vault folder",
            "Update Dashboard.md",
        ],
    }

    @classmethod
    def generate(cls, task: dict) -> str:
        """Generate Plan.md content. Silver: uses LLM for contextual plans."""
        now    = datetime.now()
        action = task.get("action", "general_processing")
        ai_summary = task.get("ai_summary", "")

        # Try LLM plan generation for Silver
        llm_steps_block = ""
        if LLMReasoner.is_available() and task.get("file_content"):
            llm_steps_block = cls._llm_generate_steps(task)

        steps     = cls._get_steps(action)
        checklist = "\n".join(f"- [ ] {s}" for s in steps)

        approval_block = ""
        if task.get("requires_approval"):
            action_hint = {
                "parse_and_respond": "email draft",
                "linkedin_content" : "LinkedIn post",
                "code"             : "code execution",
            }.get(action, "sensitive action")
            approval_block = f"""
## ⚠️ Human Approval Required

This task involves a **{action_hint}** and requires your review before the AI Employee acts.

**Action file placed in:** `Pending_Approval/`

To proceed:
- **Approve** → Move the approval file to `Approved/`
- **Reject**  → Move to `Rejected/`
- **Modify**  → Edit the draft, then move to `Approved/`
"""

        ai_insights = ""
        if ai_summary:
            ai_insights = f"""
## 🤖 AI Analysis

{ai_summary}
"""
        if llm_steps_block:
            ai_insights += f"\n{llm_steps_block}"

        return f"""---
title: "Plan: {task['name']}"
task_file: "{task['name']}"
task_type: "{task.get('task_type', 'unknown')}"
priority: "{task.get('priority', 'medium')}"
action: "{action}"
requires_approval: {str(task.get('requires_approval', False)).lower()}
created: "{now.strftime('%Y-%m-%d %H:%M:%S')}"
status: "pending"
tier: "{TIER}"
llm_assisted: {str(bool(ai_summary)).lower()}
---

# Plan: {task['name']}

| Field | Value |
|-------|-------|
| Created | {now.strftime('%Y-%m-%d %H:%M:%S')} |
| File | `{task['name']}` |
| Type | {task.get('task_type', 'unknown').replace('_', ' ').title()} |
| Priority | **{task.get('priority', 'medium').upper()}** |
| Action | {action.replace('_', ' ').title()} |
| Size | {task.get('size', 0):,} bytes |
| Detected | {task.get('modified', now).strftime('%Y-%m-%d %H:%M:%S')} |
| Requires Approval | {'**Yes ⚠️**' if task.get('requires_approval') else 'No'} |
| LLM Assisted | {'Yes ✨' if ai_summary else 'No (rule-based)'} |
{approval_block}
{ai_insights}
## Execution Checklist

{checklist}

## Observations

*Record notes here during execution.*

## Completion Checklist

- [ ] All execution steps completed
- [ ] Observations documented above
- [ ] Dashboard.md updated
- [ ] Task file moved to `Done/`
- [ ] Catalog entry written to `Logs/task_catalog.jsonl`

---
*Generated by PlanGenerator v{AGENT_VERSION} (Silver Tier)*
"""

    @classmethod
    def _llm_generate_steps(cls, task: dict) -> str:
        """Ask LLM to generate task-specific action steps."""
        content_preview = (task.get("file_content") or "")[:300]
        prompt = f"""Generate 5 specific action steps for this task:
File: {task['name']}
Type: {task.get('task_type')}
Action type: {task.get('action')}
Content: {content_preview}

Format as a markdown checklist:
- [ ] step 1
- [ ] step 2
...

Be specific to this file's actual content."""
        response = LLMReasoner.complete(prompt, max_tokens=300)
        if "- [ ]" in response or "- [x]" in response:
            return f"## 🤖 AI-Generated Task Steps\n\n{response}"
        return ""

    @classmethod
    def _get_steps(cls, action: str) -> list[str]:
        return cls._STEPS.get(action, cls._STEPS["general_processing"])


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 5 — FILE MOVER
# See: Skills/file_mover.md
# ══════════════════════════════════════════════════════════════════════════════

class FileMover:
    """Safely moves or copies files between vault folders (copy-verify-delete)."""

    @staticmethod
    def move(source: Path, dest_dir: Path, new_name: str = None) -> Optional[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_name = new_name or source.name
        dest_path = FileMover._safe_path(dest_dir / dest_name)

        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would move: {source.name} → {dest_dir.name}/{dest_path.name}")
            return dest_path

        try:
            shutil.copy2(source, dest_path)
            if not dest_path.exists():
                raise RuntimeError("Destination not found after copy")
            if dest_path.stat().st_size != source.stat().st_size:
                raise RuntimeError("Size mismatch after copy")
            source.unlink()
            logger.info(f"Moved: {source.name} → {dest_dir.name}/{dest_path.name}")
            return dest_path
        except Exception as exc:
            logger.error(f"FileMover.move({source.name}): {exc}")
            if dest_path.exists() and source.exists():
                try:
                    dest_path.unlink()
                except Exception:
                    pass
            return None

    @staticmethod
    def copy_to(source: Path, dest_dir: Path, new_name: str = None) -> Optional[Path]:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = FileMover._safe_path(dest_dir / (new_name or source.name))

        if DRY_RUN:
            logger.info(f"[DRY_RUN] Would copy: {source.name} → {dest_dir.name}/")
            return dest_path

        try:
            shutil.copy2(source, dest_path)
            return dest_path
        except Exception as exc:
            logger.error(f"FileMover.copy_to({source.name}): {exc}")
            return None

    @staticmethod
    def _safe_path(path: Path) -> Path:
        if not path.exists():
            return path
        counter = 1
        while True:
            candidate = path.parent / f"{path.stem}_{counter}{path.suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 6 — EMAIL DRAFTER  (Silver Tier)
# See: Skills/email_sender.md
# ══════════════════════════════════════════════════════════════════════════════

class EmailDrafter:
    """
    Generates AI-drafted email responses using LLMReasoner.

    The draft is written to Pending_Approval/ — it is NEVER sent
    automatically. A human must move it to Approved/ first.
    The Orchestrator then picks it up and calls the Email MCP server.
    """

    @classmethod
    def draft_response(cls, task: dict) -> Optional[Path]:
        """
        Generate an email draft for a task file containing email context.
        Returns the path to the approval request file in Pending_Approval/.
        """
        now      = datetime.now()
        ts       = now.strftime("%Y%m%d_%H%M%S")
        content  = task.get("file_content") or task.get("meta_content") or ""
        filename = task.get("name", "unknown")

        # Extract sender / subject from content
        sender  = cls._extract_field(content, "from", "Unknown Sender")
        subject = cls._extract_field(content, "subject", "No Subject")
        body    = content[:1000] if content else "(no body)"

        # Generate draft via LLM
        if LLMReasoner.is_available():
            draft_body = LLMReasoner.complete(
                f"""Draft a professional, helpful email reply to this message:

FROM: {sender}
SUBJECT: {subject}
BODY:
{body}

Write ONLY the email body (no subject line, no headers). Keep it under 200 words.""",
                max_tokens=400,
            )
        else:
            draft_body = (
                f"Thank you for your email regarding '{subject}'. "
                f"I have received your message and will review it shortly. "
                f"[AI Employee draft — please personalise before sending]"
            )

        # Create approval request file
        approval_content = f"""---
type: approval_request
action: send_email
to: "{sender}"
subject: "Re: {subject}"
original_file: "{filename}"
created: "{now.isoformat()}"
expires: "{now.replace(hour=23, minute=59).isoformat()}"
status: pending
tier: {TIER}
---

# Email Reply Draft

## Original Email
- **From:** {sender}
- **Subject:** {subject}
- **Received:** {now.strftime('%Y-%m-%d %H:%M:%S')}

## Proposed Reply

> {draft_body}

---

## ✅ Approve
Move this file to `Approved/` to send the email above.

## ❌ Reject
Move this file to `Rejected/` to discard.

## ✏️ Modify
Edit the "Proposed Reply" section above, then move to `Approved/`.

---
*Generated by EmailDrafter v{AGENT_VERSION} (Silver Tier)*
"""
        approval_path = PENDING_APPROVAL_DIR / f"{ts}_email_reply_{task['stem']}.md"
        PENDING_APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

        if VaultWriter.write(approval_path, approval_content):
            logger.info(f"EmailDrafter: Draft → Pending_Approval/{approval_path.name}")
            return approval_path
        return None

    @staticmethod
    def _extract_field(text: str, field: str, default: str) -> str:
        import re
        # Strip BOM and normalise line endings before searching
        text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        pattern = rf'^{field}\s*:\s*"?([^"\n]+)"?'
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else default


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 7 — LINKEDIN CONTENT GENERATOR  (Silver Tier)
# See: Skills/linkedin_poster.md
# ══════════════════════════════════════════════════════════════════════════════

class LinkedInContentGenerator:
    """
    Generates business LinkedIn posts using LLMReasoner.

    Posts are written to Pending_Approval/ first.
    After human approval the LinkedIn Watcher posts them.
    This creates a safe, auditable social media workflow.
    """

    _POST_TYPES = [
        "thought_leadership",
        "product_update",
        "client_success",
        "industry_insight",
        "team_culture",
    ]

    @classmethod
    def generate_post(cls, context: str = "", post_type: str = "thought_leadership") -> Optional[Path]:
        """
        Generate a LinkedIn post and write to Pending_Approval/.
        Returns the approval request path.
        """
        now = datetime.now()
        ts  = now.strftime("%Y%m%d_%H%M%S")

        goals_content = ""
        if GOALS_FILE.exists():
            try:
                goals_content = GOALS_FILE.read_text(encoding="utf-8")[:500]
            except Exception:
                pass

        if LLMReasoner.is_available():
            post_body = LLMReasoner.complete(
                f"""Write a professional LinkedIn post for our business.

Post type: {post_type}
Business context: {context or 'General business update'}
Business goals: {goals_content or 'Growing our client base and revenue'}

Requirements:
- 150–300 words
- Professional yet engaging tone
- Include 3–5 relevant hashtags at the end
- Start with a hook (compelling first line)
- Include a clear call-to-action
- NO generic filler phrases

Write ONLY the post content.""",
                max_tokens=500,
            )
        else:
            post_body = (
                f"🚀 Excited to share an update from our team!\n\n"
                f"{context or 'We are continuing to deliver exceptional value to our clients.'}\n\n"
                f"Our team is dedicated to innovation and excellence every day.\n\n"
                f"What challenges are you solving in your business? Let us know below! 👇\n\n"
                f"#Business #Innovation #Growth #AI #Technology"
            )

        approval_content = f"""---
type: approval_request
action: linkedin_post
post_type: "{post_type}"
created: "{now.isoformat()}"
status: pending
tier: {TIER}
character_count: {len(post_body)}
---

# LinkedIn Post Draft

**Post Type:** {post_type.replace('_', ' ').title()}
**Created:** {now.strftime('%Y-%m-%d %H:%M:%S')}
**Characters:** {len(post_body)}

## Proposed Post

---

{post_body}

---

## ✅ Approve
Move this file to `Approved/` to publish this post via LinkedIn.

## ❌ Reject
Move this file to `Rejected/` to discard.

## ✏️ Modify
Edit the "Proposed Post" section above, then move to `Approved/`.

---
*Generated by LinkedInContentGenerator v{AGENT_VERSION} (Silver Tier)*
"""
        approval_path = PENDING_APPROVAL_DIR / f"{ts}_linkedin_post_{post_type}.md"
        PENDING_APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

        if VaultWriter.write(approval_path, approval_content):
            logger.info(f"LinkedInContentGenerator: Draft → Pending_Approval/{approval_path.name}")
            return approval_path
        return None

    @classmethod
    def generate_from_business_goals(cls) -> Optional[Path]:
        """Generate a LinkedIn post based on current business goals."""
        context = ""
        if GOALS_FILE.exists():
            try:
                context = GOALS_FILE.read_text(encoding="utf-8")[:800]
            except Exception:
                pass
        return cls.generate_post(context=context, post_type="thought_leadership")


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 8 — DASHBOARD UPDATER  (Silver: AI summaries)
# See: Skills/dashboard_updater.md
# ══════════════════════════════════════════════════════════════════════════════

class DashboardUpdater:
    """
    Regenerates Dashboard.md with Silver-tier enhancements:
    - AI-powered status summary
    - Integration health for Gmail/LinkedIn watchers
    - Pending approval breakdown by type
    """

    @staticmethod
    def update() -> bool:
        now = datetime.now()

        inbox_files    = VaultReader.list_files(INBOX_DIR)
        na_files       = VaultReader.list_files(NEEDS_ACTION_DIR)
        done_files     = VaultReader.list_files(DONE_DIR)
        plan_files     = VaultReader.list_files(PLANS_DIR, ".md")
        pending_files  = VaultReader.list_files(PENDING_APPROVAL_DIR)
        approved_files = VaultReader.list_files(APPROVED_DIR)
        rejected_files = VaultReader.list_files(REJECTED_DIR)
        briefing_files = VaultReader.list_files(BRIEFINGS_DIR) if BRIEFINGS_DIR.exists() else []

        task_files = [f for f in na_files if not f.stem.endswith("_meta")
                      and f.suffix.lower() != ".md"]

        done_today = [f for f in done_files
                      if datetime.fromtimestamp(f.stat().st_mtime).date() == now.date()]

        # Categorise pending approvals
        email_pending    = [f for f in pending_files if "email" in f.name.lower()]
        linkedin_pending = [f for f in pending_files if "linkedin" in f.name.lower()]
        other_pending    = [f for f in pending_files
                            if "email" not in f.name.lower() and "linkedin" not in f.name.lower()]

        # Pending tasks table
        if task_files:
            rows = []
            for f in task_files[:15]:
                age = int((now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 60)
                rows.append(f"| `{f.name}` | {age}m ago | Pending | Medium |")
            pending_table = "\n".join(rows)
        else:
            pending_table = "| — | — | — | — |"

        # Done today table
        if done_today:
            rows = []
            for f in done_today[:15]:
                t = datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M")
                rows.append(f"| `{f.name}` | {t} | ✅ Completed |")
            done_table = "\n".join(rows)
        else:
            done_table = "| — | — | — |"

        # Approval breakdown table
        approval_rows = []
        for f in (email_pending + linkedin_pending + other_pending)[:10]:
            age = int((now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 60)
            kind = "📧 Email" if "email" in f.name.lower() else ("💼 LinkedIn" if "linkedin" in f.name.lower() else "📋 Task")
            approval_rows.append(f"| `{f.name}` | {kind} | {age}m ago |")
        approval_table = "\n".join(approval_rows) if approval_rows else "| — | — | — |"

        # Alerts
        alerts = []
        if len(task_files) > 10:
            alerts.append(f"- ⚠️ **High load:** {len(task_files)} items awaiting action")
        if pending_files:
            alerts.append(f"- 🔔 **Approval needed:** {len(pending_files)} item(s) — {len(email_pending)} emails, {len(linkedin_pending)} LinkedIn posts")
        if len(inbox_files) > 5:
            alerts.append(f"- 📥 **Inbox filling:** {len(inbox_files)} items unprocessed")
        if not LLMReasoner.is_available():
            alerts.append("- 🤖 **LLM offline:** Set Claude API key for AI reasoning (running rule-based mode)")
        alert_section = "\n".join(alerts) if alerts else "- ✅ No active alerts"

        # Check integration health
        gmail_status    = "🟡 Not configured" if not os.environ.get("GMAIL_CLIENT_ID") else "🟢 Active"
        linkedin_status = "🟡 Not configured" if not os.environ.get("LINKEDIN_EMAIL") else "🟢 Active"
        llm_status      = "🟢 Active" if LLMReasoner.is_available() else "🟡 Rule-based (no API key)"

        content = f"""---
last_updated: "{now.strftime('%Y-%m-%d %H:%M:%S')}"
system: "AI Employee - Silver Tier"
auto_generated: true
tier: silver
---

# 🤖 AI Employee — Dashboard

> **Last Updated:** {now.strftime('%A, %B %d, %Y at %H:%M:%S')}
> **System:** AI Employee v{AGENT_VERSION} (Silver Tier)
> **Mode:** {'⚠️ DRY RUN' if DRY_RUN else '🟢 ACTIVE'} {'| 🧪 DEV_MODE' if DEV_MODE else ''}

---

## 📊 System Overview

| Metric | Count |
|--------|-------|
| 📥 Inbox | {len(inbox_files)} |
| ⚡ Needs Action | {len(task_files)} |
| 📋 Plans Generated | {len(plan_files)} |
| ⏳ Pending Approval | {len(pending_files)} |
| 📧 Email Drafts Pending | {len(email_pending)} |
| 💼 LinkedIn Posts Pending | {len(linkedin_pending)} |
| ✅ Approved | {len(approved_files)} |
| ❌ Rejected | {len(rejected_files)} |
| ✅ Completed Today | {len(done_today)} |
| 📁 Total Done | {len(done_files)} |
| 📰 CEO Briefings | {len(briefing_files)} |

---

## ⏳ Pending Approvals

| File | Type | Age |
|------|------|-----|
{approval_table}

---

## ⚡ Pending Tasks

| File | Age | Type | Priority |
|------|-----|------|----------|
{pending_table}

---

## ✅ Completed Today

| File | Time | Status |
|------|------|--------|
{done_table}

---

## 🚨 Alerts

{alert_section}

---

## 🖥️ Integration Status

| Component | Status |
|-----------|--------|
| Vault Watcher (File System) | 🟢 Active |
| Gmail Watcher | {gmail_status} |
| LinkedIn Watcher | {linkedin_status} |
| Claude Agent | 🟢 Ready |
| LLM Reasoning (Claude API) | {llm_status} |
| Email MCP Server | 🟡 See email_mcp_server.py |
| Task Classifier | 🟢 Online |
| Plan Generator | 🟢 Online |
| Email Drafter | 🟢 Online |
| LinkedIn Generator | 🟢 Online |
| DRY_RUN Mode | {'🟡 ENABLED' if DRY_RUN else '⚫ Disabled'} |

---

## 📌 Quick Navigation

- [[Inbox]] — Drop new tasks here
- [[Needs_Action]] — Awaiting processing
- [[Plans]] — Generated execution plans
- [[Pending_Approval]] — Awaiting human review
- [[Approved]] — Approved for execution
- [[Rejected]] — Declined tasks
- [[Done]] — Completed tasks
- [[Logs]] — Audit logs and catalog
- [[Briefings]] — CEO Briefings
- [[Skills]] — Agent skill library

---

*Auto-generated by DashboardUpdater v{AGENT_VERSION} | Silver Tier*
*LLM Reasoning: {llm_status}*
"""
        return VaultWriter.write(DASHBOARD_FILE, content)


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 9 — CEO BRIEFING GENERATOR  (Silver Tier)
# See: Skills/scheduler.md
# ══════════════════════════════════════════════════════════════════════════════

class CEOBriefingGenerator:
    """
    Generates the Monday Morning CEO Briefing.
    Reads Business_Goals, task Done/, and Logs/ to produce an executive summary.
    """

    @classmethod
    def generate(cls) -> Optional[Path]:
        """Generate and save a CEO Briefing to Briefings/."""
        now = datetime.now()
        ts  = now.strftime("%Y-%m-%d")
        BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

        # Gather data
        done_files    = VaultReader.list_files(DONE_DIR)
        plans_files   = VaultReader.list_files(PLANS_DIR, ".md")
        approved      = VaultReader.list_files(APPROVED_DIR)
        rejected      = VaultReader.list_files(REJECTED_DIR)

        goals_content = ""
        if GOALS_FILE.exists():
            try:
                goals_content = GOALS_FILE.read_text(encoding="utf-8")
            except Exception:
                pass

        # Count tasks completed this week
        from datetime import timedelta
        week_ago = now - timedelta(days=7)
        weekly_done = [f for f in done_files
                       if datetime.fromtimestamp(f.stat().st_mtime) > week_ago]

        summary_prompt = f"""Generate a Monday Morning CEO Briefing based on this week's data.

BUSINESS GOALS:
{goals_content[:600] if goals_content else 'Not configured'}

WEEKLY STATS:
- Tasks completed this week: {len(weekly_done)}
- Total tasks completed (all time): {len(done_files)}
- Plans generated this week: {len([f for f in plans_files if datetime.fromtimestamp(f.stat().st_mtime) > week_ago])}
- Items approved by human: {len(approved)}
- Items rejected by human: {len(rejected)}

Generate a professional CEO briefing with:
1. Executive Summary (2-3 sentences)
2. Key Wins this week
3. Bottlenecks or concerns
4. Proactive recommendations
5. Focus areas for next week

Use markdown formatting."""

        if LLMReasoner.is_available():
            briefing_body = LLMReasoner.complete(summary_prompt, max_tokens=800)
        else:
            briefing_body = f"""## Executive Summary

Your AI Employee completed **{len(weekly_done)} tasks** this week with full audit trail.
The system is operating in rule-based mode (no Claude API key set).

## Key Wins
- {len(weekly_done)} tasks processed and moved to Done/
- {len(approved)} items reviewed and approved by you
- All actions logged to Logs/task_catalog.jsonl

## Recommendations
- Set Claude API key (ANTHROPIC_API_KEY) to enable AI-powered insights
- Review Pending_Approval/ for items awaiting your decision
- Configure Gmail and LinkedIn integrations for full Silver tier functionality
"""

        briefing_content = f"""---
generated: "{now.isoformat()}"
period: "Weekly Review"
week_ending: "{ts}"
tier: "{TIER}"
---

# Monday Morning CEO Briefing
**Week Ending:** {now.strftime('%B %d, %Y')}
**Generated by:** AI Employee v{AGENT_VERSION} (Silver Tier)

---

{briefing_body}

---

## 📊 Raw Stats This Week

| Metric | Count |
|--------|-------|
| Tasks Completed | {len(weekly_done)} |
| Plans Generated | {len([f for f in plans_files if datetime.fromtimestamp(f.stat().st_mtime) > week_ago])} |
| Items Approved | {len(approved)} |
| Items Rejected | {len(rejected)} |

---
*Generated {now.strftime('%Y-%m-%d %H:%M:%S')} by CEOBriefingGenerator (Silver Tier)*
"""

        briefing_path = BRIEFINGS_DIR / f"{ts}_Monday_Briefing.md"
        if VaultWriter.write(briefing_path, briefing_content):
            logger.info(f"CEO Briefing → Briefings/{briefing_path.name}")
            DashboardUpdater.update()
            return briefing_path
        return None


# ══════════════════════════════════════════════════════════════════════════════
# SKILL 10 — ACTION PROCESSOR  (Silver: email + LinkedIn actions)
# See: Skills/action_processor.md
# ══════════════════════════════════════════════════════════════════════════════

class ActionProcessor:
    """
    Orchestrates the full task-processing pipeline.

    Silver additions:
      - Email drafting via EmailDrafter
      - LinkedIn content generation via LinkedInContentGenerator
      - LLM-enhanced classification and planning
    """

    @staticmethod
    def run() -> dict:
        logger.info("═" * 62)
        logger.info(f"  ClaudeAgent v{AGENT_VERSION} — Silver Tier")
        logger.info(f"  Run started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  LLM: {'Active (Claude API)' if LLMReasoner.is_available() else 'Rule-based (no API key)'}")
        if DRY_RUN:
            logger.info("  *** DRY_RUN MODE — No changes will be made ***")
        logger.info("═" * 62)

        results = {
            "processed"          : 0,
            "plans_created"      : 0,
            "completed"          : 0,
            "routed_for_approval": 0,
            "email_drafts"       : 0,
            "linkedin_posts"     : 0,
            "errors"             : 0,
        }

        tasks = VaultReader.scan_needs_action()
        if not tasks:
            logger.info("Needs_Action/ is empty — nothing to process.")
            DashboardUpdater.update()
            return results

        logger.info(f"Found {len(tasks)} task(s) in Needs_Action/")

        for task in tasks:
            try:
                ActionProcessor._process_one(task, results)
            except Exception as exc:
                logger.error(f"Error on {task['name']}: {exc}", exc_info=True)
                results["errors"] += 1

        DashboardUpdater.update()
        logger.info("═" * 62)
        logger.info(f"  Run complete: {results}")
        logger.info("═" * 62)
        return results

    @staticmethod
    def _process_one(task: dict, results: dict):
        logger.info(f"▶ Processing: {task['name']}")

        # Classify (Silver: LLM-enhanced)
        ct = TaskClassifier.classify(task)
        logger.info(
            f"  type={ct['task_type']}  priority={ct['priority']}  "
            f"action={ct['action']}  approval={ct['requires_approval']}"
        )
        if ct.get("ai_summary"):
            logger.info(f"  AI: {ct['ai_summary'][:80]}")

        # Generate plan
        plan_content = PlanGenerator.generate(ct)
        ts           = datetime.now().strftime("%Y%m%d_%H%M%S")
        plan_name    = f"{ts}_{task['stem']}_plan.md"
        plan_path    = PLANS_DIR / plan_name

        PLANS_DIR.mkdir(parents=True, exist_ok=True)
        if VaultWriter.write(plan_path, plan_content):
            results["plans_created"] += 1
            logger.info(f"  ✔ Plan → Plans/{plan_name}")

        # Route based on action type
        if ct["action"] == "parse_and_respond":
            # Generate email draft → Pending_Approval
            draft_path = EmailDrafter.draft_response(ct)
            if draft_path:
                results["email_drafts"] += 1
            FileMover.move(ct["task_file"], PENDING_APPROVAL_DIR, f"{ts}_{task['name']}")
            if ct.get("meta_file") and ct["meta_file"].exists():
                FileMover.move(ct["meta_file"], PENDING_APPROVAL_DIR)
            FileMover.copy_to(plan_path, PENDING_APPROVAL_DIR)
            logger.info(f"  📧 Email draft → Pending_Approval/ (requires approval)")
            results["routed_for_approval"] += 1

        elif ct["action"] == "linkedin_content":
            # Generate LinkedIn post → Pending_Approval
            post_path = LinkedInContentGenerator.generate_post(
                context=ct.get("file_content") or ct.get("ai_summary") or "",
            )
            if post_path:
                results["linkedin_posts"] += 1
            FileMover.move(ct["task_file"], PENDING_APPROVAL_DIR, f"{ts}_{task['name']}")
            if ct.get("meta_file") and ct["meta_file"].exists():
                FileMover.move(ct["meta_file"], PENDING_APPROVAL_DIR)
            logger.info(f"  💼 LinkedIn post → Pending_Approval/ (requires approval)")
            results["routed_for_approval"] += 1

        elif ct["requires_approval"]:
            # Generic approval routing
            FileMover.move(ct["task_file"], PENDING_APPROVAL_DIR, f"{ts}_{task['name']}")
            if ct.get("meta_file") and ct["meta_file"].exists():
                FileMover.move(ct["meta_file"], PENDING_APPROVAL_DIR, f"{ts}_{ct['meta_file'].name}")
            FileMover.copy_to(plan_path, PENDING_APPROVAL_DIR)
            logger.info(f"  ⏳ Routed to Pending_Approval/ (requires approval)")
            results["routed_for_approval"] += 1

        else:
            # Safe execution
            ActionProcessor._execute(ct)
            done_name = f"{ts}_{task['name']}"
            dest = FileMover.move(ct["task_file"], DONE_DIR, done_name)
            if dest:
                results["completed"] += 1
                logger.info(f"  ✔ Done → Done/{done_name}")
            if ct.get("meta_file") and ct["meta_file"].exists():
                FileMover.move(ct["meta_file"], DONE_DIR, f"{ts}_{ct['meta_file'].name}")

        results["processed"] += 1
        logger.info(f"  ✅ {task['name']} complete")

    @staticmethod
    def _execute(task: dict):
        """Execute safe, non-destructive Silver-tier actions."""
        logger.info(f"  ⚙ Executing: {task.get('action')} on {task.get('task_type')} file")

        entry = {
            "timestamp"    : datetime.now().isoformat(),
            "file"         : task["name"],
            "type"         : task.get("task_type"),
            "action"       : task.get("action"),
            "priority"     : task.get("priority"),
            "ai_summary"   : task.get("ai_summary", ""),
            "tier"         : TIER,
            "status"       : "completed",
            "dry_run"      : DRY_RUN,
            "llm_assisted" : bool(task.get("ai_summary")),
        }

        if not DRY_RUN:
            try:
                LOGS_DIR.mkdir(parents=True, exist_ok=True)
                with open(CATALOG_FILE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry) + "\n")
            except Exception as exc:
                logger.warning(f"  Catalog write failed: {exc}")
        else:
            logger.info(f"  [DRY_RUN] Catalog entry: {json.dumps(entry)[:120]}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="claude_agent",
        description="AI Employee — Claude Agent Task Processor (Silver Tier)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python claude_agent.py                    Process all pending tasks
  python claude_agent.py --dry-run          Simulate; no changes
  python claude_agent.py --update-dashboard Refresh Dashboard.md only
  python claude_agent.py --scan             List tasks in Needs_Action/
  python claude_agent.py --briefing         Generate Monday CEO Briefing
  python claude_agent.py --linkedin-post    Generate LinkedIn post from goals

Environment variables:
  ANTHROPIC_API_KEY   Claude API key — enables Claude Code reasoning
  DRY_RUN=true        Enable dry-run mode
  DEV_MODE=true       Simulate LLM responses (offline demo mode)
        """,
    )
    p.add_argument("--dry-run",           action="store_true")
    p.add_argument("--update-dashboard",  action="store_true")
    p.add_argument("--scan",              action="store_true")
    p.add_argument("--briefing",          action="store_true",
                   help="Generate Monday Morning CEO Briefing")
    p.add_argument("--linkedin-post",     action="store_true",
                   help="Generate LinkedIn post from Business_Goals.md")
    return p


def main():
    global DRY_RUN

    args = build_parser().parse_args()

    if args.dry_run:
        DRY_RUN = True
        os.environ["DRY_RUN"] = "true"
        logger.info("DRY_RUN enabled via --dry-run flag")

    if args.scan:
        tasks = VaultReader.scan_needs_action()
        print(f"\nPending tasks in Needs_Action/ ({len(tasks)} found):")
        for t in tasks:
            print(f"  • {t['name']}  [{t['size']:,} bytes | {t['modified'].strftime('%H:%M:%S')}]")
        print()
        return

    if args.update_dashboard:
        logger.info("Dashboard update only…")
        DashboardUpdater.update()
        logger.info("Dashboard updated.")
        return

    if args.briefing:
        logger.info("Generating CEO Briefing…")
        path = CEOBriefingGenerator.generate()
        if path:
            print(f"\n✅ CEO Briefing written: {path}")
        return

    if args.linkedin_post:
        logger.info("Generating LinkedIn post from Business_Goals…")
        path = LinkedInContentGenerator.generate_from_business_goals()
        if path:
            print(f"\n✅ LinkedIn post draft: {path}")
            print("   Review in Pending_Approval/ then move to Approved/ to publish.")
        return

    results = ActionProcessor.run()

    print(f"\n{'─'*55}")
    print(f"  Run Summary (Silver Tier)")
    print(f"{'─'*55}")
    print(f"  Tasks processed       : {results['processed']}")
    print(f"  Plans created         : {results['plans_created']}")
    print(f"  Completed → Done/     : {results['completed']}")
    print(f"  Pending approval      : {results['routed_for_approval']}")
    print(f"  Email drafts created  : {results['email_drafts']}")
    print(f"  LinkedIn drafts       : {results['linkedin_posts']}")
    print(f"  Errors                : {results['errors']}")
    print(f"{'─'*55}")
    print(f"  LLM: {'Active (Claude Code)' if LLMReasoner.is_available() else 'Rule-based (set Claude API key)'}")
    print(f"{'─'*55}\n")


if __name__ == "__main__":
    main()
