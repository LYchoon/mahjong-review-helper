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

    # iterate turn-by-turn, simulating the natural draw->discard order
    # We process in the order tenhou logs them: for each "round" the draws/discards
    # are roughly chronological by seat dealer-first but interleaved by calls.
    # A simpler-but-correct approach: pointer per seat in draws/discards; the next
    # action belongs to whichever seat has a pending draw that hasn't been discarded.
    draw_ptr = [0, 0, 0, 0]
    disc_ptr = [0, 0, 0, 0]

    # Dealer of this round
    dealer = round_number % 4
    active = dealer

    safety_iters = 0
    while True:
        safety_iters += 1
        if safety_iters > 400:
            break  # malformed round; bail
        # active seat draws (if they have draws left)
        if draw_ptr[active] >= len(draws[active]):
            break

        draw_entry = draws[active][draw_ptr[active]]
        draw_ptr[active] += 1

        if isinstance(draw_entry, str):
            # call (chi/pon/kan); the called tile entered hand from someone else's discard.
            # For visibility, we add the called tile to visible_counts (was in some discard)
            # and add the meld to the seat.
            kind = draw_entry[0]
            tile_chars = draw_entry[1:]
            # extract digit groups (each tile is 2 digits in tenhou notation)
            tile_codes = _split_call_tiles(tile_chars)
            new_meld_tiles = [_decode_tenhou_tile(c) for c in tile_codes]
            # the called tile (from another player's discard) becomes visible if it wasn't
            for t in new_meld_tiles:
                visible_counts[t.tid] += 1
            if kind in ("c", "p", "m"):
                melds_count[active] += 1
            elif kind in ("a", "k"):
                # ankan: 4 tiles from own hand -> reveal them
                # kakan: add 1 to existing pon
                if kind == "a":
                    melds_count[active] += 1
        else:
            # numeric draw — drew a tile from the wall
            drawn = _decode_tenhou_tile(int(draw_entry))
            if active == hero_seat:
                # add to visible (we know our own draw)
                visible_counts[drawn.tid] += 1

            # now this seat must discard — find next discard entry
            if disc_ptr[active] >= len(discards[active]):
                break
            disc_entry = discards[active][disc_ptr[active]]
            disc_ptr[active] += 1
            turn_counter[active] += 1

            # determine actual discarded tile
            riichi_now = False
            if isinstance(disc_entry, str):
                if disc_entry == "60":
                    discarded = drawn  # tsumogiri
                elif disc_entry.startswith("r"):
                    riichi_now = True
                    tail = disc_entry[1:]
                    if tail == "60":
                        discarded = drawn
                    else:
                        discarded = _decode_tenhou_tile(int(tail))
                else:
                    # unknown event — treat as no-op for MVP
                    continue
            else:
                discarded = _decode_tenhou_tile(int(disc_entry))

            # update visible counts for the discarded tile (already counted if hero's own draw)
            if active != hero_seat:
                visible_counts[discarded.tid] += 1

            discard_piles[active].append(discarded)
            if riichi_declared_turn[active] is not None:
                discards_after_riichi[active].append(discarded)

            # ---- BEFORE discarding, snapshot the hero's decision if applicable ----
            if active == hero_seat:
                threats = _build_threats(
                    hero_seat,
                    discard_piles,
                    discards_after_riichi,
                    riichi_declared_turn,
                    melds_count,
                    dora_inds,
                )
                if threats:
                    # reconstruct the hand *before* this discard: it includes the drawn tile
                    pre_hand_codes = sorted(hands[hero_seat] + [int(draw_entry)])
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
                        )
                    )

            # update hand: add draw, remove discard
            hands[active].append(int(draw_entry))
            try:
                hands[active].remove(_encode_tile(discarded))
            except ValueError:
                # red 5 mismatch (e.g. discarded "60" was the red 5) — try alt
                alt = _alt_encoding(discarded)
                if alt is not None and alt in hands[active]:
                    hands[active].remove(alt)
                else:
                    pass

            if riichi_now:
                riichi_declared_turn[active] = turn_counter[active]

        # next seat (calls may have changed who's active, but we approximate)
        active = (active + 1) % 4

    return snaps


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
