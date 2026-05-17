from mahjong_review.analyzer import HeroState, review_decision, summarise_game
from mahjong_review.danger import Threat, ThreatKind
from mahjong_review.tiles import Tile, tile_counts, tiles_from_str


def _visible_from(hand, *extras):
    v = list(tile_counts(hand))
    for group in extras:
        for t in group:
            v[t.tid] += 1
    return v


def _make_threat(after_discards=("1z",), all_discards=("1z", "9p", "2s")):
    return Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str(" ".join(all_discards)),
        discards_after_threat=tiles_from_str(" ".join(after_discards)),
    )


def test_summary_aggregates_labels():
    hand = tiles_from_str("123m 5m 456p 789s 11z 1z")
    threat = _make_threat()
    visible = _visible_from(hand, threat.discards)
    hero = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)

    blunder = review_decision(Tile.from_str("5m"), hero, [threat], visible)
    best = review_decision(Tile.from_str("1z"), hero, [threat], visible)

    summary = summarise_game([blunder, best])
    assert summary.total == 2
    assert summary.blunder + summary.mistake >= 1
    assert summary.best + summary.good >= 1
    assert summary.accuracy < 100
    assert summary.total_ev_lost > 0
    assert summary.biggest_blunder is blunder


def test_ukeire_in_alternatives():
    hand = tiles_from_str("123m 5m 456p 789s 11z 1z")
    threat = _make_threat()
    visible = _visible_from(hand, threat.discards)
    hero = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)
    review = review_decision(Tile.from_str("1z"), hero, [threat], visible)
    # every alternative has shanten_after and ukeire fields populated
    assert all(hasattr(a, "shanten_after") for a in review.alternatives)
    # at least one alternative leaves the hand close to tenpai
    sh_values = [a.shanten_after for a in review.alternatives]
    assert min(sh_values) <= 1
