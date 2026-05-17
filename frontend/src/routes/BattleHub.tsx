import { useNavigate } from 'react-router-dom'

type Tile = {
  to: string
  label: string
  title: string
  desc: string
}

const TILES: Tile[] = [
  { to: '/app/stages', label: 'CAMPAIGN', title: 'Stages',      desc: 'Outage / audit / migration nodes' },
  { to: '/app/arena',  label: 'PVP',      title: 'Arena',       desc: 'Async ladder against other ops' },
  { to: '/app/tower',  label: 'ENDLESS',  title: 'Tower',       desc: 'Climb floors · monthly leaderboard' },
  { to: '/app/raids',  label: 'CO-OP',    title: 'Raids',       desc: 'Guild bosses · weekly cycle' },
]

export default function BattleHubRoute() {
  const navigate = useNavigate()
  return (
    <div className="battle-hub">
      <h1>// BATTLE.menu</h1>
      <div className="battle-hub-grid">
        {TILES.map((t) => (
          <div
            key={t.to}
            className="battle-tile"
            role="button"
            tabIndex={0}
            onClick={() => navigate(t.to)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(t.to) }}
          >
            <span className="label">{t.label}</span>
            <span className="title">{t.title}</span>
            <span className="desc">{t.desc}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
