"use client";

import type { CallReview } from "@/lib/api";
import { shantenLabel } from "@/lib/severity";
import { LabelBadge } from "./LabelBadge";
import { Tile } from "./Tile";

const KIND_LABEL: Record<string, string> = { pon: "碰", chi: "吃" };

/** List of reviewed call (pon/chi) decisions: actual calls + missed chances. */
export function CallReviews({ calls }: { calls: CallReview[] }) {
  if (calls.length === 0) return null;
  return (
    <div className="bg-stone-800 rounded-lg p-4 mb-4">
      <div className="text-sm font-semibold text-stone-200 mb-2">
        鳴牌判斷 · {calls.length} 筆
      </div>
      <div className="space-y-2">
        {calls.map((c, i) => {
          const agree =
            (c.actual === "called") === (c.recommended === "call");
          return (
            <div
              key={i}
              className={`rounded p-3 border ${
                agree
                  ? "bg-stone-900 border-stone-700"
                  : "bg-amber-950/30 border-amber-800"
              }`}
            >
              <div className="flex items-center gap-2 flex-wrap text-xs mb-1">
                <span className="text-stone-400">
                  {c.round_label} · 第 {c.turn} 巡
                </span>
                <Tile notation={c.tile} size="sm" />
                <span className="text-stone-300">
                  可{KIND_LABEL[c.kind] ?? c.kind} — 你
                  {c.actual === "called" ? "鳴了" : "沒鳴"} · 建議
                  {c.recommended === "call" ? "鳴" : "過"}
                </span>
                <span className="text-stone-500">
                  ({shantenLabel(c.shanten_before)} →{" "}
                  {shantenLabel(c.shanten_after)})
                </span>
                <LabelBadge label={c.label} />
              </div>
              <ul className="text-xs text-stone-400 space-y-0.5">
                {c.reasons.map((r, ri) => (
                  <li key={ri}>· {r}</li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
