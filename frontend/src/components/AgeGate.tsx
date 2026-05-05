import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

const LEGAL_PATHS = new Set(['/app/privacy', '/app/terms'])

const STORAGE_KEY = 'age_gate_v1'
const MIN_AGE = 13

interface Stored {
  confirmedAt: string
  birthYear: number
}

function getStored(): Stored | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as Stored
  } catch { return null }
}

export function AgeGate({ children }: { children: React.ReactNode }) {
  const [confirmed, setConfirmed] = useState<boolean>(() => getStored() !== null)
  const [year, setYear] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [denied, setDenied] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const stored = getStored()
    if (stored) setConfirmed(true)
  }, [])

  if (confirmed) return <>{children}</>
  if (LEGAL_PATHS.has(location.pathname)) return <>{children}</>

  function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    const y = parseInt(year, 10)
    const currentYear = new Date().getFullYear()
    if (!y || y < 1900 || y > currentYear) {
      setError('Please enter a valid 4-digit year.')
      return
    }
    const age = currentYear - y
    if (age < MIN_AGE) {
      setDenied(true)
      return
    }
    const payload: Stored = { confirmedAt: new Date().toISOString(), birthYear: y }
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(payload)) } catch { /* ignore */ }
    setConfirmed(true)
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'var(--bg)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 20, zIndex: 9999,
    }}>
      <div className="card" style={{ maxWidth: 380, width: '100%', padding: 28 }}>
        {denied ? (
          <>
            <div style={{ fontSize: 32, textAlign: 'center', marginBottom: 12 }}>🔒</div>
            <h2 style={{ margin: 0, textAlign: 'center', fontSize: 18, fontWeight: 800 }}>Sorry, you can't play yet.</h2>
            <p style={{ color: 'var(--muted)', fontSize: 13, lineHeight: 1.6, marginTop: 12, textAlign: 'center' }}>
              hero-proto is intended for players aged {MIN_AGE} and over. Come back when you're old enough.
            </p>
          </>
        ) : (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 8,
                background: 'linear-gradient(135deg, var(--accent), #7c5fff)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18, fontWeight: 900, color: '#0b0d10',
              }}>H</div>
              <div>
                <h2 style={{ margin: 0, fontSize: 16, fontWeight: 800 }}>Welcome to hero-proto</h2>
                <div style={{ fontSize: 12, color: 'var(--muted)' }}>Quick age check before we start.</div>
              </div>
            </div>
            <form onSubmit={submit} className="stack">
              <div>
                <label htmlFor="birth-year" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>
                  What year were you born?
                </label>
                <input
                  id="birth-year"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={4}
                  value={year}
                  onChange={(e) => setYear(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="YYYY"
                  required
                  style={{ width: '100%' }}
                />
              </div>
              {error && (
                <div style={{ color: 'var(--bad)', fontSize: 12 }}>{error}</div>
              )}
              <button type="submit" className="primary">Continue</button>
              <div style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.5 }}>
                We use your birth year only to verify you meet the {MIN_AGE}+ minimum. It is not stored on our servers.
                <div style={{ marginTop: 6 }}>
                  <Link to="/app/privacy" style={{ color: 'var(--muted)', textDecoration: 'underline' }}>Privacy</Link>
                  {' · '}
                  <Link to="/app/terms" style={{ color: 'var(--muted)', textDecoration: 'underline' }}>Terms</Link>
                </div>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
