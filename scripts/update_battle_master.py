#!/usr/bin/env python3
"""Build battle master JSON files for app remote distribution.

This fetches public upstream data and writes:
  - data/pokedex.json
  - data/moves.json

The app reads these files from the GBLBOX site and falls back to bundled data
when remote data is unavailable.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re

from secure_fetch import fetch_bytes


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))

SOURCES = {
    "pvpoke_gm": "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster.json",
    "species_names": "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv",
    "moves_csv": "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/moves.csv",
    "move_names": "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/move_names.csv",
}

REGIONAL_AND_MEGA_FORMS = (
    ("_alolan", "Alolan"), ("_galarian", "Galarian"), ("_hisuian", "Hisuian"),
    ("_paldean", "Paldean"), ("_mega_x", "MegaX"), ("_mega_y", "MegaY"),
    ("_mega", "Mega"), ("_primal", "Primal"),
    ("_heat", "Heat"), ("_wash", "Wash"), ("_frost", "Frost"),
    ("_fan", "Fan"), ("_mow", "Mow"),
    ("_origin", "Origin"), ("_altered", "Altered"),
    ("_therian", "Therian"), ("_incarnate", "Incarnate"),
    ("_attack", "Attack"), ("_defense", "Defense"), ("_speed", "Speed"),
)

VARIANT_FORMS = (
    ("_galarian_zen", "GalarianZen"), ("_galarian_standard", "GalarianStandard"),
    ("_crowned_shield", "CrownedShield"), ("_crowned_sword", "CrownedSword"),
    ("_rapid_strike", "RapidStrike"), ("_single_strike", "SingleStrike"),
    ("_shadow_rider", "ShadowRider"), ("_ice_rider", "IceRider"),
    ("_dawn_wings", "DawnWings"), ("_dusk_mane", "DuskMane"),
    ("_pom_pom", "PomPom"), ("_low_key", "LowKey"),
    ("_complete", "Complete"), ("_unbound", "Unbound"),
    ("_midnight", "Midnight"), ("_midday", "Midday"),
    ("_hangry", "Hangry"), ("_standard", "Standard"),
    ("_average", "Average"), ("_shield", "Shield"), ("_blade", "Blade"),
    ("_female", "Female"), ("_male", "Male"),
    ("_sunny", "Sunny"), ("_rainy", "Rainy"), ("_snowy", "Snowy"),
    ("_plant", "Plant"), ("_sandy", "Sandy"), ("_trash", "Trash"),
    ("_black", "Black"), ("_white", "White"), ("_ultra", "Ultra"),
    ("_hero", "Hero"), ("_armored", "Armored"),
    ("_aqua", "Aqua"), ("_blaze", "Blaze"), ("_combat", "Combat"),
    ("_land", "Land"), ("_sky", "Sky"), ("_zen", "Zen"),
    ("_amped", "Amped"), ("_ordinary", "Ordinary"), ("_aria", "Aria"),
    ("_baile", "Baile"), ("_pau", "Pau"), ("_sensu", "Sensu"), ("_dusk", "Dusk"),
    ("_large", "Large"), ("_small", "Small"), ("_super", "Super"),
    ("_10", "Forme10"),
)

PAREN_FORM_HINTS = (
    ("50% forme", "Forme50"), ("10% forme", "Forme10"), ("complete forme", "Complete"),
    ("sunshine", "Sunny"), ("galarian zen", "GalarianZen"),
    ("galarian standard", "GalarianStandard"), ("dawn wings", "DawnWings"),
    ("dusk mane", "DuskMane"), ("ice rider", "IceRider"), ("shadow rider", "ShadowRider"),
    ("crowned sword", "CrownedSword"), ("crowned shield", "CrownedShield"),
    ("rapid strike", "RapidStrike"), ("single strike", "SingleStrike"),
    ("black kyurem", "Black"), ("white kyurem", "White"),
)

SECOND_MOVE_CANDY = {10000: 25, 50000: 50, 75000: 75, 100000: 100}

# 2026-08-31 GO Fest: Mega Finaleで追加された、メガ進化中の追加チャージ技。
# 上流のポケモン別技リスト反映が遅れても配信側で保持する。
ADDITIONAL_CHARGED_MOVE_OVERRIDES = {
    "mewtwo_mega_x": "DYNAMIC_PUNCH_PLUS",
    "mewtwo_mega_y": "FUTURE_SIGHT_PLUS",
    "chesnaught_mega": "SEED_BOMB_PLUS",
    "delphox_mega": "MYSTICAL_FIRE_PLUS",
    "greninja_mega": "SURF_PLUS",
    "raichu_mega_x": "VOLT_TACKLE_PLUS",
    "raichu_mega_y": "ZAP_CANNON_PLUS",
    "skarmory_mega": "DRILL_PECK_PLUS",
    "falinks_mega": "BRICK_BREAK_PLUS",
    "starmie_mega": "LIQUIDATION_PLUS",
    "victreebel_mega": "ACID_SPRAY_PLUS",
    "malamar_mega": "PSYBEAM_PLUS",
    "dragonite_mega": "OUTRAGE_PLUS",
}

# 上流のreleasedフラグが遅れている実装済みフォームを補完する。
RELEASED_OVERRIDES = {
    "camerupt_mega": True,
    # 2026-08-22 GO実装。上流反映が戻っても配信側で解禁を維持する。
    "starmie_mega": True,
    # 2026-08-31 GO実装。上流反映が戻っても配信側で解禁を維持する。
    "chesnaught_mega": True,
    "delphox_mega": True,
    "greninja_mega": True,
    # 2026-08-18 GO実装。上流反映待ちの間も配信側で解禁を維持する。
    "cramorant": True,
    "arrokuda": True,
    "barraskewda": True,
}


def fetch_json(source_key: str):
    return json.loads(fetch_bytes(SOURCES[source_key]).decode("utf-8"))


def fetch_csv_rows(source_key: str):
    data = fetch_bytes(SOURCES[source_key]).decode("utf-8")
    return csv.reader(io.StringIO(data))


def load_ja_names() -> dict[int, str]:
    names: dict[int, str] = {}
    for row in fetch_csv_rows("species_names"):
        if len(row) >= 3 and row[1] == "1" and row[0].isdigit():
            names[int(row[0])] = row[2]
    return names


def load_move_ja():
    ident_by_id: dict[str, str] = {}
    for row in fetch_csv_rows("moves_csv"):
        if row and row[0].isdigit():
            ident_by_id[row[0]] = row[1]

    ja_by_ident: dict[str, str] = {}
    for row in fetch_csv_rows("move_names"):
        if len(row) >= 3 and row[1] == "1" and row[0] in ident_by_id:
            ja_by_ident[ident_by_id[row[0]]] = row[2]

    def lookup(move_id: str) -> str | None:
        parts = move_id.lower().split("_")
        while parts:
            for ident in ("-".join(parts), "".join(parts)):
                if ident in ja_by_ident:
                    return ja_by_ident[ident]
            parts = parts[:-1]
        return None

    return lookup


def parse_form(species_id: str, species_name: str) -> str:
    sid = species_id.lower()
    for key, label in VARIANT_FORMS + REGIONAL_AND_MEGA_FORMS:
        if key in sid:
            return label
    match = re.search(r"\(([^)]+)\)", species_name)
    if match:
        paren = match.group(1).lower()
        for key, label in PAREN_FORM_HINTS:
            if key in paren:
                return label
    return "Normal"


def build_pokedex(pvpoke_gamemaster: dict, ja_names: dict[int, str]) -> list[dict]:
    entries: list[dict] = []
    for pokemon in pvpoke_gamemaster["pokemon"]:
        species_id = pokemon["speciesId"]
        if species_id.endswith("_shadow"):
            continue

        base_stats = pokemon["baseStats"]
        dex_no = pokemon["dex"]
        tags = pokemon.get("tags", []) or []
        evolutions = (pokemon.get("family") or {}).get("evolutions") or []
        entry = {
            "speciesId": species_id,
            "dexNo": dex_no,
            "nameEn": pokemon["speciesName"],
            "nameJa": ja_names.get(dex_no) or pokemon["speciesName"],
            "form": parse_form(species_id, pokemon["speciesName"]),
            "baseAttack": base_stats["atk"],
            "baseDefense": base_stats["def"],
            "baseStamina": base_stats["hp"],
            "types": [type_name for type_name in pokemon.get("types", []) if type_name and type_name != "none"],
            "shadowAvailable": "shadoweligible" in tags,
            "released": RELEASED_OVERRIDES.get(species_id, bool(pokemon.get("released", False))),
            "evolutions": evolutions,
            "fastMoves": pokemon.get("fastMoves", []) or [],
            "chargedMoves": pokemon.get("chargedMoves", []) or [],
        }
        additional_move = ADDITIONAL_CHARGED_MOVE_OVERRIDES.get(species_id)
        if additional_move and additional_move not in entry["chargedMoves"]:
            entry["chargedMoves"].append(additional_move)
        third_move_cost = pokemon.get("thirdMoveCost")
        if isinstance(third_move_cost, int) and third_move_cost > 0:
            entry["secondMoveStardust"] = third_move_cost
            entry["secondMoveCandy"] = SECOND_MOVE_CANDY.get(third_move_cost, 0)
        entries.append(entry)

    best: dict[tuple, dict] = {}
    for entry in entries:
        key = (
            entry["dexNo"],
            entry["form"],
            entry["baseAttack"],
            entry["baseDefense"],
            entry["baseStamina"],
            tuple(entry["types"]),
        )
        current = best.get(key)
        if current is None or (
            entry["speciesId"].count("_"), len(entry["speciesId"]), entry["speciesId"]
        ) < (
            current["speciesId"].count("_"), len(current["speciesId"]), current["speciesId"]
        ):
            best[key] = entry

    output = list(best.values())
    output.sort(key=lambda item: (item["dexNo"], item["speciesId"]))
    return output


def build_moves(pvpoke_gamemaster: dict, move_ja) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for move in pvpoke_gamemaster.get("moves", []):
        move_id = move["moveId"]
        entry = {
            "name": move.get("name", move_id),
            "nameJa": move_ja(move_id) or move.get("name", move_id),
            "type": move.get("type", "normal"),
            "power": move.get("power", 0),
            "energy": move.get("energy", 0),
            "energyGain": move.get("energyGain", 0),
            "turns": move.get("turns", 1),
        }
        if move.get("buffs"):
            entry["buffs"] = move["buffs"]
            entry["buffTarget"] = move.get("buffTarget", "self")
            try:
                entry["buffChance"] = float(move.get("buffApplyChance", "0") or 0)
            except ValueError:
                entry["buffChance"] = 0.0
        output[move_id] = entry

    # 追加技の定義自体が上流から一時的に消えた場合も、種族側の参照を壊さない。
    additional_moves = {
        "ACID_SPRAY_PLUS": {"name": "Acid Spray+", "nameJa": "アシッドボム", "type": "poison", "power": 20, "energy": 40, "energyGain": 0, "turns": 1},
        "BRICK_BREAK_PLUS": {"name": "Brick Break+", "nameJa": "かわらわり", "type": "fighting", "power": 40, "energy": 35, "energyGain": 0, "turns": 1},
        "DRILL_PECK_PLUS": {"name": "Drill Peck+", "nameJa": "ドリルくちばし", "type": "flying", "power": 60, "energy": 35, "energyGain": 0, "turns": 1},
        "DYNAMIC_PUNCH_PLUS": {"name": "Dynamic Punch+", "nameJa": "ばくれつパンチ", "type": "fighting", "power": 130, "energy": 80, "energyGain": 0, "turns": 1},
        "FUTURE_SIGHT_PLUS": {"name": "Future Sight+", "nameJa": "みらいよち", "type": "psychic", "power": 130, "energy": 80, "energyGain": 0, "turns": 1},
        "LIQUIDATION_PLUS": {"name": "Liquidation+", "nameJa": "アクアブレイク", "type": "water", "power": 55, "energy": 40, "energyGain": 0, "turns": 1},
        "MYSTICAL_FIRE_PLUS": {"name": "Mystical Fire+", "nameJa": "マジカルフレイム", "type": "fire", "power": 50, "energy": 40, "energyGain": 0, "turns": 1},
        "OUTRAGE_PLUS": {"name": "Outrage+", "nameJa": "げきりん", "type": "dragon", "power": 80, "energy": 50, "energyGain": 0, "turns": 1},
        "PSYBEAM_PLUS": {"name": "Psybeam+", "nameJa": "サイケこうせん", "type": "psychic", "power": 60, "energy": 45, "energyGain": 0, "turns": 1},
        "SEED_BOMB_PLUS": {"name": "Seed Bomb+", "nameJa": "タネばくだん", "type": "grass", "power": 60, "energy": 40, "energyGain": 0, "turns": 1},
        "SURF_PLUS": {"name": "Surf+", "nameJa": "なみのり", "type": "water", "power": 55, "energy": 35, "energyGain": 0, "turns": 1},
        "VOLT_TACKLE_PLUS": {"name": "Volt Tackle+", "nameJa": "ボルテッカー", "type": "electric", "power": 65, "energy": 35, "energyGain": 0, "turns": 1},
        "ZAP_CANNON_PLUS": {"name": "Zap Cannon+", "nameJa": "でんじほう", "type": "electric", "power": 70, "energy": 45, "energyGain": 0, "turns": 1},
    }
    for move_id, fallback in additional_moves.items():
        output.setdefault(move_id, fallback)
    return output


def write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=0)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Update remote battle master data.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory containing pokedex.json and moves.json")
    args = parser.parse_args()

    pvpoke_gamemaster = fetch_json("pvpoke_gm")
    pokedex = build_pokedex(pvpoke_gamemaster, load_ja_names())
    moves = build_moves(pvpoke_gamemaster, load_move_ja())

    write_json(os.path.join(args.output_dir, "pokedex.json"), pokedex)
    write_json(os.path.join(args.output_dir, "moves.json"), moves)

    released_count = sum(1 for entry in pokedex if entry["released"])
    print(f"pokedex.json: {len(pokedex)} species (released={released_count})")
    print(f"moves.json: {len(moves)} moves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
