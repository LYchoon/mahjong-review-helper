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
from pathlib import Path
from typing import Any

from ..tiles import Tile
from .common import CallOpportunity, ParseResult, Snapshot, build_threats

__all__ = ["Snapshot", "parse_tenhou_log", "parse_tenhou_log_full", "parse_tenhou_file"]

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


# --- main parser ---


def parse_tenhou_log(raw: str | dict[str, Any], hero_seat: int) -> list[Snapshot]:
    """Parse a tenhou JSON log into hero discard decision points.

    Emits a snapshot for every hero discard; `Snapshot.threats` is empty when no
    opponent threat exists (the analyser then runs an efficiency review).
    """
    return parse_tenhou_log_full(raw, hero_seat).snapshots


def parse_tenhou_log_full(raw: str | dict[str, Any], hero_seat: int) -> ParseResult:
    """Like parse_tenhou_log but also returns the hero's call opportunities
    (pon/chi chances on opponent discards, with whether they were taken)."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    log = data.get("log", [])
    result = ParseResult(snapshots=[], call_opportunities=[])
    for round_idx, rnd in enumerate(log):
        snaps, opps = _parse_round(rnd, round_idx, hero_seat)
        result.snapshots.extend(snaps)
        result.call_opportunities.extend(opps)
    return result


def parse_tenhou_file(path: str | Path, hero_seat: int) -> list[Snapshot]:
    return parse_tenhou_log(Path(path).read_text(), hero_seat)


def _parse_round(
    rnd: list[Any], round_idx: int, hero_seat: int
) -> tuple[list[Snapshot], list[CallOpportunity]]:
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
    open_melds: list[list[list[Tile]]] = [[] for _ in range(4)]
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
    opportunities: list[CallOpportunity] = []
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
        # The marker letter sits before the called tile, so for pon/kan from across
        # or the right it is NOT the first character (e.g. "41p4141").
        interceptor = None
        for s in range(4):
            if s == active or draw_ptr[s] >= len(draws[s]):
                continue
            ent = draws[s][draw_ptr[s]]
            if isinstance(ent, str) and any(ch in "cpm" for ch in ent):
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
            kind, tile_codes, called_code = _parse_call(entry)

            if kind in ("a", "k", "m"):
                # Kan (concealed / added / open). No discard yet — the same player
                # draws a rinshan tile next iteration and discards after that.
                _apply_call(
                    active, kind, tile_codes, called_code,
                    hands, melds_count, open_melds, visible_counts, hero_seat,
                )
                continue

            # chi/pon — out-of-turn intercept; caller must now discard (no draw).
            _apply_call(
                active, kind, tile_codes, called_code,
                hands, melds_count, open_melds, visible_counts, hero_seat,
            )
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
                round_number,
                round_wind,
                honba,
                riichi_sticks,
                melds_count,
                dora_inds,
                open_melds,
                draws,
                draw_ptr,
                opportunities,
            )
            active = (active + 1) % 4
            continue

        # normal numeric draw
        drawn_code = int(entry)
        drawn = _decode_tenhou_tile(drawn_code)
        if active == hero_seat:
            bump_visible(drawn.tid)

        if disc_ptr[active] >= len(discards[active]):
            break

        rotate = _process_discard(
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
            round_number,
            round_wind,
            honba,
            riichi_sticks,
            melds_count,
            dora_inds,
            open_melds,
            draws,
            draw_ptr,
            opportunities,
        )
        if rotate:
            active = (active + 1) % 4

    return snaps, opportunities


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
    round_number: int,
    round_wind: int,
    honba: int,
    riichi_sticks: int,
    melds_count: list[int],
    dora_inds: list[Tile],
    open_melds: list[list[list[Tile]]],
    draws: list[list[Any]],
    draw_ptr: list[int],
    opportunities: list[CallOpportunity],
) -> bool:
    """Consume one discard-slot entry. Returns True if the turn should rotate to
    the next player, False if the same player acts again (kan → rinshan draw)."""
    disc_entry = discards[active][disc_ptr[active]]
    disc_ptr[active] += 1

    riichi_now = False
    drawn_tile = _decode_tenhou_tile(drawn_code) if drawn_code is not None else None

    if isinstance(disc_entry, str):
        if disc_entry == "60":
            if drawn_tile is None:
                return True
            discarded = drawn_tile
        elif disc_entry.startswith("r"):
            riichi_now = True
            tail = disc_entry[1:]
            if tail == "60":
                if drawn_tile is None:
                    return True
                discarded = drawn_tile
            else:
                discarded = _decode_tenhou_tile(int(tail))
        elif any(ch in "cpmak" for ch in disc_entry):
            # Kan declared in the discard slot (ankan/kakan take the place of a
            # discard in tenhou/6 logs). The drawn tile joins the hand, the kan
            # tiles leave it, and the same player draws rinshan next.
            if drawn_code is not None:
                hands[active].append(drawn_code)
            kind, tile_codes, called_code = _parse_call(disc_entry)
            _apply_call(
                active, kind, tile_codes, called_code,
                hands, melds_count, open_melds, visible_counts, hero_seat,
            )
            return False
        else:
            # unknown marker — keep the drawn tile so the hand stays consistent
            if drawn_code is not None:
                hands[active].append(drawn_code)
            return True
    else:
        discarded = _decode_tenhou_tile(int(disc_entry))

    turn_counter[active] += 1

    # visibility for the discarded tile (own draw already counted at draw time)
    if active != hero_seat:
        if visible_counts[discarded.tid] < 4:
            visible_counts[discarded.tid] += 1

    discard_piles[active].append(discarded)
    if riichi_declared_turn[active] is not None:
        discards_after_riichi[active].append(discarded)

    # snapshot before mutating hero's hand. Discards made while the hero is
    # already in riichi are forced tsumogiri — not decisions — so skip those
    # (the riichi declaration discard itself IS reviewed).
    if active == hero_seat:
        already_riichi = riichi_declared_turn[hero_seat] is not None and not riichi_now
        if drawn_code is not None and not already_riichi:
            threats = build_threats(
                hero_seat,
                discard_piles,
                discards_after_riichi,
                riichi_declared_turn,
                melds_count,
                dora_inds,
                open_melds,
            )
            pre_hand_codes = sorted(hands[hero_seat] + [drawn_code])
            pre_hand = [_decode_tenhou_tile(n) for n in pre_hand_codes]
            snaps.append(
                Snapshot(
                    round_index=round_idx,
                    round_number=round_number,
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
                    open_melds=[[list(m) for m in seat] for seat in open_melds],
                    hero_riichi_declared_now=riichi_now,
                )
            )
    else:
        _maybe_record_call_opportunity(
            active,
            discarded,
            hands,
            hero_seat,
            riichi_declared_turn,
            melds_count,
            open_melds,
            draws,
            draw_ptr,
            turn_counter,
            discard_piles,
            discards_after_riichi,
            dora_inds,
            opportunities,
            round_idx,
            round_number,
            round_wind,
            honba,
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
    return True


def _parse_call(entry: str) -> tuple[str, list[int], int | None]:
    """Decode a tenhou call string like "c111213", "41p4141" or "121212a12".

    The marker letter sits directly before the called/added tile; its position in
    the string encodes which player it came from (irrelevant for our analysis).
    Returns (kind_letter, all_tile_codes, called_or_added_code).
    """
    letter_idx = next((i for i, ch in enumerate(entry) if ch.isalpha()), None)
    kind = entry[letter_idx] if letter_idx is not None else "?"
    digits = "".join(ch for ch in entry if ch.isdigit())
    codes = [int(digits[i : i + 2]) for i in range(0, len(digits), 2)]
    called: int | None = None
    if letter_idx is not None:
        after = entry[letter_idx + 1 : letter_idx + 3]
        if len(after) == 2 and after.isdigit():
            called = int(after)
    return kind, codes, called


_RED_TO_PLAIN = {51: 15, 52: 25, 53: 35}
_PLAIN_TO_RED = {v: k for k, v in _RED_TO_PLAIN.items()}


def _remove_code_from_hand(hand: list[int], code: int) -> None:
    """Remove one tile code from a hand, tolerating red-5 / plain-5 mismatches."""
    if code in hand:
        hand.remove(code)
        return
    alt = _RED_TO_PLAIN.get(code) or _PLAIN_TO_RED.get(code)
    if alt is not None and alt in hand:
        hand.remove(alt)


def _apply_call(
    active: int,
    kind: str,
    tile_codes: list[int],
    called_code: int | None,
    hands: list[list[int]],
    melds_count: list[int],
    open_melds: list[list[list[Tile]]],
    visible_counts: list[int],
    hero_seat: int,
) -> None:
    """Apply a call (chi/pon/daiminkan/ankan/kakan) to the per-seat state.

    Removes the tiles that came out of the caller's concealed hand, updates meld
    bookkeeping, and bumps visibility only for newly revealed tiles (the called
    tile was already visible as a discard; the hero's own tiles are pre-counted).
    """
    tiles_in_call = [_decode_tenhou_tile(c) for c in tile_codes]

    if kind == "a":
        from_hand = list(tile_codes)  # all four tiles come from the hand
    elif kind == "k":
        # added kan: only the drawn/added tile leaves the hand
        from_hand = [called_code] if called_code is not None else tile_codes[-1:]
    else:
        # chi/pon/daiminkan: everything except the called tile comes from the hand
        from_hand = list(tile_codes)
        if called_code is not None and called_code in from_hand:
            from_hand.remove(called_code)

    for code in from_hand:
        _remove_code_from_hand(hands[active], code)

    if active != hero_seat:
        for code in from_hand:
            tid = _decode_tenhou_tile(code).tid
            if visible_counts[tid] < 4:
                visible_counts[tid] += 1

    if kind == "k":
        added = _decode_tenhou_tile(called_code if called_code is not None else tile_codes[-1])
        for meld in open_melds[active]:
            if len(meld) == 3 and all(t.tid == added.tid for t in meld):
                meld.append(added)
                break
        else:
            if open_melds[active]:
                open_melds[active][-1] = open_melds[active][-1] + [added]
    else:
        melds_count[active] += 1
        open_melds[active].append(tiles_in_call)


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


def _maybe_record_call_opportunity(
    active: int,
    discarded: Tile,
    hands: list[list[int]],
    hero_seat: int,
    riichi_declared_turn: list[int | None],
    melds_count: list[int],
    open_melds: list[list[list[Tile]]],
    draws: list[list[Any]],
    draw_ptr: list[int],
    turn_counter: list[int],
    discard_piles: list[list[Tile]],
    discards_after_riichi: list[list[Tile]],
    dora_inds: list[Tile],
    opportunities: list[CallOpportunity],
    round_idx: int,
    round_number: int,
    round_wind: int,
    honba: int,
) -> None:
    """Record a pon/chi chance for the hero on an opponent's discard, noting
    whether the hero actually took it (their call string, if any, sits at the
    head of their draw stream)."""
    if riichi_declared_turn[hero_seat] is not None:
        return
    hero_codes = hands[hero_seat]
    if len(hero_codes) != 13 - 3 * melds_count[hero_seat]:
        return
    hero_tiles = [_decode_tenhou_tile(n) for n in hero_codes]
    tid = discarded.tid

    can_pon = sum(1 for t in hero_tiles if t.tid == tid) >= 2
    can_chi = False
    if active == (hero_seat + 3) % 4 and not discarded.is_honor:
        tids = {t.tid for t in hero_tiles}
        r = discarded.rank
        suit_off = tid - (r - 1)
        for a, b in ((r - 2, r - 1), (r - 1, r + 1), (r + 1, r + 2)):
            if (
                1 <= a <= 9
                and 1 <= b <= 9
                and (suit_off + a - 1) in tids
                and (suit_off + b - 1) in tids
            ):
                can_chi = True
                break
    if not can_pon and not can_chi:
        return

    called = False
    if draw_ptr[hero_seat] < len(draws[hero_seat]):
        ent = draws[hero_seat][draw_ptr[hero_seat]]
        if isinstance(ent, str) and any(ch in "cpm" for ch in ent):
            _, _, called_code = _parse_call(ent)
            if called_code is not None and _decode_tenhou_tile(called_code).tid == tid:
                called = True

    threats = build_threats(
        hero_seat,
        discard_piles,
        discards_after_riichi,
        riichi_declared_turn,
        melds_count,
        dora_inds,
        open_melds,
    )
    opportunities.append(
        CallOpportunity(
            round_index=round_idx,
            round_number=round_number,
            round_wind=round_wind,
            honba=honba,
            turn=turn_counter[active],
            hero_seat=hero_seat,
            tile=discarded,
            can_pon=can_pon,
            can_chi=can_chi,
            called=called,
            hero_hand=hero_tiles,
            hero_melds_count=melds_count[hero_seat],
            hero_meld_tiles=[t for m in open_melds[hero_seat] for t in m],
            threats_count=len(threats),
        )
    )
