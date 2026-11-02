import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "../lib/motion";

/** Eases a displayed number toward `target` whenever it changes. */
export function useAnimatedNumber(target: number, ms = 600): number {
  const [value, setValue] = useState(target);
  const from = useRef(target);

  useEffect(() => {
    const begin = performance.now();
    const start = from.current;
    let raf = 0;
    const step = (now: number) => {
      const p = prefersReducedMotion() ? 1 : Math.min(1, (now - begin) / ms);
      const eased = 1 - Math.pow(1 - p, 3);
      from.current = start + (target - start) * eased;
      setValue(from.current);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);

  return value;
}
