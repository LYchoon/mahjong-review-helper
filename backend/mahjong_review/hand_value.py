"""Quick yaku detection for hand value estimation.

Not a full scorer — proper yaku requires knowing wait shape + agari tile + fu.
We need a *probabilistic* han estimate to plug into EV calculations, so we:

- Add deterministic han for guaranteed yaku (riichi, yakuhai triplets, tanyao,
  flushes, chiitoi/toitoi lines, run-based yaku, terminal/honor yaku, dora)
- Short-circuit to 13 han when the hand is on a yakuman line (daisangen,
  suuankou, kokushi, tsuuiisou, chinroutou, ryuuiisou, suushii, chuuren)
- Add fractional han for likely-but-uncertain yaku (yakuhai pair → +0.4,
  tsumo expectation → +0.25, uradora expectation → +0.5, pinfu screen → +0.3)
- Round up at the end (mahjong han are integers; EV cares about points,
  not ranks, so rounding up gives a slightly optimistic but not unreasonable
  picture)

Out of model (cannot be predicted from a 13-tile hand):
- moment-of-win yaku: ippatsu (approximated inside the riichi fractionals),
  haitei/houtei, rinshan, chankan, tenhou/chiihou, double riichi
- suukantsu (meld structure doesn't retain kan info) and nagashi mangan

A reader can still see the deterministic vs fractional decomposition in the
returned tag list.
"""

from __future__ import annotations

from .shanten import shanten_chiitoi, shanten_kokushi, shanten_standard
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
    all_counts = tile_counts(all_tiles)
    han_int = 0
    han_frac = 0.0
    tags: list[str] = []

    # yakuman lines trump everything (they don't stack with normal yaku)
    yakuman_tags = _yakuman_line_tags(counts, all_counts, all_tiles, closed)
    if yakuman_tags:
        return 13, yakuman_tags

    chiitoi_line = closed and _is_chiitoi_line(counts)

    # riichi
    if closed and likely_to_riichi:
        han_int += 1
        tags.append("立直")
        # tsumo: ~25% of wins are tsumo for closed hands, adds 1 han
        han_frac += 0.25
        tags.append("+0.25 (tsumo 期望)")
        # uradora: a riichi win reveals ura indicators, worth ~0.5 han on average
        han_frac += 0.5
        tags.append("+0.5 (裏寶期望)")

    # chiitoitsu: closed hand progressing toward seven pairs
    if chiitoi_line:
        han_int += 2
        tags.append("七對子路線")

    # yakuhai — a double wind (round wind == seat wind) is worth 2 han
    yakuhai_tids = {31, 32, 33}  # haku/hatsu/chun
    if round_wind_tid in HONORS:
        yakuhai_tids.add(round_wind_tid)
    if seat_wind_tid in HONORS:
        yakuhai_tids.add(seat_wind_tid)
    meld_counts = tile_counts(meld_tiles) if meld_tiles else None
    for tid in sorted(yakuhai_tids):
        weight = (
            (1 if tid >= 31 else 0)
            + (1 if tid == round_wind_tid else 0)
            + (1 if tid == seat_wind_tid else 0)
        )
        held = counts[tid] + (meld_counts[tid] if meld_counts else 0)
        if held >= 3 and not chiitoi_line:
            han_int += weight
            suffix = " 連風" if weight == 2 else ""
            tags.append(f"役牌×3 ({_honor_name(tid)}{suffix})")
        elif counts[tid] == 2 and not chiitoi_line:
            han_frac += 0.4 * weight
            tags.append(f"+{0.4 * weight:.1f} (役牌候補 {_honor_name(tid)} 對子)")

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

    # honroutou: everything is a terminal or honor (stacks with chiitoi/toitoi)
    honroutou = bool(all_tiles) and all(t.is_yaochuu for t in all_tiles)
    if honroutou:
        han_int += 2
        tags.append("混老頭")

    if not chiitoi_line:
        # triplet family
        if _has_sanshoku_doukou(all_counts):
            han_int += 2
            tags.append("三色同刻")
        if sum(1 for c in counts if c >= 3) >= 3:
            han_int += 2
            tags.append("三暗刻")
        dragon_counts = [all_counts[t] for t in (31, 32, 33)]
        if sum(1 for c in dragon_counts if c >= 3) == 2 and any(
            c == 2 for c in dragon_counts
        ):
            han_int += 2
            tags.append("小三元")

        # chanta family (honroutou is the stronger reading of the same tiles)
        if not honroutou and _chanta_line(all_tiles, all_counts):
            if any(t.suit == "z" for t in all_tiles):
                han_int += 2 if closed else 1
                tags.append("混全帶么九")
            else:
                han_int += 3 if closed else 2
                tags.append("純全帶么九")

        # run family
        if _has_ittsu(all_counts):
            han_int += 2 if closed else 1
            tags.append("一通")
        if _has_sanshoku(all_counts):
            han_int += 2 if closed else 1
            tags.append("三色")
        if closed:
            doubled_runs = _count_doubled_runs(counts)
            if doubled_runs >= 2:
                han_int += 3
                tags.append("二盃口")
            elif doubled_runs == 1:
                han_int += 1
                tags.append("一盃口")
        if closed and _pinfu_possible(counts):
            han_frac += 0.3
            tags.append("+0.3 (平和可能)")

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


