# state.py
# LangGraph state schema for MindBridge Wellness AI intake assistant.

from typing import TypedDict, List, Dict, Any, Optional


class QualificationInfo(TypedDict, total=False):
    name: Optional[str]
    contact: Optional[str]  # email address or phone number
    who_is_it_for: Optional[str]  # self, partner, family, teen/child
    preferences: Optional[str]  # in-person vs video, timing, gender or style preferences
    urgency: Optional[str]  # timing signals: flexible, next week, as soon as possible


class AgentState(TypedDict):
    # Complete conversation message history: list of {"role": "user"|"assistant"|"system", "content": str}
    messages: List[Dict[str, str]]
    # Stated reason for seeking counseling
    visitor_need: Optional[str]
    # Structured intake info accumulated across conversation turns
    qualification_info: Dict[str, Any]
    # Suggested therapist profile match (if matched)
    suggested_therapist: Optional[str]
    # Safety flag: set to True immediately if crisis/self-harm indicators are detected
    crisis_flag: bool
    # Flag indicating whether conversation has transitioned to human staff handoff
    handoff_requested: bool
    # Flag to prevent duplicate lead notification submissions
    lead_captured: bool
    # Total conversational turns completed in this session
    turn_count: int
    # Most recently classified user intent
    current_intent: Optional[str]
    # Reason recorded for human handoff (if applicable)
    handoff_reason: Optional[str]
    # Independently tracked qualification pieces:
    name_collected: Optional[str]
    concern_collected: Optional[str]
    contact_collected: Optional[str]
    contact_declined: bool
    # Session tracking
    session_id: Optional[str]
    # Scheduling fields
    preferred_date: Optional[str]
    preferred_time: Optional[str]
    scheduling_requested: bool
    scheduling_request_logged: bool
    # Scope guardrail flag
    off_topic: bool


def create_initial_state() -> AgentState:
    """Create a clean default starting state for a new conversation session."""
    return {
        "messages": [],
        "visitor_need": None,
        "qualification_info": {},
        "suggested_therapist": None,
        "crisis_flag": False,
        "handoff_requested": False,
        "lead_captured": False,
        "turn_count": 0,
        "current_intent": None,
        "handoff_reason": None,
        "name_collected": None,
        "concern_collected": None,
        "contact_collected": None,
        "contact_declined": False,
        "session_id": None,
        "preferred_date": None,
        "preferred_time": None,
        "scheduling_requested": False,
        "scheduling_request_logged": False,
        "off_topic": False,
    }

