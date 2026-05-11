import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

const DIORAMA_BASE = `${import.meta.env.BASE_URL}battle-3d/props`;

export const DEFAULT_THEME = "server-closet";

// V1.1 ships 5 themes. Every seeded stage gets an explicit theme assigned
// by flavor; anything not listed (future stages) falls through to
// DEFAULT_THEME ("server-closet").
export const STAGE_3D_THEME: Record<string, string> = {
  // server-closet — sci-fi technical, racks, IT crisis
  tutorial_first_ticket: "server-closet",
  onboarding_day: "server-closet",
  first_outage: "server-closet",
  legacy_server_room: "server-closet",
  tape_room_breach: "server-closet",
  pager_storm: "server-closet",
  prod_is_down: "server-closet",
  resistance_server_room: "server-closet",

  // cubicle-farm — open office beige existential vibe
  quarterly_audit: "cubicle-farm",
  the_unauthorized_tool: "cubicle-farm",
  migration_weekend: "cubicle-farm",

  // exec-floor — sleek dark gold, boardrooms + power moves
  ceos_one_on_one: "exec-floor",
  reorg_announcement: "exec-floor",
  hostile_acquisition: "exec-floor",
  boardroom_coup: "exec-floor",
  the_all_hands: "exec-floor",
  resistance_boardroom: "exec-floor",
  resistance_coup: "exec-floor",
  corpgreed_first_move: "exec-floor",
  corpgreed_boardroom: "exec-floor",

  // break-room — bright pastel casual
  resistance_aftermath: "break-room",
  corpgreed_saas: "break-room",

  // data-center — industrial scale, late-game dramatic
  the_singularity: "data-center",
  resistance_breach: "data-center",
  corpgreed_acquisition: "data-center",
  corpgreed_apotheosis: "data-center",
};

export interface DioramaAssets {
  scene: THREE.Group; // CLONED — caller owns it
  theme: string;
}

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath("https://www.gstatic.com/draco/v1/decoders/");
const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(dracoLoader);

const dioramaCache = new Map<string, Promise<GLTF>>();

function loadGLTF(url: string): Promise<GLTF> {
  return new Promise((resolve, reject) => {
    gltfLoader.load(url, resolve, undefined, reject);
  });
}

export function themeForStage(stageCode: string | null | undefined): string {
  if (!stageCode) return DEFAULT_THEME;
  return STAGE_3D_THEME[stageCode] ?? DEFAULT_THEME;
}

// Target footprint the diorama should fill, in world units. The hero
// formation spans ~9u along x and ~3u along z, so we scale the diorama
// so its on-floor footprint is at least this wide — guarantees the
// backdrop fills the frame at the v1 camera (0,5,13).
// Sized to overflow the camera frustum at (0,5,10) lookAt (0,3,0) so
// the backdrop fully fills the visible frame. The renderer also sets
// scene.background to a dark fallback color for any remaining gap.
const TARGET_DIORAMA_WIDTH = 30;   // x
const TARGET_DIORAMA_DEPTH = 22;   // z

export async function loadDiorama(theme: string): Promise<DioramaAssets> {
  let p = dioramaCache.get(theme);
  if (!p) {
    p = loadGLTF(`${DIORAMA_BASE}/${theme}.glb`);
    dioramaCache.set(theme, p);
  }
  const gltf = await p;
  const scene = (gltf.scene as unknown as { clone: (deep?: boolean) => THREE.Group }).clone(true);

  // Auto-fit: measure bounding box, scale uniformly so x-width and
  // z-depth both meet the target (pick the larger required scale so
  // we never end up smaller than the target on either axis), then
  // center horizontally and drop the floor onto y=0 so heroes stand on it.
  const box = new THREE.Box3().setFromObject(scene);
  const size = new THREE.Vector3();
  box.getSize(size);
  const sx = size.x > 0 ? TARGET_DIORAMA_WIDTH / size.x : 1;
  const sz = size.z > 0 ? TARGET_DIORAMA_DEPTH / size.z : 1;
  const s = Math.max(sx, sz);
  scene.scale.setScalar(s);

  // Re-measure after scale, then center.
  box.setFromObject(scene);
  const center = new THREE.Vector3();
  box.getCenter(center);
  scene.position.x -= center.x;
  scene.position.z -= center.z;
  scene.position.y -= box.min.y; // floor at y=0

  // Push the whole backdrop deeper along -z so its front wall sits
  // BEHIND the hero formation (which lives at z = 0 .. -1.8) instead
  // of in front of it. Without this offset the diorama's front face
  // was clipping into the heroes — only the units fully on the back
  // side of the wall were rendering.
  scene.position.z -= 9;

  return { scene, theme };
}

export function _resetDioramaCache(): void {
  dioramaCache.clear();
}
