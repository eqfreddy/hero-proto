import { NavLink } from 'react-router-dom'

interface Tab { path: string; label: string }
interface Props { tabs: Tab[] }

export function SubNav({ tabs }: Props) {
  return (
    <div style={{
      display: 'flex', gap: 2, borderBottom: '1px solid var(--border)',
      marginBottom: 16, overflowX: 'auto',
    }}>
      {tabs.map((t) => (
        <NavLink
          key={t.path}
          to={t.path}
          end
          style={({ isActive }) => ({
            padding: '6px 14px', fontSize: 13, fontWeight: isActive ? 700 : 400,
            color: isActive ? 'var(--text)' : 'var(--muted)',
            borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
            textDecoration: 'none', background: 'transparent', whiteSpace: 'nowrap',
          })}
        >
          {t.label}
        </NavLink>
      ))}
    </div>
  )
}
