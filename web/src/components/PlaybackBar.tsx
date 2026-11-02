import { SPEEDS, type Playback } from "../hooks/usePlayback";

const clock = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/Chicago",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

export function PlaybackBar({ pb, disabled }: { pb: Playback; disabled: boolean }) {
  return (
    <div className="playback">
      <button type="button" className={pb.live ? "btn live on" : "btn live"} onClick={pb.goLive} disabled={disabled}>
        ● Live
      </button>
      <button
        type="button"
        className="btn"
        onClick={pb.playing ? pb.pause : pb.play}
        disabled={disabled}
        aria-label={pb.playing ? "Pause replay" : "Replay"}
      >
        {pb.playing ? "❚❚ Pause" : "▶ Replay"}
      </button>
      <input
        type="range"
        aria-label="Time"
        min={pb.start}
        max={Math.max(pb.end, pb.start + 1)}
        step={1000}
        value={Math.min(Math.max(pb.time, pb.start), pb.end)}
        disabled={disabled}
        onChange={(e) => pb.seek(Number(e.target.value))}
      />
      <span className="clock">{disabled ? "—" : clock.format(pb.time)}</span>
      <label className="speed">
        Speed
        <select value={pb.speed} onChange={(e) => pb.setSpeed(Number(e.target.value) as (typeof SPEEDS)[number])}>
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
