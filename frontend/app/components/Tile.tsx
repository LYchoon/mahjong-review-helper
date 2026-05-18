"use client";

const SUIT_LABEL: Record<string, string> = {
  m: "萬",
  p: "筒",
  s: "索",
};
const HONOR_LABEL: Record<string, string> = {
  "1z": "東",
  "2z": "南",
  "3z": "西",
  "4z": "北",
  "5z": "白",
  "6z": "發",
  "7z": "中",
};

export function Tile({
  notation,
  size = "md",
  highlight,
  onClick,
}: {
  notation: string;
  size?: "sm" | "md" | "lg";
  highlight?: "danger" | "safe" | "chosen" | "recommend";
  onClick?: () => void;
}) {
  const rank = notation[0];
  const suit = notation[1];
  const isHonor = suit === "z";
  const isRed = rank === "0";
  const label = isHonor ? HONOR_LABEL[notation] ?? "?" : `${isRed ? "5" : rank}`;
  const suitLabel = isHonor ? "" : SUIT_LABEL[suit] ?? "";

  const sizeClass = {
    sm: "w-7 h-10 text-[10px]",
    md: "w-10 h-14 text-xs",
    lg: "w-14 h-20 text-sm",
  }[size];

  const highlightClass =
    highlight === "danger"
      ? "ring-2 ring-blunder"
      : highlight === "safe"
        ? "ring-2 ring-best"
        : highlight === "chosen"
          ? "ring-2 ring-mistake"
          : highlight === "recommend"
            ? "ring-2 ring-good"
            : "";

  const rankColor = isRed ? "text-red-500" : "text-gray-900";
  const clickableClass = onClick
    ? "cursor-pointer hover:scale-105 transition-transform"
    : "";

  const inner = (
    <>
      <span className={`font-bold ${rankColor} leading-tight`}>{label}</span>
      {suitLabel && (
        <span className="text-stone-700 leading-tight text-[0.8em]">
          {suitLabel}
        </span>
      )}
    </>
  );

  const className = `${sizeClass} ${highlightClass} ${clickableClass} bg-stone-100 rounded-md flex flex-col items-center justify-center shadow-sm border border-stone-300 select-none`;

  if (onClick) {
    return (
      <button onClick={onClick} className={className} title={notation} type="button">
        {inner}
      </button>
    );
  }
  return (
    <div className={className} title={notation}>
      {inner}
    </div>
  );
}
