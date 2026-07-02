"""Quick yaku detection for hand value estimation.

Not a full scorer — proper yaku requires knowing wait shape + agari tile + fu.
We need a *probabilistic* han estimate to plug into EV calculations, so we:

- Add deterministic han for guaranteed yaku (riichi for closed hands, yakuhai
  triplets, tanyao when no yaochuu, flushes, chiitoitsu-line hands, dora)
- Add fractional han for likely-but-uncertain yaku (yakuhai pair → +0.4,
  tsumo bonus on closed hand → +0.25)
- Round up at the end (mahjong han are integers; EV cares about points,
  not ranks, so rounding up gives a slightly optimistic but not unreasonable
  picture)

A reader can still see the deterministic vs fractional decomposition in the
returned tag list.
"""

from __future__ import annotations

from .shanten import shanten_chiitoi, shanten_standard
from .tiles import HONORS, Tile, tile_counts


def quick_yaku_han(
    hand: list[Tile],
    melds_count: int = 0,
    is_dealer: bool = False,
    round_wind_tid: int = 27,
    seat_wind_tid: int = 27,
    dora_count: int = 0,
    likely_to_riichi: bool = True,
    meld_tiles: list[Tile] | None = None,
) -> tuple[int, list[str]]:
    """Estimate final han + tags. Returns (han, list_of_yaku_labels).

    `meld_tiles` is the flattened list of tiles in the player's open melds
    (when known); it sharpens tanyao / flush / toitoi detection.
    """
    closed = melds_count == 0
    counts = tile_counts(hand)
    meld_tiles = meld_tiles or []
    all_tiles = list(hand) + meld_tiles
    han_int = 0
    han_frac = 0.0
    tags: list[str] = []

    chiitoi_line = closed and _is_chiitoi_line(counts)

    # riichi
    if closed and likely_to_riichi:
        han_int += 1
        tags.append("立直")
        # tsumo: ~25% of wins are tsumo for closed hands, adds 1 han
        han_frac += 0.25
        tags.append("+0.25 (tsumo 期望)")

    # chiitoitsu: closed hand progressing toward seven pairs
    if chiitoi_line:
        han_int += 2
        tags.append("七對子路線")

    # yakuhai
    yakuhai_tids = {31, 32, 33}  # haku/hatsu/chun
    if round_wind_tid in HONORS:
        yakuhai_tids.add(round_wind_tid)
    if seat_wind_tid in HONORS:
        yakuhai_tids.add(seat_wind_tid)
    meld_counts = tile_counts(meld_tiles) if meld_tiles else None
    for tid in yakuhai_tids:
        held = counts[tid] + (meld_counts[tid] if meld_counts else 0)
        if held >= 3 and not chiitoi_line:
            han_int += 1
            tags.append(f"役牌×3 ({_honor_name(tid)})")
        elif counts[tid] == 2 and not chiitoi_line:
            han_frac += 0.4
            tags.append(f"+0.4 (役牌候補 {_honor_name(tid)} 對子)")

    # tanyao — melded yaochuu tiles kill it too
    yaochuu = set(HONORS) | {0, 8, 9, 17, 18, 26}
    if not any(t.tid in yaochuu for t in all_tiles):
        han_int += 1
        tags.append("斷么")

    # honitsu / chinitsu: hand (+melds) already pure in one suit
    flush_han, flush_tag = _flush_value(all_tiles, closed)
    if flush_han:
        han_int += flush_han
        tags.append(flush_tag)

    # toitoi: all melds are triplets/quads and the concealed part has no
    # run material (no two tiles at distance 1-2 within a suit)
    if not closed and _is_toitoi_shape(counts, meld_tiles):
        han_int += 2
        tags.append("對對和路線")

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


def _is_chiitoi_line(counts: list[int]) -> bool:
    """True when seven pairs is strictly the closest winning form."""
    return shanten_chiitoi(counts) < shanten_standard(counts, 0)


def _flush_value(all_tiles: list[Tile], closed: bool) -> tuple[int, str]:
    """Honitsu/chinitsu han when the hand is already pure in one suit."""
    suits = {t.suit for t in all_tiles if t.suit != "z"}
    if len(suits) != 1:
        return 0, ""
    has_honors = any(t.suit == "z" for t in all_tiles)
    if has_honors:
        return (3 if closed else 2), "混一色"
    return (6 if closed else 5), "清一色"


def _is_toitoi_shape(counts: list[int], meld_tiles: list[Tile]) -> bool:
    if not meld_tiles:
        return False
    meld_counts = tile_counts(meld_tiles)
    # every meld must be a triplet/quad (all copies of one tile id)
    if any(c not in (0, 3, 4) for c in meld_counts):
        return False
    # concealed part: only pairs/triplets, no run material within any suit
    for offset in (0, 9, 18):
        for r in range(9):
            if counts[offset + r] == 0:
                continue
            for dr in (1, 2):
                if r + dr < 9 and counts[offset + r + dr] > 0:
                    return False
    return True


def _honor_name(tid: int) -> str:
    return ["東", "南", "西", "北", "白", "發", "中"][tid - 27]
