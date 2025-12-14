from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.state import (
    MeetingState, 
    StrategistOutput, 
    ExtractorOutput, 
    CriticVerification,
    EmailDraft,
    Commitment
)
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Initialize shared model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

# ============================================================
# COUNCIL AGENTS (New Non-Linear Architecture)
# ============================================================

def format_transcript(transcript: List) -> str:
    """Helper to format transcript with line numbers"""
    return "\n".join([f"[{i}] {s.speaker}: {s.text}" for i, s in enumerate(transcript)])


# --- 1️⃣ STRATEGIST AGENT ---
async def agent_strategist(state: MeetingState) -> Dict[str, Any]:
    """
    Analyzes meeting context, determines type, tone, and sentiment.
    MUST provide timestamp/line evidence for tone/sentiment claims.
    
    Reads: metadata, transcript
    Writes: strategist
    """
    logger.info("="*60)
    logger.info("🎯 STRATEGIST AGENT: Starting analysis...")
    logger.info(f"   Meeting ID: {state.meeting_id}")
    logger.info(f"   Transcript segments: {len(state.transcript)}")
    
    transcript_text = format_transcript(state.transcript)
    
    prompt = f"""
You are a meeting context analyst. Analyze this meeting and determine:

1. **Meeting Type**: Is this "Client-Facing" (external stakeholders) or "Internal" (team only)?
2. **Tone**: What communication style should be used in follow-up? 
   - "Professional" (neutral business)
   - "Urgent" (time-sensitive issues)
   - "Celebratory" (positive outcomes)
   - "Critical" (problems/warnings)
3. **Sentiment**: Overall mood of the meeting?
   - "Positive" (good news, achievements)
   - "Neutral" (routine business)
   - "Critical" (concerns, issues)

**CRITICAL REQUIREMENT**: 
For your tone and sentiment assessment, provide LINE NUMBERS as evidence.
Example: If you say "Urgent", cite lines like [3], [7], [12] that support this.

Metadata:
- Title: {state.metadata.title}
- Date: {state.metadata.date}
- Participants: {', '.join(state.metadata.participants)}

Transcript (with line numbers):
{transcript_text[:50000]}

Return your analysis with evidence.
"""
    
    try:
        logger.info("   Invoking LLM for context analysis...")
        response = await llm.with_structured_output(StrategistOutput).ainvoke([
            SystemMessage(content="You are an expert meeting analyst. Provide evidence for all claims."),
            HumanMessage(content=prompt)
        ])
        
        logger.info("✅ STRATEGIST AGENT: Analysis complete")
        logger.info(f"   Meeting Type: {response.meeting_type}")
        logger.info(f"   Tone: {response.tone}")
        logger.info(f"   Sentiment: {response.sentiment}")
        logger.info(f"   Confidence: {response.confidence}")
        logger.info(f"   Evidence Lines: {len(response.evidence_timestamps)} citations")
        logger.info("="*60)
        return {"strategist": response}
    except Exception as e:
        logger.error(f"❌ STRATEGIST AGENT FAILED: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error("="*60)
        raise


# --- 2️⃣ EXTRACTOR AGENT ---
async def agent_extractor(state: MeetingState) -> Dict[str, Any]:
    """
    Extracts structured data: commitments, metrics, decisions.
    Focus on FACTS only, no interpretation.
    
    Reads: transcript
    Writes: extractor
    """
    logger.info("="*60)
    logger.info("📊 EXTRACTOR AGENT: Starting data extraction...")
    logger.info(f"   Meeting ID: {state.meeting_id}")
    logger.info(f"   Processing {len(state.transcript)} transcript segments")
    
    transcript_text = format_transcript(state.transcript)
    logger.info(f"   Formatted transcript length: {len(transcript_text)} chars")
    
    prompt = f"""
You are a data extractor. Extract ONLY factual, structured information from this transcript:

**Extract**:
1. **Action Items** (commitments):
   - Task description
   - Owner (person name or "TBD")
   - Due date (YYYY-MM-DD or "TBD")
   - Evidence: FULL verbatim quote from transcript
   
   Look for phrases like "I will...", "I'll...", "[Name] will...", "Let's..."

2. **Quantitative Metrics** (numbers mentioned):
   - Budget amounts
   - Headcount/team size
   - Revenue/sales targets
   - Deadlines
   - Performance metrics
   Format as dictionary: {{"budget": 10000, "deadline": "2024-01-15"}}

3. **Explicit Decisions Made**:
   - Choices that were agreed upon
   List as strings

**RULES**:
- DO NOT interpret tone or sentiment (that's the Strategist's job)
- Only extract what is EXPLICITLY stated
- For commitments, include FULL sentence as evidence
- If no metrics/decisions, return empty lists/dicts

Transcript:
{transcript_text[:50000]}

Return structured data.
"""

    try:
        logger.info("   Invoking LLM for data extraction...")
        response = await llm.with_structured_output(ExtractorOutput).ainvoke([
            SystemMessage(content="You are a precise data extraction system. Facts only, no interpretation."),
            HumanMessage(content=prompt)
        ])
        
        logger.info("✅ EXTRACTOR AGENT: Extraction complete")
        logger.info(f"   Commitments found: {len(response.commitments)}")
        for i, c in enumerate(response.commitments, 1):
            logger.info(f"     {i}. {c.owner}: {c.task[:50]}... (Due: {c.due})")
        logger.info(f"   Decisions found: {len(response.decisions)}")
        for i, d in enumerate(response.decisions, 1):
            logger.info(f"     {i}. {d[:60]}...")
        logger.info(f"   Metrics extracted: {len(response.metrics)} items")
        if response.metrics:
            logger.info(f"     Keys: {list(response.metrics.keys())}")
        logger.info("="*60)
        return {"extractor": response}
    except Exception as e:
        logger.error(f"❌ EXTRACTOR AGENT FAILED: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error("="*60)
        raise


# --- 3️⃣ CRITIC AGENT (The Gatekeeper) ---
async def agent_critic(state: MeetingState) -> Dict[str, Any]:
    """
    Cross-validates Strategist and Extractor outputs against transcript.
    Can REJECT either or both if they contradict evidence or each other.
    
    This is the "Double Debate" mechanism.
    
    Reads: strategist, extractor, transcript
    Writes: critic
    """
    logger.info("="*60)
    logger.info("⚖️ CRITIC AGENT: Starting validation...")
    logger.info(f"   Meeting ID: {state.meeting_id}")
    logger.info("   Validating Strategist output:")
    logger.info(f"     • Type: {state.strategist.meeting_type}")
    logger.info(f"     • Tone: {state.strategist.tone}")
    logger.info(f"     • Sentiment: {state.strategist.sentiment}")
    logger.info("   Validating Extractor output:")
    logger.info(f"     • Commitments: {len(state.extractor.commitments)}")
    logger.info(f"     • Decisions: {len(state.extractor.decisions)}")
    logger.info(f"     • Metrics: {len(state.extractor.metrics)}")
    
    transcript_text = format_transcript(state.transcript)
    
    prompt = f"""
You are The Critic - a validation agent that checks for consistency and accuracy.

**STRATEGIST CLAIMS**:
- Meeting Type: {state.strategist.meeting_type}
- Tone: {state.strategist.tone}
- Sentiment: {state.strategist.sentiment}
- Evidence Lines: {state.strategist.evidence_timestamps}

**EXTRACTOR CLAIMS**:
- Commitments: {len(state.extractor.commitments)} items
  {[{"task": c.task, "owner": c.owner, "evidence": c.evidence[:100]} for c in state.extractor.commitments]}
- Metrics: {state.extractor.metrics}
- Decisions: {state.extractor.decisions}

**YOUR VALIDATION TASKS**:

1. **Strategist Validation**:
   - Does the claimed tone match the actual transcript content?
     Example REJECT: Tone="Celebratory" but transcript discusses layoffs
   - Does sentiment match evidence?
     Example REJECT: Sentiment="Positive" but transcript is full of complaints
   - Are the evidence lines actually relevant?

2. **Extractor Validation**:
   - Are commitments supported by verbatim evidence?
   - Are metrics accurate to what was said?
     Example REJECT: Extractor says "Budget: $10k" but transcript says "$100k"
   - Are decisions real or hallucinated?

3. **Cross-Validation**:
   - Do Strategist and Extractor contradict each other?
     Example REJECT BOTH: Strategist says "Internal meeting" but Extractor lists "Client deliverables"

**TRANSCRIPT**:
{transcript_text[:40000]}

**RETURN**:
- strategist_approved: true/false
- extractor_approved: true/false
- strategist_feedback: null or "Reason for rejection"
- extractor_feedback: null or "Reason for rejection"
- overall_status: "approved" or "rejected"

Be strict but fair. If uncertain, REJECT and ask for retry.
"""

    try:
        logger.info("   Invoking LLM for cross-validation...")
        response = await llm.with_structured_output(CriticVerification).ainvoke([
            SystemMessage(content="You are a strict validator. Prefer rejection over accepting questionable data."),
            HumanMessage(content=prompt)
        ])
        
        logger.info("✅ CRITIC AGENT: Validation complete")
        logger.info(f"   Strategist approved: {response.strategist_approved}")
        logger.info(f"   Extractor approved: {response.extractor_approved}")
        logger.info(f"   Overall status: {response.overall_status}")
        
        if not response.strategist_approved:
            logger.warning("⚠️ STRATEGIST REJECTED")
            logger.warning(f"   Reason: {response.strategist_feedback}")
            logger.warning(f"   Current retry count: {state.retry_counts.get('strategist', 0)}")
        
        if not response.extractor_approved:
            logger.warning("⚠️ EXTRACTOR REJECTED")
            logger.warning(f"   Reason: {response.extractor_feedback}")
            logger.warning(f"   Current retry count: {state.retry_counts.get('extractor', 0)}")
        
        if response.strategist_approved and response.extractor_approved:
            logger.info("🎉 Both agents APPROVED! Proceeding to Copywriter.")
        
        logger.info("="*60)
        return {"critic": response}
    except Exception as e:
        logger.error(f"❌ CRITIC AGENT FAILED: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error("="*60)
        raise


# --- 4️⃣ COPYWRITER AGENT ---
async def agent_copywriter(state: MeetingState) -> Dict[str, Any]:
    """
    Only runs when Critic approves both Strategist and Extractor.
    Uses verified data to draft the follow-up email.
    
    Reads: strategist, extractor
    Writes: email
    """
    logger.info("="*60)
    logger.info("✍️ COPYWRITER AGENT: Starting email draft...")
    logger.info(f"   Meeting ID: {state.meeting_id}")
    
    # Ensure we only run if approved
    if not (state.critic.strategist_approved and state.critic.extractor_approved):
        logger.error("❌ COPYWRITER AGENT ERROR: Called before Critic approval!")
        logger.error(f"   Strategist approved: {state.critic.strategist_approved}")
        logger.error(f"   Extractor approved: {state.critic.extractor_approved}")
        logger.error("="*60)
        return {"email": EmailDraft(subject="ERROR", body="Copywriter ran prematurely")}
    
    logger.info("   Using verified inputs:")
    logger.info(f"     • Tone: {state.strategist.tone}")
    logger.info(f"     • Action items: {len(state.extractor.commitments)}")
    logger.info(f"     • Decisions: {len(state.extractor.decisions)}")
    
    prompt = f"""
You are drafting a professional follow-up email based on VERIFIED meeting analysis.

**CONTEXT & TONE** (from Strategist):
- Meeting Type: {state.strategist.meeting_type}
- Required Tone: {state.strategist.tone}
- Sentiment: {state.strategist.sentiment}

**CONTENT** (from Extractor - VERIFIED):
- Decisions Made: {state.extractor.decisions}
- Metrics Discussed: {state.extractor.metrics}
- Action Items: {len(state.extractor.commitments)} commitments

**ACTION ITEMS DETAIL**:
{[{"owner": c.owner, "task": c.task, "due": c.due} for c in state.extractor.commitments]}

**INSTRUCTIONS**:
1. **Subject Line**: Specific and clear (e.g., "Follow-up: Q4 Planning - Action Items")
2. **Email Body**:
   - Opening: Brief context (1-2 sentences) matching the tone
   - Key Decisions: Bullet list (if decisions exist)
   - Metrics Summary: If numbers were discussed
   - Action Items: Formatted as "* **[Owner]**: [Task] (Due: [Date])"
   - Closing: Professional sign-off

3. **Tone Matching**:
   - If tone is "Urgent": Use concise, action-oriented language
   - If tone is "Celebratory": Acknowledge successes
   - If tone is "Critical": Be clear about issues without being alarmist
   - If tone is "Professional": Keep it neutral and business-like

4. **DO NOT**:
   - Add tasks not in the extractor data
   - Change owners or due dates
   - Hallucinate decisions

Write the complete email.
"""

    try:
        logger.info("   Invoking LLM for email composition...")
        response = await llm.with_structured_output(EmailDraft).ainvoke([
            SystemMessage(content="You are a professional executive assistant drafting follow-up emails."),
            HumanMessage(content=prompt)
        ])
        
        logger.info("✅ COPYWRITER AGENT: Email draft complete")
        logger.info(f"   Subject: {response.subject}")
        logger.info(f"   Body length: {len(response.body)} chars")
        logger.info(f"   First 100 chars: {response.body[:100]}...")
        logger.info("="*60)
        return {"email": response}
    except Exception as e:
        logger.error(f"❌ COPYWRITER AGENT FAILED: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error("="*60)
        raise


# --- 5️⃣ REFINER AGENT (Integrated Human Feedback) ---
async def agent_refiner(state: MeetingState) -> Dict[str, Any]:
    """
    Applies human feedback to the current draft.
    Updates email based on Slack instructions.
    
    Reads: email, human_feedback, extractor (for facts)
    Writes: email (updated)
    """
    logger.info("="*60)
    logger.info("🔄 REFINER AGENT: Processing human feedback...")
    logger.info(f"   Meeting ID: {state.meeting_id}")
    logger.info(f"   Feedback status: {state.human_feedback.status}")
    
    if not state.human_feedback.instructions:
        logger.info("ℹ️ No human feedback instructions found")
        logger.info("   Skipping refinement, returning unchanged state")
        logger.info("="*60)
        return {}
    
    logger.info(f"   Human feedback: {state.human_feedback.instructions[:100]}...")
    logger.info(f"   Slack user: {state.human_feedback.slack_user_id}")
    logger.info(f"   Current email subject: {state.email.subject}")
    
    prompt = f"""
You are refining a draft email based on human feedback.

**CURRENT EMAIL**:
Subject: {state.email.subject}
Body:
{state.email.body}

**HUMAN FEEDBACK**:
{state.human_feedback.instructions}

**VERIFIED FACTS** (DO NOT change these unless explicitly requested):
- Action Items: {[{"owner": c.owner, "task": c.task, "due": c.due} for c in state.extractor.commitments]}
- Decisions: {state.extractor.decisions}

**INSTRUCTIONS**:
1. Apply the requested changes
2. Preserve factual accuracy (don't invent commitments)
3. If feedback requests adding a task, add it to the action items section
4. If feedback requests tone change, rewrite accordingly
5. Keep professional formatting

Return the UPDATED email (full subject + body).
"""

    try:
        logger.info("   Invoking LLM for refinement...")
        response = await llm.with_structured_output(EmailDraft).ainvoke([
            SystemMessage(content="You are an intelligent editor applying human feedback precisely."),
            HumanMessage(content=prompt)
        ])
        
        logger.info("✅ REFINER AGENT: Email refinement complete")
        logger.info(f"   Updated subject: {response.subject}")
        logger.info(f"   Updated body length: {len(response.body)} chars")
        logger.info(f"   Changes applied based on: {state.human_feedback.instructions[:60]}...")
        logger.info("="*60)
        return {"email": response}
    except Exception as e:
        logger.error(f"❌ REFINER AGENT FAILED: {str(e)}")
        logger.error(f"   Error type: {type(e).__name__}")
        logger.error(f"   Original feedback: {state.human_feedback.instructions}")
        logger.error("="*60)
        raise
