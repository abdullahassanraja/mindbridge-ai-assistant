# nodes.py
# Node implementations for MindBridge Wellness LangGraph conversational agent.

import json
import os
import re
import sys
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
    print(f"[Warning] Could not import search from ingestion.ingest: {e}")
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
)
from leads import send_lead_email, log_handoff
from llm import call_llm


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
    # Affirmations & negatives
    "yes", "no", "sure", "ok", "okay", "yep", "nope", "please", "thanks", "thank", "you",
    # Verbs & states
    "struggling", "dealing", "feeling", "looking", "seeking", "hoping", "trying",
    "having", "going", "reaching", "calling", "writing", "wondering", "asking",
    "anxious", "depressed", "stressed", "overwhelmed", "hurt", "sad", "scared", "afraid",
    "tired", "exhausted", "lost", "angry", "fine", "bad", "well", "better",
    "interested", "ready", "new", "here", "just", "someone", "anyone", "person",
    "help", "therapy", "counseling", "support", "appointment", "consultation",
    "partner", "husband", "wife", "son", "daughter", "friend", "family", "doctor",
    "with", "for", "about", "from", "at", "in", "to", "on", "into", "and", "or", "but"
}


def has_concrete_concern(text: Optional[str]) -> bool:
    """Check if the text contains a concrete, specific situation or clinical need."""
    if not text:
        return False
    lower = text.lower().strip()
    if is_vague_or_uncertain(lower):
        return False
    if any(k in lower for k in CLINICAL_CONCERN_KEYWORDS):
        return True
    words = [w for w in re.findall(r'[a-z]+', lower) if w not in NON_NAME_WORDS]
    if len(words) >= 3 and not is_vague_or_uncertain(lower):
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

    # 1. Explicit name introductions: "my name is X", "call me X", "name is X", "this is X"
    explicit_name = re.search(r"\b(?:my name is|call me|name is|this is)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", text, re.IGNORECASE)
    if explicit_name:
        candidate = explicit_name.group(1).strip()
        words = candidate.split()
        if all(w.lower() not in NON_NAME_WORDS for w in words):
            found["name"] = candidate.title()

    # 2. "I'm X" or "I am X" (only if NOT followed by verb/adjective/preposition)
    if not found.get("name"):
        iam_match = re.search(r"\b(?:i am|i'm)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", text, re.IGNORECASE)
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
        # Fallback keyword scan if JSON parse fails
        crisis_keywords = ["suicide", "kill myself", "end my life", "end it all", "die", "harm myself", "cut myself", "overdose"]
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


