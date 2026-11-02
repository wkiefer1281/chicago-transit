/** Honor the OS "reduce motion" setting: animations should snap instead of glide. */
export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
