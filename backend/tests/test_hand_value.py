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
