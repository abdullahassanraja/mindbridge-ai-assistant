# main.py
# FastAPI backend wrapping MindBridge Wellness LangGraph Agent with session checkpointer and CORS.

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mindbridge_api")

# Add agent and ingestion folders to sys.path
api_dir = Path(__file__).resolve().parent
agent_dir = api_dir.parent / "agent"
ingestion_dir = api_dir.parent / "ingestion"

if str(agent_dir) not in sys.path:
    sys.path.insert(0, str(agent_dir))
if str(ingestion_dir) not in sys.path:
    sys.path.insert(0, str(ingestion_dir))

# Ensure QDRANT_PATH default points to ingestion qdrant_data
os.environ.setdefault("QDRANT_PATH", str(ingestion_dir / "qdrant_data"))

# Import LangGraph components
from langgraph.checkpoint.memory import MemorySaver
from graph import build_graph
from state import create_initial_state

# NOTE ON CHECKPOINTER PERSISTENCE:
# We use LangGraph's in-memory MemorySaver for this demo. Conversation state and history
# persist across HTTP requests within the same server lifetime keyed by session_id.
# If the server process restarts, in-memory sessions reset.
# Production Upgrade Path: Replace MemorySaver with a persistent checkpointer,
# such as PostgresSaver (backed by Supabase or Amazon RDS PostgreSQL).
checkpointer = MemorySaver()
agent_graph = build_graph(checkpointer=checkpointer)

# Initialize FastAPI App
app = FastAPI(
    title="MindBridge Wellness AI Intake API",
    description="HTTP backend serving the LangGraph conversational assistant for MindBridge Wellness.",
    version="1.0.0",
)

# CORS Configuration
allowed_origin_env = os.environ.get("ALLOWED_ORIGIN", "*").strip()

if allowed_origin_env == "*":
    logger.warning(
        "⚠️ [SECURITY NOTICE] CORS ALLOWED_ORIGIN is set to '*'. "
        "This is convenient for local development but MUST be restricted to your Squarespace domain "
        "in production (e.g. ALLOWED_ORIGIN=https://mindbridgewellness.squarespace.com)."
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Explicit origins (supports comma-separated list + standard local dev ports)
    configured_origins = [o.strip() for o in allowed_origin_env.split(",") if o.strip()]
    dev_origins = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
    ]
    for dev in dev_origins:
        if dev not in configured_origins:
            configured_origins.append(dev)

    logger.info(f"Configured CORS allowed origins: {configured_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Request & Response Models
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.get("/health")
async def health_check():
    """Health check endpoint for uptime monitoring and deployment probes."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint processing messages through the LangGraph conversational graph.
    
    Persists multi-turn conversation history per session_id using MemorySaver.
    """
    # 1. Validate and normalize session_id
    raw_session = request.session_id
    is_new_session = not (raw_session and raw_session.strip())
    if is_new_session:
        session_id = str(uuid.uuid4())
    else:
        session_id = raw_session.strip()

    user_text = request.message.strip() if request.message else ""
    
    config = {"configurable": {"thread_id": session_id}}
    is_debug = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

    # Check if session exists in checkpointer
    state_snapshot = agent_graph.get_state(config)
    has_existing_state = bool(state_snapshot and state_snapshot.values)
    session_status = "EXISTING (in checkpointer)" if has_existing_state else ("NEW (client provided id)" if not is_new_session else "NEW (generated id)")

    if is_debug:
        print(f"\n" + "=" * 65)
        print(f"[API /chat] Incoming Request")
        print(f"   Raw Message:     '{user_text}'")
        print(f"   Session ID:      {session_id}")
        print(f"   Session Status:  {session_status}")
        print(f"   Thread ID in Config: {config['configurable']['thread_id']}")

    if not user_text:
        if is_debug:
            print(f"   [API /chat] Empty message received.")
        return ChatResponse(
            response="Hello! I didn't receive any text. How can MindBridge Wellness assist you today?",
            session_id=session_id,
        )

    try:
        # 2. Retrieve existing state from checkpointer or initialize a new session
        if has_existing_state:
            state = dict(state_snapshot.values)
            messages = list(state.get("messages", []))
        else:
            state = create_initial_state()
            messages = []

        state["session_id"] = session_id

        if is_debug:
            print(f"   Messages BEFORE turn: {len(messages)}")
        # 3. Append incoming user turn
        messages.append({"role": "user", "content": user_text})
        state["messages"] = messages

        # 4. Invoke the LangGraph workflow
        final_state = agent_graph.invoke(state, config=config)

        # 5. Extract assistant's reply
        assistant_messages = [m for m in final_state.get("messages", []) if m.get("role") == "assistant"]
        if assistant_messages:
            reply_text = assistant_messages[-1]["content"]
        else:
            reply_text = (
                "Thank you for contacting MindBridge Wellness. A care coordinator from our team "
                "will be happy to assist you directly."
            )

        if is_debug:
            print(f"   Messages AFTER turn:  {len(final_state.get('messages', []))}")
            print(f"   Response Summary:     {reply_text[:80]}...")
            print("=" * 65 + "\n")

        return ChatResponse(response=reply_text, session_id=session_id)

    except Exception as exc:
        # Log real exception server-side
        logger.error(f"Error in /chat endpoint for session {session_id}: {exc}", exc_info=True)
        # Return graceful safe fallback message
        fallback_msg = (
            "Something went wrong while processing your request. Please try again, or feel free to "
            "contact our office directly at care@mindbridgewellness.demo or (555) 349-2810."
        )
        return ChatResponse(response=fallback_msg, session_id=session_id)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting MindBridge API on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
