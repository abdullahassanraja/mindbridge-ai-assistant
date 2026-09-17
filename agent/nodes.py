# nodes.py
# Node implementations for MindBridge Wellness LangGraph conversational agent.

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure ingestion directory is in sys.path and configure QDRANT_PATH default
ingestion_dir = Path(__file__).resolve().parent.parent / "ingestion"
if str(ingestion_dir) not in sys.path:
    sys.path.insert(0, str(ingestion_dir))

os.environ.setdefault("QDRANT_PATH", str(ingestion_dir / "qdrant_data"))

try:
    from ingest import search
except Exception as e:
    _safe_print(f"[Warning] Could not import search from ingestion.ingest: {e}")
    search = None

from state import AgentState
from crisis_response import CRISIS_RESPONSE_TEXT, CRISIS_HANDOFF_LOCKED_TEXT
from safety_prompts import (
    STYLE_SYSTEM_PROMPT,
    SAFETY_SYSTEM_PROMPT,
    CRISIS_DETECTION_SYSTEM_PROMPT,
    INTENT_ROUTER_SYSTEM_PROMPT,
    RAG_QA_SYSTEM_PROMPT,
    QUALIFICATION_SYSTEM_PROMPT,
    THERAPIST_MATCHING_SYSTEM_PROMPT,
    SCHEDULING_SYSTEM_PROMPT,
)
from leads import send_lead_email, log_handoff
from sheets import append_lead, append_scheduling_request
from llm import call_llm, _safe_print
from scope_guard import classify_scope, generate_scope_redirect
from date_resolution import resolve_scheduling_input, get_current_datetime, format_date_display


def _is_contact_declined(text: str) -> bool:
    """Detect if the visitor declined to share contact info."""
    lower = text.lower().strip()
    decline_patterns = [
        r"\b(rather not|prefer not|don't want to|do not want to|no email|no phone|skip|decline|keep it private|private|not sharing|not ready to share|no thanks|nope)\b",
        r"^(no|nope|nah|skip|pass)$",
    ]
    return any(re.search(pat, lower) for pat in decline_patterns)


VAGUE_INPUT_PATTERNS = [
    r"\b(just looking|looking around|just browsing|browsing|just exploring|exploring)\b",
    r"\b(not sure|not sure what i need|not really sure|unsure|unclear)\b",
    r"\b(i don't know|i dont know|idk|no idea|don't know|dont know)\b",
    r"\b(can you help|can you help me|help me figure|see what you have|see what you offer)\b",
    r"\b(nothing specific|nothing in particular|nothing really|no reason|just checking)\b",
]

CLINICAL_CONCERN_KEYWORDS = [
    "anxiet", "depress", "stress", "worry", "panic", "burnout",
    "grief", "loss", "bereave", "mourn",
    "partner", "husband", "wife", "marriage", "couples", "conflict", "fight", "arguing", "relationship",
    "teen", "adolescent", "child", "son", "daughter", "family", "parent",
    "trauma", "ptsd", "abuse",
    "adhd", "focus", "ocd", "eating", "insomnia", "sleep",
    "transition", "career", "lonel", "self-esteem"
]


def is_vague_or_uncertain(text: str) -> bool:
    """Detect if a visitor's statement is vague, exploratory, non-committal, or uncertain."""
    if not text:
        return False
    lower = text.lower().strip()
    # If text explicitly mentions clinical concern keywords, it is not vague
    if any(k in lower for k in CLINICAL_CONCERN_KEYWORDS):
        return False
    # Check for direct vague patterns
    if any(re.search(pat, lower) for pat in VAGUE_INPUT_PATTERNS):
        return True
    return False


NON_NAME_WORDS = {
    # Greetings & closings
    "hi", "hello", "hey", "there", "good", "morning", "afternoon", "evening", "howdy", "greetings",
    "bye", "goodbye", "later",
    # Name introduction pronouns and particles
    "my", "name", "is", "am", "i", "im", "this", "call", "me",
    # Affirmations & negatives
    "yes", "no", "sure", "ok", "okay", "yep", "nope", "please", "thanks", "thank", "you",
    # Verbs & states
    "struggling", "dealing", "feeling", "looking", "seeking", "hoping", "trying",
    "having", "going", "reaching", "calling", "writing", "wondering", "asking",
    "anxious", "depressed", "stressed", "overwhelmed", "hurt", "sad", "scared", "afraid",
    "tired", "exhausted", "lost", "angry", "fine", "bad", "well", "better",
    "interested", "ready", "new", "here", "just", "someone", "anyone", "person",
    "help", "therapy", "counseling", "support", "appointment", "consultation",
    "therapist", "counselor", "find", "right", "match", "looking", "suggest", "recommend",
    "partner", "husband", "wife", "son", "daughter", "friend", "family", "doctor",
    "with", "for", "about", "from", "at", "in", "to", "on", "into", "and", "or", "but"
}

MATCHING_META_PATTERNS = [
    r"\bhelp\s+me\s+find\s+(?:the\s+)?(?:right\s+)?(?:therapist|counselor|support)\b",
    r"\bfind\s+(?:the\s+)?(?:right\s+)?(?:therapist|counselor)\b",
    r"\blooking\s+for\s+(?:a|the)?\s*(?:right\s+)?(?:therapist|counselor)\b",
    r"\b(?:recommend|suggest|match)\s+(?:me\s+)?(?:a|the|someone)?\s*(?:right\s+)?(?:therapist|counselor)\b",
]

GREETING_OPENERS = {
    "hi", "hello", "hey", "hi there", "hello there", "hey there",
    "good morning", "good afternoon", "good evening", "howdy", "greetings", "start", "yo"
}


def has_concrete_concern(text: Optional[str]) -> bool:
    """Check if the text contains a concrete, specific situation or clinical need."""
    if not text:
        return False
    lower = text.lower().strip()
    if is_vague_or_uncertain(lower):
        return False
    # If the text is an explicit name introduction, it is not a clinical concern
    if re.match(r'^(?:my name is|i am|i\'m|call me|name is|this is)\s+[a-z]+(?:\s+[a-z]+)*$', lower):
        return False
    # If the text is just a meta-request or starter chip asking to find a therapist, without symptoms
    if any(re.search(pat, lower) for pat in MATCHING_META_PATTERNS):
        if not any(k in lower for k in CLINICAL_CONCERN_KEYWORDS):
            return False
    if any(k in lower for k in CLINICAL_CONCERN_KEYWORDS):
        return True
    words = [w for w in re.findall(r'[a-z]+', lower) if w not in NON_NAME_WORDS]
    if len(words) >= 3 and not is_vague_or_uncertain(lower):
        return True
    return False


