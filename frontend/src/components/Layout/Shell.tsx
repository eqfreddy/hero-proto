// frontend/src/components/Layout/Shell.tsx
import { useEffect, useRef } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { TopNav } from './TopNav'
import { PlayNav } from './PlayNav'
import { ToastContainer } from '../Toast'
import { AgeGate } from '../AgeGate'
import { VersionTag } from '../VersionTag'
import { QuestWidget } from '../QuestWidget'
import { PendingArenaReward } from '../PendingArenaReward'
import { useAuthStore } from '../../store/auth'
import { useMe } from '../../hooks/useMe'
import { initPush } from '../../api/push'
import './Chrome.css'

const PUBLIC_PATHS = new Set(['/app/login', '/app/privacy', '/app/terms'])

// Routes that take over the full viewport (no shared chrome).
// Battle play / replay etc render their own UI.
function isImmersiveRoute(pathname: string): boolean {
  if (pathname.startsWith('/battle/')) return true
  return false
}

export function Shell() {
  const jwt = useAuthStore((s) => s.jwt)
  const location = useLocation()
  const pushInitialized = useRef(false)
  const { data: me } = useMe()

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

  // Login / legal: bare shell, no chrome.
  if (PUBLIC_PATHS.has(location.pathname) || isImmersiveRoute(location.pathname)) {
    return (
      <AgeGate>
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
          <main style={{ flex: 1 }}>
            <Outlet />
          </main>
          <ToastContainer />
          <VersionTag />
        </div>
      </AgeGate>
    )
  }

  const faction = me?.faction ?? 'RESISTANCE'

  return (
    <AgeGate>
      <div
        className="chrome-root"
        data-faction={faction}
        style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--c-bg)' }}
      >
        <TopNav />
        <main className="chrome-main">
          <Outlet />
        </main>
        <PlayNav />
        <ToastContainer />
        <QuestWidget />
        <PendingArenaReward />
        <VersionTag />
      </div>
    </AgeGate>
  )
}
