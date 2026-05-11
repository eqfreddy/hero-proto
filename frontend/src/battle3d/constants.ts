import * as THREE from "three";

// Diagonal wedge formation: slot 0 is the forward-most (closest to
// the enemy line, smallest |x|), slot 2 is the back-most. z range is
// kept above -2 / below 0 so the front-most card isn't clipped by the
// HUD strip at the bottom of the screen. Mirrored for team B.
export const SLOT_POSITIONS_TEAM_A: [number, number, number][] = [
  [-1.6, 0,  0.0],   // front
  [-2.7, 0, -0.9],   // mid
  [-3.8, 0, -1.8],   // back
];

export const SLOT_POSITIONS_TEAM_B: [number, number, number][] = SLOT_POSITIONS_TEAM_A.map(
  ([x, y, z]) => [-x, y, z],
);

// Camera pulled back ~60% from (0,3.5,9) so heroes don't dominate
// the frame, and the lookAt raised from y=1 to y=3 so the characters
// fall toward the bottom third of the screen (showing more diorama
// above them).
export const CAMERA_POSITION = new THREE.Vector3(0, 5.5, 14);
export const CAMERA_LOOKAT   = new THREE.Vector3(0, 3, 0);

export const AMBIENT_INTENSITY     = 0.6;
export const DIRECTIONAL_INTENSITY = 0.8;
export const DIRECTIONAL_POSITION  = new THREE.Vector3(-3, 5, 3);

export const PERF_TARGET_FPS = 30;
export const PERF_TTI_MS_SLOW_3G = 3000;
