import requests
import time
import sys
import asyncio
from app.services.storage import db
from app.services.fireflies import fireflies_client

# USAGE: python3 tests/test_ingestion_manual.py <MEETING_ID>

async def test_direct_api(meeting_id):
    print(f"\n--- STEP 1: Testing Fireflies API Direct Fetch for {meeting_id} ---")
    try:
        meeting_state = fireflies_client.get_transcript(meeting_id)
        print("✅ Success! Fireflies API returned valid transcript.")
        print(f"Title: {meeting_state.metadata.title}")
        print(f"Participants: {meeting_state.metadata.participants}")
        print(f"Transcript Segments: {len(meeting_state.transcript)}")
        if meeting_state.transcript:
            print(f"Preview: \"{meeting_state.transcript[0].text[:100]}...\"")
        return True
    except Exception as e:
        print(f"❌ Failed to fetch from Fireflies API directly: {e}")
        print("Check your FIREFLIES_API_KEY and Meeting ID.")
        return False

def trigger_webhook(meeting_id):
    print(f"\n--- STEP 2: Triggering Webhook to Local Server ---")
    url = "http://localhost:8000/webhook/fireflies"
    payload = {
        "event": "meeting.completed",
        "meeting_id": meeting_id
    }
    try:
        print(f"Sending POST to {url}...")
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        print(f"✅ Webhook accepted by server. Response: {resp.json()}")
    except Exception as e:
        print(f"❌ Webhook failed: {e}")
        print("Is the server running? (uvicorn app.main:app --reload)")
        sys.exit(1)

async def check_db(meeting_id):
    print(f"\n--- STEP 3: Verifying MongoDB Persistence ---")
    print(f"Polling DB for meeting_id: {meeting_id}...")
    max_retries = 15
    for i in range(max_retries):
        meeting = await db.get_meeting(meeting_id)
        if meeting:
            print("\n✅ SUCCESS: Meeting found in MongoDB!")
            print(f"Title: {meeting.metadata.title}")
            print(f"Stored Segments: {len(meeting.transcript)}")
            return
        
        sys.stdout.write(".")
        sys.stdout.flush()
        await asyncio.sleep(2)
    
    print("\n\n❌ TIMEOUT: Meeting not found in DB after 30 seconds.")
    print("Check your server terminal for error logs (likely in background task).")

async def main(m_id):
    # 1. Direct API Test (Client-side verify)
    success = await test_direct_api(m_id)
    if not success:
        print("Aborting webhook test since API fetch failed.")
        return

    # 2. Trigger Webhook
    trigger_webhook(m_id)
    
    # 3. Check DB
    await check_db(m_id)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Please provide a real Fireflies Meeting ID.")
        print("Example: python3 tests/test_ingestion_manual.py <id>")
        sys.exit(1)
        
    asyncio.run(main(sys.argv[1]))
