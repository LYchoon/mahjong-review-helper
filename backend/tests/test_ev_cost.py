from mahjong_review.danger import Threat, ThreatKind
from mahjong_review.ev import DEAL_IN_COST, estimate_deal_in_cost
from mahjong_review.tiles import tiles_from_str


def test_dragon_call_raises_cost():
    base = Threat(
        player=1,
        kind=ThreatKind.DAMA_TENPAI,
        declared_turn=8,
        discards=[],
        discards_after_threat=[],
        called_tiles=[],
        dora_indicators=tiles_from_str("1m"),
    )
    haku_call = Threat(
        player=1,
        kind=ThreatKind.DAMA_TENPAI,
        declared_turn=8,
        discards=[],
        discards_after_threat=[],
        called_tiles=tiles_from_str("5z 5z 5z"),  # haku pon
        dora_indicators=tiles_from_str("1m"),
    )
    base_cost = estimate_deal_in_cost(base)
    haku_cost = estimate_deal_in_cost(haku_call)
    assert haku_cost > base_cost
    # at least a confirmed yakuhai han is worth ~1500
    assert haku_cost - base_cost >= 1000


def test_extra_dora_indicators_raise_cost():
    one_dora = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=[],
        discards_after_threat=[],
        called_tiles=[],
        dora_indicators=tiles_from_str("1m"),
    )
    three_dora = Threat(
        player=1,
        kind=ThreatKind.RIICHI,
        declared_turn=4,
        discards=[],
        discards_after_threat=[],
        called_tiles=[],
        dora_indicators=tiles_from_str("1m 2p 3s"),
    )
    assert estimate_deal_in_cost(three_dora) > estimate_deal_in_cost(one_dora)


def test_baseline_unchanged_for_no_calls():
    plain = Threat(
        player=1,
        kind=ThreatKind.DAMA_TENPAI,
        declared_turn=8,
        discards=[],
        discards_after_threat=[],
        called_tiles=[],
        dora_indicators=tiles_from_str("1m"),
    )
    assert estimate_deal_in_cost(plain) == DEAL_IN_COST[ThreatKind.DAMA_TENPAI]