def is_greeting_or_short_opener(text: str, state: AgentState) -> bool:
    """Detect if the message is a simple greeting or short opener (name, intro) that belongs in qualification flow."""
    if not text:
        return False
    lower = text.lower().strip()
    cleaned = re.sub(r'[^\w\s]', '', lower).strip()
    if cleaned in GREETING_OPENERS:
        return True
    if any(re.match(p, cleaned) for p in [
        r"^(?:hi|hello|hey|howdy|greetings|yo)(?:\s+there)?$",
        r"^good\s+(?:morning|afternoon|evening|day)$",
    ]):
        return True
    # Explicit name introductions: "my name is Sarah", "i am Sarah", "i'm Sarah", "call me Sarah", "this is Sarah"
    if re.match(r'^(?:my name is|i am|i\'m|call me|this is)\s+[a-z]+(?:\s+[a-z]+)?$', lower.rstrip(".!?, ")):
        return True
    # Bare first name when expecting a name or no name collected yet
    # e.g., 1-2 words like "Sarah" or "Sarah Jenkins"
    words = cleaned.split()
    if 1 <= len(words) <= 2 and all(w.isalpha() for w in words):
        if not any(k in cleaned for k in CLINICAL_CONCERN_KEYWORDS):
            non_opener_words = {
                "yes", "no", "why", "what", "where", "when", "how", "who",
                "hours", "cost", "fees", "insurance", "schedule", "book", "appointment",
                "medication", "prescribe", "human", "person", "cancel"
            }
            if not any(w in non_opener_words for w in words):
                if not state.get("name_collected") or len(state.get("messages", [])) <= 4:
                    return True
    return False


