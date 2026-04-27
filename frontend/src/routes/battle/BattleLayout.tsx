import { Outlet } from 'react-router-dom'

export default function BattleLayout() {
  return (
    <div style={{ width: '100vw', height: '100vh', background: 'var(--color-bg)', overflow: 'hidden', position: 'relative' }}>
      <Outlet />
    </div>
  )
}
