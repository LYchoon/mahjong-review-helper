"use client";

import { useState } from "react";

import {
  detectLogFormat,
  reviewMajsoul,
  reviewTenhou,
  type CallReview,
  type DecisionReview,
  type GameSummary,
} from "@/lib/api";
import { CallReviews } from "./CallReviews";
import { DecisionNavigator } from "./DecisionNavigator";
import { ErrorBox, Field, inputCls } from "./forms";
import { GameSummaryCard } from "./GameSummary";

export function LogReviewTab() {
  const [logJson, setLogJson] = useState("");
  const [heroSeat, setHeroSeat] = useState(0);
  const [decisions, setDecisions] = useState<DecisionReview[]>([]);
  const [calls, setCalls] = useState<CallReview[]>([]);
  const [summary, setSummary] = useState<GameSummary | null>(null);
  const [decisionIdx, setDecisionIdx] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(logText?: string) {
    setBusy(true);
    setErr(null);
    try {
      const text = logText ?? logJson;
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch (e) {
        throw new Error(
          `牌譜不是有效的 JSON：${e instanceof Error ? e.message : String(e)}`
        );
      }
      const format = detectLogFormat(parsed);
      if (!format) {
        throw new Error(
          "無法辨識牌譜格式 — 支援天鳳 JSON (含 log 欄位) 與雀魂解碼後的 record JSON。"
        );
      }
      const review = format === "tenhou" ? reviewTenhou : reviewMajsoul;
      const r = await review(parsed, heroSeat);
      setDecisions(r.decisions);
      setCalls(r.calls ?? []);
      setSummary(r.summary);
      setDecisionIdx(0);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      setDecisions([]);
      setCalls([]);
      setSummary(null);
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
      await run(text);
    } catch (e: unknown) {
      setErr(
        e instanceof Error
          ? `載入範例失敗：${e.message}`
          : "載入範例失敗；請手動貼入牌譜 JSON。"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="space-y-3 bg-stone-800 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm text-stone-300">
            牌譜 JSON (天鳳或雀魂，自動辨識格式)
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
          placeholder='天鳳: {"title": [...], "log": [...]} · 雀魂: {"head": {...}, "data": [{"name": ".lq.RecordNewRound", ...}]}'
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
          onClick={() => run()}
          disabled={busy || !logJson.trim()}
          className="w-full mt-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2 rounded font-semibold"
        >
          {busy ? "分析中…" : "解析並逐手點評"}
        </button>
        <p className="text-xs text-stone-500">
          天鳳支援 tenhou.net/6 JSON；雀魂支援工具解碼後的 record JSON
          (mjsoul-paipu-downloader 等)。
        </p>
      </div>

      {err && <ErrorBox message={err} />}
      {summary && (
        <GameSummaryCard
          summary={summary}
          onJumpToWorst={
            summary.biggest_blunder_index !== null
              ? () => setDecisionIdx(summary.biggest_blunder_index!)
              : undefined
          }
        />
      )}
      <CallReviews calls={calls} />
      {decisions.length > 0 && (
        <DecisionNavigator
          decisions={decisions}
          index={decisionIdx}
          onIndexChange={setDecisionIdx}
        />
      )}
    </>
  );
}
