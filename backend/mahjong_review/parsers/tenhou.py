"""Tenhou JSON log parser.

Tenhou's public JSON format (tenhou.net/6/):

    {
      "title": [...], "name": [p0, p1, p2, p3], "rule": {...},
      "log": [round, round, ...]
    }

Each `round` is a list:
    [round_info, scores, dora_inds, ura_dora_inds,
     haipai_0, draws_0, discards_0,
     haipai_1, draws_1, discards_1,
     haipai_2, draws_2, discards_2,
     haipai_3, draws_3, discards_3,
     ending]

Tile integer encoding:
    11..19 = 1m..9m,  21..29 = 1p..9p,  31..39 = 1s..9s
    41..47 = E S W N Haku Hatsu Chun
    51 / 52 / 53 = red 5m / 5p / 5s

`draws_N` entries are tile ints OR strings for calls:
    "c..." = chi   (e.g. "c111213" — called the first listed tile)
    "p..."  = pon
    "m..."  = daiminkan (open kan from discard)
    "a..."  = ankan (concealed kan, in draws stream)
    "k..."  = shouminkan / kakan (added to existing pon)
In a call string, the called-from-player position varies — for our defense
analysis we only need to track concealed hand changes, not perfect call lineage.

`discards_N` entries:
    int  = discard that tile
    "60" = tsumogiri (discard the tile just drawn — already in hand from `draws_N`)
    "r..." = riichi with the given tile (e.g. "r28")
    other strings = additional call-related events

This parser produces a stream of `Snapshot` objects whenever the hero (a specified
seat) must make a discard. Each snapshot includes everything the analyser needs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..danger import Threat, ThreatKind
from ..tiles import Tile, tile_counts


# --- tile id conversion ---


def _decode_tenhou_tile(n: int) -> Tile:
    if n == 51:
        return Tile(0 + 4, red=True)  # 5m red
    if n == 52:
        return Tile(9 + 4, red=True)  # 5p red
    if n == 53:
        return Tile(18 + 4, red=True)  # 5s red
    if 11 <= n <= 19:
        return Tile(n - 11)  # 1m..9m
    if 21 <= n <= 29:
        return Tile(9 + (n - 21))
    if 31 <= n <= 39:
        return Tile(18 + (n - 31))
    if 41 <= n <= 47:
        return Tile(27 + (n - 41))
    raise ValueError(f"unknown tenhou tile code {n}")


def _decode_tile_str(s: str) -> Tile:
    return _decode_tenhou_tile(int(s))


# --- snapshots emitted by the parser ---


@dataclass
class Snapshot:
    """A single hero-discard decision point."""

    round_index: int  # 0-based round number within the log
    round_wind: int  # 27=E, 28=S, ...
    honba: int
    riichi_sticks: int
    turn: int  # 1-based turn of this round (hero discards count)
    hero_seat: int  # 0..3
    hero_hand: list[Tile]  # 14-tile hand right before discard (concealed)
    hero_melds_count: int
    hero_chosen_discard: Tile  # the tile the hero actually chose
    visible_counts: list[int]
    threats: list[Threat]
    dora_indicators: list[Tile]
    all_discards: list[list[Tile]] = field(default_factory=list)  # 4 piles
    riichi_turns: list[int | None] = field(default_factory=list)  # per seat


# --- main parser ---


def parse_tenhou_log(raw: str | dict[str, Any], hero_seat: int) -> list[Snapshot]:
    """Parse a tenhou JSON log into hero defense decision points.

    Returns only snapshots where at least one opponent has declared riichi at or
    before this turn (the MVP defense-only filter).
    """
    data = json.loads(raw) if isinstance(raw, str) else raw
    log = data.get("log", [])
    out: list[Snapshot] = []
    for round_idx, rnd in enumerate(log):
        out.extend(_parse_round(rnd, round_idx, hero_seat))
    return out


def parse_tenhou_file(path: str | Path, hero_seat: int) -> list[Snapshot]:
    return parse_tenhou_log(Path(path).read_text(), hero_seat)


def _parse_round(rnd: list[Any], round_idx: int, hero_seat: int) -> list[Snapshot]:
    round_info = rnd[0]
    round_number, honba, riichi_sticks = round_info[0], round_info[1], round_info[2]
    round_wind = 27 + (round_number // 4)  # 0..3 = E1..E4; 4..7 = S1..S4
    dora_inds = [_decode_tenhou_tile(n) for n in rnd[2]]

    haipai = [rnd[4 + 3 * s] for s in range(4)]
    draws = [rnd[5 + 3 * s] for s in range(4)]
    discards = [rnd[6 + 3 * s] for s in range(4)]

    # state per seat
    hands: list[list[int]] = [
        sorted([n for n in seat_haipai]) for seat_haipai in haipai
    ]
    melds_count = [0, 0, 0, 0]
    discard_piles: list[list[Tile]] = [[] for _ in range(4)]
    riichi_declared_turn = [None, None, None, None]
    discards_after_riichi: list[list[Tile]] = [[] for _ in range(4)]

    # running visible counts
    visible_counts = [0] * 34
    for ind in dora_inds:
        visible_counts[ind.tid] += 1
    for seat_hand in (hands[hero_seat],):
        for n in seat_hand:
            visible_counts[_decode_tenhou_tile(n).tid] += 1

    snaps: list[Snapshot] = []
    turn_counter = [0, 0, 0, 0]
    draw_ptr = [0, 0, 0, 0]
    disc_ptr = [0, 0, 0, 0]

    dealer = round_number % 4
    active = dealer

    def bump_visible(tid: int) -> None:
        if visible_counts[tid] < 4:
            visible_counts[tid] += 1

    safety_iters = 0
    while safety_iters < 600:
        safety_iters += 1

        # Before active draws, check if any OTHER seat is intercepting with a call
        # (chi/pon/daiminkan) — these appear as strings at the head of their draws.
        interceptor = None
        for s in range(4):
            if s == active or draw_ptr[s] >= len(draws[s]):
                continue
            ent = draws[s][draw_ptr[s]]
            if isinstance(ent, str) and ent[0] in ("c", "p", "m"):
                interceptor = s
                break
        if interceptor is not None:
            active = interceptor

        if draw_ptr[active] >= len(draws[active]):
            # try to find any seat with remaining draws (could be us out of sync)
            remaining = [s for s in range(4) if draw_ptr[s] < len(draws[s])]
            if not remaining:
                break
            active = remaining[0]

        entry = draws[active][draw_ptr[active]]
        draw_ptr[active] += 1

        if isinstance(entry, str):
            kind = entry[0]
            tile_codes = _split_call_tiles(entry[1:])
            tiles_in_call = [_decode_tenhou_tile(c) for c in tile_codes]

            if kind in ("a", "k"):
                # Concealed / added kan during own turn — no discard handed out yet here.
                # Bump visibility for revealed tiles; melds_count += 1 for ankan only.
                for t in tiles_in_call:
                    bump_visible(t.tid)
                if kind == "a":
                    melds_count[active] += 1
                # active stays — they'll draw rinshan next iteration
                continue
            else:
                # chi/pon/daiminkan — out-of-turn intercept
                for t in tiles_in_call:
                    bump_visible(t.tid)
                melds_count[active] += 1
                # active now must discard (no draw — they used the called tile)
                if disc_ptr[active] >= len(discards[active]):
                    break
                _process_discard(
                    active,
                    discards,
                    disc_ptr,
                    None,
                    hands,
                    discard_piles,
                    discards_after_riichi,
                    riichi_declared_turn,
                    turn_counter,
                    visible_counts,
                    hero_seat,
                    snaps,
                    round_idx,
                    round_wind,
                    honba,
                    riichi_sticks,
                    melds_count,
                    dora_inds,
                )
                # active stays; if no further interceptor, next iter will find them with no pending draws
                # and rotate via the fallback. To rotate properly:
                active = (active + 1) % 4
                continue

        # normal numeric draw
        drawn_code = int(entry)
        drawn = _decode_tenhou_tile(drawn_code)
        if active == hero_seat:
            bump_visible(drawn.tid)

        if disc_ptr[active] >= len(discards[active]):
            break

        _process_discard(
            active,
            discards,
            disc_ptr,
            drawn_code,
            hands,
            discard_piles,
            discards_after_riichi,
            riichi_declared_turn,
            turn_counter,
            visible_counts,
            hero_seat,
            snaps,
            round_idx,
            round_wind,
            honba,
            riichi_sticks,
            melds_count,
            dora_inds,
        )
        active = (active + 1) % 4

    return snaps


def _process_discard(
    active: int,
    discards: list[list[Any]],
    disc_ptr: list[int],
    drawn_code: int | None,
    hands: list[list[int]],
    discard_piles: list[list[Tile]],
    discards_after_riichi: list[list[Tile]],
    riichi_declared_turn: list[int | None],
    turn_counter: list[int],
    visible_counts: list[int],
    hero_seat: int,
    snaps: list[Snapshot],
    round_idx: int,
    round_wind: int,
    honba: int,
    riichi_sticks: int,
    melds_count: list[int],
    dora_inds: list[Tile],
) -> None:
    disc_entry = discards[active][disc_ptr[active]]
    disc_ptr[active] += 1
    turn_counter[active] += 1

    riichi_now = False
    drawn_tile = _decode_tenhou_tile(drawn_code) if drawn_code is not None else None

    if isinstance(disc_entry, str):
        if disc_entry == "60":
            if drawn_tile is None:
                return
            discarded = drawn_tile
        elif disc_entry.startswith("r"):
            riichi_now = True
            tail = disc_entry[1:]
            if tail == "60":
                if drawn_tile is None:
                    return
                discarded = drawn_tile
            else:
                discarded = _decode_tenhou_tile(int(tail))
        elif disc_entry[0] in ("c", "p", "m", "a", "k"):
            # rare — embedded mid-discard call; skip
            return
        else:
            return
    else:
        discarded = _decode_tenhou_tile(int(disc_entry))

    # visibility for the discarded tile (own draw already counted at draw time)
    if active != hero_seat:
        if visible_counts[discarded.tid] < 4:
            visible_counts[discarded.tid] += 1

    discard_piles[active].append(discarded)
    if riichi_declared_turn[active] is not None:
        discards_after_riichi[active].append(discarded)

    # snapshot before mutating hero's hand
    if active == hero_seat:
        threats = _build_threats(
            hero_seat,
            discard_piles,
            discards_after_riichi,
            riichi_declared_turn,
            melds_count,
            dora_inds,
        )
        if threats and drawn_code is not None:
            pre_hand_codes = sorted(hands[hero_seat] + [drawn_code])
            pre_hand = [_decode_tenhou_tile(n) for n in pre_hand_codes]
            snaps.append(
                Snapshot(
                    round_index=round_idx,
                    round_wind=round_wind,
                    honba=honba,
                    riichi_sticks=riichi_sticks,
                    turn=turn_counter[active],
                    hero_seat=hero_seat,
                    hero_hand=pre_hand,
                    hero_melds_count=melds_count[hero_seat],
                    hero_chosen_discard=discarded,
                    visible_counts=list(visible_counts),
                    threats=threats,
                    dora_indicators=list(dora_inds),
                    all_discards=[list(p) for p in discard_piles],
                    riichi_turns=list(riichi_declared_turn),
                )
            )

    if drawn_code is not None:
        hands[active].append(drawn_code)
    try:
        hands[active].remove(_encode_tile(discarded))
    except ValueError:
        alt = _alt_encoding(discarded)
        if alt is not None and alt in hands[active]:
            hands[active].remove(alt)

    if riichi_now:
        riichi_declared_turn[active] = turn_counter[active]


def _split_call_tiles(s: str) -> list[int]:
    """Tenhou call strings are sequences of 2-digit tile codes, possibly with a single
    letter between groups to indicate which slot the called tile is in. We strip non-
    digits and chunk in 2s."""
    digits = "".join(ch for ch in s if ch.isdigit())
    return [int(digits[i : i + 2]) for i in range(0, len(digits), 2)]


def _encode_tile(t: Tile) -> int:
    """Inverse of _decode_tenhou_tile."""
    if t.red and t.rank == 5 and t.suit in "mps":
        return {"m": 51, "p": 52, "s": 53}[t.suit]
    if t.suit == "m":
        return 11 + t.rank - 1
    if t.suit == "p":
        return 21 + t.rank - 1
    if t.suit == "s":
        return 31 + t.rank - 1
    return 41 + t.rank - 1


def _alt_encoding(t: Tile) -> int | None:
    """Return the non-red encoding for a red 5, or vice versa, if applicable."""
    if t.rank != 5 or t.suit not in "mps":
        return None
    if t.red:
        return {"m": 15, "p": 25, "s": 35}[t.suit]
    return {"m": 51, "p": 52, "s": 53}[t.suit]


def _build_threats(
    hero_seat: int,
    discard_piles: list[list[Tile]],
    discards_after_riichi: list[list[Tile]],
    riichi_declared_turn: list[int | None],
    melds_count: list[int],
    dora_indicators: list[Tile],
) -> list[Threat]:
    threats: list[Threat] = []
    for seat in range(4):
        if seat == hero_seat:
            continue
        if riichi_declared_turn[seat] is not None:
            threats.append(
                Threat(
                    player=seat,
                    kind=ThreatKind.RIICHI,
                    declared_turn=riichi_declared_turn[seat],
                    discards=list(discard_piles[seat]),
                    discards_after_threat=list(discards_after_riichi[seat]),
                    called_tiles=[],
                    dora_indicators=list(dora_indicators),
                )
            )
        elif melds_count[seat] >= 2 and len(discard_piles[seat]) >= 8:
            # heuristic dama-tenpai threat: 2+ called melds late in the round
            threats.append(
                Threat(
                    player=seat,
                    kind=ThreatKind.DAMA_TENPAI,
                    declared_turn=len(discard_piles[seat]),
                    discards=list(discard_piles[seat]),
                    discards_after_threat=[],
                    called_tiles=[],
                    dora_indicators=list(dora_indicators),
                )
            )
    return threats
