---
skill_id: "task_classifier"
skill_name: "Task Classifier"
version: "1.0.0"
tier: "bronze"
category: "reasoning"
layer: "reasoning"
implementation: "claude_agent.py::TaskClassifier"
status: "active"
---

# Skill: Task Classifier

## Purpose

Analyse an incoming task descriptor and determine:
1. **Task type** — What kind of file/task is this?
2. **Priority** — How urgently must it be handled?
3. **Required action** — What should the agent do with it?
4. **Approval requirement** — Does a human need to review first?

This skill bridges Perception (raw file detection) and Action (plan execution).
It is the first reasoning step in the pipeline.

---

## Inputs

A task descriptor dictionary (output of `VaultReader.scan_needs_action()`):

```python
{
    "name"      : str,      # e.g. "20260219_quarterly_report.pdf"
    "stem"      : str,      # e.g. "20260219_quarterly_report"
    "extension" : str,      # e.g. ".pdf"
    "size"      : int,      # bytes
    "modified"  : datetime,
    "meta_content": str | None,
    ...
}
```

---

## Outputs

Returns the input dict **enriched** with classification fields:

```python
{
    ...input fields...,
    "task_type"          : str,   # document | spreadsheet | image | code |
                                  # email | archive | note | data | unknown
    "priority"           : str,   # urgent | high | medium | low
    "action"             : str,   # see Action Map below
    "requires_approval"  : bool,  # True if human must review first
    "classifier_version" : str,   # e.g. "1.0.0-bronze"
}
```

---

## Classification Logic

### Task Type Map
| Type | File Extensions |
|------|----------------|
| document | .pdf .docx .doc .rtf .odt |
| spreadsheet | .xlsx .xls .ods |
| image | .jpg .jpeg .png .gif .bmp .svg .webp |
| code | .py .js .ts .html .css .json .yaml .yml .sh .bat .ps1 |
| email | .eml .msg |
| archive | .zip .tar .gz .7z .rar |
| note | .txt .md |
| data | .csv .tsv .xml |

### Priority Map
| Priority | Filename Contains (case-insensitive) |
|----------|--------------------------------------|
| urgent | urgent, asap, critical, emergency, immediate |
| high | important, high, priority, deadline, needed |
| medium | *(default)* |
| low | low, minor, optional, sometime, fyi |

### Action Map
| Action | Triggered By |
|--------|-------------|
| `read_and_classify` | document, note; or "review" in filename |
| `generate_summary` | "report", "summary", "meeting", "invoice" in filename |
| `process_task_list` | "task", "todo" in filename |
| `analyze_and_report` | spreadsheet, data |
| `parse_and_respond` | email |
| `review_code` | code |
| `catalog_and_archive` | image |
| `extract_and_catalog` | archive |
| `general_processing` | unknown / fallback |

### Approval Requirement Rules
Approval is **required** when:
- Priority = `urgent` (external urgency implies human judgement needed)
- Task type = `email` (potential external communication)
- Task type = `code` (execution risk)

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Unknown extension | `task_type = "unknown"`, `action = "general_processing"` |
| No filename keywords match | `priority = "medium"` (safe default) |
| Exception during classify | Original task dict returned unchanged; ERROR logged |

---

## Implementation Notes

```python
# Bronze Tier — Rule-based heuristics on filename + extension
task_type = cls._TYPE_MAP.get(extension, "unknown")
priority  = "medium"
for level, keywords in cls._PRIORITY_KEYWORDS.items():
    if any(kw in name_lower for kw in keywords):
        priority = level; break

# [LLM_HOOK] Silver+:
# prompt = CLASSIFY_PROMPT.format(
#     filename=task["name"],
#     content_preview=task["meta_content"][:500],
#     handbook=load_handbook(),
#     business_goals=load_goals()
# )
# result = llm.complete(prompt, schema=ClassificationSchema)
# return {**task, **result}
```

---

## Reusability Notes

- Stateless: safe to call concurrently on multiple tasks.
- Extend `_TYPE_MAP` and `_KEYWORD_ACTIONS` without changing the interface.
- The classification output dict is the standard input format for PlanGenerator.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | Replace `classify()` body with LLM call; same interface |
| Gold | Add confidence scores; route low-confidence to human review |
| Platinum | Multi-model ensemble classification with voting |

---

## Example Usage

```python
from claude_agent import TaskClassifier, VaultReader

tasks = VaultReader.scan_needs_action()
for task in tasks:
    classified = TaskClassifier.classify(task)
    print(f"{classified['name']}: {classified['task_type']} / {classified['priority']}")
    print(f"  Action: {classified['action']}")
    print(f"  Approval: {classified['requires_approval']}")
```

---

*Task Classifier Skill v1.0.0 | Bronze Tier | Layer: Reasoning*
