import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchSessions, revokeSession, revokeAllSessions, requestDataExport, deleteAccount } from '../api/account'
import { useAuthStore } from '../store/auth'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'

export function AccountRoute() {
  const qc = useQueryClient()
  const clearJwt = useAuthStore((s) => s.clearJwt)
  const { data: sessions, isLoading } = useQuery({ queryKey: ['sessions'], queryFn: fetchSessions })

  if (isLoading) return <SkeletonGrid count={3} height={60} />

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

  async function doDeleteAccount() {
    if (!confirm('Permanently delete your account? This cannot be undone.')) return
    try {
      await deleteAccount()
      clearJwt()
      qc.clear()
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
  }

  return (
    <div className="stack" style={{ maxWidth: 600 }}>
      <h2 style={{ margin: 0 }}>⚙️ Account</h2>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Active Sessions</h3>
        {sessions?.map((s) => (
          <div key={s.id} className="row" style={{ justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
            <div>
              <span>{s.ip_address}</span>
              {s.is_current && <span className="pill good" style={{ marginLeft: 6, fontSize: 10 }}>current</span>}
              <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>{new Date(s.last_used).toLocaleString()}</div>
            </div>
            {!s.is_current && (
              <button style={{ fontSize: 11 }}
                onClick={async () => {
                  try { await revokeSession(s.id); qc.invalidateQueries({ queryKey: ['sessions'] }) }
                  catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
                }}>Revoke</button>
            )}
          </div>
        ))}
        <button style={{ marginTop: 10, fontSize: 12 }} onClick={revokeAll}>Sign out all other devices</button>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Data &amp; Privacy</h3>
        <button style={{ fontSize: 12 }} onClick={exportData}>Export my data (GDPR)</button>
      </div>
      <div className="card" style={{ border: '1px solid var(--bad)' }}>
        <h3 style={{ marginTop: 0, color: 'var(--bad)' }}>Danger Zone</h3>
        <button style={{ fontSize: 12, color: 'var(--bad)', borderColor: 'var(--bad)' }} onClick={doDeleteAccount}>
          Delete account permanently
        </button>
      </div>
    </div>
  )
}
