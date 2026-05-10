import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";

const HERO_BASE = `${import.meta.env.BASE_URL}battle-3d/heroes`;
const ANIM_BASE = `${import.meta.env.BASE_URL}battle-3d/animations`;

const KAYKIT_ARCHETYPES = new Set([
  "knight",
  "barbarian",
  "mage",
  "ranger",
  "rogue",
  "rogue_hooded",
]);

export interface HeroAssets {
  scene: THREE.Group;            // CLONED — caller owns it
  animations: THREE.AnimationClip[]; // shared array reference (caller does not mutate)
  archetype: string;
}

const dracoLoader = new DRACOLoader();
dracoLoader.setDecoderPath("https://www.gstatic.com/draco/v1/decoders/");
const gltfLoader = new GLTFLoader();
gltfLoader.setDRACOLoader(dracoLoader);

const heroCache = new Map<string, Promise<GLTF>>();
let kaykitClipsCache: Promise<THREE.AnimationClip[]> | null = null;

function loadGLTF(url: string): Promise<GLTF> {
  return new Promise((resolve, reject) => {
    gltfLoader.load(url, resolve, undefined, reject);
  });
}

function loadKaykitClips(): Promise<THREE.AnimationClip[]> {
  if (kaykitClipsCache) return kaykitClipsCache;
  kaykitClipsCache = loadGLTF(`${ANIM_BASE}/kaykit_general.glb`).then(
    (g) => g.animations,
  );
  return kaykitClipsCache;
}

export async function loadHero(archetype: string): Promise<HeroAssets> {
  let p = heroCache.get(archetype);
  if (!p) {
    p = loadGLTF(`${HERO_BASE}/${archetype}.glb`);
    heroCache.set(archetype, p);
  }
  const gltf = await p;
  const scene = (gltf.scene as unknown as { clone: (deep?: boolean) => THREE.Group }).clone(true);
  let animations = gltf.animations;
  if (KAYKIT_ARCHETYPES.has(archetype)) {
    animations = await loadKaykitClips();
  }
  return { scene, animations, archetype };
}

export function _resetHeroCache(): void {
  heroCache.clear();
  kaykitClipsCache = null;
}
