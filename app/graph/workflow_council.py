from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal
from datetime import datetime, timezone
from app.state import MeetingState
from app.graph.nodes_council import (
    agent_strategist,
    agent_extractor,
    agent_critic,
    agent_copywriter,
    agent_refiner
)
import logging

logger = logging.getLogger(__name__)

# ============================================================
# COUNCIL WORKFLOW (Non-Linear Architecture)
# ============================================================

MAX_RETRIES = 3  # Maximum debate loop iterations per agent

# Define the graph
workflow = StateGraph(MeetingState)

# Add Nodes
workflow.add_node("strategist", agent_strategist)
workflow.add_node("extractor", agent_extractor)
workflow.add_node("critic", agent_critic)
workflow.add_node("copywriter", agent_copywriter)
workflow.add_node("refiner", agent_refiner)
workflow.add_node("human_review", lambda state: state)  # Passive wait node


# ============================================================
# ENTRY POINTS (Parallel Dispatch)
# ============================================================

workflow.set_entry_point("strategist")
workflow.set_entry_point("extractor")


# ============================================================
# EDGES TO CRITIC
# ============================================================

# Both Strategist and Extractor feed into Critic
workflow.add_edge("strategist", "critic")
workflow.add_edge("extractor", "critic")


# ============================================================
# CONDITIONAL ROUTING FROM CRITIC (The Debate Loop)
# ============================================================

def route_after_critic(state: MeetingState) -> Literal["strategist", "extractor", "copywriter", "escalate"]:
    """
    The Double Debate Logic.
    
    Routes based on Critic's approval:
    - If Strategist rejected → loop back to Strategist
    - If Extractor rejected → loop back to Extractor
    - If both approved → proceed to Copywriter
    - If MAX_RETRIES exceeded → escalate to human
    """
    logger.info("🔀 ROUTING: Determining next step after Critic...")
    
    strategist_retries = state.retry_counts.get("strategist", 0)
    extractor_retries = state.retry_counts.get("extractor", 0)
    
    logger.info(f"   Retry counts: Strategist={strategist_retries}, Extractor={extractor_retries}")
    logger.info(f"   Strategist approved: {state.critic.strategist_approved}")
    logger.info(f"   Extractor approved: {state.critic.extractor_approved}")
    
    # Check for retry exhaustion
    if strategist_retries >= MAX_RETRIES:
        logger.error(f"🚨 ROUTING: Strategist exceeded MAX_RETRIES ({MAX_RETRIES}). Escalating to human.")
        logger.error(f"   Last feedback: {state.critic.strategist_feedback}")
        return "escalate"
    
    if extractor_retries >= MAX_RETRIES:
        logger.error(f"🚨 ROUTING: Extractor exceeded MAX_RETRIES ({MAX_RETRIES}). Escalating to human.")
        logger.error(f"   Last feedback: {state.critic.extractor_feedback}")
        return "escalate"
    
    # Check Critic decisions
    strategist_ok = state.critic.strategist_approved
    extractor_ok = state.critic.extractor_approved
    
    if not strategist_ok and not extractor_ok:
        # Both rejected - prioritize Strategist (context must be right first)
        logger.warning("⚠️ ROUTING: Critic rejected BOTH agents")
        logger.warning("   Priority: Strategist (context must be correct first)")
        logger.warning(f"   Strategist feedback: {state.critic.strategist_feedback}")
        logger.warning(f"   Extractor feedback: {state.critic.extractor_feedback}")
        return "strategist"
    
    if not strategist_ok:
        logger.warning("⚠️ ROUTING: Strategist rejected, looping back")
        logger.warning(f"   Feedback: {state.critic.strategist_feedback}")
        logger.warning(f"   This is retry #{strategist_retries + 1} of {MAX_RETRIES}")
        return "strategist"
    
    if not extractor_ok:
        logger.warning("⚠️ ROUTING: Extractor rejected, looping back")
        logger.warning(f"   Feedback: {state.critic.extractor_feedback}")
        logger.warning(f"   This is retry #{extractor_retries + 1} of {MAX_RETRIES}")
        return "extractor"
    
    # Both approved
    logger.info("✅ ROUTING: Both agents approved by Critic")
    logger.info("   Next step: Copywriter (drafting email)")
    logger.info(f"   Total retries: Strategist={strategist_retries}, Extractor={extractor_retries}")
    return "copywriter"


