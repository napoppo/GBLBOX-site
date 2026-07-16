#!/usr/bin/env python3
"""Validate and synchronize JSON shared by the GBL Box repositories.

Object-key order and whitespace are ignored when fingerprints are calculated.
Array order is intentionally preserved because schedule order, move priority,
and PvPoke ranking order affect app behavior.

Run from the usual sibling checkout layout:

    python3 scripts/validate_shared_data.py

To refresh app fallbacks from the newer site distribution data first:

    python3 scripts/validate_shared_data.py --sync

CI for this repository uses ``--site-only`` because sibling app checkouts are
not available there.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SITE_ROOT = Path(__file__).resolve().parents[1]
IOS_ROOT = SITE_ROOT.parent / "pokemongo_iv_manager"
ANDROID_ROOT = SITE_ROOT.parent / "GBLBox-android"

REMOTE_BATTLE_FILES = ("moves.json", "pokedex.json", "pvpoke_movesets.json")
APP_ONLY_SHARED_FILES = ("cpm.json", "power_up_costs.json")
BUILD_FIELDS = (
    "minimumBuild",
    "maximumBuild",
    "recommendedBuild",
    "minimumBuildAndroid",
    "maximumBuildAndroid",
)
ANNOUNCEMENT_OPTIONAL_TEXT_FIELDS = (
    "titleEn",
    "bodyEn",
    "actionTitleJa",
    "actionTitleEn",
    "updatePromptJa",
    "updatePromptEn",
    "updateActionTitleJa",
    "updateActionTitleEn",
)
APP_STORE_APP_ID = "id6776499795"


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def load_json(path: Path) -> Any:
    require(path.is_file(), f"missing JSON: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"invalid JSON {path}: {exc}") from exc


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def assert_semantically_equal(label: str, expected: Any, actual: Any) -> None:
    expected_hash = semantic_hash(expected)
    actual_hash = semantic_hash(actual)
    require(
        expected_hash == actual_hash,
        f"{label} drift: expected {expected_hash}, got {actual_hash}",
    )
    print(f"OK: {label} sha256={expected_hash}")


def validate_battle_documents(site_root: Path) -> None:
    moves = load_json(site_root / "data/moves.json")
    pokedex = load_json(site_root / "data/pokedex.json")
    pvpoke = load_json(site_root / "data/pvpoke_movesets.json")

    require(isinstance(moves, dict) and moves, "moves.json must be a non-empty object")
    for move_id, move in moves.items():
        require(isinstance(move_id, str) and move_id, "moves.json has an invalid move id")
        require(isinstance(move, dict), f"moves.json {move_id} must be an object")
        for key in ("name", "nameJa", "type", "power", "energy", "energyGain", "turns"):
            require(key in move, f"moves.json {move_id} missing {key}")

    require(isinstance(pokedex, list) and pokedex, "pokedex.json must be a non-empty array")
    species_ids: list[str] = []
    for index, species in enumerate(pokedex):
        require(isinstance(species, dict), f"pokedex.json entry {index} must be an object")
        species_id = species.get("speciesId")
        require(isinstance(species_id, str) and species_id, f"pokedex.json entry {index} missing speciesId")
        species_ids.append(species_id)
    require(len(species_ids) == len(set(species_ids)), "pokedex.json has duplicate speciesId values")

    require(isinstance(pvpoke, dict), "pvpoke_movesets.json must be an object")
    require(isinstance(pvpoke.get("updatedAt"), str), "pvpoke_movesets.json missing updatedAt")
    require(isinstance(pvpoke.get("leagues"), dict), "pvpoke_movesets.json missing leagues")


def validate_schedule_document(document: Any, label: str) -> None:
    require(isinstance(document, dict), f"{label} must be an object")
    require(document.get("schemaVersion") == 2, f"{label} must use schemaVersion 2")
    current_id = document.get("currentSeasonId")
    seasons = document.get("seasons")
    require(isinstance(current_id, str) and current_id, f"{label} missing currentSeasonId")
    require(isinstance(seasons, list) and seasons, f"{label} seasons must be non-empty")
    require(all(isinstance(item, dict) for item in seasons), f"{label} seasons must contain objects")
    season_ids = [item.get("id") for item in seasons]
    require(len(season_ids) == len(set(season_ids)), f"{label} has duplicate season ids")
    require(current_id in season_ids, f"{label} currentSeasonId does not exist")

    for season in seasons:
        rules = season.get("formatRules")
        schedule = season.get("schedule")
        require(isinstance(rules, list) and rules, f"{label} season {season.get('id')} has no rules")
        require(isinstance(schedule, list), f"{label} season {season.get('id')} schedule must be an array")
        rule_ids = [rule.get("id") for rule in rules if isinstance(rule, dict)]
        require(len(rule_ids) == len(rules), f"{label} has a non-object format rule")
        require(len(rule_ids) == len(set(rule_ids)), f"{label} has duplicate format rule ids")
        week_ids: set[str] = set()
        for week in schedule:
            require(isinstance(week, dict), f"{label} has a non-object schedule entry")
            week_id = week.get("id")
            require(isinstance(week_id, str) and week_id, f"{label} schedule entry missing id")
            require(week_id not in week_ids, f"{label} duplicate schedule id {week_id}")
            week_ids.add(week_id)
            formats = week.get("formatIds")
            require(isinstance(formats, list) and formats, f"{label} schedule {week_id} has no formatIds")
            unknown = set(formats) - set(rule_ids)
            require(not unknown, f"{label} schedule {week_id} references unknown formats {sorted(unknown)}")
            for key in ("start", "end"):
                value = week.get(key)
                require(isinstance(value, str), f"{label} schedule {week_id} missing {key}")
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ContractError(f"{label} schedule {week_id} has invalid {key}: {value}") from exc


def validate_app_config(document: Any, label: str) -> None:
    require(isinstance(document, dict), f"{label} must be an object")
    require(document.get("schemaVersion") == 1, f"{label} must use schemaVersion 1")
    for section in ("forceUpdate", "analytics", "billing", "proTrial"):
        require(isinstance(document.get(section), dict), f"{label} missing {section}")
    force_update = document["forceUpdate"]
    require(isinstance(force_update.get("enabled"), bool), f"{label} forceUpdate.enabled must be boolean")
    for key in ("minimumSupportedBuild", "minimumSupportedBuildAndroid"):
        if key in force_update:
            value = force_update[key]
            require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"{label} {key} must be non-negative integer")


def validate_announcements(document: Any, label: str) -> None:
    require(isinstance(document, dict), f"{label} must be an object")
    require(document.get("schemaVersion") == 1, f"{label} must use schemaVersion 1")
    announcements = document.get("announcements")
    require(isinstance(announcements, list), f"{label} announcements must be an array")
    ids: set[str] = set()
    for index, announcement in enumerate(announcements):
        require(isinstance(announcement, dict), f"{label} announcement {index} must be an object")
        announcement_id = announcement.get("id")
        require(isinstance(announcement_id, str) and announcement_id, f"{label} announcement {index} missing id")
        require(announcement_id not in ids, f"{label} duplicate announcement id {announcement_id}")
        ids.add(announcement_id)
        for key in ("titleJa", "bodyJa"):
            require(isinstance(announcement.get(key), str) and announcement[key], f"{label} {announcement_id} missing {key}")
        for key in BUILD_FIELDS:
            value = announcement.get(key)
            require(value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0), f"{label} {announcement_id} {key} must be null or non-negative integer")
        for key in ANNOUNCEMENT_OPTIONAL_TEXT_FIELDS:
            value = announcement.get(key)
            require(value is None or isinstance(value, str), f"{label} {announcement_id} {key} must be a string or null")
        for minimum, maximum in (
            ("minimumBuild", "maximumBuild"),
            ("minimumBuildAndroid", "maximumBuildAndroid"),
        ):
            low = announcement.get(minimum)
            high = announcement.get(maximum)
            require(low is None or high is None or low <= high, f"{label} {announcement_id} has an inverted {minimum}/{maximum} range")
        action_url = announcement.get("actionUrl")
        require(action_url is None or (isinstance(action_url, str) and action_url.startswith("https://")), f"{label} {announcement_id} actionUrl must use HTTPS")
        update_url = announcement.get("updateAppStoreUrl")
        require(
            update_url is None or (
                isinstance(update_url, str)
                and update_url.startswith("https://apps.apple.com/")
                and APP_STORE_APP_ID in update_url
            ),
            f"{label} {announcement_id} updateAppStoreUrl must be the GBL Box App Store HTTPS URL",
        )
        if update_url is not None:
            recommended = announcement.get("recommendedBuild")
            require(
                isinstance(recommended, int) and not isinstance(recommended, bool),
                f"{label} {announcement_id} updateAppStoreUrl requires recommendedBuild",
            )


def overlay_shared_values(base: Any, shared: Any) -> Any:
    """Overlay canonical shared fields while retaining platform extensions."""
    if isinstance(base, dict) and isinstance(shared, dict):
        merged = copy.deepcopy(base)
        for key, value in shared.items():
            merged[key] = overlay_shared_values(merged.get(key), value)
        return merged
    return copy.deepcopy(shared)


def android_config_from_site(android: dict[str, Any], site: dict[str, Any]) -> dict[str, Any]:
    """Update Android's offline fallback without importing iOS force-update copy."""
    merged = copy.deepcopy(android)
    merged["schemaVersion"] = site["schemaVersion"]
    for section in ("analytics", "billing", "proTrial", "paywall"):
        if section in site:
            merged[section] = overlay_shared_values(merged.get(section), site[section])

    site_force = site["forceUpdate"]
    android_force = merged.setdefault("forceUpdate", {})
    android_minimum = site_force.get("minimumSupportedBuildAndroid", 0)
    android_force["minimumSupportedBuildAndroid"] = android_minimum
    # With no Android minimum, the offline fallback must never inherit an iOS-only
    # enabled flag, App Store URL, or App Store message.
    if android_minimum <= 0:
        android_force["enabled"] = False
    else:
        android_force["enabled"] = site_force["enabled"]
    return merged


