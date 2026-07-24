import { useEffect, useRef, useState } from 'react'
import { Topbar, Btn, Content, SectionHead } from '../components/ui.jsx'
import LogTerminal from '../components/LogTerminal.jsx'

const TAILS = [100, 500, 1000]
const LEVELS = ['', 'info', 'warning', 'error']
const SERVICE_COLORS = ['var(--teal)', 'var(--blue)', 'var(--amber)', 'var(--green)', 'var(--red)']

const selectStyle = {
  padding: '6px 8px', fontSize: 12,
  background: 'var(--bg2)', border: '0.5px solid var(--border2)',
  borderRadius: 'var(--radius)', color: 'var(--text)', outline: 'none',
}

function serviceColor(name, services) {
  const i = services.findIndex(s => s.name === name)
  return SERVICE_COLORS[(i >= 0 ? i : 0) % SERVICE_COLORS.length]
}

export default function Logs() {
  const [services, setServices] = useState([])
  const [selected, setSelected] = useState(null)
  const [level, setLevel]       = useState('')
  const [substr, setSubstr]     = useState('')
  const [tail, setTail]         = useState(100)
  const [since, setSince]       = useState('')
  const [until, setUntil]       = useState('')
  const [lines, setLines]       = useState([])
  const [live, setLive]         = useState(false)
  const [scans, setScans]       = useState([])
  const [scanDate, setScanDate] = useState('')
  const [scanLog, setScanLog]   = useState(null)
  const wsRef                   = useRef(null)
  const mountedRef              = useRef(true)
  const liveRef                 = useRef(false)
  const attemptsRef             = useRef(0)
  const timerRef                = useRef(null)
  const selectedRef             = useRef([])
  const tailRef                 = useRef(100)

  useEffect(() => {
    mountedRef.current = true
    fetch('/api/logs/services')
      .then(r => r.json())
      .then(list => {
        const arr = Array.isArray(list) ? list : []
        setServices(arr)
        const names = arr.map(s => s.name)
        selectedRef.current = names
        setSelected(names)
      })
      .catch(() => setServices([]))
    fetch('/api/scans')
      .then(r => r.json())
      .then(d => setScans(Array.isArray(d) ? d : []))
      .catch(() => {})
    return () => {
      mountedRef.current = false
      clearTimeout(timerRef.current)
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close() }
    }
  }, [])

  useEffect(() => {
    if (selected === null) return
    if (live) {
      attemptsRef.current = 0
      connectLive()
    } else {
      fetchHistory()
    }
  }, [selected, live])

  function toggleService(name) {
    setSelected(prev => {
      const next = prev.includes(name) ? prev.filter(x => x !== name) : [...prev, name]
      selectedRef.current = next
      return next
    })
  }

  function fetchHistory() {
    const names = selectedRef.current
    if (!names.length) { setLines([]); return }
    const params = new URLSearchParams()
    params.set('tail', tailRef.current)
    if (level) params.set('level', level)
    if (substr) params.set('lines', substr)
    if (since) params.set('since', Math.floor(new Date(since).getTime() / 1000))
    if (until) params.set('until', Math.floor(new Date(until).getTime() / 1000))
    const qs = params.toString()
    Promise.all(names.map(name =>
      fetch(`/api/logs/${name}?${qs}`)
        .then(r => r.json())
        .then(d => (d.lines || []).map(l => ({ ...l, service: l.service || d.service || name })))
        .catch(() => [])
    )).then(results => {
      setLines(results.flat().sort((a, b) => (a.ts ?? 0) - (b.ts ?? 0)))
    })
  }

  function connectLive() {
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close() }
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const params = new URLSearchParams()
    if (selectedRef.current.length) params.set('services', selectedRef.current.join(','))
    params.set('tail', tailRef.current)
    const ws = new WebSocket(`${proto}://${location.host}/ws/logs?${params}`)
    wsRef.current = ws
    ws.onopen = () => { attemptsRef.current = 0; setLines([]) }
    ws.onmessage = e => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'service_log') {
        setLines(prev => [...prev, { service: msg.service, ts: msg.ts, line: msg.line, level: msg.level }])
      }
    }
    ws.onclose = () => {
      if (!mountedRef.current || !liveRef.current) return
      const delay = Math.min(1000 * 2 ** attemptsRef.current, 10000)
      attemptsRef.current += 1
      timerRef.current = setTimeout(() => {
        if (mountedRef.current && liveRef.current) connectLive()
      }, delay)
    }
  }

  function toggleLive() {
    const next = !live
    liveRef.current = next
    if (!next && wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setLive(next)
  }

  function loadScanLog(date) {
    setScanDate(date)
    if (!date) { setScanLog(null); return }
    setScanLog('')
    fetch(`/api/scans/${date}/log`)
      .then(r => r.json())
      .then(d => setScanLog(typeof d.log === 'string' ? d.log : ''))
      .catch(() => setScanLog(''))
  }

  const termLines = lines.map(l => ({ ...l, text: l.line, prefix: l.service ? `[${l.service}]` : null }))

  return (
    <>
      <Topbar title="Logs">
        <Btn variant={live ? 'danger' : 'default'} onClick={toggleLive}>
          <i className={`ti ${live ? 'ti-player-stop' : 'ti-player-play'}`} aria-hidden />
          {live ? 'Stop live tail' : 'Live tail'}
        </Btn>
      </Topbar>

      <Content>
        <SectionHead>Service logs</SectionHead>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {services.length === 0 && (
            <span style={{ fontSize: 12, color: 'var(--text3)' }}>No services found</span>
          )}
          {services.map(s => {
            const active = !!selected?.includes(s.name)
            return (
              <button
                key={s.name}
                onClick={() => toggleService(s.name)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '4px 12px', fontSize: 12, borderRadius: 20,
                  border: `0.5px solid ${active ? 'var(--teal)' : 'var(--border2)'}`,
                  background: active ? 'var(--teal-soft-bg)' : 'transparent',
                  color: active ? 'var(--teal)' : 'var(--text2)',
                  cursor: 'pointer', fontFamily: 'var(--font-mono)',
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: serviceColor(s.name, services) }} aria-hidden />
                {s.name}
              </button>
            )
          })}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <select aria-label="Level" style={selectStyle} value={level} onChange={e => setLevel(e.target.value)} disabled={live}>
            {LEVELS.map(v => <option key={v} value={v}>{v || 'all levels'}</option>)}
          </select>
          <input
            aria-label="Substring"
            style={{ ...selectStyle, fontFamily: 'var(--font-mono)', width: 180 }}
            placeholder="contains..."
            value={substr}
            onChange={e => setSubstr(e.target.value)}
            disabled={live}
          />
          <select
            aria-label="Tail"
            style={selectStyle}
            value={tail}
            onChange={e => { const v = Number(e.target.value); setTail(v); tailRef.current = v }}
          >
            {TAILS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <input aria-label="Since" type="datetime-local" style={selectStyle} value={since} onChange={e => setSince(e.target.value)} disabled={live} />
          <input aria-label="Until" type="datetime-local" style={selectStyle} value={until} onChange={e => setUntil(e.target.value)} disabled={live} />
          <Btn size="sm" onClick={fetchHistory} disabled={live}>Apply</Btn>
        </div>

        <LogTerminal
          lines={termLines}
          lineColor={l => serviceColor(l.service, services)}
          running={live}
          placeholder="No log lines"
          maxHeight={320}
        />

        <div style={{ marginTop: 24 }}>
          <SectionHead>Scan log</SectionHead>
          <div style={{ marginBottom: 12 }}>
            <select
              aria-label="Scan"
              style={{ ...selectStyle, minWidth: 280 }}
              value={scanDate}
              onChange={e => loadScanLog(e.target.value)}
            >
              <option value="">Select a scan...</option>
              {scans.map(s => (
                <option key={s.date} value={s.date}>
                  {s.date}{s.target ? ` — ${s.target}` : ''}{s.status ? ` (${s.status})` : ''}
                </option>
              ))}
            </select>
          </div>
          {scanLog !== null && (
            <LogTerminal lines={scanLog.split('\n')} maxHeight={320} placeholder="Empty log" />
          )}
        </div>
      </Content>
    </>
  )
}