workflow.add_conditional_edges(
    "critic",
    route_after_critic,
    {
        "strategist": "strategist",  # Loop back for retry
        "extractor": "extractor",    # Loop back for retry
        "copywriter": "copywriter",  # Proceed to drafting
        "escalate": END              # Human intervention needed
    }
)


# ============================================================
# HUMAN-IN-THE-LOOP CHECKPOINT
# ============================================================

# Copywriter → Human Review (INTERRUPT POINT)
workflow.add_edge("copywriter", "human_review")


def route_after_human(state: MeetingState) -> str:
    """
    Routes after human review checkpoint.
    - If user provided feedback instructions → go to Refiner
    - If user approves (status = "approved") → finalize and end
    - Otherwise → stay paused (pending)
    """
    logger.info("🔀 ROUTING: Determining next step after Human Review...")
    
    feedback_status = state.human_feedback.status
    has_instructions = state.human_feedback.instructions and len(state.human_feedback.instructions.strip()) > 0
    
    logger.info(f"   Human feedback status: {feedback_status}")
    logger.info(f"   Has instructions: {has_instructions}")
    
    # Check if user provided feedback (status can be "pending" or "active_review")
    # Both indicate the meeting is awaiting/receiving human input
    if feedback_status in ("pending", "active_review") and has_instructions:
        logger.info("🔄 ROUTING: User provided feedback")
        logger.info(f"   Instructions: {state.human_feedback.instructions[:100] if state.human_feedback.instructions else 'None'}...")
        logger.info("   Next step: Refiner (apply feedback)")
        return "refiner"
    
    if feedback_status == "approved":
        logger.info("✅ ROUTING: Human approved the draft")
        logger.info("   Next step: Finalize and END")
        return "finalize"
    
    # Default: still pending (waiting for user input)
    logger.info("⏸️ ROUTING: Still waiting for human feedback")
    logger.info("   Next step: Stay at human_review (paused)")
    return END


workflow.add_conditional_edges(
    "human_review",
    route_after_human,
    {
        "refiner": "refiner",
        "finalize": END
    }
)


# ============================================================
# REFINER LOOP
# ============================================================

# Refiner → back to Human Review (NOT Copywriter - to preserve changes)
# User feedback is applied directly to the email, no need to regenerate
workflow.add_edge("refiner", "human_review")


# ============================================================
# COMPILE WITH CHECKPOINTING
# ============================================================

# Use persistent MongoDB checkpointer for cross-request resume
# This allows the pipeline to survive between web requests (e.g. Slack events)
from app.graph.checkpoint_saver import MongoDBCheckpointSaver
checkpointer = MongoDBCheckpointSaver()

app_graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_review"]  # Graph will pause here for user input
)


# ============================================================
# EXECUTION FUNCTION
# ============================================================

async def run_council_pipeline(initial_state: MeetingState, thread_id: str = None) -> MeetingState:
    """
    Executes the Council intelligence pipeline.
    
    Args:
        initial_state: Initial meeting state with transcript
        thread_id: Unique thread ID for checkpointing (defaults to meeting_id)
    
    Returns:
        Final enriched state (or partial state if interrupted)
    """
    if not thread_id:
        thread_id = initial_state.meeting_id
    
    logger.info("="*80)
    logger.info("🚀 COUNCIL PIPELINE: Starting execution")
    logger.info(f"   Thread ID: {thread_id}")
    logger.info(f"   Meeting: {initial_state.metadata.title}")
    logger.info(f"   Transcript segments: {len(initial_state.transcript)}")
    logger.info("="*80)
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Stream through the graph
    final_state = initial_state  # Start with initial state
    async for event in app_graph.astream(initial_state, config):
        # event is a dict like {"strategist": {...}, "critic": {...}}
        if event:
            event_nodes = list(event.keys())
            logger.info(f"📊 PIPELINE EVENT: {', '.join(event_nodes)}")
            
            # Update final_state with each event's state updates
            for node_name, node_output in event.items():
                if node_name != "__interrupt__":
                    # Merge the node output into final state
                    if isinstance(node_output, dict):
                        for key, value in node_output.items():
                            if hasattr(final_state, key):
                                setattr(final_state, key, value)
            
            # Log checkpoint status
            if "__interrupt__" in event_nodes:
                logger.info("⏸️ CHECKPOINT: Pipeline paused at human_review")
                logger.info(f"   State saved for thread: {thread_id}")
    
    logger.info("="*80)
    if final_state.human_feedback.status == "pending":
        logger.info("⏸️ COUNCIL PIPELINE: PAUSED at human review")
        logger.info("   Waiting for user feedback to resume")
    else:
        logger.info("✅ COUNCIL PIPELINE: COMPLETED")
    logger.info("="*80)
    return final_state


