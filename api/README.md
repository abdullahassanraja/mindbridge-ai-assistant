# MindBridge Wellness — FastAPI Backend

FastAPI HTTP backend serving the MindBridge Wellness LangGraph conversational agent. Provides persistent multi-turn chat sessions across HTTP calls using LangGraph's checkpointer mechanism, CORS protection for Squarespace embedding, and health monitoring.

---

## API Endpoints

### 1. `POST /chat`
Processes conversational turns through the LangGraph StateGraph.

- **Request Body**:
  ```json
  {
    "session_id": "optional-uuid-string",
    "message": "Hello, do you accept insurance?"
  }
  ```
  *(If `session_id` is omitted or empty, a new UUID is generated and returned in the response).*
- **Response Body**:
  ```json
  {
    "response": "MindBridge Wellness accepts several major insurance plans...",
    "session_id": "c1f7b880-9289-4b36-9b5f-55df9b10901e"
  }
  ```

### 2. `GET /health`
Probes service health for deployment uptime checks.
- **Response**: `{"status": "ok"}`

---

## Local Development

### 1. Setup Environment
Ensure dependencies are installed:
```bash
cd mindbridge/api
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default `.env` configuration:
```ini
PORT=8000
ALLOWED_ORIGIN=*
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
QDRANT_PATH=../ingestion/qdrant_data
```

### 3. Run Server
Start the Uvicorn dev server with auto-reload:
```bash
uvicorn main:app --reload --port 8000
```
Or directly:
```bash
python main.py
```
Visit the interactive Swagger API documentation at: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Checkpointer & State Persistence Note

This demo uses LangGraph's in-memory `MemorySaver` checkpointer.
- Conversation state and history persist across HTTP requests within the same server lifetime keyed by `session_id` (used as `thread_id`).
- If the server restarts, in-memory sessions reset.
- **Production Upgrade Path**: Replace `MemorySaver` in `main.py` with `PostgresSaver` (e.g. connected to Supabase or AWS RDS PostgreSQL) for persistent, horizontally scalable chat state.

---

## Production Deployment (Railway / Render)

### Deploying to Railway:
1. Create a new project on [Railway.app](https://railway.app).
2. Connect your Git repository.
3. Set the Root Directory to `mindbridge/api`.
4. Configure Build & Start Command:
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Set Environment Variables in Railway dashboard:
   - `GROQ_API_KEY`: Your real Groq API key (`gsk_...`)
   - `GROQ_MODEL`: `llama-3.3-70b-versatile`
   - `ALLOWED_ORIGIN`: Your live Squarespace domain (e.g. `https://mindbridgewellness.squarespace.com`)
   - `QDRANT_PATH`: Path to Qdrant storage, or set `QDRANT_URL` and `QDRANT_API_KEY` for Qdrant Cloud.

### Deploying to Render:
1. Create a new **Web Service** on [Render.com](https://render.com).
2. Root directory: `mindbridge/api`.
3. Build Command: `pip install -r requirements.txt`.
4. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
5. Add the same Environment Variables under the **Environment** tab.
