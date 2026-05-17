"""Decision analyser.

Given a snapshot of the game at a moment our hero must discard, decide whether
their choice was good, and produce a chess.com-style review:

    {
      "situation": "...",
      "your_choice": {"tile": "5m", "danger": 62, "verdict": "危險", "factors": [...]},
      "recommendation": {"tile": "1z", "danger": 8, "action": "betaori", "reasons": [...]},
      "alternatives": [ ... every tile ranked by safety + EV ... ],
      "label": "blunder" | "mistake" | "inaccuracy" | "ok" | "best"
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .danger import (
    DangerAssessment,
    DangerFactor,
    Threat,
    assess_hand,
    assess_tile,
)
from .ev import HandValue, PushFoldDecision, estimate_hand_value, evaluate_push
from .shanten import shanten
from .tiles import Tile, tile_counts


Label = Literal["best", "good", "inaccuracy", "mistake", "blunder"]


@dataclass
class HeroState:
    """Our (the reviewed player's) state at a decision point."""

    seat: int  # 0..3
    hand: list[Tile]  # 13 or 14 tiles (concealed)
    melds_count: int = 0
    dora_count: int = 0  # red 5s + indicator-derived dora in hand
    is_dealer: bool = False
    turn: int = 1
    turns_remaining: int = 10  # rough
    round_wind: int = 27  # E


@dataclass
class AlternativeOption:
    tile: Tile
    danger: float
    verdict: str
    push_ev: float
    win_prob: float
    factors: list[DangerFactor]


@dataclass
class DecisionReview:
    situation: str
    your_choice: AlternativeOption
    your_decision: PushFoldDecision
    recommendation: AlternativeOption
    recommendation_decision: PushFoldDecision
    alternatives: list[AlternativeOption]
    label: Label
    summary: str


def review_decision(
    chosen_discard: Tile,
    hero: HeroState,
    threats: list[Threat],
    visible_counts: list[int],
) -> DecisionReview:
    """Produce a full review for a single discard choice."""
    if len(hero.hand) not in (13, 14):
        raise ValueError(f"hand must have 13 or 14 tiles, got {len(hero.hand)}")

    # Use the most threatening opponent (highest avg danger across hand).
    threat = _pick_primary_threat(threats, hero.hand, visible_counts, hero.round_wind)

    # Score every tile in hand against this threat.
    assessments_by_tid: dict[int, DangerAssessment] = {}
    for t in hero.hand:
        if t.tid in assessments_by_tid:
            continue
        assessments_by_tid[t.tid] = assess_tile(
            t, threat, visible_counts, hero.round_wind
        )

    # Compute push EV for every choice — but we need shanten *after* discarding.
    chosen_assessment = assessments_by_tid[chosen_discard.tid]
    options: list[tuple[AlternativeOption, PushFoldDecision]] = []
    for tid, asmt in assessments_by_tid.items():
        opt, decision = _evaluate_discard_option(
            asmt, hero, threat
        )
        options.append((opt, decision))

    # rank: higher push_ev wins; ties broken by lower danger
    options.sort(key=lambda od: (-od[1].push_ev, od[0].danger))

    best_opt, best_decision = options[0]

    # find user's choice in our table
    your_pair = next(
        (od for od in options if od[0].tile.tid == chosen_discard.tid),
        options[-1],
    )
    your_opt, your_decision = your_pair

    # label
    ev_gap = best_decision.push_ev - your_decision.push_ev
    label = _classify(ev_gap, your_opt.danger, best_opt.danger)

    situation = _describe_situation(threat, hero)
    summary = _summarise(label, your_opt, best_opt, ev_gap)

    return DecisionReview(
        situation=situation,
        your_choice=your_opt,
        your_decision=your_decision,
        recommendation=best_opt,
        recommendation_decision=best_decision,
        alternatives=[o for o, _ in options],
        label=label,
        summary=summary,
    )


def _pick_primary_threat(
    threats: list[Threat],
    hand: list[Tile],
    visible_counts: list[int],
    round_wind: int,
) -> Threat:
    if not threats:
        raise ValueError("no threats provided — defense review requires at least one threat")
    if len(threats) == 1:
        return threats[0]
    # primary = the threat where our average danger across hand is highest
    def avg_danger(th: Threat) -> float:
        scores = [
            assess_tile(t, th, visible_counts, round_wind).score for t in hand
        ]
        return sum(scores) / max(len(scores), 1)

    return max(threats, key=avg_danger)


def _evaluate_discard_option(
    assessment: DangerAssessment,
    hero: HeroState,
    threat: Threat,
) -> tuple[AlternativeOption, PushFoldDecision]:
    after_hand = _hand_without(hero.hand, assessment.tile)
    sh = shanten(after_hand, hero.melds_count)

    # estimate value: 1 (riichi if closed) + 1 (tsumo/dora bias) + dora_count
    han_est = hero.dora_count + (1 if hero.melds_count == 0 else 0) + 1
    value = estimate_hand_value(han_est, is_dealer=hero.is_dealer)
    decision = evaluate_push(
        assessment, threat, sh, value, turns_remaining=hero.turns_remaining
    )
    opt = AlternativeOption(
        tile=assessment.tile,
        danger=assessment.score,
        verdict=assessment.verdict,
        push_ev=decision.push_ev,
        win_prob=decision.win_prob,
        factors=assessment.factors,
    )
    return opt, decision


def _hand_without(hand: list[Tile], tile: Tile) -> list[Tile]:
    out = list(hand)
    for i, t in enumerate(out):
        if t.tid == tile.tid:
            del out[i]
            return out
    return out


def _classify(ev_gap: float, your_danger: float, best_danger: float) -> Label:
    if ev_gap <= 50:
        return "best"
    if ev_gap <= 300:
        return "good"
    if ev_gap <= 800:
        return "inaccuracy"
    if ev_gap <= 2000:
        return "mistake"
    return "blunder"


def _describe_situation(threat: Threat, hero: HeroState) -> str:
    rel = (threat.player - hero.seat) % 4
    rel_name = {1: "下家", 2: "對家", 3: "上家"}[rel] if rel else "自家(?)"
    kind = {
        "riichi": "立直",
        "dama_tenpai": "默聽嫌疑",
        "iishanten": "一向聽威脅",
    }[threat.kind.value]
    return f"第 {hero.turn} 巡，{rel_name} 已 {kind} ({hero.turn - threat.declared_turn + 1} 巡前)"


def _summarise(
    label: Label,
    your_opt: AlternativeOption,
    best_opt: AlternativeOption,
    ev_gap: float,
) -> str:
    if label == "best":
        return f"打 {your_opt.tile} 是最佳選擇 (危險 {your_opt.danger:.0f})。"
    if label == "good":
        return (
            f"打 {your_opt.tile} 不差，但 {best_opt.tile} 略優 "
            f"(期望值差 {ev_gap:+.0f})。"
        )
    if label == "inaccuracy":
        return (
            f"打 {your_opt.tile} 是 inaccuracy — 危險度 {your_opt.danger:.0f}，"
            f"建議改打 {best_opt.tile} (危險 {best_opt.danger:.0f})，期望值多 {ev_gap:.0f}。"
        )
    if label == "mistake":
        return (
            f"打 {your_opt.tile} 是失誤 — 危險度 {your_opt.danger:.0f}，"
            f"應該打 {best_opt.tile} (危險 {best_opt.danger:.0f})。"
        )
    return (
        f"打 {your_opt.tile} 是嚴重失誤 (blunder) — 危險度 {your_opt.danger:.0f}，"
        f"幾乎必中。應全力 betaori，選 {best_opt.tile} (危險 {best_opt.danger:.0f})。"
    )
