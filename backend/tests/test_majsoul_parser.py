"""Tests for the majsoul (雀魂) decoded-record parser."""

from mahjong_review.parsers.majsoul import looks_like_majsoul_log, parse_majsoul_log


def act(name, **data):
    return {"name": f".lq.Record{name}", "data": data}


def new_round(chang=0, ju=0, hero_tiles=None, **extra):
    """Build a RecordNewRound; seat `ju` (the dealer) gets 14 tiles."""
    base = {
        "chang": chang,
        "ju": ju,
        "ben": extra.pop("ben", 0),
        "liqibang": extra.pop("liqibang", 0),
        "doras": extra.pop("doras", ["1z"]),
    }
    hands = {
        0: ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "5s"],
        1: ["1s", "2s", "3s", "4p", "5p", "6p", "7p", "8p", "9p", "2z", "2z", "3z", "3z"],
        2: ["4s", "5s", "6s", "1m", "2m", "3m", "4m", "5m", "6m", "4z", "4z", "5z", "5z"],
        3: ["7s", "8s", "9s", "1p", "2p", "3p", "4p", "5p", "6p", "6z", "6z", "7z", "7z"],
    }
    if hero_tiles:
        hands[0] = hero_tiles
    hands[ju] = hands[ju] + ["5z"]  # dealer's 14th tile
    for seat, tiles in hands.items():
        base[f"tiles{seat}"] = tiles
    base.update(extra)
    return act("NewRound", **base)


def test_basic_riichi_threat_snapshot():
    log = {
        "head": {},
        "data": [
            new_round(),
            act("DiscardTile", seat=0, tile="5z"),  # dealer hero: no threat yet
            act("DealTile", seat=1, tile="4z"),
            act("DiscardTile", seat=1, tile="4z", is_liqi=True),  # seat 1 riichi
            act("DealTile", seat=2, tile="9m"),
            act("DiscardTile", seat=2, tile="9m"),
            act("DealTile", seat=3, tile="9p"),
            act("DiscardTile", seat=3, tile="9p"),
            act("DealTile", seat=0, tile="6s"),
            act("DiscardTile", seat=0, tile="6s"),  # hero discard under threat
            act("NoTile"),
        ],
    }
    snaps = parse_majsoul_log(log, hero_seat=0)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.round_number == 0
    assert snap.round_wind == 27
    assert len(snap.hero_hand) == 14
    assert [t.kind.value for t in snap.threats] == ["riichi"]
    assert snap.threats[0].player == 1
    # riichi discard is genbutsu material: it's in seat 1's pile
    assert any(t.to_str() == "4z" for t in snap.threats[0].discards)


def test_south_round_number_and_wind():
    log = {
        "head": {},
        "data": [
            new_round(chang=1, ju=1),  # South 2, dealer = seat 1
            act("DealTile", seat=1, tile="4z"),
            act("DiscardTile", seat=1, tile="4z", is_liqi=True),
            act("DealTile", seat=2, tile="9m"),
            act("DiscardTile", seat=2, tile="9m"),
            act("DealTile", seat=3, tile="9p"),
            act("DiscardTile", seat=3, tile="9p"),
            act("DealTile", seat=0, tile="6s"),
            act("DiscardTile", seat=0, tile="6s"),
            act("NoTile"),
        ],
    }
    snaps = parse_majsoul_log(log, hero_seat=0)
    assert len(snaps) == 1
    assert snaps[0].round_number == 5
    assert snaps[0].round_wind == 28


def test_hero_ankan_keeps_hand_consistent():
    hero_tiles = [
        "1m", "1m", "1m", "1m", "2p", "3p", "4p", "5s", "6s", "7s", "1z", "2z", "3z",
    ]
    log = {
        "head": {},
        "data": [
            new_round(hero_tiles=hero_tiles),
            act("DiscardTile", seat=0, tile="5z"),
            act("DealTile", seat=1, tile="4z"),
            act("DiscardTile", seat=1, tile="4z", is_liqi=True),
            act("DealTile", seat=2, tile="9m"),
            act("DiscardTile", seat=2, tile="9m"),
            act("DealTile", seat=3, tile="9p"),
            act("DiscardTile", seat=3, tile="9p"),
            act("DealTile", seat=0, tile="8s"),
            act("AnGangAddGang", seat=0, type=3, tiles="1m"),
            act("DealTile", seat=0, tile="9s"),  # rinshan
            act("DiscardTile", seat=0, tile="1z"),
            act("NoTile"),
        ],
    }
    snaps = parse_majsoul_log(log, hero_seat=0)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.hero_melds_count == 1
    assert len(snap.hero_hand) == 14 - 3
    assert all(t.tid != 0 for t in snap.hero_hand)  # no 1m left concealed
    assert snap.visible_counts[0] == 4  # hero's own kan: still counted exactly once


def test_opponent_call_reveals_only_hand_tiles():
    log = {
        "head": {},
        "data": [
            new_round(),
            act("DiscardTile", seat=0, tile="4m"),
            act("ChiPengGang", seat=1, type=0, tiles=["4m", "5p", "6p"], froms=[0, 1, 1]),
            act("DiscardTile", seat=1, tile="2z"),
            act("DealTile", seat=2, tile="9m"),
            act("DiscardTile", seat=2, tile="9m", is_liqi=True),
            act("DealTile", seat=3, tile="9p"),
            act("DiscardTile", seat=3, tile="9p"),
            act("DealTile", seat=0, tile="6s"),
            act("DiscardTile", seat=0, tile="6s"),
            act("NoTile"),
        ],
    }
    snaps = parse_majsoul_log(log, hero_seat=0)
    assert len(snaps) == 1
    snap = snaps[0]
    # seat 1's chi is tracked as an open meld
    assert len(snap.open_melds[1]) == 1
    # 4m (tid 3): hero held & discarded it (pre-counted once); the call must not
    # double count the called tile
    assert snap.visible_counts[3] == 1
    # 5p (tid 13) / 6p (tid 14) came out of seat 1's hand → newly visible
    assert snap.visible_counts[13] == 1
    assert snap.visible_counts[14] == 1


def test_looks_like_majsoul_log():
    assert looks_like_majsoul_log({"data": [act("NewRound", chang=0, ju=0)]})
    assert looks_like_majsoul_log([act("NewRound", chang=0, ju=0)])
    assert not looks_like_majsoul_log({"log": [[[0, 0, 0]]]})  # tenhou shape
    assert not looks_like_majsoul_log("not json-ish")
