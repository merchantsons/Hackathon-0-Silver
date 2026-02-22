---
skill_id: "action_processor"
skill_name: "Action Processor"
version: "1.0.0"
tier: "bronze"
category: "orchestration"
layer: "action"
implementation: "claude_agent.py::ActionProcessor"
status: "active"
---

# Skill: Action Processor

## Purpose

Orchestrate the complete task-processing pipeline by coordinating all other skills.
This is the **central controller** of the AI Employee's reasoning-action loop.

For each task in `Needs_Action/`, the Action Processor:
1. Classifies the task (TaskClassifier)
2. Generates a plan (PlanGenerator)
3. Routes it (approval queue or direct execution)
4. Executes safe actions (Bronze: catalog logging)
5. Moves completed tasks to `Done/`
6. Updates the Dashboard

---

## Pipeline Diagram

```
Needs_Action/
     │
     ▼
TaskClassifier.classify()
     │
     ▼
PlanGenerator.generate()  ──→  Plans/{timestamp}_plan.md
     │
     ▼
requires_approval?
   YES ──→  FileMover.copy_to(Pending_Approval/)
            [Human reviews — approve or reject]
   NO  ──→  ActionProcessor._execute()
            │
            ▼
         FileMover.move(task → Done/)
         FileMover.move(meta → Done/)
     │
     ▼
DashboardUpdater.update()
```

---

## Inputs

### `run()` — No arguments
Automatically scans `Needs_Action/` via `VaultReader.scan_needs_action()`.

### `_process_one(task, results)`
| Parameter | Type | Description |
|-----------|------|-------------|
| `task` | `dict` | Task descriptor from VaultReader |
| `results` | `dict` | Mutable results accumulator (modified in-place) |

---

## Outputs

### `run()` returns:
```python
{
    "processed"           : int,  # Total tasks touched
    "plans_created"       : int,  # Plans/ files written
    "completed"           : int,  # Tasks moved to Done/
    "routed_for_approval" : int,  # Tasks sent to Pending_Approval/
    "errors"              : int,  # Exceptions caught
}
```

---

## Bronze Tier Execution (`_execute`)

In Bronze tier, `_execute()` performs **safe, non-destructive** actions only:

1. Writes a structured JSON entry to `Logs/task_catalog.jsonl`
2. Logs the action with task metadata

```json
{
  "timestamp": "2026-02-19T12:00:00",
  "file": "quarterly_report.pdf",
  "type": "document",
  "action": "read_and_classify",
  "priority": "medium",
  "tier": "bronze",
  "status": "completed",
  "dry_run": false
}
```

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| TaskClassifier raises | Task skipped; `errors += 1`; processing continues |
| PlanGenerator raises | Task skipped; `errors += 1`; processing continues |
| FileMover fails | Logged; source file preserved; `errors += 1` |
| DashboardUpdater fails | Logged; does not abort; dashboard may be stale |
| Empty Needs_Action/ | Logs info message; updates dashboard; returns `{...0s}` |

**Principle:** One bad task never stops the entire run. Each task is
independently try/caught.

---

## Safety Rules Enforced

- All file moves use `FileMover` (copy-verify-delete guarantee).
- `requires_approval=True` tasks are **never auto-executed**.
- DRY_RUN mode propagates to all sub-skills automatically.
- No network calls, no external API calls.
- Original source files in `Inbox/` are never touched by this skill.

---

## Implementation Notes

```python
# Bronze Tier — Rule-based orchestration
classified = TaskClassifier.classify(task)
plan = PlanGenerator.generate(classified)
if classified["requires_approval"]:
    FileMover.copy_to(plan_path, Pending_Approval_dir)
else:
    _execute(classified)
    FileMover.move(task_file, Done_dir)

# [LLM_HOOK] Silver+:
# Replace _execute() body with:
# actions = llm.determine_actions(classified, handbook, business_goals)
# for action in actions:
#     if action.safe_for_auto_execution:
#         execute_action(action)
#     else:
#         route_to_approval(action)
#
# [RW_HOOK] Gold+ (Ralph Wiggum loop):
# while True:
#     ActionProcessor.run()
#     time.sleep(poll_interval)
```

---

## Reusability Notes

- `run()` is idempotent: re-running on an empty queue is safe.
- Individual `_process_one()` can be called for targeted processing.
- Results dict is suitable for logging, alerting, or dashboard metrics.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | Replace `_execute()` with LLM-driven action execution |
| Gold | Wrap `run()` in continuous Ralph Wiggum polling loop |
| Gold | Add multi-agent delegation for parallel task processing |
| Platinum | Add self-healing: detect + fix stale Needs_Action items |

---

## Example Usage

```python
from claude_agent import ActionProcessor

# Standard processing run
results = ActionProcessor.run()
print(f"Completed: {results['completed']}")
print(f"Errors: {results['errors']}")

# Dry run (no changes)
import os
os.environ["DRY_RUN"] = "true"
results = ActionProcessor.run()
```

---

*Action Processor Skill v1.0.0 | Bronze Tier | Layer: Orchestration/Action*
