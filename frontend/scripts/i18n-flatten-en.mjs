#!/usr/bin/env node
/**
 * Generates flattened string->key map from English messages for bulk UI migration.
 * Run: node scripts/i18n-flatten-en.mjs > /tmp/i18n-map.json
 */
import fs from "fs";
import path from "path";
import { fileURLToPath, pathToFileURL } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const enIndex = path.join(__dirname, "../src/messages/en/index.ts");

// dynamic import compiled ts won't work - read and eval simple structure
import enMessages from "../src/messages/en/index.ts" assert { type: "json" }.catch?.() 

function flatten(obj, prefix = "") {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "string") {
      if (v.length >= 3) out[v] = key;
    } else if (v && typeof v === "object") {
      Object.assign(out, flatten(v, key));
    }
  }
  return out;
}

// Load via ts-node alternative: use built json from manual export
const modPath = path.join(__dirname, "../src/messages/en");
const parts = ["shell", "common", "constants", "chat", "app", "home", "cohort", "labels"];
const merged = {};
for (const part of parts) {
  const file = path.join(modPath, `${part}.ts`);
  if (!fs.existsSync(file)) continue;
  const raw = fs.readFileSync(file, "utf8");
  const jsonMatch = raw.match(/=\s*(\{[\s\S]*\})\s*as const/);
  if (!jsonMatch) continue;
  try {
    merged[part] = Function(`"use strict"; return (${jsonMatch[1]});`)();
  } catch {
    // skip
  }
}

const map = flatten(merged);
console.log(JSON.stringify(map, null, 2));
