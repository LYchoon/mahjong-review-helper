/**
 * Shared severity bands. Danger scores are 0..100 (see backend danger.py):
 *   0–15 very safe · 16–35 relatively safe · 36–55 uncertain ·
 *   56–80 dangerous · 81–100 very dangerous
 * Accuracy is the chess.com-style 0..100 game score.
 */

type Band = 0 | 1 | 2 | 3 | 4;

function dangerBand(score: number): Band {
  if (score <= 15) return 0;
  if (score <= 35) return 1;
  if (score <= 55) return 2;
  if (score <= 80) return 3;
  return 4;
}

const TEXT = ["text-best", "text-good", "text-inaccuracy", "text-mistake", "text-blunder"];
const BG = ["bg-best", "bg-good", "bg-inaccuracy", "bg-mistake", "bg-blunder"];
const RING = ["ring-best", "ring-good", "ring-inaccuracy", "ring-mistake", "ring-blunder"];

export function dangerTextClass(score: number): string {
  return TEXT[dangerBand(score)];
}

export function dangerBgClass(score: number): string {
  return BG[dangerBand(score)];
}

export function dangerRingClass(score: number): string {
  // certified-safe and very-dangerous tiles get a heavier ring
  if (score <= 0) return "ring-2 ring-best";
  if (score > 80) return "ring-2 ring-blunder";
  return `ring-1 ${RING[dangerBand(score)]}`;
}

export function accuracyTextClass(accuracy: number): string {
  if (accuracy >= 90) return TEXT[0];
  if (accuracy >= 75) return TEXT[1];
  if (accuracy >= 60) return TEXT[2];
  if (accuracy >= 40) return TEXT[3];
  return TEXT[4];
}

export function shantenLabel(sh: number): string {
  if (sh < 0) return "已和";
  if (sh === 0) return "聽牌";
  return `${sh} 向聽`;
}
