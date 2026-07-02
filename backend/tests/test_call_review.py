"""Tests for call (pon/chi) opportunity detection and review."""

from mahjong_review.analyzer import review_call
from mahjong_review.parsers.common import CallOpportunity
from mahjong_review.parsers.tenhou import parse_tenhou_log_full
from mahjong_review.tiles import Tile, tiles_from_str


def _opp(hand: str, tile: str, *, can_pon=False, can_chi=False, called=False, melds=0,
         meld_tiles: str = "", threats=0) -> CallOpportunity:
    return CallOpportunity(
        round_index=0,
        round_number=0,
        round_wind=27,
        honba=0,
        turn=6,
        hero_seat=0,
        tile=Tile.from_str(tile),
        can_pon=can_pon,
        can_chi=can_chi,
        called=called,
        hero_hand=tiles_from_str(hand),
        hero_melds_count=melds,
        hero_meld_tiles=tiles_from_str(meld_tiles),
        threats_count=threats,
    )


def test_yakuhai_pon_recommended():
    # two haku in hand; ponning secures a yaku
    opp = _opp("234m 567p 88s 55z 34s 1z", "5z", can_pon=True, called=False)
    review = review_call(opp)
    assert review is not None
    assert review.recommended == "call"
    assert review.actual == "passed"
    assert review.label in ("inaccuracy", "mistake")


def test_yakuhai_pon_taken_is_best():
    opp = _opp("234m 567p 88s 55z 34s 1z", "5z", can_pon=True, called=True)
    review = review_call(opp)
    assert review is not None
    assert review.label == "best"


def test_no_yaku_call_recommends_pass():
    # chi that advances the hand but leaves no yaku (terminal in hand kills
    # tanyao; nothing else) — calling would strand the hand yaku-less
    opp = _opp("13m 45m 567p 789s 22z 9m", "6m", can_chi=True, called=False)
    review = review_call(opp)
    assert review is not None
    assert review.recommended == "pass"


def test_calling_without_yaku_is_flagged():
    opp = _opp("13m 45m 567p 789s 22z 9m", "6m", can_chi=True, called=True)
    review = review_call(opp)
    assert review is not None
    assert review.recommended == "pass"
    assert review.label == "mistake"
    assert any("沒有確定役" in r for r in review.reasons)


def test_chi_to_tenpai_recommended_when_already_open():
    # hero already ponned haku (yaku secured, no closed-hand value left);
    # chi 6m with 45m reaches tenpai — EV clearly favours calling
    opp = _opp(
        "45m 46p 567p 88s 2s", "6m",
        can_chi=True, called=False, melds=1, meld_tiles="555z",
    )
    review = review_call(opp)
    assert review is not None
    assert review.shanten_after < review.shanten_before
    assert review.recommended == "call"
    assert review.ev_call > review.ev_pass


def test_closed_iishanten_keeps_riichi_value_over_cheap_chi():
    # closed 1-shanten with riichi potential vs a 1000-point open tanyao
    # tenpai: the EV comparison favours staying closed
    opp = _opp("45m 46p 567p 456s 88s 2s", "6m", can_chi=True, called=False)
    review = review_call(opp)
    assert review is not None
    assert review.recommended == "pass"
    assert review.ev_pass >= review.ev_call


def test_tenhou_parser_records_call_opportunity():
    """Seat 0 (hero) holds two haku; seat 3 (kamicha) discards the third."""
    log = {
        "title": ["test", ""],
        "name": ["a", "b", "c", "d"],
        "rule": {},
        "log": [
            [
                [3, 0, 0],  # E4: dealer is seat 3 → seat 3 acts first
                [25000] * 4,
                [41],
                [],
                # hero: two haku + junk
                [45, 45, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43],
                [24, 25],
                [24, 25],
                [14, 15, 16, 24, 25, 26, 34, 35, 36, 44, 44, 46, 46],
                [33, 34],
                [33, 34],
                [15, 16, 17, 25, 26, 27, 35, 36, 37, 46, 47, 47, 11],
                [36, 37],
                [36, 37],
                [18, 19, 11, 28, 29, 21, 38, 39, 31, 41, 42, 43, 44],
                [45, 38],
                [45, 38],  # dealer (seat 3) discards haku (45) first
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    result = parse_tenhou_log_full(log, hero_seat=0)
    pon_opps = [o for o in result.call_opportunities if o.can_pon and o.tile.to_str() == "5z"]
    assert len(pon_opps) == 1
    assert pon_opps[0].called is False
    review = review_call(pon_opps[0])
    assert review is not None
    assert review.recommended == "call"
