"use client";

import type { Alternative, DecisionReview } from "@/lib/api";
import { LabelBadge } from "./LabelBadge";
import { Tile } from "./Tile";

function dangerColor(score: number): string {
  if (score <= 0) return "text-best";
  if (score <= 15) return "text-best";
  if (score <= 35) return "text-good";
  if (score <= 55) return "text-inaccuracy";
  if (score <= 80) return "text-mistake";
  return "text-blunder";
}

function AlternativeRow({
  alt,
  variant,
}: {
  alt: Alternative;
  variant?: "chosen" | "recommend" | undefined;
}) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-stone-700 last:border-b-0">
      <Tile notation={alt.tile} size="sm" highlight={variant} />
      <div className="flex-1">
        <div className="flex items-baseline gap-2">
          <span className={`font-mono font-semibold ${dangerColor(alt.danger)}`}>
            危險 {alt.danger}
          </span>
          <span className="text-xs text-stone-400">{alt.verdict}</span>
        </div>
        <div className="text-[11px] text-stone-400">
          押期望 {alt.push_ev >= 0 ? "+" : ""}
          {alt.push_ev} · 和率 {(alt.win_prob * 100).toFixed(1)}%
        </div>
        {alt.factors.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {alt.factors.map((f, i) => (
              <span
                key={i}
                className={`px-1.5 py-0.5 rounded text-[10px] ${
                  f.delta < 0
                    ? "bg-emerald-900/40 text-emerald-300"
                    : "bg-red-900/40 text-red-300"
                }`}
                title={`${f.code}: ${f.delta >= 0 ? "+" : ""}${f.delta}`}
              >
                {f.label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ReviewCard({ review }: { review: DecisionReview }) {
  return (
    <div className="bg-stone-800 rounded-lg p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm text-stone-300">{review.situation}</div>
        <LabelBadge label={review.label} />
      </div>

      <div className="text-base text-stone-100 leading-relaxed">
        {review.summary}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="bg-stone-900 rounded p-3">
          <div className="text-xs font-semibold text-mistake mb-2">你的選擇</div>
          <div className="flex items-center gap-3 mb-2">
            <Tile notation={review.your_choice.tile} size="md" highlight="chosen" />
            <div>
              <div className={`font-mono ${dangerColor(review.your_choice.danger)}`}>
                危險 {review.your_choice.danger} · {review.your_choice.verdict}
              </div>
              <div className="text-xs text-stone-400">
                押牌期望值 {review.your_push_ev >= 0 ? "+" : ""}
                {review.your_push_ev} 點
              </div>
            </div>
          </div>
          <ul className="text-xs text-stone-300 space-y-0.5">
            {review.your_reasons.map((r, i) => (
              <li key={i}>· {r}</li>
            ))}
          </ul>
        </div>

        <div className="bg-stone-900 rounded p-3">
          <div className="text-xs font-semibold text-good mb-2">建議選擇</div>
          <div className="flex items-center gap-3 mb-2">
            <Tile
              notation={review.recommendation.tile}
              size="md"
              highlight="recommend"
            />
            <div>
              <div className={`font-mono ${dangerColor(review.recommendation.danger)}`}>
                危險 {review.recommendation.danger} · {review.recommendation.verdict}
              </div>
              <div className="text-xs text-stone-400">
                押牌期望值 {review.recommendation_push_ev >= 0 ? "+" : ""}
                {review.recommendation_push_ev} 點
              </div>
            </div>
          </div>
          <ul className="text-xs text-stone-300 space-y-0.5">
            {review.recommendation_reasons.map((r, i) => (
              <li key={i}>· {r}</li>
            ))}
          </ul>
        </div>
      </div>

      <details className="bg-stone-900 rounded p-3">
        <summary className="text-xs text-stone-400 cursor-pointer select-none">
          所有候選 (依期望值排序) · {review.alternatives.length} 張
        </summary>
        <div className="mt-2">
          {review.alternatives.map((alt) => (
            <AlternativeRow
              key={alt.tile}
              alt={alt}
              variant={
                alt.tile === review.your_choice.tile
                  ? "chosen"
                  : alt.tile === review.recommendation.tile
                    ? "recommend"
                    : undefined
              }
            />
          ))}
        </div>
      </details>
    </div>
  );
}
