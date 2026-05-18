"use client";

import { useEffect } from "react";

import type { DecisionReview } from "@/lib/api";
import { BoardStateView } from "./BoardState";
import { ReviewCard } from "./ReviewCard";

const LABEL_DOT: Record<DecisionReview["label"], string> = {
  best: "bg-best",
  good: "bg-good",
  inaccuracy: "bg-inaccuracy",
  mistake: "bg-mistake",
  blunder: "bg-blunder",
};

export function DecisionNavigator({
  decisions,
  index,
  onIndexChange,
}: {
  decisions: DecisionReview[];
  index: number;
  onIndexChange: (i: number) => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (e.key === "ArrowLeft" && index > 0) {
        e.preventDefault();
        onIndexChange(index - 1);
      } else if (e.key === "ArrowRight" && index < decisions.length - 1) {
        e.preventDefault();
        onIndexChange(index + 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, decisions.length, onIndexChange]);

  if (decisions.length === 0) return null;
  const current = decisions[index];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 bg-stone-800 rounded-lg p-2 overflow-x-auto">
        <button
          onClick={() => onIndexChange(Math.max(0, index - 1))}
          disabled={index === 0}
          className="px-3 py-1 rounded bg-stone-700 disabled:opacity-30 text-sm shrink-0"
        >
          ←
        </button>
        <div className="flex gap-1 flex-1 overflow-x-auto py-1">
          {decisions.map((d, i) => (
            <button
              key={i}
              onClick={() => onIndexChange(i)}
              className={`w-7 h-7 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                LABEL_DOT[d.label]
              } ${
                i === index
                  ? "ring-2 ring-emerald-300"
                  : "opacity-70 hover:opacity-100"
              } ${d.label === "inaccuracy" ? "text-black" : "text-white"}`}
              title={`#${i + 1} ${d.label}`}
            >
              {i + 1}
            </button>
          ))}
        </div>
        <button
          onClick={() => onIndexChange(Math.min(decisions.length - 1, index + 1))}
          disabled={index === decisions.length - 1}
          className="px-3 py-1 rounded bg-stone-700 disabled:opacity-30 text-sm shrink-0"
        >
          →
        </button>
      </div>
      <div className="text-xs text-stone-400 text-center">
        決策 {index + 1} / {decisions.length}
        <span className="ml-2 text-stone-500">(← → 鍵切換)</span>
      </div>
      {current.board && <BoardStateView board={current.board} />}
      <ReviewCard review={current} />
    </div>
  );
}
