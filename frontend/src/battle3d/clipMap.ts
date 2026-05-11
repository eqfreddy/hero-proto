/**
 * Clip-name resolver for the Battle 3D viewer.
 *
 * Each archetype declares ordered candidate clip names per canonical slot
 * (idle/attack/hit/die). At runtime, `resolveClip` picks the first candidate
 * that exists on the loaded `AnimationClip[]` for that archetype.
 *
 * The 6 KayKit archetypes share a single skeleton; their clips live in
 * `kaykit_general.glb` and are reused via Three.js skeleton retargeting,
 * so they share the same candidate set.
 *
 * Druid (Quaternius Cleric) ships embedded clips with a different naming
 * convention (`RecieveHit` misspelling preserved — canonical in source asset).
 *
 * `engineer` is intentionally absent — no engineer model in v1; the
 * `engineer` rig name is remapped to `ranger` archetype upstream in
 * `archetypeMap.ts`.
 */

export type CanonicalClip = "idle" | "attack" | "hit" | "die";

// Shared candidate set for the 6 KayKit archetypes (shared rig, shared clip
// names sourced from kaykit_general.glb). `Throw` is the v1 attack stand-in;
// v1.1 follow-up: source a real melee clip.
const KAYKIT_CLIPS: Record<CanonicalClip, string[]> = {
  idle: ["Idle_A", "Idle_B"],
  attack: ["Throw"],
  hit: ["Hit_A", "Hit_B"],
  die: ["Death_A", "Death_B"],
};

export const ARCHETYPE_CLIP_MAP: Record<string, Record<CanonicalClip, string[]>> = {
  knight: KAYKIT_CLIPS,
  barbarian: KAYKIT_CLIPS,
  mage: KAYKIT_CLIPS,
  rogue: KAYKIT_CLIPS,
  rogue_hooded: KAYKIT_CLIPS,
  ranger: KAYKIT_CLIPS,
  druid: {
    idle: ["Idle", "Idle_Weapon"],
    attack: ["Staff_Attack", "Spell1", "Punch"],
    hit: ["RecieveHit"],
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
