from mahjong_review.danger import Threat, ThreatKind, assess_tile
from mahjong_review.tiles import NUM_TILE_TYPES, Tile, tiles_from_str


def test_honitsu_pattern_makes_suit_more_dangerous():
    # threat discarded lots of m and p but zero s — they may be on souzu honitsu.
    # Pick a tile NOT in their discards (avoids genbutsu short-circuit).
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=10,
        discards=tiles_from_str("1m 2m 3m 4m 5p 6p 7p 8p"),
        discards_after_threat=[],
    )
    visible = [0] * NUM_TILE_TYPES
    s5 = assess_tile(Tile.from_str("5s"), threat, visible)
    p9 = assess_tile(Tile.from_str("9p"), threat, visible)
    assert s5.score > p9.score
    assert any(f.code == "SUIT_CONCENTRATION" for f in s5.factors)
    assert any(f.code == "SUIT_ABANDONED" for f in p9.factors)


def test_balanced_discards_no_suit_factor():
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=10,
        discards=tiles_from_str("1m 2p 3s 9m 8p 7s"),
        discards_after_threat=[],
    )
    visible = [0] * NUM_TILE_TYPES
    a = assess_tile(Tile.from_str("5s"), threat, visible)
    assert not any(
        f.code in ("SUIT_CONCENTRATION", "SUIT_ABANDONED") for f in a.factors
    )
