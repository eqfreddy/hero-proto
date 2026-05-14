import { useState, useEffect } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import { apiFetch } from '../api/client'
import { toast } from '../store/ui'

type Tab = 'signin' | 'register' | 'forgot'
type LoginResponse =
  | { access_token: string; refresh_token: string }
  | { status: 'location_challenge'; message: string }
  | { status: 'totp_required'; challenge_token: string }

export function Login() {
  const [tab, setTab] = useState<Tab>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)
  const [locationChallenge, setLocationChallenge] = useState(false)
  const [totpToken, setTotpToken] = useState<string | null>(null)
  const [totpCode, setTotpCode] = useState('')
  const setJwt = useAuthStore((s) => s.setJwt)
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname ?? '/app/lobby'

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const v = params.get('verified')
    if (v === '1') toast.success('Email verified! You can now sign in.')
    else if (v === 'already') toast.info('Email already verified. Go ahead and sign in.')
    else if (v === 'invalid') toast.error('Verification link is invalid or expired. Request a new one.')
    if (v) navigate('/app/login', { replace: true })
  }, [])

  function switchTab(t: Tab) {
    setTab(t)
    setPassword('')
    setConfirm('')
    setForgotSent(false)
    setLocationChallenge(false)
    setTotpToken(null)
    setTotpCode('')
  }

  function finishLogin(token: string) {
    setJwt(token)
    navigate(from, { replace: true })
  }

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const data = await apiFetch<LoginResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      if ('access_token' in data) {
        finishLogin(data.access_token)
      } else if (data.status === 'location_challenge') {
        setLocationChallenge(true)
      } else if (data.status === 'totp_required') {
        setTotpToken(data.challenge_token)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      if (msg.toLowerCase().includes('locked')) {
        toast.error('Account temporarily locked after too many failed attempts. Reset your password or try again later.')
      } else if (msg.toLowerCase().includes('invalid') || msg.includes('401')) {
        toast.error('Invalid email or password.')
      } else {
        toast.error(msg || 'Sign in failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleTotp(e: React.FormEvent) {
    e.preventDefault()
    if (!totpToken) return
    setLoading(true)
    try {
      const data = await apiFetch<{ access_token: string }>('/auth/2fa/verify', {
        method: 'POST',
        body: JSON.stringify({ challenge_token: totpToken, code: totpCode }),
      })
      finishLogin(data.access_token)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Invalid code.')
      setTotpCode('')
    } finally {
      setLoading(false)
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    if (password !== confirm) { toast.error('Passwords do not match.'); return }
    if (password.length < 8) { toast.error('Password must be at least 8 characters.'); return }
    setLoading(true)
    try {
      const data = await apiFetch<{ access_token?: string }>('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      if (data.access_token) {
        setJwt(data.access_token)
        toast.success('Account created! Welcome aboard.')
        navigate(from, { replace: true })
      } else {
        toast.info('If that email is new, check your inbox to verify. Otherwise sign in.')
        switchTab('signin')
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      await apiFetch('/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      setForgotSent(true)
    } catch {
      setForgotSent(true)
    } finally {
      setLoading(false)
    }
  }

  const tabStyle = (t: Tab) => ({
    flex: 1 as const,
    padding: '8px 0',
    background: 'transparent',
    border: 'none',
    borderBottom: `2px solid ${tab === t ? 'var(--accent)' : 'transparent'}`,
    color: tab === t ? 'var(--text)' : 'var(--muted)',
    fontSize: 14,
    fontWeight: tab === t ? 600 : 400,
    cursor: 'pointer',
  })

  return (
    <div style={{ maxWidth: 360, margin: '60px auto' }}>
      <h1 style={{ textAlign: 'center', fontSize: 22, marginBottom: 24, color: 'var(--text)' }}>hero-proto</h1>
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ display: 'flex', borderBottom: '1px solid var(--border)' }}>
          <button style={tabStyle('signin')} onClick={() => switchTab('signin')}>Sign in</button>
          <button style={tabStyle('register')} onClick={() => switchTab('register')}>Register</button>
        </div>

        <div style={{ padding: '20px 24px' }}>
          {/* ── Location challenge screen ── */}
          {tab === 'signin' && locationChallenge && (
            <div className="stack" style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32 }}>📍</div>
              <div style={{ fontWeight: 600 }}>New location detected</div>
              <div className="muted" style={{ fontSize: 12 }}>
                We sent an approval link to <strong>{email}</strong>. Click it to complete sign-in, then come back and try again.
              </div>
              <button onClick={() => setLocationChallenge(false)} className="primary">Try again</button>
            </div>
          )}

          {/* ── TOTP challenge screen ── */}
          {tab === 'signin' && totpToken && !locationChallenge && (
            <form onSubmit={handleTotp} className="stack">
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 4 }}>🔐</div>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Two-factor authentication</div>
                <div className="muted" style={{ fontSize: 12 }}>Enter the 6-digit code from your authenticator app.</div>
              </div>
              <div>
                <label htmlFor="totp-code" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Authentication code</label>
                <input id="totp-code" type="text" inputMode="numeric" pattern="\d{6}" maxLength={6}
                  value={totpCode} onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                  required style={{ width: '100%', letterSpacing: '0.3em', textAlign: 'center', fontSize: 20 }}
                  autoComplete="one-time-code" autoFocus placeholder="000000" />
              </div>
              <button type="submit" className="primary" disabled={loading || totpCode.length !== 6}>
                {loading ? 'Verifying…' : 'Verify'}
              </button>
              <button type="button" onClick={() => { setTotpToken(null); setTotpCode('') }}
                style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', padding: 0, alignSelf: 'center' }}>
                Back
              </button>
            </form>
          )}

          {/* ── Normal sign-in form ── */}
          {tab === 'signin' && !locationChallenge && !totpToken && (
            <form onSubmit={handleSignIn} className="stack">
              <div>
                <label htmlFor="email" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Email</label>
                <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  required style={{ width: '100%' }} placeholder="you@example.com" autoComplete="email" />
              </div>
              <div>
                <label htmlFor="password" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Password</label>
                <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  required style={{ width: '100%' }} autoComplete="current-password" />
              </div>
              <button type="submit" className="primary" disabled={loading}>
                {loading ? 'Signing in…' : 'Sign in'}
              </button>
              <button type="button" onClick={() => switchTab('forgot')}
                style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', padding: 0, alignSelf: 'center' }}>
                Forgot password?
              </button>
            </form>
          )}

          {tab === 'register' && (
            <form onSubmit={handleRegister} className="stack">
              <div>
                <label htmlFor="reg-email" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Email</label>
                <input id="reg-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                  required style={{ width: '100%' }} placeholder="you@example.com" autoComplete="email" />
              </div>
              <div>
                <label htmlFor="reg-password" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Password</label>
                <input id="reg-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  required minLength={8} style={{ width: '100%' }} autoComplete="new-password" placeholder="8+ characters" />
              </div>
              <div>
                <label htmlFor="reg-confirm" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Confirm password</label>
                <input id="reg-confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                  required style={{ width: '100%' }} autoComplete="new-password" />
              </div>
              <button type="submit" className="primary" disabled={loading}>
                {loading ? 'Creating account…' : 'Create account'}
              </button>
            </form>
          )}

          {tab === 'forgot' && (
            forgotSent
              ? (
                <div className="stack" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32 }}>📧</div>
                  <div style={{ fontWeight: 600 }}>Check your inbox</div>
                  <div className="muted" style={{ fontSize: 12 }}>If that email has an account, a reset link is on its way.</div>
                  <button onClick={() => switchTab('signin')} className="primary">Back to sign in</button>
                </div>
              )
              : (
                <form onSubmit={handleForgot} className="stack">
                  <div style={{ color: 'var(--muted)', fontSize: 13 }}>Enter your email and we'll send a reset link.</div>
                  <div>
                    <label htmlFor="forgot-email" style={{ display: 'block', fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Email</label>
                    <input id="forgot-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                      required style={{ width: '100%' }} placeholder="you@example.com" autoComplete="email" />
                  </div>
                  <button type="submit" className="primary" disabled={loading}>
                    {loading ? 'Sending…' : 'Send reset link'}
                  </button>
                  <button type="button" onClick={() => switchTab('signin')}
                    style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', padding: 0, alignSelf: 'center' }}>
                    Back to sign in
                  </button>
                </form>
              )
          )}
        </div>
      </div>
      <div style={{ marginTop: 16, textAlign: 'center', fontSize: 11, color: 'var(--muted)' }}>
        By continuing you agree to our{' '}
        <Link to="/app/terms" style={{ color: 'var(--muted)', textDecoration: 'underline' }}>Terms</Link>
        {' '}and{' '}
        <Link to="/app/privacy" style={{ color: 'var(--muted)', textDecoration: 'underline' }}>Privacy Policy</Link>.
      </div>
    </div>
  )
}
