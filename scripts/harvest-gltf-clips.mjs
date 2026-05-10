// Parses GLB JSON chunks and prints animation clip names per file.
// Usage: node scripts/harvest-gltf-clips.mjs
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const HEROES_DIR = "frontend/public/battle-3d/heroes";
const files = readdirSync(HEROES_DIR).filter((f) => f.endsWith(".glb")).sort();

const GLB_MAGIC = 0x46546c67; // "glTF"
const JSON_CHUNK = 0x4e4f534a; // "JSON"

for (const file of files) {
  const buf = readFileSync(join(HEROES_DIR, file));
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const magic = view.getUint32(0, true);
  if (magic !== GLB_MAGIC) {
    console.error(`# ${file}: NOT a GLB (bad magic)`);
    continue;
  }
  const jsonLen = view.getUint32(12, true);
  const jsonType = view.getUint32(16, true);
  if (jsonType !== JSON_CHUNK) {
    console.error(`# ${file}: first chunk is not JSON`);
    continue;
  }
  const jsonBuf = buf.subarray(20, 20 + jsonLen);
  const gltf = JSON.parse(new TextDecoder("utf-8").decode(jsonBuf));
  const clips = (gltf.animations ?? []).map((a) => a.name);
  console.log(`\n## ${file.replace(".glb", "")}`);
  console.log(`clips (${clips.length}):`);
  for (const c of clips) console.log(`  - ${c}`);
}
