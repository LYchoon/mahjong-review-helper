"use client";

import { useEffect, useState } from "react";

import {
  reviewManual,
  reviewTenhou,
  type DecisionReview,
  type GameSummary,
} from "@/lib/api";
import { DecisionNavigator } from "./components/DecisionNavigator";
import { GameSummaryCard } from "./components/GameSummary";
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
  const [threatKind, setThreatKind] = useState<"riichi" | "dama_tenpai" | "iishanten">(
    "riichi"
  );
  const [threatDiscards, setThreatDiscards] = useState(
    SAMPLE.threats[0].discards.join(" ")
  );
  const [threatAfter, setThreatAfter] = useState(
    SAMPLE.threats[0].discards_after_threat.join(" ")
  );
  const [visibleExtra, setVisibleExtra] = useState(SAMPLE.visible_tiles ?? "");
  const [doraCount, setDoraCount] = useState(0);
  const [isDealer, setIsDealer] = useState(false);

  const [manualResult, setManualResult] = useState<DecisionReview | null>(null);

  // tenhou state
  const [logJson, setLogJson] = useState("");
  const [heroSeat, setHeroSeat] = useState(0);
  const [tenhouDecisions, setTenhouDecisions] = useState<DecisionReview[]>([]);
  const [tenhouSummary, setTenhouSummary] = useState<GameSummary | null>(null);
  const [decisionIdx, setDecisionIdx] = useState(0);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
        is_dealer: isDealer,
        turns_remaining: Math.max(1, 18 - turn),
        visible_tiles: visibleExtra,
        threats: [
          {
            player: threatPlayer,
            kind: threatKind,
            declared_turn: threatTurn,
            discards: parseTilesString(threatDiscards),
            discards_after_threat: parseTilesString(threatAfter),
          },
        ],
      });
      setManualResult(r);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      setManualResult(null);
    } finally {
      setBusy(false);
    }
  }

  async function runTenhou(logText?: string) {
    setBusy(true);
    setErr(null);
    try {
      const text = logText ?? logJson;
      const parsed = JSON.parse(text);
      const r = await reviewTenhou(parsed, heroSeat);
      setTenhouDecisions(r.decisions);
      setTenhouSummary(r.summary);
      setDecisionIdx(0);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      setTenhouDecisions([]);
      setTenhouSummary(null);
    } finally {
      setBusy(false);
    }
  }

  async function loadSample() {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch("/sample/riichi_defense_demo.json");
      if (!r.ok) throw new Error(`fetch sample failed: ${r.status}`);
      const text = await r.text();
      setLogJson(text);
      await runTenhou(text);
    } catch (e: unknown) {
      // network fetch may fail in static export; fall back to embedded sample
      setErr(
        "找不到範例檔 (可能後端未啟動或 public/ 未提供)；請手動貼入牌譜 JSON。"
      );
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
        <>
          <div className="space-y-3 bg-stone-800 rounded-lg p-4 mb-4">
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

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
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
              <Field label="威脅類型">
                <select
                  value={threatKind}
                  onChange={(e) =>
                    setThreatKind(e.target.value as typeof threatKind)
                  }
                  className={inputCls}
                >
                  <option value="riichi">立直</option>
                  <option value="dama_tenpai">默聽</option>
                  <option value="iishanten">一向聽</option>
                </select>
              </Field>
            </div>

            <Field label="威脅者立直 / 聽牌巡目">
              <input
                type="number"
                value={threatTurn}
                onChange={(e) => setThreatTurn(Number(e.target.value))}
                className={inputCls}
              />
            </Field>

            <Field label="威脅者全部河牌 (含立直前後，空白分隔)">
              <input
                value={threatDiscards}
                onChange={(e) => setThreatDiscards(e.target.value)}
                className={inputCls}
                placeholder="1z 9p 2s"
              />
            </Field>

            <Field label="威脅者立直/聽牌後的河牌">
              <input
                value={threatAfter}
                onChange={(e) => setThreatAfter(e.target.value)}
                className={inputCls}
                placeholder="1z"
              />
            </Field>

            <Field label="其他可見牌 (其他家的河 + 寶牌指示)">
              <input
                value={visibleExtra}
                onChange={(e) => setVisibleExtra(e.target.value)}
                className={inputCls}
                placeholder="9p 2s"
              />
            </Field>

            <label className="flex items-center gap-2 text-xs text-stone-400">
              <input
                type="checkbox"
                checked={isDealer}
                onChange={(e) => setIsDealer(e.target.checked)}
              />
              我是親家 (莊)
            </label>

            <button
              onClick={runManual}
              disabled={busy}
              className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded font-semibold"
            >
              {busy ? "分析中…" : "分析這手牌"}
            </button>
          </div>

          {err && <ErrorBox message={err} />}
          {manualResult && <ReviewCard review={manualResult} />}
        </>
      ) : (
        <>
          <div className="space-y-3 bg-stone-800 rounded-lg p-4 mb-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-stone-300">
                天鳳 JSON 牌譜 (整個對局)
              </span>
              <button
                onClick={loadSample}
                disabled={busy}
                className="text-xs text-emerald-400 hover:text-emerald-300 underline disabled:opacity-50"
              >
                載入範例牌譜
              </button>
            </div>
            <textarea
              value={logJson}
              onChange={(e) => setLogJson(e.target.value)}
              rows={8}
              className={`${inputCls} font-mono text-xs`}
              placeholder='{"title": [...], "log": [...]}'
            />
            <Field label="你的座位 (0=東家, 1=南家, 2=西家, 3=北家)">
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
              onClick={() => runTenhou()}
              disabled={busy || !logJson.trim()}
              className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded font-semibold"
            >
              {busy ? "分析中…" : "解析並逐手點評"}
            </button>
            <p className="text-xs text-stone-500">
              MVP 解析器處理標準摸打與多數鳴牌情境。雀魂牌譜請先轉成天鳳格式。
            </p>
          </div>

          {err && <ErrorBox message={err} />}
          {tenhouSummary && (
            <GameSummaryCard
              summary={tenhouSummary}
              onJumpToWorst={
                tenhouSummary.biggest_blunder_index !== null
                  ? () => setDecisionIdx(tenhouSummary.biggest_blunder_index!)
                  : undefined
              }
            />
          )}
          {tenhouDecisions.length > 0 && (
            <DecisionNavigator
              decisions={tenhouDecisions}
              index={decisionIdx}
              onIndexChange={setDecisionIdx}
            />
          )}
        </>
      )}

      {tab === "manual" && !busy && !manualResult && !err && (
        <p className="text-sm text-stone-500 text-center mt-8">
          預設範例已填好，按下「分析這手牌」即可看效果。
        </p>
      )}
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

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="mb-4 bg-red-900/40 border border-red-700 text-red-200 p-3 rounded text-sm">
      {message}
    </div>
  );
}
