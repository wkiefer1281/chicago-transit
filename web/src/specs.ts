import type { TopLevelSpec } from "vega-lite";
import { VEHICLE_DATASET } from "./lib/vegaSync";

const SCHEMA = "https://vega.github.io/schema/vega-lite/v6.json";
const BAR_COLOR = "#2563eb"; // single hue: magnitude, not identity
const GRID = "#e5e7eb";

const geoFeatures = (url: string) => ({ url, format: { type: "json" as const, property: "features" } });

/** Chicago with CTA track and a live `vehicles` dataset (see VehicleSync). No tile basemap. */
export function mapSpec(): TopLevelSpec {
  const noScale = { scale: null, legend: null };
  return {
    $schema: SCHEMA,
    width: "container",
    height: 640,
    autosize: { type: "fit", contains: "padding" },
    config: { view: { stroke: null } },
    projection: { type: "mercator" },
    layer: [
      {
        data: geoFeatures("/geo/community_areas.json"),
        mark: { type: "geoshape", fill: "#f3f4f6", stroke: "#ffffff", strokeWidth: 1 },
      },
      {
        data: geoFeatures("/geo/cta_rail.json"),
        mark: { type: "geoshape", filled: false, stroke: "#c4c9d2", strokeWidth: 1.6 },
      },
      {
        data: { name: VEHICLE_DATASET },
        mark: { type: "circle", opacity: 0.92 },
        encoding: {
          longitude: { field: "lon", type: "quantitative" },
          latitude: { field: "lat", type: "quantitative" },
          color: { field: "color", type: "nominal", ...noScale },
          size: { field: "size", type: "quantitative", ...noScale },
          stroke: { field: "stroke", type: "nominal", ...noScale },
          strokeWidth: { field: "strokeW", type: "quantitative", ...noScale },
          order: { field: "z", type: "quantitative" },
          tooltip: [
            { field: "label", type: "nominal", title: "label" },
            { field: "detail", type: "nominal", title: "detail" },
          ],
        },
      },
    ],
  };
}

export const ROWS = "rows";

/** % of trains delayed per line right now. Fed through the `rows` dataset. */
export function delayedByLineSpec(topPct: number, lines: number): TopLevelSpec {
  return {
    $schema: SCHEMA,
    width: "container",
    height: Math.max(120, 28 * lines),
    data: { name: ROWS },
    config: { view: { stroke: null }, axis: { gridColor: GRID } },
    encoding: {
      y: { field: "route", type: "nominal", sort: null, title: null, axis: { domain: false, ticks: false } },
      x: { field: "delayed_pct", type: "quantitative", title: "% of trains delayed", scale: { domain: [0, topPct] } },
    },
    layer: [
      {
        mark: { type: "bar", size: 14, cornerRadiusEnd: 4, color: BAR_COLOR },
        encoding: {
          tooltip: [
            { field: "route", title: "Line" },
            { field: "delayed_pct", title: "% delayed", format: ".1f" },
            { field: "delayed", title: "Delayed" },
            { field: "vehicles", title: "Running" },
          ],
        },
      },
      {
        mark: { type: "text", align: "left", dx: 4 },
        encoding: { text: { field: "delayed_pct", type: "quantitative", format: ".1f" } },
      },
    ],
  };
}

/** % of trains delayed over time, one line per CTA line in its own color. */
export function delayTrendSpec(lineColors: Record<string, string>, topPct: number): TopLevelSpec {
  const lines = Object.keys(lineColors);
  return {
    $schema: SCHEMA,
    width: "container",
    height: 300,
    data: { name: ROWS },
    config: { view: { stroke: null }, axis: { gridColor: GRID } },
    mark: { type: "line", strokeWidth: 2, point: { size: 36 } },
    encoding: {
      x: { field: "bucket", type: "temporal", title: null },
      y: { field: "delayed_pct", type: "quantitative", title: "% of trains delayed", scale: { domain: [0, topPct] } },
      color: {
        field: "route",
        type: "nominal",
        title: "Line",
        scale: { domain: lines, range: lines.map((l) => lineColors[l]) },
      },
      tooltip: [
        { field: "bucket", type: "temporal", title: "Time" },
        { field: "route", title: "Line" },
        { field: "delayed_pct", type: "quantitative", title: "% delayed", format: ".1f" },
        { field: "delayed", title: "Delayed" },
        { field: "total", title: "Train-samples" },
      ],
    },
  };
}
