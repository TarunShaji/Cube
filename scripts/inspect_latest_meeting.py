"""
Script to Inspect the Latest Meeting in MongoDB.
Use this to debug transcript content and participant lists.
"""

import asyncio
import logging
from app.services.storage import db

# Configure logging
logging.basicConfig(level=logging.INFO)

async def inspect_latest():
    print("\n" + "="*80)
    print("🔍 INSPECTING LATEST MEETING")
    print("="*80 + "\n")
    
    try:
        meeting = await db.get_latest_meeting()
        
        if not meeting:
            print("❌ No meetings found in database.")
            return

        print(f"✅ Meeting ID: {meeting.meeting_id}")
        print(f"📅 Date: {meeting.metadata.date}")
        print(f"📝 Title: {meeting.metadata.title}")
        print(f"👥 Participants ({len(meeting.metadata.participants)}):")
        for p in meeting.metadata.participants:
            print(f"   - {p}")
            
        print("\n" + "-"*40)
        print("📜 TRANSCRIPT PREVIEW (First 20 lines):")
        print("-"*40)
        
        for i, segment in enumerate(meeting.transcript[:20]):
            print(f"[{i+1}] {segment.speaker}: {segment.text[:100]}...")
            
        print("\n" + "="*80)
        print("✅ DONE")
        print("="*80 + "\n")

    except Exception as e:
        print(f"❌ Error fetching meeting: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_latest())