async def resume_council_pipeline(thread_id: str, user_feedback: str, slack_user_id: str = None):
    """
    Resume a paused pipeline from the human_review checkpoint.
    
    Args:
        thread_id: The meeting ID (used as thread_id in checkpointer)
        user_feedback: The feedback text from Slack user
        slack_user_id: Slack user ID who provided feedback
    """
    try:
        logger.info("="*80)
        logger.info("🔄 COUNCIL PIPELINE: RESUMING from checkpoint")
        logger.info(f"   Thread ID: {thread_id}")
        logger.info(f"   User feedback: {user_feedback[:100]}...")
        logger.info("="*80)
        
        # Load the current state from MongoDB
        from app.services.storage import db
        current_state = await db.get_meeting(thread_id)
        
        if not current_state:
            logger.error(f"❌ No meeting found for thread_id: {thread_id}")
            return None # Or raise an exception
        
        logger.info(f"📋 Loaded meeting state from MongoDB")
        logger.info(f"💬 User feedback: {user_feedback[:100]}...")
        
        # Define config for checkpointer operations
        config = {"configurable": {"thread_id": thread_id}}
        
        # Update the human_feedback with user's instructions
        # CRITICAL: Keep status as "pending" to allow multiple feedback rounds
        # Status will only change to "approved" when user clicks approval button
        current_state.human_feedback.instructions = user_feedback
        current_state.human_feedback.timestamp = datetime.now(timezone.utc).isoformat()
        current_state.human_feedback.slack_user_id = slack_user_id
        
        logger.info(f"   Status: pending (accepting feedback)")
        logger.info(f"   Instructions: {user_feedback[:100]}...")
        
        # CRITICAL: Use aupdate_state() (async version) for async checkpointer
        # This preserves the interrupt point at human_review
        await app_graph.aupdate_state(
            config,
            {"human_feedback": current_state.human_feedback.model_dump()}
        )
        
        logger.info(f"✅ Checkpoint updated, now resuming from human_review...")
        
        # Resume from checkpoint with None as input (means "continue from interrupt")
        # This will trigger route_after_human() which routes to refiner
        # Resume from checkpoint with None as input (means "continue from interrupt")
        # This will trigger route_after_human() which routes to refiner
        final_state = current_state
        logger.info(f"🚀 DEBUG: Calling app_graph.astream(None, config)")
        step_count = 0
        async for event in app_graph.astream(None, config):
            step_count += 1
            if event:
                event_nodes = list(event.keys())
                logger.info(f"📊 RESUME EVENT #{step_count}: {', '.join(event_nodes)}")
                logger.info(f"   Event Payload Keys: {list(event.values())[0].keys() if len(event.values()) > 0 and isinstance(list(event.values())[0], dict) else 'N/A'}")
                
                # Update final_state with each event
                for node_name, node_output in event.items():
                    if node_name != "__interrupt__" and isinstance(node_output, dict):
                        for key, value in node_output.items():
                            if hasattr(final_state, key):
                                setattr(final_state, key, value)
                                logger.info(f"   Updated state field: {key}")
        
        logger.info(f"🏁 DEBUG: Stream finished. Total steps: {step_count}")
        
        logger.info("="*80)
        logger.info("✅ COUNCIL PIPELINE: Resume completed")
        logger.info("="*80)
        return final_state
    
    except Exception as e:
        logger.error(f"❌ Error resuming pipeline: {e}")
        raise
