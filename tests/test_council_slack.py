"""
End-to-End Test: Council Pipeline with Slack Integration
Processes static transcript and sends output to Slack channel.
"""

import asyncio
import json
import logging
from app.state import MeetingState, MeetingMetadata, TranscriptSegment
from app.graph.workflow_council import run_council_pipeline
from app.services.storage import db
from app.services.slack import slack_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_with_slack():
    """
    Full pipeline test with Slack integration:
    1. Load static transcript
    2. Run Council pipeline (will pause at human_review)
    3. Save to MongoDB with status="pending"
    4. Send draft to Slack channel
    5. Wait for user DM (via running server)
    """
    
    print("\n" + "="*80)
    print("🏛️ COUNCIL PIPELINE - END-TO-END TEST WITH SLACK")
    print("="*80 + "\n")
    
    # Auto-approve any abandoned active_review meetings from previous runs
    approved_count = await db.auto_approve_active_reviews()
    if approved_count > 0:
        print(f"🔄 Auto-approved {approved_count} abandoned meeting(s) from previous session\n")
    
    # 1. Load Blackbrook transcript
    print("📂 Loading Blackbrook Case & Team Cube Ads transcript...")
    with open("tests/Blackbrook-Case-and-Team-Cube-Ads-2bc1edcb-2eeb.json", "r") as f:
        raw_transcript = json.load(f)
    
    # Extract unique speakers from transcript
    speakers = list(set([s["speaker_name"] for s in raw_transcript]))
    
    # Build MeetingState from raw transcript format
    initial_state = MeetingState(
        meeting_id="BLACKBROOK_ADS_001",
        metadata=MeetingMetadata(
            title="Blackbrook Case and Team Cube Ads",
            date="2024-12-14",
            participants=speakers
        ),
        transcript=[
            TranscriptSegment(
                speaker=s["speaker_name"],
                text=s["sentence"],
                start_time=s.get("startTime", "00:00"),
                end_time=s.get("endTime", "00:00")
            ) for s in raw_transcript
        ]
    )
    
    print(f"✅ Loaded: {initial_state.metadata.title}")
    print(f"   Meeting ID: {initial_state.meeting_id}")
    print(f"   Transcript segments: {len(initial_state.transcript)}\n")
    
    # 2. Run Council Pipeline
    print("="*80)
    print("🚀 RUNNING COUNCIL PIPELINE")
    print("="*80 + "\n")
    
    final_state = await run_council_pipeline(
        initial_state, 
        thread_id=initial_state.meeting_id
    )
    
    print("\n" + "="*80)
    print("⏸️ PIPELINE PAUSED AT HUMAN REVIEW CHECKPOINT")
    print("="*80 + "\n")
    
    # 3. Save to MongoDB
    print("💾 Saving state to MongoDB...")
    await db.save_meeting(final_state)
    print(f"✅ Saved with human_feedback.status = '{final_state.human_feedback.status}'")
    
    # CRITICAL: Activate this meeting for feedback loop
    final_state.human_feedback.status = "active_review"
    await db.save_meeting(final_state)
    print(f"🔄 Activated for review (status = 'active_review')\n")
    
    # 4. Display what will be sent to Slack
    print("="*80)
    print("📊 COUNCIL OUTPUT SUMMARY")
    print("="*80 + "\n")
    
    print(f"🎯 Strategist: {final_state.strategist.meeting_type} / {final_state.strategist.tone}")
    print(f"📊 Extractor: {len(final_state.extractor.commitments)} commitments, {len(final_state.extractor.decisions)} decisions")
    print(f"⚖️ Critic: Both approved = {final_state.critic.strategist_approved and final_state.critic.extractor_approved}")
    print(f"📧 Email Subject: {final_state.email.subject}\n")
    
    # 5. Send to Slack (if in active review mode)
    if final_state.human_feedback.status == "active_review":
        print("="*80)
        print("📢 SENDING TO SLACK CHANNEL")
        print("="*80 + "\n")
        
        # Send notification (no channel_id = uses webhook)
        slack_service.send_notification(final_state)
        
        print("✅ Draft sent to Slack!\n")
        print("="*80)
        print("👤 NEXT STEPS FOR YOU:")
        print("="*80)
        print("1. Check your Slack channel - you should see the draft")
        print("2. Start the server: uvicorn app.main:app --reload")
        print("3. DM the Cube Bot with feedback, e.g.:")
        print("   'Add a task for Bob to review the budget by Monday'")
        print("4. The bot will resume the pipeline and send updated draft")
        print("="*80 + "\n")
    else:
        print("⚠️ Pipeline completed without pause (unexpected)\n")

if __name__ == "__main__":
    print("\n")
    print("╔" + "═"*78 + "╗")
    print("║" + " "*15 + "END-TO-END COUNCIL PIPELINE TEST" + " "*31 + "║")
    print("╚" + "═"*78 + "╝")
    print("\n")
    
    asyncio.run(test_with_slack())
    
    print("\n🏛️ Test Complete! Check Slack and start the server.\n")
