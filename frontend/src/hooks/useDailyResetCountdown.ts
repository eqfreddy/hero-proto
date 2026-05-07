import { useCountdown } from './useCountdown'

function secondsUntilNextMidnightUTC(): number {
  const now = new Date()
  const tomorrow = new Date(Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate() + 1,
    0, 0, 0, 0,
  ))
  return Math.floor((tomorrow.getTime() - now.getTime()) / 1000)
}

export function useDailyResetCountdown(): string {
  return useCountdown(secondsUntilNextMidnightUTC())
}
