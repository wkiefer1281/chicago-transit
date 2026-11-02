import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import embed, { type Result } from "vega-embed";
import type { Point } from "../lib/frames";
import { VehicleSync } from "../lib/vegaSync";
import { mapSpec } from "../specs";

export interface MapHandle {
  setPoints(points: Point[]): void;
}

const escapeHtml = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

const spec = mapSpec();

/** The animated map. Frames are pushed imperatively (60 fps) rather than through React state. */
export const MapView = forwardRef<MapHandle>(function MapView(_props, ref) {
  const el = useRef<HTMLDivElement>(null);
  const sync = useRef<VehicleSync | null>(null);
  const pending = useRef<Point[]>([]);

  useImperativeHandle(ref, () => ({
    setPoints(points) {
      pending.current = points;
      sync.current?.apply(points);
    },
  }));

  useEffect(() => {
    let cancelled = false;
    let result: Result | undefined;
    embed(el.current!, spec, {
      actions: false,
      renderer: "canvas",
      tooltip: {
        formatTooltip: (value) => {
          const v = value as { label?: string; detail?: string };
          return `<strong>${escapeHtml(v.label)}</strong><br>${escapeHtml(v.detail)}`;
        },
      },
    }).then((r) => {
      if (cancelled) return r.finalize();
      result = r;
      sync.current = new VehicleSync(r.view);
      sync.current.apply(pending.current); // frames that arrived before the view was ready
    });
    return () => {
      cancelled = true;
      sync.current = null;
      result?.finalize();
    };
  }, []);

  return <div ref={el} className="map" role="img" aria-label="Live map of CTA and Metra vehicles in Chicago" />;
});