def shared_android_config_projection(document: dict[str, Any]) -> dict[str, Any]:
    """Fields whose online/offline values are shared by the Android runtime."""
    return {
        "schemaVersion": document["schemaVersion"],
        "analytics": document["analytics"],
        "billing": {"enabled": document["billing"]["enabled"]},
        "proTrial": {
            key: document["proTrial"][key]
            for key in ("freeUseLimit", "resetGeneration", "freeIndividualLimit")
        },
        "forceUpdateAndroid": {
            "minimumSupportedBuildAndroid": document["forceUpdate"].get("minimumSupportedBuildAndroid", 0),
        },
    }


def assert_shared_subset(label: str, shared: Any, extended: Any, path: str = "") -> None:
    if isinstance(shared, dict):
        require(isinstance(extended, dict), f"{label} {path or '<root>'} must be an object")
        for key, value in shared.items():
            require(key in extended, f"{label} missing shared field {path + key}")
            assert_shared_subset(label, value, extended[key], f"{path}{key}.")
        return
    require(shared == extended, f"{label} differs at {path[:-1]}: {shared!r} != {extended!r}")


def swift_block(source: str, start: str, end: str) -> str:
    start_index = source.find(start)
    end_index = source.find(end, start_index + len(start))
    require(start_index >= 0 and end_index > start_index, f"could not locate Swift block {start}")
    return source[start_index:end_index]