def _extract_contact_info(text: str, expecting_name: bool = False) -> Dict[str, str]:
    """Helper to detect name, email, and phone numbers in user messages."""
    found: Dict[str, str] = {}
    
    # Email pattern
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        found["email"] = email_match.group(0)

    # Phone pattern
    phone_match = re.search(r'(\+?\d{1,2}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phone_match:
        found["phone"] = phone_match.group(0)

    # 1. Explicit name introductions: "my name is X", "call me X", "name is X", "this is X", "X here"
    explicit_name = re.search(r"\b(?:my name is|call me|name is|this is)\s+([^\W\d_]+(?:\s+[^\W\d_]+)?)", text, re.IGNORECASE)
    if not explicit_name:
        explicit_name = re.search(r"\(?([^\W\d_]+)\s+here\)?", text, re.IGNORECASE)
    if explicit_name:
        candidate = explicit_name.group(1).strip()
        words = candidate.split()
        if all(w.lower() not in NON_NAME_WORDS for w in words):
            found["name"] = candidate.title()

    # 2. "I'm X" or "I am X" (only if NOT followed by verb/adjective/preposition)
    if not found.get("name"):
        iam_match = re.search(r"\b(?:i am|i'm|im)\s+([^\W\d_]+(?:\s+[^\W\d_]+)?)", text, re.IGNORECASE)
        if iam_match:
            candidate = iam_match.group(1).strip()
            words = candidate.split()
            if 1 <= len(words) <= 2:
                if all(w.lower() not in NON_NAME_WORDS and not w.lower().endswith("ing") and not w.lower().endswith("ed") for w in words):
                    found["name"] = candidate.title()

    # 3. Simple standalone name answer (1-2 words) when expecting name
    if not found.get("name") and expecting_name:
        cleaned = text.strip().rstrip(".!?,")
        words = cleaned.split()
        if 1 <= len(words) <= 2 and all(w.isalpha() for w in words):
            if all(w.lower() not in NON_NAME_WORDS for w in words):
                found["name"] = cleaned.title()

    return found


# Day patterns: weekday names, relative days, month names, numeric dates, ordinals
DATETIME_DAYS_PATTERN = (
    r'\b('
    r'monday|tuesday|wednesday|thursday|friday|saturday|sunday'
    r'|mon|tue|wed|thu|fri|sat|sun'
    r'|today|tomorrow|weekend|weekdays?|next week|this week'
    r'|january|february|march|april|may|june|july|august|september|october|november|december'
    r'|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec'
    r'|\d{1,2}(?:st|nd|rd|th)'
    r'|the\s+\d{1,2}(?:st|nd|rd|th)?'
    r')\b'
)

# Time patterns: time of day words, numeric times, casual ranges
DATETIME_TIMES_PATTERN = (
    r'\b('
    r'morning|afternoon|evening|night|noon|midday|lunchtime'
    r'|\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)'
    r'|\d{1,2}\s*o\'?clock'
    r'|(?:after|around|before|between|btw|from)\s+\d{1,2}'
    r'|\d{1,2}\s+(?:to|and|-)\s+\d{1,2}'
    r')\b'
)

# Catch-all: numeric date pattern like "20 september" or "september 20" or "9/20" or "20/9"
DATETIME_DATE_NUMERIC_PATTERN = (
    r'\b(?:'
    r'\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)'
    r'|(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+\d{1,2}'
    r'|\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?'
    r')\b'
)


def _extract_preferred_datetime(text: str) -> Optional[str]:
    """Extract preferred date/time phrasing as free text from visitor input.
    
    Designed to be PERMISSIVE: any plausible scheduling answer counts.
    Catches weekday names, month names, numeric dates, ordinals, time-of-day words,
    numeric times (with or without am/pm), and casual ranges ('btw 2 and 10 pm').
    """
    if not text:
        return None
    lower = text.lower().strip()
    
    has_day = bool(re.search(DATETIME_DAYS_PATTERN, lower, re.IGNORECASE))
    has_time = bool(re.search(DATETIME_TIMES_PATTERN, lower, re.IGNORECASE))
    has_date_numeric = bool(re.search(DATETIME_DATE_NUMERIC_PATTERN, lower, re.IGNORECASE))
    
    # Also catch standalone digit + pm/am patterns that might be preceded by 'btw'/'from'/'between'
    has_casual_time_range = bool(re.search(
        r'(?:btw|between|from)\s+\d{1,2}\s+(?:and|to|-)\s+\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.)?',
        lower
    ))
    
    if has_day or has_time or has_date_numeric or has_casual_time_range:
        cleaned = text.strip().rstrip(".!?,")
        prefix_pattern = r'^(?:how about|what about|maybe|i am free|i\'m free|i prefer|preferably|let\'s do|can we do|does|is)\s+(?:on\s+)?'
        candidate = re.sub(prefix_pattern, '', cleaned, flags=re.IGNORECASE).strip()
        return candidate if candidate else cleaned
    return None


def crisis_check_node(state: AgentState) -> AgentState:
    """Node 1: Runs FIRST on every user turn. Evaluates safety and crisis risk."""
    state["turn_count"] = state.get("turn_count", 0) + 1

    # If the conversation was previously flagged for crisis, permanently lock in handoff mode
    if state.get("crisis_flag", False):
        state["messages"].append({
            "role": "assistant",
            "content": CRISIS_HANDOFF_LOCKED_TEXT,
        })
        state["handoff_requested"] = True
        return state

    # Extract the latest user message
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    if not user_messages:
        return state

    latest_user_text = user_messages[-1]["content"]

    # Classify message using safety classifier
    full_prompt = SAFETY_SYSTEM_PROMPT + "\n\n" + CRISIS_DETECTION_SYSTEM_PROMPT
    raw_response = call_llm(
        system_prompt=full_prompt,
        user_prompt=latest_user_text,
        json_mode=True,
    )

    is_crisis = False
    try:
        parsed = json.loads(raw_response)
        is_crisis = bool(parsed.get("is_crisis", False))
    except Exception:
        pass

    # Deterministic safety fallback: keyword scan always runs to safeguard against LLM drift or API drops
    crisis_keywords = [
        "suicide", "kill myself", "end my life", "end it all", "die", "harm myself",
        "cut myself", "overdose", "point in going on", "no reason to live",
        "better off dead", "don't want to live", "dont want to live", "not worth living"
    ]
    if any(k in latest_user_text.lower() for k in crisis_keywords):
        is_crisis = True

    if is_crisis:
        state["crisis_flag"] = True
        state["handoff_requested"] = True
        state["handoff_reason"] = "crisis_safety_indicator"
        
        # Respond strictly with the editable crisis template
        state["messages"].append({
            "role": "assistant",
            "content": CRISIS_RESPONSE_TEXT,
        })
        
        # Log handoff event immediately
        log_handoff(
            reason="crisis_detected",
            conversation_history=state["messages"],
            lead_info=state.get("qualification_info", {}),
        )

    return state


def scope_guard_node(state: AgentState) -> AgentState:
    """Node 1b: Evaluates message scope immediately after crisis_check and before intent_router.
    
    If the message is off-topic (coding, math, trivia, creative writing, weather, roleplay, etc.):
      - Sets state["off_topic"] = True
      - Generates Ellen's warm, concise redirect back to counseling capabilities
      - Appends the assistant reply to state["messages"]
    If in-scope:
      - Sets state["off_topic"] = False
    """
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    user_messages = [m for m in state.get("messages", []) if m.get("role") == "user"]
    if not user_messages:
        state["off_topic"] = False
        return state

    latest_user_text = user_messages[-1]["content"]
    is_off_topic, category, reason = classify_scope(latest_user_text, state)

    if is_off_topic:
        state["off_topic"] = True
        if is_debug:
            _safe_print(f"[scope_guard] Message: '{latest_user_text}' -> OFF-TOPIC ({category}): {reason}")
        redirect_text = generate_scope_redirect(latest_user_text, category)
        state["messages"].append({
            "role": "assistant",
            "content": redirect_text,
        })
    else:
        state["off_topic"] = False
        if is_debug:
            _safe_print(f"[scope_guard] Message: '{latest_user_text}' -> IN-SCOPE ({reason})")

    return state


def intent_router_node(state: AgentState) -> AgentState:
    """Node 2: Classify visitor intent and route downstream."""
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"]
    lower_user = latest_user_text.lower()

    # Detect user frustration or explicit human request
    frustration_patterns = ["stop repeating", "talk to human", "real person", "speak to someone", "this is unhelpful", "you don't understand"]
    if any(p in lower_user for p in frustration_patterns) and "are you a real person" not in lower_user:
        state["current_intent"] = "wants_human"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'wants_human' (frustration/human pattern matched)")
        return state

    # If scheduling flow is already underway (visitor giving timing, name, or contact info)
    if state.get("scheduling_requested") and not state.get("scheduling_request_logged"):
        state["current_intent"] = "scheduling_request"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'scheduling_request' (active scheduling flow)")
        return state

    # 1. Deterministic greeting & short opener routing (BUG 1 FIX)
    if is_greeting_or_short_opener(latest_user_text, state):
        state["current_intent"] = "seeking_support"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'seeking_support' (greeting/opener deterministic match)")
        return state

    # Check for active scheduling flow or explicit scheduling keywords
    scheduling_cues = [
        "schedule", "appointment", "book", "consultation", "availability",
        "openings", "set up a time", "set up an appointment", "book a session",
        "meet with", "reserve", "what time", "what day", "slot"
    ]
    has_sched_cue = any(c in lower_user for c in scheduling_cues)

    # If explicit scheduling cues are present
    if has_sched_cue:
        state["current_intent"] = "scheduling_request"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'scheduling_request' (scheduling cue matched)")
        return state

    # If therapist was suggested and visitor affirms connecting/scheduling
    if state.get("suggested_therapist"):
        affirm_cues = ["yes", "please", "sure", "sounds good", "connect", "let's do it", "let's do that", "reach out", "yep", "ok", "okay", "i would", "i'd like that"]
        if any(a in lower_user for a in affirm_cues) or _extract_preferred_datetime(latest_user_text):
            state["current_intent"] = "scheduling_request"
            if is_debug:
                _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'scheduling_request' (post-match affirmation / timing)")
            return state

    # 2. Deterministic therapist matching routing (BUG 2(a) FIX)
    # If concrete concern is already collected, and visitor asks for or affirms therapist matching
    stored_concern = state.get("concern_collected") or state.get("visitor_need")
    matching_cues = [
        "recommend", "suggest", "who", "which therapist", "which counselor",
        "match", "find someone", "therapist recommendation", "counselor recommendation",
        "someone for", "who do you have", "who would you recommend", "suggest someone",
        "recommend someone", "suggest a therapist", "recommend a therapist"
    ]
    has_matching_cue = any(c in lower_user for c in matching_cues)
    
    # Affirmation to a previous recommendation offer
    prev_assistant_messages = [m for m in state.get("messages", []) if m["role"] == "assistant"]
    prev_assistant_text = prev_assistant_messages[-1]["content"].lower() if prev_assistant_messages else ""
    offered_recommendation = any(w in prev_assistant_text for w in ["recommendation", "suggest", "match", "therapist", "counselor", "options"])
    is_affirm_cue = any(a in lower_user.split() or a == lower_user.strip() for a in ["yes", "please", "sure", "sounds good", "okay", "yep", "i would", "i'd like that"])

    if stored_concern and has_concrete_concern(stored_concern):
        if has_matching_cue or (is_affirm_cue and offered_recommendation):
            state["current_intent"] = "therapist_matching"
            if is_debug:
                _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'therapist_matching' (deterministic matching cue with stored concern)")
            return state

    # 3. Starter chip / meta matching request without a stored concern -> route to qualification_flow (BUG 3 FIX)
    if any(re.search(pat, lower_user) for pat in MATCHING_META_PATTERNS) and not stored_concern:
        state["current_intent"] = "seeking_support"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'seeking_support' (starter chip / matching meta-request)")
        return state

    # If visitor is in active intake qualification and provided a name, decline, or contact info
    if _is_contact_declined(latest_user_text) or "@" in latest_user_text or re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', latest_user_text):
        state["current_intent"] = "seeking_support"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'seeking_support' (intake contact/decline pattern)")
        return state

    # If visitor gave a vague or uncertain response ("just looking", "not sure what I need"), route to qualification flow
    if is_vague_or_uncertain(latest_user_text):
        state["current_intent"] = "seeking_support"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'seeking_support' (vague/exploratory input)")
        return state

    # If visitor is asking a question about therapy types, services, or modalities, route to general_question (RAG QA)
    therapy_service_q_patterns = [
        r"\b(?:what kind of|what type of|what sort of)\s+(?:therapy|counseling|treatment|support|services?)\b",
        r"\b(?:what approaches|what methods|what modalities)\s+(?:do you|are)\b",
        r"\b(?:how do you treat|how do you approach|how does therapy work for)\b",
        r"\b(?:what are your|tell me about your)\s+(?:services|counseling services|therapy options|approaches)\b",
        r"\b(?:what do you do for|how do you help with)\s+[a-zA-Z\s]+\b",
    ]
    if any(re.search(pat, lower_user) for pat in therapy_service_q_patterns):
        state["current_intent"] = "general_question"
        if is_debug:
            _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'general_question' (therapy/services inquiry)")
        return state

    full_prompt = SAFETY_SYSTEM_PROMPT + "\n\n" + STYLE_SYSTEM_PROMPT + "\n\n" + INTENT_ROUTER_SYSTEM_PROMPT
    raw_response = call_llm(
        system_prompt=full_prompt,
        user_prompt=latest_user_text,
        messages=state["messages"][:-1],
        json_mode=True,
    )

    intent = "general_question"
    extracted_need = None
    try:
        parsed = json.loads(raw_response)
        intent = parsed.get("intent", "general_question")
        extracted_need = parsed.get("extracted_need")
    except Exception:
        pass

    state["current_intent"] = intent
    if is_debug:
        _safe_print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: '{intent}' (extracted_need: {extracted_need})")

    if extracted_need and not state.get("visitor_need") and has_concrete_concern(extracted_need):
        state["visitor_need"] = extracted_need

    return state


def rag_qa_node(state: AgentState) -> AgentState:
    """Node 3: Answers general questions using retrieved Qdrant knowledge base content."""
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    query = user_messages[-1]["content"]
    if is_debug:
        _safe_print(f"[rag_qa] Node invoked with query: '{query}'")

    # Check for AI identity or diagnostic questions
    lower_q = query.lower()
    is_identity_q = any(w in lower_q for w in ["real person", "are you a bot", "who are you", "human or ai"])
    is_diag_q = any(w in lower_q for w in ["what is wrong with me", "diagnose me", "tell me what's wrong"])

    context_str = ""
    results = []
    if search is not None:
        try:
            if is_debug:
                _safe_print(f"[rag_qa] Calling search('{query}', top_k=3)...")
            results = search(query, top_k=3)
            if is_debug:
                _safe_print(f"[rag_qa] search() returned {len(results)} chunks:")
                for idx, r in enumerate(results, 1):
                    preview = r.get("text", "").replace("\n", " ")[:65]
                    _safe_print(f"      [{idx}] {r.get('source_file')} | {r.get('section_title')} (score: {round(r.get('score', 0), 4)}) -> {preview}...")
            if results:
                context_blocks = []
                for idx, r in enumerate(results, 1):
                    context_blocks.append(
                        f"[{idx}] Source: {r.get('source_file')} | Section: {r.get('section_title')}\n{r.get('text')}"
                    )
                context_str = "\n\n".join(context_blocks)
        except Exception as e:
            if is_debug:
                _safe_print(f"[rag_qa] RAG search error: {e}")
    else:
        if is_debug:
            print("[rag_qa] search function is None!")

    visitor_name = state.get("name_collected") or state.get("qualification_info", {}).get("name")
    name_cue = f"VISITOR'S KNOWN NAME: {visitor_name} (use naturally once if appropriate, but do not force it)\n" if visitor_name else ""

    system_prompt = (
        SAFETY_SYSTEM_PROMPT + "\n\n" +
        STYLE_SYSTEM_PROMPT + "\n\n" +
        RAG_QA_SYSTEM_PROMPT + "\n\n" +
        name_cue +
        f"RETRIEVED KNOWLEDGE BASE CONTEXT:\n{context_str}\n"
    )

    response = call_llm(
        system_prompt=system_prompt,
        user_prompt=query,
        messages=state["messages"][:-1],
        temperature=0.4,
    )

    state["messages"].append({
        "role": "assistant",
        "content": response,
    })

    return state


def qualification_flow_node(state: AgentState) -> AgentState:
    """Node 4: Conversational intake gathering name, concern, and contact info naturally."""
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"] if user_messages else ""

    qual = state.get("qualification_info", {})

    # 1. Check if the visitor explicitly declined to provide contact info
    if _is_contact_declined(latest_user_text):
        state["contact_declined"] = True

    # 2. Check for contact details in this turn
    expecting_name = not bool(state.get("name_collected"))
    extracted = _extract_contact_info(latest_user_text, expecting_name=expecting_name)

    if extracted.get("email"):
        state["contact_collected"] = extracted["email"]
        qual["contact"] = extracted["email"]
    elif extracted.get("phone"):
        state["contact_collected"] = extracted["phone"]
        qual["contact"] = extracted["phone"]

    # 3. Check for name in this turn
    if extracted.get("name") and not state.get("name_collected"):
        state["name_collected"] = extracted["name"]
        qual["name"] = extracted["name"]

    # 4. Check for stated concern in this turn
    lower = latest_user_text.lower().strip()
    is_just_name = bool(extracted.get("name")) and not any(w in lower for w in ["help", "struggl", "fight", "anxiet", "depress", "therapy", "counsel", "partner", "stress", "work", "life", "need", "burnout", "panic", "grief", "sad", "loss"])
    is_just_greeting = lower in ["hi", "hello", "hey", "good morning", "good afternoon", "start"]
    is_just_contact = bool(extracted.get("email") or extracted.get("phone")) and len(latest_user_text.split()) <= 3
    is_decline_msg = _is_contact_declined(latest_user_text)
    is_vague_msg = is_vague_or_uncertain(latest_user_text)

    # Clean up any previously stored concern if it was actually vague or not a real concern
    if state.get("concern_collected"):
        if is_vague_or_uncertain(state["concern_collected"]) or not has_concrete_concern(state["concern_collected"]):
            state["concern_collected"] = None
            state["visitor_need"] = None

    if has_concrete_concern(latest_user_text) and not is_just_name and not is_just_greeting and not is_just_contact and not is_decline_msg and not is_vague_msg:
        state["concern_collected"] = latest_user_text
        state["visitor_need"] = latest_user_text

    # Extract format preferences if mentioned
    if re.search(r'\b(in-person|in person)\b', lower):
        qual["preferences"] = "In-person sessions"
    elif re.search(r'\b(video|telehealth|online|remote)\b', lower):
        qual["preferences"] = "Telehealth video sessions"

    if re.search(r'\b(partner|husband|wife|marriage|couples|both of us|together)\b', lower):
        qual["who_is_it_for"] = "Couples / Partner"
    elif re.search(r'\b(teen|adolescent|son|daughter|child|kid)\b', lower):
        qual["who_is_it_for"] = "Teen / Adolescent"
    elif re.search(r'\b(family|parents)\b', lower):
        qual["who_is_it_for"] = "Family"
    elif not qual.get("who_is_it_for") and state.get("concern_collected"):
        qual["who_is_it_for"] = "Individual"

    state["qualification_info"] = qual

    # 5. Determine the natural stage directive
    name = state.get("name_collected")
    concern = state.get("concern_collected")
    contact = state.get("contact_collected")
    declined = state.get("contact_declined", False)

    if is_vague_msg or (not concern and is_vague_or_uncertain(latest_user_text)):
        name_str = f", {name}" if name else ""
        stage_directive = (
            f"STAGE: VAGUE OR UNCERTAIN VISITOR (OFFER CONCRETE OPTIONS MENU).\n"
            f"The visitor{name_str} said: '{latest_user_text}'.\n"
            f"They are exploring, browsing, or not sure what they need, and have NOT shared a specific clinical concern yet.\n"
            f"CRITICAL RULES:\n"
            f"- Do NOT ask for their email address or phone number.\n"
            f"- Do NOT suggest specific therapists by name.\n"
            f"- Respond with warm reassurance (e.g. 'No worries at all, happy to help you figure that out!').\n"
            f"- Offer a clear, friendly menu of 3 concrete next steps:\n"
            f"  1. Schedule an initial consultation with one of our counselors\n"
            f"  2. Ask about something specific (like insurance, fees, or therapy approaches)\n"
            f"  3. Check our office hours and counseling services\n"
            f"Ask which of those sounds most helpful to explore right now.\n"
            f"Keep it to 2 to 3 short sentences. Do NOT use markdown asterisks or em dashes."
        )
    elif not name and not contact and not concern:
        if any(re.search(pat, lower) for pat in MATCHING_META_PATTERNS):
            stage_directive = (
                "STAGE: GREETING & INITIAL REASON FOR THERAPIST SEARCH.\n"
                "The visitor explicitly asked for help finding the right therapist ('Help me find the right therapist'), but their name and situation are NOT known yet.\n"
                "Warmly introduce yourself as Ellen, MindBridge's AI assistant.\n"
                "Affirm that you'd love to help connect them with the right counselor on our team.\n"
                "Gently ask for their name and what they are hoping to work through (such as anxiety, couples counseling, or life transitions) so you can suggest the best match.\n"
                "Keep it to 2 short sentences. Do NOT use markdown asterisks or em dashes. Keep it light, warm, and friendly."
            )
        else:
            stage_directive = (
                "STAGE: GREETING & NAME COLLECTION.\n"
                "The visitor's name is NOT known yet.\n"
                "Give a warm, gentle welcome introducing yourself as Ellen, MindBridge's AI assistant (e.g. 'Hey, I'm Ellen, MindBridge's AI assistant').\n"
                "CRITICAL: Do NOT use clinical or administrative words like 'intake assistant' or 'intake coordinator'.\n"
                "Be calm, inviting, and friendly, appropriate for someone who may feel nervous reaching out.\n"
                "Ask for their name in a friendly, gentle way in 1 to 2 short sentences.\n"
                "Example spirit: 'Hi there, welcome to MindBridge Wellness! I'm Ellen, MindBridge's AI assistant here to help you find the right support. What can I call you?'\n"
                "Do NOT use markdown asterisks or em dashes. Keep it light, warm, and friendly."
            )
    elif not name and (contact or concern):
        contact_note = f"They already provided contact info: {contact}. " if contact else ""
        stage_directive = (
            f"STAGE: NAME COLLECTION.\n"
            f"The visitor shared their situation ('{concern}'). {contact_note}Their name is NOT known yet.\n"
            f"Acknowledge what they shared with brief empathy, and ask for their name.\n"
            f"Do NOT ask for contact info if they already provided it.\n"
            f"Keep it to 1 to 2 short sentences. Do NOT use markdown asterisks or em dashes."
        )
    elif name and not concern:
        stage_directive = (
            f"STAGE: ORIENTATION & REASON FOR VISIT.\n"
            f"The visitor's name is {name}. Their concern/goal is NOT known yet.\n"
            f"Warmly acknowledge {name} by name. Plant the seed of how you can help: "
            f"finding the right type of support, booking a consultation, or answering questions about our services (whatever is most helpful for them). "
            f"Then gently ask what brings them in to MindBridge Wellness today.\n"
            f"Example spirit: 'Nice to meet you, {name}! I can help you find the right type of support, book a consultation, or answer questions about our services, whatever's most helpful. What brings you in today?'\n"
            f"Keep it to 2 short sentences. Do NOT use markdown asterisks or em dashes."
        )
    elif name and concern and not contact and not declined:
        stage_directive = (
            f"STAGE: CONTACT INFO COLLECTION.\n"
            f"Visitor {name} shared their concern: '{concern}'.\n"
            f"Respond with brief, genuine human empathy/warmth (1 short sentence), then naturally ask for their email address or phone number so our care team can follow up with counselor availability.\n"
            f"Example spirit: 'I would love to make sure our team can follow up with you. Can I grab your email or phone number?'\n"
            f"Keep it to 1 to 3 short sentences total. Do NOT use markdown asterisks or em dashes."
        )
    elif declined:
        stage_directive = (
            f"STAGE: CONTACT DECLINED.\n"
            f"The visitor declined to provide contact info.\n"
            f"Acknowledge this gracefully without pushing (e.g. 'No problem at all, we can keep chatting right here without it.').\n"
            f"Do NOT ask for contact info again.\n"
            f"Ask if they would like to hear about our therapist specialties or whether they prefer in-person or video visits.\n"
            f"Keep it to 1 to 2 short sentences total. Do NOT use markdown asterisks or em dashes."
        )
    else:
        stage_directive = (
            f"STAGE: INTAKE COMPLETE.\n"
            f"Name ({name}), concern ({concern}), and contact ({contact}) have all been collected.\n"
            f"Warmly thank {name}, confirm their contact details were noted for the intake coordinator, and ask if they would like to hear a therapist recommendation for their needs.\n"
            f"Keep it to 1 to 3 short sentences total. Do NOT use markdown asterisks or em dashes."
        )

    full_prompt = (
        SAFETY_SYSTEM_PROMPT + "\n\n" +
        STYLE_SYSTEM_PROMPT + "\n\n" +
        QUALIFICATION_SYSTEM_PROMPT + "\n\n" +
        f"CURRENT INTAKE STATUS:\n"
        f"- Name: {name or 'Not collected yet'}\n"
        f"- Stated Concern: {concern or 'Not collected yet'}\n"
        f"- Contact Info: {contact or ('Declined by visitor' if declined else 'Not collected yet')}\n\n"
        f"STAGE DIRECTIVE:\n{stage_directive}"
    )

    response = call_llm(
        system_prompt=full_prompt,
        user_prompt=latest_user_text,
        messages=state["messages"][:-1],
        temperature=0.5,
    )

    state["messages"].append({
        "role": "assistant",
        "content": response,
    })

    return state


def therapist_matching_node(state: AgentState) -> AgentState:
    """Node 5: Suggests matching therapist profiles based on stated needs, with mandatory clinical caveat."""
    visitor_need = state.get("concern_collected") or state.get("visitor_need")
    visitor_name = state.get("name_collected") or state.get("qualification_info", {}).get("name")

    # MINIMUM INFORMATION GATE:
    # If called without a concrete, specific concern, do NOT name therapists.
    # Fall back to asking for their concern or offering the concrete options menu.
    if not has_concrete_concern(visitor_need):
        prefix = f"Nice to meet you, {visitor_name}! " if visitor_name else ""
        fallback_msg = (
            f"{prefix}I'd love to help connect you with the right counselor on our team. "
            f"To suggest the best match, could you share a little about what you're hoping to work through (such as anxiety, couples counseling, or life transitions)?<br><br>"
            f"Or if you prefer, we can schedule an initial consultation, answer questions about our services, or check our current office hours."
        )
        state["messages"].append({
            "role": "assistant",
            "content": fallback_msg,
        })
        return state

    # Build enriched search query to emphasize specific clinical domain (BUG 2(b) FIX)
    therapy_hint = ""
    lower_need = (visitor_need or "").lower()
    who_for = state.get("qualification_info", {}).get("who_is_it_for", "")
    if any(w in lower_need for w in ["partner", "husband", "wife", "marriage", "couples", "fight", "fighting", "relationship", "communication", "trust", "conflict", "divorce", "infidelity"]) or "Couples" in who_for:
        therapy_hint = "couples therapy marriage counseling relationship conflict communication Marcus Reyes"
    elif any(w in lower_need for w in ["teen", "adolescent", "child", "son", "daughter", "school"]) or "Teen" in who_for:
        therapy_hint = "teen adolescent counseling Jordan Whitfield"
    elif any(w in lower_need for w in ["grief", "loss", "bereave", "burnout", "young adult"]):
        therapy_hint = "grief loss stress burnout Priya Nair"
    elif any(w in lower_need for w in ["anxiety", "panic", "worry", "trauma", "ptsd", "work stress", "stress"]):
        therapy_hint = "anxiety trauma PTSD work stress Dr Elena Marsh"

    search_query = f"therapist specialties {therapy_hint} {visitor_need}".strip()
    therapist_context = ""
    if search is not None:
        try:
            results = search(search_query, top_k=5)
            therapist_context = "\n\n".join([r.get("text", "") for r in results])
        except Exception as e:
            _safe_print(f"[Warning] Therapist search error: {e}")

    name_cue = f"VISITOR'S FIRST NAME: {visitor_name}\n" if visitor_name else ""

    matching_instructions = (
        "CRITICAL MATCHING INSTRUCTIONS:\n"
        "1. Match the visitor's stated concern to the specific specialty keywords in each retrieved therapist profile.\n"
        "2. Prefer the therapist whose specialty most directly and specifically addresses the visitor's situation:\n"
        "   - For couples, marriage, relationship conflict, trust, or partner communication, recommend Marcus Reyes, LMFT (NOT Dr. Elena Marsh).\n"
        "   - For anxiety, panic, trauma, PTSD, or structured CBT/EMDR, recommend Dr. Elena Marsh, PsyD.\n"
        "   - For grief, loss, young adult transitions, or mindfulness/burnout, recommend Priya Nair, LCSW.\n"
        "   - For teens, adolescents, or parenting teens, recommend Jordan Whitfield, LPC.\n"
        "3. Name the recommended therapist clearly with their full title/credentials, and explain warmly in 1-2 sentences why their specific background matches what the visitor shared."
    )

    full_prompt = (
        SAFETY_SYSTEM_PROMPT + "\n\n" +
        STYLE_SYSTEM_PROMPT + "\n\n" +
        THERAPIST_MATCHING_SYSTEM_PROMPT + "\n\n" +
        matching_instructions + "\n\n" +
        name_cue +
        f"VISITOR STATED NEED: {visitor_need}\n\n" +
        f"RETRIEVED THERAPIST PROFILES:\n{therapist_context}"
    )

    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"] if user_messages else ""

    response = call_llm(
        system_prompt=full_prompt,
        user_prompt=latest_user_text,
        messages=state["messages"][:-1],
        temperature=0.4,
    )

    # Strictly enforce the mandatory clinical team disclaimer with HTML formatting
    mandatory_caveat = (
        "<br><br><b>Please note:</b> Final therapist assignment is always made by our practice's clinical team "
        "based on clinical fit and therapist availability. This suggestion is a starting point for our team to review with you."
    )
    if "final therapist assignment is always made" not in response.lower():
        response = f"{response}{mandatory_caveat}"

    state["messages"].append({
        "role": "assistant",
        "content": response,
    })

    # Track suggested therapist name if identifiable
    norm_resp = re.sub(r'[\s\u2000-\u200f\u2028-\u202f]+', ' ', response)
    for name in ["Dr. Elena Marsh", "Marcus Reyes", "Priya Nair", "Jordan Whitfield"]:
        if name in norm_resp or name in response:
            state["suggested_therapist"] = name
            break

    return state


def scheduling_node(state: AgentState) -> AgentState:
    """Node 6: Conversational scheduling requesting date/time and logging to Google Sheets & local JSON."""
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"] if user_messages else ""

    state["scheduling_requested"] = True

    # 1. Extract contact info if present in this turn
    extracted_contact = _extract_contact_info(latest_user_text, expecting_name=not bool(state.get("name_collected")))
    qual = state.get("qualification_info", {})
    if extracted_contact.get("email"):
        state["contact_collected"] = extracted_contact["email"]
        qual["contact"] = extracted_contact["email"]
    elif extracted_contact.get("phone"):
        state["contact_collected"] = extracted_contact["phone"]
        qual["contact"] = extracted_contact["phone"]
    if extracted_contact.get("name") and not state.get("name_collected"):
        state["name_collected"] = extracted_contact["name"]
        qual["name"] = extracted_contact["name"]
    state["qualification_info"] = qual

    name = state.get("name_collected") or qual.get("name")
    contact = state.get("contact_collected") or qual.get("contact")

    # Detect therapist name if mentioned in this turn or state
    therapist_names = {
        "marcus": "Marcus Reyes",
        "reyes": "Marcus Reyes",
        "elena": "Dr. Elena Marsh",
        "marsh": "Dr. Elena Marsh",
        "priya": "Priya Nair",
        "nair": "Priya Nair",
        "jordan": "Jordan Whitfield",
        "whitfield": "Jordan Whitfield",
    }
    for key, full_name in therapist_names.items():
        if key in latest_user_text.lower():
            state["suggested_therapist"] = full_name
            break

    therapist = state.get("suggested_therapist")
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    # 2. Date and time resolution with real-time awareness
    current_dt = get_current_datetime()
    current_date_str = format_date_display(current_dt.date())

    clarification_mode = state.get("scheduling_clarification")
    pending_candidate_date = state.get("pending_candidate_date")

    date_res = resolve_scheduling_input(
        latest_user_text,
        current_dt=current_dt,
        pending_candidate_date=pending_candidate_date,
        clarification_mode=clarification_mode,
    )

    if is_debug:
        _safe_print(f"[scheduling] User message: '{latest_user_text}'")
        _safe_print(f"[scheduling] Date resolution: status={date_res['status']}, resolved={date_res.get('resolved_full')}, pending={pending_candidate_date}")

    # Process date resolution outcome
    if date_res["status"] == "confirmed":
        resolved_timing = date_res.get("resolved_full") or date_res.get("resolved_date")
        state["preferred_date"] = resolved_timing
        state["preferred_time"] = resolved_timing
        state["scheduling_clarification"] = None
        state["pending_candidate_date"] = None
    elif date_res["status"] == "needs_clarification_ambiguous":
        state["scheduling_clarification"] = "confirm_day"
        state["pending_candidate_date"] = date_res.get("resolved_full") or date_res.get("resolved_date")
    elif date_res["status"] == "rejected_past":
        state["scheduling_clarification"] = None
        state["pending_candidate_date"] = None
        # Do not store past date as preferred_date

    preferred_timing = state.get("preferred_date") or state.get("preferred_time")

    if is_debug:
        _safe_print(f"[scheduling] Resolved preferred_timing: '{preferred_timing}'")
        _safe_print(f"[scheduling] Contact: '{contact}', Name: '{name}'")

    # 3. Determine stage directive for Ellen
    if date_res["status"] == "rejected_past":
        # Specific date in the past
        if not name:
            stage_directive = (
                f"STAGE: REJECT PAST DATE & ASK UPCOMING DATE + NAME.\n"
                f"Today is {current_date_str}. The visitor asked for a date that has already passed ('{latest_user_text}').\n"
                f"Their name is NOT known yet.\n"
                f"Kindly clarify that this date has already passed, and ask what upcoming date and time works best for them.\n"
                f"Also ask for their name so you can get them set up properly.\n"
                f"CRITICAL: Do NOT accept or log this past date. Keep response to 1 to 2 short sentences."
            )
        else:
            stage_directive = (
                f"STAGE: REJECT PAST DATE & ASK UPCOMING DATE.\n"
                f"Today is {current_date_str}. The visitor ({name}) asked for a date that has already passed ('{latest_user_text}').\n"
                f"Kindly clarify that this date has already passed, and ask {name} for an upcoming date and time that works best for them.\n"
                f"CRITICAL: Do NOT accept or log this past date. Keep response to 1 to 2 short sentences."
            )
    elif date_res["status"] == "needs_clarification_ambiguous":
        # Ambiguous relative weekday requiring ONE brief confirmation
        suggested = date_res.get("suggested_confirmation") or "the upcoming date"
        if not name:
            stage_directive = (
                f"STAGE: CLARIFY AMBIGUOUS DAY & ASK NAME.\n"
                f"Today is {current_date_str}. The visitor mentioned a relative day without a specific date ('{latest_user_text}').\n"
                f"Their name is NOT known yet.\n"
                f"Ask ONE brief clarifying follow-up to confirm the exact date: 'Just to confirm, are you looking at {suggested}?'\n"
                f"Also ask for their name.\n"
                f"CRITICAL: Do NOT finalize or log the appointment yet. Keep response to 1 to 2 short sentences."
            )
        else:
            stage_directive = (
                f"STAGE: CLARIFY AMBIGUOUS DAY.\n"
                f"Today is {current_date_str}. The visitor ({name}) mentioned a relative day without a specific date ('{latest_user_text}').\n"
                f"Ask ONE brief clarifying follow-up to confirm the exact date: 'Just to confirm, are you looking at {suggested}?'\n"
                f"CRITICAL: Do NOT finalize or log the appointment yet. Keep response to 1 short sentence."
            )
    elif not name and not preferred_timing:
        # Neither name nor timing is known (ISSUE 1 FIX)
        therapist_note = f" with {therapist}" if therapist else ""
        stage_directive = (
            f"STAGE: ASK VISITOR NAME AND PREFERRED DATE/TIME.\n"
            f"The visitor is looking to book a consultation{therapist_note}, but NEITHER their name nor their preferred date/time has been shared yet.\n"
            f"Warmly welcome their request and naturally ask for BOTH their name AND what day and time tends to work best for them:\n"
            f"e.g., 'I\\'d love to help you set up a consultation{therapist_note}! What is your name, and what day and time tends to work best for you?'\n"
            f"Keep it warm, natural, and conversational in 1 to 2 short sentences.\n"
            f"CRITICAL: Do NOT assume a name or finalize any booking."
        )
    elif name and not preferred_timing:
        # Name is known, timing is not
        therapist_note = f" with {therapist}" if therapist else ""
        stage_directive = (
            f"STAGE: ASK PREFERRED DATE AND TIME.\n"
            f"The visitor's name is {name}. They are ready to schedule{therapist_note}, but haven't shared their preferred day/time yet.\n"
            f"Ask casually and conversationally what date and time generally works best for {name}:\n"
            f"e.g., 'What day and time tends to work best for you, {name}?'\n"
            f"Keep it casual and conversational, not a rigid form in 1 to 2 short sentences."
        )
    elif preferred_timing and not name:
        # Timing known, name NOT known
        stage_directive = (
            f"STAGE: COLLECT NAME AND CONTACT INFO.\n"
            f"The visitor stated their preferred timing: '{preferred_timing}'.\n"
            f"Their name and contact info (email or phone) are NOT known yet.\n"
            f"Acknowledge that you noted '{preferred_timing}' as their preference.\n"
            f"Ask for their name and the best email address or phone number for our care team to confirm with them:\n"
            f"e.g., 'Got it, I\\'ve noted {preferred_timing}. Could I get your name and the best email or phone number for our team to follow up with you?'\n"
            f"CRITICAL: Do NOT say the appointment is booked or confirmed. It is a request pending confirmation.\n"
            f"Keep response to 1 to 2 short sentences."
        )
    elif preferred_timing and name and not contact:
        # Timing and name known, contact NOT known
        stage_directive = (
            f"STAGE: COLLECT CONTACT INFO FOR CONFIRMATION.\n"
            f"Visitor Name: {name}\n"
            f"Preferred Timing: '{preferred_timing}'.\n"
            f"Their contact info (email or phone) is NOT known yet.\n"
            f"Acknowledge that you noted '{preferred_timing}' for {name}.\n"
            f"Ask specifically for their email address or phone number so our care team can confirm counselor availability with them:\n"
            f"e.g., 'What is the best email or phone number for our team to confirm that with you, {name}?'\n"
            f"CRITICAL: Do NOT say the appointment is booked or confirmed. It is a request pending confirmation.\n"
            f"Keep response to 1 to 2 short sentences."
        )
    else:
        # ALL THREE (name, contact, timing) ARE PRESENT! (ISSUE 1 & 2 SAFEGUARD)
        if not state.get("scheduling_request_logged", False):
            session_id = state.get("session_id") or "Not provided"
            req_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "name": name,
                "contact": contact,
                "preferred_date": preferred_timing,
                "preferred_time": preferred_timing,
                "matched_therapist": therapist or "None assigned yet",
                "session_id": session_id,
                "status": "Pending confirmation",
            }
            append_scheduling_request(req_data)
            state["scheduling_request_logged"] = True

        stage_directive = (
            f"STAGE: SCHEDULING REQUEST NOTED (PENDING HUMAN CONFIRMATION).\n"
            f"Visitor Name: {name}\n"
            f"Preferred Timing: {preferred_timing}\n"
            f"Contact Info: {contact}\n"
            f"Matched Therapist: {therapist or 'Practice clinical team'}\n"
            f"Respond warmly and honestly in this exact spirit:\n"
            f"'Got it, I\\'ve noted {preferred_timing} as your preference for {name}. Our team will review counselor availability and reach out to you at {contact} shortly to confirm.'\n"
            f"MANDATORY CLINICAL & ETHICAL RULE:\n"
            f"NEVER say the appointment is 'booked', 'confirmed', or 'scheduled'.\n"
            f"It is strictly a REQUEST pending human confirmation.\n"
            f"Keep response to 1 to 2 short, reassuring sentences."
        )

    full_prompt = (
        SAFETY_SYSTEM_PROMPT + "\n\n" +
        STYLE_SYSTEM_PROMPT + "\n\n" +
        SCHEDULING_SYSTEM_PROMPT + "\n\n" +
        f"CURRENT DATE AND TIME: {current_date_str} (Real-world current date)\n\n" +
        f"CURRENT SCHEDULING STATE:\n"
        f"- Name: {name or 'Not collected yet'}\n"
        f"- Preferred Timing: {preferred_timing or 'Not collected yet'}\n"
        f"- Contact Info: {contact or 'Not collected yet'}\n"
        f"- Matched Therapist: {therapist or 'None'}\n\n"
        f"STAGE DIRECTIVE:\n{stage_directive}"
    )

    response = call_llm(
        system_prompt=full_prompt,
        user_prompt=latest_user_text,
        messages=state["messages"][:-1],
        temperature=0.3,
    )

    # Post-generation guard: strictly prevent forbidden booking claims
    forbidden_terms = [
        (r"\byou(?:'re| are) booked\b", "I've noted your request"),
        (r"\bhave booked\b", "have noted your request"),
        (r"\bhas been booked\b", "has been noted as a request"),
        (r"\bappointment is booked\b", "scheduling request is noted"),
        (r"\bappointment is confirmed\b", "request has been noted and our team will confirm"),
        (r"\bconfirmed your appointment\b", "noted your preferred time for our team to confirm"),
        (r"\byou(?:'re| are) confirmed\b", "your request is noted"),
        (r"\bis scheduled\b", "has been noted as a request"),
        (r"\bare scheduled\b", "are in line for our team to confirm"),
    ]
    for pattern, replacement in forbidden_terms:
        response = re.sub(pattern, replacement, response, flags=re.IGNORECASE)

    state["messages"].append({
        "role": "assistant",
        "content": response,
    })

    return state


