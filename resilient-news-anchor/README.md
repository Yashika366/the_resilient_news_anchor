# The Resilient News Anchor

Same Planner → Critic/Recovery → Synthesizer pipeline as the original
Streamlit app, split into two pieces:

- **`backend/`** — Python (FastAPI). All agent logic lives here: the real
  GDELT + Hacker News calls, chaos injection, retry/fallback chain,
  promotional-content filtering, the step-limit stopping condition.
- **frontend (`src/`)** — React (Vite). Pure UI. It calls the backend's
  `/api/run` endpoint and renders the result; it does not call GDELT or
  Hacker News itself and contains no agent logic.

So: **backend = Python, frontend = React.** That's the honest one-line
answer if a judge asks what you used.

## Run it (two terminals)

**Terminal 1 — backend**

```bash
cd backend
python -m venv venv && source venv/bin/activate   # skip on Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Check it's alive: open `http://localhost:8000/api/health` — should return `{"ok": true}`.

**Terminal 2 — frontend**

```bash
npm install
npm run dev
```

Open the URL it prints (usually `http://localhost:5173`). The frontend
talks to `http://localhost:8000` by default — copy `.env.example` to `.env`
if your backend runs somewhere else.

## One thing to know about the live demo

GDELT's public API does not always send CORS headers, but that no longer
matters — the browser never calls GDELT directly anymore, the Python
backend does, so this isn't a CORS concern at all now. What can still
happen is GDELT itself being slow or down; that's real API flakiness, and
it's exactly what the retry → Hacker News → local-fallback chain exists to
survive. Run a couple of chaos-on passes before judging so you've seen
that path fire at least once.

## What to say when judges ask about the stack

- **Backend: Python (FastAPI)** — this is where all three agents actually
  run: Planner (GDELT tool call), Critic & Recovery (retry, then switches
  to a second real API — Hacker News — then falls back to local data;
  also rejects promotional content), and Synthesizer (formats the draft,
  logs cost/latency, stops short of publishing without a human).
- **Frontend: React** — a thin client that calls the backend's one
  endpoint (`POST /api/run`) and renders the result. No agent logic lives
  in the browser.
- Publishing is still gated behind an explicit human-approval click in
  the UI — the backend never auto-publishes.

## Your 3-hour plan

**0:00–0:25 — Get both halves running**
- Start the backend first, confirm `/api/health` responds.
- Start the frontend, click "Run agent system" once with chaos off —
  confirm a real GDELT-sourced broadcast renders end to end.
- Flip chaos on and run it a handful of times until you've personally
  seen the retry, the Hacker News switch, and the local-fallback path
  each fire at least once. Know what each looks like before judging.

**0:25–1:00 — Make it yours**
- Swap `TOPIC_KEYWORDS` in `backend/main.py` (and the matching copy in
  `src/api.js`) if "AI / Crypto / Tech" isn't the story you're telling.
- Edit the masthead copy in `src/App.jsx` to name your actual hackathon
  theme in one line.

**1:00–1:30 — Screen-record a clean backup run**
- Do this early. One clean run (chaos off), one full-recovery run (chaos
  on). This is your insurance if the network is flaky during judging.

**1:30–2:15 — Polish only if the core story already works**
- Optional: deploy the backend (Render/Railway/Fly.io — anything that
  runs a long-lived Python process) and the frontend (Vercel/Netlify),
  pointing `VITE_API_BASE` at the deployed backend URL.
- Do **not** start refactoring the agent logic this late — it already
  works and is judged on behavior, not architecture.

**2:15–2:45 — Write the pitch**
- Lead with the failure story: "our system doesn't just retry a broken
  API, it recognizes the pattern and switches to a different real source"
  — say that line early, and say it exactly like that.
- One sentence per agent, ready to go: what Planner decides, what Critic
  is allowed to reject or retry, why Synthesizer stops short of
  publishing without a human.

**2:45–3:00 — Buffer**
- Reserved for whatever breaks at the last minute. Don't fill it with
  anything else.

## Files

```
backend/
  main.py            FastAPI app — all three agents, all real API calls
  requirements.txt

src/
  api.js              calls backend's /api/run, replays the log timeline
  App.jsx              the control room UI
  styles.css           the visual design
  main.jsx              React entry point
```
