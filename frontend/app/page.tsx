"use client";

import { useState } from "react";

import { LogReviewTab } from "./components/LogReviewTab";
import { ManualTab } from "./components/ManualTab";

type Tab = "manual" | "log";

export default function Page() {
  const [tab, setTab] = useState<Tab>("manual");

  return (
    <main className="max-w-5xl mx-auto p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold mb-1">麻將復盤助手</h1>
        <p className="text-sm text-stone-400">
          chess.com 風格的逐手點評 — MVP 範圍：押牌 vs betaori 防守判斷
        </p>
      </header>

      <div className="flex gap-2 mb-4 border-b border-stone-700" role="tablist">
        {(
          [
            ["manual", "手動輸入單局"],
            ["log", "上傳牌譜 (天鳳/雀魂)"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            role="tab"
            aria-selected={tab === k}
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

      {tab === "manual" ? <ManualTab /> : <LogReviewTab />}
    </main>
  );
}
