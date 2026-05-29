import { useState, type CSSProperties } from 'react'
import type { HeroTemplate } from '../types'
import { assetUrl } from '../api/client'

const FRAME_BY_RARITY: Record<HeroTemplate['rarity'], string | null> = {
  COMMON: 'COMMON',
  UNCOMMON: 'UNCOMMON',
  RARE: 'RARE',
  EPIC: 'EPIC',
  LEGENDARY: 'LEGENDARY',
  MYTH: 'LEGENDARY',
}

const FACTION_ACCENT: Record<HeroTemplate['faction'], string> = {
  RESISTANCE: '#00d4ff',
  CORP_GREED: '#ffd166',
  EXILE: '#b388ff',
  NEUTRAL: '#9ca7b3',
}

const FACTION_LABEL: Record<HeroTemplate['faction'], string> = {
  RESISTANCE: 'RES',
  CORP_GREED: 'CORP',
  EXILE: 'EXILE',
  NEUTRAL: 'NEUT',
}

interface HeroPortraitProps {
  code: string
  name: string
  rarity: HeroTemplate['rarity']
  role: HeroTemplate['role']
  faction: HeroTemplate['faction']
  style?: CSSProperties
  imageStyle?: CSSProperties
  showFactionTag?: boolean
  showRoleBadge?: boolean
  artPriority?: 'card' | 'portrait' | 'bust'
}

export function HeroPortrait({
  code,
  name,
  rarity,
  role,
  faction,
  style,
  imageStyle,
  showFactionTag = true,
  showRoleBadge = true,
  artPriority = 'card',
}: HeroPortraitProps) {
  const fallbackOrder = artPriority === 'portrait'
    ? ['portrait', 'card', 'bust', 'placeholder'] as const
    : artPriority === 'bust'
      ? ['bust', 'card', 'portrait', 'placeholder'] as const
      : ['card', 'bust', 'portrait', 'placeholder'] as const
  const [imageStage, setImageStage] = useState<(typeof fallbackOrder)[number]>(fallbackOrder[0])
  const [roleBadgeHidden, setRoleBadgeHidden] = useState(false)
  const [frameHidden, setFrameHidden] = useState(false)

  const frameCode = FRAME_BY_RARITY[rarity]
  const accent = FACTION_ACCENT[faction] ?? '#9ca7b3'
  const src = imageStage === 'card'
    ? assetUrl(`/app/static/heroes/cards/${code}.png`)
    : imageStage === 'portrait'
      ? assetUrl(`/app/static/heroes/${code}.svg`)
      : imageStage === 'bust'
        ? assetUrl(`/app/static/heroes/busts/${code}.png`)
        : `/app/placeholder/hero/${code}.svg`

  return (
    <div
      title={`${name} · ${rarity} · ${role} · ${faction}`}
      style={{
        position: 'relative',
        aspectRatio: '1',
        overflow: 'hidden',
        borderRadius: 10,
        background: `linear-gradient(180deg, color-mix(in srgb, ${accent} 12%, #101724) 0%, #060b13 100%)`,
        border: `1px solid color-mix(in srgb, ${accent} 42%, rgba(255,255,255,0.08))`,
        boxShadow: `inset 0 1px 0 color-mix(in srgb, ${accent} 20%, transparent)`,
        ...style,
      }}
    >
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'repeating-linear-gradient(135deg, rgba(255,255,255,0.04) 0 1px, transparent 1px 8px)',
          opacity: 0.7,
        }}
      />
      <img
        src={src}
        alt={name}
        onError={() => {
          setImageStage((stage) => {
            const currentIndex = fallbackOrder.indexOf(stage)
            if (currentIndex >= 0 && currentIndex < fallbackOrder.length - 1) return fallbackOrder[currentIndex + 1]
            return stage
          })
        }}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'contain',
          objectPosition: 'center bottom',
          padding: imageStage === 'card' ? '4px' : '0',
          ...imageStyle,
        }}
      />
      {!frameHidden && frameCode && (
        <img
          src={assetUrl(`/app/static/frames/${frameCode}.svg`)}
          alt=""
          aria-hidden="true"
          onError={() => setFrameHidden(true)}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        />
      )}
      {showRoleBadge && !roleBadgeHidden && (
        <div
          style={{
            position: 'absolute',
            top: 6,
            left: 6,
            width: 26,
            height: 26,
            borderRadius: 999,
            display: 'grid',
            placeItems: 'center',
            background: 'rgba(5, 8, 14, 0.82)',
            border: `1px solid color-mix(in srgb, ${accent} 35%, rgba(255,255,255,0.12))`,
            boxShadow: '0 2px 8px rgba(0,0,0,0.24)',
          }}
        >
          <img
            src={assetUrl(`/app/static/roles/${role}.svg`)}
            alt=""
            aria-hidden="true"
            onError={() => setRoleBadgeHidden(true)}
            style={{ width: 14, height: 14 }}
          />
        </div>
      )}
      {showFactionTag && (
        <div
          style={{
            position: 'absolute',
            left: 6,
            bottom: 6,
            padding: '2px 6px',
            borderRadius: 999,
            background: 'rgba(5, 8, 14, 0.84)',
            border: `1px solid color-mix(in srgb, ${accent} 35%, rgba(255,255,255,0.12))`,
            color: accent,
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: '0.08em',
          }}
        >
          {FACTION_LABEL[faction] ?? faction}
        </div>
      )}
    </div>
  )
}