_GREEN_TIDS = {19, 20, 21, 23, 25, 32}  # 2s 3s 4s 6s 8s + hatsu


def _yakuman_line_tags(
    counts: list[int],
    all_counts: list[int],
    all_tiles: list[Tile],
    closed: bool,
) -> list[str]:
    """Detect yakuman-line hands. Multiple tags may coexist (e.g. 字一色+小四喜)."""
    if not all_tiles:
        return []
    tags: list[str] = []

    if closed:
        kokushi_sh = shanten_kokushi(counts)
        if kokushi_sh <= 1 and kokushi_sh < min(
            shanten_standard(counts, 0), shanten_chiitoi(counts)
        ):
            tags.append("國士無雙線")
        if sum(1 for c in counts if c >= 3) >= 4:
            tags.append("四暗刻線")
        for offset in (0, 9, 18):
            need = (3, 1, 1, 1, 1, 1, 1, 1, 3)
            if sum(counts[offset + i] for i in range(9)) == sum(counts) and all(
                counts[offset + i] >= need[i] for i in range(9)
            ):
                tags.append("九蓮寶燈線")
                break

    if all(all_counts[t] >= 3 for t in (31, 32, 33)):
        tags.append("大三元")
    if all(t.suit == "z" for t in all_tiles):
        tags.append("字一色")
    if all(t.suit != "z" and t.rank in (1, 9) for t in all_tiles):
        tags.append("清老頭")
    if all(t.tid in _GREEN_TIDS for t in all_tiles):
        tags.append("綠一色")

    wind_trips = sum(1 for t in range(27, 31) if all_counts[t] >= 3)
    wind_pairs = sum(1 for t in range(27, 31) if all_counts[t] == 2)
    if wind_trips == 4:
        tags.append("大四喜")
    elif wind_trips == 3 and wind_pairs >= 1:
        tags.append("小四喜")

    return tags


def _is_chiitoi_line(counts: list[int]) -> bool:
    """True when seven pairs is strictly the closest winning form."""
    return shanten_chiitoi(counts) < shanten_standard(counts, 0)


def _chanta_line(all_tiles: list[Tile], all_counts: list[int]) -> bool:
    """Chanta screen: every tile can sit in a terminal/honor-anchored block and
    there are enough yaochuu tiles to anchor ~5 blocks. Necessary conditions
    only — good enough for an estimator."""
    if not all_tiles:
        return False
    if not all(t.suit == "z" or t.rank <= 3 or t.rank >= 7 for t in all_tiles):
        return False
    yaochuu_total = sum(all_counts[t] for t in _YAOCHUU_TIDS)
    return yaochuu_total >= 5


_YAOCHUU_TIDS = (0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33)


def _has_sanshoku_doukou(all_counts: list[int]) -> bool:
    """The same rank as triplet material in all three suits."""
    return any(all(all_counts[off + r] >= 3 for off in (0, 9, 18)) for r in range(9))


def _count_doubled_runs(counts: list[int]) -> int:
    """Distinct doubled runs (iipeiko units) in the concealed hand."""
    n = 0
    for offset in (0, 9, 18):
        r = 0
        while r < 7:
            if all(counts[offset + r + d] >= 2 for d in range(3)):
                n += 1
                r += 3  # consume the run so overlaps aren't double counted
            else:
                r += 1
    return n


def _flush_value(all_tiles: list[Tile], closed: bool) -> tuple[int, str]:
    """Honitsu/chinitsu han when the hand is already pure in one suit."""
    suits = {t.suit for t in all_tiles if t.suit != "z"}
    if len(suits) != 1:
        return 0, ""
    has_honors = any(t.suit == "z" for t in all_tiles)
    if has_honors:
        return (3 if closed else 2), "混一色"
    return (6 if closed else 5), "清一色"


def _has_ittsu(all_counts: list[int]) -> bool:
    """123 456 789 material all present within one suit (hand + melds)."""
    for offset in (0, 9, 18):
        if all(all_counts[offset + r] >= 1 for r in range(9)):
            return True
    return False


def _has_sanshoku(all_counts: list[int]) -> bool:
    """The same run present in all three suits (hand + melds)."""
    for r in range(7):  # run starting at rank r+1
        if all(
            all_counts[offset + r + d] >= 1
            for offset in (0, 9, 18)
            for d in range(3)
        ):
            return True
    return False


def _pinfu_possible(counts: list[int]) -> bool:
    """Rough pinfu screen: closed, no honors, no triplet material."""
    if any(counts[t] > 0 for t in HONORS):
        return False
    return all(c <= 2 for c in counts)


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
