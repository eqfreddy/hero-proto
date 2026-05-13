import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { DRACOLoader } from "three/examples/jsm/loaders/DRACOLoader.js";
import type { GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone as cloneSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";
import * as THREE from "three";

const HERO_BASE = `${import.meta.env.BASE_URL}battle-3d/heroes`;

// Cache-bust GLB URLs whenever the SPA rebuilds. The Workbox service
// worker keys cache entries by URL; without a versioned query the same
// filename (e.g. knight.glb) is served from cache forever even after we
// swap the underlying bytes (KayKit → Quaternius migration regression).
const GLB_VERSION = __APP_VERSION__;

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

function loadGLTF(url: string): Promise<GLTF> {
  return new Promise((resolve, reject) => {
    gltfLoader.load(url, resolve, undefined, reject);
  });
}

export async function loadHero(archetype: string): Promise<HeroAssets> {
  let p = heroCache.get(archetype);
  if (!p) {
    p = loadGLTF(`${HERO_BASE}/${archetype}.glb?v=${GLB_VERSION}`);
    heroCache.set(archetype, p);
  }
  const gltf = await p;
  // Use SkeletonUtils.clone — plain Object3D.clone() shares the skeleton
  // across instances, which makes every same-archetype unit render at
  // the same animated bone positions (i.e. visually stacked).
  const scene = cloneSkinned(gltf.scene) as THREE.Group;
  return { scene, animations: gltf.animations, archetype };
}

export function _resetHeroCache(): void {
  heroCache.clear();
}
