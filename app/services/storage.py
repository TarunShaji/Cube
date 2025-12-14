from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.state import MeetingState
from datetime import datetime, timezone

class StorageService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URI)
        self.db = self.client.get_database("cube_intelligence")
        self.meetings = self.db.get_collection("meetings")

    async def save_meeting(self, meeting_state: MeetingState):
        """
        Persists the meeting state.
        Uses upsert to ensure strict one-to-one mapping by meeting_id.
        Sets last_modified timestamp for proper sorting.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Set last_modified to current UTC time
        meeting_state.last_modified = datetime.now(timezone.utc).isoformat()
        
        # Debug logging
        logger.info(f"💾 DEBUG: Saving meeting {meeting_state.meeting_id[:15]}...")
        logger.info(f"   human_feedback.status: {meeting_state.human_feedback.status}")
        logger.info(f"   last_modified: {meeting_state.last_modified}")
        
        await self.meetings.replace_one(
            {"meeting_id": meeting_state.meeting_id},
            meeting_state.model_dump(),
            upsert=True
        )
        
        logger.info(f"✅ DEBUG: Meeting saved successfully")

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

    async def save_refinement_request(self, request_data: dict):
        """
        Stores a user refinement request (from Slack).
        """
        refinements = self.db.get_collection("refinement_requests")
        await refinements.insert_one(request_data)

    async def get_latest_meeting(self) -> MeetingState:
        """
        Retrieves the most recently modified meeting.
        """
        # Sort by natural insertion order or a timestamp if we had one indexed.
        # Ideally we'd have a 'processed_at' field, but _id is decent proxy for now along with our manual dates.
        # Actually, let's just sort by _id desc (natural creation order)
        doc = await self.meetings.find_one({}, sort=[("_id", -1)])
        if not doc:
            return None
        return MeetingState(**doc)
    
    async def get_pending_meeting(self) -> MeetingState:
        """
        Retrieves the meeting currently awaiting feedback.
        
        Priority:
        1. FIRST: Check for "active_review" status (meeting currently in Slack feedback loop)
        2. FALLBACK: Check for "pending" status sorted by last_modified (newly paused meetings)
        
        This ensures follow-up feedback always applies to the same meeting until approved.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # PRIORITY 1: Check for meeting in active review (currently in feedback loop)
        logger.info("🔍 DEBUG: Checking for meetings in active_review status...")
        active_doc = await self.meetings.find_one(
            {"human_feedback.status": "active_review"}
        )
        
        if active_doc:
            logger.info(f"✅ DEBUG: Found ACTIVE REVIEW meeting: {active_doc['meeting_id']}")
            logger.info(f"   status: active_review (in feedback loop)")
            return MeetingState(**active_doc)
        
        # PRIORITY 2: Fall back to most recent pending meeting
        logger.info("🔍 DEBUG: No active_review found, checking pending meetings...")
        query = {
            "human_feedback.status": "pending",
            "last_modified": {"$exists": True}
        }
        
        # Debug: First get ALL pending meetings to see what exists
        all_pending = await self.meetings.find({"human_feedback.status": "pending"}).to_list(length=10)
        logger.info(f"📊 DEBUG: Total pending meetings: {len(all_pending)}")
        for meeting in all_pending:
            has_timestamp = "last_modified" in meeting and meeting["last_modified"] is not None
            logger.info(f"   - Meeting {meeting['meeting_id'][:15]}... | "
                       f"has_last_modified: {has_timestamp} | "
                       f"timestamp: {meeting.get('last_modified', 'NONE')}")
        
        # Now execute the actual query
        doc = await self.meetings.find_one(
            query,
            sort=[("last_modified", -1)]  # Most recent modification first
        )
        
        if not doc:
            logger.warning(f"⚠️ DEBUG: No meeting found matching query!")
            return None
        
        logger.info(f"✅ DEBUG: Found PENDING meeting: {doc['meeting_id']}")
        logger.info(f"   last_modified: {doc.get('last_modified')}")
        logger.info(f"   status: pending (will be activated on first feedback)")
        
        return MeetingState(**doc)
    
    async def auto_approve_active_reviews(self) -> int:
        """
        Auto-approves any meetings with status='active_review'.
        Called when a new meeting arrives to clean up abandoned sessions.
        Returns count of meetings approved.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        result = await self.meetings.update_many(
            {"human_feedback.status": "active_review"},
            {"$set": {"human_feedback.status": "approved"}}
        )
        
        if result.modified_count > 0:
            logger.info(f"🔄 Auto-approved {result.modified_count} abandoned meeting(s)")
        
        return result.modified_count


db = StorageService()
