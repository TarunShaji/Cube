from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.state import MeetingState

class StorageService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URI)
        self.db = self.client.get_database("cube_intelligence")
        self.meetings = self.db.get_collection("meetings")

    async def save_meeting(self, meeting_state: MeetingState):
        """
        Persists the meeting state.
        Uses upsert to ensure strict one-to-one mapping by meeting_id.
        """
        await self.meetings.replace_one(
            {"meeting_id": meeting_state.meeting_id},
            meeting_state.model_dump(),
            upsert=True
        )

    async def get_meeting(self, meeting_id: str) -> MeetingState:
        doc = await self.meetings.find_one({"meeting_id": meeting_id})
        if not doc:
            return None
        return MeetingState(**doc)

    async def mark_failed(self, meeting_id: str, error: str):
        """
        Updates specific fields to mark failure without overwriting unrelated state if possible,
        or creates a stub if it doesn't exist.
        """
        await self.meetings.update_one(
            {"meeting_id": meeting_id},
            {
                "$set": {
                    "validation.is_valid": False,
                    "validation.errors": [error] # Append or set? Spec says "Set state -> FAILED"
                }
            },
            upsert=True
        )

    async def meeting_exists(self, meeting_id: str) -> bool:
        """
        Efficiently checks if a meeting exists in the DB (projection=only _id).
        """
        doc = await self.meetings.find_one({"meeting_id": meeting_id}, {"_id": 1})
        return doc is not None

db = StorageService()
