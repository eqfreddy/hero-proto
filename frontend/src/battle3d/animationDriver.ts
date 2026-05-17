import { resolveClip, type CanonicalClip } from "./clipMap";

export interface UnitRig {
  uid: string;
  archetype: string;
  availableClips: string[];
  play: (clipName: string) => void;
  flashWhite: () => void;
  floatDamageNumber: (amount: number, opts?: { crit?: boolean; kind?: 'damage' | 'heal' | 'defend' }) => void;
  floatQuip?: (line: string) => void;
  fade: (opacity: number) => void;
}

export type CombatEvent =
  | { type: "DAMAGE"; actor_uid?: string; source?: string; target_uid?: string; target?: string; amount: number; crit?: boolean }
  | { type: "HEAL"; target_uid?: string; target?: string; amount: number }
  | { type: "DEFEND"; unit: string }
  | { type: "DEATH"; target_uid?: string; unit?: string }
  | { type: "SPECIAL"; actor_uid?: string; unit?: string }
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
  if (event.type === "DAMAGE") {
    const aUid = (event.actor_uid ?? event.source) as string | undefined;
    const tUid = (event.target_uid ?? event.target) as string | undefined;
    const attacker = aUid ? rigs.get(aUid) : undefined;
    const defender = tUid ? rigs.get(tUid) : undefined;
    if (attacker) playCanonical(attacker, "attack");
    if (defender) {
      playCanonical(defender, "hit");
      defender.flashWhite();
      defender.floatDamageNumber((event.amount as number) ?? 0, { crit: !!event.crit });
    }
    return;
  }
  if (event.type === "HEAL") {
    const tUid = (event.target_uid ?? event.target) as string | undefined;
    const tgt = tUid ? rigs.get(tUid) : undefined;
    if (tgt) tgt.floatDamageNumber(event.amount as number ?? 0, { kind: 'heal' });
    return;
  }
  if (event.type === "DEFEND") {
    const tgt = rigs.get(event.unit as string);
    if (tgt) tgt.floatDamageNumber(0, { kind: 'defend' });
    return;
  }
  if (event.type === "QUIP") {
    const uid = (event.unit ?? event.actor_uid) as string | undefined;
    const tgt = uid ? rigs.get(uid) : undefined;
    if (tgt) tgt.floatQuip?.((event.line as string) ?? "");
    return;
  }
  if (event.type === "DEATH") {
    const uid = (event.target_uid ?? event.unit) as string | undefined;
    const victim = uid ? rigs.get(uid) : undefined;
    if (victim) {
      playCanonical(victim, "die");
      victim.fade(0.4);
    }
    return;
  }
  if (event.type === "SPECIAL") {
    const uid = (event.actor_uid ?? event.unit) as string | undefined;
    const attacker = uid ? rigs.get(uid) : undefined;
    if (attacker) {
      playCanonical(attacker, "attack");
      attacker.flashWhite();
    }
    return;
  }
  // Other event types: no-op.
}
