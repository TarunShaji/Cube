from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.state import MeetingState, IntentContext, TopicSegment, Commitment, EmailDraft, ValidationResult
from pydantic import BaseModel
# Initialize shared model (Gemini 1.5 Pro recommended for logic)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

# --- 1️⃣ Intent & Context Classification Agent ---
def agent_intent_classification(state: MeetingState) -> Dict[str, Any]:
    """
    Reads: metadata, transcript
    Writes: intent_context
    """
    transcript_text = "\n".join([f"{s.speaker}: {s.text}" for s in state.transcript])
    
    prompt = f"""
    Analyze this meeting transcript and extract the high-level context.
    
    Metadata:
    Title: {state.metadata.title}
    Date: {state.metadata.date}
    Participants: {', '.join(state.metadata.participants)}
    
    Transcript:
    {transcript_text[:50000]} # Truncate if huge, though Claude has 200k context.
    
    Return JSON matching this schema:
    {{
        "meeting_type": "Daily Standup | Sales Call | Planning | 1:1 | Review | Other",
        "primary_goal": "The main objective achieved or discussed",
        "confidence_notes": "Any notes on transcript quality or ambiguity"
    }}
    """
    
    response = llm.with_structured_output(IntentContext).invoke([
        SystemMessage(content="You are an expert meeting analyst. Extract intent and context accurately."),
        HumanMessage(content=prompt)
    ])
    
    return {"intent_context": response}


# --- 2️⃣ Topic & Decision Segmentation Agent ---
def agent_topic_segmentation(state: MeetingState) -> Dict[str, Any]:
    """
    Reads: transcript, intent_context
    Writes: topics
    """
    # We might need to chunk this for very long meetings, but for now assuming it fits.
    transcript_text = "\n".join([f"Line {i}: {s.speaker}: {s.text}" for i, s in enumerate(state.transcript)])
    
    prompt = f"""
    Segment this meeting into distinct topics.
    Context: {state.intent_context.model_dump_json()}
    
    Transcript (with line numbers):
    {transcript_text}
    
    Return a list of topics. For each topic:
    - summary: Brief description
    - start_index: Line number where it starts
    - end_index: Line number where it ends
    - decisions: List of explicit decisions made (if any)
    """
    
    # Define a wrapper model for list output
    from pydantic import BaseModel, Field
    from typing import List
    class TopicList(BaseModel):
        topics: List[TopicSegment]

    response = llm.with_structured_output(TopicList).invoke([
        SystemMessage(content="You are a strict meeting segmenter. Do not invent topics. Use line numbers corresponding to the provided text."),
        HumanMessage(content=prompt)
    ])
    
    return {"topics": response.topics}


# --- 3️⃣ Commitment Extraction Agent ---
def agent_commitment_extraction(state: MeetingState) -> Dict[str, Any]:
    """
    Reads: transcript, topics
    Writes: commitments
    """
    transcript_text = "\n".join([f"{s.speaker}: {s.text}" for s in state.transcript])
    
    prompt = f"""
    Extract concrete commitments (tasks) from the transcript.
    You are the SINGLE SOURCE OF TRUTH for tasks.
    
    Rules:
    1. EXPLICIT commitments only. Look for:
       - "I will..."
       - "I'll..."
       - "Let's..."
       - "We need to..." (if assigned to someone)
    2. Owner: Person name or "Us"/"Them". "TBD" if unclear.
    3. Due: YYYY-MM-DD or specific timeframe if stated. "TBD" otherwise. 
    4. EVIDENCE (CRITICAL):
       - Quote the FULL SENTENCE (or meaningful clause) from the transcript.
       - It must be a verbatim substring.
       - Do NOT abbreviate (e.g., instead of "Send the spec", use "I will send the spec by Friday EOD").
    Examples:
    Input: "John: I will fix the bug by tomorrow."
    Output: {{"task": "Fix the bug", "owner": "John", "due": "Tomorrow", "evidence": "I will fix the bug by tomorrow."}}
    
    Input: "Alice: The report is done."
    Output: (No commitment, statement of fact)
    
    Transcript:
    {transcript_text}
    
    Return all valid commitments found.
    """
    
    class CommitmentList(BaseModel):
        commitments: List[Commitment]

    response = llm.with_structured_output(CommitmentList).invoke([
        SystemMessage(content="You are a trust-critical auditor. Prefer omission over hallucination. No guessing."),
        HumanMessage(content=prompt)
    ])
    
    return {"commitments": response.commitments}


