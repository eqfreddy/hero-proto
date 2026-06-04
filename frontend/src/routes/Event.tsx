import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchActiveEvent, claimEventQuest, redeemMilestone } from '../api/events'
import type { EventBanner, EventBundle } from '../api/events'
import { toast } from '../store/ui'
import { EmptyState } from '../components/EmptyState'
import { SkeletonGrid } from '../components/SkeletonGrid'

function formatEventWindow(endsAt: string): string {
  const diffMs = new Date(endsAt).getTime() - Date.now()
  if (diffMs <= 0) return 'Closing now'
  const totalMinutes = Math.ceil(diffMs / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    return `${days}d ${hours % 24}h left`
  }
  if (hours > 0) return `${hours}h ${minutes}m left`
  return `${minutes}m left`
}

export function EventRoute() {
  const qc = useQueryClient()
  const { data: event, isLoading } = useQuery({
    queryKey: ['active-event-detail'],
    queryFn: fetchActiveEvent,
    refetchInterval: 60_000,
  })

  if (isLoading) return <SkeletonGrid count={3} height={96} />
  if (!event) {
    return (
      <EmptyState
        icon="EVT"
        message="No active event."
        hint="Special events are dark right now. Check back after reset."
      />
    )
  }

  const openQuests = event.quests.filter((q) => !q.claimed)
  const completedQuests = event.quests.filter((q) => q.claimed).length
  const redeemableMilestones = event.milestones.filter((m) => !m.redeemed && m.affordable)
  const clearedMilestones = event.milestones.filter((m) => m.redeemed).length
  const nextMilestone = event.milestones.find((m) => !m.redeemed) ?? null

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div
        className="card"
        style={{
          padding: 18,
          border: '1px solid rgba(255,215,0,0.18)',
          background:
            'linear-gradient(135deg, rgba(255,215,0,0.09), rgba(0,255,224,0.08) 55%, rgba(10,14,22,0.98))',
          boxShadow: '0 18px 40px rgba(0,0,0,0.22)',
        }}
      >
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--gold)' }}>
              Live Event
            </div>
            <h2 style={{ margin: 0 }}>{event.display_name}</h2>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              Window: {formatEventWindow(event.ends_at)}
            </div>
          </div>
          <div
            style={{
              minWidth: 120,
              padding: '10px 12px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.08)',
              background: 'rgba(4,6,12,0.52)',
              textAlign: 'right',
            }}
          >
            <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>
              Banked
            </div>
            <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--gold)' }}>
              {event.currency_emoji} {event.currency_balance}
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)' }}>{event.currency_name}</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginTop: 16 }}>
          <MetricCard label="Quest Board" value={`${completedQuests}/${event.quests.length}`} hint={`${openQuests.length} still open`} tone="accent" />
          <MetricCard label="Milestones" value={`${clearedMilestones}/${event.milestones.length}`} hint={`${redeemableMilestones.length} redeemable`} tone="gold" />
          <MetricCard
            label="Next Spend"
            value={nextMilestone ? `${nextMilestone.cost} ${event.currency_emoji}` : 'Cleared'}
            hint={nextMilestone ? nextMilestone.title : 'All milestones done'}
            tone="crimson"
          />
        </div>
      </div>

      {event.banner && <EventBannerCard banner={event.banner} />}
      {event.bundle && !event.bundle.purchased && <EventBundleCard bundle={event.bundle} />}

      <div className="card" style={{ padding: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>Quest Board</h3>
          <span className="muted" style={{ fontSize: 12 }}>{openQuests.length} open</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {event.quests.map((q) => {
            const progressPct = Math.max(0, Math.min(100, Math.round((q.progress / Math.max(1, q.goal)) * 100)))
            const isClaimable = q.completed && !q.claimed
            return (
              <div
                key={q.code}
                style={{
                  padding: 12,
                  borderRadius: 12,
                  border: '1px solid rgba(255,255,255,0.08)',
                  background: q.claimed ? 'rgba(34,197,94,0.07)' : 'rgba(255,255,255,0.02)',
                  opacity: q.claimed ? 0.8 : 1,
                }}
              >
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{q.title}</div>
                    <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3 }}>
                      {q.progress}/{q.goal} complete
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--gold)', whiteSpace: 'nowrap' }}>
                    +{q.currency_reward} {event.currency_emoji}
                  </div>
                  {isClaimable && (
                    <button
                      className="primary"
                      style={{ fontSize: 12 }}
                      onClick={async () => {
                        try {
                          await claimEventQuest(event.id, q.code)
                          toast.success('Quest claimed')
                          qc.invalidateQueries({ queryKey: ['active-event-detail'] })
                        } catch (e) {
                          toast.error(e instanceof Error ? e.message : 'Failed')
                        }
                      }}
                    >
                      Claim
                    </button>
                  )}
                  {q.claimed && <span className="muted" style={{ fontSize: 11 }}>Claimed</span>}
                </div>
                <div style={{ marginTop: 10, height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                  <div
                    style={{
                      width: `${progressPct}%`,
                      height: '100%',
                      background: isClaimable ? 'var(--gold)' : 'var(--accent)',
                      transition: 'width 0.2s ease',
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="card" style={{ padding: 16 }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <h3 style={{ margin: 0 }}>Milestone Track</h3>
          <span className="muted" style={{ fontSize: 12 }}>{redeemableMilestones.length} ready to redeem</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {event.milestones.map((m) => (
            <div
              key={m.idx}
              style={{
                padding: 12,
                borderRadius: 12,
                border: '1px solid rgba(255,255,255,0.08)',
                background: m.redeemed ? 'rgba(255,255,255,0.03)' : m.affordable ? 'rgba(255,215,0,0.08)' : 'rgba(255,255,255,0.02)',
                opacity: m.redeemed ? 0.72 : 1,
              }}
            >
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{m.title}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3 }}>
                    Spend {m.cost} {event.currency_emoji}
                  </div>
                </div>
                {m.redeemed ? (
                  <span className="muted" style={{ fontSize: 11 }}>Redeemed</span>
                ) : m.affordable ? (
                  <button
                    className="primary"
                    style={{ fontSize: 12 }}
                    onClick={async () => {
                      try {
                        await redeemMilestone(event.id, m.idx)
                        toast.success('Milestone redeemed')
                        qc.invalidateQueries({ queryKey: ['active-event-detail'] })
                      } catch (e) {
                        toast.error(e instanceof Error ? e.message : 'Failed')
                      }
                    }}
                  >
                    Redeem
                  </button>
                ) : (
                  <span className="muted" style={{ fontSize: 11 }}>
                    Need {Math.max(0, m.cost - event.currency_balance)}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// The featured paid-pull hero for the event. Indirect-money driver: pushes
// shard demand, which the shop sells. Routes straight to the Summon banner.
function EventBannerCard({ banner }: { banner: EventBanner }) {
  const capped = banner.per_account_cap > 0 && banner.owned >= banner.per_account_cap
  return (
    <div
      className="card"
      style={{
        padding: 16,
        border: '1px solid rgba(0,255,224,0.22)',
        background: 'linear-gradient(135deg, rgba(0,255,224,0.10), rgba(10,14,22,0.98))',
      }}
    >
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 14 }}>
        <div className="row" style={{ gap: 14, alignItems: 'center', flex: 1, minWidth: 0 }}>
          <img
            src={`/static/heroes/${banner.hero_template_code}_portrait.png`}
            alt={banner.hero_name ?? banner.hero_template_code}
            width={56}
            height={56}
            style={{ borderRadius: 12, objectFit: 'cover', border: '1px solid rgba(255,255,255,0.1)' }}
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = 'hidden' }}
          />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--accent)' }}>
              Featured Banner
            </div>
            <div style={{ fontWeight: 800, fontSize: 15 }}>{banner.hero_name ?? banner.hero_template_code}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>
              {banner.shard_cost} ✦ per pull
              {banner.per_account_cap > 0 && <> · {banner.owned}/{banner.per_account_cap} claimed</>}
            </div>
          </div>
        </div>
        {capped ? (
          <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>Maxed</span>
        ) : (
          <Link to="/app/summon" className="primary" style={{ fontSize: 12, whiteSpace: 'nowrap', textDecoration: 'none', padding: '8px 16px', borderRadius: 8 }}>
            Summon →
          </Link>
        )}
      </div>
    </div>
  )
}

// The limited real-money bundle. Direct-money driver. Hidden by the parent
// once purchased (one-per-account offers shouldn't keep nagging).
function EventBundleCard({ bundle }: { bundle: EventBundle }) {
  const price = `$${(bundle.price_cents / 100).toFixed(2)}`
  return (
    <div
      className="card"
      style={{
        padding: 16,
        border: '1px solid rgba(255,215,0,0.30)',
        background: 'linear-gradient(135deg, rgba(255,215,0,0.12), rgba(10,14,22,0.98))',
      }}
    >
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--gold)' }}>
            Limited Bundle
          </div>
          <div style={{ fontWeight: 800, fontSize: 15 }}>{bundle.title}</div>
          {bundle.description && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{bundle.description}</div>
          )}
        </div>
        <Link
          to="/app/shop"
          className="primary"
          style={{ fontSize: 12, whiteSpace: 'nowrap', textDecoration: 'none', padding: '8px 16px', borderRadius: 8, background: 'var(--gold)', color: '#3a2c00' }}
        >
          Get bundle · {price}
        </Link>
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint: string
  tone: 'accent' | 'gold' | 'crimson'
}) {
  const toneColor =
    tone === 'gold' ? 'var(--gold)' : tone === 'crimson' ? 'var(--crimson)' : 'var(--accent)'

  return (
    <div
      style={{
        padding: 12,
        borderRadius: 12,
        border: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(4,6,12,0.45)',
      }}
    >
      <div style={{ fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--muted)' }}>
        {label}
      </div>
      <div style={{ marginTop: 6, fontSize: 20, fontWeight: 800, color: toneColor }}>{value}</div>
      <div style={{ marginTop: 4, fontSize: 11, color: 'var(--muted)' }}>{hint}</div>
    </div>
  )
}
