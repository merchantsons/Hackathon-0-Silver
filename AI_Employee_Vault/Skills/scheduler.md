# Skill: Scheduler

**Class:** `OrchestratorState` (schedule logic) + Windows Task Scheduler
**Tier:** Silver
**Files:** `orchestrator.py`, `setup_task_scheduler.bat`
**Introduced in:** v2.0.0

---

## Purpose

Manages time-based automation so the AI Employee proactively acts on schedule
rather than waiting for human triggers. Silver tier uses two scheduling layers:

1. **Built-in Orchestrator scheduler** — monitors time inside `orchestrator.py`
2. **Windows Task Scheduler** — OS-level cron for startup and periodic tasks

---

## Scheduled Tasks

| Task | Default Schedule | Configurable |
|------|-----------------|--------------|
| Update Dashboard | Every 5 min | `ORCHESTRATOR_POLL` |
| Daily Briefing | 8:00 AM | `DAILY_BRIEFING_TIME` |
| Weekly CEO Briefing | Monday 7:00 AM | `WEEKLY_BRIEFING_DAY/TIME` |
| LinkedIn Post Generation | 9:00 AM | `LINKEDIN_POST_TIME` |
| Process Approved Items | Every 30 sec | `ORCHESTRATOR_POLL` |

---

## Orchestrator Scheduling (Built-in)

The orchestrator runs a main loop that checks time-based conditions:

```python
# orchestrator.py checks these on every poll:
if state.should_run_daily_briefing():   # 8:00 AM, once per day
    run_daily_briefing(state)

if state.should_run_weekly_briefing():  # Monday 7:00 AM
    run_weekly_ceo_briefing(state)

if state.should_generate_linkedin():    # 9:00 AM, once per day
    run_linkedin_generation(state)
```

State is persisted to `Logs/orchestrator_state.json` so schedules survive
restarts.

---

## Windows Task Scheduler Setup

Run once as Administrator:

```batch
setup_task_scheduler.bat
```

Creates these Task Scheduler tasks:

| Task Name | Trigger | Action |
|-----------|---------|--------|
| AIEmployee\Orchestrator | On login + 2min delay | run_orchestrator.bat |
| AIEmployee\ClaudeAgent | Every 5 minutes | python claude_agent.py |
| AIEmployee\DailyBriefing | 8:00 AM daily | python claude_agent.py --update-dashboard |
| AIEmployee\WeeklyBriefing | Monday 7:00 AM | python claude_agent.py --briefing |

---

## Configuration (`.env`)

```env
# Scheduled task times (24-hour format HH:MM)
DAILY_BRIEFING_TIME=08:00
WEEKLY_BRIEFING_DAY=0       # 0=Monday, 6=Sunday
WEEKLY_BRIEFING_TIME=07:00
LINKEDIN_POST_TIME=09:00
ORCHESTRATOR_POLL=30        # seconds between orchestrator polls
```

---

## Manual Triggers

Any scheduled task can be run on-demand:

```batch
# Generate CEO Briefing now
run_orchestrator.bat --briefing

# Force-process all Approved/ items
run_orchestrator.bat --dispatch

# Generate LinkedIn post now
python claude_agent.py --linkedin-post

# Refresh Dashboard now
python claude_agent.py --update-dashboard
```

---

## Schedule State

The orchestrator persists its last-run times to `Logs/orchestrator_state.json`:

```json
{
  "last_daily_briefing": "2026-02-21",
  "last_weekly_briefing": "2026-02-17",
  "last_linkedin_gen": "2026-02-21",
  "total_dispatched": 12
}
```

This prevents double-runs if the orchestrator restarts mid-day.

---

## Monitoring

Check schedule health via:

```batch
run_orchestrator.bat --status
```

Or view the Dashboard in Obsidian — the Integration Status table shows
when each component last ran.

---

*Scheduler Skill — Silver Tier | AI Employee v2.0.0*
