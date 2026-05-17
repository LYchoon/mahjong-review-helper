"""Decision analyser.

Given a snapshot of the game at a moment our hero must discard, decide whether
their choice was good, and produce a chess.com-style review.

Per-option scoring:
    push_ev   = win_prob × est_value - deal_in_prob × est_cost
    fold_ev   = 0 (baseline — full betaori sacrifices any chance)
    win_prob  scales with shanten AND with ukeire (effective tile count remaining)
    we also produce future_safety: how many tiles in hand are still safe-ish if we
      have to keep defending next turn

Output: best > good > inaccuracy > mistake > blunder labels with concrete reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .danger import (
    DangerAssessment,
    DangerFactor,
    Threat,
    ThreatKind,
    assess_tile,
)
from .ev import HandValue, PushFoldDecision, estimate_hand_value, evaluate_push
from .hand_value import quick_yaku_han
from .shanten import effective_tiles, shanten
from .tiles import Tile


Label = Literal["best", "good", "inaccuracy", "mistake", "blunder"]


@dataclass
class HeroState:
    """Our (the reviewed player's) state at a decision point."""

    seat: int  # 0..3
    hand: list[Tile]  # 13 or 14 tiles (concealed)
    melds_count: int = 0
    dora_count: int = 0
    is_dealer: bool = False
    turn: int = 1
    turns_remaining: int = 10
    round_wind: int = 27  # E
    seat_wind: int = 27  # default E; analyzer derives proper value when given


@dataclass
class AlternativeOption:
    tile: Tile
    danger: float
    verdict: str
    push_ev: float
    win_prob: float
    factors: list[DangerFactor]
    shanten_after: int  # shanten of the hand after this discard
    ukeire: int  # remaining useful tiles to advance (0 if win/no progress)
    effective_tile_ids: list[int]  # tile ids that advance the hand after this discard
    future_safe_tiles: int  # how many tiles still ≤30 danger left in hand
    han_estimate: int
    yaku_tags: list[str]


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

    primary = _pick_primary_threat(threats, hero.hand, visible_counts, hero.round_wind)

    # danger per distinct tile: combine across all threats (1 - prod of survival probs)
    assessments_by_tid: dict[int, DangerAssessment] = {}
    for t in hero.hand:
        if t.tid in assessments_by_tid:
            continue
        assessments_by_tid[t.tid] = _combined_assessment(
            t, threats, visible_counts, hero.round_wind
        )

    # evaluate every discard option using the primary threat for EV reference cost
    options: list[tuple[AlternativeOption, PushFoldDecision]] = []
    for asmt in assessments_by_tid.values():
        opt, decision = _evaluate_discard_option(asmt, hero, primary, visible_counts)
        options.append((opt, decision))

    # rank: higher EV first; tie-break by lower danger
    options.sort(key=lambda od: (-od[1].push_ev, od[0].danger))
    best_opt, best_decision = options[0]
    your_opt, your_decision = next(
        (od for od in options if od[0].tile.tid == chosen_discard.tid),
        options[-1],
    )

    ev_gap = best_decision.push_ev - your_decision.push_ev
    label = _classify(ev_gap, your_opt, best_opt)

    return DecisionReview(
        situation=_describe_situation(primary, hero, threats),
        your_choice=your_opt,
        your_decision=your_decision,
        recommendation=best_opt,
        recommendation_decision=best_decision,
        alternatives=[o for o, _ in options],
        label=label,
        summary=_summarise(label, your_opt, best_opt, ev_gap),
    )


def _combined_assessment(
    tile: Tile,
    threats: list[Threat],
    visible_counts: list[int],
    round_wind: int,
) -> DangerAssessment:
    """Combine per-threat danger using independent-deal-in approximation:
        combined_danger = 1 - prod(1 - p_i)   (scaled to 0..100)
    Reports factors per-threat, prefixed with which seat they came from.
    """
    per_threat = []
    for th in threats:
        a = assess_tile(tile, th, visible_counts, round_wind)
        per_threat.append((th, a))
    if not per_threat:
        return assess_tile(tile, threats[0], visible_counts, round_wind)

    if len(per_threat) == 1:
        return per_threat[0][1]

    survival = 1.0
    factors: list[DangerFactor] = []
    for th, a in per_threat:
        survival *= 1.0 - (a.score / 100.0)
        rel = f"P{th.player}"
        for f in a.factors:
            factors.append(
                DangerFactor(
                    code=f"{f.code}_{rel}",
                    label=f"[{rel}] {f.label}",
                    delta=f.delta,
                )
            )
    combined = max(0.0, min(100.0, (1.0 - survival) * 100.0))
    factors.insert(
        0,
        DangerFactor("MULTI_THREAT", f"多家威脅合計 ({len(per_threat)} 家)", 0.0),
    )
    return DangerAssessment(tile, combined, factors)


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

    def avg_danger(th: Threat) -> float:
        scores = [assess_tile(t, th, visible_counts, round_wind).score for t in hand]
        return sum(scores) / max(len(scores), 1)

    return max(threats, key=avg_danger)


def _evaluate_discard_option(
    assessment: DangerAssessment,
    hero: HeroState,
    threat: Threat,
    visible_counts: list[int],
) -> tuple[AlternativeOption, PushFoldDecision]:
    after_hand = _hand_without(hero.hand, assessment.tile)
    sh = shanten(after_hand, hero.melds_count)

    # ukeire: useful tiles to advance, counting only what's still unseen
    if sh >= 0 and len(after_hand) == 13 - 3 * hero.melds_count:
        eff = effective_tiles(after_hand, hero.melds_count)
        effective_ids = [t for t in eff if (4 - visible_counts[t]) > 0]
        ukeire = sum(max(0, 4 - visible_counts[t]) for t in eff)
    else:
        effective_ids = []
        ukeire = 0

    # yaku & value
    han_est, tags = quick_yaku_han(
        after_hand,
        melds_count=hero.melds_count,
        is_dealer=hero.is_dealer,
        round_wind_tid=hero.round_wind,
        seat_wind_tid=hero.seat_wind,
        dora_count=hero.dora_count,
        likely_to_riichi=(hero.melds_count == 0 and sh <= 1),
    )
    value = estimate_hand_value(han_est, is_dealer=hero.is_dealer)

    # adjust win probability by ukeire (a 1-shanten with 30 useful tiles is much better
    # than a 1-shanten with 4). Cap at 1.5x boost / 0.4x penalty around baseline of 8 tiles.
    decision = evaluate_push(
        assessment, threat, sh, value, turns_remaining=hero.turns_remaining
    )
    if sh > 0 and ukeire > 0:
        adj = min(1.5, max(0.3, ukeire / 8.0))
        decision.win_prob *= adj
        decision.recompute()
        decision.reasons.append(
            f"剩餘有效進張 {ukeire} 枚 (調整後和率 {decision.win_prob*100:.1f}%)"
        )

    # future safety: count tiles still in hand whose danger is ≤30
    future_safe = sum(
        1
        for t in after_hand
        if assess_tile(t, threat, visible_counts, hero.round_wind).score <= 30
    )

    opt = AlternativeOption(
        tile=assessment.tile,
        danger=assessment.score,
        verdict=assessment.verdict,
        push_ev=decision.push_ev,
        win_prob=decision.win_prob,
        factors=assessment.factors,
        shanten_after=sh,
        ukeire=ukeire,
        effective_tile_ids=effective_ids,
        future_safe_tiles=future_safe,
        han_estimate=han_est,
        yaku_tags=tags,
    )
    return opt, decision


def _hand_without(hand: list[Tile], tile: Tile) -> list[Tile]:
    out = list(hand)
    for i, t in enumerate(out):
        if t.tid == tile.tid:
            del out[i]
            return out
    return out


def _classify(ev_gap: float, your_opt: AlternativeOption, best_opt: AlternativeOption) -> Label:
    """Classify the choice quality.

    Uses absolute EV gap *and* danger gap as a sanity check — a tiny EV gap that
    nonetheless adds 40+ danger points should still register as inaccuracy at minimum.
    """
    danger_gap = your_opt.danger - best_opt.danger
    if ev_gap <= 80 and danger_gap < 15:
        return "best"
    if ev_gap <= 300 and danger_gap < 25:
        return "good"
    if ev_gap <= 900 and danger_gap < 45:
        return "inaccuracy"
    if ev_gap <= 2500:
        return "mistake"
    return "blunder"


def _describe_situation(
    primary: Threat, hero: HeroState, all_threats: list[Threat]
) -> str:
    def describe(th: Threat) -> str:
        rel = (th.player - hero.seat) % 4
        rel_name = {1: "下家", 2: "對家", 3: "上家"}.get(rel, "自家(?)")
        kind = {
            "riichi": "立直",
            "dama_tenpai": "默聽嫌疑",
            "iishanten": "一向聽威脅",
        }[th.kind.value]
        ago = max(1, hero.turn - th.declared_turn + 1)
        return f"{rel_name} {kind} ({ago} 巡前)"

    parts = [f"第 {hero.turn} 巡，{describe(primary)}"]
    if len(all_threats) > 1:
        others = [describe(t) for t in all_threats if t is not primary]
        parts.append(f"另有威脅: {', '.join(others)}")
    return "；".join(parts)


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


# ---- game-level summary ----


@dataclass
class GameSummary:
    """Aggregate stats across all defense decisions in a game."""

    total: int = 0
    best: int = 0
    good: int = 0
    inaccuracy: int = 0
    mistake: int = 0
    blunder: int = 0
    total_ev_lost: float = 0.0
    biggest_blunder: DecisionReview | None = None

    @property
    def accuracy(self) -> float:
        """chess.com-style 0..100 score weighted toward severe errors."""
        if self.total == 0:
            return 100.0
        weights = {"best": 1.0, "good": 0.9, "inaccuracy": 0.6, "mistake": 0.3, "blunder": 0.0}
        weighted = (
            self.best * weights["best"]
            + self.good * weights["good"]
            + self.inaccuracy * weights["inaccuracy"]
            + self.mistake * weights["mistake"]
            + self.blunder * weights["blunder"]
        )
        return round(weighted / self.total * 100, 1)


def summarise_game(reviews: list[DecisionReview]) -> GameSummary:
    summary = GameSummary(total=len(reviews))
    biggest_gap = 0.0
    for r in reviews:
        bucket = getattr(summary, r.label)
        setattr(summary, r.label, bucket + 1)
        gap = r.recommendation_decision.push_ev - r.your_decision.push_ev
        summary.total_ev_lost += max(0.0, gap)
        if gap > biggest_gap:
            biggest_gap = gap
            summary.biggest_blunder = r
    return summary
