#!/usr/bin/env python3
"""Battle master data の最低限の妥当性チェック。

Usage:
    python3 scripts/validate_battle_master.py
    python3 scripts/validate_battle_master.py data/pokedex.json data/moves.json data/pvpoke_movesets.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def validate_pokedex(pokedex: list[dict], moves: dict) -> None:
    require(isinstance(pokedex, list) and pokedex, "pokedex must be a non-empty array")
    require(isinstance(moves, dict) and moves, "moves must be a non-empty object")

    species_ids = [entry.get("speciesId") for entry in pokedex]
    require(all(isinstance(species_id, str) and species_id for species_id in species_ids), "speciesId is required")
    require(len(set(species_ids)) == len(species_ids), "duplicate speciesId found")

    move_ids = set(moves.keys())
    for entry in pokedex:
        species_id = entry["speciesId"]
        for field in ("fastMoves", "chargedMoves"):
            values = entry.get(field)
            require(isinstance(values, list), f"{species_id}.{field} must be an array")
            missing = [move_id for move_id in values if move_id not in move_ids]
            if missing:
                raise SystemExit(f"ERROR: {species_id}.{field} references missing move: {missing[0]}")


def validate_pvpoke_movesets(pvpoke: dict, moves: dict) -> None:
    leagues = pvpoke.get("leagues", {})
    require(isinstance(leagues, dict) and leagues, "pvpoke leagues must be a non-empty object")

    move_ids = set(moves.keys())
    for league, entries in leagues.items():
        require(isinstance(entries, dict), f"{league} movesets must be an object")
        for species_id, moveset in entries.items():
            for field in ("fastId", "chargedId1", "chargedId2"):
                move_id = moveset.get(field)
                if move_id is None:
                    continue
                require(move_id in move_ids, f"{league}.{species_id}.{field} references missing move: {move_id}")


def validate_move_overrides(overrides: dict, moves: dict) -> None:
    require(overrides.get("schemaVersion") == 1, "move overrides schemaVersion must be 1")
    require(isinstance(overrides.get("updatedAt"), str), "move overrides updatedAt is required")
    entries = overrides.get("overrides")
    require(isinstance(entries, list), "move overrides must be an array")
    known_ids = set(moves)
    seen: set[str] = set()
    for entry in entries:
        require(isinstance(entry, dict), "move override entry must be an object")
        move_id = entry.get("moveId")
        require(isinstance(move_id, str) and move_id in known_ids, f"unknown move override: {move_id}")
        require(move_id not in seen, f"duplicate move override: {move_id}")
        seen.add(move_id)
        for key in ("power", "energy", "energyGain", "turns"):
            require(isinstance(entry.get(key), int), f"{move_id}.{key} must be an integer")
        for key in ("energyGainIsEstimated", "energyIsEstimated"):
            require(isinstance(entry.get(key), bool), f"{move_id}.{key} must be boolean")
        if "buffs" in entry:
            require(entry["buffs"] in ([0, 0], [0, 1], [0, -1], [1, 0], [-1, 0], [-1, -1], [1, 1]), f"{move_id}.buffs is invalid")
        if "buffTarget" in entry:
            require(entry["buffTarget"] in ("self", "opponent"), f"{move_id}.buffTarget is invalid")
        if "buffChance" in entry:
            require(isinstance(entry["buffChance"], (int, float)) and 0 <= entry["buffChance"] <= 1, f"{move_id}.buffChance is invalid")


def main() -> int:
    pokedex_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/pokedex.json")
    moves_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/moves.json")
    pvpoke_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/pvpoke_movesets.json")
    overrides_path = Path(sys.argv[4]) if len(sys.argv) > 4 else Path("data/battle_move_overrides.json")

    pokedex = load_json(pokedex_path)
    moves = load_json(moves_path)
    validate_pokedex(pokedex, moves)

    if pvpoke_path.exists():
        validate_pvpoke_movesets(load_json(pvpoke_path), moves)
    if overrides_path.exists():
        validate_move_overrides(load_json(overrides_path), moves)

    print(f"OK: {pokedex_path} species={len(pokedex)} | {moves_path} moves={len(moves)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
