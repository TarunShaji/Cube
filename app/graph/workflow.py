from langgraph.graph import StateGraph, END
from app.state import MeetingState
from app.graph.nodes import (
    agent_intent_classification,
    agent_topic_segmentation,
    agent_commitment_extraction,
    agent_verification,
    agent_email_composition,
    agent_guardrail
)
import logging

logger = logging.getLogger(__name__)

# Define the graph
workflow = StateGraph(MeetingState)

# Add Nodes
workflow.add_node("intent_classification", agent_intent_classification)
workflow.add_node("topic_segmentation", agent_topic_segmentation)
workflow.add_node("commitment_extraction", agent_commitment_extraction)
workflow.add_node("verification", agent_verification)
workflow.add_node("email_composition", agent_email_composition)
workflow.add_node("guardrail", agent_guardrail)

# Add Edges (Linear Flow)
workflow.set_entry_point("intent_classification")
workflow.add_edge("intent_classification", "topic_segmentation")
workflow.add_edge("topic_segmentation", "commitment_extraction")
workflow.add_edge("commitment_extraction", "verification")
workflow.add_edge("verification", "email_composition")
workflow.add_edge("email_composition", "guardrail")

# Logic for Post-Guardrail
def route_after_guardrail(state: MeetingState):
    if state.validation.is_valid:
        return END
    else:
        # In a real system, we might loop back or flag for human review.
        # Spec says: "If retry fails -> FAILED". 
        # For this v1, we just END but the state reflects invalidity.
        return END

workflow.add_edge("guardrail", END)

# Compile
app_graph = workflow.compile()

async def run_pipeline(initial_state: MeetingState) -> MeetingState:
    """
    Executes the full intelligence pipeline on the given meeting state.
    """
    logger.info(f"🚀 Starting Intelligence Pipeline for {initial_state.meeting_id}")
    
    # LangGraph invoke returns the final state dict
    final_state_dict = await app_graph.ainvoke(initial_state)
    
    # Assuming invoke returns the state dict, we cast back to Pydantic if needed
    # (LangGraph's state updates are dict merges usually, but StateGraph typed with Pydantic might behave differently depending on version)
    # Safest is to rely on what was returned.
    
    # If final_state_dict is a dict, wrap it back.
    if isinstance(final_state_dict, dict):
        return MeetingState(**final_state_dict)
    return final_state_dict
