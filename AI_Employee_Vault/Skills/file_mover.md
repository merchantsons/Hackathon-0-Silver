---
skill_id: "file_mover"
skill_name: "File Mover"
version: "1.0.0"
tier: "bronze"
category: "action"
layer: "action"
implementation: "claude_agent.py::FileMover"
status: "active"
---

# Skill: File Mover

## Purpose

Safely move or copy files between vault folders using a
**copy → verify → delete-source** pattern that guarantees zero data loss.

This skill is the only permitted way to move files in the vault.
Direct `os.rename()` or `shutil.move()` calls are prohibited because they
can silently fail across different filesystem mount points.

---

## Inputs

### `move(source, dest_dir, new_name=None)`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | `Path` | Yes | Absolute path to source file |
| `dest_dir` | `Path` | Yes | Destination directory |
| `new_name` | `str` | No | Rename file at destination |

### `copy_to(source, dest_dir, new_name=None)`
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | `Path` | Yes | Absolute path to source file |
| `dest_dir` | `Path` | Yes | Destination directory |
| `new_name` | `str` | No | Rename file at destination |

---

## Outputs

| Method | Return | Description |
|--------|--------|-------------|
| `move(...)` | `Path \| None` | Destination path, or `None` on failure |
| `copy_to(...)` | `Path \| None` | Destination path, or `None` on failure |

---

## Safety Guarantees

### Copy-Verify-Delete Pattern
```
1. shutil.copy2(source, dest)    ← Preserves metadata
2. Assert dest.exists()          ← Verify destination created
3. Assert dest.size == src.size  ← Verify byte-for-byte size match
4. source.unlink()               ← Only now delete source
5. If any step fails → clean up partial copy; source preserved
```

### Collision Avoidance
If the destination filename already exists, an incrementing suffix is added:
```
report.pdf → report_1.pdf → report_2.pdf → ...
```

### DRY_RUN Mode
```
[DRY_RUN] Would move: quarterly_report.pdf → Done/20260219_quarterly_report.pdf
```
No filesystem changes occur. Returns the would-be destination path.

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| Source file not found | Returns `None`; logs ERROR |
| Destination dir creation fails | Returns `None`; logs ERROR |
| Copy fails | Returns `None`; logs ERROR; partial copy cleaned up |
| Size verification fails | Returns `None`; logs ERROR; partial copy cleaned up |
| Source deletion fails | Logs WARNING; destination kept (duplicate exists) |

**Critical:** Source file is **never deleted** if any verification step fails.
The worst outcome is a duplicate — never data loss.

---

## Standard Vault Workflows

### Task Completion Flow
```python
FileMover.move(task_file, Done_dir, f"{timestamp}_{task_file.name}")
FileMover.move(meta_file, Done_dir, f"{timestamp}_{meta_file.name}")
```

### Approval Routing Flow
```python
FileMover.copy_to(plan_file, Pending_Approval_dir)
FileMover.copy_to(meta_file, Pending_Approval_dir)
# Originals stay in Plans/ and Needs_Action/
```

---

## Implementation Notes

```python
# Bronze Tier — shutil-based local filesystem operations
shutil.copy2(source, dest)
source.unlink()

# [LLM_HOOK] Silver+:
# await mcp_client.move_file(str(source), str(dest))
# (MCP handles copy-verify-delete internally)
```

---

## Reusability Notes

- Stateless; safe for sequential calls (not concurrent on same file).
- `_safe_path()` helper prevents silent overwrites.
- Works with any two vault directories — not limited to specific folders.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | Swap shutil calls for MCP filesystem server operations |
| Gold | Add move event emission for Ralph Wiggum loop |
| Platinum | Add distributed move support for cloud vault mirrors |

---

## Example Usage

```python
from claude_agent import FileMover
from pathlib import Path

vault = Path("AI_Employee_Vault")

# Move completed task to Done/
result = FileMover.move(
    source   = vault / "Needs_Action" / "report.pdf",
    dest_dir = vault / "Done",
    new_name = "20260219_120000_report.pdf"
)
if result:
    print(f"Moved to: {result}")
else:
    print("Move failed — check logs")

# Copy plan to Pending_Approval (preserves original)
FileMover.copy_to(
    source   = vault / "Plans" / "plan.md",
    dest_dir = vault / "Pending_Approval"
)
```

---

*File Mover Skill v1.0.0 | Bronze Tier | Layer: Action*
