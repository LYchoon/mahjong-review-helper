"""Quick yaku detection for hand value estimation.

Not a full scorer — proper yaku requires knowing wait shape + agari tile + fu.
We need a *probabilistic* han estimate to plug into EV calculations, so we:

- Add deterministic han for guaranteed yaku (riichi for closed hands, yakuhai
  triplets, tanyao when no yaochuu, dora)
- Add fractional han for likely-but-uncertain yaku (yakuhai pair → +0.4,
  tsumo bonus on closed hand → +0.25)
- Round up at the end (mahjong han are integers; EV cares about points,
  not ranks, so rounding up gives a slightly optimistic but not unreasonable
  picture)

A reader can still see the deterministic vs fractional decomposition in the
returned tag list.
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
    han_int = 0
    han_frac = 0.0
    tags: list[str] = []

    # riichi
    if closed and likely_to_riichi:
        han_int += 1
        tags.append("立直")
        # tsumo: ~25% of wins are tsumo for closed hands, adds 1 han
        han_frac += 0.25
        tags.append("+0.25 (tsumo 期望)")

    # yakuhai
    yakuhai_tids = {31, 32, 33}  # haku/hatsu/chun
    if round_wind_tid in HONORS:
        yakuhai_tids.add(round_wind_tid)
    if seat_wind_tid in HONORS:
        yakuhai_tids.add(seat_wind_tid)
    for tid in yakuhai_tids:
        if counts[tid] >= 3:
            han_int += 1
            tags.append(f"役牌×3 ({_honor_name(tid)})")
        elif counts[tid] == 2:
            han_frac += 0.4
            tags.append(f"+0.4 (役牌候補 {_honor_name(tid)} 對子)")

    # tanyao
    yaochuu = set(HONORS) | {0, 8, 9, 17, 18, 26}
    if not any(counts[t] > 0 for t in yaochuu):
        han_int += 1
        tags.append("斷么")

    # dora
    han_int += dora_count
    if dora_count > 0:
        tags.append(f"寶牌 ×{dora_count}")

    total = han_int + han_frac
    # if we have NO yaku at all on a closed hand, riichi covers it (already counted).
    # for an open hand with no yaku, the win is impossible — represent as worst case 1 han
    # so EV isn't zero (player may finish their hand by drawing a yakuhai).
    if total < 1:
        total = 1.0
        tags.append("(假設至少 1 翻)")

    # round up so the integer-han point table maps sensibly
    rounded = int(total) if total == int(total) else int(total) + 1
    return rounded, tags


def _honor_name(tid: int) -> str:
    return ["東", "南", "西", "北", "白", "發", "中"][tid - 27]