# --- 4️⃣ Verification & Consistency Agent ---
def agent_verification(state: MeetingState) -> Dict[str, Any]:
    """
    Reads: commitments, transcript
    Writes: commitments (FILTERED)
    
    This agent assumes the role of a skeptic. It filters out weak commitments.
    """
    if not state.commitments:
        return {"commitments": []}

    transcript_text = "\n".join([f"{s.speaker}: {s.text}" for s in state.transcript])
    
    filtered_commitments = []
    
    for c in state.commitments:
        # We verify each commitment against the transcript
        verify_prompt = f"""
        Verify this commitment against the transcript.
        
        Commitment: {c.model_dump_json()}
        
        Transcript Snippet (Evidence context):
        ... {c.evidence} ...
        
        Full Transcript provided in context.
        
        Task:
        1. Does the evidence support this task?
        2. Is it a real commitment, or just a suggestion/idea?
        3. Is the owner correct?
        
        Return TRUE only if valid. If ambiguous, return FALSE.
        """
        
        # Simplified boolean check for this stage
        # In a real heavy system, we might use structured output again.
        # For efficiency here, we'll ask for a filtered list in one go.
        pass

    prompt = f"""
    Review these proposed commitments. Remove any that are weak, ambiguous, or hallucinated.
    
    Proposed Commitments:
    { [c.model_dump()] for c in state.commitments }
    
    Transcript:
    {transcript_text[:30000]}
    
    Return the FINAL list of valid commitments. You can remove items, but DO NOT add new ones.
    """
    
    class CommitmentList(BaseModel):
        commitments: List[Commitment]
        
    response = llm.with_structured_output(CommitmentList).invoke([
        SystemMessage(content="You are a data cleaner. Remove hallucinated or weak tasks. Be aggressive."),
        HumanMessage(content=prompt)
    ])
    
    return {"commitments": response.commitments}


# --- 5️⃣ Email Composition Agent ---
def agent_email_composition(state: MeetingState) -> Dict[str, Any]:
    """
    Reads: commitments, intent_context
    Writes: email
    """
    # Aggregate decisions from topics
    all_decisions = []
    for t in state.topics:
        if t.decisions:
            all_decisions.extend(t.decisions)

    prompt = f"""
    Draft a professional, executive-ready follow-up email based on the meeting data.
    
    CONTEXT:
    - Type: {state.intent_context.meeting_type}
    - Primary Goal: {state.intent_context.primary_goal}
    
    DECISIONS REFERENCED (from topics):
    {all_decisions}
    
    RAW COMMITMENTS (Evidence-backed):
    { [c.model_dump() for c in state.commitments] }
    
    INSTRUCTIONS:
    1. **Structure**: 
       - Subject Line: Clear and specific to the meeting.
       - **Body Content** (do NOT repeat the subject line here):
         - **Executive Summary**: 2-3 sentences on context and outcomes.
         - **Key Decisions**: Bullet points (ONLY if decisions exist).
         - **Action Items**: Bullet points derived from 'RAW COMMITMENTS'.
    
    2. **Action Item Formatting**:
       - Rewrite the 'task' description to be concise, direct, and professional (imperative mood).
       - Format: "* **[Owner]**: [Refined Task Description] (Due: [Date])"
       - Example: "* **Alice**: Finalize the API Specification (Due: Friday)"
       - Do NOT change the meaning or owner.
       - Do NOT invent new items.
       - If no commitments exist, write: "No specific action items were identified."
    
    3. **Tone**: Neutral, efficient, professional.
    """
    
    response = llm.with_structured_output(EmailDraft).invoke([
        SystemMessage(content="You are a professional executive assistant."),
        HumanMessage(content=prompt)
    ])
    
    return {"email": response}


# --- 6️⃣ Final Guardrail / Quality Gate Agent ---
def agent_guardrail(state: MeetingState) -> Dict[str, Any]:
    """
    Reads: entire state
    Writes: validation
    """
    errors = []
    
    # Rule 1: Commitments must have evidence
    for c in state.commitments:
        if not c.evidence or len(c.evidence.strip()) < 5:
            errors.append(f"Commitment '{c.task}' missing evidence.")
    
    # Rule 2: Email must exist
    if not state.email.body:
        errors.append("Email body is empty.")
        
    is_valid = len(errors) == 0
    
    return {
        "validation": ValidationResult(
            is_valid=is_valid,
            errors=errors
        )
    }
