# llm.py
# Groq LLM integration with dynamic model selection and mock/stub fallback.

import json
import os
import re
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def get_groq_model() -> str:
    """Return configured Groq model from environment or fallback default."""
    return os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)


def get_groq_api_key() -> Optional[str]:
    """Return Groq API key if configured and not a placeholder."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key or key.startswith("gsk_your") or key == "your_api_key_here":
        return None
    return key


_groq_client = None


def get_groq_client():
    """Return Groq client if API key is present."""
    global _groq_client
    api_key = get_groq_api_key()
    if not api_key:
        return None
    if _groq_client is None:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=api_key, max_retries=0)
        except Exception as e:
            _safe_print(f"[Warning] Could not initialize Groq client: {e}")
            _groq_client = None
    return _groq_client


def _mock_llm_response(
    system_prompt: str,
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    json_mode: bool = False,
) -> str:
    """High-fidelity local heuristic fallback when Groq API key is absent."""
    user_lower = user_prompt.lower()
    combined_lower = user_lower
    if messages:
        combined_lower = " ".join([m.get("content", "").lower() for m in messages]) + " " + user_lower

    # 1. Crisis Detection stub
    if "is_crisis" in system_prompt or "clinical safety classifier" in system_prompt.lower():
        crisis_patterns = [
            r"\b(kill myself|end my life|end it all|want to die|suicid|better off dead)\b",
            r"\b(harm myself|hurt myself|cut myself|cutting|overdose)\b",
            r"\b(kill someone|hurt others|harm others)\b",
            r"\b(emergency|crisis|take all my pills)\b",
            r"\b(point in going on|no reason to live|not worth living|give up on life)\b",
        ]
        is_crisis = any(re.search(pat, user_lower) for pat in crisis_patterns)
        if is_crisis:
            return json.dumps({
                "is_crisis": True,
                "reason": "Explicit crisis / self-harm indicator detected in user text",
            })
        return json.dumps({
            "is_crisis": False,
            "reason": "No acute crisis language detected",
        })

    # 1b. Scope Classifier stub
    if "scope classifier" in system_prompt.lower() or "clearly off-topic" in system_prompt.lower():
        off_topic_words = ["python", "code", "programming", "capital of", "poem", "poetry", "weather", "ignore previous", "homework", "sum two numbers"]
        if any(w in user_lower for w in off_topic_words):
            return json.dumps({
                "is_off_topic": True,
                "category": "other",
                "reason": "Off-topic query detected in mock LLM",
            })
        return json.dumps({
            "is_off_topic": False,
            "category": None,
            "reason": "Practice-related query in mock LLM",
        })

    # 1c. Scope Redirect generator stub
    if "outside mindbridge's counseling scope" in system_prompt.lower() or "warm redirect" in system_prompt.lower():
        return (
            "That's outside what I can help with here, but I'm happy to answer questions about our counseling services, "
            "help you find the right therapist, or connect you with our team. What can I help with today?"
        )

    # 2. Intent Classification stub
    if "intent classification" in system_prompt.lower() or "possible intents" in system_prompt.lower():
        # Check if user is asking for a therapist recommendation
        if any(w in user_lower for w in ["recommend", "which therapist", "suggest a therapist", "who would you recommend", "who on your team", "who is right for", "match me"]):
            return json.dumps({
                "intent": "therapist_matching",
                "confidence": 0.95,
                "extracted_need": "Looking for therapist recommendation",
            })

        # Wants human
        if any(w in user_lower for w in ["human", "real person", "agent", "receptionist", "speak with someone", "call me", "phone"]):
            if "are you a real person" in user_lower:
                return json.dumps({
                    "intent": "general_question",
                    "confidence": 0.95,
                    "extracted_need": "Inquiring about AI identity",
                })
            return json.dumps({
                "intent": "wants_human",
                "confidence": 0.95,
                "extracted_need": "Requested direct human contact",
            })

        # General practice / policies / cancellation / fees / AI questions (check BEFORE scheduling!)
        if any(w in user_lower for w in [
            "cancel", "miss", "late", "policy", "policies", "fee", "cost", "insurance", "sliding scale", "hours",
            "diagnos", "what is wrong with me", "tell me what's wrong",
            "are you a real person", "are you an ai", "what services", "how does", "what are your", "faq"
        ]):
            return json.dumps({
                "intent": "general_question",
                "confidence": 0.95,
                "extracted_need": "General practice or policy question",
            })

        # Ongoing qualification conversation (user responding to previous qualification questions)
        has_ongoing_need = messages and any(
            "intake qualifying" in m.get("content", "").lower() or "what's bringing" in m.get("content", "").lower() or "therapist" in m.get("content", "").lower()
            for m in messages
        )
        if any(w in user_lower for w in ["couples", "together", "individual", "in-person", "video", "telehealth", "@", "email", "name is", "alex", "both of us"]):
            return json.dumps({
                "intent": "seeking_support",
                "confidence": 0.95,
                "extracted_need": user_prompt[:80],
            })

        # Explicit scheduling request (only when explicitly booking or asking to schedule)
        if any(w in user_lower for w in ["schedule an appointment", "book an appointment", "book a session", "request an appointment", "schedule consultation", "get on the calendar"]):
            return json.dumps({
                "intent": "scheduling_request",
                "confidence": 0.90,
                "extracted_need": "Looking to schedule a therapy appointment",
            })

        # Seeking support / Qualification
        if any(w in user_lower for w in [
            "fight", "fighting", "arguing", "conflict", "relationship", "partner", "husband", "wife", "marriage",
            "couples", "anxiety", "anxious", "depress", "stress", "overwhelm", "panic", "lonely", "sad", "insomnia",
            "struggling", "struggle", "trouble", "help", "need therapy", "grief", "burnout", "worry", "worried",
            "teen", "son", "daughter", "family", "counseling"
        ]):
            return json.dumps({
                "intent": "seeking_support",
                "confidence": 0.95,
                "extracted_need": user_prompt[:80],
            })

        return json.dumps({
            "intent": "general_question",
            "confidence": 0.70,
            "extracted_need": "General conversation",
        })

    # 3. RAG QA stub — dynamically answers using retrieved Qdrant context from system_prompt
    if "knowledge base qa specialist" in system_prompt.lower() or "practice knowledge about mindbridge" in system_prompt.lower() or "retrieved knowledge base context" in system_prompt:
        # Safety / Guardrail: AI Transparency
        if any(q in user_lower for q in ["real person", "are you an ai", "are you a bot", "who are you", "human or ai"]):
            return (
                "I'm Ellen, an AI assistant for MindBridge Wellness, here to help answer questions and connect you with our team. "
                "I'm not a therapist or a human, but I can help get you set up with one of our licensed counselors."
            )
        # Safety / Guardrail: Clinical Diagnosis refusal
        if any(q in user_lower for q in ["what is wrong with me", "diagnose me", "what's wrong with me", "do i have depression", "do i have anxiety"]):
            return (
                "I can't provide a diagnosis or medical assessment, as only a licensed clinician can do that. "
                "Our therapists at MindBridge Wellness would be glad to talk through what you're feeling in an initial session."
            )

        # Extract retrieved context if provided in system prompt
        context_text = ""
        if "RETRIEVED KNOWLEDGE BASE CONTEXT:" in system_prompt:
            context_text = system_prompt.split("RETRIEVED KNOWLEDGE BASE CONTEXT:")[-1].strip()

        # Compound Question Check: Hours + Insurance / Fees
        has_hours = any(w in user_lower for w in ["hour", "hours", "saturday", "evening", "weekend", "when are you", "what time", "business hours"]) or ("open" in user_lower and "reopen" not in user_lower)
        has_insurance = any(q in user_lower for q in ["insurance", "sliding scale", "copay"]) or any(re.search(p, user_lower) for p in [r"\bcosts?\b", r"\bfees?\b", r"\bpay\b", r"\bpaying\b", r"\brates?\b"])
        if has_hours and has_insurance:
            return (
                "<b>Office Hours:</b> We're open Monday through Saturday, with evening appointments available on select weekdays.<br><br>"
                "<b>Insurance & Fees:</b> We accept several major insurance plans and also offer sliding scale self-pay options. Our intake team can verify your exact coverage before your first session.<br><br>"
                "Would you like help setting up a consultation or verifying your coverage?"
            )

        # Compound Question Check: Hours + Location / Telehealth
        has_location = any(w in user_lower for w in ["location", "where", "address", "office", "directions", "telehealth", "online"])
        if has_hours and has_location:
            return (
                "<b>Office Hours:</b> We're open Monday through Saturday, with evening appointments available on select weekdays.<br><br>"
                "<b>Location & Formats:</b> We offer both in-person sessions at our office and secure video telehealth across the state.<br><br>"
                "Which format works best for you?"
            )

        # Office Hours & Scheduling availability
        if has_hours or ("schedule" in user_lower and "reschedule" not in user_lower and "cancel" not in user_lower):
            return (
                "We're open Monday through Saturday, with evening appointments available on select weekdays.<br><br>"
                "Our intake team will confirm exact times when setting up your session."
            )

        # Location & Formats
        if has_location:
            return (
                "We offer both in-person sessions at our office and secure video telehealth across the state.<br><br>"
                "Which format works best for you?"
            )

        # Cancellation & Rescheduling
        if any(q in user_lower for q in ["cancel", "miss my appointment", "cancellation", "reschedule"]) or re.search(r"\blate\b", user_lower):
            return (
                "We ask for at least 24 hours' notice to cancel or reschedule without a cancellation fee.<br><br>"
                "Need help adjusting an upcoming time?"
            )

        # Insurance, Fees & Sliding Scale
        if has_insurance:
            return (
                "We accept several major insurance plans and also offer sliding scale self-pay options.<br><br>"
                "Our team can verify your exact coverage before your first session."
            )

        # Services & Evidence-Based Modalities
        if any(q in user_lower for q in ["service", "modalit", "trauma", "approach", "what do you offer"]) or any(re.search(p, user_lower) for p in [r"\bcbt\b", r"\bact\b", r"\beft\b"]):
            return (
                "We provide counseling across several areas:<ul>"
                "<li><b>Individual Therapy</b>: anxiety, depression, and personal growth</li>"
                "<li><b>Couples Therapy</b>: communication and relationship conflict</li>"
                "<li><b>Family & Young Adult</b>: life transitions and teen support</li>"
                "</ul>What kind of support are you looking for?"
            )

        # Medical advice / Diagnosis / Medication questions
        if any(q in user_lower for q in ["diagnos", "what is wrong with me", "what's wrong with me", "medication", "xanax", "prescrib"]):
            return (
                "I cannot provide a diagnosis or medical assessment, as only a licensed physician or psychiatrist can do that. "
                "Our therapists at MindBridge Wellness provide evidence-based counseling and would be glad to talk through what you're experiencing in an initial session."
            )

        # Therapists on team & specialties
        if any(q in user_lower for q in ["who are the therapists", "specialties", "counselors on your team", "therapists on your team", "team of therapists"]):
            return (
                "Our team includes Dr. Elena Marsh (anxiety, depression, trauma/EMDR), Marcus Reyes (couples therapy and relationship communication), "
                "Priya Nair (mindfulness, stress, burnout), and Jordan Whitfield (adolescents, teens, and young adults).<br><br>"
                "<b>Please note:</b> Final therapist assignment is always made by our clinical team based on clinical fit and availability."
            )

        # First Session / Intake
        if any(q in user_lower for q in ["first session", "what to expect", "prepare", "intake"]):
            return (
                "Your first session is a relaxed conversation to talk through what brings you in and see if it's a good fit.<br><br>"
                "There's no pressure to share everything right away."
            )

        # Dynamic grounding: extract text from retrieved context if available
        if context_text:
            lines = [
                l.strip() for l in context_text.splitlines()
                if l.strip()
                and not l.startswith("[")
                and not l.startswith("**[")
                and not l.startswith("#")
                and not l.startswith("Source:")
                and "editable" not in l.lower()
                and "practice to" not in l.lower()
            ]
            substantive = " ".join(lines[:2])
            if substantive:
                clean_substantive = re.sub(r"^\s*(?:Our Therapists|Frequently Asked Questions|Our Services|Policies)\s*—\s*", "", substantive)
                clean_substantive = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", clean_substantive)
                return f"{clean_substantive}<br><br>Let me know if you'd like more details on this!"

        return "We offer individual, couples, and family counseling tailored to your goals.<br><br>How can I help you today?"

    # 4. Qualification Flow stub
    if "intake qualifying specialist" in system_prompt.lower() or "having a warm, friendly chat with a visitor" in system_prompt.lower() or "current intake status" in system_prompt.lower():
        # Check decline
        if any(w in user_lower for w in ["rather not", "prefer not", "skip", "private", "no thanks", "don't want to share"]):
            return "No problem at all, we can keep chatting here without your contact info! What questions can I answer for you?"

        has_email_or_phone = bool(re.search(r'[\w\.-]+@[\w\.-]+|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', user_prompt))

        # Check if user shared name (filter out common non-names)
        NON_NAMES = {
            "just", "looking", "here", "ready", "interested", "trying",
            "hoping", "wondering", "feeling", "anxious", "depressed",
            "stressed", "fine", "good", "not", "new", "sorry", "afraid",
            "struggling", "okay", "ok", "yes", "no", "hello", "hi", "hey"
        }
        name_match = re.search(r"(?:my name is|i'm|i am|name is|call me)\s+([A-Za-z]+)", user_prompt, re.IGNORECASE)
        tokens = user_prompt.strip().split()
        if len(tokens) == 1 and tokens[0].isalpha() and len(tokens[0]) > 1 and tokens[0].lower() not in NON_NAMES:
            name_str = tokens[0].title()
        elif name_match and name_match.group(1).lower() not in NON_NAMES:
            name_str = name_match.group(1).title()
        else:
            name_str = None

        # Check vague input
        if any(w in user_lower for w in ["just looking", "looking around", "just browsing", "not sure", "don't know", "dont know", "can you help", "nothing specific", "nothing in particular"]):
            prefix = f"No worries at all, {name_str}! " if name_str else "No worries at all! "
            return (
                f"{prefix}I'm happy to help you figure that out. Would you like to:<ul>"
                f"<li><b>Schedule an initial consultation</b> with one of our counselors</li>"
                f"<li><b>Ask something specific</b> (like insurance, fees, or therapy approaches)</li>"
                f"<li><b>Check our office hours and services</b></li>"
                f"</ul>Which of those sounds most helpful to explore right now?"
            )

        # Check system prompt for known name or concern
        system_name_match = re.search(r"- Name:\s*(.+?)(?:\n|$)", system_prompt)
        known_name = system_name_match.group(1).strip() if system_name_match and "Not collected yet" not in system_name_match.group(1) else None
        eff_name = name_str or known_name

        system_concern_match = re.search(r"- Stated Concern:\s*(.+?)(?:\n|$)", system_prompt)
        known_concern = system_concern_match.group(1).strip() if system_concern_match and "Not collected yet" not in system_concern_match.group(1) else None

        prior_user_text = " ".join([m.get("content", "").lower() for m in (messages or []) if m.get("role") == "user"])
        has_emotional_concern = any(w in user_lower or w in prior_user_text or (known_concern and w in known_concern.lower()) for w in ["anxious", "anxiety", "depress", "stress", "overwhelm", "panic", "sad", "hopeless", "struggl", "trouble", "burnout"])

        if has_email_or_phone:
            return "Thanks so much for sharing that! Our intake coordinator will reach out shortly to help you get scheduled. In the meantime, is there anything else I can help with?"

        # 1. Visitor shares emotional distress / feelings on turn 1 or early, but NAME is NOT collected yet!
        # Be empathetic and ask for their name first
        if not eff_name and any(w in user_lower for w in ["anx", "depres", "stress", "overwhelm", "panic", "sad", "hopeless", "struggl", "trouble", "burnout"]):
            if "anx" in user_lower and "depres" in user_lower:
                feelings = "anxiety and depression"
            elif "anx" in user_lower:
                feelings = "anxious"
            elif "depres" in user_lower:
                feelings = "depressed"
            elif "stress" in user_lower or "overwhelm" in user_lower:
                feelings = "stressed and overwhelmed"
            else:
                feelings = "what you're experiencing"

            return (
                f"I'm so sorry you're feeling {feelings} right now. Reaching out can take real courage, and we're here to help you through this.<br><br>"
                f"Before we talk through our counseling options, may I ask your name so I know who I'm chatting with?"
            )

        # 2. Visitor provides their name (or name is known), and an emotional concern was shared!
        # Greet by name, tell the details of how we help, and invite them forward
        if eff_name and has_emotional_concern:
            return (
                f"It's really nice to meet you, {eff_name}.<br><br>"
                f"Here at MindBridge Wellness, our individual therapy sessions focus directly on managing anxiety, depression, and stress using evidence-based approaches like CBT and ACT. "
                f"Our licensed counselors work one-on-one with you to develop personalized coping strategies and help you regain a sense of calm.<br><br>"
                f"Would you like to schedule an initial consultation with one of our counselors, or would you like more details on how our sessions work?"
            )

        # 3. Visitor gave name without any clinical concern
        if eff_name and not has_emotional_concern and not any(w in user_lower for w in ["fight", "conflict", "partner", "relationship"]):
            return (
                f"Nice to meet you, {eff_name}! I can help you find the right type of support, "
                f"book a consultation, or answer questions about our services, whatever's most helpful. "
                f"What brings you in today?"
            )

        if any(w in user_lower for w in ["thank you", "thanks", "appreciate it", "sounds good", "that's all", "thats all", "goodbye", "bye"]):
            return "You're very welcome! Feel free to reach out anytime whenever you're ready or have more questions. We're always here to help."

        is_turn_one = not messages or len([m for m in messages if m.get("role") == "user"]) <= 1
        if is_turn_one:
            return "Hi there, welcome to MindBridge Wellness! I'm Ellen, MindBridge's AI assistant here to help you find the right support. What's your name?"
        else:
            return "I'd be glad to help with that! What's the best name to call you, and what questions can I answer?"

    # 5. Scheduling Flow stub
    if "scheduling philosophy" in system_prompt.lower() or "current scheduling state" in system_prompt.lower():
        has_contact = bool(re.search(r'[\w\.-]+@[\w\.-]+|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', user_prompt))
        
        # Extract name and timing from system prompt if available
        name_match = re.search(r"- Name:\s*(.+?)(?:\n|$)", system_prompt)
        name = name_match.group(1).strip() if name_match and "Not collected yet" not in name_match.group(1) else None
        
        timing_match = re.search(r"- Preferred Timing:\s*(.+?)(?:\n|$)", system_prompt)
        timing = timing_match.group(1).strip() if timing_match and "Not collected yet" not in timing_match.group(1) else None

        # Check stage directives
        if "REJECT PAST DATE" in system_prompt:
            name_phrase = f", {name}" if name else ""
            return f"That date has already passed. Could you share an upcoming date and time that works best for you{name_phrase}?"
            
        if "CLARIFY AMBIGUOUS DAY" in system_prompt:
            suggested_match = re.search(r"looking at ([^?]+)\?", system_prompt)
            suggested = suggested_match.group(1).strip() if suggested_match else "the upcoming date"
            if not name:
                return f"Just to confirm, are you looking at {suggested}? And could I also get your name so we have that ready?"
            return f"Just to confirm, are you looking at {suggested}?"

        if "ASK VISITOR NAME AND PREFERRED DATE/TIME" in system_prompt:
            return "I'd love to help you set up a consultation! What is your name, and what day and time tends to work best for you?"

        if "COLLECT NAME AND CONTACT INFO" in system_prompt:
            timing_str = f" {timing}" if timing else ""
            return f"Got it, I've noted{timing_str} as your preference. Could I get your name and the best email or phone number for our team to follow up with you?"

        if "COLLECT CONTACT INFO FOR CONFIRMATION" in system_prompt:
            timing_str = f" {timing}" if timing else ""
            name_str = f", {name}" if name else ""
            return f"Got it, I've noted{timing_str} as your preference{name_str}. What's the best email or phone number for our team to confirm that with you?"

        if "SCHEDULING REQUEST NOTED" in system_prompt:
            timing_str = f" {timing}" if timing else " your requested time"
            name_str = f" for {name}" if name else ""
            return f"Got it, I've noted{timing_str} as your preference{name_str}. Our team will review counselor availability and follow up with you shortly to confirm."

        if not name and not timing:
            return "I'd love to help you set up a consultation! What is your name, and what day and time tends to work best for you?"
        elif not timing:
            return f"What day and time tends to work best for you{f', {name}' if name else ''}?"
        elif not name:
            return "Got it, I've noted your timing preference. Could I get your name and the best email or phone number for our team to follow up with you?"
        else:
            return f"Got it, I've noted that preference. What's the best email or phone number for our team to confirm with you, {name}?"

    # 6. Therapist Matching stub
    if "therapist matching specialist" in system_prompt.lower() or "retrieved therapist profiles" in system_prompt.lower():
        # Minimum information gate check
        if not any(w in combined_lower for w in [
            "partner", "arguing", "relationship", "marriage", "couples", "conflict",
            "teen", "adolescent", "high school", "grief", "loss", "burnout", "college",
            "anxious", "anxiety", "depress", "stress"
        ]):
            return (
                "I'd love to help connect you with the right counselor on our team. "
                "To suggest the best match, could you share a little about what you're hoping to work through (such as anxiety, couples counseling, or life transitions)?<br><br>"
                "Or if you prefer, we can schedule an initial consultation, answer questions about our services, or check our current office hours."
            )

        if any(w in combined_lower for w in ["partner", "arguing", "relationship", "marriage", "couples", "conflict"]):
            return (
                "Based on what you've shared, I'd suggest <b>Marcus Reyes, LMFT</b>.<br><br>"
                "Marcus specializes in couples counseling and communication patterns using Emotionally Focused Therapy (EFT).<br><br>"
                "Our clinical team will confirm therapist fit and availability when scheduling."
            )
        elif any(w in combined_lower for w in ["teen", "adolescent", "high school"]):
            return (
                "I would recommend <b>Jordan Whitfield, LPC</b>.<br><br>"
                "Jordan specializes in adolescent and young adult counseling, working on stress, identity, and family communication.<br><br>"
                "Our clinical team will confirm therapist fit and availability when scheduling."
            )
        elif any(w in combined_lower for w in ["grief", "loss", "burnout", "college"]):
            return (
                "I would suggest <b>Priya Nair, LCSW</b>.<br><br>"
                "Priya focuses on grief, life transitions, and burnout using Acceptance and Commitment Therapy (ACT).<br><br>"
                "Our clinical team will confirm therapist fit and availability when scheduling."
            )
        else:
            return (
                "I'd suggest <b>Dr. Elena Marsh, PsyD</b>.<br><br>"
                "Dr. Marsh brings extensive experience in cognitive-behavioral therapy for anxiety and life adjustments.<br><br>"
                "Our clinical team will confirm therapist fit and availability when scheduling."
            )

    return "Thank you for reaching out to MindBridge Wellness. How can our counseling team assist you today?"


def _safe_print(msg: str):
    """Print to console, safely handling unicode chars that Windows cp1252 can't encode."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace chars the console can't handle
        safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
        print(safe_msg)


