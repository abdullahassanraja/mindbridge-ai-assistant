"""Test: Reproduce and verify fix for scheduling loop bug.

Tests:
1. "20 september btw 2 and 10 pm" — exact bug report scenario
2. "next Tuesday at 3pm" — well-formatted input (regression check)
3. "whenever" — genuinely unclear input (should ask clarifying follow-up)
"""
import os
import sys
import uuid
from pathlib import Path

agent_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(agent_dir))
sys.path.insert(0, str(agent_dir.parent / "ingestion"))
os.environ.setdefault("QDRANT_PATH", str(agent_dir.parent / "ingestion" / "qdrant_data"))
os.environ["DEBUG"] = "true"

from langgraph.checkpoint.memory import MemorySaver
from graph import build_graph
from state import create_initial_state
from nodes import _extract_preferred_datetime

# ============================================================
# Unit test: _extract_preferred_datetime on all formats
# ============================================================
print("=" * 70)
print("UNIT TEST: _extract_preferred_datetime")
print("=" * 70)

test_inputs = [
    ("20 september btw 2 and 10 pm", True),
    ("sunday from 2 and 10 pm", True),
    ("next Tuesday at 3pm", True),
    ("september 20 between 2 and 10pm", True),
    ("the 20th at 3pm", True),
    ("friday afternoon", True),
    ("tomorrow morning", True),
    ("wednesday afternoon around 2:30pm", True),
    ("9/20 at 2pm", True),
    ("whenever", False),
    ("I don't know", False),
    ("hi", False),
]

all_unit_pass = True
for text, should_match in test_inputs:
    result = _extract_preferred_datetime(text)
    matched = result is not None
    passed = matched == should_match
    status = "PASS" if passed else "FAIL"
    if not passed:
        all_unit_pass = False
    print(f"  [{status}] '{text}' -> {repr(result)} (expected match={should_match})")

print(f"\nUnit tests: {'ALL PASSED' if all_unit_pass else 'SOME FAILED'}")

# ============================================================
# Integration Test 1: Exact bug report scenario
# ============================================================
print("\n" + "=" * 70)
print("INTEGRATION TEST 1: '20 september btw 2 and 10 pm'")
print("=" * 70)

def run_conversation(messages_list):
    """Run a full multi-turn conversation and return (final_state, responses)."""
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    session_id = f"test-sched-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": session_id}}
    
    state = create_initial_state()
    state["session_id"] = session_id
    responses = []
    
    for msg in messages_list:
        state["messages"].append({"role": "user", "content": msg})
        final_state = graph.invoke(state, config=config)
        state = dict(final_state)
        
        assistant_msgs = [m for m in state["messages"] if m["role"] == "assistant"]
        latest_reply = assistant_msgs[-1]["content"] if assistant_msgs else "(no reply)"
        responses.append(latest_reply)
        
        print(f"\n  USER: {msg}")
        print(f"  ELLEN: {latest_reply[:200]}")
        print(f"  [State] preferred_date={state.get('preferred_date')} | scheduling_request_logged={state.get('scheduling_request_logged')} | contact={state.get('contact_collected')}")
    
    return state, responses

# Flow: greeting -> name -> concern -> scheduling cue -> date/time answer
test1_msgs = [
    "hi",
    "Sarah",
    "I've been having a lot of anxiety lately",
    "I'd like to schedule an appointment",
    "20 september btw 2 and 10 pm",
]

state1, responses1 = run_conversation(test1_msgs)

# Verify: preferred_date should be set after the date/time message
t1_pass = (
    state1.get("preferred_date") is not None and
    "september" in state1.get("preferred_date", "").lower() and
    "what day" not in responses1[-1].lower()
)
print(f"\n  Result Test 1: {'PASS' if t1_pass else 'FAIL'}")
print(f"  preferred_date = {state1.get('preferred_date')}")
print(f"  Response does NOT re-ask: {'what day' not in responses1[-1].lower()}")

# ============================================================
# Integration Test 2: Well-formatted input
# ============================================================
print("\n" + "=" * 70)
print("INTEGRATION TEST 2: 'next Tuesday at 3pm'")
print("=" * 70)

test2_msgs = [
    "hi",
    "Jake",
    "dealing with work stress and burnout",
    "I want to schedule an appointment",
    "next Tuesday at 3pm",
]

state2, responses2 = run_conversation(test2_msgs)

t2_pass = (
    state2.get("preferred_date") is not None and
    "tuesday" in state2.get("preferred_date", "").lower() and
    "what day" not in responses2[-1].lower()
)
print(f"\n  Result Test 2: {'PASS' if t2_pass else 'FAIL'}")
print(f"  preferred_date = {state2.get('preferred_date')}")

# ============================================================
# Integration Test 3: Genuinely unclear input ("whenever")
# ============================================================
print("\n" + "=" * 70)
print("INTEGRATION TEST 3: 'whenever' (should prompt for clarification)")
print("=" * 70)

test3_msgs = [
    "hi",
    "Mia",
    "I need help with relationship issues",
    "I'd like to schedule",
    "whenever",
]

state3, responses3 = run_conversation(test3_msgs)

# "whenever" should NOT set preferred_date, and the response should ask for specifics
t3_pass = (
    state3.get("preferred_date") is None and
    not state3.get("scheduling_request_logged", False)
)
print(f"\n  Result Test 3: {'PASS' if t3_pass else 'FAIL'}")
print(f"  preferred_date = {state3.get('preferred_date')} (should be None)")
print(f"  scheduling_request_logged = {state3.get('scheduling_request_logged')} (should be False)")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
all_pass = all_unit_pass and t1_pass and t2_pass and t3_pass
print(f"  Unit tests:         {'PASS' if all_unit_pass else 'FAIL'}")
print(f"  Test 1 (bug report): {'PASS' if t1_pass else 'FAIL'}")
print(f"  Test 2 (well-formatted): {'PASS' if t2_pass else 'FAIL'}")
print(f"  Test 3 (unclear):   {'PASS' if t3_pass else 'FAIL'}")
print(f"  Overall:            {'ALL PASSED' if all_pass else 'SOME FAILED'}")
