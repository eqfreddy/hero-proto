import * as THREE from "three";

// Slots spread along X (horizontal across the screen) with slight Z
// stagger so the team forms a diagonal line rather than stacking
// behind the camera's projection axis.
export const SLOT_POSITIONS_TEAM_A: [number, number, number][] = [
  [-1.4, 0,  0.6],   // front-most (closest to camera)
  [-2.4, 0,  0.0],   // mid
  [-3.4, 0, -0.6],   // back-most
];

export const SLOT_POSITIONS_TEAM_B: [number, number, number][] = SLOT_POSITIONS_TEAM_A.map(
  ([x, y, z]) => [-x, y, z],
);

export const CAMERA_POSITION = new THREE.Vector3(0, 4, 9);
export const CAMERA_LOOKAT   = new THREE.Vector3(0, 1, 0);

export const AMBIENT_INTENSITY     = 0.6;
export const DIRECTIONAL_INTENSITY = 0.8;
export const DIRECTIONAL_POSITION  = new THREE.Vector3(-3, 5, 3);

export const PERF_TARGET_FPS = 30;
export const PERF_TTI_MS_SLOW_3G = 3000;
