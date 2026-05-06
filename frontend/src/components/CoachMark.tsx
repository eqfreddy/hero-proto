import { useEffect, useState, useRef, type ReactNode } from 'react'

const STORAGE_KEY = 'heroproto_coachmarks_seen'

function getSeen(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return new Set(raw ? JSON.parse(raw) : [])
  } catch {
    return new Set()
  }
}

function markSeen(screenId: string) {
  const seen = getSeen()
  seen.add(screenId)
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...seen]))
}

interface Props {
  screenId: string       // unique ID stored in localStorage
  tooltip: string        // ≤15 words
  side?: 'left' | 'right'  // which side of the highlighted element the tooltip appears
  children: ReactNode    // the element to highlight
}

export function CoachMark({ screenId, tooltip, side = 'left', children }: Props) {
  const [visible, setVisible] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!getSeen().has(screenId)) {
      setVisible(true)
    }
  }, [screenId])

  function dismiss() {
    markSeen(screenId)
    setVisible(false)
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      {children}
      {visible && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', zIndex: 500 }}
          onClick={dismiss}
        >
          {/* Highlight ring around the element */}
          {ref.current && (() => {
            const rect = ref.current.getBoundingClientRect()
            return (
              <>
                <div style={{
                  position: 'fixed',
                  top: rect.top - 4, left: rect.left - 4,
                  width: rect.width + 8, height: rect.height + 8,
                  boxShadow: '0 0 0 3px var(--accent), 0 0 0 6px rgba(78,161,255,0.22)',
                  borderRadius: 6, pointerEvents: 'none', zIndex: 501,
                }} />
                {/* Tooltip bubble */}
                <div style={{
                  position: 'fixed',
                  top: rect.top - 4,
                  ...(side === 'left'
                    ? { right: window.innerWidth - rect.left + 10 }
                    : { left: rect.right + 10 }),
                  zIndex: 502,
                  background: 'var(--warn)', color: '#0b0d10',
                  borderRadius: 6, padding: '8px 12px',
                  fontSize: 11, fontWeight: 600, maxWidth: 180,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
                  pointerEvents: 'none',
                }}>
                  {tooltip}
                </div>
              </>
            )
          })()}
          {/* Dismiss hint */}
          <div style={{
            position: 'fixed', bottom: 20, left: 0, right: 0,
            textAlign: 'center', zIndex: 502,
            color: 'rgba(255,255,255,0.55)', fontSize: 11,
            pointerEvents: 'none',
          }}>
            Tap anywhere to dismiss
          </div>
        </div>
      )}
    </div>
  )
}
