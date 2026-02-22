---
skill_id: "dashboard_updater"
skill_name: "Dashboard Updater"
version: "1.0.0"
tier: "bronze"
category: "action"
layer: "action"
implementation: "claude_agent.py::DashboardUpdater"
status: "active"
---

# Skill: Dashboard Updater

## Purpose

Regenerate `Dashboard.md` with live statistics from the current vault state.
The dashboard provides a human-readable snapshot of:
- System health
- Pending workload
- Completed work
- Active alerts
- Quick navigation links

The dashboard is the **primary human interface** to the AI Employee's activity.

---

## Inputs

`update()` takes no arguments. It reads vault state directly via `VaultReader`.

### Data Sources
| Section | Source |
|---------|--------|
| Inbox count | `Inbox/` file count |
| Needs Action count | `Needs_Action/` non-meta, non-md files |
| Plans count | `Plans/` .md files |
| Pending Approval | `Pending_Approval/` file count |
| Done today | `Done/` files modified today |
| Total done | `Done/` total file count |

---

## Outputs

Writes `Dashboard.md` in the vault root. Returns `bool` (True = success).

### Dashboard Sections Generated

| Section | Content |
|---------|---------|
| System Overview | 8-row metrics table |
| Pending Tasks | Up to 15 most recent Needs_Action files with age |
| In Progress | Placeholder (future real-time tracking) |
| Completed Today | Up to 15 Done/ files from today |
| Alerts | Dynamic alert list based on thresholds |
| System Status | Per-component green/yellow/red status |
| Quick Navigation | Obsidian wiki-links to all vault folders |

### Alert Conditions
| Condition | Alert Generated |
|-----------|----------------|
| > 10 items in Needs_Action | ⚠️ High load warning |
| Any items in Pending_Approval | 🔔 Approval needed reminder |
| > 5 items in Inbox (unprocessed) | 📥 Inbox filling warning |

---

## Failure Handling

| Scenario | Behaviour |
|----------|-----------|
| VaultReader fails for one directory | That section shows 0; continues |
| VaultWriter.write() fails | Returns `False`; logs ERROR |
| Dashboard.md doesn't exist | Created fresh |
| DRY_RUN=true | Logs content size; returns True; no write |

---

## Update Frequency

| Trigger | When |
|---------|------|
| Automatic | End of every `ActionProcessor.run()` call |
| Manual | `python claude_agent.py --update-dashboard` |
| Scheduled | Not implemented in Bronze (add cron/Task Scheduler in Silver) |

---

## Implementation Notes

```python
# Bronze Tier — File count statistics from directory listings
inbox_count = len(VaultReader.list_files(INBOX_DIR))
task_files  = [f for f in na_files if not f.stem.endswith("_meta")]
done_today  = [f for f in done_files
               if datetime.fromtimestamp(f.stat().st_mtime).date() == now.date()]

# [LLM_HOOK] Silver+:
# For each pending task, generate a one-line AI summary:
# summaries = []
# for task_file in task_files[:5]:
#     content = VaultReader.read_file(task_file)
#     summary = llm.summarise(content, max_words=20)
#     summaries.append(f"| `{task_file.name}` | {summary} |")
```

---

## Dashboard YAML Frontmatter

The generated file includes machine-parseable YAML:
```yaml
---
last_updated: "2026-02-19 12:00:00"
system: "AI Employee - Bronze Tier"
auto_generated: true
---
```

This enables future tooling to check dashboard freshness programmatically.

---

## Reusability Notes

- Stateless; safe to call as frequently as needed.
- Always rewrites Dashboard.md completely (no partial updates).
- DRY_RUN-safe; propagates via global flag.
- Can be called independently without running ActionProcessor.

---

## Future Tier Compatibility

| Tier | Change Required |
|------|----------------|
| Silver | Add AI-generated task summaries (1 line per pending task) |
| Gold | Add real-time streaming updates (WebSocket or file watch) |
| Platinum | Add multi-agent workload distribution visualisation |

---

## Example Usage

```python
from claude_agent import DashboardUpdater

# Refresh dashboard after any vault changes
DashboardUpdater.update()

# Standalone from CLI
# python claude_agent.py --update-dashboard
```

---

*Dashboard Updater Skill v1.0.0 | Bronze Tier | Layer: Action*
