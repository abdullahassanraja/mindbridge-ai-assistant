# MindBridge Wellness — AI Intake & Care Assistant

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-DC2626.svg)](https://qdrant.tech/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AI-powered intake and lead qualification assistant for mental wellness practices — RAG-grounded Q&A, empathetic conversational qualification, therapist matching, and built-in crisis-safety guardrails. Built as a case study demo (Olema).**

---

## Overview

**MindBridge Wellness** is an outpatient mental health counseling practice demo. This repository provides an end-to-end, production-ready AI intake assistant architecture that:
1. **Engages Website Visitors**: Warm, conversational intake with **Ellen**, MindBridge's AI assistant.
2. **RAG-Grounded Answers**: Answers questions about clinical services, insurance, fees, and office policies using local semantic vector search in **Qdrant**.
3. **Conversational Qualification**: Discretely collects visitor needs, preferred session format (in-person vs. video telehealth), and contact info.
4. **Therapist Matching**: Matches prospective clients with specialized practitioners (e.g. Couples EFT, Individual CBT/ACT, Teen & Young Adult) with mandatory clinical disclaimers.
5. **Strict Crisis & Safety Guardrails**: Permanent 988 Suicide & Crisis Lifeline / 911 redirection when acute distress is detected. Strictly refuses to offer diagnoses or prescriptive clinical advice.
6. **Embeddable Vanilla Widget**: Dependency-free embeddable chat widget compatible with Squarespace, Webflow, WordPress, or custom HTML websites.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Frontend Website / CMS                        │
│             (Squarespace, Webflow, WordPress, Static HTML)             │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │           mindbridge/widget (Vanilla JavaScript)               │   │
│   │  • Floating Launcher with Ellen Avatar & Online Beacon         │   │
│   │  • Full-Height Floating Window with Animated Soothing Aura     │   │
│   │  • Welcoming Ticker ("let us help you heal/grow/breathe...")   │   │
│   │  • 3 Starter Prompts ("Help me find the right therapist", etc.)│   │
│   │  • Gemini-style Chat Bubbles (Blue User / White Assistant)     │   │
│   │  • Session Persistence via browser sessionStorage              │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
└───────────────────────────────────┼────────────────────────────────────┘
                                    │ HTTP POST /chat (JSON)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend Server                          │
│                          (mindbridge/api)                              │
│                                                                        │
│   • POST /chat  — Session-aware conversational endpoint                │
│   • GET /health — Service health and monitoring                        │
│   • CORS protection configured for site embedding                      │
│   • LangGraph MemorySaver checkpointer (session state continuity)      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Invokes StateGraph
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   LangGraph Conversational Agent                       │
│                         (mindbridge/agent)                             │
│                                                                        │
│         [crisis_check] ──(crisis detected)──► [crisis_response] (988)  │
│                │                                                       │
│           (safe turn)                                                  │
│                ▼                                                       │
│         [intent_router]                                                │
│         ├──► [rag_qa] ───────────────┐                                 │
│         ├──► [qualification_flow] ───┼──► [therapist_matching]         │
│         ├──► [scheduling_stub] ──────┤              │                  │
│         └──► [human_handoff] ────────┴──────────────▼                  │
│                                              [lead_capture]            │
│                                              (leads.json / dispatch)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Semantic Query Search
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      Document Ingestion & RAG                          │
│                       (mindbridge/ingestion)                           │
│                                                                        │
│   • Markdown Chunking (H2-split, Greedy Paragraph Packing, FAQ-aware)  │
│   • Local Embeddings via FastEmbed (BAAI/bge-small-en-v1.5, 384-dim)   │
│   • Qdrant Vector Database (Embedded local storage or Qdrant Cloud)    │
│   • Practice Knowledge Base: Overview, Services, Therapists, FAQs      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mindbridge/
├── .gitignore                   # Excludes .env, local DBs, logs, caches
├── README.md                    # Root architecture and setup documentation
├── .env.example                 # Root environment template
│
├── ingestion/                   # Document Chunking & Vector Search
│   ├── docs/                    # Knowledge base markdown source files
│   │   ├── 01_practice_overview.md
│   │   ├── 02_services.md
│   │   ├── 03_therapists.md
│   │   ├── 04_policies.md
│   │   └── 05_faqs.md
│   ├── chunker.py               # Document & text chunking logic
│   ├── ingest.py                # FastEmbed + Qdrant index builder
│   ├── test_pipeline.py         # Automated ingestion test suite
│   ├── requirements.txt         # Ingestion dependencies
│   └── README.md                # Ingestion documentation
│
├── agent/                       # LangGraph Conversational Agent
│   ├── state.py                 # StateGraph schema (AgentState)
│   ├── nodes.py                 # 8 specialized workflow nodes
│   ├── graph.py                 # StateGraph routing & compilation
│   ├── crisis_response.py       # Clinical safety constants (988/911)
│   ├── safety_prompts.py        # System prompts & clinical guardrails
│   ├── llm.py                   # Groq LLM integration + fallback
│   ├── leads.py                 # Lead logger & handoff dispatcher
│   ├── main.py                  # Terminal interactive CLI loop
│   ├── test_agent.py            # Clinical & safety scenario tests
│   ├── requirements.txt         # Agent dependencies
│   └── README.md                # Agent documentation
│
├── api/                         # FastAPI HTTP Web Service
│   ├── main.py                  # API endpoints (/chat, /health)
│   ├── test_api.py              # Backend API test suite
│   ├── requirements.txt         # FastAPI dependencies
│   └── README.md                # Deployment guide (Railway / Render)
│
└── widget/                      # Embeddable Chat Widget
    ├── widget.js                # Zero-dependency vanilla JS widget
    ├── ellen_avatar.jpg         # Ellen's photorealistic counselor avatar
    ├── index.html               # Practice demo page hosting widget
    ├── embed-snippet.html       # Squarespace embed snippet
    ├── test_widget_redesign.py  # Automated Edge browser verification
    └── README.md                # Embedding guide & widget documentation
```

---

## Core Features & Safety Guardrails

### 1. Transparent AI Disclosure
- Greet visitors immediately as an AI intake assistant.
- Explains its role: to help prospective clients learn about counseling services and connect with the care team.

### 2. Zero Clinical Diagnosis
- Strictly refuses requests to diagnose disorders (e.g. *"Do I have Major Depression or Bipolar?"*).
- Validates the visitor's feelings empathetically and encourages discussing symptoms in depth with a licensed therapist.

### 3. Immediate Crisis Lockout
- Detects suicide, self-harm, domestic danger, or acute psychiatric crisis keywords.
- Immediately provides editable, verified crisis assistance (988 Suicide & Crisis Lifeline, Crisis Text Line `HOME` to `741741`, 911).
- Dispatches emergency alert to `handoffs.json` and locks subsequent conversation turns into crisis response mode.

### 4. Transparent Therapist Matching
- Recommends practitioner profiles (e.g. Marcus Reyes, LMFT; Sarah Lin, LCSW; Dr. Elena Rostova, PsyD) based on clinical match.
- Includes mandatory clinical disclaimer:
  > *"Final therapist assignment is always made by our practice's clinical team based on clinical fit and therapist availability."*

---

## Quick Start / Local Development

### 1. Clone & Setup Environment
```bash
git clone https://github.com/abdullahassanraja/mindbridge-ai-assistant.git
cd mindbridge-ai-assistant
```

### 2. Ingest Knowledge Base
```bash
cd ingestion
pip install -r requirements.txt
python ingest.py
```
*Creates local vector store in `ingestion/qdrant_data/` with 38 knowledge chunks.*

### 3. Run FastAPI Backend
```bash
cd ../api
pip install -r requirements.txt
cp .env.example .env
python main.py
```
*Backend runs at `http://127.0.0.1:8000` with Swagger docs at `/docs`.*

### 4. Serve Widget Demo Page
In a separate terminal:
```bash
cd ../widget
python -m http.server 3000
```
*Open `http://localhost:3000/index.html` in your browser to interact with Ellen.*

---

## Testing & Quality Assurance

Each component includes dedicated automated test suites:

| Component | Test Command | What It Verifies |
|---|---|---|
| **Ingestion** | `python ingestion/test_pipeline.py` | Vector search relevance, chunk deletion, and upload pipeline. |
| **Agent** | `python agent/test_agent.py` | Multi-turn qualification, RAG retrieval, crisis lockout, AI refusal to diagnose. |
| **API** | `python api/test_api.py` | FastAPI `/chat` session persistence, CORS headers, and `/health`. |
| **Widget** | `python widget/test_widget_redesign.py` | Edge browser CDP test for avatar, full-height UI, dynamic ticker, and starter cards. |

---

## Squarespace & CMS Embedding

To embed Ellen into your live practice website (Squarespace, Webflow, or WordPress):

1. Deploy the `api/` folder to a hosting platform (e.g. [Railway](https://railway.app), [Render](https://render.com), or AWS).
2. Host `widget.js` and `ellen_avatar.jpg` on your web host or CDN.
3. Add the following snippet to your site's **Code Injection (Footer)**:
   ```html
   <script src="https://your-domain.com/widget.js" defer></script>
   ```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details. Built as a mental health wellness intake case study demo.
