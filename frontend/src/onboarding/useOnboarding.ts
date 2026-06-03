const KEY = 'heroproto_onboarding_seen'

export function hasSeenOnboarding(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export function markOnboardingSeen(): void {
  try {
    localStorage.setItem(KEY, '1')
  } catch {
    /* best-effort: private mode / disabled storage */
  }
}

export function replayOnboarding(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* no-op */
  }
}

// Not reactive (localStorage isn't); recomputed each render. Named use* for
// call-site readability. Show only for a genuinely-new, not-yet-onboarded account.
export function useShouldOnboard(accountLevel: number | undefined): boolean {
  return accountLevel === 1 && !hasSeenOnboarding()
}
