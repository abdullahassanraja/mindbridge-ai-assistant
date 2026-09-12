# graph.py
# LangGraph StateGraph construction and compilation for MindBridge Wellness.

from typing import Literal
from langgraph.graph import StateGraph, START, END

from state import AgentState
from nodes import (
    crisis_check_node,
    intent_router_node,
    rag_qa_node,
    qualification_flow_node,
    therapist_matching_node,
    scheduling_stub_node,
    lead_capture_node,
    human_handoff_node,
    has_concrete_concern,
)


def route_after_crisis_check(state: AgentState) -> Literal["end", "intent_router"]:
    """If crisis detected, immediately terminate graph execution for safety."""
    if state.get("crisis_flag", False):
        return "end"
    return "intent_router"


def route_after_intent_router(state: AgentState) -> Literal[
    "human_handoff",
    "scheduling_stub",
    "qualification_flow",
    "therapist_matching",
    "rag_qa",
]:
    """Route message to appropriate specialized node based on classified intent."""
    intent = state.get("current_intent", "general_question")

    if intent == "wants_human":
        return "human_handoff"
    elif intent == "scheduling_request":
        return "scheduling_stub"
    elif intent == "seeking_support":
        return "qualification_flow"
    elif intent == "therapist_matching":
        # STRUCTURAL GATE: Therapist matching requires at least one concrete, specific concern
        concern = state.get("concern_collected") or state.get("visitor_need")
        if not has_concrete_concern(concern):
            return "qualification_flow"
        return "therapist_matching"
    elif intent == "other":
        return "qualification_flow"
    else:
        return "rag_qa"


def route_after_qualification(state: AgentState) -> Literal["therapist_matching", "lead_capture"]:
    """Check if qualification step should transition into therapist matching."""
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    if user_messages:
        latest = user_messages[-1]["content"].lower()
        matching_cues = ["recommend", "therapist", "who", "match", "suggest", "which counselor"]
        concern = state.get("concern_collected") or state.get("visitor_need")

        # STRUCTURAL GATE: Therapist matching requires at least one concrete, specific concern
        if has_concrete_concern(concern):
            if any(cue in latest for cue in matching_cues) or any(
                affirm in latest for affirm in ["yes", "please", "sure", "sounds good"]
            ):
                if not state.get("suggested_therapist"):
                    return "therapist_matching"

    return "lead_capture"


def build_graph(checkpointer=None):
    """Build and compile the LangGraph StateGraph, optionally with a checkpointer."""
    builder = StateGraph(AgentState)

    # 1. Add all 8 nodes
    builder.add_node("crisis_check", crisis_check_node)
    builder.add_node("intent_router", intent_router_node)
    builder.add_node("rag_qa", rag_qa_node)
    builder.add_node("qualification_flow", qualification_flow_node)
    builder.add_node("therapist_matching", therapist_matching_node)
    builder.add_node("scheduling_stub", scheduling_stub_node)
    builder.add_node("lead_capture", lead_capture_node)
    builder.add_node("human_handoff", human_handoff_node)

    # 2. Wire entry point
    builder.add_edge(START, "crisis_check")

    # 3. Crisis conditional routing
    builder.add_conditional_edges(
        "crisis_check",
        route_after_crisis_check,
        {
            "end": END,
            "intent_router": "intent_router",
        },
    )

    # 4. Intent conditional routing
    builder.add_conditional_edges(
        "intent_router",
        route_after_intent_router,
        {
            "human_handoff": "human_handoff",
            "scheduling_stub": "scheduling_stub",
            "qualification_flow": "qualification_flow",
            "therapist_matching": "therapist_matching",
            "rag_qa": "rag_qa",
        },
    )

    # 5. Qualification routing to matching or lead capture
    builder.add_conditional_edges(
        "qualification_flow",
        route_after_qualification,
        {
            "therapist_matching": "therapist_matching",
            "lead_capture": "lead_capture",
        },
    )

    # 6. Reconvergence through lead_capture to END
    builder.add_edge("therapist_matching", "lead_capture")
    builder.add_edge("rag_qa", "lead_capture")
    builder.add_edge("scheduling_stub", "lead_capture")
    builder.add_edge("human_handoff", "lead_capture")
    builder.add_edge("lead_capture", END)

    return builder.compile(checkpointer=checkpointer)


# Compiled singleton graph instance (uncheckpointed for CLI / tests)
app_graph = build_graph()

