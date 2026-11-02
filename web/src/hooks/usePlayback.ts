import { useCallback, useEffect, useRef, useState } from "react";
import { frameAt, type Point, type Snapshot } from "../lib/frames";
import { prefersReducedMotion } from "../lib/motion";

export const SPEEDS = [30, 60, 120, 300] as const;
export type Speed = (typeof SPEEDS)[number];

/** How long vehicles take to glide to the newest snapshot when it arrives in live mode. */
const LIVE_GLIDE_MS = 2500;
const glideMs = () => (prefersReducedMotion() ? 1 : LIVE_GLIDE_MS);
const FRAME_MS = 1000 / 30;
const UI_MS = 200;

export interface Playback {
  live: boolean;
  playing: boolean;
  speed: Speed;
  /** Playhead (epoch ms) for display; updates ~5x/s, not every frame. */
  time: number;
  start: number;
  end: number;
  play(): void;
  pause(): void;
  seek(t: number): void;
  goLive(): void;
  /** Re-emit the current frame (e.g. after the caller changed what it filters out). */
  redraw(): void;
  setSpeed(s: Speed): void;
}

/**
 * Drives the animation clock. Live mode sits on the newest snapshot and glides there whenever a
 * new one arrives; replay mode advances the playhead at `speed` simulated seconds per real second.
 * Frames go to `onFrame` straight from requestAnimationFrame, bypassing React rendering.
 */
export function usePlayback(snaps: Snapshot[], onFrame: (points: Point[]) => void): Playback {
  const start = snaps[0]?.t ?? 0;
  const end = snaps[snaps.length - 1]?.t ?? 0;

  const [ui, setUi] = useState({ live: true, playing: false, speed: 60 as Speed, time: end });
  const s = useRef({ playhead: end, live: true, playing: false, speed: 60 as Speed, glideRate: 0, dirty: true });
  const snapsRef = useRef(snaps);
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  // New data: in live mode, glide from where we are to the newest snapshot.
  useEffect(() => {
    const prevEnd = snapsRef.current[snapsRef.current.length - 1]?.t ?? 0;
    snapsRef.current = snaps;
    const cur = s.current;
    if (cur.live) {
      if (prevEnd === 0) cur.playhead = end; // first data: no glide, just appear
      cur.glideRate = Math.max(0, end - cur.playhead) / glideMs();
    } else if (cur.playhead < start) {
      cur.playhead = start; // replay window slid past the playhead
    }
    cur.dirty = true;
  }, [snaps, start, end]);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let lastFrame = 0;
    let lastUi = 0;

    const loop = (now: number) => {
      const dt = Math.min(now - last, 250); // a background tab shouldn't fast-forward the replay
      last = now;
      const cur = s.current;
      const last_t = snapsRef.current[snapsRef.current.length - 1]?.t ?? 0;

      let next = cur.playhead;
      if (cur.live) {
        next = Math.min(last_t, cur.playhead + dt * cur.glideRate);
      } else if (cur.playing) {
        next = cur.playhead + dt * cur.speed;
        if (next >= last_t) {
          next = last_t;
          cur.playing = false;
        }
      }
      if (next !== cur.playhead) cur.dirty = true;
      cur.playhead = next;

      if (cur.dirty && now - lastFrame >= FRAME_MS) {
        cur.dirty = false;
        lastFrame = now;
        onFrameRef.current(frameAt(snapsRef.current, cur.playhead));
      }
      if (now - lastUi >= UI_MS) {
        lastUi = now;
        setUi((u) =>
          u.time === cur.playhead && u.playing === cur.playing && u.live === cur.live
            ? u
            : { ...u, time: cur.playhead, playing: cur.playing, live: cur.live },
        );
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  const sync = () => setUi((u) => ({ ...u, live: s.current.live, playing: s.current.playing, time: s.current.playhead, speed: s.current.speed }));

  const play = useCallback(() => {
    const cur = s.current;
    cur.live = false;
    if (cur.playhead >= (snapsRef.current[snapsRef.current.length - 1]?.t ?? 0)) {
      cur.playhead = snapsRef.current[0]?.t ?? 0; // replay from the beginning
    }
    cur.playing = true;
    cur.dirty = true;
    sync();
  }, []);
  const pause = useCallback(() => {
    s.current.playing = false;
    sync();
  }, []);
  const seek = useCallback((t: number) => {
    const cur = s.current;
    cur.live = false;
    cur.playing = false;
    cur.playhead = t;
    cur.dirty = true;
    sync();
  }, []);
  const goLive = useCallback(() => {
    const cur = s.current;
    cur.live = true;
    cur.playing = false;
    cur.glideRate = Math.max(0, (snapsRef.current[snapsRef.current.length - 1]?.t ?? 0) - cur.playhead) / glideMs();
    cur.dirty = true;
    sync();
  }, []);
  const redraw = useCallback(() => {
    s.current.dirty = true;
  }, []);
  const setSpeed = useCallback((speed: Speed) => {
    s.current.speed = speed;
    sync();
  }, []);

  return { ...ui, start, end, play, pause, seek, goLive, redraw, setSpeed };
}
