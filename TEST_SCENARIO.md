# 🧪 Test Scenario — AI Employee Bronze Tier

> **Goal:** Verify the complete pipeline from file drop to Done/, Dashboard update, and rollback on Inbox delete.
> **Time required:** ~8 minutes (with rollback test)
> **Prerequisites:** Setup complete (`setup.bat` or manual install)

---

## Pre-Test Checklist

- [ ] `pip install -r requirements.txt` completed
- [ ] `AI_Employee_Vault/` directory structure exists
- [ ] You have two terminal windows ready (one for watcher, one for agent)
- [ ] (Windows) `run_rollback.bat` available for Test 4.2

---

## Test 1 — Dry Run (Safe, No Changes)

Verify the system works before enabling live mode.

### Step 1.1 — Start dry-run watcher
```bash
# Terminal 1
DRY_RUN=true python watcher.py    # macOS/Linux
run_watcher.bat --dry              # Windows
```

Expected console output:
```
══════════════════════════════════════════════════════════════
  VaultWatcher v1.0.0 — Bronze Tier
══════════════════════════════════════════════════════════════
  *** DRY_RUN MODE — No files will be modified ***
  Vault Root : /path/to/AI_Employee_Vault
  Watching   : /path/to/AI_Employee_Vault/Inbox
  Watcher active. Drop files into Inbox/ to begin.
  Press Ctrl+C to stop safely.
```

### Step 1.2 — Create a test file in Inbox

**Windows:**
```batch
echo This is a test task for the AI Employee. > "AI_Employee_Vault\Inbox\test_document.txt"
```

**macOS/Linux:**
```bash
echo "This is a test task for the AI Employee." > AI_Employee_Vault/Inbox/test_document.txt
```

Expected watcher output (DRY_RUN):
```
2026-02-19 12:00:01 [INFO] VaultWatcher: ▶ New file detected: test_document.txt
2026-02-19 12:00:01 [INFO] VaultWatcher:   [DRY_RUN] Would copy  → Needs_Action/20260219_120001_test_document.txt
2026-02-19 12:00:01 [INFO] VaultWatcher:   [DRY_RUN] Would write → Needs_Action/20260219_120001_test_document_meta.md
```

### Step 1.3 — Stop watcher (Ctrl+C)

### Step 1.4 — Run dry-run agent
```bash
# Terminal 2
DRY_RUN=true python claude_agent.py   # macOS/Linux
run_agent.bat --dry                    # Windows
```

Expected output:
```
Pending tasks in Needs_Action/ (0 found):   ← Nothing here in dry-run since watcher was also dry
```

**This confirms:** The scripts run without errors. ✅

---

## Test 2 — Live Pipeline (Full End-to-End)

### Step 2.1 — Start the live watcher
```bash
# Terminal 1
python watcher.py     # macOS/Linux
run_watcher.bat       # Windows
```

### Step 2.2 — Drop 3 test files

**File A — Standard document (medium priority)**
```batch
echo "Quarterly review notes: Sales up 12%, marketing budget approved." > "AI_Employee_Vault\Inbox\quarterly_report.txt"
```

**File B — Urgent file (triggers approval routing)**
```batch
echo "URGENT: Client contract renewal deadline tomorrow. Review immediately." > "AI_Employee_Vault\Inbox\urgent_contract.txt"
```

**File C — Email file (triggers approval routing)**
```bash
# Create a fake .eml file (email type → requires approval)
echo "From: client@example.com\nSubject: Meeting Request\nBody: Can we meet Friday?" > "AI_Employee_Vault\Inbox\client_meeting_request.eml"
```

Watch Terminal 1 output — you should see 3 detection events.

### Step 2.3 — Verify Needs_Action contents

```bash
python claude_agent.py --scan
```
Windows: `run_agent.bat --scan`

Expected output:
```
Pending tasks in Needs_Action/ (3 found):
  • 20260219_120001_quarterly_report.txt          [72 bytes | 12:00:01]
  • 20260219_120002_urgent_contract.txt           [88 bytes | 12:00:02]
  • 20260219_120003_client_meeting_request.eml    [91 bytes | 12:00:03]
```

### Step 2.4 — Run the agent

```bash
python claude_agent.py
```
Windows: `run_agent.bat`

