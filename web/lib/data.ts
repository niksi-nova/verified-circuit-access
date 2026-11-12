import fs from "node:fs";
import path from "node:path";
import type { Circuit, StatusData } from "@/lib/types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

let circuitsCache: Circuit[] | null = null;
let statusCache: StatusData | null = null;

export function dataAvailable(): boolean {
  return fs.existsSync(path.join(DATA_DIR, "circuits.json"));
}

export function getAllCircuits(): Circuit[] {
  if (!circuitsCache) {
    const raw = fs.readFileSync(path.join(DATA_DIR, "circuits.json"), "utf-8");
    circuitsCache = JSON.parse(raw) as Circuit[];
  }
  return circuitsCache;
}

export function getCircuit(id: string): Circuit | undefined {
  return getAllCircuits().find((c) => c.id === id);
}

export function getStatus(): StatusData | null {
  if (statusCache) return statusCache;
  const file = path.join(DATA_DIR, "status.json");
  if (!fs.existsSync(file)) return null;
  statusCache = JSON.parse(fs.readFileSync(file, "utf-8")) as StatusData;
  return statusCache;
}

export const START_HERE_CLEAN = ["002", "003", "014", "015", "019"];
export const START_HERE_FLAGGED = ["095", "097"];
