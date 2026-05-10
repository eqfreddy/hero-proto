import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

const DIORAMA_BASE = "/battle-3d/props";

export const DEFAULT_THEME = "server-closet";

// V1 ships 2 themes only — fan all stages onto these.
// Anything not listed → DEFAULT_THEME ("server-closet").
// Mid/late-game and corporate-themed stages map to "data-center"; the rest
// (early levels, server rooms, helpdesk-flavored fights) fall through to
// "server-closet" by default.
export const STAGE_3D_THEME: Record<string, string> = {
  // Early/tutorial — server-closet feel
  tutorial_first_ticket: "server-closet",
  onboarding_day: "server-closet",
  first_outage: "server-closet",
  legacy_server_room: "server-closet",
  tape_room_breach: "server-closet",

  // Corporate / late-game — data-center feel
  ceos_one_on_one: "data-center",
  reorg_announcement: "data-center",
  hostile_acquisition: "data-center",
  boardroom_coup: "data-center",
  the_all_hands: "data-center",
  corpgreed_boardroom: "data-center",
  corpgreed_acquisition: "data-center",
  corpgreed_apotheosis: "data-center",
  the_singularity: "data-center",
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
