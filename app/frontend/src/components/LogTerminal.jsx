import { useEffect, useRef } from 'react'

export default function LogTerminal({ lines, lineColor, running = false, placeholder = 'Waiting for output...', maxHeight = 380 }) {
  const termRef = useRef(null)

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [lines])

  return (
    <div
      ref={termRef}
      style={{
        background: '#0d1117', borderRadius: 'var(--radius)',
        border: '0.5px solid var(--border)',
        padding: '12px 14px', fontFamily: 'var(--font-mono)',
        fontSize: 12, lineHeight: 1.8,
        maxHeight, overflowY: 'auto',
      }}
    >
      {lines.length === 0 && (
        <span style={{ color: '#484f58' }}>{placeholder}</span>
      )}
      {lines.map((line, i) => {
        const isObj = typeof line === 'object' && line !== null
        const text = isObj ? line.text : line
        const prefix = isObj ? line.prefix : null
        const color = lineColor ? lineColor(line) : 'var(--text2)'
        return (
          <div key={i}>
            {prefix && <span style={{ color, fontWeight: 600 }}>{prefix} </span>}
            <span style={{ color: prefix ? 'var(--text2)' : color }}>{text}</span>
          </div>
        )
      })}
      {running && (
        <span style={{ color: 'var(--teal)', animation: 'blink 1s step-end infinite' }}>█</span>
      )}
    </div>
  )
}
