from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel
from app.config import settings
from app.state import MeetingState, Commitment, EmailDraft
import logging

logger = logging.getLogger(__name__)

# Re-use the shared model configuration
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0
)

# Output structure for the refinement agent
class RefinementOutput(BaseModel):
    commitments: List[Commitment]
    email: EmailDraft
    explanation: str # Why/What was changed

async def run_refinement(state: MeetingState, instruction: str) -> MeetingState:
    """
    Apply user instructions to the existing meeting state using an LLM.
    Returns the updated MeetingState.
    """
    logger.info(f"✨ Running Refinement Agent for {state.meeting_id} with instruction: '{instruction}'")

    prompt = f"""
    You are an intelligent editor for meeting intelligence.
    
    GOAL:
    Update the Draft Email and/or Action Items based strictly on the USER INSTRUCTION.
    
    USER INSTRUCTION:
    "{instruction}"
    
    CURRENT STATE:
    
    [Action Items]
    { [c.model_dump() for c in state.commitments] }
    
    [Draft Email]
    Subject: {state.email.subject}
    Body:
    {state.email.body}
    
    RULES:
    1. Apply the user's requested changes.
    2. Do NOT hallucinate new information unrelated to the request.
    3. If the user asks to "rewrite tone", change the email body accordingly.
    4. If the user asks to "add a task", add it to the Commitments list.
    5. If the request is about formatting, update the relevant text.
    6. Preserve existing valid information unless asked to change it.
    
    Return the FULL updated list of commitments and the FULL updated email.
    Also provide a brief explanation of what you changed.
    """
    
    try:
        response = await llm.with_structured_output(RefinementOutput).ainvoke([
            SystemMessage(content="You are a precise AI editor. Follow instructions exactly."),
            HumanMessage(content=prompt)
        ])
        
        # Apply updates to state
        # Create a copy of state to return (or modify in place if safe, Pydantic copy is safer)
        new_state = state.model_copy(deep=True)
        
        new_state.commitments = response.commitments
        new_state.email = response.email
        
        logger.info(f"✅ Refinement Complete: {response.explanation}")
        return new_state

    except Exception as e:
        logger.error(f"❌ Refinement Agent Failed: {e}")
        # In case of failure, return original state safe
        return state
