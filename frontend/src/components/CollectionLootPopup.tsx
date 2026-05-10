import type { CollectionDrop } from '../types'

interface Props {
  pieces: CollectionDrop[]
  collectionName?: string
  ownedCount: number
  totalCount: number
  onInspect?: () => void
  onClose: () => void
}

export function CollectionLootPopup({ pieces, collectionName, ownedCount, totalCount, onInspect, onClose }: Props) {
  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed', inset: 0, zIndex: 200,
          background: 'rgba(0,0,0,0.65)',
        }}
        aria-hidden="true"
      />

      {/* Panel — slides in from bottom */}
      <div
        role="dialog"
        aria-label="Collection piece found"
        style={{
          position: 'fixed', bottom: 0, left: 0, right: 0,
          zIndex: 201,
          background: 'var(--panel)',
          borderTop: '1px solid var(--border)',
          borderRadius: '12px 12px 0 0',
          padding: '20px 20px 32px',
          animation: 'slideUp 0.22s ease-out',
          maxWidth: 520,
          margin: '0 auto',
        }}
      >
        <style>{`@keyframes slideUp { from { transform: translateY(60px); opacity: 0; } to { transform: none; opacity: 1; } }`}</style>

        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Collection Piece{pieces.length > 1 ? 's' : ''} Found!
          </div>
          {collectionName && (
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{collectionName}</div>
          )}
        </div>

        {/* Piece cards */}
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
          {pieces.map((p) => (
            <div
              key={p.piece_code}
              style={{
                border: `2px solid ${p.is_completion_piece ? '#ffd700' : 'var(--accent)'}`,
                borderRadius: 'var(--radius)',
                padding: '10px 14px',
                textAlign: 'center',
                minWidth: 80,
                background: p.is_completion_piece ? 'rgba(255,215,0,0.08)' : 'var(--bg-inset)',
                position: 'relative',
              }}
            >
              {p.is_completion_piece && (
                <div style={{ position: 'absolute', top: -8, left: '50%', transform: 'translateX(-50%)', fontSize: 12 }}>✨</div>
              )}
              <div style={{ fontSize: 24 }}>{p.icon}</div>
              <div style={{ fontSize: 11, fontWeight: 600, marginTop: 4, color: p.is_completion_piece ? '#ffd700' : 'inherit' }}>
                {p.name}
              </div>
              {p.is_completion_piece && (
                <div style={{ fontSize: 10, color: '#ffd700', marginTop: 2 }}>★ Set complete!</div>
              )}
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
            <span>Collection progress</span>
            <span>{ownedCount} / {totalCount}</span>
          </div>
          <div style={{ height: 6, background: 'var(--bg-inset)', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${Math.min(100, (ownedCount / Math.max(1, totalCount)) * 100)}%`,
                background: 'var(--accent)',
                borderRadius: 3,
                transition: 'width 0.4s ease',
              }}
            />
          </div>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 10 }}>
          {onInspect && (
            <button
              className="secondary"
              style={{ flex: 1 }}
              onClick={onInspect}
            >
              Inspect Collection
            </button>
          )}
          <button
            className="primary"
            style={{ flex: 1 }}
            onClick={onClose}
          >
            Continue
          </button>
        </div>
      </div>
    </>
  )
}