#### Expected Console Output:
```
══════════════════════════════════════════════════════════════
  ClaudeAgent v1.0.0 — Bronze Tier
  Run started: 2026-02-19 12:01:00
══════════════════════════════════════════════════════════════
Found 3 task(s) in Needs_Action/

▶ Processing: 20260219_120001_quarterly_report.txt
  type=note  priority=medium  action=generate_summary  approval=False
  ✔ Plan → Plans/20260219_120100_quarterly_report_plan.md
  ⚙ Executing: generate_summary on note file
  ✔ Done → Done/20260219_120100_quarterly_report.txt
  ✅ 20260219_120001_quarterly_report.txt complete

▶ Processing: 20260219_120002_urgent_contract.txt
  type=note  priority=urgent  action=read_and_classify  approval=True
  ✔ Plan → Plans/20260219_120100_urgent_contract_plan.md
  ⏳ Routed to Pending_Approval/ (approval required)
  ✅ 20260219_120002_urgent_contract.txt complete

▶ Processing: 20260219_120003_client_meeting_request.eml
  type=email  priority=medium  action=parse_and_respond  approval=True
  ✔ Plan → Plans/20260219_120100_client_meeting_request_plan.md
  ⏳ Routed to Pending_Approval/ (approval required)
  ✅ 20260219_120003_client_meeting_request.eml complete

──────────────────────────────────────────────────
  Run Summary
──────────────────────────────────────────────────
  Tasks processed       : 3
  Plans created         : 3
  Completed → Done/     : 1
  Pending approval      : 2
  Errors                : 0
──────────────────────────────────────────────────
```

---

## Verification Checklist

After Test 2, verify each expectation:

### 📁 Folder State

**`AI_Employee_Vault/Inbox/`** — Original files still here ✅
```
quarterly_report.txt          ← PRESERVED (never deleted)
urgent_contract.txt           ← PRESERVED
client_meeting_request.eml    ← PRESERVED
```

**`AI_Employee_Vault/Needs_Action/`** — Should be empty (tasks processed) ✅

**`AI_Employee_Vault/Plans/`** — 3 plan files ✅
```
20260219_120100_..._quarterly_report_plan.md
20260219_120100_..._urgent_contract_plan.md
20260219_120100_..._client_meeting_request_plan.md
```

**`AI_Employee_Vault/Done/`** — 2 files (task + meta for the one completed task, e.g. quarterly_report) ✅
```
20260219_120100_20260219_120001_quarterly_report.txt
20260219_120100_20260219_120001_quarterly_report_meta.md
```

**`AI_Employee_Vault/Pending_Approval/`** — 6 files (plan + meta + task copy for urgent + email) ✅
```
*..._urgent_contract_plan.md
*..._urgent_contract_meta.md
*..._urgent_contract.txt
*..._client_meeting_request_plan.md
*..._client_meeting_request_meta.md
*..._client_meeting_request.eml
```

### 📊 Dashboard.md — Updated metrics ✅
Open `AI_Employee_Vault/Dashboard.md` and verify:
```
| ✅ Completed Today | 1 |
| ⏳ Pending Approval | 2+ |
| 📋 Plans Generated | 3 |
```

### 📝 Plan file content — Has checklist ✅
Open any Plan file in `Plans/`. It should contain:
```
## Execution Checklist
- [ ] Read the full document
- [ ] Identify main topics...
```

### 📋 Audit trail — JSONL entry created ✅
Check `AI_Employee_Vault/Logs/task_catalog.jsonl`:
```json
{"timestamp":"2026-02-19T12:01:00","file":"20260219_120001_quarterly_report.txt","type":"note","action":"generate_summary","priority":"medium","tier":"bronze","status":"completed","dry_run":false}
```

---

## Test 3 — Human Approval Workflow

### Step 3.1 — Review pending items
Open `AI_Employee_Vault/Pending_Approval/` in Obsidian or Explorer.

You'll see (names include timestamps):
- `*urgent_contract*plan.md` — The generated plan for the urgent task
- `*urgent_contract*meta.md` — The task metadata
- `*client_meeting_request*plan.md` and corresponding meta/task files for the email

### Step 3.2 — Approve a plan
Move the plan file for the urgent task to `AI_Employee_Vault/Approved/` (e.g. the file named `*urgent_contract*plan.md`).

### Step 3.3 — Reject a plan
Move the plan file for the email task to `AI_Employee_Vault/Rejected/` (e.g. `*client_meeting_request*plan.md`).
Add a rejection note at the bottom of the file (optional).

