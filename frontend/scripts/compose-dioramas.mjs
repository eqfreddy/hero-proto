// Programmatic diorama composer for the Battle 3D Viewer.
//
// Reads a small whitelist of primitives from the SciFi MegaKit and stamps them
// into 2 backdrop scenes (server-closet, data-center). Output goes to
// frontend/public/battle-3d/props/<theme>.glb.
//
// Coordinate convention:
//   +x right, +y up, +z toward camera. The diorama sits behind the unit slots
//   (units live near z = 0); back wall is around z = -3, side walls at x = ±3
//   to ±5. Camera looks down +z toward the wall.
//
// Each primitive's local origin sits at floor level, centered in xy. A
// Platform_CenterPlate spans (-2,0,-2)..(2,0,2). A WallBand_Straight is a
// thin panel ~4m wide × 3m tall, default lying so its 4m axis is z (after
// placing we rotate to make it stand on the back wall).
//
// We deliberately keep the script self-contained: import primitives, deep-copy
// nodes, attach them under a fresh root scene, write binary .glb. Texture
// embedding happens automatically because writeBinary inlines image data.

import { NodeIO } from "@gltf-transform/core";
import { dedup, mergeDocuments, prune, textureCompress, unpartition } from "@gltf-transform/functions";
import sharp from "sharp";
import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "../..");
const KIT = path.join(
  REPO,
  "maynewmodels/Modular SciFi MegaKit[Standard]/Modular SciFi MegaKit[Standard]/glTF/",
);
const OUT_DIR = path.join(REPO, "frontend/public/battle-3d/props/");

const io = new NodeIO();

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Quaternion for rotation around Y axis (radians). */
function quatY(rad) {
  const h = rad / 2;
  return [0, Math.sin(h), 0, Math.cos(h)];
}

/** Load a primitive gltf as a Document. */
async function loadPrim(rel) {
  return await io.read(KIT + rel);
}

/**
 * Copy every top-level node from `srcDoc` into `dstDoc` under a new node, then
 * apply transform. Returns the new wrapper node.
 *
 * gltf-transform v4 exposes `dstDoc.merge(srcDoc)` which merges the entire
 * source document's resources (meshes, materials, textures, scenes) into dst.
 * After merging we collect the newly-added scene's root nodes and re-parent
 * them under a fresh wrapper node so we can transform/instance them freely.
 */
function instantiate(dstDoc, srcDoc, { translate = [0, 0, 0], rotate = [0, 0, 0, 1], scale = [1, 1, 1], name = "inst" } = {}) {
  const dstScene = dstDoc.getRoot().listScenes()[0];

  // Track which scenes/nodes existed before merge so we can find the new ones.
  const beforeScenes = new Set(dstDoc.getRoot().listScenes());
  mergeDocuments(dstDoc, srcDoc);
  const newScenes = dstDoc.getRoot().listScenes().filter((s) => !beforeScenes.has(s));

  const wrapper = dstDoc.createNode(name);
  wrapper.setTranslation(translate);
  wrapper.setRotation(rotate);
  wrapper.setScale(scale);

  for (const ns of newScenes) {
    for (const n of ns.listChildren()) {
      ns.removeChild(n);
      wrapper.addChild(n);
    }
    ns.dispose();
  }

  dstScene.addChild(wrapper);
  return wrapper;
}

/**
 * Build a fresh empty document with one named scene and ready for assembly.
 */
function newDocument(sceneName) {
  const doc = io.createDocument ? io.createDocument() : null;
  // gltf-transform v4 doesn't have createDocument on IO — use Document directly
  if (!doc) {
    return null;
  }
  return doc;
}

// ---------------------------------------------------------------------------
// Composition recipes
// ---------------------------------------------------------------------------

/**
 * server-closet: small 6×6m room with a back wall lined with server racks.
 *
 *   - Floor: Platform_CenterPlate scaled 1.5× (→ 6×6m) at origin
 *   - Back wall: 2× WallBand_Straight panels at z = -3, side-by-side along x
 *   - Side walls: 1× WallBand_Straight at x = ±3, rotated 90° to face inward
 *   - 3× Prop_Computer arrayed across the back wall
 *   - 2× Prop_Crate3 stacked at the right
 *   - 2× Prop_Light_Floor along the floor edges
 */
