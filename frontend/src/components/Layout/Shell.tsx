// frontend/src/components/Layout/Shell.tsx
import { useEffect, useRef } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { NavBar } from './NavBar'
import { CurrencyBar } from './CurrencyBar'
import { ToastContainer } from '../Toast'
import { AgeGate } from '../AgeGate'
import { VersionTag } from '../VersionTag'
import { QuestWidget } from '../QuestWidget'
import { useAuthStore } from '../../store/auth'
import { initPush } from '../../api/push'

const PUBLIC_PATHS = new Set(['/app/login', '/app/privacy', '/app/terms'])

export function Shell() {
  const jwt = useAuthStore((s) => s.jwt)
  const location = useLocation()
  const pushInitialized = useRef(false)
  const isLobby = location.pathname === '/app/me' || location.pathname === '/app/'

  useEffect(() => {
    if (jwt && !pushInitialized.current) {
      pushInitialized.current = true
      initPush().catch(() => {/* push is non-critical */})
    }
    if (!jwt) pushInitialized.current = false
  }, [jwt])

  if (!jwt && !PUBLIC_PATHS.has(location.pathname)) {
    return <Navigate to="/app/login" replace state={{ from: location }} />
  }

  if (isLobby) {
    return (
      <AgeGate>
        <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Outlet />
          <ToastContainer />
        </div>
      </AgeGate>
    )
  }

  return (
    <AgeGate>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <NavBar />
        <CurrencyBar />
        <main className="main-content" style={{ padding: 18, maxWidth: 1100, margin: '0 auto', width: '100%', flex: 1 }}>
          <Outlet />
        </main>
        <ToastContainer />
        <QuestWidget />
        <VersionTag />
      </div>
    </AgeGate>
  )
}
