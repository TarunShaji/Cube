from typing import List, Optional, Dict, Any
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

# ============================================================
# Council Architecture Models (New)
# ============================================================

class StrategistOutput(BaseModel):
    """Output from the Strategist Agent (Context & Tone Analysis)"""
    meeting_type: str = "Unknown"  # "Client-Facing" | "Internal" | "Unknown"
    tone: str = "Professional"  # "Professional" | "Urgent" | "Celebratory" | "Neutral"
    sentiment: str = "Neutral"  # "Positive" | "Neutral" | "Critical"
    evidence_timestamps: List[str] = Field(default_factory=list)  # Proof citations from transcript
    confidence: float = 0.0  # 0.0 to 1.0

class ExtractorOutput(BaseModel):
    """Output from the Extractor Agent (Structured Data)"""
    commitments: List[Commitment] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)  # e.g., {"budget": 10000, "deadline": "2024-01-15"}
    decisions: List[str] = Field(default_factory=list)

class CriticVerification(BaseModel):
    """Output from the Critic Agent (Validation Results)"""
    strategist_approved: bool = False
    extractor_approved: bool = False
    strategist_feedback: Optional[str] = None
    extractor_feedback: Optional[str] = None
    overall_status: str = "pending"  # "pending" | "approved" | "rejected"

class HumanFeedback(BaseModel):
    """Human-in-the-Loop Feedback"""
    status: str = "pending"  # "pending" | "active_review" | "approved"
    instructions: Optional[str] = None
    timestamp: Optional[str] = None
    slack_user_id: Optional[str] = None

# ============================================================
# Main State Object
# ============================================================

class MeetingState(BaseModel):
    # Core Identity
    meeting_id: str
    metadata: MeetingMetadata = Field(default_factory=MeetingMetadata)
    transcript: List[TranscriptSegment] = Field(default_factory=list)
    
    # Council Architecture Outputs (New)
    strategist: StrategistOutput = Field(default_factory=StrategistOutput)
    extractor: ExtractorOutput = Field(default_factory=ExtractorOutput)
    critic: CriticVerification = Field(default_factory=CriticVerification)
    email: EmailDraft = Field(default_factory=EmailDraft)
    
    # Control Flow (New)
    human_feedback: HumanFeedback = Field(default_factory=HumanFeedback)
    retry_counts: Dict[str, int] = Field(default_factory=dict)  # {"strategist": 0, "extractor": 0}
    last_modified: Optional[str] = None  # ISO timestamp for sorting pending meetings
    
    # Legacy Fields (Deprecated - for backward compatibility during migration)
    # TODO: Remove after full migration
    intent_context: IntentContext = Field(default_factory=IntentContext)
    topics: List[TopicSegment] = Field(default_factory=list)
    commitments: List[Commitment] = Field(default_factory=list)
    validation: ValidationResult = Field(default_factory=ValidationResult)

