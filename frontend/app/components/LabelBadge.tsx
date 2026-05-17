"use client";

import type { DecisionReview } from "@/lib/api";

const TEXT: Record<DecisionReview["label"], string> = {
  best: "最佳",
  good: "良好",
  inaccuracy: "不準確",
  mistake: "失誤",
  blunder: "嚴重失誤",
};

const BG: Record<DecisionReview["label"], string> = {
  best: "bg-best",
  good: "bg-good",
  inaccuracy: "bg-inaccuracy text-black",
  mistake: "bg-mistake",
  blunder: "bg-blunder",
};

export function LabelBadge({ label }: { label: DecisionReview["label"] }) {
  return (
    <span
      className={`inline-block px-3 py-1 rounded-full text-white text-sm font-semibold ${BG[label]}`}
    >
      {TEXT[label]}
    </span>
  );
}
