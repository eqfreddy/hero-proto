// Quick probe of source primitives — dims + tri counts. Used during composition planning.
import { NodeIO } from "@gltf-transform/core";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(__dirname, "../..");
const BASE = path.join(
  REPO,
  "maynewmodels/Modular SciFi MegaKit[Standard]/Modular SciFi MegaKit[Standard]/glTF/",
);

const files = [
  "Walls/WallBand_Straight.gltf",
  "Walls/WallAstra_Straight.gltf",
  "Platforms/Platform_CenterPlate.gltf",
  "Platforms/Platform_3Plates.gltf",
  "Props/Prop_Computer.gltf",
  "Props/Prop_Light_Corner.gltf",
  "Props/Prop_Light_Floor.gltf",
  "Props/Prop_Crate3.gltf",
  "Props/Prop_Cable_1.gltf",
];

const io = new NodeIO();
for (const f of files) {
  const doc = await io.read(BASE + f);
  const root = doc.getRoot();
  let tris = 0;
  const min = [Infinity, Infinity, Infinity];
  const max = [-Infinity, -Infinity, -Infinity];
  for (const m of root.listMeshes()) {
    for (const p of m.listPrimitives()) {
      const idx = p.getIndices();
      const pos = p.getAttribute("POSITION");
      if (idx) tris += idx.getCount() / 3;
      else if (pos) tris += pos.getCount() / 3;
      if (pos) {
        const pmin = pos.getMin([]);
        const pmax = pos.getMax([]);
        for (let i = 0; i < 3; i++) {
          min[i] = Math.min(min[i], pmin[i]);
          max[i] = Math.max(max[i], pmax[i]);
        }
      }
    }
  }
  const dim = max.map((v, i) => (v - min[i]).toFixed(2));
  console.log(
    f.padEnd(40),
    "tris=" + String(tris).padStart(5),
    "dim=" + dim.join("x").padEnd(20),
    "min=" + min.map((v) => v.toFixed(2)).join(","),
  );
}
