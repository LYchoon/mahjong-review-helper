"use client";

import { Tile } from "./Tile";

type BoardState = {
  round_label: string;
  turn: number;
  hero_seat: number;
  hero_hand: string[];
  discards: string[][];
  riichi_turns: (number | null)[];
  dora_indicators: string[];
  threats: { player: number; kind: string; declared_turn: number }[];
};

const SEAT_NAME = ["東", "南", "西", "北"];

function DiscardPile({
  tiles,
  riichiTurn,
  label,
  isHero,
  isThreat,
}: {
  tiles: string[];
  riichiTurn: number | null;
  label: string;
  isHero: boolean;
  isThreat: boolean;
}) {
  return (
    <div
      className={`p-2 rounded ${
        isHero
          ? "bg-emerald-950/50 border border-emerald-700"
          : isThreat
            ? "bg-red-950/50 border border-red-700"
            : "bg-stone-900 border border-stone-700"
      }`}
    >
      <div className="flex items-center justify-between text-[10px] mb-1">
        <span
          className={
            isHero
              ? "text-emerald-300 font-bold"
              : isThreat
                ? "text-red-300 font-bold"
                : "text-stone-400"
          }
        >
          {label}
        </span>
        {riichiTurn !== null && (
          <span className="text-yellow-300 font-bold">
            立直 (T{riichiTurn})
          </span>
        )}
      </div>
      <div className="grid grid-cols-6 gap-0.5 min-h-[60px]">
        {tiles.map((t, i) => {
          const afterRiichi =
            riichiTurn !== null && i >= riichiTurn - 1;
          return (
            <div key={i} className={afterRiichi ? "ring-1 ring-yellow-400 rounded-sm" : ""}>
              <Tile notation={t} size="sm" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function BoardStateView({ board }: { board: BoardState }) {
  const threatSet = new Set(board.threats.map((t) => t.player));
  return (
    <div className="bg-stone-800 rounded-lg p-4 mb-3">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="text-sm font-semibold text-stone-200">
          {board.round_label} · 第 {board.turn} 巡
        </div>
        <div className="flex items-center gap-2 text-xs text-stone-400">
          <span>寶牌指示:</span>
          <div className="flex gap-0.5">
            {board.dora_indicators.map((t, i) => (
              <Tile key={i} notation={t} size="sm" />
            ))}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-2 mb-3">
        {[0, 1, 2, 3].map((seat) => (
          <DiscardPile
            key={seat}
            tiles={board.discards[seat] ?? []}
            riichiTurn={board.riichi_turns[seat]}
            label={`${SEAT_NAME[seat]} (座 ${seat})${seat === board.hero_seat ? " — 你" : ""}`}
            isHero={seat === board.hero_seat}
            isThreat={threatSet.has(seat)}
          />
        ))}
      </div>

      <div className="bg-stone-900 rounded p-2 border border-stone-700">
        <div className="text-[10px] text-stone-400 mb-1">你的手牌 (打牌前)</div>
        <div className="flex flex-wrap gap-1">
          {board.hero_hand.map((t, i) => (
            <Tile key={i} notation={t} size="sm" />
          ))}
        </div>
      </div>
    </div>
  );
}
