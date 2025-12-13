from typing import List, Optional
from pydantic import BaseModel, Field

class MeetingMetadata(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    participants: List[str] = Field(default_factory=list)

class TranscriptSegment(BaseModel):
    speaker: str
    text: str
    timestamp: Optional[str] = None

class IntentContext(BaseModel):
    meeting_type: Optional[str] = None
    primary_goal: Optional[str] = None
    confidence_notes: Optional[str] = None

class TopicSegment(BaseModel):
    topic_id: str
    summary: str
    start_index: int
    end_index: int
    decisions: List[str] = Field(default_factory=list)

class Commitment(BaseModel):
    task: str
    owner: str = "TBD"  # Us | Them | TBD
    due: str = "TBD"    # YYYY-MM-DD | TBD
    evidence: str

class EmailDraft(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None

class ValidationResult(BaseModel):
    is_valid: bool = False
    errors: List[str] = Field(default_factory=list)

class MeetingState(BaseModel):
    meeting_id: str
    metadata: MeetingMetadata = Field(default_factory=MeetingMetadata)
    transcript: List[TranscriptSegment] = Field(default_factory=list)
    intent_context: IntentContext = Field(default_factory=IntentContext)
    topics: List[TopicSegment] = Field(default_factory=list)
    commitments: List[Commitment] = Field(default_factory=list)
    email: EmailDraft = Field(default_factory=EmailDraft)
    validation: ValidationResult = Field(default_factory=ValidationResult)
