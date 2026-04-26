# Battle rig event mapping — spec for production rigs

This is the contract between the **combat resolver** (server) and any
**DragonBones rig** dropped into `app/static/battle-rigs/`. Whoever
builds an ATK / DEF / SUP rig in Moho or the DragonBones editor needs
to expose at least these animation names; the registry does the
event→animation routing, but the rig must have something to play.

## Required animation names

Every production rig **must** export an armature with at least these
animations. Names are case-sensitive.

| Name | When it plays | Loop? | Min duration | Notes |
|------|---------------|-------|--------------|-------|
| `idle` | Default state, between turns | ✅ yes | 0.8 – 1.2 s | Loops in place. Subtle bob / breath. Played the whole time the unit is alive and not acting. |
| `attack_basic` | `DAMAGE` event with `via=BASIC` | ❌ once | 0.6 – 0.9 s | Quick swing / shot. Returns to idle automatically. |
| `attack_special` | `DAMAGE` with `via=SPECIAL` (single-target damage signature) | ❌ once | 0.9 – 1.4 s | Heavier wind-up. The damage popup spawns mid-anim — keep impact frame around 60 % through. |
| `attack_special_aoe` | `AOE_DAMAGE`, `BOSS_PHASE`, `HAIL_MARY` | ❌ once | 1.0 – 1.6 s | Big sweep / radial effect. Slower, more cinematic. |
| `attack_special_heal` | `HEAL`, `AOE_HEAL`, `REVIVE`, `AOE_REVIVE` | ❌ once | 0.9 – 1.4 s | Cast-style. SUP rig especially needs this to feel different from damage. |
| `attack_special_buff` | `BUFF`, `AOE_BUFF`, `SHIELD`, `CLEANSE` | ❌ once | 0.8 – 1.2 s | Self-pose / arm-raise. No projectile. |
| `hit` | This unit was the **target** of `DAMAGE` or `REFLECT` | ❌ once | 0.25 – 0.45 s | Recoil flinch. **Must be short** — overlapping events fire fast. |
| `death` | `DEATH` event with this unit as `source` | ❌ once | 0.8 – 1.5 s | Hold the final pose; the unit stays in death-pose until the battle restarts. |
| `victory` | End of battle, on the winning side | ✅ yes (loops on hold) | 1.0 – 2.0 s | Optional but recommended. Plays after the last log event when our side won. |

## Optional / nice-to-haves

- `walk` — entrance / retreat / dodging. The current viewer doesn't use
  it but space is reserved in the registry so it can land later
  (e.g., when active combat UI ships in Phase 3.2).
- `cast_loop` — looping mid-cast pose. Use for long charge-up specials.
- `taunt`, `provoke` — flavor animations the player triggers manually
  in the post-Phase-3 active-combat layer.

## Rig orientation

- Rig **faces right** in its native authored orientation. The viewer
  flips Side B units by setting `armature.scale.x = -scale`.
- Anchor / origin point should be at the **feet center**. The viewer
  positions the armature by its feet at `slotPosition(side, idx)`.
- Hit-react motion should kick **leftward** (away from attacker on the
  right). Side B's mirroring handles the inverse automatically.

## Skin slots

Production rigs should expose two named slots so the viewer can skin
them per-hero without authoring 30 different skeletons:

| Slot | Required? | Texture | Source |
|------|-----------|---------|--------|
| `head` | ✅ yes | 256×256 transparent PNG | `/app/static/heroes/busts/<code>.png` (already auto-cropped to 512×512; the runtime scales it down) |
| `weapon` | optional | varies (sword / laptop / gun / pen) | Per-hero override; default rig weapon is fine for v1 |

**Skin-swap call** (in the prototype viewer):

```js
// armature.armature.getSlot("head").displayList = [newSprite];
// or via factory.changeSkin / replaceSlotDisplay — see the
// DragonBones runtime docs. The prototype viewer will fold this
// into the actor build step once head_slot is set in registry.json.
```

## Combat-log → animation route table (authoritative)

This table mirrors the `EVENT_TO_ANIM` map in `battle-pixi.html`. If
new event types land in the resolver, add a route here and keep both
in sync.

