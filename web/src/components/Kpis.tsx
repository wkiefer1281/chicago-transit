import type { Summary } from "../api";
import { useAnimatedNumber } from "../hooks/useAnimatedNumber";

interface KpiProps {
  label: string;
  /** null shows a dash: there is nothing to report. */
  value: number | null;
  decimals?: number;
  suffix?: string;
  note?: string;
}

function Kpi({ label, value, decimals = 0, suffix = "", note }: KpiProps) {
  const shown = useAnimatedNumber(value ?? 0);
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value === null ? "—" : `${shown.toFixed(decimals)}${suffix}`}</div>
      {note && <div className="kpi-note">{note}</div>}
    </div>
  );
}

export function Kpis({ kpis }: { kpis: Summary["kpis"] }) {
  return (
    <section className="kpis" aria-label="Key figures">
      <Kpi label="Trains running" value={kpis.trains} />
      <Kpi label="Trains delayed" value={kpis.trains_delayed_pct} decimals={1} suffix="%" />
      <Kpi label="Buses running" value={kpis.buses} />
      <Kpi label="Buses delayed" value={kpis.buses_delayed_pct} decimals={1} suffix="%" />
      <Kpi label="Metra trains" value={kpis.metra} />
      <Kpi
        label="Metra delayed"
        value={kpis.metra_delayed_pct}
        decimals={1}
        suffix="%"
        note={`of ${kpis.metra_tracked} with a prediction`}
      />
    </section>
  );
}
