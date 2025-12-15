# Cube Intelligence: Project Overview

## 🎯 Objective

**Cube** is a post-meeting automation system that transforms Fireflies.ai transcripts into actionable intelligence with human-in-the-loop refinement. It extracts commitments, decisions, and metrics from meetings and drafts professional follow-up emails.

---

## 🔄 Complete Workflow

```mermaid
flowchart TD
    A[Fireflies.ai] -->|Webhook| B[/webhook/fireflies]
    B -->|GraphQL API| C[Fetch Transcript]
    C --> D[(MongoDB)]
    D --> E[Council Pipeline]
    E --> F[Slack Draft]
    F -->|User Feedback| G[Refiner Agent]
    G --> F
    F -->|Approve Button| H[Gmail Compose]
```

### Step-by-Step Flow

| Step | Component | Action |
|------|-----------|--------|
| 1 | Fireflies | Sends webhook when transcription completes |
| 2 | `webhook.py` | Receives `meetingId`, deduplicates, enqueues task |
| 3 | `fireflies.py` | Queries GraphQL API for transcript |
| 4 | `storage.py` | Saves `MeetingState` to MongoDB |
| 5 | `workflow_council.py` | Runs agentic pipeline |
| 6 | `slack.py` | Posts draft to Slack with Approve button |
| 7 | `slack_events.py` | Handles user feedback, resumes pipeline |
| 8 | `interactions.py` | Handles Approve button click |
| 9 | Browser | Opens Gmail with pre-filled draft |

---

## 💾 Storage Architecture

### MongoDB Collections

| Collection | Purpose |
|------------|---------|
| `meetings` | Stores `MeetingState` documents (transcript, analysis, email drafts) |
| `checkpoints` | LangGraph checkpoints for pause/resume |
| `checkpoint_writes` | Checkpoint metadata |

### What's Stored

```python
MeetingState {
    meeting_id: str           # Unique identifier
    metadata: {title, date, participants}
    transcript: [{speaker, text, start_time, end_time}]
    strategist: {meeting_type, tone, sentiment, evidence}
    extractor: {commitments, decisions, metrics}
    critic: {approved, feedback}
    email: {subject, body}
    human_feedback: {status, instructions, slack_user_id, channel_id}
}
```

### Status Flow

```
pending → active_review → approved
```

| Status | Meaning |
|--------|---------|
| `pending` | Pipeline paused, not yet sent to Slack |
| `active_review` | Draft in Slack, accepting feedback |
| `approved` | User clicked Approve, workflow complete |

### Deduplication

- **In-memory set**: `SEEN_MEETINGS` prevents duplicate webhook processing
- **MongoDB check**: `meeting_exists()` prevents re-processing across restarts
- **Auto-approve stale**: `auto_approve_active_reviews()` clears old sessions when new meeting arrives

---

## 🤖 Agentic Pipeline (Council Architecture)

### Agent Roles

| Agent | Purpose | Output |
|-------|---------|--------|
| **Strategist** | Context analysis | `meeting_type`, `tone`, `sentiment` |
| **Extractor** | Data extraction | `commitments`, `decisions`, `metrics` |
| **Critic** | Cross-validation | Approve/Reject with feedback |
| **Copywriter** | Email drafting | `email.subject`, `email.body` |
| **Refiner** | Apply human feedback | Updated `email` |

### Pipeline Flow

```
┌─────────────┐     ┌─────────────┐
│ Strategist  │────→│   Critic    │←────│ Extractor   │
│ (Parallel)  │     │ (Validate)  │     │ (Parallel)  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┴────────────┐
              │ Approved? → Copywriter  │
              │ Rejected? → Retry (3x)  │
              └────────────┬────────────┘
                           ↓
                   ┌──────────────┐
                   │ Human Review │ ⏸️ PAUSE
                   │ (interrupt)  │
                   └──────┬───────┘
                          │
              ┌───────────┴───────────┐
              │ Feedback? → Refiner   │
              │ Approved? → END       │
              └───────────────────────┘
```

### LangGraph Features Used

- **Parallel Execution**: Strategist + Extractor run simultaneously
- **Conditional Routing**: Critic decides next step
- **Interrupt**: Pauses at `human_review` node
- **Checkpointing**: MongoDB persistence for resume
- **Retry Loop**: Up to 3 attempts per agent

---

## 📢 Slack Integration

### Output Format

```
┌──────────────────────────────────────────┐
│ 🧠 Cube Intelligence: Meeting Title      │
├──────────────────────────────────────────┤
│ Date: 2024-12-14  |  Intent: N/A         │
├──────────────────────────────────────────┤
│ Goal: [Extracted goal]                   │
│ Action Items: [List of commitments]      │
├──────────────────────────────────────────┤
│ Draft Email:                             │
│ ```                                      │
│ [Full email body]                        │
│ ```                                      │
├──────────────────────────────────────────┤
│ [✅ Approve & Open Gmail]                │
├──────────────────────────────────────────┤
│ 💡 Reply to refine, or click Approve     │
└──────────────────────────────────────────┘
```

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /slack/events` | Receives Slack messages (user feedback) |
| `POST /slack/interactions` | Handles button clicks (Approve) |

### Feedback Loop

1. User DMs the bot with feedback
2. `slack_events.py` finds `active_review` meeting
3. Resumes pipeline with new feedback
4. Refiner applies changes, Copywriter re-drafts
5. Updated draft sent back to same channel
6. Loop continues until Approve clicked

---

## 🔐 Environment Variables

| Variable | Purpose |
|----------|---------|
| `FIREFLIES_API_KEY` | Authentication for Fireflies GraphQL API |
| `MONGODB_URI` | Connection string for MongoDB Atlas |
| `GEMINI_API_KEY` | Google Generative AI (LLM for all agents) |
| `SLACK_WEBHOOK_URL` | Default channel for notifications (fallback) |
| `SLACK_BOT_TOKEN` | Bot token for dynamic channel messaging |
| `SLACK_SIGNING_SECRET` | Verifies incoming Slack requests |

---

## ✅ Key Features

### 1. Automation
- Fully automated: Fireflies → Intelligence → Slack → Gmail
- No manual transcript processing required
- Background task processing (`BackgroundTasks`)

### 2. Deduplication
- In-memory set (`SEEN_MEETINGS`)
- MongoDB existence check
- Prevents duplicate processing across server restarts

### 3. Human-in-the-Loop
- Pipeline pauses for human review
- Iterative refinement via Slack DMs
- Explicit approval required before Gmail

### 4. Agentic Intelligence
- Multi-agent collaboration (Council Architecture)
- Cross-validation (Critic agent)
- Self-correction (retry loops)

### 5. Persistence
- Checkpoints survive server restarts
- Resume from exact pause point
- Full state recovery

### 6. Gmail Integration
- One-click email drafting
- Pre-filled subject and body
- Opens in user's browser

---

## 📁 Key Files

| Category | Files |
|----------|-------|
| **API** | `main.py`, `webhook.py`, `slack_events.py`, `interactions.py` |
| **Pipeline** | `workflow_council.py`, `nodes_council.py`, `checkpoint_saver.py` |
| **Services** | `fireflies.py`, `slack.py`, `storage.py` |
| **State** | `state.py` |
| **Config** | `config.py`, `.env` |
