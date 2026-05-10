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

export async function loadDiorama(theme: string): Promise<DioramaAssets> {
  let p = dioramaCache.get(theme);
  if (!p) {
    p = loadGLTF(`${DIORAMA_BASE}/${theme}.glb`);
    dioramaCache.set(theme, p);
  }
  const gltf = await p;
  const scene = (gltf.scene as unknown as { clone: (deep?: boolean) => THREE.Group }).clone(true);
  return { scene, theme };
}

export function _resetDioramaCache(): void {
  dioramaCache.clear();
}
