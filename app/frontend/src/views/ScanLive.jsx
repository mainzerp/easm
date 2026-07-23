import { useEffect, useRef, useState } from 'react'
import { Topbar, Btn, Content, SectionHead } from '../components/ui.jsx'

const STEPS = ['Discovery', 'DNS', 'HTTP probe', 'Ports', 'Nuclei']
const STEP_MARKERS = ['[1/5]', '[2/5]', '[3/5]', '[4/5]', '[5/5]']

function detectStep(log) {
  for (let i = STEP_MARKERS.length - 1; i >= 0; i--) {
    if (log.some(l => l.includes(STEP_MARKERS[i]))) return i
  }
  return -1
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

export default function ScanLive({ onNav, scanTarget }) {
  const [log, setLog]       = useState([])
  const [done, setDone]     = useState(false)
  const [running, setRunning] = useState(false)
  const [queued, setQueued] = useState(false)
  const [target, setTarget] = useState(scanTarget || '')
  const [config, setConfig] = useState({ targets: [] })
  const termRef             = useRef(null)
  const wsRef               = useRef(null)

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(setConfig)
    fetch('/api/scan/status').then(r => r.json()).then(st => {
      if (st.running) {
        setRunning(true)
        setQueued(st.state === 'queued')
        setTarget(st.target || '')
        connectWs()
      }
    })
    return () => wsRef.current?.close()
  }, [])

  // Auto-scroll terminal
  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [log])

  // If scanTarget passed in from Dashboard, start immediately
  useEffect(() => {
    if (scanTarget) triggerScan(scanTarget === '__all__' ? '' : scanTarget)
  }, [scanTarget])

  function connectWs() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/scan`)
    wsRef.current = ws
    ws.onmessage = e => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'log') setLog(prev => [...prev, msg.line])
      if (msg.type === 'done') { setDone(true); setRunning(false) }
    }
    ws.onerror = () => setLog(prev => [...prev, '[WS] Verbindung unterbrochen'])
  }

  function triggerScan(t) {
    const tgt = t !== undefined ? t : target
    setLog([])
    setDone(false)
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
        if (res.status === 'domain_conflict') {
          setLog(prev => [...prev, `[conflict] Scan für ${res.domains?.join(', ')} läuft bereits`])
        }
        connectWs()
      })
  }

  function cancelScan() {
    fetch('/api/scan/cancel', { method: 'POST' })
      .then(() => setLog(prev => [...prev, '[cancel] Abbruch angefordert...']))
  }

  const currentStep = detectStep(log)

  return (
    <>
      <Topbar title="Scan">
        {running && (
          <Btn variant="danger" onClick={cancelScan}>
            <i className="ti ti-player-stop" aria-hidden /> Abbrechen
          </Btn>
        )}
        <Btn onClick={() => onNav('dashboard')}>
          <i className="ti ti-arrow-left" aria-hidden /> Dashboard
        </Btn>
        {done && (
          <Btn variant="primary" onClick={() => onNav('findings')}>
            Findings ansehen <i className="ti ti-arrow-right" aria-hidden />
          </Btn>
        )}
      </Topbar>

      <Content>
        {/* Target selector (nur wenn kein Scan läuft) */}
        {!running && !done && (
          <div style={{ maxWidth: 500, marginBottom: 24 }}>
            <SectionHead>Ziel</SectionHead>
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
                <i className="ti ti-player-play" aria-hidden /> Starten
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
                  >Alle scannen</button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Status header */}
        {(running || done) && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              {running
                ? <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: 'var(--teal)', animation: 'pulse 1.8s ease-in-out infinite' }} />
                : <i className="ti ti-circle-check" style={{ color: 'var(--teal)', fontSize: 18 }} aria-hidden />
              }
              <span style={{ fontSize: 14, fontWeight: 500 }}>
                {running
                  ? (queued ? `In Queue: ${target || 'Alle Targets'}...` : `Scanne ${target || 'Alle Targets'}...`)
                  : `Scan abgeschlossen — ${target || 'Alle Targets'}`}
              </span>
            </div>

            {/* Step progress */}
            <div style={{ display: 'flex', gap: 6 }}>
              {STEPS.map((step, i) => {
                const past    = i < currentStep
                const current = i === currentStep
                const future  = i > currentStep
                return (
                  <div key={step} style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    padding: '4px 10px', borderRadius: 20,
                    fontSize: 11, border: '0.5px solid',
                    background: past    ? 'var(--sev-low-bg)'
                               : current ? 'var(--sev-high-bg)'
                               : 'transparent',
                    borderColor: past    ? 'var(--sev-low-border)'
                                : current ? 'var(--sev-high-border)'
                                : 'var(--border)',
                    color: past    ? 'var(--sev-low-fg)'
                          : current ? 'var(--sev-high-fg)'
                          : 'var(--text3)',
                  }}>
                    {past    && <i className="ti ti-check" style={{ fontSize: 11 }} aria-hidden />}
                    {current && running && <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--sev-high-fg)', animation: 'pulse 1.2s ease-in-out infinite' }} />}
                    {step}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Terminal */}
        {(running || done || log.length > 0) && (
          <>
            <SectionHead>Log</SectionHead>
            <div
              ref={termRef}
              style={{
                background: '#0d1117', borderRadius: 'var(--radius)',
                border: '0.5px solid var(--border)',
                padding: '12px 14px', fontFamily: 'var(--font-mono)',
                fontSize: 12, lineHeight: 1.8,
                maxHeight: 380, overflowY: 'auto',
              }}
            >
              {log.length === 0 && (
                <span style={{ color: '#484f58' }}>Warte auf Output...</span>
              )}
              {log.map((line, i) => (
                <div key={i} style={{ color: lineClass(line) }}>
                  {line}
                </div>
              ))}
              {running && (
                <span style={{ color: 'var(--teal)', animation: 'blink 1s step-end infinite' }}>█</span>
              )}
            </div>
          </>
        )}
      </Content>

      <style>{`
        @keyframes pulse  { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.75)} }
        @keyframes blink  { 0%,100%{opacity:1} 50%{opacity:0} }
      `}</style>
    </>
  )
}
