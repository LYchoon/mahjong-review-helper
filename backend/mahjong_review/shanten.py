"""Shanten calculator.

Returns the minimum number of tile exchanges to reach tenpai (-1 means already won).

Three forms checked: standard (4 sets + pair), chiitoitsu (7 pairs), kokushi musou
(13 orphans). The function returns the minimum across all three.

Standard shanten uses a straightforward recursive search over meld decompositions of
each suit. Performance is fine for 13–14 tile hands; not optimised for batch use.
"""

from __future__ import annotations

from functools import lru_cache

from .tiles import HONORS, NUM_TILE_TYPES, Tile, tile_counts


def shanten(hand: list[Tile], melds_count: int = 0) -> int:
    """Return shanten for `hand` (concealed tiles only).

    `melds_count` is the number of already-called melds (chi/pon/kan); the hand
    should have 13 - 3*melds_count or 14 - 3*melds_count tiles.
    """
    counts = tile_counts(hand)
    return shanten_from_counts(counts, melds_count)


def shanten_from_counts(counts: list[int], melds_count: int = 0) -> int:
    return min(
        _shanten_standard(counts, melds_count),
        _shanten_chiitoi(counts) if melds_count == 0 else 8,
        _shanten_kokushi(counts) if melds_count == 0 else 8,
    )


# ---------- chiitoitsu ----------


def _shanten_chiitoi(counts: list[int]) -> int:
    pairs = sum(1 for c in counts if c >= 2)
    kinds = sum(1 for c in counts if c >= 1)
    sh = 6 - pairs
    if kinds < 7:
        sh += 7 - kinds
    return sh


# ---------- kokushi ----------

_YAOCHUU = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)


def _shanten_kokushi(counts: list[int]) -> int:
    unique = 0
    has_pair = False
    for t in _YAOCHUU:
        if counts[t] >= 1:
            unique += 1
        if counts[t] >= 2:
            has_pair = True
    return 13 - unique - (1 if has_pair else 0)


# ---------- standard (4 sets + pair) ----------


def _shanten_standard(counts: list[int], melds_count: int) -> int:
    sets_needed = 4 - melds_count
    best = [8]

    # Try every possible pair (including no pair) and decompose the rest into sets/partials.
    # Honor partials are limited (only pair/triplet).
    for pair_tile in range(-1, NUM_TILE_TYPES):
        if pair_tile == -1:
            new_counts = counts
            has_pair = 0
        else:
            if counts[pair_tile] < 2:
                continue
            new_counts = counts.copy()
            new_counts[pair_tile] -= 2
            has_pair = 1

        m = 0  # complete sets
        p = 0  # partials (pairs / two-tile proto-runs)

        # honors first — only pairs / triplets possible
        honor_m = 0
        honor_p = 0
        for h in HONORS:
            c = new_counts[h]
            if c >= 3:
                honor_m += 1
                c -= 3
            if c == 2:
                honor_p += 1

        # number suits via recursive decomposition
        suit_m = 0
        suit_p = 0
        for suit_start in (0, 9, 18):
            sm, sp = _best_suit_decomposition(tuple(new_counts[suit_start : suit_start + 9]))
            suit_m += sm
            suit_p += sp

        m = honor_m + suit_m
        p = honor_p + suit_p

        # cap partials: m + p <= sets_needed (+1 for the pair slot if no pair yet)
        max_partials = sets_needed - m + (0 if has_pair else 1)
        if p > max_partials:
            p = max_partials

        sh = 2 * sets_needed - 2 * m - p - has_pair
        if sh < best[0]:
            best[0] = sh

    return best[0]


@lru_cache(maxsize=None)
def _best_suit_decomposition(c: tuple[int, ...]) -> tuple[int, int]:
    """Return (max complete sets, partials given that set count) for a single suit.

    A 'set' is run (i, i+1, i+2) or triplet (i, i, i). A 'partial' is pair (i, i)
    or proto-run (i, i+1) or (i, i+2). We want to maximise sets first, then partials.
    """
    best = (0, 0)

    def rec(arr: list[int], i: int, sets: int, partials: int) -> None:
        nonlocal best
        # skip empty positions
        while i < 9 and arr[i] == 0:
            i += 1
        if i >= 9:
            if (sets, partials) > best:
                best = (sets, partials)
            return

        # upper bound prune: at most each remaining tile contributes
        remaining = sum(arr[i:])
        if sets + (remaining // 3) < best[0]:
            return

        # try triplet
        if arr[i] >= 3:
            arr[i] -= 3
            rec(arr, i, sets + 1, partials)
            arr[i] += 3
        # try run
        if i + 2 < 9 and arr[i] >= 1 and arr[i + 1] >= 1 and arr[i + 2] >= 1:
            arr[i] -= 1
            arr[i + 1] -= 1
            arr[i + 2] -= 1
            rec(arr, i, sets + 1, partials)
            arr[i] += 1
            arr[i + 1] += 1
            arr[i + 2] += 1
        # try pair (partial)
        if arr[i] >= 2:
            arr[i] -= 2
            rec(arr, i, sets, partials + 1)
            arr[i] += 2
        # try proto-run (i, i+1)
        if i + 1 < 9 and arr[i] >= 1 and arr[i + 1] >= 1:
            arr[i] -= 1
            arr[i + 1] -= 1
            rec(arr, i, sets, partials + 1)
            arr[i] += 1
            arr[i + 1] += 1
        # try kanchan (i, i+2)
        if i + 2 < 9 and arr[i] >= 1 and arr[i + 2] >= 1:
            arr[i] -= 1
            arr[i + 2] -= 1
            rec(arr, i, sets, partials + 1)
            arr[i] += 1
            arr[i + 2] += 1
        # skip this tile entirely (treat as floating)
        saved = arr[i]
        arr[i] = 0
        rec(arr, i + 1, sets, partials)
        arr[i] = saved

    rec(list(c), 0, 0, 0)
    return best


def effective_tiles(hand: list[Tile], melds_count: int = 0) -> dict[int, int]:
    """For a 13-tile hand, return {tile_id: shanten_after_drawing_that_tile} dict.

    Only includes tiles that reduce shanten (i.e. useful draws to advance).
    """
    counts = tile_counts(hand)
    if sum(counts) != 13 - 3 * melds_count:
        raise ValueError(f"hand must have {13 - 3*melds_count} tiles, got {sum(counts)}")
    current = shanten_from_counts(counts, melds_count)
    out: dict[int, int] = {}
    for tid in range(NUM_TILE_TYPES):
        if counts[tid] >= 4:
            continue
        counts[tid] += 1
        new_sh = shanten_from_counts(counts, melds_count)
        counts[tid] -= 1
        if new_sh < current:
            out[tid] = new_sh
    return out
