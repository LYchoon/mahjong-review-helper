"""Tile representation and conversion.

Internal tile id is an integer 0..33:
    0..8   : 1m .. 9m
    9..17  : 1p .. 9p
    18..26 : 1s .. 9s
    27..33 : East, South, West, North, Haku, Hatsu, Chun

A "Tile" wraps an id plus a `red` flag (aka dora 0m/0p/0s — represented as 4m/4p/4s
internally with red=True so that all engine math works on suit ranks normally).
"""

from __future__ import annotations

from dataclasses import dataclass

NUM_TILE_TYPES = 34
SUIT_OFFSETS = {"m": 0, "p": 9, "s": 18, "z": 27}

HONORS = list(range(27, 34))
EAST, SOUTH, WEST, NORTH, HAKU, HATSU, CHUN = HONORS
WINDS = (EAST, SOUTH, WEST, NORTH)
DRAGONS = (HAKU, HATSU, CHUN)
TERMINALS = (0, 8, 9, 17, 18, 26)  # 1/9 m/p/s
YAOCHUUHAI = tuple(sorted(set(TERMINALS) | set(HONORS)))


@dataclass(frozen=True)
class Tile:
    tid: int  # 0..33
    red: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.tid < NUM_TILE_TYPES:
            raise ValueError(f"invalid tile id {self.tid}")

    @property
    def suit(self) -> str:
        if self.tid < 9:
            return "m"
        if self.tid < 18:
            return "p"
        if self.tid < 27:
            return "s"
        return "z"

    @property
    def rank(self) -> int:
        """1..9 for suits, 1..7 for honors (E/S/W/N/Haku/Hatsu/Chun)."""
        if self.suit == "z":
            return self.tid - 27 + 1
        return (self.tid % 9) + 1

    @property
    def is_honor(self) -> bool:
        return self.suit == "z"

    @property
    def is_terminal(self) -> bool:
        return self.tid in TERMINALS

    @property
    def is_yaochuu(self) -> bool:
        return self.tid in YAOCHUUHAI

    def to_str(self) -> str:
        if self.red and self.rank == 5 and self.suit in "mps":
            return f"0{self.suit}"
        return f"{self.rank}{self.suit}"

    @classmethod
    def from_str(cls, s: str) -> "Tile":
        """Parse '5m', '0p' (red 5p), 'z3' or '3z' (West)."""
        s = s.strip().lower()
        if len(s) != 2:
            raise ValueError(f"bad tile string {s!r}")
        a, b = s[0], s[1]
        if a in SUIT_OFFSETS and b.isdigit():
            suit, rank_ch = a, b
        elif b in SUIT_OFFSETS and a.isdigit():
            suit, rank_ch = b, a
        else:
            raise ValueError(f"bad tile string {s!r}")
        rank = int(rank_ch)
        if rank == 0:
            if suit not in ("m", "p", "s"):
                raise ValueError(f"red 0 only allowed for mps, got {s!r}")
            return cls(SUIT_OFFSETS[suit] + 4, red=True)
        if suit == "z":
            if not 1 <= rank <= 7:
                raise ValueError(f"honor rank must be 1..7, got {s!r}")
            return cls(27 + rank - 1)
        if not 1 <= rank <= 9:
            raise ValueError(f"suit rank must be 1..9, got {s!r}")
        return cls(SUIT_OFFSETS[suit] + rank - 1)

    def __str__(self) -> str:
        return self.to_str()


def tiles_from_str(s: str) -> list[Tile]:
    """Parse compact tenhou-style notation: '123m456p789sESW' or '13m 55p 0s'."""
    s = s.replace(" ", "").lower()
    out: list[Tile] = []
    buf: list[str] = []
    for ch in s:
        if ch.isdigit():
            buf.append(ch)
        elif ch in SUIT_OFFSETS:
            for d in buf:
                rank = int(d)
                if rank == 0:
                    if ch not in ("m", "p", "s"):
                        raise ValueError(f"red 0 only for mps, near {ch!r}")
                    out.append(Tile(SUIT_OFFSETS[ch] + 4, red=True))
                else:
                    if ch == "z" and not 1 <= rank <= 7:
                        raise ValueError(f"honor rank must be 1..7, got {rank}")
                    if ch != "z" and not 1 <= rank <= 9:
                        raise ValueError(f"suit rank must be 1..9, got {rank}")
                    base = 27 if ch == "z" else SUIT_OFFSETS[ch]
                    out.append(Tile(base + rank - 1))
            buf = []
        else:
            raise ValueError(f"unexpected char {ch!r} in {s!r}")
    if buf:
        raise ValueError(f"trailing digits without suit: {''.join(buf)}")
    return out


def tile_counts(tiles: list[Tile]) -> list[int]:
    """Return a length-34 count vector (red flag ignored)."""
    counts = [0] * NUM_TILE_TYPES
    for t in tiles:
        counts[t.tid] += 1
    return counts


def tiles_to_str(tiles: list[Tile]) -> str:
    """Compact representation: sorted, grouped by suit, e.g. '123m 456p 77z'."""
    if not tiles:
        return ""
    sorted_tiles = sorted(tiles, key=lambda t: (t.tid, not t.red))
    groups: dict[str, list[str]] = {"m": [], "p": [], "s": [], "z": []}
    for t in sorted_tiles:
        groups[t.suit].append("0" if t.red else str(t.rank))
    parts = []
    for suit in ("m", "p", "s", "z"):
        if groups[suit]:
            parts.append("".join(groups[suit]) + suit)
    return " ".join(parts)
