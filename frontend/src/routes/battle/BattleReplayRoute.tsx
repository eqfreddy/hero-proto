import { useRef, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useBattleLog } from '../../hooks/useBattleLog'
import { BattleHUD } from '../../components/BattleHUD'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const Phaser: any

const CANVAS_W = 960
const CANVAS_H = 540
const SPRITE_SCALE = 2.5

const SOLDIER_FRAMES = { idle: 6, attack: 6, hurt: 4, death: 4 }
const ORC_FRAMES     = { idle: 6, attack: 6, hurt: 4, death: 4 }

export default function BattleReplayRoute() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const canvasRef = useRef<HTMLDivElement>(null)
  const { data: battle, isLoading, error } = useBattleLog(id)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!canvasRef.current || !battle) return

    class ReplayScene extends Phaser.Scene {
      private cursor = 0
      private timer: any | null = null
      private unitSprites: Map<string, any> = new Map()
      private deadUnits: Set<string> = new Set()

      preload() {
        const base = '/app/static/battle-assets/characters'
        const fw100 = { frameWidth: 100, frameHeight: 100 }
        this.load.spritesheet('soldier-idle',   `${base}/soldier/Soldier-Idle.png`,    fw100)
        this.load.spritesheet('soldier-attack',  `${base}/soldier/Soldier-Attack01.png`, fw100)
        this.load.spritesheet('soldier-hurt',    `${base}/soldier/Soldier-Hurt.png`,   fw100)
        this.load.spritesheet('soldier-death',   `${base}/soldier/Soldier-Death.png`,  fw100)
        this.load.spritesheet('orc-idle',        `${base}/orc/Orc-Idle.png`,           fw100)
        this.load.spritesheet('orc-attack',      `${base}/orc/Orc-Attack01.png`,       fw100)
        this.load.spritesheet('orc-hurt',        `${base}/orc/Orc-Hurt.png`,           fw100)
        this.load.spritesheet('orc-death',       `${base}/orc/Orc-Death.png`,          fw100)
      }

      create() {
        this.cameras.main.setBackgroundColor('#0b0d10')

        // Define animations
        this.anims.create({ key: 'soldier-idle',   frames: this.anims.generateFrameNumbers('soldier-idle',   { start: 0, end: SOLDIER_FRAMES.idle - 1 }),   frameRate: 8,  repeat: -1 })
        this.anims.create({ key: 'soldier-attack',  frames: this.anims.generateFrameNumbers('soldier-attack',  { start: 0, end: SOLDIER_FRAMES.attack - 1 }),  frameRate: 10, repeat: 0 })
        this.anims.create({ key: 'soldier-hurt',    frames: this.anims.generateFrameNumbers('soldier-hurt',    { start: 0, end: SOLDIER_FRAMES.hurt - 1 }),    frameRate: 10, repeat: 0 })
        this.anims.create({ key: 'soldier-death',   frames: this.anims.generateFrameNumbers('soldier-death',   { start: 0, end: SOLDIER_FRAMES.death - 1 }),   frameRate: 8,  repeat: 0 })
        this.anims.create({ key: 'orc-idle',        frames: this.anims.generateFrameNumbers('orc-idle',        { start: 0, end: ORC_FRAMES.idle - 1 }),        frameRate: 8,  repeat: -1 })
        this.anims.create({ key: 'orc-attack',      frames: this.anims.generateFrameNumbers('orc-attack',      { start: 0, end: ORC_FRAMES.attack - 1 }),      frameRate: 10, repeat: 0 })
        this.anims.create({ key: 'orc-hurt',        frames: this.anims.generateFrameNumbers('orc-hurt',        { start: 0, end: ORC_FRAMES.hurt - 1 }),        frameRate: 10, repeat: 0 })
        this.anims.create({ key: 'orc-death',       frames: this.anims.generateFrameNumbers('orc-death',       { start: 0, end: ORC_FRAMES.death - 1 }),       frameRate: 8,  repeat: 0 })

        const units = this.extractUnits()
        units.forEach((u: { uid: string; name?: string; side: string }, i: number) => {
          const isA = u.side === 'a'
          const x = isA ? 180 + i * 130 : CANVAS_W - 180 - i * 130
          const y = CANVAS_H / 2 + 20
          const key = isA ? 'soldier-idle' : 'orc-idle'
          const sprite = this.add.sprite(x, y, key)
          sprite.setScale(SPRITE_SCALE)
          if (!isA) sprite.setFlipX(true)  // orcs face left
          sprite.play(key)
          this.unitSprites.set(u.uid, { sprite, side: u.side })
          this.add.text(x, y + 70, u.name ?? u.uid, {
            fontSize: '11px', color: '#ffffff', align: 'center',
          }).setOrigin(0.5)
        })

        this.timer = this.time.addEvent({ delay: 600, callback: this.tick, callbackScope: this, loop: true })
      }

      private extractUnits(): { uid: string; name?: string; side: string }[] {
        const seen = new Map<string, { uid: string; name?: string; side: string }>()
        for (const ev of battle!.log) {
          for (const side of ['a', 'b']) {
            const uid = (ev as Record<string, unknown>)[`${side}_uid`] as string | undefined
            if (uid && !seen.has(uid)) seen.set(uid, { uid, name: (ev as Record<string, unknown>)[`${side}_name`] as string | undefined, side })
          }
        }
        return Array.from(seen.values())
      }

      private returnToIdle(uid: string) {
        if (this.deadUnits.has(uid)) return
        const entry = this.unitSprites.get(uid)
        if (!entry) return
        const { sprite, side } = entry
        const idleKey = side === 'a' ? 'soldier-idle' : 'orc-idle'
        sprite.play(idleKey)
      }

      private tick() {
        if (this.cursor >= battle!.log.length) {
          this.timer?.remove()
          setDone(true)
          return
        }
        const ev = battle!.log[this.cursor] as Record<string, unknown>

        if (ev.event === 'damage') {
          const targetUid = ev.target_uid as string | undefined
          if (targetUid && !this.deadUnits.has(targetUid)) {
            const entry = this.unitSprites.get(targetUid)
            if (entry) {
              const { sprite, side } = entry
              const hp = ev.hp as number | undefined
              if (hp !== undefined && hp <= 0) {
                this.deadUnits.add(targetUid)
                const deathKey = side === 'a' ? 'soldier-death' : 'orc-death'
                sprite.play(deathKey)
              } else {
                const hurtKey = side === 'a' ? 'soldier-hurt' : 'orc-hurt'
                sprite.play(hurtKey, true)
                sprite.once('animationcomplete', () => this.returnToIdle(targetUid))
              }
            }
          }

          // Play attack anim on attacker
          const attackerUid = ev.attacker_uid as string | undefined
          if (attackerUid && !this.deadUnits.has(attackerUid)) {
            const entry = this.unitSprites.get(attackerUid)
            if (entry) {
              const { sprite, side } = entry
              const attackKey = side === 'a' ? 'soldier-attack' : 'orc-attack'
              sprite.play(attackKey, true)
              sprite.once('animationcomplete', () => this.returnToIdle(attackerUid))
            }
          }
        }

        this.cursor++
      }
    }

    const game = new Phaser.Game({
      type: Phaser.AUTO,
      width: CANVAS_W,
      height: CANVAS_H,
      parent: canvasRef.current,
      scene: ReplayScene,
      scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
    })

    return () => { game.destroy(true) }
  }, [battle])

  if (isLoading) return <div style={{ color: 'var(--color-muted)', padding: 24 }}>Loading battle…</div>
  if (error) return <div style={{ color: 'var(--color-error)', padding: 24 }}>Failed to load battle.</div>

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh' }}>
      <div ref={canvasRef} style={{ width: '100%', height: '100%' }} />
      <BattleHUD
        teamA={[]}
        teamB={[]}
        onAct={undefined}
        pendingActorUid={null}
        validTargets={[]}
        acting={false}
        done={done}
        rewards={null}
        onClose={() => navigate('/app/stages')}
      />
    </div>
  )
}
