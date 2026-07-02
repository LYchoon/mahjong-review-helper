"""Shared parser output types and threat heuristics.

Every log parser (tenhou, majsoul, ...) replays a game and emits a stream of
`Snapshot` objects — one per hero discard where at least one opponent threat
exists. The analyser consumes snapshots without caring which client produced
the log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..danger import Threat, ThreatKind
from ..tiles import Tile


@dataclass
class Snapshot:
    """A single hero-discard decision point."""

    round_index: int  # 0-based position of this round within the log array
    round_number: int  # round id: 0..3 = E1..E4, 4..7 = S1..S4 (dealer = number % 4)
    round_wind: int  # 27=E, 28=S, ...
    honba: int
    riichi_sticks: int
    turn: int  # 1-based turn of this round (hero discards count)
    hero_seat: int  # 0..3
    hero_hand: list[Tile]  # hand right before discard (concealed, incl. draw)
    hero_melds_count: int
    hero_chosen_discard: Tile  # the tile the hero actually chose
    visible_counts: list[int]
    threats: list[Threat]
    dora_indicators: list[Tile]
    all_discards: list[list[Tile]] = field(default_factory=list)
    riichi_turns: list[int | None] = field(default_factory=list)
    open_melds: list[list[list[Tile]]] = field(default_factory=list)  # [seat][meld_idx][tiles]


def build_threats(
    hero_seat: int,
    discard_piles: list[list[Tile]],
    discards_after_riichi: list[list[Tile]],
    riichi_declared_turn: list[int | None],
    melds_count: list[int],
    dora_indicators: list[Tile],
    open_melds: list[list[list[Tile]]] | None = None,
) -> list[Threat]:
    threats: list[Threat] = []
    open_melds = open_melds or [[] for _ in range(4)]
    for seat in range(4):
        if seat == hero_seat:
            continue
        called_tiles = [t for meld in open_melds[seat] for t in meld]
        if riichi_declared_turn[seat] is not None:
            threats.append(
                Threat(
                    player=seat,
                    kind=ThreatKind.RIICHI,
                    declared_turn=riichi_declared_turn[seat],
                    discards=list(discard_piles[seat]),
                    discards_after_threat=list(discards_after_riichi[seat]),
                    called_tiles=called_tiles,
                    dora_indicators=list(dora_indicators),
                )
            )
        elif melds_count[seat] >= 2 and len(discard_piles[seat]) >= 7:
            threats.append(
                Threat(
                    player=seat,
                    kind=ThreatKind.DAMA_TENPAI,
                    declared_turn=len(discard_piles[seat]),
                    discards=list(discard_piles[seat]),
                    discards_after_threat=[],
                    called_tiles=called_tiles,
                    dora_indicators=list(dora_indicators),
                )
            )
        elif looks_like_late_iishanten(discard_piles[seat], melds_count[seat]):
            threats.append(
                Threat(
                    player=seat,
                    kind=ThreatKind.IISHANTEN,
                    declared_turn=len(discard_piles[seat]),
                    discards=list(discard_piles[seat]),
                    discards_after_threat=[],
                    called_tiles=called_tiles,
                    dora_indicators=list(dora_indicators),
                )
            )
    return threats


def looks_like_late_iishanten(pile: list[Tile], melds: int) -> bool:
    """Heuristic: 8+ turns deep, last 3 discards are all middle tiles (2..8)
    suggesting they've finished sorting out floating yaochuu — likely close to
    tenpai even without a riichi declaration."""
    if len(pile) < 8:
        return False
    last = pile[-3:]
    if any(t.is_yaochuu for t in last):
        return False
    # also require they discarded yaochuu in the first half (typical pattern)
    early = pile[: max(1, len(pile) // 2)]
    if not any(t.is_yaochuu for t in early):
        return False
    return True
