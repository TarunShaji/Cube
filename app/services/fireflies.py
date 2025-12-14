import requests
import logging
from app.config import settings
from app.state import MeetingState, MeetingMetadata, TranscriptSegment

logger = logging.getLogger(__name__)

class FirefliesClient:
    API_URL = "https://api.fireflies.ai/graphql"

    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.FIREFLIES_API_KEY}",
            "Content-Type": "application/json"
        }

    def get_transcript(self, meeting_id: str) -> MeetingState:
        query = """
        query Transcript($id: String!) {
            transcript(id: $id) {
                id
                title
                date
                participants
                sentences {
                    speaker_name
                    text
                    start_time
                }
            }
        }
        """
        
        try:
            response = requests.post(
                self.API_URL, 
                json={"query": query, "variables": {"id": meeting_id}}, 
                headers=self.headers,
                timeout=10
            )
            if not response.ok:
                logger.error(f"Fireflies API Failed: {response.text}")
                print(f"❌ Fireflies API Error Body: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            
            # Debug: Log what we got from Fireflies
            logger.info(f"🔍 DEBUG: Fireflies API response keys: {list(data.keys())}")
            
            if "errors" in data:
                logger.error(f"Fireflies API Error: {data['errors']}")
                raise ValueError(f"Fireflies API returned errors: {data['errors']}")

            t_data = data.get("data", {}).get("transcript")
            
            # Debug: Check what transcript data looks like
            if t_data:
                logger.info(f"✅ DEBUG: Got transcript data with keys: {list(t_data.keys())}")
                logger.info(f"   Sentences count: {len(t_data.get('sentences', []))}")
            else:
                logger.error(f"❌ DEBUG: No transcript data found!")
                logger.error(f"   Full response: {data}")
                raise ValueError(f"Meeting {meeting_id} not found or transcript not ready yet")

            # Map to MeetingState
            # Note: Fireflies date is a specific format, we might need to normalize it. 
            # For now, keeping as is or ISO string.
            
            metadata = MeetingMetadata(
                title=t_data.get("title") or "Untitled Meeting",
                date=str(t_data.get("date")),
                participants=t_data.get("participants", [])
            )

            transcript_segments = []
            sentences = t_data.get("sentences") or []  # Handle None when no speech in meeting
            if not sentences:
                logger.warning(f"⚠️ Meeting {meeting_id} has no sentences in transcript")
            
            for s in sentences:
                segment = TranscriptSegment(
                    speaker=s.get("speaker_name") or "Unknown",
                    text=s.get("text") or "",
                    timestamp=str(s.get("start_time"))
                )
                transcript_segments.append(segment)

            return MeetingState(
                meeting_id=meeting_id,
                metadata=metadata,
                transcript=transcript_segments
            )

        except Exception as e:
            logger.error(f"Failed to fetch transcript for {meeting_id}: {e}")
            raise

fireflies_client = FirefliesClient()
