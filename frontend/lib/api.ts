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
  effective_tiles: string[];
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

export type DecisionType = "defense" | "efficiency";

export type DecisionReview = {
  situation: string;
  label: DecisionLabel;
  summary: string;
  decision_type: DecisionType;
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
  defense_total: number;
  efficiency_total: number;
};

export type LogReviewResult = {
  hero_seat: number;
  decisions: DecisionReview[];
  summary: GameSummary;
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
  own_discards?: string;
};

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(
      `無法連線到後端 (${API_BASE}) — 請確認後端已啟動，或設定 NEXT_PUBLIC_API_BASE。`
    );
  }
  if (!r.ok) {
    const err = await r.text();
    throw new Error(`API ${r.status}: ${err}`);
  }
  return r.json();
}

export function reviewManual(req: ManualReviewRequest): Promise<DecisionReview> {
  return postJson("/review/manual", req);
}

export function reviewTenhou(log: unknown, heroSeat: number): Promise<LogReviewResult> {
  return postJson("/review/tenhou", { log, hero_seat: heroSeat });
}

export function reviewMajsoul(log: unknown, heroSeat: number): Promise<LogReviewResult> {
  return postJson("/review/majsoul", { log, hero_seat: heroSeat });
}

export type LogFormat = "tenhou" | "majsoul";

/** Sniff whether a parsed log JSON is tenhou (tenhou.net/6) or a decoded majsoul record. */
export function detectLogFormat(parsed: unknown): LogFormat | null {
  if (Array.isArray(parsed)) {
    return looksLikeMajsoulActions(parsed) ? "majsoul" : null;
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const obj = parsed as Record<string, unknown>;
  if (Array.isArray(obj.log)) return "tenhou";
  for (const key of ["data", "record", "actions"]) {
    if (Array.isArray(obj[key]) && looksLikeMajsoulActions(obj[key] as unknown[])) {
      return "majsoul";
    }
  }
  return null;
}

function looksLikeMajsoulActions(entries: unknown[]): boolean {
  return entries.some(
    (e) =>
      typeof e === "object" &&
      e !== null &&
      typeof (e as Record<string, unknown>).name === "string" &&
      ((e as Record<string, unknown>).name as string).includes("Record")
  );
}
