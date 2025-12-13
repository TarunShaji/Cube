import asyncio
from app.services.storage import db

async def list_meetings():
    print("Checking MongoDB for meetings...")
    cursor = db.meetings.find({})
    count = 0
    async for doc in cursor:
        count += 1
        print(f"FOUND: {doc.get('meeting_id')} | {doc.get('metadata', {}).get('title')}")
    
    if count == 0:
        print("No meetings found yet.")

if __name__ == "__main__":
    asyncio.run(list_meetings())
