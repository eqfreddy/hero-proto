import { useRef, useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useBattleLog } from '../../hooks/useBattleLog'
import { BattleHUD } from '../../components/BattleHUD'

/* eslint-disable @typescript-eslint/no-explicit-any */
declare const Phaser: any

const CANVAS_W = 960
const CANVAS_H = 540

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

      create() {
        this.cameras.main.setBackgroundColor('#0b0d10')

        const units = this.extractUnits()
        units.forEach((u: { uid: string; name?: string; side: string }, i: number) => {
          const x = u.side === 'a' ? 200 + i * 120 : CANVAS_W - 200 - i * 120
          const y = CANVAS_H / 2
          const rect = this.add.rectangle(x, y, 60, 80, u.side === 'a' ? 0x59a0ff : 0xff7a59)
          this.unitSprites.set(u.uid, rect)
          this.add.text(x, y + 50, u.name ?? u.uid, {
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

      private tick() {
        if (this.cursor >= battle!.log.length) {
          this.timer?.remove()
          setDone(true)
          return
        }
        const ev = battle!.log[this.cursor] as Record<string, unknown>
        if (ev.event === 'damage') {
          const targetSprite = this.unitSprites.get(ev.target_uid as string)
          if (targetSprite) {
            this.tweens.add({ targets: targetSprite, alpha: 0.3, duration: 80, yoyo: true })
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
