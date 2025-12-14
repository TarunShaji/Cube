
import asyncio
import json
import logging
from app.state import MeetingState, MeetingMetadata, TranscriptSegment
from app.graph.workflow_council import run_council_pipeline, resume_council_pipeline

# Configure logging to see agent activity
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("app.graph")
logger.setLevel(logging.INFO)

async def test_council_pipeline():
    """
    Test the Council Architecture pipeline with:
    1. Parallel Processing (Strategist + Extractor)
    2. Debate Loop (Critic validation)
    3. Human-in-the-Loop (Checkpoint & Resume)
    4. Refinement (Integrated feedback)
    """
    print("=" * 80)
    print("🏛️ COUNCIL ARCHITECTURE TEST")
    print("=" * 80)
    print()
    
    # 1. Load Static Transcript
    print("📂 Loading static transcript...")
    with open("tests/static_transcript.json", "r") as f:
        raw_data = json.load(f)
    
    # 2. Hydrate State
    initial_state = MeetingState(
        meeting_id=raw_data["meeting_id"],
        metadata=MeetingMetadata(**raw_data["metadata"]),
        transcript=[TranscriptSegment(**t) for t in raw_data["transcript"]]
    )
    
    print(f"✅ Loaded: {initial_state.metadata.title}")
    print(f"   📝 Transcript segments: {len(initial_state.transcript)}")
    print()
    
    # 3. Run Council Pipeline (Will pause at human_review)
    print("=" * 80)
    print("🚀 RUNNING COUNCIL PIPELINE")
    print("=" * 80)
    print()
    print("Expected Flow:")
    print("  1️⃣ Strategist & Extractor (Parallel)")
    print("  2️⃣ Critic validates both")
    print("  3️⃣ If rejected → Debate Loop (retry)")
    print("  4️⃣ If approved → Copywriter drafts email")
    print("  5️⃣ Pipeline PAUSES at Human Review ⏸️")
    print()
    
    final_state = await run_council_pipeline(initial_state, thread_id="test_council_001")
    
    print()
    print("=" * 80)
    print("⏸️ PIPELINE PAUSED AT HUMAN REVIEW CHECKPOINT")
    print("=" * 80)
    print()
    
    # 4. Display Council Outputs
    print("📊 COUNCIL OUTPUTS:")
    print()
    
    print("🎯 STRATEGIST:")
    print(f"   Meeting Type: {final_state.strategist.meeting_type}")
    print(f"   Tone: {final_state.strategist.tone}")
    print(f"   Sentiment: {final_state.strategist.sentiment}")
    print(f"   Evidence Lines: {final_state.strategist.evidence_timestamps}")
    print()
    
    print("📊 EXTRACTOR:")
    print(f"   Commitments: {len(final_state.extractor.commitments)}")
    for c in final_state.extractor.commitments:
        print(f"      • {c.owner}: {c.task} (Due: {c.due})")
    print(f"   Decisions: {final_state.extractor.decisions}")
    print(f"   Metrics: {final_state.extractor.metrics}")
    print()
    
    print("⚖️ CRITIC VALIDATION:")
    print(f"   Strategist Approved: {final_state.critic.strategist_approved}")
    print(f"   Extractor Approved: {final_state.critic.extractor_approved}")
    print(f"   Overall Status: {final_state.critic.overall_status}")
    if final_state.critic.strategist_feedback:
        print(f"   Strategist Feedback: {final_state.critic.strategist_feedback}")
    if final_state.critic.extractor_feedback:
        print(f"   Extractor Feedback: {final_state.critic.extractor_feedback}")
    print()
    
    print("📧 DRAFT EMAIL:")
    print(f"   Subject: {final_state.email.subject}")
    print("-" * 80)
    print(final_state.email.body)
    print("-" * 80)
    print()
    
    print("🔄 RETRY COUNTS:")
    print(f"   {final_state.retry_counts}")
    print()
    
    # 5. Simulate Human Feedback (Revision Request)
    print("=" * 80)
    print("👤 SIMULATING HUMAN FEEDBACK (Revision Request)")
    print("=" * 80)
    print()
    
    user_feedback = "Add a commitment for Bob to review the budget by next Monday"
    print(f"User says: \"{user_feedback}\"")
    print()
    
    print("🔄 Resuming Council Pipeline with feedback...")
    print("Expected Flow:")
    print("  1️⃣ Refiner applies user feedback")
    print("  2️⃣ Copywriter re-drafts email")
    print("  3️⃣ Returns to Human Review checkpoint")
    print()
    
    updated_state = await resume_council_pipeline(
        thread_id="test_council_001",
        user_feedback=user_feedback
    )
    
    print()
    print("=" * 80)
    print("✅ PIPELINE RESUMED AND UPDATED")
    print("=" * 80)
    print()
    
    print("📧 UPDATED DRAFT EMAIL:")
    print(f"   Subject: {updated_state.email.subject}")
    print("-" * 80)
    print(updated_state.email.body)
    print("-" * 80)
    print()
    
    print("📊 UPDATED COMMITMENTS (from Extractor):")
    for c in updated_state.extractor.commitments:
        print(f"   • {c.owner}: {c.task} (Due: {c.due})")
    print()
    
    # 6. Summary
    print("=" * 80)
    print("🏁 TEST SUMMARY")
    print("=" * 80)
    print()
    print("✅ Council Architecture Features Tested:")
    print("   1. ✓ Parallel Processing (Strategist + Extractor)")
    print("   2. ✓ Critic Validation (Debate Loop capable)")
    print("   3. ✓ Human-in-the-Loop (Checkpoint & Pause)")
    print("   4. ✓ Integrated Refinement (Resume with feedback)")
    print("   5. ✓ State Persistence (Checkpointer)")
    print()
    print("📝 Key Differences from Old Linear Pipeline:")
    print("   • Agents run in parallel where possible")
    print("   • Critic can reject and loop back to specific agents")
    print("   • Human feedback is part of the graph (not external)")
    print("   • Refinement doesn't re-run the full pipeline")
    print()
    print("🎯 Production Readiness:")
    print("   • Replace MemorySaver with PostgresSaver/RedisSaver")
    print("   • Add timeout handling for human review")
    print("   • Implement webhook for final approval → email send")
    print()

if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "COUNCIL PIPELINE TEST SUITE" + " " * 31 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")
    
    asyncio.run(test_council_pipeline())
    
    print("\n")
    print("🏛️ Council Architecture Test Complete!")
    print()
