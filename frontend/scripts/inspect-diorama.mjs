// Inspector for composited dioramas. Reports mesh / primitive / triangle
// counts, bounding box, and file size — used to verify ≤1 MB and ≤5k tris
// per scene per the Battle 3D Viewer spec §6 budget.

import { NodeIO } from "@gltf-transform/core";
import { KHRDracoMeshCompression } from "@gltf-transform/extensions";
import draco3d from "draco3dgltf";
import path from "node:path";
import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "../..");
const OUT_DIR = path.join(REPO, "frontend/public/battle-3d/props/");

const io = new NodeIO()
  .registerExtensions([KHRDracoMeshCompression])
  .registerDependencies({
    "draco3d.decoder": await draco3d.createDecoderModule(),
  });

const themes = ["server-closet", "data-center"];

for (const t of themes) {
  const file = path.join(OUT_DIR, `${t}.glb`);
  const stat = await fs.stat(file);
  const doc = await io.read(file);
  const root = doc.getRoot();

  const meshes = root.listMeshes();
  let prims = 0;
  let tris = 0;
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];

  // Walk scene graph to apply node transforms when computing world-space bbox.
  const scene = root.listScenes()[0];
  const traverse = (node, parentMat) => {
    const mat = mulMat4(parentMat, nodeMat4(node));
    const mesh = node.getMesh();
    if (mesh) {
      for (const p of mesh.listPrimitives()) {
        prims += 1;
        const idx = p.getIndices();
        const pos = p.getAttribute("POSITION");
        if (idx) tris += idx.getCount() / 3;
        else if (pos) tris += pos.getCount() / 3;
        if (pos) {
          // Sample 8 corners of the primitive's local AABB for cheap world bbox.
          const pmin = pos.getMin([]);
          const pmax = pos.getMax([]);
          for (let bx = 0; bx < 2; bx++) {
            for (let by = 0; by < 2; by++) {
              for (let bz = 0; bz < 2; bz++) {
                const v = applyMat4(mat, [
                  bx ? pmax[0] : pmin[0],
                  by ? pmax[1] : pmin[1],
                  bz ? pmax[2] : pmin[2],
                ]);
                for (let i = 0; i < 3; i++) {
                  if (v[i] < min[i]) min[i] = v[i];
                  if (v[i] > max[i]) max[i] = v[i];
                }
              }
            }
          }
        }
      }
    }
    for (const c of node.listChildren()) traverse(c, mat);
  };
  for (const n of scene.listChildren()) traverse(n, identityMat4());

  const dim = max.map((v, i) => (v - min[i]).toFixed(2));
  console.log(`${t}.glb`);
  console.log(`  size: ${(stat.size / 1024).toFixed(1)} KB`);
  console.log(`  meshes: ${meshes.length}  primitives: ${prims}  triangles: ${tris}`);
  console.log(`  bbox dim (W×H×D): ${dim.join(" × ")}  m`);
  console.log(`  bbox min: ${min.map((v) => v.toFixed(2)).join(", ")}`);
  console.log(`  bbox max: ${max.map((v) => v.toFixed(2)).join(", ")}`);

  const sizeOk = stat.size <= 1024 * 1024;
  const trisOk = tris <= 5000;
  console.log(
    `  budget: size ${sizeOk ? "OK" : "OVER"}  tris ${trisOk ? "OK" : "OVER"}`,
  );
  console.log();
}

// ---------- minimal mat4 helpers (avoid pulling in gl-matrix) ----------

function identityMat4() {
  return new Float64Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]);
}

function nodeMat4(node) {
  const t = node.getTranslation();
  const r = node.getRotation();
  const s = node.getScale();
  return composeTRS(t, r, s);
}

function composeTRS(t, r, s) {
  const [x, y, z, w] = r;
  const [sx, sy, sz] = s;
  const xx = x * x, xy = x * y, xz = x * z, xw = x * w;
  const yy = y * y, yz = y * z, yw = y * w;
  const zz = z * z, zw = z * w;
  const m = new Float64Array(16);
  m[0] = (1 - 2 * (yy + zz)) * sx;
  m[1] = (2 * (xy + zw)) * sx;
  m[2] = (2 * (xz - yw)) * sx;
  m[3] = 0;
  m[4] = (2 * (xy - zw)) * sy;
  m[5] = (1 - 2 * (xx + zz)) * sy;
  m[6] = (2 * (yz + xw)) * sy;
  m[7] = 0;
  m[8] = (2 * (xz + yw)) * sz;
  m[9] = (2 * (yz - xw)) * sz;
  m[10] = (1 - 2 * (xx + yy)) * sz;
  m[11] = 0;
  m[12] = t[0];
  m[13] = t[1];
  m[14] = t[2];
  m[15] = 1;
  return m;
}

function mulMat4(a, b) {
  const out = new Float64Array(16);
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 4; c++) {
      out[c * 4 + r] =
        a[0 * 4 + r] * b[c * 4 + 0] +
        a[1 * 4 + r] * b[c * 4 + 1] +
        a[2 * 4 + r] * b[c * 4 + 2] +
        a[3 * 4 + r] * b[c * 4 + 3];
    }
  }
  return out;
}

function applyMat4(m, v) {
  const [x, y, z] = v;
  return [
    m[0] * x + m[4] * y + m[8] * z + m[12],
    m[1] * x + m[5] * y + m[9] * z + m[13],
    m[2] * x + m[6] * y + m[10] * z + m[14],
  ];
}
