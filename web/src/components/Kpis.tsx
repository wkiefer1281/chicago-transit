import type { Summary } from "../api";
import { useAnimatedNumber } from "../hooks/useAnimatedNumber";

function Kpi({ label, value, decimals = 0, suffix = "" }: { label: string; value: number; decimals?: number; suffix?: string }) {
  const shown = useAnimatedNumber(value);
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {shown.toFixed(decimals)}
        {suffix}
      </div>
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
    </section>
  );
}
