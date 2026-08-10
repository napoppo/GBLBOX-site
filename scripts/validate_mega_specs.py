#!/usr/bin/env python3
"""メガ仕様JSONのスキーマと図鑑参照を検証する。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mega_specs.json")
    pokedex_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/pokedex.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    pokedex = json.loads(pokedex_path.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    require(payload.get("schemaVersion") == 1, "schemaVersion must be 1")
    require(isinstance(entries, list), "entries must be an array")
    ids = [entry.get("speciesId") for entry in entries]
    require(len(ids) == len(set(ids)), "duplicate speciesId found")
    allowed_ids = {entry.get("speciesId") for entry in pokedex}
    for entry in entries:
        species_id = entry.get("speciesId")
        require(species_id in allowed_ids, f"unknown speciesId: {species_id}")
        require(entry.get("form") in {"Mega", "MegaX", "MegaY", "Primal"}, f"not a mega form: {species_id}")
        require(isinstance(entry.get("megaMaxLevel"), int) and 1 <= entry["megaMaxLevel"] <= 4,
                f"invalid megaMaxLevel: {species_id}")
        levels = entry.get("levelsAvailable")
        require(isinstance(levels, list) and entry["megaMaxLevel"] in levels,
                f"levelsAvailable is invalid: {species_id}")
    print(f"OK: {path} entries={len(entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
