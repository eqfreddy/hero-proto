import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchSessions, revokeSession, revokeAllSessions, requestDataExport, deleteAccount } from '../api/account'
import { enrollTotp, confirmTotp, disableTotp, regenerateCodes } from '../api/totp'
import { useMe } from '../hooks/useMe'
import { useAuthStore } from '../store/auth'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

// Backend requires confirm_email to match the account email.

// ── 2FA management ────────────────────────────────────────────────────────────

type TotpView = 'idle' | 'enroll' | 'enrolled' | 'disable' | 'regen' | 'regen-done'

function TotpSection({ enabled, onChanged }: { enabled: boolean; onChanged: () => void }) {
  const [view, setView] = useState<TotpView>('idle')
  const [enrollData, setEnrollData] = useState<{ uri: string; secret: string } | null>(null)
  const [code, setCode] = useState('')
  const [codes, setCodes] = useState<string[]>([])
  const [loading, setLoading] = useState(false)

  function reset() { setView('idle'); setCode(''); setEnrollData(null); setCodes([]) }

  async function startEnroll() {
    setLoading(true)
    try {
      const d = await enrollTotp()
      setEnrollData({ uri: d.otpauth_uri, secret: d.secret })
      setView('enroll')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setLoading(false) }
  }

  async function submitConfirm() {
    if (!code || code.length < 6) return
    setLoading(true)
    try {
      const d = await confirmTotp(code)
      setCodes(d.recovery_codes)
      setView('enrolled')
      onChanged()
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Invalid code — try again.'); setCode('') }
    finally { setLoading(false) }
  }

  async function submitDisable() {
    if (!code) return
    setLoading(true)
    try {
      await disableTotp(code)
      toast.success('Two-factor authentication disabled.')
      reset()
      onChanged()
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Invalid code.'); setCode('') }
    finally { setLoading(false) }
  }

  async function submitRegen() {
    if (!code) return
    setLoading(true)
    try {
      const d = await regenerateCodes(code)
      setCodes(d.recovery_codes)
      setView('regen-done')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Invalid code.'); setCode('') }
    finally { setLoading(false) }
  }

  // ── Enroll step 1: scan / enter secret
  if (view === 'enroll' && enrollData) {
    return (
      <div className="stack" style={{ fontSize: 13 }}>
        <div style={{ fontWeight: 600 }}>Scan in your authenticator app</div>
        <a
          href={enrollData.uri}
          style={{
            display: 'inline-block', padding: '10px 16px', borderRadius: 'var(--radius)',
            background: 'var(--bg-inset)', border: '1px solid var(--border)',
            color: 'var(--accent)', fontSize: 12, wordBreak: 'break-all',
          }}
        >
          Open in authenticator app →
        </a>
        <div className="muted" style={{ fontSize: 12 }}>
          Or enter this key manually:
          <code style={{
            display: 'block', marginTop: 6, padding: '6px 10px',
            background: 'var(--bg-inset)', borderRadius: 'var(--radius-sm)',
            letterSpacing: '0.15em', fontSize: 13, wordBreak: 'break-all',
            border: '1px solid var(--border)',
          }}>{enrollData.secret}</code>
        </div>
        <div>
          <label style={{ display: 'block', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
            Enter the 6-digit code from your app to confirm
          </label>
          <input
            type="text" inputMode="numeric" pattern="\d{6}" maxLength={6}
            value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            placeholder="000000" autoFocus
            style={{ width: '100%', letterSpacing: '0.2em', textAlign: 'center', fontSize: 18 }}
          />
        </div>
        <div className="row">
          <button className="primary" onClick={submitConfirm} disabled={loading || code.length < 6}>
            {loading ? 'Verifying…' : 'Activate 2FA'}
          </button>
          <button onClick={reset} disabled={loading}>Cancel</button>
        </div>
      </div>
    )
  }

  // ── Enroll step 2: show recovery codes
  if (view === 'enrolled') {
    return (
      <div className="stack">
        <div style={{ color: 'var(--good)', fontWeight: 700 }}>✅ Two-factor authentication enabled!</div>
        <div style={{ fontSize: 12, lineHeight: 1.6 }}>
          Save these recovery codes somewhere safe. Each can be used once if you lose access to your authenticator app.
        </div>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
          background: 'var(--bg-inset)', padding: 12, borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
        }}>
          {codes.map((c) => (
            <code key={c} style={{ fontSize: 12, letterSpacing: '0.1em' }}>{c}</code>
          ))}
        </div>
        <button onClick={reset}>Done</button>
      </div>
    )
  }

  // ── Disable prompt
  if (view === 'disable') {
    return (
      <div className="stack" style={{ fontSize: 13 }}>
        <div>Enter a 6-digit code or a recovery code to disable 2FA.</div>
        <input
          type="text" value={code} onChange={(e) => setCode(e.target.value)}
          placeholder="000000 or recovery code" autoFocus
          style={{ width: '100%' }}
        />
        <div className="row">
          <button className="primary" onClick={submitDisable} disabled={loading || !code}
            style={{ background: 'var(--bad)', borderColor: 'var(--bad)', color: '#fff' }}>
            {loading ? 'Disabling…' : 'Disable 2FA'}
          </button>
          <button onClick={reset} disabled={loading}>Cancel</button>
        </div>
      </div>
    )
  }

  // ── Regen prompt
  if (view === 'regen') {
    return (
      <div className="stack" style={{ fontSize: 13 }}>
        <div>Enter your current TOTP code to regenerate recovery codes. Old codes will be invalidated.</div>
        <input
          type="text" inputMode="numeric" pattern="\d{6}" maxLength={6}
          value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          placeholder="000000" autoFocus style={{ width: '100%' }}
        />
        <div className="row">
          <button className="primary" onClick={submitRegen} disabled={loading || code.length < 6}>
            {loading ? 'Regenerating…' : 'Regenerate codes'}
          </button>
          <button onClick={reset} disabled={loading}>Cancel</button>
        </div>
      </div>
    )
  }

  // ── Regen done
  if (view === 'regen-done') {
    return (
      <div className="stack">
        <div style={{ fontWeight: 600 }}>New recovery codes</div>
        <div style={{ fontSize: 12 }}>Your old codes are now invalid. Save these.</div>
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6,
          background: 'var(--bg-inset)', padding: 12, borderRadius: 'var(--radius)',
          border: '1px solid var(--border)',
        }}>
          {codes.map((c) => (
            <code key={c} style={{ fontSize: 12, letterSpacing: '0.1em' }}>{c}</code>
          ))}
        </div>
        <button onClick={reset}>Done</button>
      </div>
    )
  }

  // ── Idle: show status + action buttons
  return (
    <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
      <div>
        <span style={{ fontWeight: 600, fontSize: 13 }}>
          {enabled ? '🔐 Two-factor authentication is on' : '🔓 Two-factor authentication is off'}
        </span>
        <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
          {enabled
            ? 'Your account is protected with a TOTP authenticator.'
            : 'Add an extra layer of security to your account.'}
        </div>
      </div>
      {enabled ? (
        <div className="row" style={{ gap: 6 }}>
          <button style={{ fontSize: 12 }} onClick={() => { reset(); setView('regen') }}>Recovery codes</button>
          <button style={{ fontSize: 12, color: 'var(--bad)', borderColor: 'var(--bad)' }}
            onClick={() => { reset(); setView('disable') }}>Disable</button>
        </div>
      ) : (
        <button className="primary" style={{ fontSize: 12 }} onClick={startEnroll} disabled={loading}>
          {loading ? 'Loading…' : 'Enable 2FA'}
        </button>
      )}
    </div>
  )
}

// ── Main route ────────────────────────────────────────────────────────────────

export function AccountRoute() {
  const qc = useQueryClient()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const { data: me, isLoading: meLoading } = useMe()
  const { data: sessions, isLoading: sessionsLoading } = useQuery({ queryKey: ['sessions'], queryFn: fetchSessions })
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)

  if (meLoading || sessionsLoading) return <SkeletonGrid count={3} height={60} />

  async function exportData() {
    try {
      const res = await requestDataExport()
      if (res.download_url) window.location.href = res.download_url
      else toast.info('Export queued — check your email.')
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Export failed') }
  }

  async function revokeAll() {
    if (!confirm('Sign out of all other devices?')) return
    try {
      await revokeAllSessions()
      toast.success('All other sessions revoked.')
      qc.invalidateQueries({ queryKey: ['sessions'] })
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  const myEmail = me?.email ?? ''

  async function confirmDelete() {
    if (confirmText.toLowerCase() !== myEmail.toLowerCase()) return
    setDeleting(true)
    try {
      await deleteAccount(confirmText)
      clearJwt()
      qc.clear()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed')
      setDeleting(false)
    }
  }

  function closeDeleteModal() { setShowDeleteModal(false); setConfirmText('') }

  return (
    <div className="stack" style={{ maxWidth: 600 }}>
      <h2 style={{ margin: 0 }}>⚙️ Account</h2>

      {/* 2FA */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Security</h3>
        <TotpSection
          enabled={me?.totp_enabled ?? false}
          onChanged={() => qc.invalidateQueries({ queryKey: ['me'] })}
        />
      </div>

      {/* Sessions */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Active Sessions</h3>
        {sessions?.map((s) => {
          const lastSeen = s.last_used_at ?? s.issued_at
          return (
          <div key={s.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
            <div>
              <span>{s.ip ?? 'unknown ip'}</span>
              {s.is_current && <span className="pill good" style={{ marginLeft: 6, fontSize: 10 }}>current</span>}
              <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>
                {new Date(lastSeen).toLocaleString()}
                {s.user_agent && <span style={{ marginLeft: 6, opacity: 0.7 }}>· {s.user_agent.slice(0, 48)}</span>}
              </div>
            </div>
            {!s.is_current && (
              <button style={{ fontSize: 11 }}
                onClick={async () => {
                  try { await revokeSession(s.id); qc.invalidateQueries({ queryKey: ['sessions'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Revoke</button>
            )}
          </div>
          )
        })}
        <button style={{ marginTop: 10, fontSize: 12 }} onClick={revokeAll}>Sign out all other devices</button>
      </div>

      {/* Data & Privacy */}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Data &amp; Privacy</h3>
        <button style={{ fontSize: 12 }} onClick={exportData}>Export my data (GDPR)</button>
        <div style={{ marginTop: 12, display: 'flex', gap: 16, fontSize: 12 }}>
          <Link to="/app/privacy" style={{ color: 'var(--accent)' }}>Privacy Policy</Link>
          <Link to="/app/terms" style={{ color: 'var(--accent)' }}>Terms of Service</Link>
        </div>
      </div>

      {/* Danger zone */}
      <div className="card" style={{ border: '1px solid var(--bad)' }}>
        <h3 style={{ marginTop: 0, color: 'var(--bad)' }}>Danger Zone</h3>
        <p className="muted" style={{ fontSize: 12, marginTop: 0, lineHeight: 1.5 }}>
          Permanently deletes your account, heroes, gear, currencies, and history.
          Hard-deleted within 24 hours per our <Link to="/app/privacy" style={{ color: 'var(--muted)', textDecoration: 'underline' }}>privacy policy</Link>.
          This cannot be undone.
        </p>
        <button
          style={{ fontSize: 12, color: 'var(--bad)', borderColor: 'var(--bad)' }}
          onClick={() => setShowDeleteModal(true)}
        >
          Delete account permanently
        </button>
      </div>

      {showDeleteModal && (
        <div
          role="dialog" aria-modal="true"
          onClick={(e) => { if (e.target === e.currentTarget && !deleting) closeDeleteModal() }}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            padding: 20, zIndex: 1000,
          }}
        >
          <div className="card" style={{ maxWidth: 420, width: '100%', padding: 24, border: '1px solid var(--bad)' }}>
            <h3 style={{ marginTop: 0, color: 'var(--bad)' }}>Delete your account?</h3>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>
              This permanently deletes your account and everything tied to it.
              Heroes, gear, currencies, guild membership, friend list, battle history — all gone.
              Purchases cannot be transferred to a new account.
            </p>
            <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
              Type your email address <strong style={{ color: 'var(--text)' }}>{myEmail}</strong> to confirm.
            </p>
            <input
              type="email" autoFocus value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder={myEmail} disabled={deleting}
              style={{ width: '100%', marginBottom: 14 }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={closeDeleteModal} disabled={deleting} style={{ fontSize: 12 }}>Cancel</button>
              <button
                onClick={confirmDelete}
                disabled={confirmText.toLowerCase() !== myEmail.toLowerCase() || deleting}
                style={{
                  fontSize: 12,
                  color: confirmText.toLowerCase() === myEmail.toLowerCase() ? '#fff' : 'var(--muted)',
                  background: confirmText.toLowerCase() === myEmail.toLowerCase() ? 'var(--bad)' : 'var(--bg-inset)',
                  borderColor: 'var(--bad)',
                }}
              >
                {deleting ? 'Deleting…' : 'Delete forever'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