def verify_ios_schedule_contract(site_schedule: dict[str, Any], swift_path: Path) -> tuple[list[str], list[str]]:
    source = swift_path.read_text(encoding="utf-8")
    season = next(item for item in site_schedule["seasons"] if item["id"] == site_schedule["currentSeasonId"])

    current_block = swift_block(source, "static let currentSeasonFormatRules", "static let archivedFormatRules")
    archived_block = swift_block(source, "static let archivedFormatRules", "static let formatRules")
    swift_current_ids = re.findall(r"\.init\(\s*id:\s*\"([^\"]+)\"", current_block)
    swift_archived_ids = re.findall(r"\.init\(\s*id:\s*\"([^\"]+)\"", archived_block)
    site_current_ids = [rule["id"] for rule in season["formatRules"]]
    require(swift_current_ids == site_current_ids, f"iOS current format ids drift: {swift_current_ids} != {site_current_ids}")

    ja_match = re.search(r'static let sourceUpdatedJa = "([^"]+)"', source)
    en_match = re.search(r'static let sourceUpdatedEn = "([^"]+)"', source)
    require(ja_match is not None and ja_match.group(1) == season["sourceUpdatedJa"], "iOS sourceUpdatedJa drift")
    require(en_match is not None and en_match.group(1) == season["sourceUpdatedEn"], "iOS sourceUpdatedEn drift")

    schedule_block = swift_block(source, "static let schedule: [GBLScheduleEntry]", "static let tournamentEvents")
    entry_pattern = re.compile(
        r'\.init\(id:\s*"([^"]+)",\s*start:\s*dateUTC\((\d+),\s*(\d+),\s*(\d+)\),\s*'
        r'end:\s*dateUTC\((\d+),\s*(\d+),\s*(\d+)\),\s*formatIds:\s*\[([^]]+)\],\s*'
        r'stardustBonus:\s*(true|false)\)',
    )
    parsed_schedule: list[dict[str, Any]] = []
    for match in entry_pattern.finditer(schedule_block):
        start = datetime(int(match[2]), int(match[3]), int(match[4]), 20, tzinfo=timezone.utc)
        end = datetime(int(match[5]), int(match[6]), int(match[7]), 20, tzinfo=timezone.utc)
        format_ids = re.findall(r'"([^"]+)"', match[8])
        parsed_schedule.append({
            "id": match[1],
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "formatIds": format_ids,
            "stardustBonus": match[9] == "true",
        })
    assert_semantically_equal("iOS/site weekly schedule", season["schedule"], parsed_schedule)

    tournament_block = swift_block(source, "static let tournamentEvents: [GBLTournamentEvent]", "static var rulesById")
    swift_tournament_ids = re.findall(r"\.init\(\s*id:\s*\"([^\"]+)\"", tournament_block)
    site_tournament_ids = [event["id"] for event in season.get("tournamentEvents", [])]
    require(swift_tournament_ids == site_tournament_ids, f"iOS tournament ids drift: {swift_tournament_ids} != {site_tournament_ids}")
    print("OK: iOS/site schedule metadata, format ids, weekly timeline, and tournament ids")
    return swift_current_ids, swift_archived_ids


