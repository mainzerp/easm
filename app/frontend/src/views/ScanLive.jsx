import { useEffect, useRef, useState } from 'react'
import { Topbar, Btn, Content, SectionHead, StatCard } from '../components/ui.jsx'
import LogTerminal from '../components/LogTerminal.jsx'

const COUNTER_LABELS = [
  ['subdomains', 'Subdomains'],
  ['resolved', 'Resolved'],
  ['http', 'HTTP services'],
  ['findings', 'Findings'],
]

const DONE_TEXT = { done: 'Scan finished', failed: 'Scan failed', canceled: 'Scan canceled' }
const DONE_COLOR = { done: 'var(--teal)', failed: 'var(--red)', canceled: 'var(--amber)' }

const PHASE_COLOR = {
  queued: 'var(--text3)',
  running: 'var(--text)',
  done: 'var(--text2)',
  failed: 'var(--red)',
  skipped: 'var(--amber)',
}

function lineClass(line) {
  if (line.includes('===') || line.includes('complete') || line.includes('Done'))
    return 'var(--teal)'
  if (line.includes('Warning') || line.includes('WARN'))
    return 'var(--amber)'
  if (line.includes('ERR') || line.includes('error') || line.includes('canceled'))
    return 'var(--red)'
  return 'var(--text2)'
}