def _call_gemini_fallback(
    system_prompt: str,
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    json_mode: bool = False,
) -> Optional[str]:
    """Fallback LLM invocation using Google Gemini 1.5 Flash via REST if key is present."""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not gemini_key:
        return None
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        contents = []
        if messages:
            for m in messages:
                role = "user" if m.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})
        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.4},
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
    except Exception as e:
        logger.warning(f"Gemini fallback error: {e}")
    return None


def call_llm(
    system_prompt: str,
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    json_mode: bool = False,
    temperature: float = 0.5,
    max_tokens: Optional[int] = None,
) -> str:
    """Invoke Groq LLM with safety prompt and fall back to Gemini or local stub."""
    client = get_groq_client()
    model_name = get_groq_model()
    raw_key = os.environ.get("GROQ_API_KEY", "").strip()
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    if is_debug:
        _safe_print(f"\n[LLM Call]")
        _safe_print(f"   GROQ_API_KEY loaded: {bool(raw_key)} (length: {len(raw_key)})")
        _safe_print(f"   GROQ_MODEL:         '{model_name}'")
        _safe_print(f"   Has Groq Client:    {client is not None}")
        _safe_print(f"   User Prompt:        '{user_prompt[:70]}...'")

    if client is not None:
        try:
            formatted_messages = [{"role": "system", "content": system_prompt}]
            if messages:
                for m in messages:
                    if m.get("role") in ("user", "assistant"):
                        formatted_messages.append({"role": m["role"], "content": m["content"]})
            formatted_messages.append({"role": "user", "content": user_prompt})

            if is_debug:
                _safe_print(f"   Calling Groq API model='{model_name}' with {len(formatted_messages)} messages...")
            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": formatted_messages,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            elif max_tokens:
                kwargs["max_tokens"] = max(max_tokens, 900)
            else:
                kwargs["max_tokens"] = 900

            import time
            for attempt in range(3):
                try:
                    completion = client.chat.completions.create(**kwargs)
                    raw_content = completion.choices[0].message.content or ""
                    if not json_mode:
                        raw_content = raw_content.replace("\u2014", ", ").replace("\u2013", "-")
                        raw_content = re.sub(r',\s*,', ',', raw_content)
                    if is_debug:
                        _safe_print(f"   Groq API Response ({len(raw_content)} chars): {raw_content[:90]}...")
                    return raw_content
                except UnicodeEncodeError:
                    return raw_content
                except Exception as api_err:
                    err_str = str(api_err).lower()
                    if "tpd" in err_str or "tokens per day" in err_str:
                        if is_debug:
                            _safe_print(f"[LLM Rate Limit] Daily token limit (TPD) reached. Falling back immediately.")
                        break
                    if ("429" in err_str or "rate" in err_str) and attempt < 2:
                        sleep_s = 2.0 * (attempt + 1)
                        if is_debug:
                            _safe_print(f"[LLM Rate Limit] 429 received, backing off {sleep_s}s (attempt {attempt + 1}/3)...")
                        time.sleep(sleep_s)
                        continue
                    raise api_err
        except UnicodeEncodeError:
            pass
        except Exception as e:
            if is_debug:
                _safe_print(f"[LLM Error] Groq API call raised exception: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()

    # Try secondary Gemini provider if available
    gemini_resp = _call_gemini_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        messages=messages,
        json_mode=json_mode,
    )
    if gemini_resp:
        if is_debug:
            _safe_print(f"   [LLM Notice] Gemini Fallback returned: '{gemini_resp[:90]}...'")
        return gemini_resp

    if is_debug:
        _safe_print(f"   [LLM Notice] No active Groq/Gemini response. Delegating to local heuristic handler.")
    resp = _mock_llm_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        messages=messages,
        json_mode=json_mode,
    )
    if is_debug:
        _safe_print(f"   Local Fallback returned: '{resp[:90]}...'")
    return resp
