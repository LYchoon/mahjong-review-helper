"""Sanity tests for the tenhou parser using synthetic minimal logs."""

import json
from pathlib import Path

from mahjong_review.parsers.tenhou import _parse_call, parse_tenhou_log

SAMPLE_PATH = Path(__file__).parent.parent.parent / "sample_logs" / "riichi_defense_demo.json"


def test_sample_log_yields_defense_snapshots():
    data = json.loads(SAMPLE_PATH.read_text())
    snaps = parse_tenhou_log(data, hero_seat=0)
    # demo log has seat-1 riichi on turn 4 and 6 hero discards after that
    assert len(snaps) >= 5
    assert all(any(t.kind.value == "riichi" for t in s.threats) for s in snaps)


def test_snapshot_carries_full_visible_state():
    data = json.loads(SAMPLE_PATH.read_text())
    snaps = parse_tenhou_log(data, hero_seat=0)
    for s in snaps:
        # visible counts must never exceed 4 per tile id
        assert all(0 <= c <= 4 for c in s.visible_counts)
        # hand at snapshot is 14 (pre-discard) or 13 if called melds
        assert len(s.hero_hand) in (14, 14 - 3 * s.hero_melds_count)


def test_parser_handles_call_string_in_draws():
    """Tiny synthetic round with a chi call; verify melds_count goes up and a
    snapshot taken after riichi includes the open meld."""
    haipai = [[11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 42, 42] for _ in range(4)]
    # Seat 1 chi-calls right after seat 0's first discard, then later seat 2 riichis.
    log = {
        "title": ["test", ""],
        "name": ["a", "b", "c", "d"],
        "rule": {},
        "log": [
            [
                [0, 0, 0],
                [25000] * 4,
                [41],
                [],
                haipai[0], [14, 15, 16, 17], [14, 15, 16, 17],
                haipai[1], ["c111213", 24, 25, 26], [27, 28, 29, 32],
                haipai[2], [33, 34, 35, 36], [f"r{33}", 34, 35, 36],
                haipai[3], [37, 38, 39, 41], [37, 38, 39, 41],
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    snaps = parse_tenhou_log(log, hero_seat=0)
    # snapshots will exist after seat 2's riichi
    assert len(snaps) >= 1
    # the called meld for seat 1 should be tracked
    last = snaps[-1]
    assert any(len(seat_melds) > 0 for seat_melds in last.open_melds)


def test_parse_call_decodes_marker_anywhere():
    # chi: marker first, called tile right after
    assert _parse_call("c111213") == ("c", [11, 12, 13], 11)
    # pon called from across: marker mid-string
    assert _parse_call("41p4141") == ("p", [41, 41, 41], 41)
    # ankan
    assert _parse_call("121212a12") == ("a", [12, 12, 12, 12], 12)


def test_hero_ankan_removes_tiles_from_hand():
    """After the hero declares an ankan, later snapshots must not contain the
    four kan tiles, and the hand size must shrink by 3 (kan − rinshan draw)."""
    log = {
        "title": ["test", ""],
        "name": ["a", "b", "c", "d"],
        "rule": {},
        "log": [
            [
                [0, 0, 0],
                [25000] * 4,
                [46],
                [],
                # hero: four 1m + 123p + 123s + ESW
                [11, 11, 11, 11, 21, 22, 23, 31, 32, 33, 41, 42, 43],
                [24, 25, 26],
                ["111111a11", 41, 42],  # ankan in the discard slot, then discards
                [12, 13, 14, 22, 23, 24, 32, 33, 34, 44, 44, 45, 45],
                [33, 34],
                ["r33", 34],  # seat 1 declares riichi
                [15, 16, 17, 25, 26, 27, 35, 36, 37, 46, 46, 47, 47],
                [36, 37],
                [36, 37],
                [18, 19, 11, 28, 29, 21, 38, 39, 31, 41, 42, 43, 44],
                [45, 46],
                [45, 46],
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    snaps = parse_tenhou_log(log, hero_seat=0)
    assert len(snaps) >= 1
    snap = snaps[0]
    assert snap.hero_melds_count == 1
    assert len(snap.hero_hand) == 14 - 3 * snap.hero_melds_count
    # the four 1m are locked in the kan, not in the concealed hand
    assert all(t.tid != 0 for t in snap.hero_hand)
    # hero's own kan tiles were already counted from the haipai — still exactly 4
    assert snap.visible_counts[0] == 4


def test_hero_chi_removes_used_tiles_from_hand():
    """A hero chi must remove the two tiles used from the concealed hand."""
    log = {
        "title": ["test", ""],
        "name": ["a", "b", "c", "d"],
        "rule": {},
        "log": [
            [
                [1, 0, 0],  # E2: dealer is seat 1
                [25000] * 4,
                [46],
                [],
                [12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 44, 45],
                ["c111213", 24],
                [41, 42],
                [14, 15, 16, 24, 25, 26, 34, 35, 36, 44, 44, 45, 45],
                [33, 34],
                ["r33", 34],  # seat 1 declares riichi
                [15, 16, 17, 25, 26, 27, 35, 36, 37, 46, 46, 47, 47],
                [36, 37],
                [36, 37],
                [18, 19, 11, 28, 29, 21, 38, 39, 31, 41, 42, 43, 44],
                [45, 46],
                [45, 46],
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    snaps = parse_tenhou_log(log, hero_seat=0)
    assert len(snaps) >= 1
    snap = snaps[0]
    assert snap.hero_melds_count == 1
    assert len(snap.hero_hand) == 14 - 3 * snap.hero_melds_count
    assert snap.round_number == 1


def test_snapshot_round_number_from_round_info():
    data = json.loads(SAMPLE_PATH.read_text())
    snaps = parse_tenhou_log(data, hero_seat=0)
    assert all(s.round_number == 0 for s in snaps)  # demo log is East-1
