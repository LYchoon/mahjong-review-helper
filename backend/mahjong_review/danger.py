"""Danger tile assessment.

Given a threat player (typically the riichi declarer) and the visible state, score
how dangerous each tile is to discard. This is intentionally heuristic — no full
hand-range simulation — but it cites concrete reasons that a human player can verify:

- Genbutsu (現物): in the threat's discard pile after their threat began
- Suji (筋): the 1/4/7, 2/5/8, 3/6/9 chains, only safe against ryanmen waits
- Kabe (壁): all 4 of a tile visible removes some ryanmen possibilities
- No-chance / one-chance: zero or one of the partner tiles for a ryanmen visible
- Honor visibility: 3 of an honor out → 4th is safe; 2 out + late round → likely safe
- Tile position: 4/5/6 highest base danger, 1/9 lowest among numbers
- Threat strength: riichi at early turn is more dangerous than late dama

Scores are 0..100, where:
  0     = certified safe (genbutsu)
  1-15  = very safe
  16-35 = relatively safe
  36-55 = uncertain
  56-80 = dangerous
  81-100 = very dangerous / 振聽 risk
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .tiles import HONORS, NUM_TILE_TYPES, Tile, tile_counts


class ThreatKind(str, Enum):
    RIICHI = "riichi"
    DAMA_TENPAI = "dama_tenpai"  # heuristic: many calls + late round
    IISHANTEN = "iishanten"


@dataclass
class Threat:
    """A single opponent threat we need to defend against."""

    player: int  # 0..3 absolute seat
    kind: ThreatKind
    declared_turn: int  # turn number when threat began (1-indexed)
    discards: list[Tile] = field(default_factory=list)  # full discard pile in order
    discards_after_threat: list[Tile] = field(default_factory=list)
    called_tiles: list[Tile] = field(default_factory=list)  # tiles in their opened melds
    dora_indicators: list[Tile] = field(default_factory=list)


@dataclass
class DangerFactor:
    code: str  # short identifier, e.g. "GENBUTSU", "SUJI_47"
    label: str  # human-readable Chinese label
    delta: float  # signed contribution to the final score (negative = safer)


@dataclass
class DangerAssessment:
    tile: Tile
    score: float  # 0..100
    factors: list[DangerFactor]

    @property
    def verdict(self) -> str:
        if self.score <= 0:
            return "完全安全"
        if self.score <= 15:
            return "非常安全"
        if self.score <= 35:
            return "相對安全"
        if self.score <= 55:
            return "不確定"
        if self.score <= 80:
            return "危險"
        return "非常危險"


# Base danger by tile position (rough industry numbers: middle tiles most dangerous).
# These approximate the relative frequency that a tile appears in winning waits.
_BASE_DANGER_NUMBER = {
    1: 28,
    2: 32,
    3: 38,
    4: 44,
    5: 50,
    6: 44,
    7: 38,
    8: 32,
    9: 28,
}
_BASE_DANGER_HONOR = 22  # before any visibility adjustment


def assess_tile(
    tile: Tile,
    threat: Threat,
    visible_counts: list[int],
    round_wind: int = 27,  # East by default
    seat_wind_of_threat: int = 27,
) -> DangerAssessment:
    """Score how dangerous it is to discard `tile` against `threat`.

    `visible_counts` is a length-34 count of every tile visible to us (our hand,
    all discards from all players, dora indicators, and called melds). The
    threat's own concealed hand is NOT visible.
    """
    factors: list[DangerFactor] = []

    # --- 1. genbutsu (現物) ---
    if any(t.tid == tile.tid for t in threat.discards_after_threat):
        factors.append(DangerFactor("GENBUTSU", "現物 (對手立直/聽牌後已切過)", -200))
        return DangerAssessment(tile, 0.0, factors)

    # furiten safety: tile is in any of the threat's earlier discards
    if any(t.tid == tile.tid for t in threat.discards):
        # for riichi this is also genbutsu (cannot ron furiten); for dama it's strong evidence
        if threat.kind == ThreatKind.RIICHI:
            factors.append(DangerFactor("GENBUTSU_PRE", "立直前已切過 (振聽不能榮)", -200))
            return DangerAssessment(tile, 0.0, factors)
        factors.append(DangerFactor("EARLY_DISCARD", "對手早期切過 (但聽牌可能更新)", -25))

    # --- 2. base by position ---
    if tile.is_honor:
        score = float(_base_honor_danger(tile, visible_counts, round_wind, seat_wind_of_threat))
        factors.append(DangerFactor("BASE_HONOR", f"字牌基準危險度", score))
    else:
        base = _BASE_DANGER_NUMBER[tile.rank]
        score = float(base)
        factors.append(DangerFactor("BASE_NUM", f"{tile.rank} 位數牌基準危險度", base))

    # --- 3. suji (only for number tiles) ---
    if not tile.is_honor:
        suji_adj = _suji_adjustment(tile, threat, factors)
        score += suji_adj

    # --- 4. kabe / no-chance / one-chance ---
    if not tile.is_honor:
        kabe_adj = _kabe_adjustment(tile, visible_counts, factors)
        score += kabe_adj

    # --- 5. threat strength multiplier ---
    score = _apply_threat_strength(score, threat, factors)

    # clamp
    score = max(0.0, min(100.0, score))
    return DangerAssessment(tile, score, factors)


def _base_honor_danger(
    tile: Tile,
    visible_counts: list[int],
    round_wind: int,
    seat_wind_of_threat: int,
) -> float:
    visible = visible_counts[tile.tid]
    if visible >= 3:
        return 1.0  # the 4th is essentially safe; can only be shanpon wait with paired honor
    yakuhai = tile.tid in (round_wind, seat_wind_of_threat) or 30 <= tile.tid <= 33  # ESWN + dragons subset
    is_dragon = tile.tid >= 31
    is_yakuhai_wind = tile.tid in (round_wind, seat_wind_of_threat)
    base = _BASE_DANGER_HONOR
    if is_dragon:
        base += 6
    if is_yakuhai_wind:
        base += 6
    # visibility adjustments
    if visible == 2:
        base -= 14  # likely safe — only shanpon with the last one
    elif visible == 1:
        base -= 6
    # not-yakuhai winds (客風) are safer
    if tile.tid in (27, 28, 29, 30) and not is_yakuhai_wind:
        base -= 6
    return max(2.0, float(base))


def _suji_adjustment(tile: Tile, threat: Threat, factors: list[DangerFactor]) -> float:
    """筋牌調整: if relevant suji partners are in threat's discards, danger drops."""
    rank = tile.rank
    suit = tile.suit

    def in_threat_discards(target_rank: int) -> bool:
        target_tid = (rank - 1) - (rank - target_rank) + _suit_offset(suit)
        target_tid = _suit_offset(suit) + (target_rank - 1)
        return any(t.tid == target_tid for t in threat.discards)

    # Suji logic — safe ONLY against ryanmen, not against penchan / kanchan / shanpon / tanki.
    if rank == 1:
        if in_threat_discards(4):
            factors.append(DangerFactor("SUJI_14", "4 已切，1 是片筋", -12))
            return -12.0
    elif rank == 9:
        if in_threat_discards(6):
            factors.append(DangerFactor("SUJI_69", "6 已切，9 是片筋", -12))
            return -12.0
    elif rank == 2:
        if in_threat_discards(5):
            factors.append(DangerFactor("SUJI_25", "5 已切，2 是片筋", -10))
            return -10.0
    elif rank == 8:
        if in_threat_discards(5):
            factors.append(DangerFactor("SUJI_58", "5 已切，8 是片筋", -10))
            return -10.0
    elif rank == 3:
        if in_threat_discards(6):
            factors.append(DangerFactor("SUJI_36", "6 已切，3 是片筋", -10))
            return -10.0
    elif rank == 7:
        if in_threat_discards(4):
            factors.append(DangerFactor("SUJI_47", "4 已切，7 是片筋", -10))
            return -10.0
    elif rank in (4, 5, 6):
        # middle tiles can be "double suji" — both partners on the chain are out
        partners = {4: (1, 7), 5: (2, 8), 6: (3, 9)}[rank]
        a_out = in_threat_discards(partners[0])
        b_out = in_threat_discards(partners[1])
        if a_out and b_out:
            factors.append(
                DangerFactor("SUJI_DOUBLE", f"{partners[0]} 與 {partners[1]} 皆已切，雙筋", -22)
            )
            return -22.0
        if a_out or b_out:
            out = partners[0] if a_out else partners[1]
            factors.append(DangerFactor("SUJI_HALF", f"{out} 已切，半筋 (仍可能另一面)", -8))
            return -8.0
    return 0.0


