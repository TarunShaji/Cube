from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
import logging
from app.services.fireflies import fireflies_client
from app.services.storage import db
from app.state import MeetingState

router = APIRouter()
logger = logging.getLogger(__name__)

# Process-level in-memory deduplication (Set)
SEEN_MEETINGS = set()

class FirefliesPayload(BaseModel):
    meetingId: str
    eventType: str

async def process_meeting_task(meeting_id: str):
    """
    Background task to process the meeting.
    Fetches transcript and saves to DB.
    """
    if meeting_id in SEEN_MEETINGS:
        logger.info(f"⏩ Skipping duplicate meeting_id: {meeting_id}")
        return

    SEEN_MEETINGS.add(meeting_id)
    
    print(f"\n{'='*60}")
    print(f"🚀 STARTING INGESTION FOR MEETING: {meeting_id}")
    print(f"{'='*60}")
    
    try:
        logger.info(f"📥 Fetching transcript from Fireflies...")
        meeting_state = fireflies_client.get_transcript(meeting_id)
        print(f"✅ Transcript Fetched: \"{meeting_state.metadata.title}\"")
        print(f"   - Participants: {len(meeting_state.metadata.participants)}")
        print(f"   - Segments: {len(meeting_state.transcript)}")
        
        # Save 'TRANSCRIPT_FETCHED' state (conceptually)
        # We start with validation=False by default in the model
        await db.save_meeting(meeting_state)
        print(f"💾 Saved to MongoDB (id={meeting_id})")
        
        # Trigger Intelligence Pipeline (Contract B)
        from app.graph.workflow import run_pipeline
        print(f"🧠 Running Intelligence Pipeline...")
        final_state = await run_pipeline(meeting_state)
        
        # Save Final State
        await db.save_meeting(final_state)
        print(f"💾 Updated MongoDB with Intelligence Results")

        # Send to Slack (Contract C)
        from app.services.slack import slack_service
        slack_service.send_notification(final_state)
        print(f"📢 Notification Sent to Slack")
        
        print(f"{'='*60}")
        print(f"✨ COMPLETED INGESTION FOR {meeting_id}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"❌ Error processing meeting {meeting_id}: {e}")
        print(f"❌ FAILED: {e}")
        await db.mark_failed(meeting_id, str(e))

@router.post("/webhook/fireflies")
async def fireflies_webhook(payload: FirefliesPayload, background_tasks: BackgroundTasks):
    """
    Contract A: Ingestion
    Payload: {'meetingId': '...', 'eventType': 'Transcription completed'}
    """
    print(f"\n🔔 WEBHOOK RECEIVED: Event='{payload.eventType}' | ID='{payload.meetingId}'")
    
    # Accept 'Transcription completed' (what we saw) or 'meeting.completed' (what documentation sometimes says)
    valid_events = ["Transcription completed", "meeting.completed"]
    
    if payload.eventType in valid_events:
        if payload.meetingId in SEEN_MEETINGS:
           logger.info(f"✋ Ignored duplicate webhook for {payload.meetingId} (Memory)")
           return {"status": "ignored_duplicate_mem"}

        # Persistent Check (MongoDB)
        if await db.meeting_exists(payload.meetingId):
            logger.info(f"✋ Ignored duplicate webhook for {payload.meetingId} (DB)")
            # Add to memory so we don't hit DB again this run
            SEEN_MEETINGS.add(payload.meetingId)
            return {"status": "ignored_duplicate_db"}

        # Enqueue heavy lifting
        background_tasks.add_task(process_meeting_task, payload.meetingId)
        print(f"⏳ Task enqueued for background processing...")
        return {"status": "received"}
    
    print(f"⚠️ Ignored event type: {payload.eventType}")
    return {"status": "ignored_event", "event": payload.eventType}
