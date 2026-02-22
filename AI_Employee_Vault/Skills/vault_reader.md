---
skill_id: "vault_reader"
skill_name: "Vault Reader"
version: "1.0.0"
tier: "bronze"
category: "perception"
layer: "perception"
implementation: "claude_agent.py::VaultReader"
status: "active"
---

# Skill: Vault Reader

## Purpose

Read files and list directory contents from the AI Employee Vault. This skill
is the primary **read interface** between the AI reasoning layer and the
local filesystem storage layer.

It abstracts all file I/O so that higher-level skills never touch the
filesystem directly — enabling a clean swap to MCP server reads in Silver+.

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | `Path` | Yes (for `read_file`) | Absolute path to a vault file |
| `directory` | `Path` | Yes (for `list_files`) | Vault directory to list |
| `suffix` | `str` | No | Filter by file extension (e.g. `.md`) |

---

## Outputs

| Method | Return Type | Description |
|--------|-------------|-------------|
| `read_file(path)` | `str \| None` | Full text content of file, or `None` on error |
| `list_files(dir, suffix)` | `list[Path]` | Sorted list of file paths (by mtime) |
| `scan_needs_action()` | `list[dict]` | Task descriptor dicts with paired meta files |

### Task Descriptor Format (`scan_needs_action`)
```python
{
    "task_file"   : Path,       # The actual task file
    "meta_file"   : Path|None,  # Paired _meta.md file
    "meta_content": str|None,   # Content of meta file
    "name"        : str,        # Filename
    "stem"        : str,        # Filename without extension
    "extension"   : str,        # Lowercase extension
    "size"        : int,        # File size in bytes
    "modified"    : datetime,   # Last modification time
}
```

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| File not found | Returns `None`; logs ERROR |
| Permission denied | Returns `None`; logs ERROR |
| Directory not found | Returns `[]`; logs ERROR |
| Encoding error | Returns `None`; logs ERROR |

**Principle:** Vault Reader never raises exceptions to callers. All errors
are caught, logged, and expressed as `None` / empty list return values.

---

## Implementation Notes

```python
# Bronze Tier — Direct filesystem reads
content = path.read_text(encoding="utf-8")

# [LLM_HOOK] Silver+ — MCP filesystem server read:
# content = await mcp_client.read_file(path)
```

---

## Reusability Notes

- Call from any skill that needs to read vault content.
- `scan_needs_action()` is the standard entry point for the agent loop.
- All reads are non-destructive and safe to call repeatedly.
- Thread-safe for concurrent read access.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | Swap `read_file` internals to use MCP `filesystem` server |
| Gold | Add caching layer for frequently-read files (e.g. Handbook) |
| Platinum | Add vector-search read for semantic vault queries |

---

## Example Usage

```python
from claude_agent import VaultReader

# Read a specific file
content = VaultReader.read_file(vault_root / "Dashboard.md")

# List all markdown files in Plans/
plans = VaultReader.list_files(plans_dir, suffix=".md")

# Get all pending tasks
tasks = VaultReader.scan_needs_action()
for task in tasks:
    print(task["name"], task["size"])
```

---

*Vault Reader Skill v1.0.0 | Bronze Tier | Layer: Perception*
