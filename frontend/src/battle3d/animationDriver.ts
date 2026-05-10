import { resolveClip, type CanonicalClip } from "./clipMap";

export interface UnitRig {
  uid: string;
  archetype: string;
  availableClips: string[];
  play: (clipName: string) => void;
  flashWhite: () => void;
  floatDamageNumber: (amount: number) => void;
  fade: (opacity: number) => void;
}

export type CombatEvent =
  | { type: "DAMAGE"; actor_uid: string; target_uid: string; amount: number }
  | { type: "DEATH"; target_uid: string }
  | { type: "SPECIAL"; actor_uid: string }
  | { type: string; [k: string]: unknown };

function playCanonical(rig: UnitRig, canonical: CanonicalClip): boolean {
  const clip = resolveClip(rig.archetype, canonical, rig.availableClips);
  if (clip) {
    rig.play(clip);
    return true;
  }
  // eslint-disable-next-line no-console
  console.warn(`[battle-3d] no '${canonical}' clip for archetype '${rig.archetype}'`);
  return false;
}

export function handleEvent(event: CombatEvent, rigs: Map<string, UnitRig>): void {
  if (event.type === "DAMAGE" && "actor_uid" in event && "target_uid" in event) {
    const attacker = rigs.get(event.actor_uid as string);
    const defender = rigs.get(event.target_uid as string);
    if (attacker) playCanonical(attacker, "attack");
    if (defender) {
      playCanonical(defender, "hit");
      defender.flashWhite();
      defender.floatDamageNumber((event.amount as number) ?? 0);
    }
    return;
  }
  if (event.type === "DEATH" && "target_uid" in event) {
    const victim = rigs.get(event.target_uid as string);
    if (victim) {
      playCanonical(victim, "die");
      victim.fade(0.4);
    }
    return;
  }
  if (event.type === "SPECIAL" && "actor_uid" in event) {
    const attacker = rigs.get(event.actor_uid as string);
    if (attacker) {
      playCanonical(attacker, "attack");
      // Flash the attacker so SPECIAL announcements have a visual marker
      // distinct from a basic attack. Follow-up DAMAGE events from the
      // special's effects will flash defenders via the DAMAGE branch.
      attacker.flashWhite();
    }
    return;
  }
  // Other event types: no-op.
}
