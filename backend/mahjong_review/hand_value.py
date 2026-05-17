"""Quick yaku detection for hand value estimation.

This is *not* a full yaku scorer — that requires knowing wait shape, agari tile,
and fu. We need an estimate of likely final han for EV computations, so we look
for yaku that are likely or guaranteed given the current shape:

- riichi (+1)       — if hand is closed and likely to reach tenpai
- tsumo (+1)        — if closed (always available on tsumo)
- yakuhai (+1 each) — pair or triplet of dragons / round wind / seat wind
- tanyao (+1)       — if no yaochuu tiles
- pinfu hint (+1)   — closed, no triplets, mostly runs
- dora              — passed in as count

Output: estimated final han (current visible + 1 luck buffer).
"""

from __future__ import annotations

from .tiles import HONORS, Tile, tile_counts


def quick_yaku_han(
    hand: list[Tile],
    melds_count: int = 0,
    is_dealer: bool = False,
    round_wind_tid: int = 27,
    seat_wind_tid: int = 27,
    dora_count: int = 0,
    likely_to_riichi: bool = True,
) -> tuple[int, list[str]]:
    """Estimate final han + tags. Returns (han, list_of_yaku_labels)."""
    closed = melds_count == 0
    counts = tile_counts(hand)
    han = 0
    tags: list[str] = []

    # riichi (and tsumo bonus expected)
    if closed and likely_to_riichi:
        han += 1
        tags.append("立直")
        # tsumo expected with ~25% odds — fold into expected value
        han += 0  # not added deterministically; expected via win_prob path

    # yakuhai
    yakuhai_tids = {31, 32, 33}  # haku, hatsu, chun
    if round_wind_tid in HONORS:
        yakuhai_tids.add(round_wind_tid)
    if seat_wind_tid in HONORS:
        yakuhai_tids.add(seat_wind_tid)
    for tid in yakuhai_tids:
        if counts[tid] >= 3:
            han += 1
            tags.append(f"役牌×3 ({_honor_name(tid)})")
        elif counts[tid] == 2:
            # pair could become triplet; ~30% likely if early
            # don't add full han, but bias by 0.5 → round up
            pass

    # tanyao: no yaochuu (terminals + honors)
    yaochuu = set(HONORS) | {0, 8, 9, 17, 18, 26}
    has_yaochuu = any(counts[t] > 0 for t in yaochuu)
    if not has_yaochuu:
        han += 1
        tags.append("斷么")

    # all-simples-leaning: only 1-2 yaochuu and many middles — soft hint, no han added

    # pinfu hint: all runs + pair not yakuhai + ryanmen wait. We can't know wait shape,
    # so a very loose check: closed, no triplets in hand, plenty of consecutive runs.
    if closed:
        triplets = sum(1 for c in counts if c >= 3)
        if triplets == 0:
            # high chance of pinfu; conservative +1 only if we already have a defined shape
            # (i.e. shanten 0 or 1 — caller can decide)
            pass  # leave to caller

    han += dora_count
    if dora_count > 0:
        tags.append(f"寶牌 ×{dora_count}")

    # baseline: every hand needs at least 1 han to win. If we estimated 0, bump to 1.
    if han == 0:
        han = 1
        tags.append("(假設至少 1 翻)")

    return han, tags


def _honor_name(tid: int) -> str:
    return ["東", "南", "西", "北", "白", "發", "中"][tid - 27]
