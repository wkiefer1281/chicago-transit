import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getDelayHistory,
  getMeta,
  getPositions,
  getSummary,
  type GroupDelay,
  type HistoryRow,
  type Meta,
  type Mode,
  type Summary,
} from "./api";
import { Kpis } from "./components/Kpis";
import { MapView, type MapHandle } from "./components/MapView";
import { PlaybackBar } from "./components/PlaybackBar";
import { VegaChart } from "./components/VegaChart";
import { usePlayback } from "./hooks/usePlayback";
import { usePolling } from "./hooks/usePolling";
import { parseSnapshots, type Point } from "./lib/frames";
import { delayTrendSpec, delayedByLineSpec, ROWS } from "./specs";

const DEFAULT_REFRESH_S = 60;
const HISTORY_MINUTES = [30, 60, 180] as const;
const HISTORY_LABELS: Record<string, string> = { "6h": "Last 6 hours", "24h": "Last 24 hours", "7d": "Last 7 days" };
const LAYERS: { mode: Mode; label: string }[] = [
  { mode: "trains", label: "CTA trains" },
  { mode: "buses", label: "CTA buses" },
  { mode: "metra", label: "Metra" },
];

/** Round up to a multiple of 5 so the axis doesn't change (and the chart re-embed) on every refresh. */
const axisTop = (max: number) => Math.max(5, Math.ceil((max * 1.2) / 5) * 5);

export function App() {
  const meta = usePolling(getMeta, 3600, "meta").data;
  const refreshS = meta?.refresh_s ?? DEFAULT_REFRESH_S;

  const [minutes, setMinutes] = useState<(typeof HISTORY_MINUTES)[number]>(60);
  const [window, setWindow] = useState("24h");
  const [show, setShow] = useState<Record<Mode, boolean>>({ trains: true, buses: true, metra: true });

  const summary = usePolling(getSummary, refreshS, "summary");
  const positions = usePolling((signal) => getPositions(minutes, signal), refreshS, `positions-${minutes}`);
  const history = usePolling((signal) => getDelayHistory(window, signal), 300, `history-${window}`);

  const snaps = useMemo(
    () => (meta && positions.data ? parseSnapshots(positions.data, meta) : []),
    [meta, positions.data],
  );

  const mapRef = useRef<MapHandle>(null);
  const showRef = useRef(show);
  showRef.current = show;
  const onFrame = useCallback((points: Point[]) => {
    const visible = showRef.current;
    mapRef.current?.setPoints(points.filter((p) => visible[p.base.key.split(":", 1)[0] as Mode]));
  }, []);
  const playback = usePlayback(snaps, onFrame);
  useEffect(() => playback.redraw(), [show, playback.redraw]);

  const s = summary.data;
  return (
    <main>
      <header>
        <h1>Chicago Transit Live</h1>
        <Freshness summary={s} refreshS={refreshS} failed={!!summary.error} />
      </header>

      {s && <Kpis kpis={s.kpis} />}

      <section className="card">
        <div className="card-head">
          <h2>Vehicles</h2>
          <div className="layers">
            {LAYERS.map(({ mode, label }) => (
              <label key={mode}>
                <input
                  type="checkbox"
                  checked={show[mode]}
                  onChange={(e) => setShow((cur) => ({ ...cur, [mode]: e.target.checked }))}
                />
                {label}
              </label>
            ))}
            <label>
              Replay window
              <select value={minutes} onChange={(e) => setMinutes(Number(e.target.value) as typeof minutes)}>
                {HISTORY_MINUTES.map((m) => (
                  <option key={m} value={m}>
                    {m < 60 ? `${m} min` : `${m / 60} h`}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <MapView ref={mapRef} />
        <PlaybackBar pb={playback} disabled={snaps.length === 0} />
        {meta && <Legend meta={meta} />}
        {positions.error && <p className="note">Couldn’t load vehicle positions: {positions.error.message}</p>}
      </section>

      <div className="grid-2">
        <section className="card">
          <h2>Trains delayed, by line (now)</h2>
          {!s || s.trains_by_line.length === 0 ? (
            <p className="note">No train data.</p>
          ) : (
            <DelayedByLine rows={s.trains_by_line} />
          )}
        </section>
        <section className="card">
          <h2>Buses delayed, worst routes (now)</h2>
          {!s || s.buses_by_route.length === 0 ? (
            <p className="note">No bus data.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Route</th>
                  <th>Running</th>
                  <th>Delayed</th>
                  <th>% delayed</th>
                </tr>
              </thead>
              <tbody>
                {s.buses_by_route.map((r) => (
                  <tr key={r.route}>
                    <td>{r.route}</td>
                    <td>{r.vehicles}</td>
                    <td>{r.delayed}</td>
                    <td>{r.delayed_pct.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Train delays over time</h2>
          <label>
            History window
            <select value={window} onChange={(e) => setWindow(e.target.value)}>
              {(meta?.history_windows ?? [window]).map((w) => (
                <option key={w} value={w}>
                  {HISTORY_LABELS[w] ?? w}
                </option>
              ))}
            </select>
          </label>
        </div>
        {meta && history.data && history.data.length > 0 ? (
          <Trend meta={meta} rows={history.data} />
        ) : (
          <p className="note">{history.loading ? "Loading…" : "No history yet. Points appear as the ETL job accumulates runs."}</p>
        )}
      </section>
    </main>
  );
}

function Freshness({ summary, refreshS, failed }: { summary: Summary | undefined; refreshS: number; failed: boolean }) {
  if (failed && !summary) return <p className="banner warn">Couldn’t reach the API.</p>;
  if (!summary) return <p className="muted">Loading…</p>;
  if (!summary.updated_at) return <p className="banner warn">No recent data in BigQuery. Has the ETL job run?</p>;
  const local = new Date(summary.updated_at).toLocaleString("en-US", {
    timeZone: "America/Chicago",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
  const text = `Data as of ${local} (${Math.round(summary.age_minutes ?? 0)} min ago). Refreshes every ${refreshS}s.`;
  return summary.stale ? (
    <p className="banner warn">{text} The ETL job may be stalled.</p>
  ) : (
    <p className="muted">{text}</p>
  );
}

function DelayedByLine({ rows }: { rows: GroupDelay[] }) {
  const top = axisTop(Math.max(...rows.map((r) => r.delayed_pct)));
  const n = rows.length;
  const spec = useMemo(() => delayedByLineSpec(top, n), [top, n]);
  const data = useMemo(() => ({ [ROWS]: rows }), [rows]);
  return <VegaChart spec={spec} data={data} />;
}

function Trend({ meta, rows }: { meta: Meta; rows: HistoryRow[] }) {
  const top = axisTop(Math.max(...rows.map((r) => r.delayed_pct)));
  const spec = useMemo(() => delayTrendSpec(meta.line_colors, top), [meta, top]);
  const data = useMemo(() => ({ [ROWS]: rows }), [rows]);
  return <VegaChart spec={spec} data={data} />;
}

function Legend({ meta }: { meta: Meta }) {
  return (
    <ul className="legend" aria-label="Legend">
      {Object.entries(meta.line_colors).map(([name, color]) => (
        <li key={name}>
          <i style={{ background: color }} />
          {name.replace(" Line", "")}
        </li>
      ))}
      <li>
        <i style={{ background: meta.bus_color }} />
        Bus
      </li>
      <li>
        <i style={{ background: meta.metra_color }} />
        Metra
      </li>
      <li>
        <i className="ring" />
        Delayed
      </li>
    </ul>
  );
}
