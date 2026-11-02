export interface Meta {
  refresh_s: number;
  line_colors: Record<string, string>;
  bus_color: string;
  metra_color: string;
  history_windows: string[];
  google_maps_api_key: string | null;
}

export interface GroupDelay {
  route: string;
  vehicles: number;
  delayed: number;
  delayed_pct: number;
}

export interface Summary {
  updated_at: string | null;
  age_minutes: number | null;
  stale: boolean;
  kpis: {
    trains: number;
    trains_delayed_pct: number;
    buses: number;
    buses_delayed_pct: number;
    metra: number;
  };
  trains_by_line: GroupDelay[];
  buses_by_route: GroupDelay[];
}

export type Mode = "trains" | "buses" | "metra";

/** One vehicle in one ETL snapshot, as the API sends it. */
export interface RawVehicle {
  id: string;
  route: string;
  lat: number;
  lon: number;
  destination: string | null;
  next_stop?: string | null;
  speed_mph?: number | null;
  label?: string | null;
  is_delayed?: boolean | null;
}

export interface RawSnapshot extends Record<Mode, RawVehicle[]> {
  t: string;
}

export interface HistoryRow {
  bucket: string;
  route: string;
  delayed: number;
  total: number;
  delayed_pct: number;
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const getMeta = (signal?: AbortSignal) => getJson<Meta>("/api/meta", signal);
export const getSummary = (signal?: AbortSignal) => getJson<Summary>("/api/summary", signal);
export const getPositions = (minutes: number, signal?: AbortSignal) =>
  getJson<{ snapshots: RawSnapshot[] }>(`/api/positions?minutes=${minutes}`, signal).then((r) => r.snapshots);
export const getDelayHistory = (window: string, signal?: AbortSignal) =>
  getJson<{ rows: HistoryRow[] }>(`/api/delay-history?window=${window}`, signal).then((r) => r.rows);
