"use client";

import { memo } from "react";

import type { Alternative, DecisionReview, RiichiAdvice } from "@/lib/api";
import { helpFor } from "@/lib/factorHelp";
import { dangerTextClass, shantenLabel } from "@/lib/severity";
import { DangerBar, EVBar } from "./DangerBar";
import { HandSafetyView } from "./HandSafety";
import { InfoPopover } from "./InfoPopover";
import { LabelBadge } from "./LabelBadge";
import { Tile } from "./Tile";

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
          <span className={`font-mono font-semibold ${dangerTextClass(alt.danger)}`}>
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
        <div className="mt-1 grid grid-cols-[3rem_1fr] gap-x-2 items-center">
          <span className="text-[10px] text-stone-500">危險</span>
          <DangerBar score={alt.danger} />
          <span className="text-[10px] text-stone-500">押EV</span>
          <EVBar value={alt.push_ev} />
        </div>
        <div className="text-[11px] text-stone-400 mt-1">
          押期望 {alt.push_ev >= 0 ? "+" : ""}
          {alt.push_ev} · 和率 {(alt.win_prob * 100).toFixed(1)}% · 估{alt.han_estimate}翻
        </div>
        {alt.factors.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {alt.factors.map((f, i) => {
              const help = helpFor(f.code);
              const deltaText = `${f.delta >= 0 ? "+" : ""}${f.delta}`;
              return (
                <InfoPopover
                  key={`${f.code}-${i}`}
                  label={f.label}
                  buttonClass={`px-1.5 py-0.5 rounded text-[10px] cursor-help ${
                    f.delta < 0
                      ? "bg-emerald-900/40 text-emerald-300"
                      : "bg-red-900/40 text-red-300"
                  }`}
                >
                  <span className="font-mono text-stone-400">
                    {f.code} ({deltaText})
                  </span>
                  {help ? `\n\n${help}` : ""}
                </InfoPopover>
              );
            })}
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
        <div className="min-w-0 flex-1">
          <div className={`font-mono ${dangerTextClass(alt.danger)}`}>
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
        </div>
      </div>
      <div className="grid grid-cols-[3rem_1fr] gap-x-2 items-center mb-1">
        <span className="text-[10px] text-stone-500">危險</span>
        <DangerBar score={alt.danger} height="h-2" />
        <span className="text-[10px] text-stone-500">押EV</span>
        <EVBar value={pushEv} height="h-2" />
      </div>
      {alt.yaku_tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
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
      {alt.effective_tiles.length > 0 && (
        <div className="mb-2">
          <div className="text-[10px] text-stone-500 mb-1">
            切後有效進張 ({alt.ukeire} 枚):
          </div>
          <div className="flex flex-wrap gap-0.5">
            {alt.effective_tiles.map((t, i) => (
              <Tile key={i} notation={t} size="sm" />
            ))}
          </div>
        </div>
      )}
      <ul className="text-xs text-stone-300 space-y-0.5">
        {reasons.map((r, i) => (
          <li key={i}>· {r}</li>
        ))}
      </ul>
    </div>
  );
}

export const ReviewCard = memo(function ReviewCard({
  review,
}: {
  review: DecisionReview;
}) {
  return (
    <div className="bg-stone-800 rounded-lg p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0 ${
              review.decision_type === "defense"
                ? "bg-red-900/60 text-red-200"
                : "bg-sky-900/60 text-sky-200"
            }`}
          >
            {review.decision_type === "defense" ? "防守" : "進攻"}
          </span>
          <div className="text-sm text-stone-300">{review.situation}</div>
        </div>
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

      {review.riichi && <RiichiPanel advice={review.riichi} />}

      <HandSafetyView
        alternatives={review.alternatives}
        chosenTile={review.your_choice.tile}
        recommendedTile={review.recommendation.tile}
      />

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
});

function RiichiPanel({ advice }: { advice: RiichiAdvice }) {
  const agree = advice.declared === advice.recommended;
  return (
    <div
      className={`rounded p-3 border ${
        agree
          ? "bg-emerald-950/40 border-emerald-800"
          : "bg-amber-950/40 border-amber-700"
      }`}
    >
      <div className="flex items-center gap-2 text-xs font-semibold mb-1">
        <span className="px-1.5 py-0.5 rounded bg-yellow-500 text-black text-[10px]">
          立直判斷
        </span>
        <span className={agree ? "text-emerald-300" : "text-amber-300"}>
          你{advice.declared ? "立直了" : "選擇不立直"} · 建議
          {advice.recommended ? "立直" : "默聽"}
          {agree ? " — 一致" : ""}
        </span>
      </div>
      <ul className="text-xs text-stone-300 space-y-0.5">
        {advice.reasons.map((r, i) => (
          <li key={i}>· {r}</li>
        ))}
      </ul>
    </div>
  );
}
