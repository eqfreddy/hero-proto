import { describe, it, expect } from "vitest";
import { resolveClip, ARCHETYPE_CLIP_MAP } from "../clipMap";

describe("resolveClip", () => {
  it("returns the first matching candidate for a KayKit archetype + canonical name", () => {
    const available = ["Idle_A", "Idle_B", "Throw", "Hit_A", "Hit_B", "Death_A", "Death_B"];
    expect(resolveClip("knight", "idle", available)).toBe("Idle_A");
    expect(resolveClip("knight", "attack", available)).toBe("Throw");
    expect(resolveClip("knight", "hit", available)).toBe("Hit_A");
    expect(resolveClip("knight", "die", available)).toBe("Death_A");
  });

  it("returns Idle_B when Idle_A is unavailable (KayKit fallback)", () => {
    expect(resolveClip("knight", "idle", ["Idle_B"])).toBe("Idle_B");
  });

  it("resolves druid clips (embedded, distinct candidate set)", () => {
    const available = ["Idle", "Idle_Weapon", "Staff_Attack", "Spell1", "Punch", "RecieveHit", "Death"];
    expect(resolveClip("druid", "idle", available)).toBe("Idle");
    expect(resolveClip("druid", "attack", available)).toBe("Staff_Attack");
    expect(resolveClip("druid", "hit", available)).toBe("RecieveHit");
    expect(resolveClip("druid", "die", available)).toBe("Death");
  });

  it("returns null when no candidate is available", () => {
    expect(resolveClip("knight", "idle", ["WeirdName"])).toBeNull();
  });

  it("returns null for an unknown archetype", () => {
    expect(resolveClip("does_not_exist", "idle", ["Idle_A"])).toBeNull();
  });

  it("ARCHETYPE_CLIP_MAP covers all 7 archetypes with all 4 canonical clips", () => {
    const archetypes = ["knight", "barbarian", "mage", "rogue", "rogue_hooded", "ranger", "druid"];
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

  it("all 6 KayKit archetypes share the same candidate sets (shared rig)", () => {
    const kaykit = ["knight", "barbarian", "mage", "rogue", "rogue_hooded", "ranger"];
    const ref = ARCHETYPE_CLIP_MAP["knight"];
    for (const a of kaykit) {
      expect(ARCHETYPE_CLIP_MAP[a]).toEqual(ref);
    }
  });
});
