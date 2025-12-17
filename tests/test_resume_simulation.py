"""
Simulation Test: Resume Pipeline Logic
Verifies that `resume_council_pipeline` works correctly when called with feedback.
Crucially, this runs LOCALLY without needing actual Slack connectivity.
"""

import asyncio
import logging
from app.services.storage import db
from app.graph.workflow_council import resume_council_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_resume_simulation():
    print("\n" + "="*80)
    print("🔄 SIMULATION: RESUME PIPELINE WITH FEEDBACK")
    print("="*80 + "\n")
    
    # 1. Find a meeting in 'active_review' or 'pending' state
    # We use the meeting we just created in the previous test
    print("🔍 Looking for a suitable meeting to resume...")
    meeting_state = await db.get_pending_meeting()
    
    if not meeting_state:
        print("❌ No meeting found! Please run `test_council_slack.py` first to generate a pending meeting.")
        return

    meeting_id = meeting_state.meeting_id
    print(f"✅ Found meeting: {meeting_id}")
    print(f"   Current Status: {meeting_state.human_feedback.status}")
    print(f"   Current Subject: {meeting_state.email.subject}")
    
    # 2. Simulate User Feedback
    feedback_text = "Change the email subject to 'URGENT: Application Refinement Needed' and add a new internal task for Nithin to check the server logs."
    slack_user = "U12345678"
    
    print("\n" + "-"*40)
    print("💬 SIMULATING USER FEEDBACK:")
    print(f"'{feedback_text}'")
    print("-"*40 + "\n")
    
    # 3. Call Resume Function
    print("🚀 Calling `resume_council_pipeline`...")
    try:
        updated_state = await resume_council_pipeline(
            thread_id=meeting_id,
            user_feedback=feedback_text,
            slack_user_id=slack_user
        )
        
        if updated_state:
            print("\n" + "="*80)
            print("✅ PIPELINE RESUMED SUCCESSFULLY!")
            print("="*80)
            print(f"📧 New Subject: {updated_state.email.subject}")
            print(f"📋 Metrics/Decisions preserved: {len(updated_state.extractor.decisions)} decisions")
            print(f"📝 Internal Plan Length: {len(updated_state.email.internal_action_plan)} chars")
            
            # Verify the subject changed
            if "URGENT" in updated_state.email.subject:
                 print("✅ VERIFIED: Subject updated correctly")
            else:
                 print("⚠️ WARNING: Subject did not update as expected")
                 
        else:
            print("❌ Resume returned None!")

    except Exception as e:
        print(f"❌ EXECUTION ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_resume_simulation())
