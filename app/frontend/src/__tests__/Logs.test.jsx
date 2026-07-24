import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import Logs from '../views/Logs.jsx'

const SERVICES = [
  { name: 'backend', container: 'easm-backend', status: 'running' },
  { name: 'worker', container: 'easm-worker', status: 'running' },
]

function makeFetch(calls) {
  return vi.fn((url) => {
    const u = String(url)
    if (u.startsWith('/api/logs/services')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(SERVICES) })
    }
    if (u.startsWith('/api/logs/backend')) {
      calls.push(u)
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ service: 'backend', lines: [{ ts: 2, stream: 'stdout', line: 'backend line', level: 'info' }] }),
      })
    }
    if (u.startsWith('/api/logs/worker')) {
      calls.push(u)
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ service: 'worker', lines: [{ ts: 1, stream: 'stdout', line: 'worker line', level: 'warning' }] }),
      })
    }
    if (u.startsWith('/api/scans')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ date: '2026-07-23_10-00-00', target: 'example.com', status: 'done' }]),
      })
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
  })
}

let calls

beforeEach(() => {
  calls = []
  vi.stubGlobal('fetch', makeFetch(calls))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Logs', () => {
  it('renders service chips and merged log lines', async () => {
    render(<Logs />)

    await waitFor(() => expect(screen.getByText('backend')).toBeTruthy())
    expect(screen.getByText('worker')).toBeTruthy()

    await waitFor(() => expect(screen.getByText('backend line')).toBeTruthy())
    expect(screen.getByText('worker line')).toBeTruthy()
    expect(screen.getByText('[backend]')).toBeTruthy()
    expect(screen.getByText('[worker]')).toBeTruthy()
  })

  it('issues history requests with expected query params when filters applied', async () => {
    render(<Logs />)

    await waitFor(() => expect(calls.length).toBe(2))
    expect(calls.some(u => u.includes('/api/logs/backend') && u.includes('tail=100'))).toBe(true)
    calls.length = 0

    fireEvent.change(screen.getByLabelText('Tail'), { target: { value: '500' } })
    fireEvent.change(screen.getByLabelText('Level'), { target: { value: 'error' } })
    fireEvent.change(screen.getByLabelText('Substring'), { target: { value: 'foo' } })
    fireEvent.click(screen.getByText('Apply'))

    await waitFor(() => expect(calls.length).toBeGreaterThan(0))
    const hit = calls.find(u => u.includes('/api/logs/backend'))
    expect(hit).toContain('tail=500')
    expect(hit).toContain('level=error')
    expect(hit).toContain('lines=foo')
  })

  it('refetches only selected services when a chip is toggled off', async () => {
    render(<Logs />)

    await waitFor(() => expect(calls.length).toBe(2))
    calls.length = 0

    fireEvent.click(screen.getByText('worker'))

    await waitFor(() => expect(calls.length).toBe(1))
    expect(calls[0]).toContain('/api/logs/backend')
    expect(calls[0]).not.toContain('/api/logs/worker')
  })
})
