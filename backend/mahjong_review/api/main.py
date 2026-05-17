"""FastAPI endpoints for the review system."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..analyzer import (
    DecisionReview,
    GameSummary,
    HeroState,
    review_decision,
    summarise_game,
)
from ..danger import Threat, ThreatKind
from ..parsers.tenhou import Snapshot, parse_tenhou_log
from ..shanten import shanten as compute_shanten
from ..tiles import Tile, tile_counts, tiles_from_str

app = FastAPI(title="Mahjong Review Helper", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------- request / response models --------


class TenhouReviewRequest(BaseModel):
    log: dict[str, Any] = Field(..., description="parsed tenhou JSON log object")
    hero_seat: int = Field(..., ge=0, le=3)


class ThreatModel(BaseModel):
    player: int
    kind: str  # "riichi" | "dama_tenpai" | "iishanten"
    declared_turn: int
    discards: list[str] = Field(default_factory=list)
    discards_after_threat: list[str] = Field(default_factory=list)


class ManualReviewRequest(BaseModel):
    hand: str = Field(..., description="e.g. '123m 456p 789s 11z 5p'")
    chosen_discard: str
    melds_count: int = 0
    dora_count: int = 0
    is_dealer: bool = False
    turn: int = 6
    turns_remaining: int = 10
    round_wind_tile: str = "1z"  # E by default
    hero_seat: int = 0
    threats: list[ThreatModel]
    visible_tiles: str = Field(
        default="",
        description="all other visible tiles (everyone's discards + dora indicators); "
        "ours is auto-counted from `hand`",
    )


class FactorOut(BaseModel):
    code: str
    label: str
    delta: float


class AlternativeOut(BaseModel):
    tile: str
    danger: float
    verdict: str
    push_ev: float
    win_prob: float
    factors: list[FactorOut]
    shanten_after: int
    ukeire: int
    future_safe_tiles: int
    han_estimate: int
    yaku_tags: list[str]


class BoardStateOut(BaseModel):
    round_label: str
    turn: int
    hero_seat: int
    hero_hand: list[str]
    discards: list[list[str]]  # 4 piles
    riichi_turns: list[int | None]
    dora_indicators: list[str]
    threats: list[dict[str, object]]


class DecisionReviewOut(BaseModel):
    situation: str
    label: str
    summary: str
    your_choice: AlternativeOut
    recommendation: AlternativeOut
    alternatives: list[AlternativeOut]
    your_push_ev: float
    your_win_prob: float
    recommendation_push_ev: float
    recommendation_win_prob: float
    your_reasons: list[str]
    recommendation_reasons: list[str]
    board: BoardStateOut | None = None


class GameSummaryOut(BaseModel):
    total: int
    best: int
    good: int
    inaccuracy: int
    mistake: int
    blunder: int
    accuracy: float
    total_ev_lost: float
    biggest_blunder_index: int | None  # index into decisions list


class TenhouReviewResponse(BaseModel):
    hero_seat: int
    decisions: list[DecisionReviewOut]
    summary: GameSummaryOut


# -------- routes --------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/review/manual", response_model=DecisionReviewOut)
def review_manual(req: ManualReviewRequest) -> DecisionReviewOut:
    try:
        hand = tiles_from_str(req.hand)
        chosen = tiles_from_str(req.chosen_discard)
        if len(chosen) != 1:
            raise ValueError("chosen_discard must be exactly one tile")
        chosen_t = chosen[0]
        round_wind_t = tiles_from_str(req.round_wind_tile)[0]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    visible = list(tile_counts(hand))
    for t in tiles_from_str(req.visible_tiles):
        visible[t.tid] += 1

    threats = []
    for tm in req.threats:
        try:
            kind = ThreatKind(tm.kind)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"unknown threat kind {tm.kind}")
        threats.append(
            Threat(
                player=tm.player,
                kind=kind,
                declared_turn=tm.declared_turn,
                discards=tiles_from_str(" ".join(tm.discards)),
                discards_after_threat=tiles_from_str(" ".join(tm.discards_after_threat)),
            )
        )
    if not threats:
        raise HTTPException(status_code=400, detail="defense review requires at least one threat")

    hero = HeroState(
        seat=req.hero_seat,
        hand=hand,
        melds_count=req.melds_count,
        dora_count=req.dora_count,
        is_dealer=req.is_dealer,
        turn=req.turn,
        turns_remaining=req.turns_remaining,
        round_wind=round_wind_t.tid,
    )
    review = review_decision(chosen_t, hero, threats, visible)
    return _serialize_review(review)


@app.post("/review/tenhou", response_model=TenhouReviewResponse)
def review_tenhou(req: TenhouReviewRequest) -> TenhouReviewResponse:
    try:
        snapshots = parse_tenhou_log(req.log, req.hero_seat)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"tenhou parse failed: {e}")

    decisions_out: list[DecisionReviewOut] = []
    reviews: list[DecisionReview] = []
    for snap in snapshots:
        hero = HeroState(
            seat=snap.hero_seat,
            hand=snap.hero_hand,
            melds_count=snap.hero_melds_count,
            dora_count=_count_dora(snap),
            is_dealer=(req.hero_seat == snap.round_index % 4),
            turn=snap.turn,
            turns_remaining=max(1, 18 - snap.turn),
            round_wind=snap.round_wind,
            seat_wind=27 + ((req.hero_seat - snap.round_index) % 4),
        )
        try:
            review = review_decision(
                snap.hero_chosen_discard, hero, snap.threats, snap.visible_counts
            )
        except Exception:
            continue
        reviews.append(review)
        out = _serialize_review(review)
        out.board = _board_from_snapshot(snap)
        decisions_out.append(out)

    summary = summarise_game(reviews)
    biggest_idx = (
        reviews.index(summary.biggest_blunder) if summary.biggest_blunder else None
    )
    summary_out = GameSummaryOut(
        total=summary.total,
        best=summary.best,
        good=summary.good,
        inaccuracy=summary.inaccuracy,
        mistake=summary.mistake,
        blunder=summary.blunder,
        accuracy=summary.accuracy,
        total_ev_lost=round(summary.total_ev_lost, 0),
        biggest_blunder_index=biggest_idx,
    )

    return TenhouReviewResponse(
        hero_seat=req.hero_seat, decisions=decisions_out, summary=summary_out
    )


# -------- helpers --------


def _count_dora(snap: Snapshot) -> int:
    """Count dora in hero's hand (red 5s + indicator-derived)."""
    n = 0
    for t in snap.hero_hand:
        if t.red:
            n += 1
    indicator_doras = {_next_tile_id(i.tid) for i in snap.dora_indicators}
    for t in snap.hero_hand:
        if t.tid in indicator_doras:
            n += 1
    return n


