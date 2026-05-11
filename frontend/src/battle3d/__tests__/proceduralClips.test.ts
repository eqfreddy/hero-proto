import { describe, it, expect } from "vitest";
import * as THREE from "three";
import { buildKaykitMeleeSwing } from "../proceduralClips";

function rigWithBones(names: string[]): THREE.Object3D {
  const root = new THREE.Object3D();
  for (const n of names) {
    const b = new THREE.Bone();
    b.name = n;
    root.add(b);
  }
  return root;
}

describe("buildKaykitMeleeSwing", () => {
  it("returns a clip named MeleeSwing with 0.4s duration when all 3 right-arm bones exist", () => {
    const root = rigWithBones(["UpperArm_R", "Forearm_R", "Hand_R"]);
    const clip = buildKaykitMeleeSwing(root);
    expect(clip).not.toBeNull();
    expect(clip!.name).toBe("MeleeSwing");
    expect(clip!.duration).toBeCloseTo(0.4, 5);
    expect(clip!.tracks).toHaveLength(3);
  });

  it("matches case-insensitive variants and alternate words", () => {
    const root = rigWithBones(["upper_arm_r", "lowerarm_R", "RightHand"]);
    const clip = buildKaykitMeleeSwing(root);
    expect(clip).not.toBeNull();
    expect(clip!.tracks).toHaveLength(3);
  });

  it("returns null when the forearm bone is missing", () => {
    const root = rigWithBones(["UpperArm_R", "Hand_R"]);
    expect(buildKaykitMeleeSwing(root)).toBeNull();
  });

  it("returns null when the scene has no bones", () => {
    expect(buildKaykitMeleeSwing(new THREE.Object3D())).toBeNull();
  });

  it("track names target each matched bone's actual name with .quaternion suffix", () => {
    const root = rigWithBones(["UpperArm_R", "Forearm_R", "Hand_R"]);
    const clip = buildKaykitMeleeSwing(root)!;
    const names = clip.tracks.map((t) => t.name).sort();
    expect(names).toEqual(
      ["Forearm_R.quaternion", "Hand_R.quaternion", "UpperArm_R.quaternion"].sort(),
    );
  });

  it("first and last keyframes are identical (returns to rest)", () => {
    const root = rigWithBones(["UpperArm_R", "Forearm_R", "Hand_R"]);
    const clip = buildKaykitMeleeSwing(root)!;
    for (const t of clip.tracks) {
      const stride = t.values.length / t.times.length; // 4 components for quaternion
      const first = Array.from(t.values.slice(0, stride));
      const last = Array.from(t.values.slice(t.values.length - stride));
      for (let i = 0; i < stride; i++) {
        expect(first[i]).toBeCloseTo(last[i], 6);
      }
    }
  });
});
