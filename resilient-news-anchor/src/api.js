// The React app no longer talks to GDELT/Hacker News directly — all agent
// logic (Planner, Critic & Recovery, Synthesizer) runs in the Python
// backend (backend/main.py). This file just calls that API and replays
// the returned log timeline so the wire feed still animates live.

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

// Kept in sync with backend/main.py's TOPIC_KEYWORDS by hand — small
// enough duplication for a hackathon build. If you edit one, edit both.
export const TOPIC_KEYWORDS = {
  AI: ['ai', 'gpt', 'llm', 'model', 'openai', 'machine learning', 'neural'],
  Crypto: ['crypto', 'bitcoin', 'ethereum', 'blockchain', 'token', 'coin'],
  Tech: ['tech', 'chip', 'software', 'app', 'startup', 'browser', 'cloud'],
}

export const MAX_STEPS = 3

function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms))
}

export async function runPipeline(topic, keywords, chaosMode, onUpdate) {
  const resp = await fetch(`${API_BASE}/api/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, keywords, chaosMode }),
  })

  if (!resp.ok) {
    const body = await resp.text().catch(() => '')
    throw new Error(`Backend request failed (${resp.status}): ${body || resp.statusText}`)
  }

  const { state: finalState, draft } = await resp.json()

  // The backend runs the whole pipeline before responding, so replay the
  // returned log entries one at a time here — the wire feed still reads
  // like a live console instead of dumping everything at once.
  onUpdate({ ...finalState, logs: [] })
  for (let i = 0; i < finalState.logs.length; i++) {
    onUpdate({ ...finalState, logs: finalState.logs.slice(0, i + 1) })
    await sleep(160)
  }

  return { state: finalState, draft }
}
