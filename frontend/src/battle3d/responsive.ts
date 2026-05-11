// Viewport-responsive camera framing for the 3D battle scene.
//
// The baseline scene is tuned for a 16:9 viewport at ~1280px wide.
// Bigger viewports pull the camera further back (so the formation
// takes a consistent share of the frame instead of feeling huge on
// a 27" display). Narrower / portrait viewports pull in so the
// hero formation stays readable on phones.

import * as THREE from "three";

export interface ResponsiveFrame {
  cameraPosition: THREE.Vector3;
  cameraLookAt: THREE.Vector3;
}

const BASE_WIDTH = 1280;
const BASE_ASPECT = 16 / 9;

// Anchor positions at baseline viewport.
const BASE_CAM = { x: 0, y: 5, z: 10 };
const BASE_LOOKAT = { x: 0, y: 3, z: 0 };

export function computeResponsiveFrame(
  viewportWidth: number,
  viewportHeight: number,
): ResponsiveFrame {
  const w = Math.max(320, viewportWidth);
  const h = Math.max(240, viewportHeight);
  const aspect = w / h;

  // Square root softens the width factor so the scene doesn't blow
  // out at very large viewports; clamp so a single resize step
  // never feels chaotic.
  const widthFactor = Math.sqrt(Math.max(0.35, Math.min(3, w / BASE_WIDTH)));

  // Inverse-aspect correction: ultra-wide screens (aspect > 16/9)
  // already show more horizontally at a given camera distance, so
  // pull the camera in slightly. Portrait viewports (aspect < 1)
  // need it further out.
  const aspectFactor = Math.pow(BASE_ASPECT / aspect, 0.3);

  const factor = Math.max(0.7, Math.min(1.8, widthFactor * aspectFactor));

  return {
    cameraPosition: new THREE.Vector3(
      BASE_CAM.x,
      BASE_CAM.y * factor,
      BASE_CAM.z * factor,
    ),
    cameraLookAt: new THREE.Vector3(
      BASE_LOOKAT.x,
      BASE_LOOKAT.y * Math.sqrt(factor),
      BASE_LOOKAT.z,
    ),
  };
}
