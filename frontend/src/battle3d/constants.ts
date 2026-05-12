import * as THREE from "three";

// Diagonal wedge formation: slot 0 is the forward-most (closest to
// the enemy line, smallest |x|), slot 2 is the back-most. z range is
// kept above -2 / below 0 so the front-most card isn't clipped by the
// HUD strip at the bottom of the screen. Mirrored for team B.
export const SLOT_POSITIONS_TEAM_A: [number, number, number][] = [
  [-1.6, 0,  0.0],   // front
  [-3.7, 0, -1.8],   // mid
  [-5.8, 0, -3.6],   // back
];

export const SLOT_POSITIONS_TEAM_B: [number, number, number][] = SLOT_POSITIONS_TEAM_A.map(
  ([x, y, z]) => [-x, y, z],
);

// Camera pulled back further (was 0,5,10) so the wider Quaternius rigs
// don't dominate the frame; lookAt y=3 keeps characters in the bottom
// third with more diorama above them.
export const CAMERA_POSITION = new THREE.Vector3(0, 6, 14);
export const CAMERA_LOOKAT   = new THREE.Vector3(0, 3, 0);

// Zoom range — wheel listener moves the camera along the lookAt→camera
// vector and clamps the resulting distance into this interval.
export const ZOOM_MIN_DIST = 7;
export const ZOOM_MAX_DIST = 24;
export const ZOOM_WHEEL_STEP = 0.001; // distance delta per wheel pixel

export const AMBIENT_INTENSITY     = 0.6;
export const DIRECTIONAL_INTENSITY = 0.8;
export const DIRECTIONAL_POSITION  = new THREE.Vector3(-3, 5, 3);

export const PERF_TARGET_FPS = 30;
export const PERF_TTI_MS_SLOW_3G = 3000;
