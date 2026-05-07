import { useEffect, useRef, useState } from 'react'

function format(seconds: number): string {
  if (seconds <= 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export function useCountdown(seconds: number, onZero?: () => void): string {
  const [remaining, setRemaining] = useState(Math.max(0, Math.floor(seconds)))
  const firedRef = useRef(false)

  useEffect(() => {
    setRemaining(Math.max(0, Math.floor(seconds)))
    firedRef.current = false
  }, [seconds])

  useEffect(() => {
    if (remaining <= 0) {
      if (!firedRef.current && onZero) {
        firedRef.current = true
        onZero()
      }
      return
    }
    const id = setInterval(() => {
      setRemaining(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(id)
  }, [remaining, onZero])

  return format(remaining)
}
