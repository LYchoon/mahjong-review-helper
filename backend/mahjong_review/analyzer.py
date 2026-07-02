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
    assess_tile,
)
from .ev import WIN_PROB_BY_SHANTEN, PushFoldDecision, estimate_hand_value, evaluate_push
from .hand_value import quick_yaku_han
from .parsers.common import CallOpportunity
from .shanten import effective_tiles, shanten
from .tiles import Tile, tile_counts

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
    own_discards: list[Tile] = field(default_factory=list)  # for furiten detection
    meld_tiles: list[Tile] = field(default_factory=list)  # flattened own open melds
    declared_riichi_now: bool = False  # this discard is a riichi declaration


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


DecisionType = Literal["defense", "efficiency"]


@dataclass
class RiichiAdvice:
    """Riichi vs dama advice for a closed tenpai discard."""

    declared: bool  # what the hero actually did
    recommended: bool  # True = declare riichi
    reasons: list[str]


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
    decision_type: DecisionType = "defense"
    riichi_advice: RiichiAdvice | None = None


def review_decision(
    chosen_discard: Tile,
    hero: HeroState,
    threats: list[Threat],
    visible_counts: list[int],
) -> DecisionReview:
    """Produce a full review for a single discard choice.

    With threats present this is a push/fold defense review; with no threats it
    becomes a pure efficiency review (shanten / ukeire / hand value).
    """
    expected = 14 - 3 * hero.melds_count
    if len(hero.hand) not in (expected, expected - 1):
        raise ValueError(
            f"hand must have {expected - 1} or {expected} tiles "
            f"with {hero.melds_count} melds, got {len(hero.hand)}"
        )

    if not threats:
        return _review_efficiency(chosen_discard, hero, visible_counts)

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
        decision_type="defense",
        riichi_advice=_riichi_advice(hero, your_opt, visible_counts, len(threats)),
    )


def _review_efficiency(
    chosen_discard: Tile,
    hero: HeroState,
    visible_counts: list[int],
) -> DecisionReview:
    """No-threat review: rank discards purely by hand advancement value."""
    options: list[tuple[AlternativeOption, PushFoldDecision]] = []
    seen: set[int] = set()
    for t in hero.hand:
        if t.tid in seen:
            continue
        seen.add(t.tid)
        assessment = DangerAssessment(t, 0.0, [])
        opt, decision = _evaluate_discard_option(assessment, hero, None, visible_counts)
        options.append((opt, decision))

    options.sort(key=lambda od: (-od[1].push_ev, od[0].shanten_after, -od[0].ukeire))
    best_opt, best_decision = options[0]
    your_opt, your_decision = next(
        (od for od in options if od[0].tile.tid == chosen_discard.tid),
        options[-1],
    )

    ev_gap = best_decision.push_ev - your_decision.push_ev
    label = _classify(ev_gap, your_opt, best_opt)

    return DecisionReview(
        situation=f"第 {hero.turn} 巡，場上無威脅 — 進攻效率分析",
        your_choice=your_opt,
        your_decision=your_decision,
        recommendation=best_opt,
        recommendation_decision=best_decision,
        alternatives=[o for o, _ in options],
        label=label,
        summary=_summarise_efficiency(label, your_opt, best_opt, ev_gap),
        decision_type="efficiency",
        riichi_advice=_riichi_advice(hero, your_opt, visible_counts, 0),
    )


def _summarise_efficiency(
    label: Label,
    your_opt: AlternativeOption,
    best_opt: AlternativeOption,
    ev_gap: float,
) -> str:
    def shape(opt: AlternativeOption) -> str:
        parts = [f"切後{_shanten_word(opt.shanten_after)}"]
        if opt.ukeire > 0:
            parts.append(f"進張 {opt.ukeire} 枚")
        return "、".join(parts)

    if label == "best":
        return f"打 {your_opt.tile} 是效率最佳選擇 ({shape(your_opt)})。"
    if label == "good":
        return (
            f"打 {your_opt.tile} 不差 ({shape(your_opt)})，"
            f"但 {best_opt.tile} 略優 ({shape(best_opt)}，期望值差 {ev_gap:+.0f})。"
        )
    return (
        f"打 {your_opt.tile} 拖慢了手牌 ({shape(your_opt)})；"
        f"建議改打 {best_opt.tile} ({shape(best_opt)})，期望值多 {ev_gap:.0f}。"
    )


