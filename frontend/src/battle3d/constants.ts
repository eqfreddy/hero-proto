import * as THREE from "three";

// Diagonal wedge formation: slot 0 is the forward-most (closest to
// the enemy line), slot 2 is the back-most. Each step back also steps
// further out on x so the wedge spreads visually. Mirrored for team B.
export const SLOT_POSITIONS_TEAM_A: [number, number, number][] = [
  [-1.6, 0,  1.2],   // front
  [-3.0, 0,  0.0],   // mid
  [-4.4, 0, -1.2],   // back
];

export const SLOT_POSITIONS_TEAM_B: [number, number, number][] = SLOT_POSITIONS_TEAM_A.map(
  ([x, y, z]) => [-x, y, z],
);

export const CAMERA_POSITION = new THREE.Vector3(0, 5, 13);
export const CAMERA_LOOKAT   = new THREE.Vector3(0, 1, 0);

export const AMBIENT_INTENSITY     = 0.6;
export const DIRECTIONAL_INTENSITY = 0.8;
export const DIRECTIONAL_POSITION  = new THREE.Vector3(-3, 5, 3);

export const PERF_TARGET_FPS = 30;
export const PERF_TTI_MS_SLOW_3G = 3000;
