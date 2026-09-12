# MindBridge Wellness — Embeddable Chat Widget

A standalone, dependency-free vanilla JavaScript chat widget designed to embed the **MindBridge Wellness AI Intake Assistant** on any website or Squarespace page.

---

## Features

- **Zero Build / Zero Dependencies**: Single self-contained `widget.js` file.
- **Upfront AI Disclosure**:
  - Header explicitly displays **AI Assistant | Care Intake Support**.
  - On the first open of a session, automatically greets the visitor with an initial assistant message clearly identifying as an AI assistant.
- **Session Continuity**: Saves `session_id` and message history in browser `sessionStorage`, allowing page refreshes without losing context while starting fresh in new tabs.
- **Calming Design**: Tailored with soft sage green accents (`#2D5A4C`), high contrast text, and micro-animations suitable for a mental health counseling practice.
- **Mobile Responsive**: Adapts smoothly to mobile and tablet screen widths.
- **Graceful Error Handling**: Displays friendly inline notifications if backend connectivity is interrupted.

---

## Local Testing

### Step 1: Start the FastAPI Backend
In a terminal, start the API server on port 8000:
```bash
cd mindbridge/api
uvicorn main:app --reload --port 8000
```

### Step 2: Serve the Widget Test Page
In a separate terminal, serve the `widget/` directory (for example on port 8080):
```bash
cd mindbridge/widget
python -m http.server 8080
```

### Step 3: Open in Browser
Visit [http://localhost:8080/index.html](http://localhost:8080/index.html).
1. Click the floating green chat bubble in the lower-right corner.
2. Verify the opening AI disclosure greeting appears immediately.
3. Chat with the assistant and confirm multi-turn persistence across questions.
4. Refresh the page to verify that conversation history is preserved in `sessionStorage`.

---

## Squarespace Embedding Instructions

### Prerequisites
1. Deploy your FastAPI backend to a public URL with HTTPS (e.g. via Railway, Render, or Fly.io).
2. Host `widget.js` on your public server, CDN, or within your Squarespace uploaded files.
3. Open `widget.js` and set the backend URL on line 9:
   ```javascript
   const MINDBRIDGE_BACKEND_URL = 'https://your-api.railway.app';
   ```

---

### Option A: Site-Wide Footer Code Injection (Recommended)
This displays the chat widget across every page of your Squarespace site.

> *Note: Code Injection requires a Squarespace Business or Commerce plan.*

1. Log into your Squarespace website management dashboard.
2. In the left navigation menu, go to:
   - **Website** > **Pages** > scroll down to **Website Tools** > **Code Injection**
   *(In older Squarespace menus: Settings > Advanced > Code Injection)*.
3. Scroll down to the **Footer** text area.
4. Paste the snippet from [`embed-snippet.html`](embed-snippet.html):
   ```html
   <!-- MindBridge Wellness AI Chat Widget -->
   <script src="https://your-domain.com/widget.js" defer></script>
   ```
5. Click **Save** in the upper left corner.

---

### Option B: Page-Specific Code Block
If you only want the assistant on a specific page (e.g. `/get-started`, `/contact`, or `/new-clients`):

1. Navigate to the specific page in the Squarespace Editor.
2. Click **Edit** on the page.
3. Add a new **Block** and choose **Code** (`</>`).
4. Set the mode to **HTML** (ensure "Display Source" is toggled OFF).
5. Paste the script tag:
   ```html
   <script src="https://your-domain.com/widget.js" defer></script>
   ```
6. Click **Save** and **Exit**.