def android_schedule_core(document: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    core = copy.deepcopy(document)
    archived_rules: list[dict[str, Any]] = []
    for season in core["seasons"]:
        current_rules: list[dict[str, Any]] = []
        for rule in season["formatRules"]:
            if rule.get("isArchived") is True:
                archived_rules.append(rule)
            else:
                current_rules.append(rule)
        season["formatRules"] = current_rules
        archived_ids = {rule["id"] for rule in archived_rules}
        for week in season.get("schedule", []):
            overlap = archived_ids.intersection(week.get("formatIds", []))
            require(not overlap, f"Android schedule {week.get('id')} references archived formats {sorted(overlap)}")
    return core, archived_rules


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SYNC: {path}")


def synchronize(site_root: Path, ios_root: Path, android_root: Path) -> None:
    for filename in REMOTE_BATTLE_FILES:
        source = site_root / "data" / filename
        payload = source.read_text(encoding="utf-8")
        for destination in (
            ios_root / "IVLab/Resources" / filename,
            android_root / "app/src/main/assets" / filename,
        ):
            destination.write_text(payload, encoding="utf-8")
            print(f"SYNC: {destination}")

    site_schedule = load_json(site_root / "data/gbl_schedule.json")
    android_path = android_root / "app/src/main/assets/gbl_schedule.json"
    android_schedule = load_json(android_path)
    _, archived_rules = android_schedule_core(android_schedule)
    target = copy.deepcopy(site_schedule)
    target_season = next(item for item in target["seasons"] if item["id"] == target["currentSeasonId"])
    target_season["formatRules"].extend(archived_rules)
    write_json(android_path, target)

    site_config = load_json(site_root / "data/app_config_v2.json")
    android_config_path = android_root / "app/src/main/assets/app_config_v2.json"
    android_config = load_json(android_config_path)
    write_json(android_config_path, android_config_from_site(android_config, site_config))


def validate_cross_repo(site_root: Path, ios_root: Path, android_root: Path) -> None:
    ios_resources = ios_root / "IVLab/Resources"
    android_assets = android_root / "app/src/main/assets"

    for filename in APP_ONLY_SHARED_FILES:
        ios_value = load_json(ios_resources / filename)
        android_value = load_json(android_assets / filename)
        assert_semantically_equal(f"iOS/Android {filename}", ios_value, android_value)

    for filename in REMOTE_BATTLE_FILES:
        site_value = load_json(site_root / "data" / filename)
        ios_value = load_json(ios_resources / filename)
        android_value = load_json(android_assets / filename)
        assert_semantically_equal(f"site/iOS {filename}", site_value, ios_value)
        assert_semantically_equal(f"site/Android {filename}", site_value, android_value)

    site_schedule = load_json(site_root / "data/gbl_schedule.json")
    android_schedule = load_json(android_assets / "gbl_schedule.json")
    validate_schedule_document(android_schedule, "Android gbl_schedule.json")
    _, swift_archived_ids = verify_ios_schedule_contract(
        site_schedule,
        ios_root / "IVLab/Features/GBL/GBLPlannerData.swift",
    )
    android_core, archived_rules = android_schedule_core(android_schedule)
    assert_semantically_equal("site/Android active schedule core", site_schedule, android_core)
    android_archived_ids = [rule["id"] for rule in archived_rules]
    require(android_archived_ids == swift_archived_ids, f"Android/iOS archived format ids drift: {android_archived_ids} != {swift_archived_ids}")
    print(f"OK: Android carries {len(android_archived_ids)} iOS archived format rules as offline-only extensions")

    site_config = load_json(site_root / "data/app_config_v2.json")
    android_config = load_json(android_assets / "app_config_v2.json")
    validate_app_config(android_config, "Android app_config_v2.json")
    site_projection = shared_android_config_projection(site_config)
    android_projection = shared_android_config_projection(android_config)
    assert_semantically_equal("site/Android app config runtime projection", site_projection, android_projection)
    android_force = android_config["forceUpdate"]
    if android_force.get("minimumSupportedBuildAndroid", 0) <= 0:
        require(not android_force["enabled"], "Android offline config must disable force update when no Android minimum exists")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=SITE_ROOT)
    parser.add_argument("--ios-root", type=Path, default=IOS_ROOT)
    parser.add_argument("--android-root", type=Path, default=ANDROID_ROOT)
    parser.add_argument("--site-only", action="store_true")
    parser.add_argument("--sync", action="store_true", help="refresh app fallback JSON from canonical site data")
    args = parser.parse_args()

    try:
        if args.sync:
            require(not args.site_only, "--sync cannot be combined with --site-only")
            synchronize(args.site_root, args.ios_root, args.android_root)

        validate_battle_documents(args.site_root)
        schedule = load_json(args.site_root / "data/gbl_schedule.json")
        config = load_json(args.site_root / "data/app_config_v2.json")
        announcements = load_json(args.site_root / "data/announcements.json")
        validate_schedule_document(schedule, "site gbl_schedule.json")
        validate_app_config(config, "site app_config_v2.json")
        validate_announcements(announcements, "site announcements.json")
        print(f"OK: site gbl_schedule.json sha256={semantic_hash(schedule)}")
        print(f"OK: site app_config_v2.json sha256={semantic_hash(config)}")
        print(f"OK: site announcements.json sha256={semantic_hash(announcements)}")

        if not args.site_only:
            validate_cross_repo(args.site_root, args.ios_root, args.android_root)
    except (ContractError, OSError, StopIteration) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("OK: shared data contract is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