### Step 3.4 — Refresh dashboard
```bash
python claude_agent.py --update-dashboard
```
Windows: `run_agent.bat --dashboard`

Dashboard will reflect the updated Approved/Rejected counts. ✅

---

## Test 4 — Rollback on Inbox File Delete

When you delete the **original file from Inbox/**, all processing for that file is rolled back: Needs_Action, Done, Plans, Pending_Approval, and task_catalog.jsonl entries are removed; Dashboard is refreshed.

### Step 4.1 — Rollback with watcher running

1. Start the watcher (Terminal 1): `python watcher.py` or `run_watcher.bat`
2. Ensure at least one task has been processed (e.g. from Test 2, a file in Done/).
3. Delete the **original** file from `AI_Employee_Vault/Inbox/` (e.g. `quarterly_report.txt`).
4. **Expected (Terminal 1):** Watcher logs:
   ```
   ▶ Inbox file deleted: quarterly_report.txt — rolling back all related artifacts
     ✔ Removed Done\..._quarterly_report_meta.md
     ✔ Removed Done\..._quarterly_report.txt
     ✔ Removed Plans\..._quarterly_report_plan.md
     ✔ Removed catalog entry: ...
     ✔ Dashboard updated
   ✅ Rollback complete for quarterly_report.txt
   ```
5. Verify: Done/, Plans/, and task_catalog.jsonl no longer contain that task; Dashboard counts updated.

### Step 4.2 — Rollback when watcher was not running

If you deleted the Inbox file while the watcher was stopped, run rollback manually:

**Windows:**
```batch
run_rollback.bat "quarterly_report.txt"
```

**macOS/Linux:**
```bash
python -c "from watcher import rollback_for_deleted_inbox_file; rollback_for_deleted_inbox_file('quarterly_report.txt')"
```

Use the **exact Inbox filename** you deleted. Same artifacts are removed and Dashboard is refreshed.

---

## Test 5 — Edge Cases

### Empty queue run (should exit cleanly)
```bash
# After all tasks are processed
python claude_agent.py
```
Windows: `run_agent.bat`

Expected:
```
Needs_Action/ is empty — nothing to process.
```

### Missing Inbox file (race condition simulation)
Drop a file, immediately delete it before watcher picks it up.
Expected: Watcher logs a warning, continues running gracefully.

### Large file handling
Drop a file > 1 MB into Inbox.
Expected: Processes normally (no size limit in Bronze tier).

### Filename with special characters
```
Drop file: "Q1 Report [FINAL] (2026).pdf"
```
Expected: Sanitized to `Q1_Report__FINAL___2026_.pdf` in Needs_Action.

---

## Test 6 — Watcher Restart Recovery

1. Start watcher
2. Kill it (Ctrl+C)
3. While it's stopped, drop files into Inbox (they won't be detected)
4. Restart watcher
5. Note: **already-dropped files are NOT retroactively processed**
6. Run agent directly: `python claude_agent.py` — it checks Needs_Action only

> **Bronze Tier note:** The watcher only detects files dropped while running.
> For retroactive processing, run `python claude_agent.py` manually.
> Silver tier: Startup scan can be added to catch missed files.

---

## Success Criteria Scorecard

| Criterion | Expected | Verified |
|-----------|----------|---------|
| Watcher starts without error | ✅ | [ ] |
| New file detected in Inbox | ✅ | [ ] |
| File copied to Needs_Action | ✅ | [ ] |
| Metadata .md created | ✅ | [ ] |
| Original file preserved in Inbox | ✅ | [ ] |
| Agent classifies task correctly | ✅ | [ ] |
| Plan.md created in Plans/ | ✅ | [ ] |
| Plan has execution checklist | ✅ | [ ] |
| Standard task moved to Done/ | ✅ | [ ] |
| Urgent/email routed to Pending_Approval | ✅ | [ ] |
| Dashboard.md updated with stats | ✅ | [ ] |
| Audit trail in task_catalog.jsonl | ✅ | [ ] |
| No files permanently deleted | ✅ | [ ] |
| Graceful shutdown on Ctrl+C | ✅ | [ ] |
| DRY_RUN mode works | ✅ | [ ] |
| Rollback on Inbox delete (watcher or run_rollback.bat) | ✅ | [ ] |

**Score 16/16 = Bronze Tier complete ✅**

---

*Test Scenario v1.1.0 | AI Employee Bronze Tier | 2026-02-20*
