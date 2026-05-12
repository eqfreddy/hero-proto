/**
 * Clip-name resolver for the Battle 3D viewer.
 *
 * Each archetype declares ordered candidate clip names per canonical slot
 * (idle/attack/hit/die). At runtime, `resolveClip` picks the first candidate
 * that exists on the loaded `AnimationClip[]` for that archetype.
 *
 * All shipped archetypes are Quaternius RPG Characters (chibi pack). Each
 * `.glb` carries its own embedded clip set; there is no shared animation
 * file. Clip-name typo `RecieveHit` is preserved — canonical in the source.
 *
 * `engineer` is intentionally absent — no engineer template wired yet; the
 * `engineer` rig name is remapped to `ranger` archetype upstream in
 * `archetypeMap.ts`. Monk rig is staged at /heroes/monk.glb for when an
 * engineer template ships.
 */

export type CanonicalClip = "idle" | "attack" | "hit" | "die";

export const ARCHETYPE_CLIP_MAP: Record<string, Record<CanonicalClip, string[]>> = {
  knight: {
    idle: ["Idle_Weapon", "Idle_Attacking", "Idle"],
    attack: ["Sword_Attack", "Sword_Attack2"],
    hit: ["RecieveHit"],
    die: ["Death"],
  },
  barbarian: {
    idle: ["Idle_Weapon", "Idle_Attacking", "Idle"],
    attack: ["Sword_Attack2", "Sword_Attack"],
    hit: ["RecieveHit"],
    die: ["Death"],
  },
  mage: {
    idle: ["Idle_Weapon", "Idle_Attacking", "Idle"],
    attack: ["Staff_Attack", "Spell1", "Spell2"],
    hit: ["RecieveHit", "RecieveHit_2"],
    die: ["Death"],
  },
  rogue: {
    idle: ["Attacking_Idle", "Idle"],
    attack: ["Dagger_Attack", "Dagger_Attack2"],
    hit: ["RecieveHit", "RecieveHit_2"],
    die: ["Death"],
  },
  rogue_hooded: {
    idle: ["Attacking_Idle", "Idle"],
    attack: ["Dagger_Attack2", "Dagger_Attack"],
    hit: ["RecieveHit", "RecieveHit_2"],
    die: ["Death"],
  },
  ranger: {
    idle: ["Idle_Weapon", "Idle_Attacking", "Idle"],
    attack: ["Bow_Shoot", "Bow_Draw"],
    hit: ["RecieveHit", "RecieveHit_2"],
    die: ["Death"],
  },
  druid: {
    idle: ["Idle_Weapon", "Idle"],
    attack: ["Staff_Attack", "Spell1", "Punch"],
    hit: ["RecieveHit"],
    die: ["Death"],
  },
  monk: {
    idle: ["Idle_Attacking", "Idle"],
    attack: ["Attack", "Attack2"],
    hit: ["RecieveHit", "RecieveHit_2"],
    die: ["Death"],
  },
};

export function resolveClip(
  archetype: string,
  canonical: CanonicalClip,
  available: string[],
): string | null {
  const candidates = ARCHETYPE_CLIP_MAP[archetype]?.[canonical];
  if (!candidates) return null;
  for (const name of candidates) {
    if (available.includes(name)) return name;
  }
  return null;
}
