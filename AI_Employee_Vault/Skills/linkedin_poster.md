# Skill: LinkedIn Poster

**Class:** `LinkedInContentGenerator`
**Tier:** Silver
**Files:** `claude_agent.py`, `linkedin_watcher.py`
**Introduced in:** v2.0.0

---

## Purpose

Automates business LinkedIn content creation and publishing to generate sales
and build thought leadership. All posts require **human approval** before
publishing — the system never posts autonomously.

---

## How It Works

### Content Generation (claude_agent.py)

```python
# Generate a post from Business_Goals context
approval_path = LinkedInContentGenerator.generate_from_business_goals()

# Generate a specific post type
approval_path = LinkedInContentGenerator.generate_post(
    context   = "We just completed Project Alpha milestone 2...",
    post_type = "client_success",  # or thought_leadership, product_update, etc.
)
```

### Post Types

| Type | Use Case |
|------|----------|
| `thought_leadership` | Industry insights, opinions, frameworks |
| `product_update` | New features, launches, improvements |
| `client_success` | Anonymised win stories |
| `industry_insight` | Trends, research, data-driven content |
| `team_culture` | Behind the scenes, values, hiring |

---

## Approval Workflow

```
Trigger (scheduled / manual / LinkedIn notification)
    ↓
LinkedInContentGenerator.generate_post()
    ↓
AI drafts post body (LLM or template fallback)
    ↓
Writes to Pending_Approval/TIMESTAMP_linkedin_post_TYPE.md
    ↓
Human reviews in Obsidian
    ↓
Move to Approved/ (publish) or Rejected/ (discard)
    ↓
LinkedInWatcher detects .md in Approved/
    ↓
Posts via LinkedIn API or Playwright
    ↓
Audit log → Logs/linkedin_posts.jsonl
    ↓
File moved to Done/
```

---

## Triggers

| Trigger | How |
|---------|-----|
| Manual | `python claude_agent.py --linkedin-post` |
| Scheduled (daily) | Orchestrator at `LINKEDIN_POST_TIME` |
| LinkedIn notification | LinkedInWatcher detects sales opportunity |
| File drop | Drop a `.txt` with "linkedin" in name to `Inbox/` |

---

## LinkedIn API Setup (Option A — Recommended)

1. Go to [developer.linkedin.com](https://developer.linkedin.com)
2. Create an app → Request "Share on LinkedIn" product
3. Generate access token via OAuth 2.0
4. Add to `.env`:

```env
LINKEDIN_ACCESS_TOKEN=your_bearer_token
LINKEDIN_PERSON_URN=urn:li:person:YOUR_ID
```

## Browser Automation (Option B — Fallback)

```env
LINKEDIN_EMAIL=your@linkedin.com
LINKEDIN_PASSWORD=your_password
```

Requires: `pip install playwright && playwright install chromium`

---

## Content Quality Controls

| Control | Value |
|---------|-------|
| Post frequency | Max 1 per day |
| Minimum length | 150 characters |
| Maximum length | 300 words |
| Required elements | Hook + body + CTA + hashtags |
| Human approval | Always required |
| Political content | Blocked |
| Competitor mentions | Blocked |
| Audit log | `Logs/linkedin_posts.jsonl` |

---

## Generated Post Structure

```
[Hook — compelling first line]

[2-3 paragraphs of value content]

[Call to action — question or invitation]

#Hashtag1 #Hashtag2 #Hashtag3 #Hashtag4 #Hashtag5
```

---

*LinkedIn Poster Skill — Silver Tier | AI Employee v2.0.0*
