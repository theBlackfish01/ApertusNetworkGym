// The network drawn from the topology's coordinates (longitude, latitude), no map tiles: the page
// works without a network connection.

import type { NodeRow } from "./types";

export interface Point { x: number; y: number }

/** Equirectangular projection, corrected for latitude, fitted into width × height with a margin. */
export function project(nodes: NodeRow[], width: number, height: number, margin = 30): Record<string, Point> {
  if (!nodes.length) return {};
  const lons = nodes.map((n) => n.lon), lats = nodes.map((n) => n.lat);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons), minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const k = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);
  const w = (maxLon - minLon) * k || 1, h = maxLat - minLat || 1;
  const scale = Math.min((width - 2 * margin) / w, (height - 2 * margin) / h);
  const ox = (width - w * scale) / 2, oy = (height - h * scale) / 2;
  const out: Record<string, Point> = {};
  for (const n of nodes) out[n.name] = { x: ox + (n.lon - minLon) * k * scale, y: oy + (maxLat - n.lat) * scale };
  return out;
}

export function linkKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`;
}

/** The links of a route, as keys. */
export function routeLinks(route: string[] | null | undefined): Set<string> {
  const out = new Set<string>();
  if (!route) return out;
  for (let i = 1; i < route.length; i++) out.add(linkKey(route[i - 1], route[i]));
  return out;
}
