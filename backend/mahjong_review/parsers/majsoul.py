"""Mahjong Soul (Majsoul) parser — stub.

Majsoul logs are protobuf-encoded inside the `mjs` (action records) stream.
Parsing requires the .proto definitions extracted from the client, plus base64
unwrapping. The community tool `mjai-reviewer`/`majsoul-paipu-tools` does this.

For this MVP we expose the same `parse_*` interface so the API can route to it
once implemented. Calling either function will raise NotImplementedError until
then.

TODO: integrate one of:
    - https://github.com/MahjongRepository/mahjong (parser layer)
    - majsoul protobuf decoder (vendor as a submodule)
and convert decoded events into the same `Snapshot` shape as the tenhou parser.
"""

from __future__ import annotations

from pathlib import Path

from .tenhou import Snapshot


def parse_majsoul_log(raw: str | bytes, hero_seat: int) -> list[Snapshot]:
    raise NotImplementedError(
        "Majsoul parser not yet implemented. Convert your log to Tenhou JSON "
        "format using majsoul-paipu-tools, or use the manual entry endpoint."
    )


def parse_majsoul_file(path: str | Path, hero_seat: int) -> list[Snapshot]:
    raise NotImplementedError("Majsoul parser not yet implemented")
