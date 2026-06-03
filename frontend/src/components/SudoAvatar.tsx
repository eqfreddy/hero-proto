import './SudoAvatar.css'

interface Props {
  size?: number
}

// SUDO as a little helpdesk daemon: a terminal-head creature with glowing
// eyes, a deadpan flat mouth, and a status antenna. Pure presentational SVG.
export function SudoAvatar({ size = 56 }: Props) {
  return (
    <svg
      className="sudo-avatar"
      data-testid="sudo-avatar"
      role="img"
      aria-label="SUDO"
      width={size}
      height={size}
      viewBox="0 0 64 64"
    >
      <defs>
        <linearGradient id="sudoFace" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1b2b3a" />
          <stop offset="1" stopColor="#0d1620" />
        </linearGradient>
      </defs>
      <line x1="32" y1="12" x2="32" y2="5" stroke="#00e0d0" strokeWidth="2" />
      <circle cx="32" cy="4" r="2.5" fill="#e8a35a" />
      <rect x="8" y="12" width="48" height="40" rx="11" fill="url(#sudoFace)" stroke="#00e0d0" strokeWidth="2" />
      <circle className="sudo-avatar-eye" cx="24" cy="30" r="4" fill="#00e0d0" />
      <circle className="sudo-avatar-eye" cx="40" cy="30" r="4" fill="#00e0d0" />
      <rect x="24" y="40" width="16" height="2.5" rx="1.25" fill="#5ad8ff" />
    </svg>
  )
}
