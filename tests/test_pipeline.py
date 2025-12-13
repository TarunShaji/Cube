
import asyncio
import json
import logging
from app.state import MeetingState, MeetingMetadata, TranscriptSegment
from app.graph.workflow import run_pipeline

# Configure logging to see agent activity
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("app.graph")
logger.setLevel(logging.INFO)

async def test_pipeline():
    print("--- 🚀 STARTING PIPELINE TEST (STATIC TRANSCRIPT) ---")
    
    # 1. Load Static Transcript
    with open("tests/static_transcript.json", "r") as f:
        raw_data = json.load(f)
    
    # 2. Hydrate State
    initial_state = MeetingState(
        meeting_id=raw_data["meeting_id"],
        metadata=MeetingMetadata(**raw_data["metadata"]),
        transcript=[TranscriptSegment(**t) for t in raw_data["transcript"]]
    )
    
    print(f"Loaded Meeting: {initial_state.metadata.title}")
    print(f"Transcript Length: {len(initial_state.transcript)} segments")
    
    # 3. Run Pipeline
    print("\n--- 🏃 RUNNING AGENTS ---")
    final_state = await run_pipeline(initial_state)
    
    # 4. Print Results
    print("\n--- ✅ PIPELINE COMPLETE ---")
    
    print(f"\n🏷️  INTENT: {final_state.intent_context.meeting_type}")
    print(f"🎯 GOAL: {final_state.intent_context.primary_goal}")
    
    print("\n📚 TOPICS:")
    for t in final_state.topics:
        print(f"  - [{t.start_index}-{t.end_index}] {t.summary}")
        if t.decisions:
            print(f"    Decisions: {t.decisions}")

    print("\n✅ COMMITMENTS (Filtered):")
    if not final_state.commitments:
        print("  (None found)")
    for c in final_state.commitments:
        print(f"  - [Owner: {c.owner} | Due: {c.due}] {c.task}")
        print(f"    Evidence: \"{c.evidence}\"")

    print("\n📧 EMAIL DRAFT:")
    print(f"Subject: {final_state.email.subject}")
    print("-" * 40)
    print(final_state.email.body)
    print("-" * 40)
    
    print("\n🛡️ VALIDATION:")
    print(f"Is Valid: {final_state.validation.is_valid}")
    if final_state.validation.errors:
        print(f"Errors: {final_state.validation.errors}")

    # 4b. Persist to MongoDB (Contract D Prerequisite)
    print("\n💾 SAVING TO MONGODB...")
    from app.services.storage import db
    await db.save_meeting(final_state)
    print(f"Saved meeting {final_state.meeting_id} to DB.")

    # 5. Send to Slack (Test Contract C)
    print("\n--- 📢 SENDING TO SLACK ---")
    from app.services.slack import slack_service
    slack_service.send_notification(final_state)
    print("Notification sent (check your channel).")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
