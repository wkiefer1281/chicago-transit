import { describe, expect, it } from "vitest";
import type { Meta, RawSnapshot, RawVehicle } from "../api";
import { frameAt, parseSnapshots } from "./frames";

const meta: Meta = {
  refresh_s: 60,
  line_colors: { "Red Line": "#c60c30" },
  bus_color: "#0f766e",
  metra_color: "#2563eb",
  history_windows: ["24h"],
};

const train = (id: string, lat: number, lon: number, extra: Partial<RawVehicle> = {}): RawVehicle => ({
  id,
  route: "Red Line",
  lat,
  lon,
  destination: "Howard",
  next_stop: "Belmont",
  is_delayed: false,
  ...extra,
});

const snap = (t: string, trains: RawVehicle[]): RawSnapshot => ({ t, trains, buses: [], metra: [] });

const MIN = 60_000;
const T0 = Date.parse("2026-11-01T12:00:00Z");
const T1 = T0 + 5 * MIN;

const snaps = parseSnapshots(
  [
    snap("2026-11-01T12:05:00Z", [train("1", 42, -87.8), train("new", 41.5, -87.5)]), // deliberately out of order
    snap("2026-11-01T12:00:00Z", [train("1", 41, -87.6), train("gone", 41.1, -87.1)]),
  ],
  meta,
);

describe("parseSnapshots", () => {
  it("sorts by time and styles vehicles", () => {
    expect(snaps.map((s) => s.t)).toEqual([T0, T1]);
    const v = snaps[0].vehicles.get("trains:1")!;
    expect(v.color).toBe("#c60c30");
    expect(v.label).toBe("Red Line → Howard");
    expect(v.detail).toBe("Next: Belmont · On time");
  });

  it("falls back for unknown lines and missing fields", () => {
    const [s] = parseSnapshots(
      [snap("2026-11-01T12:00:00Z", [train("x", 1, 1, { route: "Mystery", next_stop: null, is_delayed: true })])],
      meta,
    );
    const v = s.vehicles.get("trains:x")!;
    expect(v.color).toBe("#6b7280");
    expect(v.detail).toBe("Next: ? · Delayed");
    expect(v.delayed).toBe(true);
  });
});

describe("frameAt", () => {
  const byKey = (time: number, gap?: number) =>
    new Map(frameAt(snaps, time, gap).map((p) => [p.base.key, p]));

  it("interpolates vehicles present in both snapshots", () => {
    const p = byKey(T0 + 2.5 * MIN).get("trains:1")!;
    expect(p.lat).toBeCloseTo(41.5);
    expect(p.lon).toBeCloseTo(-87.7);
  });

  it("holds vanished vehicles and hides not-yet-seen ones until their snapshot", () => {
    const mid = byKey(T0 + 2.5 * MIN);
    expect(mid.get("trains:gone")).toMatchObject({ lat: 41.1, lon: -87.1 });
    expect(mid.has("trains:new")).toBe(false);
    const end = byKey(T1);
    expect(end.has("trains:gone")).toBe(false);
    expect(end.get("trains:new")).toBeDefined();
  });

  it("clamps outside the recorded range", () => {
    expect(byKey(T0 - MIN).get("trains:1")!.lat).toBe(41);
    expect(byKey(T1 + MIN).get("trains:1")!.lat).toBe(42);
  });

  it("jumps instead of gliding across a long gap", () => {
    expect(byKey(T0 + 4 * MIN, 3 * MIN).get("trains:1")!.lat).toBe(41);
  });

  it("is empty with no snapshots", () => {
    expect(frameAt([], T0)).toEqual([]);
  });
});
