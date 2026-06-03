import { useEffect, useState } from 'react'
import { useMe } from '../hooks/useMe'
import { SudoAvatar } from './SudoAvatar'
import { ONBOARDING_STEPS } from '../onboarding/onboardingSteps'
import { useShouldOnboard, markOnboardingSeen } from '../onboarding/useOnboarding'
import './SudoOnboarding.css'

export function SudoOnboarding() {
  const { data: me } = useMe()
  const should = useShouldOnboard(me?.account_level)
  const [active, setActive] = useState(false)
  const [idx, setIdx] = useState(0)
  const [rect, setRect] = useState<DOMRect | null>(null)

  // Latch active once eligible so a dismiss stays dismissed this session.
  useEffect(() => {
    if (should) setActive(true)
  }, [should])

  const step = ONBOARDING_STEPS[idx]

  useEffect(() => {
    if (!active || !step) return
    function place() {
      const el = step.tourTarget
        ? document.querySelector(`[data-tour="${step.tourTarget}"]`)
        : null
      setRect(el ? el.getBoundingClientRect() : null)
    }
    place()
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  }, [active, step])

  if (!active || !step) return null

  function finish() {
    markOnboardingSeen()
    setActive(false)
  }
  function next() {
    if (idx >= ONBOARDING_STEPS.length - 1) finish()
    else setIdx((i) => i + 1)
  }
  const isLast = idx >= ONBOARDING_STEPS.length - 1

  return (
    <div className="sudo-onb" role="dialog" aria-modal="true" aria-label="Getting started">
      {rect && (
        <div
          data-testid="sudo-onb-ring"
          className="sudo-onb-ring"
          style={{
            top: rect.top - 4,
            left: rect.left - 4,
            width: rect.width + 8,
            height: rect.height + 8,
          }}
        />
      )}
      <div className="sudo-onb-card">
        <div className="sudo-onb-head">
          <SudoAvatar size={48} />
          <div className="sudo-onb-title">{step.title}</div>
        </div>
        <div className="sudo-onb-body">{step.body}</div>
        <div className="sudo-onb-dots" aria-hidden="true">
          {ONBOARDING_STEPS.map((_, i) => (
            <span key={i} className={'sudo-onb-dot' + (i === idx ? ' is-on' : '')} />
          ))}
        </div>
        <div className="sudo-onb-actions">
          <button className="sudo-onb-skip" onClick={finish}>Skip tour</button>
          <button className="sudo-onb-next" onClick={next}>{isLast ? 'Got it' : 'Next'}</button>
        </div>
      </div>
    </div>
  )
}
