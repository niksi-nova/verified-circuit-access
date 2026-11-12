// Fallback for platforms where a symlink at web/public/data doesn't work
// (e.g. Windows without developer mode). Copies demo/data into
// web/public/data instead. Both paths are git-ignored.
import { cpSync, existsSync, rmSync, lstatSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const source = path.resolve(here, "..", "..", "demo", "data");
const target = path.resolve(here, "..", "public", "data");

if (!existsSync(source)) {
  console.error(`No demo data at ${source}. Run scripts/build_demo_data.py first.`);
  process.exit(1);
}

if (existsSync(target) && !lstatSync(target).isSymbolicLink()) {
  rmSync(target, { recursive: true, force: true });
}
if (existsSync(target) && lstatSync(target).isSymbolicLink()) {
  rmSync(target, { force: true });
}

cpSync(source, target, { recursive: true, dereference: true });
console.log(`Copied ${source} -> ${target}`);
