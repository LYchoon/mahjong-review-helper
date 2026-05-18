from mahjong_review.shanten import effective_tiles, shanten
from mahjong_review.tiles import tiles_from_str


def test_winning_hand_is_minus_one():
    # 234m 567p 234s 678s 11z  (14 tiles, complete: 234m + 567p + 234s + 678s + 11z)
    hand = tiles_from_str("234m 567p 234s 678s 11z")
    assert shanten(hand) == -1


def test_tenpai_is_zero():
    # 13-tile waiting hand: 234m 567p 234s 678s 1z (waiting on 1z)
    hand = tiles_from_str("234m 567p 234s 678s 1z")
    assert shanten(hand) == 0


def test_chiitoi_tenpai():
    # 6 pairs + 1 single = chiitoi tenpai
    hand = tiles_from_str("11m 22m 33p 44p 55s 66s 7z")
    assert shanten(hand) == 0


def test_chiitoi_complete():
    hand = tiles_from_str("11m 22m 33p 44p 55s 66s 77z")
    assert shanten(hand) == -1


def test_kokushi_13_wait():
    # 13 unique yaochuu (no pair) = kokushi 13-wait tenpai
    hand = tiles_from_str("19m 19p 19s 1234567z")
    assert shanten(hand) == 0


def test_kokushi_complete():
    # 13 unique yaochuu + 1 paired yaochuu = winning kokushi
    hand = tiles_from_str("19m 19p 19s 11234567z")
    assert shanten(hand) == -1


def test_iishanten():
    # Construct a known 1-shanten:  123m 456p 789s 1z 2z 3z  + 1m (14 -> remove one)
    # 13 tiles: 234m 567p 89s 11z 2z 3z 4z  — many useless honors, far from win.
    # Easier: 234m 567p 789s 11z 2z  → has all complete except the 2z floating
    # That's 13 tiles. The 2z needs a pair partner. Shanten should be 1.
    hand = tiles_from_str("234m 567p 789s 11z 2z")
    assert shanten(hand) == 1


def test_effective_tiles_tenpai():
    # 234m 567p 234s 678s 1z — waiting on 1z (tanki)
    hand = tiles_from_str("234m 567p 234s 678s 1z")
    eff = effective_tiles(hand)
    # the only tile that completes is 1z
    assert 27 in eff
    assert eff[27] == -1
