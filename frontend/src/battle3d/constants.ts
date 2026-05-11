import * as THREE from "three";

// Slots arranged in a battle line — same z, spread along x with
// enough gap (~2u) that ~1.5u-wide hero models do not visually
// overlap from the camera's POV.
export const SLOT_POSITIONS_TEAM_A: [number, number, number][] = [
  [-1.8, 0, 0],   // front-most (toward center, closest to enemy)
  [-3.8, 0, 0],   // mid
  [-5.8, 0, 0],   // back-most (farthest from center)
];

export const SLOT_POSITIONS_TEAM_B: [number, number, number][] = SLOT_POSITIONS_TEAM_A.map(
  ([x, y, z]) => [-x, y, z],
);

// Camera pulled back + raised so a 6-unit battle line (~14u wide)
// fits in frame with the diorama backdrop visible behind.
export const CAMERA_POSITION = new THREE.Vector3(0, 5, 13);
export const CAMERA_LOOKAT   = new THREE.Vector3(0, 1, 0);

export const AMBIENT_INTENSITY     = 0.6;
export const DIRECTIONAL_INTENSITY = 0.8;
export const DIRECTIONAL_POSITION  = new THREE.Vector3(-3, 5, 3);

export const PERF_TARGET_FPS = 30;
export const PERF_TTI_MS_SLOW_3G = 3000;