| Combat log event `type` | Source plays | Target plays |
|-------------------------|--------------|--------------|
| `DAMAGE` (via=BASIC) | `attack_basic` | `hit` |
| `DAMAGE` (via=SPECIAL) | `attack_special` | `hit` |
| `AOE_DAMAGE` | `attack_special_aoe` | `hit` (every target) |
| `HEAL` / `AOE_HEAL` | `attack_special_heal` | (target glows; no anim required) |
| `BUFF` / `AOE_BUFF` | `attack_special_buff` | (target gets buff icon) |
| `SHIELD` | `attack_special_buff` | — |
| `CLEANSE` | `attack_special_buff` | — |
| `REVIVE` / `AOE_REVIVE` | `attack_special_heal` | dead unit returns to idle |
| `BOSS_PHASE` | `attack_special_aoe` | every live enemy plays `hit` |
| `HAIL_MARY` | `attack_special_aoe` | varies by role flavor |
| `REFLECT` | (no source anim — counter event) | original attacker plays `hit` |
| `DEATH` | `death` (and stays in pose) | — |
| `STATUS_APPLIED` / `STATUS_EXPIRED` | (no anim — UI overlay only) | — |
| `LIFESTEAL` | (no anim — log only; viewer can heal-pulse the source) | — |
| `WAVE_START` | (no anim — clears prior state) | — |
| `FACTION_SYNERGY` | (no anim — banner overlay only) | — |

## Audio sync points

The Phaser viewer plays sound effects at specific event types via
`window.sound.play(...)`. Hooks the Pixi prototype should fire too
(currently TODO):

- `attack_basic` → `combat_swing`
- `attack_special` → `combat_special_charge` (then `_release` on impact)
- `hit` → `combat_hit`
- `death` → `combat_death`
- `BOSS_PHASE` → `cinematic_boss_phase`
- `HAIL_MARY` → `cinematic_hail_mary`

## Authoring checklist (for whoever builds the rigs)

1. ☐ Pick a tool — DragonBones editor (free, native) **or** Moho /
   Adobe Animate with a DragonBones export pipeline.
2. ☐ Author the **ATK rig** first as the proof: idle + attack_basic +
   attack_special + hit + death. ~3 days for a novice rigger.
3. ☐ Run a 1-hour spike to confirm the export round-trips back into
   the runtime cleanly (open in the editor, play every animation,
   no broken frames).
4. ☐ Drop the rig at `app/static/battle-rigs/atk/`:
   ```
   atk/
     atk_ske.json
     atk_tex.json
     atk_tex.png
   ```
5. ☐ Update `app/static/battle-rigs/registry.json` — add an entry to
   `rigs` keyed `"atk"`, mapping the standard animation names to your
   actual exported names. Then change a unit's `rig` field to `"atk"`
   and reload `battle-pixi.html?id=<some-battle>` to see it land.
6. ☐ Rinse + repeat for DEF and SUP rigs.
7. ☐ Once all three ship: bulk-rewrite the `units` block in registry
   to `{rig: <role-driven>}`. Optionally script this from `app/seed.py`
   so it stays auto-synced as new heroes are added.
8. ☐ Polish pass — head-skin slot wiring, particle hooks, faction
   recolors. ~2 days.

## Where to test

Once rigs land:

1. Open the dashboard, win any battle on Stages.
2. Click **🦴 Pixi proto** in the post-mortem (next to "watch replay").
3. The prototype viewer loads at `/app/battle-pixi.html?id=<id>` with
   the rigs you just shipped.
4. Iterate.

## Why we're keeping both viewers

`battle-phaser.html` stays as the production viewer until the
DragonBones rigs are authored. The Pixi prototype is a side-by-side
preview, not a replacement. Once Plan B is sign-off complete, the
Phaser viewer either:

a) Gets retired (delete + redirect /app/battle-phaser.html → Pixi version), or
b) Becomes the "lite" replay (no rigs, just the cards) for environments
   where DragonBones can't load (low-end mobile, screen readers).

Decision deferred until we see how production rigs perform.
