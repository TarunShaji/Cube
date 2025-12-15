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
    model="gemini-2.5-flash",
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
You are a PRECISE data extractor. Extract structured action items from this transcript.

**TEAM ROLES** (use for intelligent assignment):
- **Sahana K** = Designer (Figma, images, visual elements, UI/UX)
- **Nithin Reddy** = Developer (code, backend, functionality, uploads, deployment)
- **Karthik B** = Project Manager (coordination, client communication)

=============================================================
CRITICAL EXTRACTION RULES - FOLLOW EXACTLY
=============================================================

**1. KILL THE PRONOUNS (Context Resolution):**
❌ NEVER output vague instructions like "Delete this," "Fix that," or "Remove something"
✅ ALWAYS look at the 2-3 sentences BEFORE the action in the transcript to find the specific noun

Examples:
❌ BAD: "Delete something to avoid confusion"
✅ GOOD: "Delete the duplicate arrow icon on the homepage"

❌ BAD: "Change this to match"
✅ GOOD: "Change the footer background color to match the header (#2B4A6F)"

❌ BAD: "Hide them from the back end"
✅ GOOD: "Hide the 'Benefits' and 'Case Study' pages from the navigation menu"

**2. QUALIFY COMMUNICATION TASKS:**
❌ NEVER just say "Write to [Name]" or "Email [Name]"
✅ ALWAYS specify WHAT the email/message is about

Examples:
❌ BAD: "Write to Alex"
✅ GOOD: "Email Alex to request the shipping address for the product bottles"

❌ BAD: "Contact client"
✅ GOOD: "Contact client to get GSC access credentials for seo@cubehq.ai"

**3. INTELLIGENT ROLE ASSIGNMENT:**
If someone says "[Name] do X" but the task doesn't match their role, assign correctly:

- Visual/Design/Figma/Images → Sahana K (Designer)
- Code/Backend/Functionality/Shopify → Nithin Reddy (Developer)  
- Coordination/Follow-up/PM tasks → Karthik B (PM)

Example: If transcript says "Nithin change the image" but it's a design task:
→ Assign to Sahana K with task: "Update product image on homepage"
→ OR assign to Nithin if it's just uploading: "Upload updated product image to Shopify"

**4. DECISIONS vs ACTION ITEMS - NO OVERLAP:**
- **Decisions** = High-level strategic choices (e.g., "Launch Phase 1 before Christmas")
- **Action Items** = Granular executable tasks (e.g., "Hide buttons on page X")
- DO NOT repeat the same item in both lists!

=============================================================
WHAT TO EXTRACT
=============================================================

**1. Action Items (commitments):**
- Task: SPECIFIC description (use context resolution!)
- Owner: Assign based on task type (Designer/Developer/PM/Client/TBD)
- Due: YYYY-MM-DD or relative (e.g., "Friday", "Next week", "TBD")
- Evidence: The FULL sentence from transcript

**2. Quantitative Metrics:**
- Budget amounts, deadlines, targets, counts
- Format as dictionary: {{"budget": 10000, "deadline": "2024-01-15"}}

**3. Key Decisions Made:**
- HIGH-LEVEL choices only (strategy, priorities, direction)
- NOT granular tasks

=============================================================
TRANSCRIPT
=============================================================
{transcript_text[:50000]}

