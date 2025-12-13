# Cube Intelligence: Post-Meeting Automation

Cube is a trust-critical backend system that processes meeting transcripts to produce auditable, evidence-backed post-meeting intelligence (Action Items, Decisions, Draft Emails).

## 🚀 Core Features

*   **Zero-Hallucination Philosophy**: Commitments are only extracted if supported by verbatim evidence from the transcript.
*   **Contract-Based Architecture**: Strict data contracts between Ingestion, Processing, and Output layers.
*   **Multi-Agent Pipeline**: 6 specialized LangGraph agents (using Gemini 1.5/2.0) for intent classification, topic segmentation, and commitment verification.
*   **Persistent Deduplication**: Idempotent processing using MongoDB to ensure meetings are never processed twice.
*   **Slack Integration**: Delivers executive summaries and draft emails directly to your team channel.
*   **Interactive Refinement (Bot)**: Reply to the bot to refine drafts (e.g., "Add a task for Alice", "Rewrite email") without re-running the full pipeline.

## 🛠️ Architecture

**Flow**: `Fireflies` → `MongoDB` → `Pipeline` → `Slack` ↔️ `Refinement Agent`

1.  **Ingestion (Contract A)**:
    *   Receives `Transcription completed` webhook from Fireflies.ai.
    *   Fetches full transcript via GraphQL.
    *   Persists raw state to MongoDB.
    *   Prevents duplicate processing via in-memory set and DB existence checks.

2.  **Intelligence (Contract B)**:
    *   **Intent Agent**: Classifies meeting type (Daily Sync, Strategy, etc).
    *   **Topic Agent**: Segments transcript into logical blocks and decisions.
    *   **Commitment Agent**: Extracts tasks with owner, due date, and *verbatim evidence*.
    *   **Verification Agent**: Filters weak or ambiguous tasks.
    *   **Email Agent**: Drafts a professional, executive-style follow-up email.
    *   **Guardrail Agent**: Validates schema and quality before output.

3.  **Output (Contract C)**:
    *   Formats intelligence into a structured Slack message (Block Kit).
    *   Includes Goals, Decisions, Evidence-backed Action Items, and the Draft Email.

4.  **Refinement (Contract D)**:
    *   Listens for Slack Events (`app_mention`, `message`).
    *   Infers context from the latest processed meeting.
    *   **Refinement Agent** applies user instructions (deltas) to the existing state.
    *   Updates MongoDB and replies with the *updated* draft in the same channel.

## 📦 Tech Stack

*   **Language**: Python 3.9+
*   **Framework**: FastAPI
*   **Orchestration**: LangGraph / LangChain
*   **LLM**: Google Gemini (1.5 Flash / 2.0 Flash)
*   **Database**: MongoDB (Motor AsyncIO)
*   **Integrations**: Fireflies.ai (GraphQL), Slack (Webhooks & Events API)

## ⚙️ Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/TarunShaji/Cube.git
    cd Cube
    ```

2.  **Install Dependencies**:
    ```bash
    python3 -m venv cube
    source cube/bin/activate
    pip install -r requirements.txt
    ```

3.  **Environment Variables**:
    Create a `.env` file:
    ```env
    FIREFLIES_API_KEY=...
    MONGODB_URI=...
    GEMINI_API_KEY=...
    
    # Slack Integration
    SLACK_WEBHOOK_URL=...
    SLACK_BOT_TOKEN=...
    SLACK_SIGNING_SECRET=...
    
    # Optional: LangSmith Tracing
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=...
    ```

## 🏃 Usage

**Start the Server**:
```bash
uvicorn app.main:app --reload
```

**Run Manual Test (Static Transcript)**:
```bash
PYTHONPATH=. python3 tests/test_pipeline.py
```

**Run End-to-End Ingestion Test**:
```bash
python3 tests/test_ingestion_manual.py
```
