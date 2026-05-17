"""Push / fold expected-value heuristics.

This is intentionally rough — proper EV would need a Monte-Carlo over remaining
draws and opponent hand ranges. For an explainable MVP we use closed-form
approximations that a player can sanity-check.

Push EV (per turn, in points):
    EV_push(tile) = P(win) * V(hand) - P(deal_in given push) * V(deal_in)

Fold EV:
    EV_fold = 0 (with mild negative for forced cheap discards later)

P(win) by shanten, given ~10 turns remaining mid-round (rough Tenhou-style numbers):
    tenpai   : 0.30
    1-shanten: 0.10
    2-shanten: 0.025
    3+       : 0.005

V(hand): han + dora estimate translated to non-dealer non-tsumo points.
V(deal_in): depends on threat kind; riichi avg ~ 6500, dama ~ 5200, iishanten ~ 3500.
"""

from __future__ import annotations

from dataclasses import dataclass

from .danger import DangerAssessment, Threat, ThreatKind
from .tiles import Tile


WIN_PROB_BY_SHANTEN = {
    -1: 0.95,
    0: 0.30,
    1: 0.10,
    2: 0.025,
    3: 0.005,
    4: 0.001,
}

DEAL_IN_COST = {
    ThreatKind.RIICHI: 6500.0,
    ThreatKind.DAMA_TENPAI: 5200.0,
    ThreatKind.IISHANTEN: 3500.0,
}


@dataclass
class HandValue:
    han: int  # estimated final han (incl. dora)
    points: float  # estimated payout if we win (non-dealer ron baseline)


def estimate_hand_value(
    han_estimate: int,
    is_dealer: bool = False,
    is_tsumo_likely: bool = False,
) -> HandValue:
    """Rough point estimate for an `han_estimate`-han hand (assume 30 fu)."""
    table = {
        1: 1000,
        2: 2000,
        3: 3900,
        4: 7700,
        5: 8000,
        6: 12000,
        7: 12000,
        8: 16000,
        9: 16000,
        10: 16000,
        11: 24000,
        12: 24000,
        13: 32000,
    }
    han = max(1, min(13, han_estimate))
    base = float(table[han])
    if is_dealer:
        base *= 1.5
    # tsumo distributes; for ron model this is fine
    return HandValue(han=han, points=base)


@dataclass
class PushFoldDecision:
    tile: Tile
    danger_score: float
    deal_in_prob: float  # 0..1
    win_prob: float  # 0..1 conditional on pushing till tenpai/win
    push_ev: float  # signed expected value in points
    fold_ev: float  # baseline (~0)
    recommend_push: bool
    reasons: list[str]


def evaluate_push(
    assessment: DangerAssessment,
    threat: Threat,
    own_shanten: int,
    own_hand_value: HandValue,
    turns_remaining: int = 10,
) -> PushFoldDecision:
    """Decide whether discarding `assessment.tile` to push is +EV vs folding."""
    deal_in_prob = assessment.score / 100.0
    win_prob = WIN_PROB_BY_SHANTEN.get(min(own_shanten, 4), 0.0)
    # taper by turns remaining (rough): full prob if 8+ turns, halve at 4, near zero at 1
    if turns_remaining < 8:
        win_prob *= max(0.1, turns_remaining / 8.0)

    cost = DEAL_IN_COST.get(threat.kind, 5000.0)
    push_ev = win_prob * own_hand_value.points - deal_in_prob * cost
    fold_ev = 0.0

    reasons: list[str] = []
    if own_shanten >= 2:
        reasons.append(f"自手 {own_shanten} 向聽，和了率僅約 {win_prob*100:.1f}%")
    elif own_shanten == 1:
        reasons.append(f"自手一向聽，和了率約 {win_prob*100:.0f}%")
    elif own_shanten == 0:
        reasons.append(f"自手已聽牌，和了率約 {win_prob*100:.0f}%")
    reasons.append(f"放銃率約 {deal_in_prob*100:.0f}% × 預估失點 {int(cost)}")
    reasons.append(f"和了打點預估 {int(own_hand_value.points)} 點")
    reasons.append(f"押牌期望值 {push_ev:+.0f} vs 全防 0")

    return PushFoldDecision(
        tile=assessment.tile,
        danger_score=assessment.score,
        deal_in_prob=deal_in_prob,
        win_prob=win_prob,
        push_ev=push_ev,
        fold_ev=fold_ev,
        recommend_push=push_ev > fold_ev,
        reasons=reasons,
    )
