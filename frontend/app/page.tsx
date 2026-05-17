"use client";

import { useState } from "react";

import { reviewManual, reviewTenhou, type DecisionReview } from "@/lib/api";
import { ReviewCard } from "./components/ReviewCard";
import { Tile } from "./components/Tile";

const SAMPLE: Parameters<typeof reviewManual>[0] = {
  hand: "123m 5m 456p 789s 11z 1z",
  chosen_discard: "5m",
  turn: 6,
  round_wind_tile: "1z",
  hero_seat: 0,
  dora_count: 0,
  melds_count: 0,
  is_dealer: false,
  turns_remaining: 10,
  visible_tiles: "9p 2s",
  threats: [
    {
      player: 1,
      kind: "riichi",
      declared_turn: 5,
      discards: ["1z", "9p", "2s"],
      discards_after_threat: ["1z"],
    },
  ],
};

function parseTilesString(s: string): string[] {
  // very lenient: split by whitespace, expand suit-suffix groups like "123m"
  const out: string[] = [];
  for (const chunk of s.trim().split(/\s+/).filter(Boolean)) {
    const m = chunk.match(/^([0-9]+)([mpsz])$/i);
    if (m) {
      for (const d of m[1]) out.push(`${d}${m[2].toLowerCase()}`);
    } else {
      out.push(chunk);
    }
  }
  return out;
}

type Tab = "manual" | "tenhou";

