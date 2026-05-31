import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("three/examples/jsm/loaders/DRACOLoader.js", () => ({
  DRACOLoader: class {
    setDecoderPath() {}
  },
}));

// The mock scene must be a real THREE.Object3D: loadDiorama clones it and then
// runs Box3.setFromObject + scale/position auto-fit on the clone, which call
// Object3D methods (updateWorldMatrix, etc.). A plain object can't satisfy that.
// Async factory + dynamic import avoids the vi.mock hoisting trap.
vi.mock("three/examples/jsm/loaders/GLTFLoader.js", async () => {
  const THREE = await import("three");
  return {
    GLTFLoader: class {
      setDRACOLoader() {}
      load(_url: string, onLoad: (gltf: any) => void) {
        const scene = new THREE.Group();
        // A child mesh gives the bounding box real, non-degenerate extents.
        scene.add(new THREE.Mesh(new THREE.BoxGeometry(2, 2, 2)));
        // loadDiorama calls scene.clone(true); THREE's real clone returns a
        // fresh Object3D each call, so cached-then-cloned scenes differ.
        setTimeout(() => onLoad({ scene, animations: [] }), 0);
      }
    },
  };
});

import {
  themeForStage,
  loadDiorama,
  DEFAULT_THEME,
  STAGE_3D_THEME,
  _resetDioramaCache,
} from "../dioramaLoader";

describe("themeForStage", () => {
  it("returns DEFAULT_THEME for unknown stage", () => {
    expect(themeForStage("not_a_real_stage")).toBe(DEFAULT_THEME);
  });

  it("returns DEFAULT_THEME for null/undefined", () => {
    expect(themeForStage(null)).toBe(DEFAULT_THEME);
    expect(themeForStage(undefined)).toBe(DEFAULT_THEME);
  });

  it("returns DEFAULT_THEME for empty string", () => {
    expect(themeForStage("")).toBe(DEFAULT_THEME);
  });

  it("returns mapped theme for known stage", () => {
    expect(themeForStage("tutorial_first_ticket")).toBe("server-closet");
    expect(themeForStage("ceos_one_on_one")).toBe("exec-floor");
    expect(themeForStage("quarterly_audit")).toBe("cubicle-farm");
    expect(themeForStage("resistance_aftermath")).toBe("break-room");
    expect(themeForStage("the_singularity")).toBe("data-center");
  });

  it("only emits one of the 5 v1.1 themes", () => {
    const allowed = new Set([
      "server-closet",
      "data-center",
      "cubicle-farm",
      "exec-floor",
      "break-room",
    ]);
    for (const theme of Object.values(STAGE_3D_THEME)) {
      expect(allowed.has(theme)).toBe(true);
    }
    expect(allowed.has(DEFAULT_THEME)).toBe(true);
  });
});

describe("loadDiorama", () => {
  beforeEach(() => _resetDioramaCache());

  it("caches per theme (different scenes per call due to clone)", async () => {
    const a = await loadDiorama("server-closet");
    const b = await loadDiorama("server-closet");
    expect(a.theme).toBe("server-closet");
    expect(b.theme).toBe("server-closet");
    expect(a.scene).not.toBe(b.scene);
  });
});