Extract with MAXIMUM specificity. No vague pronouns. No ambiguous tasks.
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
    Generates TWO outputs:
    1. Client-facing email (professional, no internal names)
    2. Internal action plan (detailed, grouped by owner)
    
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
    
    # Group commitments by owner for the internal section
    commitments_by_owner = {}
    for c in state.extractor.commitments:
        owner = c.owner if c.owner and c.owner != "TBD" else "Unassigned"
        if owner not in commitments_by_owner:
            commitments_by_owner[owner] = []
        commitments_by_owner[owner].append({"task": c.task, "due": c.due})
    
    prompt = f"""
You are drafting a professional meeting follow-up with TWO SEPARATE OUTPUTS.

**CONTEXT** (from Strategist):
- Meeting Type: {state.strategist.meeting_type}
- Required Tone: {state.strategist.tone}
- Sentiment: {state.strategist.sentiment}
- Meeting Title: {state.metadata.title}
- Date: {state.metadata.date}
- Participants: {', '.join(state.metadata.participants)}

**RAW DATA** (from Extractor):
- Decisions Made: {state.extractor.decisions}
- Metrics Discussed: {state.extractor.metrics}
- All Commitments by Owner: {commitments_by_owner}

=============================================================
SAMPLE CLIENT EMAILS (MATCH THIS STYLE)
=============================================================

**Example 1:**
Hi Team,
Following up from today's call - here are the latest updates:
Blog Page - Blog page is now live: https://example.com/blog
Product Page - We'll rework the page as per the PDF shared and send the updated version by Tuesday
Please review and share feedback or approvals where applicable.
Thanks!

**Example 2:**
Hi Wendy, Tina and Gadi,
Thank you for your time on today's call. Sharing the latest updates for your review and approval:
Title & Meta: View
Blog Page Preview Links:
Collection: View
Individual: View
Please let us know which variation you'd like to proceed with so we can begin development.
Thanks,
Jatin

**Example 3:**
Hi T and John,
Hope you're both doing well. Sharing the following for your review:
SEO report - View
Call recording - View
Blog drafts for your review and approval:
- Korean Food Catering NYC: Full-Service Event Catering
- Authentic Korean Restaurant in Manhattan
Thank you for granting access to the Ads account.
Best,

**Example 4:**
Hi Nancy, Peggy, and Jeff,
Thank you for your time on the call today. As discussed, I'm sharing the implementation plan we went over - Click here.
We'll begin working on the schema markup, title and header descriptions, and the blog page.
Please let us know if you have any questions.
Looking forward to our call next week!
Best,
Sahana

=============================================================
OUTPUT 1: CLIENT-FACING EMAIL
=============================================================

**Audience**: The external client/stakeholder
**Style**: SHORT, CONCISE, BULLETED - like the examples above

**FORMAT RULES**:
1. Short greeting with client name(s) if known
2. Brief thank you for the call (1 line max)
3. Bullet list of updates/items with clear labels
4. Action items the CLIENT needs to do
5. Short closing (Thanks! / Best, / Looking forward)

**CRITICAL CONSTRAINTS - DO NOT**:
- ❌ Mention internal employee names (Nithin, Sahana, Karthik, etc.)
- ❌ List internal technical tasks (backend changes, hide buttons, etc.)
- ❌ Use "TBD" in the client email
- ❌ Write long paragraphs - use bullets!
- ❌ Be overly formal - keep it friendly and direct

=============================================================
OUTPUT 2: INTERNAL ACTION PLAN
=============================================================

**Audience**: Internal team (PMs, developers, designers)
**Tone**: Tactical, direct, detailed

**WHAT TO INCLUDE**:
1. Key Decisions section (bullet list)
2. Tasks grouped by Owner name
3. Technical details and specific instructions
4. Client tasks to track (what we're waiting on)
5. Unassigned/TBD items that need owners

=============================================================
REQUIRED OUTPUT FORMAT (MUST INCLUDE BOTH SECTIONS!)
=============================================================

**Subject line**: Put in the 'subject' field

**Body**: Must contain BOTH sections separated by the divider:

Hi [Client Name(s)],

Thank you for your time on today's call. Here are the latest updates:

[BULLET LIST OF UPDATES/ITEMS]

[CLIENT ACTION ITEMS IF ANY]

[SHORT CLOSING]

---
=== INTERNAL USE ONLY ===
---

### Key Decisions
* [Decision 1]
* [Decision 2]

### Tasks by Owner

**Nithin Reddy**
* [Task] (Due: [Date])

**Sahana K**
* [Task] (Due: [Date])

**Karthik B**
* [Task] (Due: [Date])

**Client Action Items (to track)**
* [What we're waiting on from client]

**Unassigned / Needs Owner**
* [Task without owner]

IMPORTANT: You MUST include BOTH the client email AND the internal action plan!
"""

    try:
        logger.info("   Invoking LLM for email composition...")
        response = await llm.with_structured_output(EmailDraft).ainvoke([
            SystemMessage(content="You are a professional executive assistant. Generate both a client-facing email AND an internal action plan. Keep them clearly separated."),
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
