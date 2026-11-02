import { useEffect, useRef, useState } from "react";

export interface Polled<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
}

/**
 * Calls `load` now and every `intervalS` seconds while the tab is visible.
 * The last good value is kept when a refresh fails. Re-runs when `key` changes.
 */
export function usePolling<T>(
  load: (signal: AbortSignal) => Promise<T>,
  intervalS: number,
  key: string,
): Polled<T> {
  const [state, setState] = useState<Polled<T>>({ data: undefined, error: undefined, loading: true });
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller = new AbortController();
    let stopped = false;
    setState((s) => ({ ...s, loading: true }));

    const tick = async () => {
      if (stopped) return;
      if (document.hidden) {
        timer = setTimeout(tick, 1000);
        return;
      }
      controller = new AbortController();
      try {
        const data = await loadRef.current(controller.signal);
        if (!stopped) setState({ data, error: undefined, loading: false });
      } catch (err) {
        if (!stopped && !controller.signal.aborted) {
          setState((s) => ({ data: s.data, error: err as Error, loading: false }));
        }
      }
      if (!stopped) timer = setTimeout(tick, intervalS * 1000);
    };
    tick();

    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [intervalS, key]);

  return state;
}
