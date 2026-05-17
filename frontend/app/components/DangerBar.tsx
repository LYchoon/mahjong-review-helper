"use client";

/** A horizontal bar showing danger score 0..100 with a colour gradient. */
export function DangerBar({
  score,
  height = "h-1.5",
}: {
  score: number;
  height?: string;
}) {
  const clamped = Math.max(0, Math.min(100, score));
  // colour bands: 0=green, 35=yellow, 55=orange, 80=red
  const color =
    clamped <= 15
      ? "bg-best"
      : clamped <= 35
        ? "bg-good"
        : clamped <= 55
          ? "bg-inaccuracy"
          : clamped <= 80
            ? "bg-mistake"
            : "bg-blunder";
  return (
    <div className={`relative bg-stone-700 rounded-full overflow-hidden ${height} w-full`}>
      <div
        className={`absolute top-0 left-0 ${height} ${color} rounded-full transition-all`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

/** EV bar: signed value, centred at 0; negative shows left in red, positive right in green. */
export function EVBar({
  value,
  scale = 8000,
  height = "h-1.5",
}: {
  value: number;
  scale?: number;
  height?: string;
}) {
  const pct = Math.max(-100, Math.min(100, (value / scale) * 100));
  const isNeg = pct < 0;
  const width = Math.abs(pct);
  return (
    <div className={`relative bg-stone-700 rounded-full ${height} w-full overflow-hidden`}>
      <div className="absolute top-0 left-1/2 w-px h-full bg-stone-500 z-10" />
      {isNeg ? (
        <div
          className={`absolute top-0 ${height} bg-blunder rounded-l-full`}
          style={{ right: "50%", width: `${width / 2}%` }}
        />
      ) : (
        <div
          className={`absolute top-0 ${height} bg-best rounded-r-full`}
          style={{ left: "50%", width: `${width / 2}%` }}
        />
      )}
    </div>
  );
}
