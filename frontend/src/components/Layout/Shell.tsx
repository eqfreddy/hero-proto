// frontend/src/components/Layout/Shell.tsx
import { useEffect, useRef } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { NavBar } from './NavBar'
import { CurrencyBar } from './CurrencyBar'
import { ToastContainer } from '../Toast'
import { AgeGate } from '../AgeGate'
import { VersionTag } from '../VersionTag'
import { QuestWidget } from '../QuestWidget'
import { PendingArenaReward } from '../PendingArenaReward'
import { useAuthStore } from '../../store/auth'
import { initPush } from '../../api/push'

const PUBLIC_PATHS = new Set(['/app/login', '/app/privacy', '/app/terms'])

const V2_PATH_PREFIXES = [
  '/app/lobby',
  '/app/summon',
  '/app/roster',
  '/app/battle-v2',
  '/app/summon-v2',
  '/app/roster-v2',
]

function isV2Route(pathname: string): boolean {
  // /app/roster has child routes (/:heroId, /legacy). Only the index
  // and direct v2 routes get compact chrome; the hero detail page
  // benefits from the full nav.
  if (pathname === '/app/roster' || pathname === '/app/roster/') return true
  if (pathname.startsWith('/app/roster/')) return false
  if (pathname.startsWith('/app/summon/legacy')) return false
  return V2_PATH_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))
}

export function Shell() {
  const jwt = useAuthStore((s) => s.jwt)
  const location = useLocation()
  const pushInitialized = useRef(false)

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

  const v2 = isV2Route(location.pathname)

  return (
    <AgeGate>
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        <NavBar compact={v2} />
        {!v2 && <CurrencyBar />}
        <main
          className="main-content"
          style={
            v2
              ? { padding: 0, width: '100%', flex: 1 }
              : { padding: 18, maxWidth: 1100, margin: '0 auto', width: '100%', flex: 1 }
          }
        >
          <Outlet />
        </main>
        <ToastContainer />
        {!v2 && <QuestWidget />}
        <PendingArenaReward />
        <VersionTag />
      </div>
    </AgeGate>
  )
}
