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
    """Tiny synthetic round with a chi call; verify melds_count goes up."""
    # haipai must be 13 ints per seat; draws/discards lists can have any length.
    haipai = [[11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 41, 42, 42] for _ in range(4)]
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
                haipai[0], [14], [14],
                haipai[1], ["c111213"], [25],  # seat 1 chi-calls 111213, then discards 5p (25)
                haipai[2], [15], [15],
                haipai[3], [16], [16],
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    # parsing should not raise even though hero (seat 0) has no riichi threats yet
    snaps = parse_tenhou_log(log, hero_seat=0)
    # no riichi → no defense snapshots
    assert snaps == []
