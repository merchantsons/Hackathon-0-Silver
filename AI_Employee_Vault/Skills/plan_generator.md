---
skill_id: "plan_generator"
skill_name: "Plan Generator"
version: "1.0.0"
tier: "bronze"
category: "reasoning"
layer: "reasoning"
implementation: "claude_agent.py::PlanGenerator"
status: "active"
---

# Skill: Plan Generator

## Purpose

Generate a structured, human-readable `Plan.md` file for each classified task.
The plan contains:
- Task metadata (type, priority, action)
- An executable checklist of steps
- Approval notice if required
- An observations section for runtime notes
- A completion checklist

Plans are saved to `Plans/` and serve as the agent's explicit reasoning
trace — every action is documented *before* it is taken.

---

## Inputs

A **classified task dictionary** (output of `TaskClassifier.classify()`):

```python
{
    "name"               : str,
    "stem"               : str,
    "extension"          : str,
    "size"               : int,
    "modified"           : datetime,
    "task_type"          : str,
    "priority"           : str,
    "action"             : str,
    "requires_approval"  : bool,
    "classifier_version" : str,
    ...
}
```

---

## Outputs

| Return | Type | Description |
|--------|------|-------------|
| `generate(task)` | `str` | Complete Markdown content for the Plan.md file |

### Output File Format
```
Plans/
  └── {YYYYMMDD_HHMMSS}_{task_stem}_plan.md
```

The generated file includes YAML frontmatter for machine parsing and
a human-readable Markdown body with checklist.

---

## Plan Templates

### Available Action Templates

| Action | Steps |
|--------|-------|
| `read_and_classify` | 8 steps: read → identify → summarise → tag → archive |
| `generate_summary` | 7 steps: read → extract → write summary → list actions |
| `process_task_list` | 7 steps: parse → prioritise → estimate → flag → plan |
| `analyze_and_report` | 7 steps: open → validate → statistics → insights → report |
| `parse_and_respond` | 7 steps: parse headers → extract → draft → file → log |
| `review_code` | 7 steps: read → syntax → logic → security → summarise |
| `catalog_and_archive` | 6 steps: verify → classify → rename → catalog → archive |
| `extract_and_catalog` | 7 steps: verify → list → assess → extract → catalog |
| `general_processing` | 6 steps: read → determine → apply rules → document → route |

### Template Extension
Add new templates to `_STEPS` dictionary without changing the interface:
```python
PlanGenerator._STEPS["my_new_action"] = [
    "Step one description",
    "Step two description",
    ...
]
```

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Unknown action | Falls back to `general_processing` template |
| Missing task fields | Uses safe defaults; logs WARNING |
| Write failure | Logged as ERROR; processing continues |

---

## Approval Notice Generation

When `task["requires_approval"] == True`, the plan includes a prominent
approval block:
```
## ⚠️ Human Approval Required
File placed in: Pending_Approval/
To approve: Move plan to Approved/
To reject:  Move plan to Rejected/
```

---

## Implementation Notes

```python
# Bronze Tier — Template lookup by action name
steps = cls._STEPS.get(action, cls._STEPS["general_processing"])
checklist = "\n".join(f"- [ ] {s}" for s in steps)

# [LLM_HOOK] Silver+:
# context = load_handbook() + "\n\n" + load_business_goals()
# prompt = PLAN_PROMPT.format(task=task, context=context)
# raw_plan = llm.complete(prompt)
# steps = parse_plan_steps(raw_plan)
# checklist = "\n".join(f"- [ ] {s}" for s in steps)
```

---

## Reusability Notes

- Stateless; safe for concurrent calls.
- Extend templates by adding to `_STEPS` dict — no method changes needed.
- Output format is stable; consumers (FileMover, DashboardUpdater) rely on it.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | LLM-generated plans with file content analysis |
| Gold | Multi-step plans with agent sub-task delegation |
| Platinum | Dynamic plan adaptation based on partial execution results |

---

## Example Usage

```python
from claude_agent import TaskClassifier, PlanGenerator, VaultWriter

task = TaskClassifier.classify(raw_task)
plan_content = PlanGenerator.generate(task)

plan_path = plans_dir / f"20260219_123456_{task['stem']}_plan.md"
VaultWriter.write(plan_path, plan_content)
```

---

*Plan Generator Skill v1.0.0 | Bronze Tier | Layer: Reasoning*
