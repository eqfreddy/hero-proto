import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { fetchStory, chooseAlignment, type ChapterStatus } from '../api/story'
import { CHAPTER_NAMED_GEAR } from '../api/gear'
import { useMe } from '../hooks/useMe'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import { toast } from '../store/ui'

function AlignmentFork() {
  const [picking, setPicking] = useState<'RESISTANCE' | 'CORP_GREED' | null>(null)
  const [confirming, setConfirming] = useState(false)
  const qc = useQueryClient()

  async function confirm() {
    if (!picking) return
    setConfirming(true)
    try {
      await chooseAlignment(picking)
      await qc.invalidateQueries({ queryKey: ['me'] })
      await qc.invalidateQueries({ queryKey: ['story'] })
      toast.success(`Alignment locked: ${picking === 'RESISTANCE' ? 'The Resistance' : 'Corp Greed'}`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed')
      setPicking(null)
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div className="card" style={{
      border: '1px solid var(--accent)',
      borderRadius: 'var(--radius)',
      background: 'linear-gradient(135deg, var(--panel) 0%, color-mix(in srgb, var(--accent) 6%, var(--panel)) 100%)',
      padding: 24,
    }}>
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div style={{ fontSize: 18, fontWeight: 800, marginTop: 8 }}>Chapter 4 - The Alignment Fork</div>
        <div className="muted" style={{ fontSize: 13, marginTop: 8, maxWidth: 480, marginInline: 'auto' }}>
          You've seen the Corp. You've seen behind the curtain. Now you choose: fight it from the inside, or become it. This decision is permanent.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: picking ? 16 : 0 }}>
        <button
          onClick={() => setPicking('RESISTANCE')}
          style={{
            padding: '20px 16px',
            borderRadius: 'var(--radius)',
            border: `2px solid ${picking === 'RESISTANCE' ? '#4eb8ff' : 'var(--border)'}`,
            background: picking === 'RESISTANCE' ? 'color-mix(in srgb, #4eb8ff 15%, var(--bg-inset))' : 'var(--bg-inset)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 800, color: '#4eb8ff' }}>The Resistance</div>
          <div className="muted" style={{ fontSize: 11 }}>Fight the Corp. Leak the memo. Get The Whistleblower.</div>
        </button>

        <button
          onClick={() => setPicking('CORP_GREED')}
          style={{
            padding: '20px 16px',
            borderRadius: 'var(--radius)',
            border: `2px solid ${picking === 'CORP_GREED' ? '#ffd166' : 'var(--border)'}`,
            background: picking === 'CORP_GREED' ? 'color-mix(in srgb, #ffd166 12%, var(--bg-inset))' : 'var(--bg-inset)',
            cursor: 'pointer',
            transition: 'all 0.2s',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <div style={{ fontSize: 15, fontWeight: 800, color: '#ffd166' }}>Corp Greed</div>
          <div className="muted" style={{ fontSize: 11 }}>Become the Corp. Close the deal. Get The Successor.</div>
        </button>
      </div>

      {picking && (
        <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 4 }}>
          <button className="secondary" onClick={() => setPicking(null)} style={{ fontSize: 13 }}>Back</button>
          <button
            className="primary"
            onClick={confirm}
            disabled={confirming}
            style={{ fontSize: 13, background: picking === 'RESISTANCE' ? '#4eb8ff' : '#ffd166', color: '#0b0d10' }}
          >
            {confirming ? '...' : `Confirm - ${picking === 'RESISTANCE' ? 'The Resistance' : 'Corp Greed'}`}
          </button>
        </div>
      )}
    </div>
  )
}

function ChapterCard({ ch }: { ch: ChapterStatus }) {
  const [open, setOpen] = useState(false)
  const clearedCount = ch.stages.filter((stage) => stage.cleared).length
  const totalCount = ch.stages.length
  const factionColor = ch.required_alignment === 'RESISTANCE' ? '#4eb8ff'
    : ch.required_alignment === 'CORP_GREED' ? '#ffd166'
      : 'var(--accent)'

  return (
    <div className="card" style={{ borderColor: ch.required_alignment ? factionColor : undefined, opacity: ch.unlocked ? 1 : 0.55 }}>
      <div
        className="row"
        style={{ justifyContent: 'space-between', cursor: 'pointer' }}
        onClick={() => ch.unlocked && setOpen((value) => !value)}
      >
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
          <span style={{ fontSize: 24 }}>{ch.icon}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>{ch.title}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{ch.blurb}</div>
            {ch.required_alignment && (
              <div style={{
                display: 'inline-block',
                marginTop: 4,
                fontSize: 10,
                fontWeight: 700,
                padding: '1px 6px',
                borderRadius: 99,
                background: `color-mix(in srgb, ${factionColor} 18%, transparent)`,
                border: `1px solid color-mix(in srgb, ${factionColor} 40%, transparent)`,
                color: factionColor,
              }}>
                {ch.required_alignment === 'RESISTANCE' ? 'Resistance Path' : 'Corp Greed Path'}
              </div>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>
            {clearedCount}/{totalCount} stages
          </div>
          {ch.completed && !ch.reward_claimed && (
            <span style={{ fontSize: 11, color: 'var(--good)', fontWeight: 600 }}>Claim reward</span>
          )}
          {ch.reward_claimed && (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Claimed</span>
          )}
          {!ch.unlocked && (
            <span style={{ fontSize: 11, color: 'var(--muted)' }}>Lv {ch.unlock_level}</span>
          )}
        </div>
      </div>

      {ch.unlocked && (
        <div style={{ background: 'var(--bg-inset)', borderRadius: 4, height: 4, marginTop: 12, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            borderRadius: 4,
            background: ch.completed ? 'var(--good)' : factionColor,
            width: `${ch.completion_pct}%`,
            transition: 'width 0.4s ease',
          }} />
        </div>
      )}

      {ch.unlocked && CHAPTER_NAMED_GEAR[ch.code] && (
        <div style={{
          marginTop: 12,
          padding: '10px 12px',
          borderRadius: 'var(--radius-sm)',
          background: ch.reward_claimed
            ? 'color-mix(in srgb, var(--r-legendary) 8%, var(--bg-inset))'
            : 'var(--bg-inset)',
          border: `1px solid ${ch.reward_claimed ? 'var(--r-legendary)' : 'var(--border)'}`,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <span style={{ fontSize: 22, opacity: ch.reward_claimed ? 1 : 0.55 }}>
            {CHAPTER_NAMED_GEAR[ch.code].icon}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: ch.reward_claimed ? 'var(--r-legendary)' : 'var(--muted)' }}>
              {ch.reward_claimed ? 'Unlocked: ' : 'Locked: '}
              {CHAPTER_NAMED_GEAR[ch.code].name}
            </div>
            <div className="muted" style={{ fontSize: 10 }}>
              Legendary {CHAPTER_NAMED_GEAR[ch.code].slot.toLowerCase()} piece
              {ch.reward_claimed ? ' - in inventory' : ' - clear chapter to unlock'}
            </div>
          </div>
        </div>
      )}

      {open && ch.unlocked && (
        <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {ch.stages.map((stage, index) => (
            <div key={stage.code} style={{
              display: 'flex',
              gap: 10,
              alignItems: 'flex-start',
              padding: '10px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-inset)',
              opacity: stage.unlocked ? 1 : 0.4,
            }}>
              <span style={{ fontSize: 18, lineHeight: 1, marginTop: 1, flexShrink: 0 }}>
                {stage.cleared ? 'Done' : stage.unlocked ? 'Open' : 'Locked'}
              </span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>Stage {index + 1} - {stage.name}</div>
                {stage.intro && (
                  <div className="muted" style={{ fontSize: 11, marginTop: 3, fontStyle: 'italic' }}>
                    <strong>{stage.intro.speaker}:</strong> "{stage.intro.text.slice(0, 120)}{stage.intro.text.length > 120 ? '...' : ''}"
                  </div>
                )}
              </div>
            </div>
          ))}
          {ch.alignment_hero && (
            <div style={{
              marginTop: 4,
              padding: '10px 14px',
              borderRadius: 'var(--radius-sm)',
              background: `color-mix(in srgb, ${factionColor} 10%, var(--bg-inset))`,
              border: `1px solid color-mix(in srgb, ${factionColor} 30%, transparent)`,
              fontSize: 12,
              fontWeight: 600,
            }}>
              Chapter reward: Exclusive hero unlocked on completion
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function StoryRoute() {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const { data, isLoading } = useQuery({ queryKey: ['story'], queryFn: fetchStory })

  if (isLoading) return <SkeletonGrid count={3} height={80} />
  if (!data) return <EmptyState icon="Story" message="Story unavailable." />

  const showAlignmentFork = me
    && parseInt(String(me.account_level), 10) >= 50
    && me.faction === 'EXILE'
    && !me.alignment_chosen_at

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <h2 style={{ margin: 0 }}>Story</h2>
        <div className="muted" style={{ fontSize: 12 }}>Account Level <strong>{data.account_level}</strong></div>
      </div>

      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>Ready to push the next node?</div>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            Story tracks the arc. Stages are where you actually crack heads and clear progress.
          </div>
        </div>
        <button className="primary" onClick={() => navigate('/app/stages')}>
          Continue Campaign
        </button>
      </div>

      {showAlignmentFork && <AlignmentFork />}

      {data.chapters.map((chapter) => (
        <ChapterCard key={chapter.code} ch={chapter} />
      ))}

      <div className="card" style={{ opacity: 0.55, borderColor: 'var(--border)', cursor: 'default' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <span style={{ fontSize: 24 }}>?</span>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>Next Arc - The Merger</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                Your branch choice feeds the next arc. More stages, tougher checks, and the next chapter reward ladder land here.
              </div>
              <div style={{
                display: 'inline-block',
                marginTop: 6,
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 99,
                background: 'color-mix(in srgb, var(--muted) 12%, transparent)',
                border: '1px solid color-mix(in srgb, var(--muted) 25%, transparent)',
                color: 'var(--muted)',
              }}>
                Clears after the current chapter path
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ fontSize: 11, color: 'var(--muted)' }}>More stages incoming</div>
          </div>
        </div>
      </div>
    </div>
  )
}
