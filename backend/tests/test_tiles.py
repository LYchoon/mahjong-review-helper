from mahjong_review.tiles import Tile, tiles_from_str, tiles_to_str


def test_tile_from_str():
    assert Tile.from_str("1m").tid == 0
    assert Tile.from_str("9m").tid == 8
    assert Tile.from_str("1p").tid == 9
    assert Tile.from_str("1s").tid == 18
    assert Tile.from_str("1z").tid == 27
    assert Tile.from_str("7z").tid == 33
    red = Tile.from_str("0m")
    assert red.tid == 4 and red.red


def test_compact_parse():
    tiles = tiles_from_str("123m 0p 5s 11z")
    assert [t.to_str() for t in tiles] == ["1m", "2m", "3m", "0p", "5s", "1z", "1z"]


def test_compact_roundtrip():
    s = "123m 456p 789s 1z 1z"
    assert tiles_to_str(tiles_from_str(s)) == "123m 456p 789s 11z"
