"use client";

import { useEffect, useState } from "react";

import { reviewManual, type DecisionReview } from "@/lib/api";
import { parseTilesString } from "@/lib/tiles";
import { ErrorBox, Field, inputCls } from "./forms";
import { ReviewCard } from "./ReviewCard";
import { Tile } from "./Tile";

const STORAGE_KEY = "mahjong-review-manual-form-v1";

type ManualFormState = {
  hand: string;
  chosen: string;
  turn: number;
  threatPlayer: number;
  threatTurn: number;
  threatKind: "riichi" | "dama_tenpai" | "iishanten";
  threatDiscards: string;
  threatAfter: string;
  visibleExtra: string;
  doraCount: number;
  isDealer: boolean;
};

const DEFAULT_FORM: ManualFormState = {
  hand: "123m 5m 456p 789s 11z 1z",
  chosen: "5m",
  turn: 6,
  threatPlayer: 1,
  threatTurn: 5,
  threatKind: "riichi",
  threatDiscards: "1z 9p 2s",
  threatAfter: "1z",
  visibleExtra: "9p 2s",
  doraCount: 0,
  isDealer: false,
};

function loadStored<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function ManualTab() {
  const [hand, setHand] = useState(DEFAULT_FORM.hand);
  const [chosen, setChosen] = useState(DEFAULT_FORM.chosen);
  const [turn, setTurn] = useState(DEFAULT_FORM.turn);
  const [threatPlayer, setThreatPlayer] = useState(DEFAULT_FORM.threatPlayer);
  const [threatTurn, setThreatTurn] = useState(DEFAULT_FORM.threatTurn);
  const [threatKind, setThreatKind] = useState<ManualFormState["threatKind"]>(
    DEFAULT_FORM.threatKind
  );
  const [threatDiscards, setThreatDiscards] = useState(DEFAULT_FORM.threatDiscards);
  const [threatAfter, setThreatAfter] = useState(DEFAULT_FORM.threatAfter);
  const [visibleExtra, setVisibleExtra] = useState(DEFAULT_FORM.visibleExtra);
  const [doraCount, setDoraCount] = useState(DEFAULT_FORM.doraCount);
  const [isDealer, setIsDealer] = useState(DEFAULT_FORM.isDealer);

  const [result, setResult] = useState<DecisionReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // hydrate from localStorage once on mount
  useEffect(() => {
    const stored = loadStored<Partial<ManualFormState>>(STORAGE_KEY, {});
    if (stored.hand !== undefined) setHand(stored.hand);
    if (stored.chosen !== undefined) setChosen(stored.chosen);
    if (stored.turn !== undefined) setTurn(stored.turn);
    if (stored.threatPlayer !== undefined) setThreatPlayer(stored.threatPlayer);
    if (stored.threatTurn !== undefined) setThreatTurn(stored.threatTurn);
    if (stored.threatKind !== undefined) setThreatKind(stored.threatKind);
    if (stored.threatDiscards !== undefined) setThreatDiscards(stored.threatDiscards);
    if (stored.threatAfter !== undefined) setThreatAfter(stored.threatAfter);
    if (stored.visibleExtra !== undefined) setVisibleExtra(stored.visibleExtra);
    if (stored.doraCount !== undefined) setDoraCount(stored.doraCount);
    if (stored.isDealer !== undefined) setIsDealer(stored.isDealer);
  }, []);

  // persist on change
  useEffect(() => {
    const state: ManualFormState = {
      hand,
      chosen,
      turn,
      threatPlayer,
      threatTurn,
      threatKind,
      threatDiscards,
      threatAfter,
      visibleExtra,
      doraCount,
      isDealer,
    };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // localStorage may be unavailable; ignore
    }
  }, [
    hand,
    chosen,
    turn,
    threatPlayer,
    threatTurn,
    threatKind,
    threatDiscards,
    threatAfter,
    visibleExtra,
    doraCount,
    isDealer,
  ]);

  async function run() {
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
      setResult(r);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const handTiles = parseTilesString(hand);

  return (
    <>
      <div className="space-y-3 bg-stone-800 rounded-lg p-4 mb-4">
        <Field label="手牌 (14 張) — 點擊牌選擇要打的">
          <input
            value={hand}
            onChange={(e) => setHand(e.target.value)}
            className={inputCls}
            placeholder="123m 456p 789s 11z 1z"
          />
          <div className="flex flex-wrap gap-1 mt-2">
            {handTiles.map((t, i) => (
              <Tile
                key={`${t}-${i}`}
                notation={t}
                size="sm"
                highlight={t === chosen ? "chosen" : undefined}
                onClick={() => setChosen(t)}
              />
            ))}
          </div>
          <div className="text-xs text-stone-400 mt-1">
            目前選擇打:{" "}
            <span className="font-mono text-mistake">{chosen || "(無)"}</span>
            {" — "}
            <button
              onClick={() => setChosen("")}
              className="text-stone-500 hover:text-stone-300 underline"
              type="button"
            >
              或手動輸入
            </button>
          </div>
        </Field>

        {!handTiles.includes(chosen) && (
          <Field label="你打出的牌 (手動輸入)">
            <input
              value={chosen}
              onChange={(e) => setChosen(e.target.value)}
              className={inputCls}
              placeholder="5m"
            />
          </Field>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <Field label="現在巡目">
            <input
              type="number"
              min={1}
              max={22}
              value={turn}
              onChange={(e) => setTurn(Number(e.target.value))}
              className={inputCls}
            />
          </Field>
          <Field label="自手寶牌數">
            <input
              type="number"
              min={0}
              max={13}
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
              onChange={(e) => setThreatKind(e.target.value as typeof threatKind)}
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
            min={1}
            max={22}
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
          onClick={run}
          disabled={busy}
          className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded font-semibold"
        >
          {busy ? "分析中…" : "分析這手牌"}
        </button>
      </div>

      {err && <ErrorBox message={err} />}
      {result && <ReviewCard review={result} />}

      {!busy && !result && !err && (
        <p className="text-sm text-stone-500 text-center mt-8">
          預設範例已填好，按下「分析這手牌」即可看效果。
        </p>
      )}
    </>
  );
}