def intent_router_node(state: AgentState) -> AgentState:
    """Node 2: Classify visitor intent and route downstream."""
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"]

    # Detect user frustration or explicit human request
    frustration_patterns = ["stop repeating", "talk to human", "real person", "speak to someone", "this is unhelpful", "you don't understand"]
    if any(p in latest_user_text.lower() for p in frustration_patterns) and "are you a real person" not in latest_user_text.lower():
        state["current_intent"] = "wants_human"
        if is_debug:
            print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'wants_human' (frustration/human pattern matched)")
        return state

    # If visitor is in active intake qualification and provided a name, decline, or contact info
    if _is_contact_declined(latest_user_text) or "@" in latest_user_text or re.search(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', latest_user_text):
        state["current_intent"] = "seeking_support"
        if is_debug:
            print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'seeking_support' (intake contact/decline pattern)")
        return state

    # If visitor gave a vague or uncertain response ("just looking", "not sure what I need"), route to qualification flow
    if is_vague_or_uncertain(latest_user_text):
        state["current_intent"] = "seeking_support"
        if is_debug:
            print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: 'seeking_support' (vague/exploratory input)")
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
        print(f"[intent_router] Message: '{latest_user_text}' -> Classified Intent: '{intent}' (extracted_need: {extracted_need})")

    if extracted_need and not state.get("visitor_need") and has_concrete_concern(extracted_need):
        state["visitor_need"] = extracted_need

    return state


def rag_qa_node(state: AgentState) -> AgentState:
    """Node 3: Answers general questions using retrieved Qdrant knowledge base content."""
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    query = user_messages[-1]["content"]
    if is_debug:
        print(f"[rag_qa] Node invoked with query: '{query}'")

    # Check for AI identity or diagnostic questions
    lower_q = query.lower()
    is_identity_q = any(w in lower_q for w in ["real person", "are you a bot", "who are you", "human or ai"])
    is_diag_q = any(w in lower_q for w in ["what is wrong with me", "diagnose me", "tell me what's wrong"])

    context_str = ""
    results = []
    if search is not None:
        try:
            if is_debug:
                print(f"[rag_qa] Calling search('{query}', top_k=3)...")
            results = search(query, top_k=3)
            if is_debug:
                print(f"[rag_qa] search() returned {len(results)} chunks:")
                for idx, r in enumerate(results, 1):
                    preview = r.get("text", "").replace("\n", " ")[:65]
                    print(f"      [{idx}] {r.get('source_file')} | {r.get('section_title')} (score: {round(r.get('score', 0), 4)}) -> {preview}...")
            if results:
                context_blocks = []
                for idx, r in enumerate(results, 1):
                    context_blocks.append(
                        f"[{idx}] Source: {r.get('source_file')} | Section: {r.get('section_title')}\n{r.get('text')}"
                    )
                context_str = "\n\n".join(context_blocks)
        except Exception as e:
            if is_debug:
                print(f"[rag_qa] RAG search error: {e}")
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
    is_just_name = bool(extracted.get("name")) and len(latest_user_text.split()) <= 3 and not any(w in lower for w in ["help", "struggl", "fight", "anxiet", "depress", "therapy", "counsel", "partner", "stress", "work", "life", "need"])
    is_just_greeting = lower in ["hi", "hello", "hey", "good morning", "good afternoon", "start"]
    is_just_contact = bool(extracted.get("email") or extracted.get("phone")) and len(latest_user_text.split()) <= 3
    is_decline_msg = _is_contact_declined(latest_user_text)
    is_vague_msg = is_vague_or_uncertain(latest_user_text)

    # Clean up any previously stored concern if it was actually vague
    if state.get("concern_collected") and is_vague_or_uncertain(state["concern_collected"]):
        state["concern_collected"] = None
        state["visitor_need"] = None

    if not state.get("concern_collected") and not is_just_name and not is_just_greeting and not is_just_contact and not is_decline_msg and not is_vague_msg:
        if has_concrete_concern(latest_user_text):
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

    therapist_context = ""
    if search is not None:
        try:
            results = search(f"therapist specialties for {visitor_need}", top_k=3)
            therapist_context = "\n\n".join([r.get("text", "") for r in results])
        except Exception as e:
            print(f"[Warning] Therapist search error: {e}")

    name_cue = f"VISITOR'S FIRST NAME: {visitor_name}\n" if visitor_name else ""

    full_prompt = (
        SAFETY_SYSTEM_PROMPT + "\n\n" +
        STYLE_SYSTEM_PROMPT + "\n\n" +
        THERAPIST_MATCHING_SYSTEM_PROMPT + "\n\n" +
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
    for name in ["Dr. Elena Marsh", "Marcus Reyes", "Priya Nair", "Jordan Whitfield"]:
        if name in response:
            state["suggested_therapist"] = name
            break

    return state


def scheduling_stub_node(state: AgentState) -> AgentState:
    """Node 6: Handles appointment requests with a clear CTA and modular structure for future booking APIs."""
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"] if user_messages else ""

    extracted = _extract_contact_info(latest_user_text)
    qual = state.get("qualification_info", {})
    if "email" in extracted:
        state["contact_collected"] = extracted["email"]
        qual["contact"] = extracted["email"]
    if "phone" in extracted:
        state["contact_collected"] = extracted["phone"]
        qual["contact"] = extracted["phone"]
    if "name" in extracted and not state.get("name_collected"):
        state["name_collected"] = extracted["name"]
        qual["name"] = extracted["name"]
    state["qualification_info"] = qual

    scheduling_message = (
        "We would love to help you get scheduled! You can request an initial consultation online anytime at "
        "<b>mindbridgewellness.demo/schedule</b>.<br><br>"
        "Our administrative team is also available Monday through Saturday. If you share your preferred days and times, "
        "our care coordinator will confirm available openings with you directly."
    )

    state["messages"].append({
        "role": "assistant",
        "content": scheduling_message,
    })

    return state


def lead_capture_node(state: AgentState) -> AgentState:
    """Node 7: Dispatches lead email/notification when name, contact info and need are available."""
    qual = state.get("qualification_info", {})
    name = state.get("name_collected") or qual.get("name")
    contact = state.get("contact_collected") or qual.get("contact")
    need = state.get("concern_collected") or state.get("visitor_need")

    if name and contact and need:
        if not state.get("lead_captured", False):
            send_lead_email(
                name=name,
                contact=contact,
                need=need,
                suggested_therapist=state.get("suggested_therapist"),
                qualification_info=qual,
            )
            state["lead_captured"] = True
        elif state.get("suggested_therapist") and not state.get("lead_therapist_notified", False):
            send_lead_email(
                name=name,
                contact=contact,
                need=need,
                suggested_therapist=state.get("suggested_therapist"),
                qualification_info=qual,
            )
            state["lead_therapist_notified"] = True

    return state


def human_handoff_node(state: AgentState) -> AgentState:
    """Node 8: Warm transition to human clinical/administrative staff."""
    state["handoff_requested"] = True
    reason = state.get("handoff_reason") or "visitor_requested_human"

    log_handoff(
        reason=reason,
        conversation_history=state["messages"],
        lead_info=state.get("qualification_info", {}),
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