async function buildServerCloset() {
  const { Document } = await import("@gltf-transform/core");
  const doc = new Document();
  doc.createScene("server-closet");

  // Primitive sources (loaded once, instantiated multiple times).
  const wall = await loadPrim("Walls/WallBand_Straight.gltf");
  const wallAstra = await loadPrim("Walls/WallAstra_Straight.gltf");
  const floor = await loadPrim("Platforms/Platform_CenterPlate.gltf");
  const computer = await loadPrim("Props/Prop_Computer.gltf");
  const crate = await loadPrim("Props/Prop_Crate3.gltf");
  const light = await loadPrim("Props/Prop_Light_Floor.gltf");

  // Floor: 4×4m → scale 1.5 = 6×6m.
  instantiate(doc, await cloneDoc(floor), {
    translate: [0, 0, -1.0],
    scale: [1.5, 1, 1.5],
    name: "floor",
  });

  // Back wall: WallBand panel is 4m on z-axis × 3m tall × thin. Rotate 90° around Y
  // so the 4m extent lies along x. Two panels side-by-side cover ~8m of back wall;
  // we'll center them so they straddle x=0 with the join at x=0.
  for (let i = 0; i < 2; i++) {
    const x = (i - 0.5) * 3.6; // -1.8, +1.8 → 7.2m wide, slight overlap is fine
    instantiate(doc, await cloneDoc(wall), {
      translate: [x, 0, -3.0],
      rotate: quatY(Math.PI / 2),
      name: `back-wall-${i}`,
    });
  }

  // Side walls: rotate 0° so 4m runs along z, place at x = ±3.
  instantiate(doc, await cloneDoc(wall), {
    translate: [-3.0, 0, -1.0],
    rotate: quatY(0),
    name: "side-wall-L",
  });
  instantiate(doc, await cloneDoc(wall), {
    translate: [3.0, 0, -1.0],
    rotate: quatY(Math.PI),
    name: "side-wall-R",
  });

  // Computers: server racks lined up across back wall. Prop_Computer is ~0.7×1.6×0.5.
  // Place at z = -2.6 (just in front of back wall), spaced across x.
  for (let i = 0; i < 3; i++) {
    const x = (i - 1) * 1.5;
    instantiate(doc, await cloneDoc(computer), {
      translate: [x, 0, -2.6],
      name: `rack-${i}`,
    });
  }

  // Stacked crates at the right corner.
  instantiate(doc, await cloneDoc(crate), {
    translate: [2.4, 0.5, -2.4],
    name: "crate-bottom",
  });
  instantiate(doc, await cloneDoc(crate), {
    translate: [2.4, 1.5, -2.4],
    name: "crate-top",
  });

  // Floor lights along the front edge (closer to camera than units; this gives
  // a runway-light effect).
  for (let i = 0; i < 2; i++) {
    const x = (i - 0.5) * 4;
    instantiate(doc, await cloneDoc(light), {
      translate: [x, 0, 0.2],
      rotate: quatY(Math.PI),
      name: `light-${i}`,
    });
  }

  // Decorative accent: one Astra panel as a wider feature on left side wall
  // (single instance — keeps tri budget under control).
  instantiate(doc, await cloneDoc(wallAstra), {
    translate: [-2.95, 0, 0.5],
    rotate: quatY(0),
    scale: [0.7, 1, 0.7],
    name: "accent-astra",
  });

  await doc.transform(dedup(), prune());
  return doc;
}

/**
 * data-center: wider 10×6m hall with a long back wall and 4 server racks.
 *
 *   - Floor: 2× Platform_CenterPlate side-by-side (→ 8×4m) plus an extra strip
 *     scaled wider; we'll just use 1 platform scaled 2.5×1.5 = 10×6m
 *   - Back wall: 3× WallBand panels along x
 *   - Side walls: 1× WallBand each side
 *   - 4× Prop_Computer evenly spaced across back wall
 *   - 4× Prop_Light_Floor along the front edge
 *   - 2× Prop_Crate3 stacked at right corner
 */
