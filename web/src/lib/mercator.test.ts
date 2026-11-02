import { describe, expect, it } from "vitest";
import { mercatorView } from "./mercator";

// Google's documented world-pixel formulas, which Vega's mercator has to reproduce.
const worldPx = (lon: number, lat: number, zoom: number) => {
  const world = 256 * 2 ** zoom;
  const sin = Math.sin((lat * Math.PI) / 180);
  return { x: ((lon + 180) / 360) * world, y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * world };
};

/** Where Vega's mercator (x = k*lambda + tx, y = ty - k*ln(tan(pi/4 + phi/2))) draws a point. */
const vegaPx = (lon: number, lat: number, k: number, [tx, ty]: [number, number]) => ({
  x: k * ((lon * Math.PI) / 180) + tx,
  y: ty - k * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)),
});

describe("mercatorView", () => {
  const center = { lon: -87.9, lat: 41.95 };

  it("puts the center in the middle of the view", () => {
    const { scale, translate } = mercatorView(center, 9, 1000, 600);
    const p = vegaPx(center.lon, center.lat, scale, translate);
    expect(p.x).toBeCloseTo(500, 6);
    expect(p.y).toBeCloseTo(300, 6);
  });

  it.each([7, 9, 12])("offsets other points by the same pixels Google does at zoom %i", (zoom) => {
    const { scale, translate } = mercatorView(center, zoom, 1000, 600);
    const [lon, lat] = [-87.63, 41.88]; // the Loop
    const a = worldPx(center.lon, center.lat, zoom);
    const b = worldPx(lon, lat, zoom);
    const p = vegaPx(lon, lat, scale, translate);
    expect(p.x).toBeCloseTo(500 + (b.x - a.x), 6);
    expect(p.y).toBeCloseTo(300 + (b.y - a.y), 6);
  });
});
