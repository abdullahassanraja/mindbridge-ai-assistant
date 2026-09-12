# MindBridge Wellness — LangGraph Conversational Agent

An AI intake assistant for **MindBridge Wellness**, an outpatient counseling practice demo. The agent engages website visitors in natural, compassionate qualifying conversations, answers questions about practice policies and services using local vector RAG, suggests matching therapist profiles, captures qualified leads, and enforces strict safety and clinical guardrails.

---

## Architecture & StateGraph Flow

The conversational agent is built with **LangGraph** (`StateGraph`) and routes messages across 8 specialized nodes:

```
                  ┌──────────────────────┐
                  │    User Message      │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │    crisis_check      │
                  └──────┬────────┬──────┘
       [crisis=True]     │        │ [crisis=False]
       ┌─────────────────┘        ▼
       │                  ┌──────────────────────┐
       │                  │    intent_router     │
       │                  └──────┬───────────────┘
       │                         │
       │      ┌──────────────────┼──────────────────┬─────────────────┐
       │      │ wants_human      │ seeking_support  │ scheduling_req  │ general_question / other
       │      ▼                  ▼                  ▼                 ▼
       │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
       │  │ human_handoff│   │qualification_│   │ scheduling_  │   │    rag_qa    │
       │  └──────┬───────┘   │     flow     │   │     stub     │   └──────┬───────┘
       │         │           └──────┬───────┘   └──────┬───────┘          │
       │         │   [match cue]    │                  │                  │
       │         │   ┌──────────────┘                  │                  │
       │         │   ▼                                 │                  │
       │         │ ┌──────────────────────┐            │                  │
       │         │ │ therapist_matching   │            │                  │
       │         │ └─────────┬────────────┘            │                  │
       │         │           │                         │                  │
       │         ▼           ▼                         ▼                  ▼
       │       ┌────────────────────────────────────────────────────────────┐
       │       │                      lead_capture                          │
       │       └─────────────────────────────┬──────────────────────────────┘
       │                                     │
       ▼                                     ▼
   ┌───────┐                             ┌───────┐
   │  END  │                             │  END  │
   └───────┘                             └───────┘
```

---

## Key Modules & Files

| File | Description |
|---|---|
| [`state.py`](file:///c:/Users/pc/Documents/mindbridge/agent/state.py) | TypedDict state schema tracking messages, visitor need, structured qualification info, therapist match, flags, and turn count. |
| [`crisis_response.py`](file:///c:/Users/pc/Documents/mindbridge/agent/crisis_response.py) | **EDITABLE** crisis response constants containing 988 Lifeline, 911, and Crisis Text Line guidance. Never freestyled by the LLM. |
| [`safety_prompts.py`](file:///c:/Users/pc/Documents/mindbridge/agent/safety_prompts.py) | `SAFETY_SYSTEM_PROMPT` prepended to every LLM call, plus node-specific prompts for safety classification, routing, QA, and qualification. |
| [`llm.py`](file:///c:/Users/pc/Documents/mindbridge/agent/llm.py) | Groq SDK integration (`llama-3.3-70b-versatile` default) with high-fidelity local fallback for offline/test environments. |
| [`nodes.py`](file:///c:/Users/pc/Documents/mindbridge/agent/nodes.py) | Implementations of all 8 nodes with guardrails, entity extraction, and RAG search integration. |
| [`graph.py`](file:///c:/Users/pc/Documents/mindbridge/agent/graph.py) | LangGraph `StateGraph` compilation and conditional routing logic. |
| [`leads.py`](file:///c:/Users/pc/Documents/mindbridge/agent/leads.py) | Stubbed lead dispatch (`leads.json`) and human handoff event logger (`handoffs.json`). |
| [`main.py`](file:///c:/Users/pc/Documents/mindbridge/agent/main.py) | Interactive CLI loop for testing conversations in the terminal. |
| [`test_agent.py`](file:///c:/Users/pc/Documents/mindbridge/agent/test_agent.py) | Automated scenario test suite covering all 5 clinical and safety verification flows. |
| [`.env.example`](file:///c:/Users/pc/Documents/mindbridge/agent/.env.example) | Environment variable template. |

---

## Setup & Installation

### 1. Requirements
- Python 3.10+ (tested on Python 3.11)
- Installed Qdrant vector index in `../ingestion/qdrant_data` (created by running `python ingest.py` in `mindbridge/ingestion/`).

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` to configure:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
QDRANT_PATH=../ingestion/qdrant_data
```
*(Note: If `GROQ_API_KEY` is not provided, the agent uses an intelligent built-in deterministic handler so testing and CLI demonstrations work immediately out of the box).*

---

## Running the Interactive CLI

Launch the terminal chat session:

```bash
python main.py
```

### CLI Commands:
- Type any message and press **Enter** to chat.
- Type `reset` to start a new conversation.
- Type `exit` or `quit` to end the session.

---

## Running Automated Scenario Tests

Execute the full verification suite to test all 5 clinical and guardrail scenarios:

```bash
python test_agent.py
```

### Scenarios Covered:
1. **General Question**: Hits `rag_qa` and retrieves cancellation policy details from Qdrant.
2. **Qualification & Matching**: Multi-turn intake for relationship conflict -> gathers format and contact info -> dispatches lead notification -> recommends **Marcus Reyes, LMFT** with mandatory clinical disclaimer.
3. **Crisis Language Detection**: Immediately redirects to editable 988/911 crisis template, logs handoff event, and locks subsequent conversation turns into handoff mode.
4. **AI Disclosure & Refusal to Diagnose**: Transparently acknowledges AI status and refuses to diagnose clinical symptoms.
5. **Direct Human Request**: Routes directly to `human_handoff` and logs care coordinator alert.

---

## Clinical Safety & Guardrails Summary

1. **AI Disclosure**: Always identifies as an AI intake assistant.
2. **Zero Diagnosis**: Strictly refuses to diagnose or suggest clinical labels.
3. **No Prescriptive Advice**: Never prescribes clinical exercises or interventions.
4. **Permanent Crisis Lockout**: If suicidal ideation or self-harm is detected, the conversation is locked permanently into crisis redirection.
5. **Mandatory Matching Disclaimer**:
   > *"Please note: Final therapist assignment is always made by our practice's clinical team based on clinical fit and therapist availability. This suggestion is a starting point for our team to review with you."*
