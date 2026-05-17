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

function shantenLabel(sh: number): string {
  if (sh < 0) return "已和";
  if (sh === 0) return "聽牌";
  return `${sh} 向聽`;
}

function AlternativeRow({
  alt,
  variant,
}: {
  alt: Alternative;
  variant?: "chosen" | "recommend" | undefined;
}) {
  return (
    <div className="flex items-start gap-3 py-2 border-b border-stone-700 last:border-b-0">
      <Tile notation={alt.tile} size="sm" highlight={variant} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className={`font-mono font-semibold ${dangerColor(alt.danger)}`}>
            危險 {alt.danger}
          </span>
          <span className="text-xs text-stone-400">{alt.verdict}</span>
          <span className="text-xs text-stone-500">
            · {shantenLabel(alt.shanten_after)}
          </span>
          {alt.ukeire > 0 && (
            <span className="text-xs text-stone-500">
              · 進張 {alt.ukeire}
            </span>
          )}
        </div>
        <div className="text-[11px] text-stone-400">
          押期望 {alt.push_ev >= 0 ? "+" : ""}
          {alt.push_ev} · 和率 {(alt.win_prob * 100).toFixed(1)}% · 估{alt.han_estimate}翻
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

function ChoicePanel({
  title,
  titleClass,
  alt,
  pushEv,
  reasons,
  variant,
}: {
  title: string;
  titleClass: string;
  alt: Alternative;
  pushEv: number;
  reasons: string[];
  variant: "chosen" | "recommend";
}) {
  return (
    <div className="bg-stone-900 rounded p-3">
      <div className={`text-xs font-semibold mb-2 ${titleClass}`}>{title}</div>
      <div className="flex items-center gap-3 mb-2">
        <Tile notation={alt.tile} size="md" highlight={variant} />
        <div className="min-w-0">
          <div className={`font-mono ${dangerColor(alt.danger)}`}>
            危險 {alt.danger} · {alt.verdict}
          </div>
          <div className="text-xs text-stone-400">
            押牌期望值 {pushEv >= 0 ? "+" : ""}
            {pushEv} 點 · 和率 {(alt.win_prob * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-stone-500 mt-0.5">
            切後 {shantenLabel(alt.shanten_after)}
            {alt.ukeire > 0 && ` · 進張 ${alt.ukeire} 枚`}
            {` · 殘餘安全牌 ${alt.future_safe_tiles}`}
          </div>
          {alt.yaku_tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {alt.yaku_tags.map((tag, i) => (
                <span
                  key={i}
                  className="px-1.5 py-0.5 rounded text-[10px] bg-amber-900/40 text-amber-200"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <ul className="text-xs text-stone-300 space-y-0.5">
        {reasons.map((r, i) => (
          <li key={i}>· {r}</li>
        ))}
      </ul>
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
        <ChoicePanel
          title="你的選擇"
          titleClass="text-mistake"
          alt={review.your_choice}
          pushEv={review.your_push_ev}
          reasons={review.your_reasons}
          variant="chosen"
        />
        <ChoicePanel
          title="建議選擇"
          titleClass="text-good"
          alt={review.recommendation}
          pushEv={review.recommendation_push_ev}
          reasons={review.recommendation_reasons}
          variant="recommend"
        />
      </div>

      <details className="bg-stone-900 rounded p-3">
        <summary className="text-xs text-stone-400 cursor-pointer select-none">
          所有候選 (依押牌期望值排序) · {review.alternatives.length} 張
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
