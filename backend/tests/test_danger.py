from mahjong_review.danger import Threat, ThreatKind, assess_tile
from mahjong_review.tiles import NUM_TILE_TYPES, Tile, tiles_from_str


def _empty_visible() -> list[int]:
    return [0] * NUM_TILE_TYPES


def test_genbutsu_is_safe():
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=5,
        discards=tiles_from_str("1m 5p 7s"),
        discards_after_threat=tiles_from_str("5p 7s"),
    )
    visible = _empty_visible()
    a = assess_tile(Tile.from_str("5p"), threat, visible)
    assert a.score == 0
    assert any(f.code == "GENBUTSU" for f in a.factors)


def test_furiten_pre_riichi_is_safe():
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=5,
        discards=tiles_from_str("1m 5p 7s"),  # 5p was discarded before riichi
        discards_after_threat=tiles_from_str("9m"),
    )
    visible = _empty_visible()
    a = assess_tile(Tile.from_str("5p"), threat, visible)
    assert a.score == 0
    assert any(f.code == "GENBUTSU_PRE" for f in a.factors)


def test_suji_reduces_danger():
    # Threat discarded 4m. Now 1m and 7m are "片筋" — safer against ryanmen on 4m.
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=5,
        discards=tiles_from_str("4m"),
        discards_after_threat=tiles_from_str("4m"),
    )
    visible = _empty_visible()
    a_no_suji = assess_tile(Tile.from_str("5p"), threat, visible)
    a_suji = assess_tile(Tile.from_str("7m"), threat, visible)
    assert a_suji.score < a_no_suji.score
    assert any(f.code == "SUJI_47" for f in a_suji.factors)


def test_honor_visibility():
    # If 3 of an honor are visible, the 4th is very safe.
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=10,  # late riichi avoids the early-riichi bonus
        discards=[],
        discards_after_threat=[],
    )
    visible = _empty_visible()
    visible[Tile.from_str("3z").tid] = 3
    a = assess_tile(Tile.from_str("3z"), threat, visible)
    assert a.score < 5


def test_kabe_reduces_danger():
    # All 4 of 4m visible -> any 4m kabe means ryanmen waits relying on 4m can't be held.
    threat = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=5,
        discards=[],
        discards_after_threat=[],
    )
    base_visible = _empty_visible()
    a_baseline = assess_tile(Tile.from_str("5m"), threat, base_visible)
    kabe_visible = _empty_visible()
    kabe_visible[Tile.from_str("4m").tid] = 4
    a_kabe = assess_tile(Tile.from_str("5m"), threat, kabe_visible)
    assert a_kabe.score < a_baseline.score


def test_dama_threat_softer_than_riichi():
    discards = tiles_from_str("1z 2z 9m")
    riichi = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=5,
        discards=discards,
        discards_after_threat=discards,
    )
    dama = Threat(
        player=1,
        kind=ThreatKind.DAMA_TENPAI,
        declared_turn=5,
        discards=discards,
        discards_after_threat=[],
    )
    visible = _empty_visible()
    tile = Tile.from_str("5m")
    assert assess_tile(tile, dama, visible).score < assess_tile(tile, riichi, visible).score
