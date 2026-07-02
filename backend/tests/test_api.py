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


def test_manual_review_requires_threat():
    resp = client.post("/review/manual", json=_manual_request(threats=[]))
    assert resp.status_code == 400


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
    assert body["summary"]["total"] == 1
    assert body["decisions"][0]["board"]["round_label"] == "南1"


def test_majsoul_review_rejects_garbage():
    resp = client.post("/review/majsoul", json={"log": {"foo": "bar"}, "hero_seat": 0})
    assert resp.status_code == 400
