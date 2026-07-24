import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor, cleanup } from '@testing-library/react'
import ScanLive from '../views/ScanLive.jsx'

class MockWebSocket {
  static instances = []
  constructor(url) {
    this.url = url
    this.readyState = 0
    MockWebSocket.instances.push(this)
  }
  close() {
    this.readyState = 3
    if (this.onclose) this.onclose()
  }
  open() {
    this.readyState = 1
    if (this.onopen) this.onopen()
  }
  message(data) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(data) })
  }
}

function fetchMock(routes) {
  return vi.fn((url) => {
    const u = String(url)
    for (const [prefix, payload] of routes) {
      if (u.startsWith(prefix)) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(payload) })
      }
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  })
}

beforeEach(() => {
  MockWebSocket.instances = []
  vi.stubGlobal('WebSocket', MockWebSocket)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ScanLive', () => {
  it('renders server-driven phases and counters, connects with scan_id, clears timeline on done', async () => {
    vi.stubGlobal('fetch', fetchMock([
      ['/api/config', { targets: [] }],
      ['/api/scan/status', { running: true, state: 'running', target: 'example.com', id: 42 }],
    ]))

    render(<ScanLive onNav={() => {}} />)

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1))
    const ws = MockWebSocket.instances[0]
    expect(ws.url).toContain('/ws/scan')
    expect(ws.url).toContain('scan_id=42')

    act(() => {
      ws.message({ type: 'phase', phase: 'subfinder', title: 'Subdomain Discovery', status: 'queued', seq: 1, total: 2, elapsed_ms: null, reason: null, error: null })
      ws.message({ type: 'phase', phase: 'dnsx', title: 'DNS Resolution', status: 'queued', seq: 2, total: 2, elapsed_ms: null, reason: null, error: null })
    })
    expect(screen.getByText('Subdomain Discovery')).toBeTruthy()
    expect(screen.getByText('DNS Resolution')).toBeTruthy()

    act(() => {
      ws.message({ type: 'phase', phase: 'subfinder', title: 'Subdomain Discovery', status: 'done', seq: 1, total: 2, elapsed_ms: 1234, reason: null, error: null })
      ws.message({ type: 'phase', phase: 'dnsx', title: 'DNS Resolution', status: 'running', seq: 2, total: 2, elapsed_ms: null, reason: null, error: null })
    })
    expect(screen.getByText('1.2s')).toBeTruthy()

    act(() => {
      ws.message({ type: 'counter', counters: { subdomains: 12, resolved: 10, http: 5, findings: 0 } })
    })
    expect(screen.getByText('Subdomains')).toBeTruthy()
    expect(screen.getByText('12')).toBeTruthy()
    expect(screen.getByText('HTTP services')).toBeTruthy()

    act(() => { ws.message({ type: 'log', line: 'some output' }) })
    expect(screen.getByText('some output')).toBeTruthy()

    expect(screen.getByText('Cancel')).toBeTruthy()
    expect(screen.queryByText(/Abbrechen/)).toBeNull()
    expect(screen.queryByText(/Scanne/)).toBeNull()

    expect(screen.getByTestId('phase-timeline')).toBeTruthy()
    act(() => { ws.message({ type: 'done', date: '2026-07-23_10-00-00', status: 'done' }) })
    expect(screen.queryByTestId('phase-timeline')).toBeNull()
    expect(screen.getByTestId('scan-summary')).toBeTruthy()
    expect(screen.getAllByText('View findings').length).toBeGreaterThan(0)
    expect(screen.getByText(/Scan finished/)).toBeTruthy()
  })

  it('shows failed status in completion summary', async () => {
    vi.stubGlobal('fetch', fetchMock([
      ['/api/config', { targets: [] }],
      ['/api/scan/status', { running: true, state: 'running', target: 'example.com', id: 7 }],
    ]))

    render(<ScanLive onNav={() => {}} />)
    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1))
    const ws = MockWebSocket.instances[0]

    act(() => { ws.message({ type: 'done', date: '2026-07-23_10-00-00', status: 'failed' }) })
    expect(screen.getByTestId('scan-summary')).toBeTruthy()
    expect(screen.getByText(/Scan failed/)).toBeTruthy()
  })

  it('triggers a scan and connects WS with id from trigger response', async () => {
    const fm = fetchMock([
      ['/api/config', { targets: [] }],
      ['/api/scan/status', { running: false, state: 'idle', id: null }],
      ['/api/scan/trigger', { status: 'queued', id: 77 }],
    ])
    vi.stubGlobal('fetch', fm)

    render(<ScanLive onNav={() => {}} scanTarget={null} />)

    const input = await screen.findByPlaceholderText('domain.tld')
    fireEvent.change(input, { target: { value: 'example.org' } })
    fireEvent.click(screen.getByText('Start'))

    await waitFor(() => expect(MockWebSocket.instances.length).toBe(1))
    expect(MockWebSocket.instances[0].url).toContain('scan_id=77')
    const triggerCalls = fm.mock.calls.filter(c => String(c[0]).startsWith('/api/scan/trigger'))
    expect(triggerCalls.length).toBe(1)

    expect(screen.getByText('Cancel')).toBeTruthy()
    expect(screen.queryByText(/Starten/)).toBeNull()
  })
})