scheduling_stub_node = scheduling_node


def lead_capture_node(state: AgentState) -> AgentState:
    """Node 7: Dispatches lead email/notification when name, contact info and need are available."""
    qual = state.get("qualification_info", {})
    name = state.get("name_collected") or qual.get("name")
    contact = state.get("contact_collected") or qual.get("contact")
    need = state.get("concern_collected") or state.get("visitor_need")
    session_id = state.get("session_id") or "Not provided"

    if name and contact and need:
        if not state.get("lead_captured", False):
            send_lead_email(
                name=name,
                contact=contact,
                need=need,
                suggested_therapist=state.get("suggested_therapist"),
                qualification_info=qual,
                session_id=session_id,
                source="chat",
            )
            state["lead_captured"] = True
        elif state.get("suggested_therapist") and not state.get("lead_therapist_notified", False):
            send_lead_email(
                name=name,
                contact=contact,
                need=need,
                suggested_therapist=state.get("suggested_therapist"),
                qualification_info=qual,
                session_id=session_id,
                source="chat",
            )
            state["lead_therapist_notified"] = True

    return state


def human_handoff_node(state: AgentState) -> AgentState:
    """Node 8: Warm transition to human clinical/administrative staff."""
    state["handoff_requested"] = True
    reason = state.get("handoff_reason") or "visitor_requested_human"
    session_id = state.get("session_id") or "Not provided"

    log_handoff(
        reason=reason,
        conversation_history=state["messages"],
        lead_info=state.get("qualification_info", {}),
        session_id=session_id,
    )

    handoff_message = (
        "I would be glad to connect you with a member of our team! Our practice coordinator is available "
        "Monday through Saturday to help with scheduling, billing questions, or clinical matching.<br><br>"
        "You can reach our office directly at <b>(555) 349-2810</b> or by email at <b>care@mindbridgewellness.demo</b>.<br><br>"
        "If you have already shared your contact information, a team member will follow up with you promptly!"
    )

    state["messages"].append({
        "role": "assistant",
        "content": handoff_message,
    })

    return state
