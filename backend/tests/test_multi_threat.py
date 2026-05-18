from mahjong_review.analyzer import HeroState, review_decision
from mahjong_review.danger import Threat, ThreatKind
from mahjong_review.tiles import Tile, tile_counts, tiles_from_str


def _visible_from(hand, *groups):
    v = list(tile_counts(hand))
    for g in groups:
        for t in g:
            v[t.tid] += 1
    return v


def test_double_riichi_increases_danger():
    hand = tiles_from_str("123m 5m 456p 789s 11z 1z")
    # both downstream and across riichied, neither has discarded 5m or 1z post-riichi
    t1 = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("9p"),
        discards_after_threat=tiles_from_str("9p"),
    )
    t2 = Threat(
        player=2,
        kind=ThreatKind.RIICHI,
        declared_turn=5,
        discards=tiles_from_str("3z"),
        discards_after_threat=tiles_from_str("3z"),
    )
    visible = _visible_from(hand, t1.discards, t2.discards)
    hero = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)

    review = review_decision(Tile.from_str("5m"), hero, [t1, t2], visible)
    # 5m is genbutsu against neither, so danger should be high; the situation mentions both
    assert "另有威脅" in review.situation
    five_m_alt = next(a for a in review.alternatives if a.tile.to_str() == "5m")
    # multi-threat combined danger should be > single-threat danger for 5m
    one_m_alt = next(a for a in review.alternatives if a.tile.to_str() == "1m")
    assert five_m_alt.danger >= one_m_alt.danger


def test_single_threat_situation_omits_secondary():
    hand = tiles_from_str("123m 5m 456p 789s 11z 1z")
    t1 = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("1z"),
        discards_after_threat=tiles_from_str("1z"),
    )
    visible = _visible_from(hand, t1.discards)
    hero = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)

    review = review_decision(Tile.from_str("1z"), hero, [t1], visible)
    assert "另有威脅" not in review.situation
