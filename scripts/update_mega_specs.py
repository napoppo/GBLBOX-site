#!/usr/bin/env python3
"""Game Master からメガ進化レベル仕様を正規化して配信する。"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

from secure_fetch import fetch_bytes


GAME_MASTER_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
GAME_MASTER_TIMESTAMP_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/timestamp.txt"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "mega_specs.json"
MEGA_FORMS = {"Mega", "MegaX", "MegaY", "Primal"}
TEMPLATE_RE = re.compile(r"^MEGA_EVOLUTION_LEVEL_(\d+)_V(\d{4})_POKEMON_")

# PvPokeのreleasedフラグが更新されるまでの安全な補完。
# 新しい実装済みメガは、公式発表を確認したうえでここへ追加する。
RELEASED_OVERRIDES = {
    "camerupt_mega": True,
}

# メガミュウツーはGame Master側にレベル4テンプレートが現れない期間が
# あるため、ゲーム内で解放可能な上限を補完する。
MEGA_MAX_LEVEL_OVERRIDES = {
    "mewtwo_mega_x": 4,
    "mewtwo_mega_y": 4,
}
MEGA_POWER_LEVEL_BONUS_OVERRIDES = {
    "mewtwo_mega_x": 2,
    "mewtwo_mega_y": 2,
}


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_mega_settings(value):
    if isinstance(value, dict):
        template_id = value.get("templateId")
        data = value.get("data") if isinstance(value.get("data"), dict) else value
        settings = data.get("megaEvoLevelSettings") if isinstance(data, dict) else None
        if isinstance(template_id, str) and isinstance(settings, dict):
            match = TEMPLATE_RE.match(template_id)
            if match:
                level = int(match.group(1))
                dex_no = int(match.group(2))
                yield level, dex_no, settings
        for child in value.values():
            yield from iter_mega_settings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_mega_settings(child)


def unique_settings(game_master: dict) -> dict[tuple[int, int], dict]:
    found: dict[tuple[int, int], dict] = {}
    for level, dex_no, settings in iter_mega_settings(game_master):
        key = (level, dex_no)
        found[key] = settings
    return found


def build_specs(pokedex: list[dict], game_master: dict, source_version: str) -> dict:
    settings_by_level_dex = unique_settings(game_master)
    entries = []
    for pokemon in pokedex:
        if pokemon.get("form") not in MEGA_FORMS:
            continue
        species_id = pokemon["speciesId"]
        levels = sorted(level for level, dex_no in settings_by_level_dex if dex_no == pokemon.get("dexNo"))
        if not levels:
            # Game Masterに個体別設定が無い場合は、最大レベルを推測しない。
            continue
        observed_max_level = max(levels)
        max_level = max(observed_max_level, MEGA_MAX_LEVEL_OVERRIDES.get(species_id, 0))
        settings = settings_by_level_dex[(observed_max_level, pokemon["dexNo"])]
        if max_level not in levels:
            levels.append(max_level)
        effects = settings.get("effects") if isinstance(settings.get("effects"), dict) else {}
        entries.append({
            "speciesId": species_id,
            "dexNo": pokemon["dexNo"],
            "form": pokemon["form"],
            "released": RELEASED_OVERRIDES.get(species_id, bool(pokemon.get("released", False))),
            "megaMaxLevel": max_level,
            "powerLevelBonus": MEGA_POWER_LEVEL_BONUS_OVERRIDES.get(
                species_id, effects.get("selfCpBoostAdditionalLevel")
            ),
            "levelsAvailable": levels,
            "sourceVersion": source_version,
        })
    entries.sort(key=lambda item: item["speciesId"])
    return {
        "schemaVersion": 1,
        "source": "PokeMiners Game Master",
        "sourceURL": GAME_MASTER_URL,
        "sourceVersion": source_version,
        "updatedAt": dt.datetime.now(dt.UTC).date().isoformat(),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pokedex", default=str(Path(__file__).resolve().parents[1] / "data" / "pokedex.json"))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    game_master = json.loads(fetch_bytes(GAME_MASTER_URL).decode("utf-8"))
    timestamp = fetch_bytes(GAME_MASTER_TIMESTAMP_URL).decode("utf-8").strip()
    payload = build_specs(load_json(Path(args.pokedex)), game_master, timestamp)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"mega_specs.json: {len(payload['entries'])} forms, source={timestamp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
