"""Majsoul (雀魂) game record parser.

Majsoul's native paipu is protobuf; every common download tool (mjsoul-paipu-
downloader, amae-koromo derivatives, the in-browser devtool exporters, ...)
decodes it into a JSON action stream. This parser accepts that decoded form:

    {
      "head": { ... game metadata ... },
      "data": [                       # also accepted under "record"/"actions",
        {"name": ".lq.RecordNewRound",     "data": {...}},   # or bare list
        {"name": ".lq.RecordDealTile",     "data": {...}},
        {"name": ".lq.RecordDiscardTile",  "data": {...}},
        {"name": ".lq.RecordChiPengGang",  "data": {...}},
        {"name": ".lq.RecordAnGangAddGang","data": {...}},
        {"name": ".lq.RecordHule",         "data": {...}},
        ...
      ]
    }

The ".lq." prefix is optional. Tile notation is majsoul strings: "1m".."9m",
"0m"/"0p"/"0s" = red fives, "1z".."7z" honors.

Action fields used:
    RecordNewRound:      chang (0=E,1=S,2=W), ju (dealer seat), ben (honba),
                         liqibang, doras / dora, tiles0..tiles3 (haipai; the
                         dealer's list has 14 tiles)
    RecordDealTile:      seat, tile, doras (full current indicator list)
    RecordDiscardTile:   seat, tile, is_liqi / is_wliqi, doras
    RecordChiPengGang:   seat, type (0=chi 1=pon 2=daiminkan), tiles, froms
    RecordAnGangAddGang: seat, type (3=ankan 2=kakan), tiles (single string)

Like the tenhou parser, this emits a `Snapshot` per hero discard; snapshots
without opponent threats get an efficiency review from the analyser.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..tiles import Tile
from .common import CallOpportunity, ParseResult, Snapshot, build_threats

__all__ = [
    "parse_majsoul_log",
    "parse_majsoul_log_full",
    "parse_majsoul_file",
    "looks_like_majsoul_log",
]


def parse_majsoul_log(raw: str | dict[str, Any] | list[Any], hero_seat: int) -> list[Snapshot]:
    """Parse a decoded majsoul record into hero discard decision points."""
    return parse_majsoul_log_full(raw, hero_seat).snapshots


def parse_majsoul_log_full(
    raw: str | dict[str, Any] | list[Any], hero_seat: int
) -> ParseResult:
    """Like parse_majsoul_log but also returns the hero's call opportunities."""
    data = json.loads(raw) if isinstance(raw, str) else raw
    actions = _extract_actions(data)
    if not actions:
        raise ValueError("no majsoul record actions found (expected data/record/actions list)")

    result = ParseResult(snapshots=[], call_opportunities=[])
    state: _RoundState | None = None
    round_idx = -1
    for name, act in actions:
        if name == "RecordNewRound":
            round_idx += 1
            state = _RoundState(act, round_idx, hero_seat)
        elif state is None:
            continue
        elif name == "RecordDealTile":
            state.on_deal(act)
        elif name == "RecordDiscardTile":
            state.on_discard(act, result.snapshots, result.call_opportunities)
        elif name == "RecordChiPengGang":
            state.on_call(act)
        elif name == "RecordAnGangAddGang":
            state.on_kan(act)
        elif name in ("RecordHule", "RecordNoTile", "RecordLiuJu"):
            state = None
    return result


def parse_majsoul_file(path: str | Path, hero_seat: int) -> list[Snapshot]:
    return parse_majsoul_log(Path(path).read_text(), hero_seat)


def looks_like_majsoul_log(data: Any) -> bool:
    """Cheap structural sniff used for format auto-detection."""
    try:
        return bool(_extract_actions(data))
    except Exception:
        return False


# --- internals ---


def _extract_actions(data: Any) -> list[tuple[str, dict[str, Any]]]:
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("data") or data.get("record") or data.get("actions") or []
    else:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for e in entries:
        if not isinstance(e, dict) or "name" not in e:
            continue
        name = str(e["name"]).rsplit(".", 1)[-1]
        payload = e.get("data", {})
        if isinstance(payload, dict) and name.startswith("Record"):
            out.append((name, payload))
    return out


def _tile(s: str) -> Tile:
    return Tile.from_str(s)


