"""Sanity tests for the tenhou parser using synthetic minimal logs."""

import json
from pathlib import Path

from mahjong_review.parsers.tenhou import parse_tenhou_log


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
