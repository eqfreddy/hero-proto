import * as THREE from "three";

/**
 * Procedural animation clips for the Battle 3D viewer.
 *
 * Used to synthesize attack/idle/etc. clips when the source rig ships none.
 * Currently used for KayKit melee swing (kaykit_general.glb has no melee
 * clip — see docs/superpowers/notes/2026-05-10-battle-3d-clip-names.md).
 *
 * Built per-scene because AnimationClip tracks reference bones by name and
 * skeleton naming can differ between archetypes. Falls back to null if bone
 * discovery fails so the caller can resolve to a different clip.
 */

type ArmSlot = "upper" | "fore" | "hand";

const FOREARM_KW = /fore.?arm|lower.?arm|elbow/i;
const HAND_KW = /hand|wrist|fist/i;
const ARM_KW = /arm/i;

function isRightSide(name: string): boolean {
  // Suffix forms: `_R`, `.R`, `R` at end; prefix form: `Right...`.
  return /(_r$|\.r$|right)/i.test(name);
}

function classifyBone(name: string): ArmSlot | null {
  if (!isRightSide(name)) return null;
  if (HAND_KW.test(name)) return "hand";
  if (FOREARM_KW.test(name)) return "fore";
  if (ARM_KW.test(name)) return "upper";
  return null;
}

function findArmBones(root: THREE.Object3D): Record<ArmSlot, THREE.Object3D | null> {
  const result: Record<ArmSlot, THREE.Object3D | null> = {
    upper: null,
    fore: null,
    hand: null,
  };
  // Defensive: callers may pass non-Object3D inputs in tests / edge cases.
  if (typeof (root as { traverse?: unknown }).traverse !== "function") return result;
  root.traverse((node) => {
    if (!node.name) return;
    const slot = classifyBone(node.name);
    if (slot && !result[slot]) result[slot] = node;
  });
  return result;
}

function eulerToQuat(xDeg: number, yDeg: number, zDeg: number): [number, number, number, number] {
  const e = new THREE.Euler(
    THREE.MathUtils.degToRad(xDeg),
    THREE.MathUtils.degToRad(yDeg),
    THREE.MathUtils.degToRad(zDeg),
    "XYZ",
  );
  const q = new THREE.Quaternion().setFromEuler(e);
  return [q.x, q.y, q.z, q.w];
}

function quatTrack(
  boneName: string,
  poses: Array<[number, number, number]>,
): THREE.QuaternionKeyframeTrack {
  const times = [0.0, 0.12, 0.30, 0.40];
  const values: number[] = [];
  for (const [x, y, z] of poses) {
    const q = eulerToQuat(x, y, z);
    values.push(...q);
  }
  return new THREE.QuaternionKeyframeTrack(`${boneName}.quaternion`, times, values);
}

/**
 * Build a 400ms diagonal right-arm swing clip from the given rig root.
 *
 * Returns null if any of the three right-arm bones (upperarm/forearm/hand)
 * cannot be located by name pattern. Callers should fall back to a different
 * attack clip on null.
 */
export function buildKaykitMeleeSwing(root: THREE.Object3D): THREE.AnimationClip | null {
  const { upper, fore, hand } = findArmBones(root);
  if (!upper || !fore || !hand) return null;

  // Euler deltas at [rest, wind-up, swing apex, rest]
  // Wind-up: arm pulls back + up. Swing: arm comes down-forward across the body.
  const upperPoses: Array<[number, number, number]> = [
    [0, 0, 0],
    [-25, 15, 0],
    [55, -10, 0],
    [0, 0, 0],
  ];
  const forePoses: Array<[number, number, number]> = [
    [0, 0, 0],
    [30, 0, 0],
    [-15, 0, 0],
    [0, 0, 0],
  ];
  const handPoses: Array<[number, number, number]> = [
    [0, 0, 0],
    [0, 0, 10],
    [0, 0, -20],
    [0, 0, 0],
  ];

  const tracks = [
    quatTrack(upper.name, upperPoses),
    quatTrack(fore.name, forePoses),
    quatTrack(hand.name, handPoses),
  ];

  return new THREE.AnimationClip("MeleeSwing", 0.4, tracks);
}
