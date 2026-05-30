import { useEffect, useRef, useState, useCallback } from 'react'
import './RecycleBinFinisher.css'

export interface FinisherResult {
  targetUid: string
  perfect: boolean
}

interface Props {
  targetUid: string
  targetName: string
  windowMs?: number
  onResolve: (r: FinisherResult) => void
}

/** Deterministic-enough bin placement without Math.random in render:
 *  derive from the uid so it varies per target but is stable across re-renders. */
function binPosition(uid: string): { topPct: number; leftPct: number } {
  let h = 0
  for (let i = 0; i < uid.length; i++) h = (h * 31 + uid.charCodeAt(i)) >>> 0
  // Safe zone: 15-75% vertical (off the bottom action bar), 10-80% horizontal.
  const topPct = 15 + (h % 60)
  const leftPct = 10 + ((h >> 8) % 70)
  return { topPct, leftPct }
}

export function RecycleBinFinisher({ targetUid, targetName, windowMs = 2500, onResolve }: Props) {
  const resolvedRef = useRef(false)
  const binRef = useRef<HTMLDivElement | null>(null)
  const grabOffsetRef = useRef<{ dx: number; dy: number }>({ dx: 0, dy: 0 })
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null)
  const pos = binPosition(targetUid)

  const resolve = useCallback((perfect: boolean) => {
    if (resolvedRef.current) return
    resolvedRef.current = true
    onResolve({ targetUid, perfect })
  }, [onResolve, targetUid])

  useEffect(() => {
    const t = window.setTimeout(() => resolve(false), windowMs)
    return () => window.clearTimeout(t)
  }, [resolve, windowMs])

  // Fix 1+2: handlers on the chip; capture on currentTarget; offset applied
  const onChipPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    grabOffsetRef.current = { dx: e.clientX - rect.left, dy: e.clientY - rect.top }
    setDragPos({ x: e.clientX, y: e.clientY })
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onChipPointerMove = (e: React.PointerEvent) => {
    if (dragPos === null) return
    setDragPos({ x: e.clientX, y: e.clientY })
  }
  const onChipPointerUp = (e: React.PointerEvent) => {
    if (dragPos === null) return
    const bin = binRef.current?.getBoundingClientRect()
    const hit = bin
      ? e.clientX >= bin.left && e.clientX <= bin.right && e.clientY >= bin.top && e.clientY <= bin.bottom
      : false
    setDragPos(null)
    if (hit) resolve(true)
    // miss: leave the window running — they can retry until it expires (plain on timeout)
  }

  return (
    <div
      className="recycle-finisher"
      role="dialog"
      aria-modal="true"
      aria-label="Delete target"
    >
      <div className="recycle-finisher-prompt">Drag to the bin</div>
      <div
        data-testid="finisher-draggable"
        className="recycle-finisher-target"
        style={dragPos ? { left: dragPos.x - grabOffsetRef.current.dx, top: dragPos.y - grabOffsetRef.current.dy } : undefined}
        onPointerDown={onChipPointerDown}
        onPointerMove={onChipPointerMove}
        onPointerUp={onChipPointerUp}
      >
        {targetName}
      </div>
      <div
        data-testid="recycle-bin"
        ref={binRef}
        className="recycle-finisher-bin"
        style={{ top: `${pos.topPct}%`, left: `${pos.leftPct}%` }}
      >
        🗑
      </div>
      {/* Fix 3: accessible button is the BASE path (perfect: false) */}
      <button className="recycle-finisher-accessible" onClick={() => resolve(false)}>
        Delete now
      </button>
    </div>
  )
}
