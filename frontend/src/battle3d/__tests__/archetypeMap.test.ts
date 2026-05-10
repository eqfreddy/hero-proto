import { describe, it, expect } from "vitest";
import { TEMPLATE_TO_3D_ARCHETYPE, DEFAULT_3D_ARCHETYPE } from "../archetypeMap";
import { ARCHETYPE_CLIP_MAP } from "../clipMap";

describe("archetypeMap", () => {
  it("DEFAULT_3D_ARCHETYPE has clip-map coverage", () => {
    expect(ARCHETYPE_CLIP_MAP[DEFAULT_3D_ARCHETYPE]).toBeDefined();
  });

  it("every mapped archetype has clip-map coverage", () => {
    for (const archetype of Object.values(TEMPLATE_TO_3D_ARCHETYPE)) {
      expect(ARCHETYPE_CLIP_MAP[archetype]).toBeDefined();
    }
  });

  it("only the 7 supported archetypes appear as values (no engineer)", () => {
    const archetypes = ["knight", "barbarian", "mage", "rogue", "rogue_hooded", "ranger", "druid"];
    const used = new Set(Object.values(TEMPLATE_TO_3D_ARCHETYPE));
    for (const a of used) {
      expect(archetypes).toContain(a);
    }
    expect(used.has("engineer")).toBe(false);
  });

  it("at least 10 templates are mapped", () => {
    expect(Object.keys(TEMPLATE_TO_3D_ARCHETYPE).length).toBeGreaterThanOrEqual(10);
  });

  it("no orphan archetypes in clipMap (every clipMap key is reachable from a template or is the default)", () => {
    const reachable = new Set([
      ...Object.values(TEMPLATE_TO_3D_ARCHETYPE),
      DEFAULT_3D_ARCHETYPE,
    ]);
    for (const key of Object.keys(ARCHETYPE_CLIP_MAP)) {
      expect(reachable.has(key)).toBe(true);
    }
  });
});
