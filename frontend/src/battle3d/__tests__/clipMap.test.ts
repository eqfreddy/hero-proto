import { describe, it, expect } from "vitest";
import { resolveClip, ARCHETYPE_CLIP_MAP } from "../clipMap";

describe("resolveClip", () => {
  it("resolves knight Sword_Attack from Quaternius Warrior clipset", () => {
    const available = ["Idle_Weapon", "Sword_Attack", "Sword_Attack2", "RecieveHit", "Death"];
    expect(resolveClip("knight", "idle", available)).toBe("Idle_Weapon");
    expect(resolveClip("knight", "attack", available)).toBe("Sword_Attack");
    expect(resolveClip("knight", "hit", available)).toBe("RecieveHit");
    expect(resolveClip("knight", "die", available)).toBe("Death");
  });

  it("barbarian prefers Sword_Attack2 over Sword_Attack (visual differentiation from knight)", () => {
    const available = ["Idle_Weapon", "Sword_Attack", "Sword_Attack2", "RecieveHit", "Death"];
    expect(resolveClip("barbarian", "attack", available)).toBe("Sword_Attack2");
  });

  it("mage resolves Staff_Attack with Spell fallbacks", () => {
    expect(resolveClip("mage", "attack", ["Idle_Weapon", "Staff_Attack"])).toBe("Staff_Attack");
    expect(resolveClip("mage", "attack", ["Idle", "Spell1"])).toBe("Spell1");
    expect(resolveClip("mage", "attack", ["Idle", "Spell2"])).toBe("Spell2");
  });

  it("rogue resolves Dagger_Attack", () => {
    expect(resolveClip("rogue", "attack", ["Idle", "Dagger_Attack"])).toBe("Dagger_Attack");
    expect(resolveClip("rogue", "idle", ["Attacking_Idle", "Idle"])).toBe("Attacking_Idle");
  });

  it("ranger resolves Bow_Shoot then Bow_Draw", () => {
    expect(resolveClip("ranger", "attack", ["Idle_Weapon", "Bow_Shoot", "Bow_Draw"])).toBe("Bow_Shoot");
    expect(resolveClip("ranger", "attack", ["Idle_Weapon", "Bow_Draw"])).toBe("Bow_Draw");
  });

  it("druid resolves embedded Cleric clips", () => {
    const available = ["Idle", "Idle_Weapon", "Staff_Attack", "Spell1", "Punch", "RecieveHit", "Death"];
    expect(resolveClip("druid", "idle", available)).toBe("Idle_Weapon");
    expect(resolveClip("druid", "attack", available)).toBe("Staff_Attack");
    expect(resolveClip("druid", "hit", available)).toBe("RecieveHit");
    expect(resolveClip("druid", "die", available)).toBe("Death");
  });

  it("monk staged for engineer remap (Attack, Attack2)", () => {
    expect(resolveClip("monk", "attack", ["Idle_Attacking", "Attack", "Attack2"])).toBe("Attack");
  });

  it("returns null when no candidate is available", () => {
    expect(resolveClip("knight", "idle", ["WeirdName"])).toBeNull();
  });

  it("returns null for an unknown archetype", () => {
    expect(resolveClip("does_not_exist", "idle", ["Idle"])).toBeNull();
  });

  it("ARCHETYPE_CLIP_MAP covers all 8 archetypes with all 4 canonical clips", () => {
    const archetypes = ["knight", "barbarian", "mage", "rogue", "rogue_hooded", "ranger", "druid", "monk"];
    const canonicals = ["idle", "attack", "hit", "die"] as const;
    for (const a of archetypes) {
      expect(ARCHETYPE_CLIP_MAP[a]).toBeDefined();
      for (const c of canonicals) {
        expect(ARCHETYPE_CLIP_MAP[a][c]?.length).toBeGreaterThan(0);
      }
    }
  });

  it("does NOT include engineer (remapped to ranger upstream)", () => {
    expect(ARCHETYPE_CLIP_MAP["engineer"]).toBeUndefined();
  });
});
