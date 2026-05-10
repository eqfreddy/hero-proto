import * as THREE from "three";

export const SLOT_POSITIONS_TEAM_A: [number, number, number][] = [
  [-2, 0,  0.0],
  [-2, 0, -1.5],
  [-2, 0,  1.5],
];

export const SLOT_POSITIONS_TEAM_B: [number, number, number][] = SLOT_POSITIONS_TEAM_A.map(
  ([x, y, z]) => [-x, y, z],
);

export const CAMERA_POSITION = new THREE.Vector3(0, 3, 6);
export const CAMERA_LOOKAT   = new THREE.Vector3(0, 1, 0);

export const AMBIENT_INTENSITY     = 0.6;
export const DIRECTIONAL_INTENSITY = 0.8;
export const DIRECTIONAL_POSITION  = new THREE.Vector3(-3, 5, 3);

export const PERF_TARGET_FPS = 30;
export const PERF_TTI_MS_SLOW_3G = 3000;
