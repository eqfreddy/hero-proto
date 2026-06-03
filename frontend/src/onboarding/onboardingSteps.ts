export interface OnboardingStep {
  tourTarget: string | null  // matches a [data-tour="..."] attr; null = no spotlight
  title: string
  body: string
}

// Steps 1 & 2 share the Heroes hub by design — recruiting and team-building
// both live there. SUDO's register: deadpan, a touch warmer for newcomers.
export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    tourTarget: 'heroes',
    title: 'Step 1 — Recruit',
    body: 'Summon your first recruits. They live under Heroes. Try not to whiff.',
  },
  {
    tourTarget: 'heroes',
    title: 'Step 2 — Build',
    body: 'Form a squad from what you pulled. Same place. Pick the ones that look expensive.',
  },
  {
    tourTarget: 'battle',
    title: 'Step 3 — Deploy',
    body: 'Throw them at a stage. This is the part that matters. Permission granted.',
  },
]