export default function Page() {
  const [tab, setTab] = useState<Tab>("manual");

  // manual form state
  const [hand, setHand] = useState(SAMPLE.hand);
  const [chosen, setChosen] = useState(SAMPLE.chosen_discard);
  const [turn, setTurn] = useState(SAMPLE.turn ?? 6);
  const [threatPlayer, setThreatPlayer] = useState(1);
  const [threatTurn, setThreatTurn] = useState(5);
  const [threatDiscards, setThreatDiscards] = useState(
    SAMPLE.threats[0].discards.join(" ")
  );
  const [threatAfter, setThreatAfter] = useState(
    SAMPLE.threats[0].discards_after_threat.join(" ")
  );
  const [visibleExtra, setVisibleExtra] = useState(SAMPLE.visible_tiles ?? "");
  const [doraCount, setDoraCount] = useState(0);

  const [results, setResults] = useState<DecisionReview[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // tenhou
  const [logJson, setLogJson] = useState("");
  const [heroSeat, setHeroSeat] = useState(0);

  async function runManual() {
    setBusy(true);
    setErr(null);
    try {
      const r = await reviewManual({
        hand,
        chosen_discard: chosen,
        turn,
        round_wind_tile: "1z",
        hero_seat: 0,
        dora_count: doraCount,
        melds_count: 0,
        is_dealer: false,
        turns_remaining: Math.max(1, 18 - turn),
        visible_tiles: visibleExtra,
        threats: [
          {
            player: threatPlayer,
            kind: "riichi",
            declared_turn: threatTurn,
            discards: parseTilesString(threatDiscards),
            discards_after_threat: parseTilesString(threatAfter),
          },
        ],
      });
      setResults([r]);
    } catch (e: any) {
      setErr(e.message ?? String(e));
      setResults([]);
    } finally {
      setBusy(false);
    }
  }

  async function runTenhou() {
    setBusy(true);
    setErr(null);
    try {
      const parsed = JSON.parse(logJson);
      const r = await reviewTenhou(parsed, heroSeat);
      setResults(r.decisions);
    } catch (e: any) {
      setErr(e.message ?? String(e));
      setResults([]);
    } finally {
      setBusy(false);
    }
  }

  const handTiles = parseTilesString(hand);

  return (
    <main className="max-w-5xl mx-auto p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold mb-1">麻將復盤助手</h1>
        <p className="text-sm text-stone-400">
          chess.com 風格的逐手點評 — MVP 範圍：押牌 vs betaori 防守判斷
        </p>
      </header>

      <div className="flex gap-2 mb-4 border-b border-stone-700">
        {(
          [
            ["manual", "手動輸入單局"],
            ["tenhou", "上傳天鳳牌譜"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-4 py-2 text-sm ${
              tab === k
                ? "border-b-2 border-emerald-400 text-emerald-300"
                : "text-stone-400 hover:text-stone-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "manual" ? (
        <div className="grid md:grid-cols-[1fr_auto] gap-4 items-start">
          <div className="space-y-3 bg-stone-800 rounded-lg p-4">
            <Field label="手牌 (14 張)">
              <input
                value={hand}
                onChange={(e) => setHand(e.target.value)}
                className={inputCls}
                placeholder="123m 456p 789s 11z 1z"
              />
              <div className="flex flex-wrap gap-1 mt-2">
                {handTiles.map((t, i) => (
                  <Tile
                    key={i}
                    notation={t}
                    size="sm"
                    highlight={t === chosen ? "chosen" : undefined}
                  />
                ))}
              </div>
            </Field>

            <Field label="你打出的牌">
              <input
                value={chosen}
                onChange={(e) => setChosen(e.target.value)}
                className={inputCls}
                placeholder="5m"
              />
            </Field>

            <div className="grid grid-cols-3 gap-2">
              <Field label="現在巡目">
                <input
                  type="number"
                  value={turn}
                  onChange={(e) => setTurn(Number(e.target.value))}
                  className={inputCls}
                />
              </Field>
              <Field label="自手寶牌數">
                <input
                  type="number"
                  value={doraCount}
                  onChange={(e) => setDoraCount(Number(e.target.value))}
                  className={inputCls}
                />
              </Field>
              <Field label="威脅者座位 (1=下家)">
                <input
                  type="number"
                  min={1}
                  max={3}
                  value={threatPlayer}
                  onChange={(e) => setThreatPlayer(Number(e.target.value))}
                  className={inputCls}
                />
              </Field>
            </div>

            <Field label="威脅者立直巡目">
              <input
                type="number"
                value={threatTurn}
                onChange={(e) => setThreatTurn(Number(e.target.value))}
                className={inputCls}
              />
            </Field>

            <Field label="威脅者全部河牌 (立直前 + 後，空白分隔)">
              <input
                value={threatDiscards}
                onChange={(e) => setThreatDiscards(e.target.value)}
                className={inputCls}
                placeholder="1z 9p 2s"
              />
            </Field>

            <Field label="威脅者立直後的河牌">
              <input
                value={threatAfter}
                onChange={(e) => setThreatAfter(e.target.value)}
                className={inputCls}
                placeholder="1z"
              />
            </Field>

            <Field label="其他可見牌 (其他人的河 + 寶牌指示)">
              <input
                value={visibleExtra}
                onChange={(e) => setVisibleExtra(e.target.value)}
                className={inputCls}
                placeholder="9p 2s"
              />
            </Field>

            <button
              onClick={runManual}
              disabled={busy}
              className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded font-semibold"
            >
              {busy ? "分析中…" : "分析這手牌"}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3 bg-stone-800 rounded-lg p-4">
          <Field label="天鳳 JSON 牌譜 (整個對局)">
            <textarea
              value={logJson}
              onChange={(e) => setLogJson(e.target.value)}
              rows={8}
              className={`${inputCls} font-mono text-xs`}
              placeholder='{"title": [...], "log": [...]}'
            />
          </Field>
          <Field label="你的座位 (0=東家)">
            <input
              type="number"
              min={0}
              max={3}
              value={heroSeat}
              onChange={(e) => setHeroSeat(Number(e.target.value))}
              className={inputCls}
            />
          </Field>
          <button
            onClick={runTenhou}
            disabled={busy}
            className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded font-semibold"
          >
            {busy ? "分析中…" : "解析並逐手點評"}
          </button>
          <p className="text-xs text-stone-500">
            注意：MVP 解析器僅處理標準摸打流程，遇到複雜的鳴牌組合可能跳過。雀魂牌譜請先轉成天鳳格式。
          </p>
        </div>
      )}

      {err && (
        <div className="mt-4 bg-red-900/40 border border-red-700 text-red-200 p-3 rounded">
          {err}
        </div>
      )}

      <div className="mt-6 space-y-4">
        {results.map((r, i) => (
          <ReviewCard key={i} review={r} />
        ))}
        {!busy && results.length === 0 && !err && (
          <p className="text-sm text-stone-500 text-center mt-8">
            預設範例已填好，按下「分析這手牌」即可看效果。
          </p>
        )}
      </div>
    </main>
  );
}

const inputCls =
  "w-full bg-stone-900 border border-stone-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs text-stone-400 mb-1">{label}</span>
      {children}
    </label>
  );
}
