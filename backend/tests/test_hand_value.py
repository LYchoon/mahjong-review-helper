from mahjong_review.hand_value import quick_yaku_han
from mahjong_review.tiles import tiles_from_str


def test_tanyao_detected():
    # all simple tiles (2..8)
    hand = tiles_from_str("234m 456p 678s 234s 55p")
    han, tags = quick_yaku_han(hand)
    assert "斷么" in tags
    assert han >= 2  # riichi + tanyao at least


def test_yakuhai_triplet():
    # round wind = east; haku triplet
    hand = tiles_from_str("123m 456p 78s 1z 555z 6z")
    han, tags = quick_yaku_han(hand, round_wind_tid=27, seat_wind_tid=27)
    assert any("白" in t for t in tags)
    assert han >= 2


def test_no_riichi_when_open():
    hand = tiles_from_str("123m 456p 789s 11z")
    han, tags = quick_yaku_han(hand, melds_count=1, likely_to_riichi=False)
    assert "立直" not in tags


def test_dora_adds_han():
    hand = tiles_from_str("234m 456p 678s 234s 55p")
    han0, _ = quick_yaku_han(hand, dora_count=0)
    han2, tags = quick_yaku_han(hand, dora_count=2)
    assert han2 == han0 + 2
    assert any("寶牌" in t for t in tags)


def test_tsumo_expectation_tag_on_closed_hand():
    hand = tiles_from_str("234m 456p 678s 234s 55p")
    _, tags = quick_yaku_han(hand, likely_to_riichi=True)
    assert any("tsumo" in t for t in tags)


def test_yakuhai_pair_partial_credit():
    # one haku pair, otherwise nondescript closed hand
    hand = tiles_from_str("123m 456p 78s 55z 234m")
    han_with, tags = quick_yaku_han(hand, likely_to_riichi=True)
    # pair only — not a guaranteed +1 han, but should appear as a candidate tag
    assert any("候補" in t and "白" in t for t in tags)
    # value is at least riichi (1) and rounded up with fractional → 2
    assert han_with >= 2


def test_chiitoi_line_detected():
    # six pairs + a floater: seven pairs is clearly the closest form
    hand = tiles_from_str("11m 33m 55p 77p 99s 22z 7z")
    han, tags = quick_yaku_han(hand)
    assert "七對子路線" in tags
    assert han >= 3  # riichi + chiitoi


def test_honitsu_detected():
    hand = tiles_from_str("123m 789m 99m 11z 22z 3z")
    han, tags = quick_yaku_han(hand)
    assert "混一色" in tags
    assert han >= 4  # riichi + honitsu(3)


def test_chinitsu_detected():
    hand = tiles_from_str("123m 456m 789m 22m 57m")
    han, tags = quick_yaku_han(hand)
    assert "清一色" in tags
    assert han >= 7  # riichi + chinitsu(6)


def test_open_flush_smaller():
    concealed = tiles_from_str("123m 789m 99m 5m")
    melds = tiles_from_str("111m")
    han_open, tags_open = quick_yaku_han(
        concealed, melds_count=1, likely_to_riichi=False, meld_tiles=melds
    )
    assert "清一色" in tags_open
    assert han_open >= 5


def test_toitoi_shape_detected():
    concealed = tiles_from_str("22m 55p 88s 3z")
    melds = tiles_from_str("111z 999s")
    han, tags = quick_yaku_han(
        concealed, melds_count=2, likely_to_riichi=False, meld_tiles=melds
    )
    assert "對對和路線" in tags
    assert "斷么" not in tags  # meld contains yaochuu (1z/9s)


def test_meld_yaochuu_kills_tanyao():
    concealed = tiles_from_str("234m 567p 22s 55s")
    melds = tiles_from_str("999s")
    _, tags = quick_yaku_han(
        concealed, melds_count=1, likely_to_riichi=False, meld_tiles=melds
    )
    assert "斷么" not in tags
    # without meld info the old (over-optimistic) behavior granted tanyao
    _, tags_blind = quick_yaku_han(concealed, melds_count=1, likely_to_riichi=False)
    assert "斷么" in tags_blind


def test_ittsu_detected():
    hand = tiles_from_str("123456789m 55p 46s")
    han, tags = quick_yaku_han(hand)
    assert "一通" in tags


def test_sanshoku_detected():
    hand = tiles_from_str("234m 234p 234s 55z 46m")
    han, tags = quick_yaku_han(hand)
    assert "三色" in tags


def test_iipeiko_closed_only():
    hand = tiles_from_str("223344m 567p 88s 46p")
    _, tags_closed = quick_yaku_han(hand)
    assert "一盃口" in tags_closed
    concealed = tiles_from_str("223344m 88s 46p")
    _, tags_open = quick_yaku_han(
        concealed, melds_count=1, likely_to_riichi=False,
        meld_tiles=tiles_from_str("567p"),
    )
    assert "一盃口" not in tags_open


def test_pinfu_fraction_when_no_honors_no_triplets():
    hand = tiles_from_str("234m 456p 678s 34s 55m 7p")
    _, tags = quick_yaku_han(hand)
    assert any("平和可能" in t for t in tags)
    with_triplet = tiles_from_str("222m 456p 678s 34s 55m 7p")
    _, tags2 = quick_yaku_han(with_triplet)
    assert not any("平和可能" in t for t in tags2)


def test_uradora_expectation_on_riichi_line():
    hand = tiles_from_str("234m 456p 678s 34s 55m 7p")
    _, tags = quick_yaku_han(hand, likely_to_riichi=True)
    assert any("裏寶" in t for t in tags)
    _, tags_dama = quick_yaku_han(hand, likely_to_riichi=False)
    assert not any("裏寶" in t for t in tags_dama)


def test_double_wind_worth_two_han():
    # dealer in East round: an East triplet is round wind + seat wind = 2 han
    hand = tiles_from_str("111z 234m 567p 88s 46m")
    han_double, tags = quick_yaku_han(
        hand, round_wind_tid=27, seat_wind_tid=27, likely_to_riichi=False
    )
    assert any("連風" in t for t in tags)
    han_single, _ = quick_yaku_han(
        hand, round_wind_tid=27, seat_wind_tid=28, likely_to_riichi=False
    )
    assert han_double == han_single + 1