def _shanten_word(sh: int) -> str:
    if sh < 0:
        return "已和"
    if sh == 0:
        return "聽牌"
    return f"{sh} 向聽"


_REAL_YAKU_TAGS = ("斷么", "七對子路線", "混一色", "清一色", "對對和路線")


def _has_real_yaku(tags: list[str]) -> bool:
    """True if the tag list contains a yaku that allows winning without riichi
    (dora and the 1-han floor don't count)."""
    return any(t in _REAL_YAKU_TAGS or t.startswith("役牌×3") for t in tags)


def _riichi_advice(
    hero: HeroState,
    your_opt: AlternativeOption,
    visible_counts: list[int],
    threats_count: int,
) -> RiichiAdvice | None:
    """Riichi vs dama advice when the chosen discard leaves a closed tenpai."""
    if hero.melds_count != 0 or your_opt.shanten_after != 0:
        return None
    after_hand = _hand_without(hero.hand, your_opt.tile)
    if len(after_hand) != 13:
        return None

    waits = effective_tiles(after_hand, 0)
    live_waits = sum(max(0, 4 - visible_counts[t]) for t in waits)
    own_tids = {t.tid for t in hero.own_discards} | {your_opt.tile.tid}
    furiten = bool(set(waits) & own_tids)

    common = dict(
        melds_count=0,
        is_dealer=hero.is_dealer,
        round_wind_tid=hero.round_wind,
        seat_wind_tid=hero.seat_wind,
        dora_count=hero.dora_count,
    )
    riichi_han, _ = quick_yaku_han(after_hand, likely_to_riichi=True, **common)
    dama_han, dama_tags = quick_yaku_han(after_hand, likely_to_riichi=False, **common)
    dama_has_yaku = _has_real_yaku(dama_tags)
    riichi_value = estimate_hand_value(riichi_han, is_dealer=hero.is_dealer).points

    reasons = [f"待牌 {len(waits)} 種 / 場上還剩 {live_waits} 枚"]
    if furiten:
        recommended = False
        reasons.append("待牌振聽 — 立直後只能自摸；默聽保留換聽彈性")
    elif not dama_has_yaku:
        recommended = True
        reasons.append("默聽無役 (榮和不可，只能門清自摸) — 立直補上役與打點")
    elif dama_han >= 4:
        recommended = False
        reasons.append(f"默聽已約 {dama_han} 翻且有役 — 隱藏聽牌、保留自由度價值更高")
    elif threats_count > 0 and riichi_value < 3900 and live_waits <= 4:
        recommended = False
        reasons.append("場上已有威脅、手牌便宜且待牌薄 — 不值得立直對衝")
    else:
        recommended = True
        reasons.append(
            f"標準立直 (+1 翻 + 裏寶期望 + 施壓)，立直線估值約 {int(riichi_value)} 點"
        )
    return RiichiAdvice(
        declared=hero.declared_riichi_now,
        recommended=recommended,
        reasons=reasons,
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
    threat: Threat | None,
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
        eff: dict[int, int] = {}
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
        meld_tiles=hero.meld_tiles,
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

    # hero furiten: tenpai but a winning tile is in our own pond (or is the tile
    # we are discarding right now) → cannot ron, only tsumo wins
    if sh == 0 and eff:
        own_tids = {t.tid for t in hero.own_discards}
        own_tids.add(assessment.tile.tid)
        if set(eff) & own_tids:
            decision.win_prob *= 0.35
            decision.recompute()
            decision.reasons.append("振聽 — 待牌在自家河中，榮和不可 (只能自摸)")

    # future safety: count tiles still in hand whose danger is ≤30
    if threat is None:
        future_safe = len(after_hand)
    else:
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
    biggest_blunder_index: int | None = None
    defense_total: int = 0
    efficiency_total: int = 0

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
    for i, r in enumerate(reviews):
        bucket = getattr(summary, r.label)
        setattr(summary, r.label, bucket + 1)
        if r.decision_type == "defense":
            summary.defense_total += 1
        else:
            summary.efficiency_total += 1
        gap = r.recommendation_decision.push_ev - r.your_decision.push_ev
        summary.total_ev_lost += max(0.0, gap)
        if gap > biggest_gap:
            biggest_gap = gap
            summary.biggest_blunder = r
            summary.biggest_blunder_index = i
    return summary


# ---- call (chi/pon) review ----


@dataclass
class CallReview:
    """Review of one call opportunity (taken or passed)."""

    round_number: int
    turn: int
    tile: Tile
    kind: str  # "pon" | "chi" — best available call shape
    actual: str  # "called" | "passed"
    recommended: str  # "call" | "pass"
    label: Label
    reasons: list[str]
    shanten_before: int
    shanten_after: int  # best shanten reachable by calling (then discarding)
    ev_call: float = 0.0  # rough EV of the calling line
    ev_pass: float = 0.0  # rough EV of staying closed/passing


def review_call(opp: CallOpportunity, seat_wind: int = 27) -> CallReview | None:
    """Judge whether calling the discarded tile was (or would have been) good.

    Heuristic: a call is worth it when it secures a yakuhai yaku without losing
    tempo, or advances shanten while a real yaku remains available. Otherwise
    passing keeps the closed-hand (riichi / menzen tsumo) value.
    """
    hand = opp.hero_hand
    m = opp.hero_melds_count
    if len(hand) != 13 - 3 * m:
        return None
    sh_before = shanten(hand, m)
    tile = opp.tile

    variants: list[tuple[str, list[Tile]]] = []
    if opp.can_pon:
        same = [t for t in hand if t.tid == tile.tid][:2]
        if len(same) == 2:
            variants.append(("pon", same))
    if opp.can_chi:
        r = tile.rank
        suit_off = tile.tid - (r - 1)
        for a, b in ((r - 2, r - 1), (r - 1, r + 1), (r + 1, r + 2)):
            if not (1 <= a <= 9 and 1 <= b <= 9):
                continue
            ta = next((t for t in hand if t.tid == suit_off + a - 1), None)
            tb = next((t for t in hand if t.tid == suit_off + b - 1), None)
            if ta is not None and tb is not None:
                variants.append(("chi", [ta, tb]))
    if not variants:
        return None

    # (shanten, no_yaku, kind, has_yaku, after_hand, call_han)
    best: tuple[int, int, str, bool, list[Tile], int] | None = None
    for kind, used in variants:
        remaining = list(hand)
        for u in used:
            remaining.remove(u)
        # after calling, the hero must discard: take the best resulting shanten
        best_sh = 99
        best_after: list[Tile] | None = None
        seen: set[int] = set()
        for i, d in enumerate(remaining):
            if d.tid in seen:
                continue
            seen.add(d.tid)
            after = remaining[:i] + remaining[i + 1 :]
            sh = shanten(after, m + 1)
            if sh < best_sh:
                best_sh = sh
                best_after = after
        if best_after is None:
            continue
        call_han, tags = quick_yaku_han(
            best_after,
            melds_count=m + 1,
            round_wind_tid=opp.round_wind,
            seat_wind_tid=seat_wind,
            likely_to_riichi=False,
            meld_tiles=opp.hero_meld_tiles + used + [tile],
        )
        has_yaku = _has_real_yaku(tags)
        cand = (best_sh, 0 if has_yaku else 1, kind, has_yaku, best_after, call_han)
        if best is None or cand[:2] < best[:2]:
            best = cand
    if best is None:
        return None
    sh_after, _, kind, has_yaku, call_after, call_han = best

    # quantify both lines: rough EV = win_prob(shanten, ukeire) × hand value
    pass_han, _ = quick_yaku_han(
        hand,
        melds_count=m,
        round_wind_tid=opp.round_wind,
        seat_wind_tid=seat_wind,
        likely_to_riichi=(m == 0 and sh_before <= 1),
        meld_tiles=opp.hero_meld_tiles,
    )
    ev_pass = _line_ev(hand, m, sh_before, pass_han)
    ev_call = _line_ev(call_after, m + 1, sh_after, call_han if has_yaku else 1)
    if not has_yaku:
        ev_call = 0.0  # a yaku-less open hand cannot win

    yakuhai_tids = {31, 32, 33, opp.round_wind, seat_wind}
    is_yakuhai_pon = kind == "pon" and tile.tid in yakuhai_tids
    closed_tenpai = sh_before == 0 and m == 0

    reasons: list[str] = []
    if closed_tenpai:
        recommended = "pass"
        reasons.append("已是門清聽牌 — 保留立直/門清價值，不需副露")
    elif not has_yaku:
        recommended = "pass"
        reasons.append("鳴了之後沒有確定役 — 副露會斷送立直/門清自摸路線")
    elif is_yakuhai_pon and sh_after <= sh_before:
        recommended = "call"
        reasons.append(f"碰 {tile} 直接確保役牌役 (向聽 {sh_before} → {sh_after})")
    elif ev_call > ev_pass:
        recommended = "call"
        reasons.append(f"鳴後向聽 {sh_before} → {sh_after}，期望值支持鳴牌")
    else:
        recommended = "pass"
        reasons.append(
            f"鳴牌加速有限 (向聽 {sh_before} → {sh_after})，門清線期望值更高"
        )
    reasons.append(f"鳴線 EV {ev_call:+.0f} vs 過線 EV {ev_pass:+.0f}")
    if opp.threats_count > 0:
        reasons.append("場上已有威脅，鳴牌前先評估防守")

    actual = "called" if opp.called else "passed"
    agree = (actual == "called") == (recommended == "call")
    if agree:
        label: Label = "best"
    elif opp.called and not has_yaku:
        label = "mistake"
        reasons.append("實際鳴了 — 無役副露很難和牌")
    elif not opp.called and is_yakuhai_pon and sh_after == 0 and sh_before > 0:
        label = "mistake"
        reasons.append("漏掉役牌碰直接聽牌的機會")
    else:
        label = "inaccuracy"

    return CallReview(
        round_number=opp.round_number,
        turn=opp.turn,
        tile=tile,
        kind=kind,
        actual=actual,
        recommended=recommended,
        label=label,
        reasons=reasons,
        shanten_before=sh_before,
        shanten_after=sh_after,
        ev_call=round(ev_call, 0),
        ev_pass=round(ev_pass, 0),
    )


def _line_ev(concealed: list[Tile], melds: int, sh: int, han: int) -> float:
    """Rough line EV for the call decision: win_prob(shanten, ukeire) × value.

    Uses raw 4-per-type ukeire (no table visibility) — both lines share the
    same approximation, so the comparison stays fair.
    """
    win = WIN_PROB_BY_SHANTEN.get(min(sh, 4), 0.0)
    if sh > 0 and len(concealed) == 13 - 3 * melds:
        counts = tile_counts(concealed)
        eff = effective_tiles(concealed, melds)
        ukeire = sum(max(0, 4 - counts[t]) for t in eff)
        if ukeire > 0:
            win *= min(1.5, max(0.3, ukeire / 8.0))
    return win * estimate_hand_value(han).points
