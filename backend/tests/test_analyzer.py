from mahjong_review.analyzer import HeroState, review_decision
from mahjong_review.danger import Threat, ThreatKind
from mahjong_review.tiles import NUM_TILE_TYPES, Tile, tile_counts, tiles_from_str


def _visible_from(hand, *extras):
    v = list(tile_counts(hand))
    for group in extras:
        for t in group:
            v[t.tid] += 1
    return v


def test_genbutsu_is_recommended_over_middle_tile():
    # Hero hand has a clearly safe genbutsu (1z) and a clearly dangerous 5m.
    hand = tiles_from_str("123m 5m 456p 789s 11z 1z")
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("1z 9p 2s"),
        discards_after_threat=tiles_from_str("1z"),
    )
    visible = _visible_from(hand, threat.discards)
    hero = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)
    review = review_decision(Tile.from_str("5m"), hero, [threat], visible)
    assert review.label in ("mistake", "blunder", "inaccuracy")
    assert review.recommendation.tile.to_str() == "1z"
    assert review.your_choice.danger > review.recommendation.danger


def test_picking_genbutsu_is_best():
    hand = tiles_from_str("123m 5m 456p 789s 11z 1z")
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("1z 9p 2s"),
        discards_after_threat=tiles_from_str("1z"),
    )
    visible = _visible_from(hand, threat.discards)
    hero = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)
    review = review_decision(Tile.from_str("1z"), hero, [threat], visible)
    assert review.label in ("best", "good")
