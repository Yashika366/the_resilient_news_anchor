README Content
# 📡 The Resilient News Anchor
## Overview

A multi-agent system that compiles a live news brief on any topic while surviving real-world API failures — timeouts, malformed responses, dead endpoints — without collapsing. Built for Escape Velocity 1.0 (AI Hackathon), Problem Statement P-03: Multi-Agent Systems — Systems That Plan, Delegate and Recover.

Most multi-agent demos work only on the happy path and break the moment a real API misbehaves. This project is built around the opposite assumption: failure is expected, and the interesting engineering is in how the system recovers, not in how many agents it has.

## Problem It Solves

Free/public news and data APIs are unreliable — they time out, change schema, or return junk. A naive integration either crashes or silently shows nothing. This system decomposes "get me current news on X" into a pipeline that plans the fetch, critically reviews what comes back (both for structural validity and content quality), recovers through multiple real fallback paths, and only ever publishes with a human's explicit sign-off.

## Architecture

### Agent 1 — Planner & Tool-Caller

Decomposes the user's topic into a real search query
Calls GDELT (a live, keyless, global news search API covering any topic, not just tech)
Under "Inject Chaos," deliberately triggers one of three genuine failure types: a dead endpoint (real HTTP error), a forced timeout (real Timeout exception), or a truncated response (real JSON parse error)
Measures and logs actual latency — never estimated

### Agent 2 — Critic & Recovery Agent

If the Planner fails: retries the same source once, and if that fails too, switches to a second real, independent tool (Hacker News API) before ever touching local mock data — genuine tool selection under uncertainty, not blind retrying
Independently of where the data came from, runs a content-quality pass that can outright reject items matching promotional patterns (e.g. "click here," "subscribe now," "!!!") — using word-boundary matching so it doesn't false-flag legitimate words like "wholesale"
This is the "critic that can actually reject work," not a rubber-stamp pass-through

### Agent 3 — Synthesizer & Auditor

Formats the approved data into a broadcast draft
Logs the total measured cost of the run (steps used, total latency)
Deliberately stops short of publishing — treats "going live" as an irreversible action requiring a human's explicit approval click, logged in the same audit trail
Key Engineering Features
Real tool calls, not mocks — GDELT and Hacker News are live, unpredictable, external APIs
Genuine failure injection — chaos mode causes real network/parsing failures, not scripted exceptions
Two-tier real recovery — retry same source → switch to alternate real source → local fallback, only as a last resort
Content-quality gate — structural success doesn't guarantee publishable content; the critic checks both
Auditable trace — every agent action is logged with a timestamp, what happened, and why the agent chose that action
Enforced stopping condition — a hard step-limit per run prevents runaway execution
Human-in-the-loop gate — no output reaches "published" state without explicit human approval
Custom topic support — not locked to preset categories; works on any topic + keyword set

## Tech Stack

Frontend: React (Vite)
Backend: FastAPI (Python)
Real APIs: GDELT Doc 2.0 API (primary), Hacker News Firebase API (secondary fallback)
No API keys required for either data source
## Use Cases
Newsroom resilience tooling — a real pattern for any team building on top of unreliable third-party feeds who needs guaranteed uptime for a downstream product
General template for resilient agentic pipelines — the Planner/Critic/Synthesizer pattern generalizes to any task needing decomposition + real tool use + recovery (customer support, data aggregation, monitoring dashboards)
Content moderation layer — the critic's rejection logic demonstrates a reusable pattern for filtering low-quality/promotional content before it reaches an end user
Educational demo of agentic resilience engineering — a teaching example of why "it works in the demo" isn't the same as "it survives production," specifically for hackathon judges evaluating engineering maturity over feature count
Setup
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd resilient-news-anchor
npm install
npm run dev

## Known Limitations / Honest Disclosures

GDELT's search latency varies; a timespan restriction and generous timeout are set to mitigate this, but it is a public, best-effort service with no uptime SLA
Hacker News, as a tech/startup-focused source, may return few or no matches for non-tech topics — in that case the system correctly falls through to local data rather than fabricating a result
Promotional-content detection is keyword/heuristic-based, not a trained classifier — a deliberate scope choice for a 3-hour build
CORS: the frontend calls both APIs directly from the browser; this is fine for a hackathon demo but would need a backend proxy for a production deployment