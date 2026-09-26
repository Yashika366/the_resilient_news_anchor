"""
The Resilient News Anchor — FastAPI backend
Same Planner / Critic / Synthesizer multi-agent pipeline as the original
Streamlit app.py, exposed as a JSON API for the React frontend.

Run with:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""

import json
import random
import re
import time
from datetime import datetime
from typing import List, Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_BAD_URL = "https://api.gdeltproject.org/api/v2/doc/nonexistent_endpoint"
HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

TOPIC_KEYWORDS = {
    "AI": ["ai", "gpt", "llm", "model", "openai", "machine learning", "neural"],
    "Crypto": ["crypto", "bitcoin", "ethereum", "blockchain", "token", "coin"],
    "Tech": ["tech", "chip", "software", "app", "startup", "browser", "cloud"],
}

FALLBACK_SOURCE = {
    "AI": [
        "[Fallback] Open-source model release matches frontier benchmarks.",
        "[Fallback] University lab publishes new alignment research.",
        "🔥 LIMITED TIME: Subscribe now for 50% off AI newsletter!!!",
    ],
    "Crypto": [
        "[Fallback] Layer-2 network reports record daily transactions.",
        "[Fallback] Central bank pilots a wholesale digital currency.",
        "CLICK HERE for the #1 crypto trading secret brokers hate!!!",
    ],
    "Tech": [
        "[Fallback] Chipmaker previews next-gen low-power architecture.",
        "[Fallback] Browser vendor ships a privacy-focused update.",
        "SALE ENDS TONIGHT: Buy our tech course, act now!!!",
    ],
}

GENERIC_FALLBACK = [
    "[Fallback] No cached items available yet for this custom topic.",
    "[Fallback] Try again shortly — this feed hasn't been seeded with backup data.",
    "LAST CHANCE: subscribe now, limited time offer!!!",
]

PROMO_KEYWORDS = ["% off", "sale", "subscribe now", "limited time", "click here",
                   "act now", "buy now", "secret", "!!!"]


def contains_promo_keyword(item: str) -> bool:
    """
    True if `item` looks promotional. Multi-word phrases and symbol-based
    keywords ("click here", "!!!", "% off") are matched as plain substrings.
    Single words ("sale", "secret") are matched as whole words only, so a
    word like "wholesale" doesn't false-trigger on the substring "sale".
    """
    text = item.lower()
    for kw in PROMO_KEYWORDS:
        if " " in kw or kw == "!!!" or "%" in kw:
            if kw in text:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return True
    return False

MAX_STEPS = 3
STEP_TIMEOUT = 8.0

app = FastAPI(title="Resilient News Anchor API")

# Hackathon-simple CORS: allow the Vite dev server (and any origin) to call this API.
# Tighten allow_origins to your deployed frontend URL before you actually ship this anywhere.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# REQUEST / RESPONSE SHAPES
# ------------------------------------------------------------------

class RunRequest(BaseModel):
    topic: str
    keywords: List[str]
    chaosMode: bool = False


# ------------------------------------------------------------------
# SHARED STATE + LOGGING
# camelCase keys throughout so the React frontend needs no mapping.
# ------------------------------------------------------------------

def fresh_state(topic: str) -> dict:
    return {
        "task": f"Compile a live, promotion-free news brief for topic: {topic}",
        "currentAgent": None,
        "apiStatus": "IDLE",
        "isSelfHealed": False,
        "stepCount": 0,
        "stopReason": None,
        "approvalStatus": "NOT_READY",
        "logs": [],
        "latenciesMs": [],
        "filteredOut": [],
    }


def log(state: dict, emoji: str, agent: str, message: str, reasoning: Optional[str] = None):
    state["currentAgent"] = agent
    state["logs"].append({
        "ts": datetime.now().strftime("%H:%M:%S"),
        "emoji": emoji,
        "agent": agent,
        "message": message,
        "reasoning": reasoning,
    })


def push_latency(state: dict, label: str, ms: float):
    state["latenciesMs"].append({"label": label, "ms": ms})


def step_guard(state: dict) -> bool:
    state["stepCount"] += 1
    if state["stepCount"] > MAX_STEPS:
        state["stopReason"] = f"Step limit ({MAX_STEPS}) reached — pipeline halted to prevent runaway execution."
        log(state, "🛑", "Orchestrator", state["stopReason"])
        return False
    return True


# ------------------------------------------------------------------
# ALTERNATE REAL SOURCE: Hacker News
# ------------------------------------------------------------------

def fetch_hackernews_fallback(state: dict, topic: str, keywords: List[str], timeout: float) -> List[str]:
    log(state, "🔄", "Critic & Recovery",
        f"Switching real tool: querying Hacker News API as an alternate source for '{topic}'.",
        reasoning="GDELT failed twice in a row — a different, independently-hosted real API is more "
                  "likely to succeed than a third attempt on the same one.")
    start = time.perf_counter()
    resp = requests.get(HN_TOP_STORIES_URL, timeout=timeout)
    resp.raise_for_status()
    story_ids = resp.json()[:20]
    titles = []
    for sid in story_ids:
        item = requests.get(HN_ITEM_URL.format(sid), timeout=timeout).json()
        title = item.get("title", "")
        if any(kw.lower() in title.lower() for kw in keywords):
            titles.append(title)
        if len(titles) >= 5:
            break
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    push_latency(state, "Critic (alternate source: Hacker News)", elapsed_ms)
    if not titles:
        raise ValueError(f"Hacker News returned no items matching '{topic}' either.")
    log(state, "✅", "Critic & Recovery", f"Alternate source responded in {elapsed_ms}ms. {len(titles)} matching item(s) found.")
    return titles


# ------------------------------------------------------------------
# AGENT 1: PLANNER & TOOL-CALLER
# ------------------------------------------------------------------

def agent_planner(state: dict, topic: str, keywords: List[str], chaos_mode: bool) -> List[str]:
    query = " OR ".join(f'"{kw.strip()}"' if " " in kw.strip() else kw.strip()
                         for kw in keywords if kw.strip())
    log(state, "🔄", "Planner",
        f"Decomposing task -> querying GDELT global news API (real tool) for '{topic}' (query: {query}).",
        reasoning="GDELT indexes live global news across thousands of outlets in real time and needs "
                  "no API key — real current-events coverage, not a fixed tech-only feed.")

    url = GDELT_DOC_URL
    timeout = STEP_TIMEOUT
    chaos_type = None

    if chaos_mode:
        chaos_type = random.choice(["bad_endpoint", "timeout", "malformed"])
        if chaos_type == "bad_endpoint":
            url = GDELT_BAD_URL
        elif chaos_type == "timeout":
            timeout = 0.001

    params = {"query": query, "mode": "ArtList", "maxrecords": 10, "format": "json",
              "sort": "DateDesc", "timespan": "2d"}

    start = time.perf_counter()
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        raw = resp.text

        if chaos_mode and chaos_type == "malformed":
            raw = raw[: len(raw) // 3]

        payload = json.loads(raw)
        articles = payload.get("articles", [])

        titles = []
        for article in articles:
            title = article.get("title")
            if title:
                titles.append(title)
            if len(titles) >= 5:
                break

        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        push_latency(state, "Planner (primary fetch)", elapsed_ms)

        if not titles:
            titles = [f"(No live GDELT articles matched '{topic}' right now — real API, real gap.)"]

        state["apiStatus"] = "OK"
        log(state, "✅", "Planner", f"Live API responded in {elapsed_ms}ms with a valid schema. {len(titles)} matching item(s) found.")
        return titles

    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        push_latency(state, "Planner (failed attempt)", elapsed_ms)
        state["apiStatus"] = f"FAILED ({type(e).__name__})"
        log(state, "⚠️", "Planner", f"Real tool call failed after {elapsed_ms}ms — {type(e).__name__}: {e}")
        raise


# ------------------------------------------------------------------
# AGENT 2: CRITIC & RECOVERY AGENT
# ------------------------------------------------------------------

def agent_critic_recovery(state: dict, topic: str, keywords: List[str],
                           candidate_data: Optional[List[str]] = None,
                           upstream_error: Optional[Exception] = None):
    healed = False
    data = candidate_data

    if upstream_error is not None:
        log(state, "🛠️", "Critic & Recovery", f"Reviewing failure: {upstream_error}.",
            reasoning="A transient failure deserves one retry before trying a different tool.")
        log(state, "🔄", "Critic & Recovery", "Attempting one retry of the primary tool call.")
        time.sleep(0.4)
        try:
            data = agent_planner(state, topic, keywords, chaos_mode=False)
        except Exception as e:
            log(state, "⚠️", "Critic & Recovery", f"Retry also failed ({e}).",
                reasoning="Two consecutive failures on the same tool point to a source-level outage, "
                          "not a fluke — worth trying a different tool before giving up on real data entirely.")
            try:
                data = fetch_hackernews_fallback(state, topic, keywords, timeout=STEP_TIMEOUT)
                healed = True
            except Exception as e2:
                log(state, "⚠️", "Critic & Recovery",
                    f"Alternate source also failed ({e2}). Rerouting to local fallback matrix.",
                    reasoning="Both real sources are unavailable — falling back to local data is the "
                              "only remaining safe option.")
                data = FALLBACK_SOURCE.get(topic, GENERIC_FALLBACK)
                healed = True

    log(state, "🔎", "Critic & Recovery", "Reviewing content quality before approving data downstream.",
        reasoning="Structural success doesn't guarantee content is fit to publish — promotional junk must be caught too.")
    approved, rejected = [], []
    for item in data:
        if contains_promo_keyword(item):
            rejected.append(item)
        else:
            approved.append(item)

    if rejected:
        state["filteredOut"].extend(rejected)
        log(state, "❌", "Critic & Recovery", f"REJECTED {len(rejected)} item(s) as promotional content — excluded from broadcast.")
    else:
        log(state, "✅", "Critic & Recovery", "All items passed content review. Nothing rejected.")

    return approved, healed


# ------------------------------------------------------------------
# AGENT 3: SYNTHESIZER & AUDITOR
# ------------------------------------------------------------------

def agent_synthesizer(state: dict, topic: str, approved_items: List[str]) -> dict:
    log(state, "🔄", "Synthesizer", "Formatting approved data into a broadcast draft.")
    time.sleep(0.3)

    headline = f"{topic.upper()} BRIEF — {datetime.now().strftime('%b %d, %Y')}"
    total_latency = sum(l["ms"] for l in state["latenciesMs"])
    log(state, "📊", "Synthesizer", f"Run cost: {state['stepCount']} agent step(s), {total_latency:.1f}ms total measured latency.")
    log(state, "✅", "Synthesizer", "Draft sealed in audit trail. Awaiting human approval before publishing — publishing is treated as irreversible.")

    state["approvalStatus"] = "PENDING"
    return {"headline": headline, "body": approved_items or None}


# ------------------------------------------------------------------
# ORCHESTRATION
# ------------------------------------------------------------------

def run_pipeline(topic: str, keywords: List[str], chaos_mode: bool) -> dict:
    state = fresh_state(topic)

    if not step_guard(state):
        return {"state": state, "draft": {"headline": "", "body": None, "halted": True}}

    error = None
    data = None
    try:
        data = agent_planner(state, topic, keywords, chaos_mode)
    except Exception as e:
        error = e

    if not step_guard(state):
        return {"state": state, "draft": {"headline": "", "body": None, "halted": True}}

    if error is not None:
        approved, healed = agent_critic_recovery(state, topic, keywords, upstream_error=error)
    else:
        approved, healed = agent_critic_recovery(state, topic, keywords, candidate_data=data)
    state["isSelfHealed"] = healed

    if not step_guard(state):
        return {"state": state, "draft": {"headline": "", "body": None, "halted": True}}

    draft = agent_synthesizer(state, topic, approved)
    state["currentAgent"] = "Awaiting Approval"
    return {"state": state, "draft": draft}


# ------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/topics")
def topics():
    return {"topics": TOPIC_KEYWORDS, "maxSteps": MAX_STEPS}


@app.post("/api/run")
def run(req: RunRequest):
    keywords = [k.strip() for k in req.keywords if k.strip()]
    return run_pipeline(req.topic, keywords, req.chaosMode)