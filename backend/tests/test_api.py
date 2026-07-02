"""FastAPI endpoint tests via TestClient."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from mahjong_review.api.main import app

client = TestClient(app)

SAMPLE_PATH = Path(__file__).parent.parent.parent / "sample_logs" / "riichi_defense_demo.json"


def _manual_request(**overrides):
    req = {
        "hand": "123m 456p 789s 11z 5p 6p 7p",
        "chosen_discard": "1z",
        "turn": 8,
        "turns_remaining": 8,
        "threats": [
            {
                "player": 1,
                "kind": "riichi",
                "declared_turn": 6,
                "discards": ["1z", "9p", "2s"],
                "discards_after_threat": ["1z"],
            }
        ],
    }
    req.update(overrides)
    return req


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_manual_review_ok():
    resp = client.post("/review/manual", json=_manual_request())
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] in ("best", "good", "inaccuracy", "mistake", "blunder")
    # 1z is genbutsu (in discards_after_threat) → the safest possible call
    assert body["your_choice"]["danger"] == 0.0


def test_manual_review_without_threat_runs_efficiency_review():
    resp = client.post("/review/manual", json=_manual_request(threats=[]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision_type"] == "efficiency"
    assert all(a["danger"] == 0.0 for a in body["alternatives"])


def test_manual_review_rejects_bad_discard():
    resp = client.post("/review/manual", json=_manual_request(chosen_discard="1z 2z"))
    assert resp.status_code == 400


def test_manual_review_rejects_unknown_threat_kind():
    req = _manual_request()
    req["threats"][0]["kind"] = "psychic"
    resp = client.post("/review/manual", json=req)
    assert resp.status_code == 400


def test_manual_review_counts_threat_discards_as_visible():
    """Threat discards must feed kabe logic: with all four 8p in the threat's
    pond, a 9p can no longer be hit by any ryanmen/kanchan → no-chance."""
    req = _manual_request(
        hand="123m 456m 789m 11z 9p 5s 6s",
        chosen_discard="9p",
        threats=[
            {
                "player": 1,
                "kind": "riichi",
                "declared_turn": 6,
                "discards": ["8p", "8p", "8p", "8p", "1m"],
                "discards_after_threat": [],
            }
        ],
    )
    resp = client.post("/review/manual", json=req)
    assert resp.status_code == 200
    codes = [f["code"] for f in resp.json()["your_choice"]["factors"]]
    assert "NO_CHANCE" in codes


def test_tenhou_review_sample_log():
    log = json.loads(SAMPLE_PATH.read_text())
    resp = client.post("/review/tenhou", json={"log": log, "hero_seat": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total"] == len(body["decisions"]) > 0
    if body["summary"]["biggest_blunder_index"] is not None:
        assert 0 <= body["summary"]["biggest_blunder_index"] < len(body["decisions"])
    # demo log is a single East-1 round
    assert all(d["board"]["round_label"] == "東1" for d in body["decisions"])


def test_tenhou_review_south_round_uses_round_number():
    """Dealer / seat wind / round label must come from the tenhou round id
    (round_info[0]), not from the round's position in the log array."""
    haipai = [[11, 12, 13, 21, 22, 23, 31, 32, 33, 41, 42, 43, 44] for _ in range(4)]
    log = {
        "title": ["test", ""],
        "name": ["a", "b", "c", "d"],
        "rule": {},
        "log": [
            [
                [5, 0, 0],  # South 2: dealer is seat 1
                [25000] * 4,
                [41],
                [],
                haipai[0], [24, 25, 26], [24, 25, 26],
                haipai[1], [33, 34, 35], ["r33", 34, 35],
                haipai[2], [36, 37, 38], [36, 37, 38],
                haipai[3], [45, 45, 46], [45, 45, 46],
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    resp = client.post("/review/tenhou", json={"log": log, "hero_seat": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["decisions"]) >= 1
    assert body["decisions"][0]["board"]["round_label"] == "南2"


def test_tenhou_review_rejects_garbage():
    resp = client.post("/review/tenhou", json={"log": {"log": [[1, 2]]}, "hero_seat": 0})
    assert resp.status_code == 400


def _msact(name, **data):
    return {"name": f".lq.Record{name}", "data": data}


def test_majsoul_review_endpoint():
    hands = {
        0: ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "5s", "5z"],
        1: ["1s", "2s", "3s", "4p", "5p", "6p", "7p", "8p", "9p", "2z", "2z", "3z", "3z"],
        2: ["4s", "5s", "6s", "1m", "2m", "3m", "4m", "5m", "6m", "4z", "4z", "5z", "5z"],
        3: ["7s", "8s", "9s", "1p", "2p", "3p", "4p", "5p", "6p", "6z", "6z", "7z", "7z"],
    }
    log = {
        "head": {"uuid": "test"},
        "data": [
            _msact(
                "NewRound",
                chang=1, ju=0, ben=0, liqibang=0, doras=["1z"],
                **{f"tiles{s}": t for s, t in hands.items()},
            ),
            _msact("DiscardTile", seat=0, tile="5z"),
            _msact("DealTile", seat=1, tile="4z"),
            _msact("DiscardTile", seat=1, tile="4z", is_liqi=True),
            _msact("DealTile", seat=2, tile="9m"),
            _msact("DiscardTile", seat=2, tile="9m"),
            _msact("DealTile", seat=3, tile="9p"),
            _msact("DiscardTile", seat=3, tile="9p"),
            _msact("DealTile", seat=0, tile="6s"),
            _msact("DiscardTile", seat=0, tile="6s"),
            _msact("NoTile"),
        ],
    }
    resp = client.post("/review/majsoul", json={"log": log, "hero_seat": 0})
    assert resp.status_code == 200
    body = resp.json()
    # hero's first discard (no threat) = efficiency, second (under riichi) = defense
    assert body["summary"]["total"] == 2
    assert body["summary"]["efficiency_total"] == 1
    assert body["summary"]["defense_total"] == 1
    assert [d["decision_type"] for d in body["decisions"]] == ["efficiency", "defense"]
    assert body["decisions"][0]["board"]["round_label"] == "南1"


def test_majsoul_review_rejects_garbage():
    resp = client.post("/review/majsoul", json={"log": {"foo": "bar"}, "hero_seat": 0})
    assert resp.status_code == 400


def test_tenhou_hero_riichi_flow():
    """Hero declares riichi: the declaration discard carries riichi advice with
    declared=True, and forced post-riichi discards are not reviewed."""
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
                # hero (dealer): 234m 567p 234s 678s 1z + 9m, tenpai on 1z after 9m cut
                [12, 13, 14, 25, 26, 27, 32, 33, 34, 36, 37, 38, 41],
                [19, 15, 16],
                ["r19", "60", "60"],  # riichi discarding the drawn 9m, then tsumogiri
                [14, 15, 16, 24, 25, 26, 34, 35, 36, 44, 44, 45, 45],
                [33, 34, 35],
                [33, 34, 35],
                [15, 16, 17, 25, 26, 27, 35, 36, 37, 46, 46, 47, 47],
                [36, 37, 38],
                [36, 37, 38],
                [18, 19, 11, 28, 29, 21, 38, 39, 31, 41, 42, 43, 44],
                [45, 46, 47],
                [45, 46, 47],
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    resp = client.post("/review/tenhou", json={"log": log, "hero_seat": 0})
    assert resp.status_code == 200
    body = resp.json()
    # only the riichi declaration itself is a decision; forced discards skipped
    assert len(body["decisions"]) == 1
    d = body["decisions"][0]
    assert d["riichi"] is not None
    assert d["riichi"]["declared"] is True
    assert d["riichi"]["recommended"] is True  # tanki 1z, no yaku dama
    assert "calls" in body


def test_tenhou_missed_yakuhai_pon_reported():
    log = {
        "title": ["test", ""],
        "name": ["a", "b", "c", "d"],
        "rule": {},
        "log": [
            [
                [3, 0, 0],  # dealer = seat 3, so seat 3 discards before hero acts
                [25000] * 4,
                [41],
                [],
                [45, 45, 12, 13, 21, 22, 23, 31, 32, 33, 42, 43, 44],
                [24],
                [24],
                [14, 15, 16, 24, 25, 26, 34, 35, 36, 44, 44, 46, 46],
                [33],
                [33],
                [15, 16, 17, 25, 26, 27, 35, 36, 37, 46, 47, 47, 11],
                [36],
                [36],
                [18, 19, 11, 28, 29, 21, 38, 39, 31, 41, 42, 43, 44],
                [45],
                [45],  # seat 3 discards haku; hero holds two and passes
                ["流局", [0, 0, 0, 0]],
            ]
        ],
    }
    resp = client.post("/review/tenhou", json={"log": log, "hero_seat": 0})
    assert resp.status_code == 200
    calls = resp.json()["calls"]
    missed = [c for c in calls if c["tile"] == "5z"]
    assert len(missed) == 1
    assert missed[0]["actual"] == "passed"
    assert missed[0]["recommended"] == "call"