_ROUND_LABELS = ["東1", "東2", "東3", "東4", "南1", "南2", "南3", "南4"]


def _board_from_snapshot(snap: Snapshot) -> BoardStateOut:
    return BoardStateOut(
        round_label=_ROUND_LABELS[snap.round_index]
        if snap.round_index < len(_ROUND_LABELS)
        else f"R{snap.round_index + 1}",
        turn=snap.turn,
        hero_seat=snap.hero_seat,
        hero_hand=[str(t) for t in snap.hero_hand],
        discards=[[str(t) for t in pile] for pile in snap.all_discards],
        riichi_turns=list(snap.riichi_turns),
        dora_indicators=[str(t) for t in snap.dora_indicators],
        threats=[
            {
                "player": t.player,
                "kind": t.kind.value,
                "declared_turn": t.declared_turn,
            }
            for t in snap.threats
        ],
    )


def _next_tile_id(indicator_tid: int) -> int:
    """Dora is the tile *after* the indicator (wraps within suit/honor group)."""
    if indicator_tid < 9:
        return (indicator_tid + 1) % 9
    if indicator_tid < 18:
        return 9 + (indicator_tid + 1 - 9) % 9
    if indicator_tid < 27:
        return 18 + (indicator_tid + 1 - 18) % 9
    if indicator_tid < 31:
        return 27 + (indicator_tid + 1 - 27) % 4  # winds cycle E S W N
    return 31 + (indicator_tid + 1 - 31) % 3  # dragons cycle Haku Hatsu Chun


def _serialize_review(r: DecisionReview) -> DecisionReviewOut:
    def alt(a) -> AlternativeOut:
        return AlternativeOut(
            tile=str(a.tile),
            danger=round(a.danger, 1),
            verdict=a.verdict,
            push_ev=round(a.push_ev, 0),
            win_prob=round(a.win_prob, 3),
            factors=[FactorOut(code=f.code, label=f.label, delta=f.delta) for f in a.factors],
            shanten_after=a.shanten_after,
            ukeire=a.ukeire,
            future_safe_tiles=a.future_safe_tiles,
            han_estimate=a.han_estimate,
            yaku_tags=a.yaku_tags,
        )

    return DecisionReviewOut(
        situation=r.situation,
        label=r.label,
        summary=r.summary,
        your_choice=alt(r.your_choice),
        recommendation=alt(r.recommendation),
        alternatives=[alt(a) for a in r.alternatives],
        your_push_ev=round(r.your_decision.push_ev, 0),
        your_win_prob=round(r.your_decision.win_prob, 3),
        recommendation_push_ev=round(r.recommendation_decision.push_ev, 0),
        recommendation_win_prob=round(r.recommendation_decision.win_prob, 3),
        your_reasons=r.your_decision.reasons,
        recommendation_reasons=r.recommendation_decision.reasons,
    )
