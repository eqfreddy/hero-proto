import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCollections, claimCollection, openEightTrack } from '../api/collections'
import { CollectionLootPopup } from '../components/CollectionLootPopup'
import { useMe } from '../hooks/useMe'
import { toast } from '../store/ui'
import { SkeletonGrid } from '../components/SkeletonGrid'
import { EmptyState } from '../components/EmptyState'
import type { Collection, CollectionDrop } from '../types'

type Filter = 'ALL' | 'UNCOMMON' | 'RARE' | 'EPIC' | 'LEGENDARY' | 'completed'

const RARITY_COLORS: Record<string, string> = {
  UNCOMMON: '#2ecc71',
  RARE:     '#3498db',
  EPIC:     '#9b59b6',
  LEGENDARY:'#f39c12',
}

const BRACKETS = ['1-20', '21-40', '41-60'] as const

export default function CollectionsRoute() {
  const qc = useQueryClient()
  const { data: me } = useMe()
  const [filter, setFilter] = useState<Filter>('ALL')
  const [lootPieces, setLootPieces] = useState<CollectionDrop[] | null>(null)
  const [lootMeta, setLootMeta] = useState<{ name: string; owned: number; total: number } | null>(null)

  const { data: collections, isLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: fetchCollections,
    refetchInterval: 60_000,
  })

  const claimMut = useMutation({
    mutationFn: (code: string) => claimCollection(code),
    onSuccess: () => {
      toast.success('Reward claimed!')
      qc.invalidateQueries({ queryKey: ['collections'] })
      qc.invalidateQueries({ queryKey: ['me'] })
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Claim failed'),
  })

  const openMut = useMutation({
    mutationFn: openEightTrack,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['me'] })
      qc.invalidateQueries({ queryKey: ['collections'] })
      setLootPieces(data.pieces)
      setLootMeta(null)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Open failed'),
  })

  if (isLoading || !collections) return <SkeletonGrid count={6} height={100} />
  if (collections.length === 0) return <EmptyState icon="📜" message="No collections available yet." />

  const visible = collections.filter((c) => {
    if (filter === 'completed') return c.completed_at !== null
    if (filter === 'ALL') return true
    return c.rarity === filter
  })

  const byBracket = (bracket: string) =>
    visible.filter((c) => c.level_bracket === bracket)

  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ margin: 0 }}>📜 Collections</h2>
        <button
          className="primary"
          disabled={!me || me.eight_tracks <= 0 || openMut.isPending}
          onClick={() => openMut.mutate()}
          title={me && me.eight_tracks > 0 ? `Open 8-track (${me.eight_tracks} owned)` : 'No 8-tracks in inventory'}
        >
          {openMut.isPending ? '…' : `🎵 Open 8-Track${me && me.eight_tracks > 0 ? ` (${me.eight_tracks})` : ''}`}
        </button>
      </div>

      {/* Filter bar */}
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        {(['ALL', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY', 'completed'] as Filter[]).map((f) => (
          <button
            key={f}
            className={filter === f ? 'primary' : 'secondary'}
            style={{ fontSize: 11, padding: '4px 10px', ...(f !== 'ALL' && f !== 'completed' ? { color: RARITY_COLORS[f] } : {}) }}
            onClick={() => setFilter(f)}
          >
            {f === 'completed' ? '✓ Completed' : f}
          </button>
        ))}
      </div>

      {/* Grouped by bracket */}
      {BRACKETS.map((bracket) => {
        const items = byBracket(bracket)
        if (items.length === 0) return null
        return (
          <div key={bracket}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
              Levels {bracket}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
              {items.map((c) => (
                <CollectionCard
                  key={c.code}
                  collection={c}
                  onClaim={() => claimMut.mutate(c.code)}
                  claimBusy={claimMut.isPending && claimMut.variables === c.code}
                />
              ))}
            </div>
          </div>
        )
      })}

      {visible.length === 0 && (
        <EmptyState icon="📜" message="No collections match this filter." />
      )}

      {/* 8-track loot popup */}
      {lootPieces && (
        <CollectionLootPopup
          pieces={lootPieces}
          collectionName={lootMeta?.name}
          ownedCount={lootMeta?.owned ?? 0}
          totalCount={lootMeta?.total ?? 0}
          onInspect={undefined}
          onClose={() => setLootPieces(null)}
        />
      )}
    </div>
  )
}

function CollectionCard({ collection: c, onClaim, claimBusy }: {
  collection: Collection
  onClaim: () => void
  claimBusy: boolean
}) {
  const color = RARITY_COLORS[c.rarity] ?? 'var(--border)'
  const pct = c.total_count > 0 ? (c.owned_count / c.total_count) * 100 : 0

  return (
    <div className="card" style={{ padding: 14, borderLeft: `3px solid ${color}` }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700 }}>{c.name}</div>
          <div style={{ fontSize: 10, color: color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            {c.rarity}
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'right' }}>
          {c.owned_count}/{c.total_count}
          {c.completed_at && <div style={{ color: '#ffd700' }}>✓ done</div>}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ margin: '8px 0', height: 4, background: 'var(--bg-inset)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>

      {/* Piece icons */}
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
        {c.pieces.map((p) => (
          <span
            key={p.code}
            title={p.name}
            style={{
              fontSize: 16,
              opacity: p.owned ? 1 : 0.3,
              filter: p.is_completion_piece && p.owned ? 'drop-shadow(0 0 4px #ffd700)' : undefined,
            }}
          >
            {p.icon}
          </span>
        ))}
      </div>

      {c.reward_summary && (
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 8 }}>
          Reward: {c.reward_summary}
        </div>
      )}

      {c.claimable && !c.claimed_at && (
        <button className="primary" style={{ width: '100%', fontSize: 12 }} disabled={claimBusy} onClick={onClaim}>
          {claimBusy ? '…' : '🎁 Claim Reward'}
        </button>
      )}
      {c.claimed_at && (
        <div style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center' }}>Reward claimed ✓</div>
      )}
    </div>
  )
}
