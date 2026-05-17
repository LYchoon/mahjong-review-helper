export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Factor = {
  code: string;
  label: string;
  delta: number;
};

export type Alternative = {
  tile: string;
  danger: number;
  verdict: string;
  push_ev: number;
  win_prob: number;
  factors: Factor[];
  shanten_after: number;
  ukeire: number;
  future_safe_tiles: number;
  han_estimate: number;
  yaku_tags: string[];
};

export type DecisionLabel =
  | "best"
  | "good"
  | "inaccuracy"
  | "mistake"
  | "blunder";

export type BoardState = {
  round_label: string;
  turn: number;
  hero_seat: number;
  hero_hand: string[];
  discards: string[][];
  open_melds: string[][][];
  riichi_turns: (number | null)[];
  dora_indicators: string[];
  threats: { player: number; kind: string; declared_turn: number }[];
};

export type DecisionReview = {
  situation: string;
  label: DecisionLabel;
  summary: string;
  your_choice: Alternative;
  recommendation: Alternative;
  alternatives: Alternative[];
  your_push_ev: number;
  your_win_prob: number;
  recommendation_push_ev: number;
  recommendation_win_prob: number;
  your_reasons: string[];
  recommendation_reasons: string[];
  board?: BoardState;
};

export type GameSummary = {
  total: number;
  best: number;
  good: number;
  inaccuracy: number;
  mistake: number;
  blunder: number;
  accuracy: number;
  total_ev_lost: number;
  biggest_blunder_index: number | null;
};

export type ManualReviewRequest = {
  hand: string;
  chosen_discard: string;
  melds_count?: number;
  dora_count?: number;
  is_dealer?: boolean;
  turn?: number;
  turns_remaining?: number;
  round_wind_tile?: string;
  hero_seat?: number;
  threats: {
    player: number;
    kind: "riichi" | "dama_tenpai" | "iishanten";
    declared_turn: number;
    discards: string[];
    discards_after_threat: string[];
  }[];
  visible_tiles?: string;
};

export async function reviewManual(
  req: ManualReviewRequest
): Promise<DecisionReview> {
  const r = await fetch(`${API_BASE}/review/manual`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    const err = await r.text();
    throw new Error(`API ${r.status}: ${err}`);
  }
  return r.json();
}

export async function reviewTenhou(
  log: unknown,
  heroSeat: number
): Promise<{
  hero_seat: number;
  decisions: DecisionReview[];
  summary: GameSummary;
}> {
  const r = await fetch(`${API_BASE}/review/tenhou`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ log, hero_seat: heroSeat }),
  });
  if (!r.ok) {
    const err = await r.text();
    throw new Error(`API ${r.status}: ${err}`);
  }
  return r.json();
}
