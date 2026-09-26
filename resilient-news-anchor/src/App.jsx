import { useState, useRef } from 'react'
import { runPipeline, TOPIC_KEYWORDS, MAX_STEPS } from './api.js'

const TOPICS = Object.keys(TOPIC_KEYWORDS)

function statusInfo(state, published) {
  if (published) return { label: 'Published', tone: 'published' }
  if (state?.isSelfHealed) return { label: 'Self-Healed: True', tone: 'healed' }
  if (state?.approvalStatus === 'PENDING') return { label: 'Pending Approval', tone: 'pending' }
  if (state) return { label: 'Operational', tone: 'ok' }
  return { label: 'Standby', tone: 'idle' }
}

export default function App() {
  const [topicChoice, setTopicChoice] = useState('AI')
  const [customName, setCustomName] = useState('Space')
  const [customKw, setCustomKw] = useState('space, nasa, rocket, satellite')
  const [chaosMode, setChaosMode] = useState(false)
  const [running, setRunning] = useState(false)
  const [state, setState] = useState(null)
  const [draft, setDraft] = useState(null)
  const [published, setPublished] = useState(false)
  const [runError, setRunError] = useState(null)
  const feedEndRef = useRef(null)

  const topic = topicChoice === 'Custom' ? customName.trim() || 'Custom' : topicChoice
  const keywords =
    topicChoice === 'Custom'
      ? customKw.split(',').map((k) => k.trim()).filter(Boolean)
      : TOPIC_KEYWORDS[topicChoice]

  async function handleRun() {
    if (!keywords.length) return
    setRunning(true)
    setPublished(false)
    setDraft(null)
    setState(null)
    setRunError(null)
    try {
      const { draft: finalDraft } = await runPipeline(topic, keywords, chaosMode, (s) => {
        setState(s)
        requestAnimationFrame(() => feedEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }))
      })
      setDraft(finalDraft)
    } catch (e) {
      setRunError(e.message || 'Could not reach the backend.')
    } finally {
      setRunning(false)
    }
  }

  function handlePublish() {
    setState((prev) => ({
      ...prev,
      logs: [...prev.logs, { ts: new Date().toLocaleTimeString('en-GB'), emoji: '🧑‍⚖️', agent: 'Human', message: 'Broadcast approved and published by human operator.', reasoning: null }],
      approvalStatus: 'PUBLISHED',
    }))
    setPublished(true)
  }

  const status = statusInfo(state, published)
  const totalLatency = state?.latenciesMs?.reduce((sum, l) => sum + l.ms, 0) ?? 0

  return (
    <div className="stage">
      <header className="masthead">
        <div className="masthead-mark" aria-hidden="true" />
        <div>
          <h1>The Resilient News Anchor</h1>
          <p>Planner routes to Critic routes to Synthesizer, on real live APIs, with a human sign-off before anything airs.</p>
        </div>
      </header>

      <div className="console">
        <aside className="deck">
          <section className="deck-group">
            <h2>Topic</h2>
            <div className="topic-picker">
              {[...TOPICS, 'Custom'].map((t) => (
                <button
                  key={t}
                  className={`topic-btn ${topicChoice === t ? 'is-active' : ''}`}
                  onClick={() => setTopicChoice(t)}
                  type="button"
                >
                  {t}
                </button>
              ))}
            </div>
            {topicChoice === 'Custom' && (
              <div className="custom-fields">
                <label>
                  Topic name
                  <input value={customName} onChange={(e) => setCustomName(e.target.value)} placeholder="Space" />
                </label>
                <label>
                  Keywords, comma-separated
                  <input value={customKw} onChange={(e) => setCustomKw(e.target.value)} placeholder="space, nasa, rocket" />
                </label>
              </div>
            )}
          </section>

          <section className="deck-group">
            <h2>Chaos injection</h2>
            <button
              type="button"
              className={`chaos-switch ${chaosMode ? 'is-on' : ''}`}
              onClick={() => setChaosMode((v) => !v)}
              aria-pressed={chaosMode}
            >
              <span className="chaos-switch-track">
                <span className="chaos-switch-thumb" />
              </span>
              <span className="chaos-switch-label">{chaosMode ? 'Armed' : 'Off'}</span>
            </button>
            <p className="deck-hint">Forces a real failure on the primary source — bad endpoint, timeout, or malformed JSON.</p>
          </section>

          <button className="run-btn" onClick={handleRun} disabled={running || !keywords.length} type="button">
            {running ? 'Running…' : 'Run agent system'}
          </button>

          {runError && (
            <p className="run-error">
              {runError} — make sure the backend is running (<code>uvicorn main:app --reload --port 8000</code> inside{' '}
              <code>backend/</code>).
            </p>
          )}

          {state && (
            <div className="deck-meta">
              <div className={`status-pill tone-${status.tone}`}>{status.label}</div>
              <dl>
                <div>
                  <dt>API status</dt>
                  <dd>{state.apiStatus}</dd>
                </div>
                <div>
                  <dt>Steps used</dt>
                  <dd>
                    {state.stepCount}/{MAX_STEPS}
                  </dd>
                </div>
                <div>
                  <dt>Measured latency</dt>
                  <dd>{totalLatency.toFixed(1)}ms</dd>
                </div>
              </dl>
            </div>
          )}
        </aside>

        <main className="broadcast-column">
          <section className="on-air-screen">
            <div className="on-air-chrome">
              <span className={`on-air-dot ${published ? 'is-live' : ''}`} />
              {published ? 'On air' : draft ? 'Ready' : 'Standby'}
            </div>

            {!draft && !running && <p className="on-air-empty">Run the agent system to compile a broadcast.</p>}
            {running && !draft && <p className="on-air-empty">Compiling live broadcast…</p>}

            {draft && (
              <div className="on-air-body">
                <h2>{draft.headline}</h2>
                {draft.body ? (
                  <ul>
                    {draft.body.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="on-air-none">No items survived review.</p>
                )}
              </div>
            )}

            {state?.stopReason && <p className="stop-reason">{state.stopReason}</p>}
          </section>

          {state?.filteredOut?.length > 0 && (
            <details className="rejected">
              <summary>{state.filteredOut.length} item(s) rejected by the Critic — promotional content</summary>
              <ul>
                {state.filteredOut.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </details>
          )}

          {state?.approvalStatus === 'PENDING' && !published && (
            <div className="approval-bar">
              <p>This broadcast is not yet public. Publishing is treated as an irreversible action and needs explicit sign-off.</p>
              <button type="button" onClick={handlePublish}>
                Approve &amp; publish
              </button>
            </div>
          )}

          <section className="wire-feed" aria-label="Agent audit trail">
            <h2>Agent wire feed</h2>
            <div className="wire-lines">
              {!state?.logs?.length && <p className="wire-empty">Logs will appear here once a run starts.</p>}
              {state?.logs?.map((entry, i) => (
                <div className="wire-line" key={i}>
                  <span className="wire-ts">{entry.ts}</span>
                  <span className="wire-emoji">{entry.emoji}</span>
                  <span className="wire-agent">{entry.agent}</span>
                  <span className="wire-msg">
                    {entry.message}
                    {entry.reasoning && <em className="wire-reasoning">↳ {entry.reasoning}</em>}
                  </span>
                </div>
              ))}
              <div ref={feedEndRef} />
            </div>
          </section>
        </main>
      </div>

      <footer className="colophon">
        Agent 1 — Planner &amp; Tool-Caller (GDELT) → on failure → Agent 2 — Critic &amp; Recovery (retries, then Hacker News, then local
        fallback; rejects promotional content) → Agent 3 — Synthesizer &amp; Auditor (halts before publishing until a human approves).
      </footer>
    </div>
  )
}
