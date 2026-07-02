import random

from mahjong.shanten import Shanten as ReferenceShanten

from mahjong_review.shanten import effective_tiles, shanten, shanten_from_counts
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


def test_no_pair_needs_extra_step():
    # 1 set + 4 proto-runs, zero pairs: a proto-run can't become the pair,
    # so this is 3-shanten, not 2 (the classic no-pair correction).
    hand = tiles_from_str("12346m 139p 1356s 5z")
    assert shanten(hand) == 3


def test_karaten_tanki_is_not_tenpai():
    # 234m 7777m 567s 678s: "4 sets + 7m tanki" but all four 7m are in our
    # own hand — the wait is dead, so this is 1-shanten, not tenpai.
    hand = tiles_from_str("234m 7777m 566778s")
    assert shanten(hand) == 1


def test_fuzz_matches_reference_library():
    """Seeded fuzz: our shanten must agree with the `mahjong` reference library
    on random 13-tile hands (uniform and block-structured)."""
    ref = ReferenceShanten()
    rng = random.Random(20260702)

    def random_uniform_hand():
        pool = [i for i in range(34) for _ in range(4)]
        rng.shuffle(pool)
        counts = [0] * 34
        for t in pool[:13]:
            counts[t] += 1
        return counts

    def random_structured_hand():
        counts = [0] * 34
        while sum(counts) < 13:
            r = rng.random()
            space = 13 - sum(counts)
            if r < 0.4 and space >= 3:
                s = rng.choice([0, 9, 18]) + rng.randint(0, 6)
                if all(counts[s + d] < 4 for d in range(3)):
                    for d in range(3):
                        counts[s + d] += 1
            elif r < 0.6 and space >= 2:
                t = rng.randint(0, 33)
                if counts[t] <= 2:
                    counts[t] += 2
            else:
                t = rng.randint(0, 33)
                if counts[t] < 4:
                    counts[t] += 1
        return counts

    for gen in (random_uniform_hand, random_structured_hand):
        for _ in range(1500):
            counts = gen()
            assert shanten_from_counts(counts, 0) == ref.calculate_shanten(counts), counts
