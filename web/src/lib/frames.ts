import type { Meta, Mode, RawSnapshot, RawVehicle } from "../api";

/** Longest gap between two snapshots we still glide across; beyond it a vehicle just jumps. */
export const MAX_GLIDE_MS = 15 * 60 * 1000;

const SIZE: Record<Mode, number> = { trains: 90, buses: 28, metra: 110 };
const Z: Record<Mode, number> = { buses: 0, metra: 1, trains: 2 }; // later = drawn on top
const FALLBACK_COLOR = "#6b7280";

/** Static look + tooltip text of a vehicle in one snapshot; position is animated separately. */
export interface Vehicle {
  key: string;
  lat: number;
  lon: number;
  color: string;
  size: number;
  z: number;
  delayed: boolean;
  label: string;
  detail: string;
}

export interface Snapshot {
  t: number; // epoch ms
  vehicles: Map<string, Vehicle>;
}

/** A vehicle at an instant: its look from the snapshot it last appeared in, plus the tweened position. */
export interface Point {
  base: Vehicle;
  lat: number;
  lon: number;
}

const status = (delayed: boolean | null | undefined) => (delayed ? "Delayed" : "On time");

function describe(mode: Mode, v: RawVehicle): { label: string; detail: string } {
  switch (mode) {
    case "trains":
      return {
        label: `${v.route} → ${v.destination ?? "?"}`,
        detail: `Next: ${v.next_stop ?? "?"} · ${status(v.is_delayed)}`,
      };
    case "buses":
      return {
        label: `Bus ${v.route} → ${v.destination ?? "?"}`,
        detail: `${v.speed_mph ?? "?"} mph · ${status(v.is_delayed)}`,
      };
    case "metra":
      return { label: `Metra ${v.route} ${v.destination ?? ""}`.trim(), detail: `Train ${v.label ?? v.id}` };
  }
}

function colorOf(mode: Mode, route: string, meta: Meta): string {
  if (mode === "buses") return meta.bus_color;
  if (mode === "metra") return meta.metra_color;
  return meta.line_colors[route] ?? FALLBACK_COLOR;
}

export function parseSnapshots(raw: RawSnapshot[], meta: Meta): Snapshot[] {
  return raw
    .map((snap) => {
      const vehicles = new Map<string, Vehicle>();
      for (const mode of ["buses", "metra", "trains"] as const) {
        for (const v of snap[mode]) {
          const key = `${mode}:${v.id}`;
          vehicles.set(key, {
            key,
            lat: v.lat,
            lon: v.lon,
            color: colorOf(mode, v.route, meta),
            size: SIZE[mode],
            z: Z[mode],
            delayed: v.is_delayed === true,
            ...describe(mode, v),
          });
        }
      }
      return { t: Date.parse(snap.t), vehicles };
    })
    .sort((a, b) => a.t - b.t);
}

/** Index of the last snapshot at or before `time` (0 when `time` precedes them all). */
function floorIndex(snaps: Snapshot[], time: number): number {
  let lo = 0;
  let hi = snaps.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (snaps[mid].t <= time) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/**
 * Where every vehicle is at `time`. Vehicles present in both neighbouring snapshots glide
 * linearly between them; ones that vanish in the next snapshot hold their last position until
 * it arrives; ones that only appear in the next snapshot show up when it does.
 */
export function frameAt(snaps: Snapshot[], time: number, maxGlideMs = MAX_GLIDE_MS): Point[] {
  if (snaps.length === 0) return [];
  const i = floorIndex(snaps, time);
  const from = snaps[i];
  const to = snaps[i + 1];
  const span = to ? to.t - from.t : 0;
  const f = to && span > 0 && span <= maxGlideMs ? Math.min(1, Math.max(0, (time - from.t) / span)) : 0;

  const points: Point[] = [];
  for (const base of from.vehicles.values()) {
    const next = f > 0 ? to.vehicles.get(base.key) : undefined;
    points.push(
      next
        ? { base, lat: base.lat + (next.lat - base.lat) * f, lon: base.lon + (next.lon - base.lon) * f }
        : { base, lat: base.lat, lon: base.lon },
    );
  }
  return points;
}
