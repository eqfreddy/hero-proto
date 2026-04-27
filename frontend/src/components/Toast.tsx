import { useUiStore } from '../store/ui'

export function ToastContainer() {
  const toasts = useUiStore((s) => s.toasts)
  const dismiss = useUiStore((s) => s.dismissToast)

  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed', bottom: 20, left: '50%', transform: 'translateX(-50%)',
      zIndex: 9000, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center',
    }}>
      {toasts.map((t) => (
        <div key={t.id} onClick={() => dismiss(t.id)} style={{
          padding: '10px 18px', borderRadius: 6, cursor: 'pointer',
          fontSize: 13, fontWeight: 500, maxWidth: 420, textAlign: 'center',
          background: t.kind === 'error' ? 'var(--bad)' : t.kind === 'success' ? 'var(--good)' : 'var(--accent)',
          color: '#0b0d10', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        }}>
          {t.message}
        </div>
      ))}
    </div>
  )
}