function formatElapsed(ms) {
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

function PhaseIcon({ status }) {
  if (status === 'running')
    return <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', animation: 'pulse 1.2s ease-in-out infinite' }} aria-hidden />
  if (status === 'done')
    return <i className="ti ti-check" style={{ color: 'var(--teal)', fontSize: 13 }} aria-hidden />
  if (status === 'failed')
    return <i className="ti ti-x" style={{ color: 'var(--red)', fontSize: 13 }} aria-hidden />
  if (status === 'skipped')
    return <i className="ti ti-minus" style={{ color: 'var(--amber)', fontSize: 13 }} aria-hidden />
  return <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', border: '1.5px solid var(--text3)' }} aria-hidden />
}

export default function ScanLive({ onNav, scanTarget }) {
  const [log, setLog]         = useState([])
  const [phases, setPhases]   = useState([])
  const [counters, setCounters] = useState(null)
  const [done, setDone]       = useState(false)
  const [doneStatus, setDoneStatus] = useState('done')
  const [running, setRunning] = useState(false)
  const [queued, setQueued]   = useState(false)
  const [target, setTarget]   = useState(scanTarget || '')
  const [config, setConfig]   = useState({ targets: [] })
  const wsRef                 = useRef(null)
  const scanIdRef             = useRef(null)
  const doneRef               = useRef(false)
  const mountedRef            = useRef(true)
  const attemptsRef           = useRef(0)
  const timerRef              = useRef(null)

  useEffect(() => {
    mountedRef.current = true
    fetch('/api/config').then(r => r.json()).then(setConfig)
    fetch('/api/scan/status').then(r => r.json()).then(st => {
      if (st.id != null) scanIdRef.current = st.id
      if (st.running) {
        setRunning(true)
        setQueued(st.state === 'queued')
        setTarget(st.target || '')
        connectWs()
      }
    })
    return () => {
      mountedRef.current = false
      clearTimeout(timerRef.current)
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close() }
    }
  }, [])

  // If scanTarget passed in from Dashboard, start immediately
  useEffect(() => {
    if (scanTarget) triggerScan(scanTarget === '__all__' ? '' : scanTarget)
  }, [scanTarget])

  function resetFeed() {
    setLog([])
    setPhases([])
    setCounters(null)
  }

  function connectWs() {
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close() }
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const qs = scanIdRef.current != null ? `?scan_id=${scanIdRef.current}` : ''
    const ws = new WebSocket(`${proto}://${location.host}/ws/scan${qs}`)
    wsRef.current = ws
    ws.onopen = () => {
      attemptsRef.current = 0
      resetFeed()
    }
    ws.onmessage = e => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'log') {
        setLog(prev => [...prev, msg.line])
      } else if (msg.type === 'phase') {
        setPhases(prev => {
          const next = prev.filter(p => p.key !== msg.phase)
          next.push({
            key: msg.phase,
            title: msg.title,
            status: msg.status,
            elapsed_ms: msg.elapsed_ms,
            reason: msg.reason,
            seq: msg.seq ?? prev.length + 1,
          })
          next.sort((a, b) => a.seq - b.seq)
          return next
        })
      } else if (msg.type === 'counter') {
        setCounters(msg.counters)
      } else if (msg.type === 'status') {
        if (msg.status === 'running') { setRunning(true); setQueued(false) }
      } else if (msg.type === 'done') {
        doneRef.current = true
        setDone(true)
        setDoneStatus(msg.status || 'done')
        setRunning(false)
        setQueued(false)
      }
    }
    ws.onerror = () => setLog(prev => [...prev, '[WS] Connection lost'])
    ws.onclose = () => {
      if (!mountedRef.current || doneRef.current) return
      const delay = Math.min(1000 * 2 ** attemptsRef.current, 10000)
      attemptsRef.current += 1
      timerRef.current = setTimeout(() => {
        if (mountedRef.current && !doneRef.current) connectWs()
      }, delay)
    }
  }

  function triggerScan(t) {
    const tgt = t !== undefined ? t : target
    doneRef.current = false
    setLog([])
    setPhases([])
    setCounters(null)
    setDone(false)
    setDoneStatus('done')
    setRunning(true)
    setQueued(true)
    setTarget(tgt)
    fetch('/api/scan/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: tgt }),
    })
      .then(r => r.json())
      .then(res => {
        if (res.id != null) scanIdRef.current = res.id
        if (res.status === 'domain_conflict') {
          setLog(prev => [...prev, `[conflict] Scan for ${res.domains?.join(', ')} is already running`])
        }
        connectWs()
      })
  }

  function cancelScan() {
    fetch('/api/scan/cancel', { method: 'POST' })
      .then(() => setLog(prev => [...prev, '[cancel] Cancellation requested...']))
  }

  return (
    <>
      <Topbar title="Scan">
        {running && (
          <Btn variant="danger" onClick={cancelScan}>
            <i className="ti ti-player-stop" aria-hidden /> Cancel
          </Btn>
        )}
        <Btn onClick={() => onNav('dashboard')}>
          <i className="ti ti-arrow-left" aria-hidden /> Dashboard
        </Btn>
        {done && (
          <Btn variant="primary" onClick={() => onNav('findings')}>
            View findings <i className="ti ti-arrow-right" aria-hidden />
          </Btn>
        )}
      </Topbar>

      <Content>
        {/* Target selector (only when no scan is running) */}
        {!running && !done && (
          <div style={{ maxWidth: 500, marginBottom: 24 }}>
            <SectionHead>Target</SectionHead>
            <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
              <input
                style={{
                  flex: 1, padding: '8px 10px', fontSize: 13,
                  background: 'var(--bg2)', border: '0.5px solid var(--border2)',
                  borderRadius: 'var(--radius)', color: 'var(--text)',
                  fontFamily: 'var(--font-mono)', outline: 'none',
                }}
                placeholder="domain.tld"
                value={target}
                onChange={e => setTarget(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && triggerScan()}
              />
              <Btn variant="primary" onClick={() => target && triggerScan()}>
                <i className="ti ti-player-play" aria-hidden /> Start
              </Btn>
            </div>
            {config.targets?.length > 0 && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {config.targets.map(t => (
                  <button
                    key={t}
                    onClick={() => { setTarget(t); triggerScan(t) }}
                    style={{
                      padding: '4px 10px', fontSize: 12, borderRadius: 20,
                      border: '0.5px solid var(--border2)', background: 'transparent',
                      color: 'var(--text2)', cursor: 'pointer', fontFamily: 'var(--font-mono)',
                    }}
                  >{t}</button>
                ))}
                {config.targets.length > 1 && (
                  <button
                    onClick={() => triggerScan('')}
                    style={{
                      padding: '4px 12px', fontSize: 12, borderRadius: 20,
                      border: '0.5px solid var(--teal)', background: 'transparent',
                      color: 'var(--teal)', cursor: 'pointer', fontWeight: 500,
                    }}
                  >Scan all</button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Status header */}
        {(running || done) && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {running
                ? <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', animation: 'pulse 1.8s ease-in-out infinite' }} />
                : doneStatus === 'done'
                  ? <i className="ti ti-circle-check" style={{ color: 'var(--teal)', fontSize: 18 }} aria-hidden />
                  : doneStatus === 'failed'
                    ? <i className="ti ti-circle-x" style={{ color: 'var(--red)', fontSize: 18 }} aria-hidden />
                    : <i className="ti ti-circle-minus" style={{ color: 'var(--amber)', fontSize: 18 }} aria-hidden />
              }
              <span style={{ fontSize: 14, fontWeight: 500 }}>
                {running
                  ? (queued ? `Queued: ${target || 'all targets'}...` : `Scanning ${target || 'all targets'}...`)
                  : `${DONE_TEXT[doneStatus] || DONE_TEXT.done} — ${target || 'all targets'}`}
              </span>
            </div>
          </div>
        )}

        {/* Counters */}
        {(running || done) && counters && (
          <div data-testid="scan-counters" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 16 }}>
            {COUNTER_LABELS.map(([key, label]) => (
              <StatCard key={key} label={label} value={counters[key] ?? 0} />
            ))}
          </div>
        )}

        {/* Pipeline timeline (cleared on completion) */}
        {running && phases.length > 0 && (
          <div data-testid="phase-timeline" style={{ marginBottom: 16 }}>
            <SectionHead>Pipeline</SectionHead>
            <div className="card" style={{ padding: '6px 14px' }}>
              {phases.map(p => (
                <div
                  key={p.key}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 0', fontSize: 13,
                    color: PHASE_COLOR[p.status] || 'var(--text2)',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <span style={{ width: 16, display: 'inline-flex', justifyContent: 'center', flexShrink: 0 }}>
                    <PhaseIcon status={p.status} />
                  </span>
                  <span style={{ flex: 1, fontWeight: p.status === 'running' ? 600 : 400 }}>{p.title}</span>
                  {p.status === 'skipped' && p.reason && (
                    <span style={{ fontSize: 11, color: 'var(--text3)' }}>{p.reason}</span>
                  )}
                  {p.elapsed_ms != null && (
                    <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text3)' }}>
                      {formatElapsed(p.elapsed_ms)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Completion summary (replaces timeline) */}
        {done && (
          <div data-testid="scan-summary" className="card" style={{ padding: '16px 18px', marginBottom: 16 }}>
            <SectionHead>Summary</SectionHead>
            <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 6 }}>
              Status: <span style={{ color: DONE_COLOR[doneStatus] || 'var(--text2)', fontWeight: 600 }}>{doneStatus}</span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 12 }}>
              Target: <span style={{ fontFamily: 'var(--font-mono)' }}>{target || 'all targets'}</span>
            </div>
            <Btn variant="primary" size="sm" onClick={() => onNav('findings')}>
              View findings <i className="ti ti-arrow-right" aria-hidden />
            </Btn>
          </div>
        )}

        {/* Terminal */}
        {(running || done || log.length > 0) && (
          <>
            <SectionHead>Log</SectionHead>
            <LogTerminal lines={log} lineColor={lineClass} running={running} placeholder="Waiting for output..." />
          </>
        )}
      </Content>
    </>
  )
}
