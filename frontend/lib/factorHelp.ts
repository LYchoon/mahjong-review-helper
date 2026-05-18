/**
 * Educational explanations for each danger factor code.
 * Shown in tooltips so users can learn what each shorthand means.
 */
export const FACTOR_HELP: Record<string, string> = {
  GENBUTSU:
    "現物 — 對手立直 (或聽牌威脅) 後已切過的牌。立直者不能榮和振聽牌，所以是 100% 安全。",
  GENBUTSU_PRE:
    "立直前現物 — 對手立直之前已切過的牌。立直者進入立直後不能更改聽牌，所以振聽中也不能榮和。",
  EARLY_DISCARD:
    "早期切過 — 對手早期切過這張牌。對非立直威脅而言，聽牌可能在後續才形成，安全性比現物低。",
  SUJI_47: "片筋 1-4-7 — 對手切了 4，所以 7 不會是 5-7 兩面聽 (5-6 才會等 7)。仍可能是嵌張/邊張/單騎。",
  SUJI_14: "片筋 1-4-7 — 對手切了 4，1 不會被 2-3 等。",
  SUJI_25: "片筋 2-5-8 — 對手切了 5，2 不會被 3-4 等。",
  SUJI_58: "片筋 2-5-8 — 對手切了 5，8 不會被 6-7 等。",
  SUJI_36: "片筋 3-6-9 — 對手切了 6，3 不會被 4-5 等。",
  SUJI_69: "片筋 3-6-9 — 對手切了 6，9 不會被 7-8 等。",
  SUJI_DOUBLE:
    "雙筋 — 中張兩邊的筋都已切過 (例如打 5 時 2 和 8 都見了)。兩面聽完全排除，但仍可能嵌張/單騎。",
  SUJI_HALF:
    "半筋 — 中張只有一側的筋被切。另一側的兩面聽仍可能等這張牌。",
  NO_CHANCE:
    "no-chance — 形成此牌兩面搭子所需的內側鄰牌已全部見光，沒有人能持有相應的搭子形。",
  ONE_CHANCE:
    "one-chance — 形成此牌搭子的內側鄰牌只剩 1 枚未見。對手要剛好持有那 1 枚才會等到。",
  KABE_BOTH: "雙側壁 — 此牌兩側的內側鄰牌都已全見，幾乎不可能形成兩面搭。",
  KABE_SIDE: "單側壁 — 此牌一側的內側鄰牌已全見。",
  BASE_NUM: "數牌基準危險度 — 中央 (4-6) 最危險，邊端 (1, 9) 最安全。",
  BASE_HONOR: "字牌基準危險度 — 役牌 (場/自風/三元) 比客風危險。已見越多越安全。",
  EARLY_RIICHI: "早巡立直 — 6 巡內立直的玩家通常有打點壓力與牌效。+5 基準危險。",
  DAMA_DISCOUNT: "默聽折扣 — 沒有立直宣言，可能仍是聽牌但不確定，整體放銃率較低。",
  IISHANTEN_DISCOUNT: "一向聽折扣 — 推測對手未聽牌，放銃機率明顯較低。",
  SUIT_CONCENTRATION: "染色嫌疑 — 對手很少切這個花色，疑似在做混一色/清一色。",
  SUIT_ABANDONED: "放棄色 — 對手大量切過此花色，相對安全。",
  MULTI_THREAT:
    "多家威脅 — 合計每位對手獨立放銃機率: 1 − ∏(1 − pᵢ)。下面每個因素都有 [P0/P1/P2/P3] 標記來源。",
};

export function helpFor(code: string): string | undefined {
  // strip multi-threat seat suffix if present (e.g. "GENBUTSU_P1")
  const m = code.match(/^(.*?)_P\d$/);
  return FACTOR_HELP[m ? m[1] : code];
}
