"use client";

import { Tile } from "./Tile";

type BoardState = {
  round_label: string;
  turn: number;
  hero_seat: number;
  hero_hand: string[];
  discards: string[][];
  open_melds: string[][][];
  riichi_turns: (number | null)[];
  dora_indicators: string[];
  threats: { player: number; kind: string; declared_turn: number }[];
};

const SEAT_NAME = ["東", "南", "西", "北"];

const THREAT_LABEL: Record<string, { text: string; cls: string }> = {
  riichi: { text: "立直", cls: "bg-yellow-500 text-black" },
  dama_tenpai: { text: "默聽嫌疑", cls: "bg-orange-500 text-white" },
  iishanten: { text: "一向聽", cls: "bg-purple-500 text-white" },
};

const YAKUHAI_LABEL: Record<string, string> = {
  "5z": "白",
  "6z": "發",
  "7z": "中",
  "1z": "東",
  "2z": "南",
  "3z": "西",
  "4z": "北",
};

function YakuhaiBadges({ melds }: { melds: string[][] }) {
  const yakuhaiTags: string[] = [];
  for (const meld of melds) {
    if (meld.length < 3) continue;
    const tile = meld[0];
    const counts = meld.filter((t) => t === tile).length;
    if (counts >= 3 && YAKUHAI_LABEL[tile]) {
      yakuhaiTags.push(YAKUHAI_LABEL[tile]);
    }
  }
  if (!yakuhaiTags.length) return null;
  return (
    <span className="ml-1 inline-flex gap-1">
      {yakuhaiTags.map((tag, i) => (
        <span
          key={i}
          className="px-1 py-0.5 rounded text-[9px] bg-amber-500 text-black font-bold"
          title="副露役牌 (已確定有役)"
        >
          {tag}役
        </span>
      ))}
    </span>
  );
}

function DiscardPile({
  tiles,
  melds,
  riichiTurn,
  threatKind,
  label,
  isHero,
}: {
  tiles: string[];
  melds: string[][];
  riichiTurn: number | null;
  threatKind: string | null;
  label: string;
  isHero: boolean;
}) {
  const isThreat = !!threatKind;
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
      <div className="flex items-center justify-between text-[10px] mb-1 flex-wrap gap-1">
        <div className="flex items-center">
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
          <YakuhaiBadges melds={melds} />
        </div>
        <div className="flex gap-1">
          {riichiTurn !== null && (
            <span className="px-1.5 py-0.5 rounded text-[9px] bg-yellow-500 text-black font-bold">
              立直 (T{riichiTurn})
            </span>
          )}
          {threatKind && riichiTurn === null && (
            <span
              className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${THREAT_LABEL[threatKind]?.cls ?? "bg-stone-600 text-white"}`}
            >
              {THREAT_LABEL[threatKind]?.text ?? threatKind}
            </span>
          )}
        </div>
      </div>
      {melds.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-1 p-1 bg-stone-950 rounded">
          <span className="text-[9px] text-stone-500 self-center">副露:</span>
          {melds.map((meld, mi) => (
            <div key={mi} className="flex gap-0.5">
              {meld.map((t, ti) => (
                <Tile key={ti} notation={t} size="sm" />
              ))}
            </div>
          ))}
        </div>
      )}
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
  const threatKindBySeat = new Map<number, string>(
    board.threats.map((t) => [t.player, t.kind])
  );
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
            melds={board.open_melds[seat] ?? []}
            riichiTurn={board.riichi_turns[seat]}
            threatKind={threatKindBySeat.get(seat) ?? null}
            label={`${SEAT_NAME[seat]} (座 ${seat})${seat === board.hero_seat ? " — 你" : ""}`}
            isHero={seat === board.hero_seat}
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
