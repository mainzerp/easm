import { useEffect, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import UserSettingsModal from './components/UserSettingsModal.jsx'
import Dashboard from './views/Dashboard.jsx'
import Assets from './views/Assets.jsx'
import Scans from './views/Scans.jsx'
import Findings from './views/Findings.jsx'
import Config from './views/Config.jsx'
import ScanLive from './views/ScanLive.jsx'
import Logs from './views/Logs.jsx'
import Login from './views/Login.jsx'

const VIEWS = { dashboard: Dashboard, assets: Assets, scans: Scans, findings: Findings, config: Config, scan: ScanLive, logs: Logs }

export default function App() {
  const [view, setView]           = useState('dashboard')
  const [scanTarget, setScanTarget] = useState(null)
  const [authState, setAuthState] = useState(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [theme, setTheme]         = useState(() => {
    const saved = localStorage.getItem('easm-theme')
    if (saved === 'light' || saved === 'dark') return saved
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('easm-theme', theme)
  }, [theme])

  useEffect(() => {
    fetch('/api/auth/check')
      .then(r => r.json())
      .then(setAuthState)
      .catch(() => setAuthState({ authenticated: false, totp_enabled: false }))
  }, [])

  useEffect(() => {
    const orig = window.fetch
    window.fetch = async (...args) => {
      const res = await orig(...args)
      if (res.status === 401 && !String(args[0]).includes('/api/auth/')) {
        setAuthState(a => (a && a.authenticated ? { ...a, authenticated: false } : a))
      }
      return res
    }
    return () => { window.fetch = orig }
  }, [])

  function startScan(target) {
    setScanTarget(target)
    setView('scan')
  }

  async function handleLogout() {
    try { await window.fetch('/api/auth/logout', { method: 'POST' }) } catch { /* ignore network errors */ }
    setAuthState(a => ({ authenticated: false, totp_enabled: a?.totp_enabled ?? false }))
  }

  if (authState === null) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg)', color: 'var(--text3)', fontSize: 13,
      }}>
        <i className="ti ti-loader" style={{ marginRight: 8 }} aria-hidden /> Lade...
      </div>
    )
  }

  if (!authState.authenticated) {
    return (
      <Login
        totpEnabled={authState.totp_enabled}
        onLogin={() => setAuthState(a => ({ ...a, authenticated: true }))}
      />
    )
  }

  const View = VIEWS[view] || Dashboard

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        active={view}
        onNav={setView}
        onLogout={handleLogout}
        theme={theme}
        onToggleTheme={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}
        username="admin"
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <UserSettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        totpEnabled={authState?.totp_enabled ?? false}
        onToggled={() => setAuthState(a => ({ ...a, totp_enabled: !a?.totp_enabled }))}
        onLogout={handleLogout}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <View onNav={setView} onStartScan={startScan} scanTarget={scanTarget} />
      </div>
    </div>
  )
}