async function buildDataCenter() {
  const { Document } = await import("@gltf-transform/core");
  const doc = new Document();
  doc.createScene("data-center");

  const wall = await loadPrim("Walls/WallBand_Straight.gltf");
  const floor = await loadPrim("Platforms/Platform_CenterPlate.gltf");
  const computer = await loadPrim("Props/Prop_Computer.gltf");
  const crate = await loadPrim("Props/Prop_Crate3.gltf");
  const light = await loadPrim("Props/Prop_Light_Floor.gltf");

  // Floor: 4×4m base → scale 2.5×1.5 = 10×6m
  instantiate(doc, await cloneDoc(floor), {
    translate: [0, 0, -1.0],
    scale: [2.5, 1, 1.5],
    name: "floor",
  });

  // Back wall: 3 panels rotated 90° around Y, spread across 10m
  for (let i = 0; i < 3; i++) {
    const x = (i - 1) * 3.6; // -3.6, 0, +3.6
    instantiate(doc, await cloneDoc(wall), {
      translate: [x, 0, -3.0],
      rotate: quatY(Math.PI / 2),
      name: `back-wall-${i}`,
    });
  }

  // Side walls
  instantiate(doc, await cloneDoc(wall), {
    translate: [-5.0, 0, -1.0],
    rotate: quatY(0),
    name: "side-wall-L",
  });
  instantiate(doc, await cloneDoc(wall), {
    translate: [5.0, 0, -1.0],
    rotate: quatY(Math.PI),
    name: "side-wall-R",
  });

  // Server racks: 4 across, more spread out
  for (let i = 0; i < 4; i++) {
    const x = (i - 1.5) * 2.2; // -3.3, -1.1, 1.1, 3.3
    instantiate(doc, await cloneDoc(computer), {
      translate: [x, 0, -2.6],
      name: `rack-${i}`,
    });
  }

  // Floor lights: 4 along the front edge
  for (let i = 0; i < 4; i++) {
    const x = (i - 1.5) * 2.4;
    instantiate(doc, await cloneDoc(light), {
      translate: [x, 0, 0.2],
      rotate: quatY(Math.PI),
      name: `light-${i}`,
    });
  }

  // Stacked crates at right corner
  instantiate(doc, await cloneDoc(crate), {
    translate: [4.3, 0.5, -2.4],
    name: "crate-bottom",
  });
  instantiate(doc, await cloneDoc(crate), {
    translate: [4.3, 1.5, -2.4],
    name: "crate-top",
  });

  await doc.transform(dedup(), prune());
  return doc;
}

/**
 * Re-load a primitive document from disk so each `merge()` consumes a fresh
 * copy. (gltf-transform's `merge` mutates the source's parent links; reusing
 * the same source twice corrupts later instances.)
 */
async function cloneDoc(srcDoc) {
  // Round-trip through binary to get a deep-clone.
  const bin = await io.writeBinary(srcDoc);
  return await io.readBinary(bin);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function writeDoc(doc, name) {
  await fs.mkdir(OUT_DIR, { recursive: true });
  // Resize/compress textures (4K source → 256 PNG/JPEG; targets ≤1MB total),
  // then collapse all buffers/buffer-views into a single buffer (required for .glb).
  await doc.transform(
    textureCompress({
      encoder: sharp,
      targetFormat: "jpeg",
      resize: [256, 256],
      quality: 80,
      slots: /^(?!normalTexture).*$/,
    }),
    textureCompress({
      encoder: sharp,
      targetFormat: "png",
      resize: [256, 256],
      slots: /^normalTexture$/,
    }),
    unpartition(),
  );
  const outPath = path.join(OUT_DIR, `${name}.glb`);
  await io.write(outPath, doc);
  const stat = await fs.stat(outPath);
  console.log(`wrote ${name}.glb  (${(stat.size / 1024).toFixed(1)} KB)`);
}

(async () => {
  const closet = await buildServerCloset();
  await writeDoc(closet, "server-closet");

  const dc = await buildDataCenter();
  await writeDoc(dc, "data-center");

  console.log("\nNext: run gltf-pipeline draco compression on each output:");
  console.log(
    "  npx gltf-pipeline -i public/battle-3d/props/server-closet.glb -o public/battle-3d/props/server-closet.glb --draco.compressionLevel=10",
  );
})();
