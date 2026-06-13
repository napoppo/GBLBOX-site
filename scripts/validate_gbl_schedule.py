#!/usr/bin/env python3
"""Validate data/gbl_schedule.json before deploy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEDULE_PATH = ROOT / "data" / "gbl_schedule.json"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def warn(msg: str) -> None:
    print(f"WARN: {msg}", file=sys.stderr)


def validate_v2(doc: dict) -> None:
    current_id = doc.get("currentSeasonId")
    if not current_id:
        fail("currentSeasonId is required")

    seasons = doc.get("seasons")
    if not isinstance(seasons, list) or not seasons:
        fail("seasons must be a non-empty array")

    by_id = {s.get("id"): s for s in seasons if isinstance(s, dict)}
    if current_id not in by_id:
        fail(f"currentSeasonId '{current_id}' not found in seasons")

    season = by_id[current_id]
    format_rules = season.get("formatRules", [])
    if not format_rules:
        fail(f"season '{current_id}' has no formatRules")

    rule_ids = {r["id"] for r in format_rules if isinstance(r, dict) and "id" in r}
    if len(rule_ids) != len(format_rules):
        fail(f"season '{current_id}' has duplicate formatRules ids")

    for rule in format_rules:
        if not isinstance(rule, dict):
            continue
        for key in ("regulationLinesJa", "regulationLinesEn"):
            lines = rule.get(key)
            if lines is None:
                continue
            if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
                fail(f"formatRules '{rule.get('id')}' {key} must be an array of strings")

    schedule = season.get("schedule", [])
    if not isinstance(schedule, list):
        fail(f"season '{current_id}' schedule must be an array")

    week_ids: set[str] = set()
    for entry in schedule:
        if not isinstance(entry, dict):
            fail("schedule entries must be objects")
        week_id = entry.get("id")
        if week_id in week_ids:
            fail(f"duplicate schedule id: {week_id}")
        week_ids.add(week_id)

        for fmt in entry.get("formatIds", []):
            if fmt not in rule_ids:
                fail(f"schedule '{week_id}' references unknown format id '{fmt}'")

    print(f"OK: schema v2, current season '{current_id}'")
    print(f"    formatRules: {len(rule_ids)}, schedule weeks: {len(schedule)}")
    print(f"    tournamentEvents: {len(season.get('tournamentEvents', []))}")
    print(f"    archived seasons in file: {len(seasons) - 1}")


def validate_v1(doc: dict) -> None:
    rules = doc.get("currentSeasonFormatRules", [])
    rule_ids = {r["id"] for r in rules if isinstance(r, dict) and "id" in r}
    for entry in doc.get("schedule", []):
        for fmt in entry.get("formatIds", []):
            if fmt not in rule_ids:
                fail(f"schedule '{entry.get('id')}' references unknown format id '{fmt}'")
    print("OK: schema v1 (legacy flat format)")


def main() -> None:
    if not SCHEDULE_PATH.exists():
        fail(f"missing {SCHEDULE_PATH}")

    try:
        doc = json.loads(SCHEDULE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {exc}")

    version = doc.get("schemaVersion")
    if version == 2:
        validate_v2(doc)
    elif version == 1:
        validate_v1(doc)
    else:
        fail(f"unsupported schemaVersion: {version}")


if __name__ == "__main__":
    main()
