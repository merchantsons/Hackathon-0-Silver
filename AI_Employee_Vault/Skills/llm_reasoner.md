# Skill: LLM Reasoner

**Class:** `LLMReasoner`
**Tier:** Silver
**File:** `claude_agent.py`
**Introduced in:** v2.0.0

---

## Purpose

Provides intelligent reasoning via Claude Code (Claude API). All AI-powered
features in Silver tier route through this class.

Falls back gracefully to rule-based responses when:
- Claude API key (`ANTHROPIC_API_KEY`) is not set
- `DEV_MODE=true` (offline demo mode)
- The API call fails

---

## Interface

```python
# Check if LLM is available
available: bool = LLMReasoner.is_available()

# Call Claude with a prompt
response: str = LLMReasoner.complete(
    prompt     = "Your task prompt here",
    system_extra = "Additional system context",
    max_tokens = 1024,
)
```

---

## Context Injection

Every LLM call automatically includes:
1. **Company_Handbook.md** — rules of engagement and policies
2. **Business_Goals.md** — current objectives and context

This ensures Claude acts as a company employee, not a generic assistant.

---

## Usage by Other Skills

| Skill | How it uses LLMReasoner |
|-------|------------------------|
| TaskClassifier | Enriches classification with AI analysis |
| PlanGenerator | Generates contextual, task-specific plans |
| EmailDrafter | Creates professional reply drafts |
| LinkedInContentGenerator | Writes engaging business posts |
| CEOBriefingGenerator | Produces executive summaries |

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key (Claude Code) | — (required for LLM) |
| `DEV_MODE=true` | Use fallback responses | false |

---

## Fallback Behaviour

When Claude is unavailable, each skill uses its rule-based fallback:
- `TaskClassifier` → heuristic keyword matching
- `PlanGenerator` → template-based checklists
- `EmailDrafter` → generic professional placeholder
- `LinkedInContentGenerator` → template post with placeholders
- `CEOBriefingGenerator` → stats-only summary

---

*LLM Reasoner Skill — Silver Tier | AI Employee v2.0.0*
