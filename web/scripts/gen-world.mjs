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
// Rings crossing the antimeridian (Russia, Fiji, …) would draw lines across the whole map:
// move the minority side onto the ±180° edge instead.
const fixRing = (ring) => {
  const crosses = ring.some((p, i) => i > 0 && Math.abs(p[0] - ring[i - 1][0]) > 180);
  if (!crosses) return ring;
  const east = ring.filter((p) => p[0] >= 0).length >= ring.length / 2;
  return ring.map(([x, y]) => [east ? (x < 0 ? 180 : x) : (x > 0 ? -180 : x), y]);
};
const fixGeom = (g) => g.type === "Polygon"
  ? { type: g.type, coordinates: g.coordinates.map(fixRing) }
  : { type: g.type, coordinates: g.coordinates.map((poly) => poly.map(fixRing)) };
const round = (c) => (Array.isArray(c[0]) ? c.map(round) : [Math.round(c[0] * 100) / 100, Math.round(c[1] * 100) / 100]);
const out = {
  type: "FeatureCollection",
  attribution: "Natural Earth (public domain) via world-atlas",
  features: geo.features
    .map((f) => {
      const a2 = countries.numericToAlpha2(String(f.id).padStart(3, "0"));
      if (!a2 || a2 === "AQ") return null; // Antarctica: no traffic, only clutters the map
      const g = fixGeom(f.geometry);
      return { type: "Feature", id: a2, properties: { name: a2 }, geometry: { type: g.type, coordinates: round(g.coordinates) } };
    })
    .filter(Boolean),
};
const json = JSON.stringify(out);
for (const target of ["public/world.json", "../android/app/src/main/assets/world.json"]) {
  mkdirSync(target.substring(0, target.lastIndexOf("/")), { recursive: true });
  writeFileSync(target, json);
}
console.log(`wrote ${out.features.length} countries, ${(json.length / 1024).toFixed(0)} KiB`);
