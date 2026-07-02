"use client";

import { useMemo } from "react";

import type { Alternative } from "@/lib/api";
import { dangerRingClass } from "@/lib/severity";
import { DangerBar } from "./DangerBar";
import { Tile } from "./Tile";

/**
 * Visualize danger per tile in the hand. Takes the sorted alternatives list
 * (one entry per distinct tile id) and renders each tile colour-ringed by its
 * danger level, with a tiny bar underneath.
 */
export function HandSafetyView({
  alternatives,
  chosenTile,
  recommendedTile,
}: {
  alternatives: Alternative[];
  chosenTile: string;
  recommendedTile: string;
}) {
  const sorted = useMemo(
    () => [...alternatives].sort((a, b) => a.danger - b.danger),
    [alternatives]
  );
  return (
    <div className="bg-stone-900 rounded p-3">
      <div className="text-xs text-stone-400 mb-2">
        手牌安全分佈 (依危險度由低到高)
      </div>
      <div className="grid grid-cols-7 sm:grid-cols-10 md:grid-cols-14 gap-2">
        {sorted.map((alt) => {
          const isChosen = alt.tile === chosenTile;
          const isRecommended = alt.tile === recommendedTile;
          return (
            <div key={alt.tile} className="flex flex-col items-center gap-1">
              <div className={`rounded ${dangerRingClass(alt.danger)}`}>
                <Tile
                  notation={alt.tile}
                  size="sm"
                  highlight={
                    isChosen
                      ? "chosen"
                      : isRecommended
                        ? "recommend"
                        : undefined
                  }
                />
              </div>
              <div className="w-full">
                <DangerBar score={alt.danger} height="h-1" />
              </div>
              <span className="text-[9px] text-stone-500 font-mono">
                {alt.danger.toFixed(0)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
