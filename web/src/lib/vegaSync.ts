import { changeset, type View } from "vega";
import type { Point } from "./frames";

const DELAYED_STROKE = "#dc2626";
const NORMAL_STROKE = "#ffffff";

/** The mutable datum Vega holds for one vehicle. Vega owns lon/lat once inserted. */
interface Row {
  key: string;
  lon: number;
  lat: number;
  color: string;
  size: number;
  z: number;
  stroke: string;
  strokeW: number;
  label: string;
  detail: string;
  base: Point["base"];
}

export const VEHICLE_DATASET = "vehicles";

/**
 * Keeps a Vega dataset in step with animation frames. Each vehicle keeps the same datum for as
 * long as it is on the map, so a frame only rewrites lon/lat in place: Vega re-encodes the marks
 * instead of rebuilding them, which keeps hover tooltips steady while things move.
 */
export class VehicleSync {
  private rows = new Map<string, Row>();

  constructor(private view: View) {}

  apply(points: Point[]): void {
    const cs = changeset();
    const seen = new Set<string>();

    for (const p of points) {
      const { base } = p;
      seen.add(base.key);
      const row = this.rows.get(base.key);
      if (!row) {
        const fresh: Row = {
          key: base.key,
          lon: p.lon,
          lat: p.lat,
          color: base.color,
          size: base.size,
          z: base.z,
          stroke: base.delayed ? DELAYED_STROKE : NORMAL_STROKE,
          strokeW: base.delayed ? 1.6 : 0.8,
          label: base.label,
          detail: base.detail,
          base,
        };
        this.rows.set(base.key, fresh);
        cs.insert(fresh);
        continue;
      }
      cs.modify(row, "lon", p.lon).modify(row, "lat", p.lat);
      if (row.base !== base) {
        // Crossed into a new snapshot: delay status and tooltip text may have changed.
        row.base = base;
        cs.modify(row, "label", base.label)
          .modify(row, "detail", base.detail)
          .modify(row, "stroke", base.delayed ? DELAYED_STROKE : NORMAL_STROKE)
          .modify(row, "strokeW", base.delayed ? 1.6 : 0.8);
      }
    }

    for (const [key, row] of this.rows) {
      if (!seen.has(key)) {
        cs.remove(row);
        this.rows.delete(key);
      }
    }
    this.view.change(VEHICLE_DATASET, cs).run();
  }
}
