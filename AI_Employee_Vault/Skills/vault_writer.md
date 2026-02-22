---
skill_id: "vault_writer"
skill_name: "Vault Writer"
version: "1.0.0"
tier: "bronze"
category: "action"
layer: "action"
implementation: "claude_agent.py::VaultWriter"
status: "active"
---

# Skill: Vault Writer

## Purpose

Write and append text content to files in the AI Employee Vault. This skill
is the primary **write interface** between the AI reasoning layer and local
storage.

It respects DRY_RUN mode, creates parent directories automatically, handles
encoding consistently, and logs every write operation for auditability.

---

## Inputs

### `write(path, content, overwrite=True)`
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | `Path` | Yes | — | Destination file path |
| `content` | `str` | Yes | — | UTF-8 text content to write |
| `overwrite` | `bool` | No | `True` | If False, skip if file exists |

### `append(path, content)`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | `Path` | Yes | Target file path |
| `content` | `str` | Yes | Text to append |

---

## Outputs

| Method | Return | Description |
|--------|--------|-------------|
| `write(...)` | `bool` | `True` = success, `False` = failure |
| `append(...)` | `bool` | `True` = success, `False` = failure |

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Directory doesn't exist | Auto-created via `mkdir(parents=True)` |
| Permission denied | Returns `False`; logs ERROR |
| Disk full | Returns `False`; logs ERROR |
| `overwrite=False`, file exists | Returns `False`; logs WARNING |
| DRY_RUN=true | Logs what would happen; returns `True` (simulated success) |

---

## Safety Features

### DRY_RUN Mode
When `DRY_RUN=true`, all writes are simulated:
```
[DRY_RUN] Would write 4,231 bytes → Plans/20260219_task_plan.md
```
No filesystem changes occur. Return value is `True` to allow pipeline to continue.

### Overwrite Protection
```python
# Prevent accidental overwrites of existing files
VaultWriter.write(path, content, overwrite=False)
```

---

## Implementation Notes

```python
# Bronze Tier — Direct filesystem write
path.write_text(content, encoding="utf-8")

# [LLM_HOOK] Silver+ — MCP filesystem server write:
# await mcp_client.write_file(path, content)
```

---

## Reusability Notes

- Always use VaultWriter for vault writes — never use raw `open()` calls.
- Ensures consistent UTF-8 encoding across all vault files.
- Centralised logging of all write operations.
- Parent directory creation is automatic.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | Swap internals to MCP `filesystem` server writes |
| Gold | Add write conflict detection for multi-agent scenarios |
| Platinum | Add write versioning / diff history |

---

## Example Usage

```python
from claude_agent import VaultWriter
from pathlib import Path

vault = Path("AI_Employee_Vault")

# Write a new plan file (overwrites if exists)
VaultWriter.write(vault / "Plans" / "my_plan.md", plan_content)

# Write only if new (skip if already exists)
VaultWriter.write(vault / "Notes" / "notes.md", content, overwrite=False)

# Append to activity log
VaultWriter.append(vault / "Logs" / "activity.log", "Task completed\n")
```

---

*Vault Writer Skill v1.0.0 | Bronze Tier | Layer: Action*
