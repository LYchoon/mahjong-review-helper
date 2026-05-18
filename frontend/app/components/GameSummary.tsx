"use client";

import type { GameSummary } from "@/lib/api";

function accuracyColor(a: number): string {
  if (a >= 90) return "text-best";
  if (a >= 75) return "text-good";
  if (a >= 60) return "text-inaccuracy";
  if (a >= 40) return "text-mistake";
  return "text-blunder";
}

function Stat({
  count,
  label,
  colorClass,
}: {
  count: number;
  label: string;
  colorClass: string;
}) {
  return (
    <div className="flex flex-col items-center">
      <span className={`text-xl font-bold ${colorClass}`}>{count}</span>
      <span className="text-[10px] text-stone-400 uppercase tracking-wide">
        {label}
      </span>
    </div>
  );
}

export function GameSummaryCard({
  summary,
  onJumpToWorst,
}: {
  summary: GameSummary;
  onJumpToWorst?: () => void;
}) {
  if (summary.total === 0) {
    return (
      <div className="bg-stone-800 rounded-lg p-4 text-sm text-stone-400">
        這局沒有需要分析的防守決策 (沒有對手立直或鳴牌威脅)。
      </div>
    );
  }
  return (
    <div className="bg-stone-800 rounded-lg p-5 mb-4">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div>
          <div className="text-xs text-stone-400 uppercase tracking-wide">
            防守準確率
          </div>
          <div className={`text-4xl font-bold ${accuracyColor(summary.accuracy)}`}>
            {summary.accuracy.toFixed(1)}
            <span className="text-lg text-stone-500">%</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-stone-400">分析的防守決策數</div>
          <div className="text-2xl font-bold">{summary.total}</div>
          <div className="text-xs text-stone-500 mt-1">
            累積期望失分 −{Math.round(summary.total_ev_lost)} 點
          </div>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-2 bg-stone-900 rounded p-3">
        <Stat count={summary.best} label="最佳" colorClass="text-best" />
        <Stat count={summary.good} label="良好" colorClass="text-good" />
        <Stat
          count={summary.inaccuracy}
          label="不準確"
          colorClass="text-inaccuracy"
        />
        <Stat count={summary.mistake} label="失誤" colorClass="text-mistake" />
        <Stat count={summary.blunder} label="嚴重失誤" colorClass="text-blunder" />
      </div>

      {summary.biggest_blunder_index !== null && onJumpToWorst && (
        <button
          onClick={onJumpToWorst}
          className="mt-3 text-xs text-emerald-400 hover:text-emerald-300 underline"
        >
          → 跳到最大失誤 (#{summary.biggest_blunder_index + 1})
        </button>
      )}
    </div>
  );
}
