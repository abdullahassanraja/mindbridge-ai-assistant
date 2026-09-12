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
            _groq_client = Groq(api_key=api_key)
        except Exception as e:
            print(f"[Warning] Could not initialize Groq client: {e}")
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
            "couples", "anxiety", "depress", "struggling", "struggle", "trouble", "help", "need therapy", "grief", "burnout",
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
    if "knowledge base qa specialist" in system_prompt.lower():
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

        # Office Hours & Scheduling availability
        if any(w in user_lower for w in ["hour", "hours", "open", "schedule", "saturday", "evening", "weekend", "when are you"]):
            return (
                "We're open Monday through Saturday, with evening appointments available on select weekdays.<br><br>"
                "Our intake team will confirm exact times when setting up your session."
            )

        # Location & Formats
        if any(w in user_lower for w in ["location", "where", "address", "office", "directions", "telehealth", "online"]):
            return (
                "We offer both in-person sessions at our office and secure video telehealth across the state.<br><br>"
                "Which format works best for you?"
            )

        # Cancellation & Rescheduling
        if any(q in user_lower for q in ["cancel", "miss my appointment", "cancellation", "late", "reschedule"]):
            return (
                "We ask for at least 24 hours' notice to cancel or reschedule without a cancellation fee.<br><br>"
                "Need help adjusting an upcoming time?"
            )

        # Insurance, Fees & Sliding Scale
        if any(q in user_lower for q in ["insurance", "cost", "fee", "pay", "rate", "sliding scale", "copay"]):
            return (
                "We accept several major insurance plans and also offer sliding scale self-pay options.<br><br>"
                "Our team can verify your exact coverage before your first session."
            )

        # Services & Evidence-Based Modalities
        if any(q in user_lower for q in ["service", "modalit", "cbt", "act", "eft", "trauma", "approach", "what do you offer"]):
            return (
                "We provide counseling across several areas:<ul>"
                "<li><b>Individual Therapy</b>: anxiety, depression, and personal growth</li>"
                "<li><b>Couples Therapy</b>: communication and relationship conflict</li>"
                "<li><b>Family & Young Adult</b>: life transitions and teen support</li>"
                "</ul>What kind of support are you looking for?"
            )

        # First Session / Intake
        if any(q in user_lower for q in ["first session", "what to expect", "prepare", "intake"]):
            return (
                "Your first session is a relaxed conversation to talk through what brings you in and see if it's a good fit.<br><br>"
                "There's no pressure to share everything right away."
            )

        # Dynamic grounding: extract text from retrieved context if available
        if context_text:
            lines = [l.strip() for l in context_text.splitlines() if l.strip() and not l.startswith("[") and not l.startswith("#") and not l.startswith("Source:")]
            substantive = " ".join(lines[:2])
            if substantive:
                return f"{substantive}<br><br>Let me know if you'd like more details on this!"

        return "We offer individual, couples, and family counseling tailored to your goals.<br><br>How can I help you today?"

    # 4. Qualification Flow stub
    if "intake qualifying specialist" in system_prompt.lower():
        # Check decline
        if any(w in user_lower for w in ["rather not", "prefer not", "skip", "private", "no thanks", "don't want to share"]):
            return "No problem at all, we can keep chatting here without your contact info! What questions can I answer for you?"

        has_email_or_phone = bool(re.search(r'[\w\.-]+@[\w\.-]+|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', user_prompt))

        # Check if user shared name
        name_match = re.search(r"(?:my name is|i'm|i am|name is|call me)\s+([A-Za-z]+)", user_prompt, re.IGNORECASE)
        tokens = user_prompt.strip().split()
        if len(tokens) == 1 and tokens[0].isalpha() and len(tokens[0]) > 1:
            name_str = tokens[0].title()
        elif name_match:
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

        if has_email_or_phone:
            return "Thanks so much for sharing that! Our intake coordinator will reach out shortly to help you get scheduled. In the meantime, is there anything else I can help with?"

        if name_str and not any(w in user_lower for w in ["anxious", "anxiety", "depress", "fight", "conflict", "help", "therapy", "partner", "stress"]):
            return (
                f"Nice to meet you, {name_str}! I can help you find the right type of support, "
                f"book a consultation, or answer questions about our services, whatever's most helpful. "
                f"What brings you in today?"
            )

        if any(w in user_lower for w in ["anxious", "anxiety", "depress", "stress", "fight", "conflict", "partner", "relationship", "trouble", "struggl"]):
            prefix = f"Thanks for sharing that, {name_str}. " if name_str else "I appreciate you sharing that with me. "
            return f"{prefix}We have therapists who specialize in this. What's the best email or phone number for our intake coordinator to follow up with you?"

        return "Hi there, welcome to MindBridge Wellness! I'm Ellen, MindBridge's AI assistant here to help you find the right support. What's your name?"

    # 5. Therapist Matching stub
    if "therapist matching specialist" in system_prompt.lower():
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


def call_llm(
    system_prompt: str,
    user_prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    json_mode: bool = False,
    temperature: float = 0.5,
    max_tokens: Optional[int] = None,
) -> str:
    """Invoke Groq LLM with safety prompt and fall back to local stub if key is not configured."""
    client = get_groq_client()
    model_name = get_groq_model()
    raw_key = os.environ.get("GROQ_API_KEY", "").strip()
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    if is_debug:
        print(f"\n[LLM Call]")
        print(f"   GROQ_API_KEY loaded: {bool(raw_key)} (length: {len(raw_key)})")
        print(f"   GROQ_MODEL:         '{model_name}'")
        print(f"   Has Groq Client:    {client is not None}")
        print(f"   User Prompt:        '{user_prompt[:70]}...'")

    if client is not None:
        try:
            formatted_messages = [{"role": "system", "content": system_prompt}]
            if messages:
                for m in messages:
                    if m.get("role") in ("user", "assistant"):
                        formatted_messages.append({"role": m["role"], "content": m["content"]})
            formatted_messages.append({"role": "user", "content": user_prompt})

            if is_debug:
                print(f"   Calling Groq API model='{model_name}' with {len(formatted_messages)} messages...")
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

            completion = client.chat.completions.create(**kwargs)
            raw_content = completion.choices[0].message.content or ""
            if not json_mode:
                raw_content = raw_content.replace("—", ", ").replace("–", "-")
                raw_content = re.sub(r',\s*,', ',', raw_content)
            if is_debug:
                print(f"   Groq API Response ({len(raw_content)} chars): {raw_content[:90]}...")
            return raw_content
        except Exception as e:
            if is_debug:
                print(f"[LLM Error] Groq API call raised exception: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                print(f"   Falling back to _mock_llm_response...")

    if is_debug:
        print(f"   [LLM Notice] No active Groq client. Delegating to local heuristic handler.")
    resp = _mock_llm_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        messages=messages,
        json_mode=json_mode,
    )
    if is_debug:
        print(f"   Local Fallback returned: '{resp[:90]}...'")
    return resp
