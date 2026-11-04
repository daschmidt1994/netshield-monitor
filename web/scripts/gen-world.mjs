// Generates a compact world GeoJSON keyed by ISO 3166-1 alpha-2 codes.
// Source: Natural Earth (public domain) via world-atlas (ISC). Output is committed so
// neither the Docker build nor the Android build needs network access for map data.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { feature } from "topojson-client";
import countries from "i18n-iso-countries";

const require = createRequire(import.meta.url);
const topo = JSON.parse(readFileSync(require.resolve("world-atlas/countries-110m.json"), "utf8"));
const geo = feature(topo, topo.objects.countries);
const round = (c) => (Array.isArray(c[0]) ? c.map(round) : [Math.round(c[0] * 100) / 100, Math.round(c[1] * 100) / 100]);
const out = {
  type: "FeatureCollection",
  attribution: "Natural Earth (public domain) via world-atlas",
  features: geo.features
    .map((f) => {
      const a2 = countries.numericToAlpha2(String(f.id).padStart(3, "0"));
      if (!a2) return null;
      return { type: "Feature", id: a2, properties: { name: a2 }, geometry: { type: f.geometry.type, coordinates: round(f.geometry.coordinates) } };
    })
    .filter(Boolean),
};
const json = JSON.stringify(out);
for (const target of ["public/world.json", "../android/app/src/main/assets/world.json"]) {
  mkdirSync(target.substring(0, target.lastIndexOf("/")), { recursive: true });
  writeFileSync(target, json);
}
console.log(`wrote ${out.features.length} countries, ${(json.length / 1024).toFixed(0)} KiB`);