def _suit_offset(suit: str) -> int:
    return {"m": 0, "p": 9, "s": 18}[suit]


def _kabe_adjustment(tile: Tile, visible_counts: list[int], factors: list[DangerFactor]) -> float:
    """Kabe (壁) / no-chance / one-chance.

    If all 4 of tile X are visible, ryanmen waits that need X are impossible. We check
    the partner tiles that would form ryanmen on `tile`:

    For a discard of rank r in a suit, the ryanmen waits that could be hit are:
       (r-2, r-1) waiting on r        — needs r-1 and r-2 still in opponent hand
       (r-1, r-2) waiting on r-3 / r  — already covered
       (r+1, r+2) waiting on r        — needs r+1 and r+2
       (r-1, r+1) ... no, that's kanchan

    We say `tile` is no-chance if BOTH partners for every ryanmen that hits it are
    impossible (all 4 visible of the inner partner). One-chance = only 1 of the
    inner partner is unseen.
    """
    if tile.is_honor:
        return 0.0
    rank = tile.rank
    suit_off = _suit_offset(tile.suit)

    def remaining(r: int) -> int:
        if r < 1 or r > 9:
            return -1  # not applicable
        return 4 - visible_counts[suit_off + r - 1]

    # ryanmen shapes that wait on `rank`:
    #   left side: shape (rank-2, rank-1)  — also waits on rank+1 if applicable
    #   right side: shape (rank+1, rank+2) — also waits on rank-1
    # For pure no-chance on `rank`, we need: there's no possible held shape that waits on it.
    # We approximate by requiring both partner tiles of every relevant ryanmen to be fully gone.

    left_inner = remaining(rank - 1)
    left_outer = remaining(rank - 2)
    right_inner = remaining(rank + 1)
    right_outer = remaining(rank + 2)

    left_possible = left_inner > 0 and left_outer > 0  # (r-2, r-1) shape possible
    right_possible = right_inner > 0 and right_outer > 0

    # also kanchan on `rank` (held: rank-1, rank+1) — partner tiles different
    kanchan_possible = left_inner > 0 and right_inner > 0

    if not left_possible and not right_possible and not kanchan_possible:
        factors.append(DangerFactor("NO_CHANCE", "no-chance: 形成搭子的牌已全見", -30))
        return -30.0

    # one-chance: at least one partner only has 1 left in unseen
    danger_delta = 0.0
    if (left_inner == 1 and left_outer >= 1) or (right_inner == 1 and right_outer >= 1):
        factors.append(DangerFactor("ONE_CHANCE", "one-chance: 內側搭子只剩 1 枚未見", -10))
        danger_delta -= 10

    # kabe on inner partner
    if left_inner == 0 and right_inner == 0:
        factors.append(DangerFactor("KABE_BOTH", "兩側內筋牌已全見 (兩面搭子不可能)", -22))
        danger_delta -= 22
    elif left_inner == 0 or right_inner == 0:
        side = "左" if left_inner == 0 else "右"
        factors.append(DangerFactor("KABE_SIDE", f"{side}側內筋牌已全見", -10))
        danger_delta -= 10

    return danger_delta


