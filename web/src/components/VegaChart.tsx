import { useEffect, useRef } from "react";
import type { TopLevelSpec } from "vega-lite";
import embed, { type Result } from "vega-embed";

interface Props {
  spec: TopLevelSpec;
  /** Named datasets, kept in sync without re-embedding so charts update in place. */
  data: Record<string, object[]>;
  className?: string;
}

export function VegaChart({ spec, data, className }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const result = useRef<Result | null>(null);
  const latest = useRef(data);
  latest.current = data;

  useEffect(() => {
    let cancelled = false;
    // Seed the datasets at embed time so the first render never sees an empty (infinite-extent) domain.
    const seeded = latest.current;
    embed(el.current!, { ...spec, datasets: seeded }, { actions: false, renderer: "canvas" }).then((r) => {
      if (cancelled) return r.finalize();
      result.current = r;
      if (latest.current !== seeded) {
        // Fresher data landed while embedding.
        for (const [name, rows] of Object.entries(latest.current)) r.view.data(name, rows);
        void r.view.runAsync();
      }
    });
    return () => {
      cancelled = true;
      result.current?.finalize();
      result.current = null;
    };
  }, [spec]);

  useEffect(() => {
    const view = result.current?.view;
    if (!view) return;
    for (const [name, rows] of Object.entries(data)) view.data(name, rows);
    void view.runAsync();
  }, [data]);

  return <div ref={el} className={className} />;
}
