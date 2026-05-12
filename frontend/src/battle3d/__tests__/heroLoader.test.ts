import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("three/examples/jsm/loaders/DRACOLoader.js", () => ({
  DRACOLoader: class {
    setDecoderPath() {}
  },
}));

vi.mock("three/examples/jsm/utils/SkeletonUtils.js", () => ({
  // Mirror real SkeletonUtils.clone signature; returns a fresh object each call.
  clone: (root: any) => ({ __cloned: true, src: root?.src, id: Math.random() }),
}));

vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => {
  return {
    GLTFLoader: class {
      setDRACOLoader() {}
      load(url: string, onLoad: (gltf: any) => void) {
        // Every archetype's .glb ships its own embedded clips (Quaternius pack).
        const animations = url.includes("druid")
          ? [{ name: "Idle" }, { name: "Staff_Attack" }, { name: "RecieveHit" }, { name: "Death" }]
          : url.includes("knight") || url.includes("barbarian")
          ? [{ name: "Idle_Weapon" }, { name: "Sword_Attack" }, { name: "RecieveHit" }, { name: "Death" }]
          : url.includes("mage")
          ? [{ name: "Idle_Weapon" }, { name: "Staff_Attack" }, { name: "RecieveHit" }, { name: "Death" }]
          : url.includes("rogue")
          ? [{ name: "Attacking_Idle" }, { name: "Dagger_Attack" }, { name: "RecieveHit" }, { name: "Death" }]
          : url.includes("ranger")
          ? [{ name: "Idle_Weapon" }, { name: "Bow_Shoot" }, { name: "RecieveHit" }, { name: "Death" }]
          : [];
        const scene = { src: url };
        setTimeout(() => onLoad({ scene, animations }), 0);
      }
    },
  };
});

import { loadHero, _resetHeroCache } from "../heroLoader";

describe("loadHero", () => {
  beforeEach(() => _resetHeroCache());

  it("caches per-archetype GLTF (second call uses same loaded gltf)", async () => {
    const a = await loadHero("knight");
    const b = await loadHero("knight");
    expect(a.archetype).toBe("knight");
    expect(b.archetype).toBe("knight");
  });

  it("knight ships embedded Sword_Attack clip (no shared kaykit_general)", async () => {
    const knight = await loadHero("knight");
    expect(knight.animations.map((c: any) => c.name)).toEqual([
      "Idle_Weapon",
      "Sword_Attack",
      "RecieveHit",
      "Death",
    ]);
  });

  it("mage ships embedded Staff_Attack", async () => {
    const mage = await loadHero("mage");
    expect(mage.animations.map((c: any) => c.name)).toContain("Staff_Attack");
  });

  it("rogue ships embedded Dagger_Attack", async () => {
    const rogue = await loadHero("rogue");
    expect(rogue.animations.map((c: any) => c.name)).toContain("Dagger_Attack");
  });

  it("ranger ships embedded Bow_Shoot", async () => {
    const ranger = await loadHero("ranger");
    expect(ranger.animations.map((c: any) => c.name)).toContain("Bow_Shoot");
  });

  it("druid uses its own embedded clips", async () => {
    const druid = await loadHero("druid");
    expect(druid.animations.map((c: any) => c.name)).toEqual([
      "Idle",
      "Staff_Attack",
      "RecieveHit",
      "Death",
    ]);
  });

  it("scene is cloned per call (different references)", async () => {
    const a = await loadHero("knight");
    const b = await loadHero("knight");
    expect(a.scene).not.toBe(b.scene);
  });
});