def _apply_threat_strength(score: float, threat: Threat, factors: list[DangerFactor]) -> float:
    if threat.kind == ThreatKind.RIICHI:
        # riichi means definitely tenpai — full danger applies
        if threat.declared_turn <= 6:
            factors.append(DangerFactor("EARLY_RIICHI", "早巡立直 (打點壓力大)", +5))
            return score + 5
        return score
    if threat.kind == ThreatKind.DAMA_TENPAI:
        factors.append(DangerFactor("DAMA_DISCOUNT", "默聽威脅 (尚未確認聽牌)", -8))
        return score - 8
    if threat.kind == ThreatKind.IISHANTEN:
        factors.append(DangerFactor("IISHANTEN_DISCOUNT", "一向聽威脅 (還沒聽牌)", -20))
        return score - 20
    return score


def assess_hand(
    hand: list[Tile],
    threat: Threat,
    visible_counts: list[int],
    round_wind: int = 27,
    seat_wind_of_threat: int = 27,
) -> list[DangerAssessment]:
    """Score every distinct tile in `hand` (deduplicated by tile id)."""
    seen: set[int] = set()
    out: list[DangerAssessment] = []
    for t in hand:
        if t.tid in seen:
            continue
        seen.add(t.tid)
        out.append(
            assess_tile(t, threat, visible_counts, round_wind, seat_wind_of_threat)
        )
    out.sort(key=lambda a: a.score)
    return out
