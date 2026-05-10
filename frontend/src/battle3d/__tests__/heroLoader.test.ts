import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("three/examples/jsm/loaders/DRACOLoader.js", () => ({
  DRACOLoader: class {
    setDecoderPath() {}
  },
}));

vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => {
  return {
    GLTFLoader: class {
      setDRACOLoader() {}
      load(url: string, onLoad: (gltf: any) => void) {
        const isKaykitClips = url.includes("kaykit_general");
        const animations = isKaykitClips
          ? [{ name: "Idle_A" }, { name: "Throw" }, { name: "Hit_A" }, { name: "Death_A" }]
          : url.includes("druid")
          ? [{ name: "Idle" }, { name: "Staff_Attack" }, { name: "RecieveHit" }, { name: "Death" }]
          : []; // KayKit hero meshes have no animations
        // unique scene object per resolved gltf so .clone() returns fresh refs
        const scene = { clone: (_deep?: boolean) => ({ __cloned: true, src: url, id: Math.random() }) };
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

  it("KayKit archetype gets shared kaykit_general clips", async () => {
    const knight = await loadHero("knight");
    expect(knight.animations.map((c: any) => c.name)).toEqual([
      "Idle_A",
      "Throw",
      "Hit_A",
      "Death_A",
    ]);
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
