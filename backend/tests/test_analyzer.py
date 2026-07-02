from mahjong_review.analyzer import HeroState, review_decision
from mahjong_review.danger import Threat, ThreatKind
from mahjong_review.tiles import Tile, tile_counts, tiles_from_str


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


def test_furiten_reduces_win_probability():
    # Hand: 234m 567p 234s 678s 1z 9m — discarding 9m leaves a 1z tanki tenpai.
    # If our own pond already contains 1z, that wait is furiten.
    hand = tiles_from_str("234m 567p 234s 678s 1z 9m")
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("2p 8m"),
        discards_after_threat=tiles_from_str("2p"),
    )
    visible = _visible_from(hand, threat.discards)
    base = HeroState(seat=0, hand=hand, turn=6, turns_remaining=10)
    clean = review_decision(Tile.from_str("9m"), base, [threat], visible)

    furiten_hero = HeroState(
        seat=0, hand=hand, turn=6, turns_remaining=10,
        own_discards=tiles_from_str("1z"),
    )
    furiten = review_decision(Tile.from_str("9m"), furiten_hero, [threat], visible)

    assert furiten.your_decision.win_prob < clean.your_decision.win_prob
    assert any("振聽" in r for r in furiten.your_decision.reasons)


def test_melded_hand_is_reviewable():
    # 1 meld → 11-tile concealed hand (pre-discard) must be accepted.
    hand = tiles_from_str("234m 567p 22s 1z 5m")
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("1z 9p"),
        discards_after_threat=tiles_from_str("1z"),
    )
    visible = _visible_from(hand, threat.discards)
    hero = HeroState(seat=0, hand=hand, melds_count=1, turn=6, turns_remaining=10)
    review = review_decision(Tile.from_str("1z"), hero, [threat], visible)
    assert review.your_choice.danger == 0.0


def test_efficiency_review_no_threats():
    # 234m 567p 234s 678s 1z 9m — best is discarding 1z or 9m to keep tenpai;
    # cutting 4s instead breaks a completed run.
    hand = tiles_from_str("234m 567p 234s 678s 1z 9m")
    visible = _visible_from(hand)
    hero = HeroState(seat=0, hand=hand, turn=5, turns_remaining=12)

    good = review_decision(Tile.from_str("9m"), hero, [], visible)
    assert good.decision_type == "efficiency"
    assert good.your_choice.shanten_after == 0
    assert all(a.danger == 0.0 for a in good.alternatives)
    assert all(not a.factors for a in good.alternatives)

    bad = review_decision(Tile.from_str("4s"), hero, [], visible)
    assert bad.decision_type == "efficiency"
    assert bad.your_choice.shanten_after > good.your_choice.shanten_after
    assert bad.your_decision.push_ev < good.your_decision.push_ev
    assert bad.label != "best"


def test_efficiency_summary_counts():
    from mahjong_review.analyzer import summarise_game

    hand = tiles_from_str("234m 567p 234s 678s 1z 9m")
    visible = _visible_from(hand)
    hero = HeroState(seat=0, hand=hand, turn=5, turns_remaining=12)
    eff = review_decision(Tile.from_str("9m"), hero, [], visible)

    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=tiles_from_str("2p 8m"),
        discards_after_threat=tiles_from_str("2p"),
    )
    dfs = review_decision(Tile.from_str("9m"), hero, [threat], visible)

    s = summarise_game([eff, dfs])
    assert s.total == 2
    assert s.efficiency_total == 1
    assert s.defense_total == 1
