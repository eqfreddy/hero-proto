import { useEffect, useState } from 'react'

interface BackendVersion {
  version: string
  branch: string
  built_at: string
}

const FRONT_VERSION = __APP_VERSION__
const FRONT_BUILT_AT = __APP_BUILD_TIME__

/**
 * Floating version badge — bottom-right corner.
 * Shows the SPA build (local) and, on hover/tap, the backend /version too.
 * Use this to instantly see whether the running emulator app matches what
 * was just built. Color-codes when local and backend versions disagree.
 */
export function VersionTag() {
  const [open, setOpen] = useState(false)
  const [backend, setBackend] = useState<BackendVersion | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || backend || error) return
    const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
    fetch(`${base}/version`)
      .then((r) => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then((j) => setBackend(j))
      .catch((e) => setError(String(e)))
  }, [open, backend, error])

  const mismatch = backend && backend.version !== 'dev' && FRONT_VERSION !== 'dev'
    && backend.version !== FRONT_VERSION

  return (
    <div
      onClick={() => setOpen((v) => !v)}
      style={{
        position: 'fixed',
        bottom: 'calc(72px + env(safe-area-inset-bottom))',
        right: 6,
        fontSize: 9,
        fontFamily: 'ui-monospace, SFMono-Regular, monospace',
        padding: open ? '6px 10px' : '2px 7px',
        borderRadius: 4,
        background: mismatch ? 'var(--bad)' : 'rgba(20, 32, 43, 0.7)',
        color: mismatch ? 'white' : 'var(--muted)',
        border: `1px solid ${mismatch ? 'var(--bad)' : 'var(--border)'}`,
        cursor: 'pointer',
        zIndex: 9998,
        userSelect: 'none',
        transition: 'all 0.15s',
        backdropFilter: 'blur(4px)',
      }}
      title="Click for build details"
    >
      {!open ? (
        <>v{FRONT_VERSION}</>
      ) : (
        <div style={{ minWidth: 220, lineHeight: 1.5 }}>
          <div style={{ fontWeight: 700, fontSize: 10, marginBottom: 4 }}>
            BUILD INFO {mismatch && '⚠️'}
          </div>
          <div><strong>SPA:</strong> {FRONT_VERSION}</div>
          <div style={{ opacity: 0.7 }}>built {FRONT_BUILT_AT}</div>
          <div style={{ marginTop: 4 }}>
            <strong>API:</strong> {backend ? backend.version : (error ? `❌ ${error}` : 'loading…')}
          </div>
          {backend && (
            <div style={{ opacity: 0.7 }}>built {backend.built_at}</div>
          )}
          {mismatch && (
            <div style={{ marginTop: 4, fontWeight: 700 }}>
              ⚠️ SPA and API are different versions
            </div>
          )}
          <div style={{ marginTop: 4, opacity: 0.5, fontSize: 8 }}>tap to close</div>
        </div>
      )}
    </div>
  )
}