class _RoundState:
    def __init__(self, act: dict[str, Any], round_idx: int, hero_seat: int) -> None:
        chang = int(act.get("chang", 0))
        ju = int(act.get("ju", 0))
        self.round_idx = round_idx
        self.round_number = chang * 4 + ju
        self.round_wind = 27 + chang
        self.honba = int(act.get("ben", 0))
        self.riichi_sticks = int(act.get("liqibang", 0))
        self.hero_seat = hero_seat

        doras = act.get("doras") or ([act["dora"]] if act.get("dora") else [])
        self.dora_inds = [_tile(d) for d in doras]

        self.hands: list[list[Tile]] = []
        for seat in range(4):
            tiles = act.get(f"tiles{seat}") or []
            self.hands.append([_tile(t) for t in tiles])

        self.melds_count = [0, 0, 0, 0]
        self.open_melds: list[list[list[Tile]]] = [[] for _ in range(4)]
        self.discard_piles: list[list[Tile]] = [[] for _ in range(4)]
        self.riichi_declared_turn: list[int | None] = [None, None, None, None]
        self.discards_after_riichi: list[list[Tile]] = [[] for _ in range(4)]
        self.turn_counter = [0, 0, 0, 0]

        self.visible = [0] * 34
        for ind in self.dora_inds:
            self._bump(ind.tid)
        for t in self.hands[hero_seat]:
            self._bump(t.tid)

        # the most recent hero call opportunity, resolved by the next action
        self._last_opportunity: CallOpportunity | None = None

    def _bump(self, tid: int) -> None:
        if self.visible[tid] < 4:
            self.visible[tid] += 1

    def _update_doras(self, act: dict[str, Any]) -> None:
        doras = act.get("doras")
        if not doras or len(doras) <= len(self.dora_inds):
            return
        new = [_tile(d) for d in doras]
        for ind in new[len(self.dora_inds) :]:
            self._bump(ind.tid)
        self.dora_inds = new

    def _remove_from_hand(self, seat: int, tile: Tile) -> None:
        hand = self.hands[seat]
        for i, t in enumerate(hand):
            if t.tid == tile.tid and t.red == tile.red:
                del hand[i]
                return
        for i, t in enumerate(hand):  # tolerate red/plain mismatches
            if t.tid == tile.tid:
                del hand[i]
                return

    def on_deal(self, act: dict[str, Any]) -> None:
        self._last_opportunity = None  # a draw means nobody called the discard
        seat = int(act.get("seat", 0))
        tile = _tile(act["tile"])
        self.hands[seat].append(tile)
        if seat == self.hero_seat:
            self._bump(tile.tid)
        self._update_doras(act)

    def on_discard(
        self,
        act: dict[str, Any],
        snaps: list[Snapshot],
        opportunities: list[CallOpportunity] | None = None,
    ) -> None:
        seat = int(act.get("seat", 0))
        tile = _tile(act["tile"])
        riichi_now = bool(act.get("is_liqi") or act.get("is_wliqi"))
        self.turn_counter[seat] += 1
        if seat != self.hero_seat:
            self._bump(tile.tid)

        self.discard_piles[seat].append(tile)
        if self.riichi_declared_turn[seat] is not None:
            self.discards_after_riichi[seat].append(tile)

        if seat == self.hero_seat:
            # skip forced tsumogiri while the hero is already in riichi
            already_riichi = (
                self.riichi_declared_turn[seat] is not None and not riichi_now
            )
            # only full-size hands are reviewable (14 - 3*melds pre-discard)
            if not already_riichi and len(self.hands[seat]) == 14 - 3 * self.melds_count[seat]:
                threats = build_threats(
                    self.hero_seat,
                    self.discard_piles,
                    self.discards_after_riichi,
                    self.riichi_declared_turn,
                    self.melds_count,
                    self.dora_inds,
                    self.open_melds,
                )
                snaps.append(
                    Snapshot(
                        round_index=self.round_idx,
                        round_number=self.round_number,
                        round_wind=self.round_wind,
                        honba=self.honba,
                        riichi_sticks=self.riichi_sticks,
                        turn=self.turn_counter[seat],
                        hero_seat=self.hero_seat,
                        hero_hand=sorted(self.hands[seat], key=lambda t: t.tid),
                        hero_melds_count=self.melds_count[seat],
                        hero_chosen_discard=tile,
                        visible_counts=list(self.visible),
                        threats=threats,
                        dora_indicators=list(self.dora_inds),
                        all_discards=[list(p) for p in self.discard_piles],
                        riichi_turns=list(self.riichi_declared_turn),
                        open_melds=[[list(m) for m in s] for s in self.open_melds],
                        hero_riichi_declared_now=riichi_now,
                    )
                )
        elif opportunities is not None:
            self._maybe_record_opportunity(seat, tile, opportunities)

        self._remove_from_hand(seat, tile)
        if riichi_now:
            self.riichi_declared_turn[seat] = self.turn_counter[seat]
        self._update_doras(act)

    def _maybe_record_opportunity(
        self, seat: int, tile: Tile, opportunities: list[CallOpportunity]
    ) -> None:
        if self.riichi_declared_turn[self.hero_seat] is not None:
            return
        hero_hand = self.hands[self.hero_seat]
        if len(hero_hand) != 13 - 3 * self.melds_count[self.hero_seat]:
            return
        can_pon = sum(1 for t in hero_hand if t.tid == tile.tid) >= 2
        can_chi = False
        if seat == (self.hero_seat + 3) % 4 and tile.suit != "z":
            tids = {t.tid for t in hero_hand}
            r = tile.rank
            suit_off = tile.tid - (r - 1)
            for a, b in ((r - 2, r - 1), (r - 1, r + 1), (r + 1, r + 2)):
                if (
                    1 <= a <= 9
                    and 1 <= b <= 9
                    and (suit_off + a - 1) in tids
                    and (suit_off + b - 1) in tids
                ):
                    can_chi = True
                    break
        if not can_pon and not can_chi:
            return
        threats = build_threats(
            self.hero_seat,
            self.discard_piles,
            self.discards_after_riichi,
            self.riichi_declared_turn,
            self.melds_count,
            self.dora_inds,
            self.open_melds,
        )
        opportunities.append(
            CallOpportunity(
                round_index=self.round_idx,
                round_number=self.round_number,
                round_wind=self.round_wind,
                honba=self.honba,
                turn=self.turn_counter[seat],
                hero_seat=self.hero_seat,
                tile=tile,
                can_pon=can_pon,
                can_chi=can_chi,
                called=False,  # flipped by on_call when the hero takes it
                hero_hand=list(hero_hand),
                hero_melds_count=self.melds_count[self.hero_seat],
                hero_meld_tiles=[t for m in self.open_melds[self.hero_seat] for t in m],
                threats_count=len(threats),
            )
        )
        self._last_opportunity = opportunities[-1]

    def on_call(self, act: dict[str, Any]) -> None:
        """Chi / pon / daiminkan (type 0 / 1 / 2)."""
        seat = int(act.get("seat", 0))
        tiles = [_tile(t) for t in act.get("tiles", [])]
        froms = act.get("froms") or [seat] * len(tiles)
        # the record's call action directly follows the discard it takes
        last_opp = getattr(self, "_last_opportunity", None)
        if (
            seat == self.hero_seat
            and last_opp is not None
            and any(t.tid == last_opp.tile.tid for t in tiles)
        ):
            last_opp.called = True
        self._last_opportunity = None
        self.melds_count[seat] += 1
        self.open_melds[seat].append(tiles)
        for t, frm in zip(tiles, froms, strict=False):
            if int(frm) == seat:
                # tile leaves the caller's concealed hand and becomes visible
                self._remove_from_hand(seat, t)
                if seat != self.hero_seat:
                    self._bump(t.tid)
            # the called tile itself was already counted when discarded

    def on_kan(self, act: dict[str, Any]) -> None:
        """Ankan (type 3) / kakan (type 2). `tiles` is a single tile string."""
        seat = int(act.get("seat", 0))
        kind = int(act.get("type", 3))
        raw_tiles = act.get("tiles", "")
        tile = _tile(raw_tiles if isinstance(raw_tiles, str) else raw_tiles[0])

        if kind == 2:  # kakan: one tile from hand joins the existing pon
            self._remove_from_hand(seat, tile)
            if seat != self.hero_seat:
                self._bump(tile.tid)
            for meld in self.open_melds[seat]:
                if len(meld) == 3 and all(t.tid == tile.tid for t in meld):
                    meld.append(tile)
                    break
        else:  # ankan: all four tiles leave the hand
            removed = [t for t in self.hands[seat] if t.tid == tile.tid]
            self.hands[seat] = [t for t in self.hands[seat] if t.tid != tile.tid]
            if seat != self.hero_seat:
                for _ in range(4):
                    self._bump(tile.tid)
            self.melds_count[seat] += 1
            self.open_melds[seat].append(removed if len(removed) == 4 else [tile] * 4)
        self._update_doras(act)
