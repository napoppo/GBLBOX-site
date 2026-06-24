#!/usr/bin/env python3
"""
PvPokeのリーグ別ランキングJSONから推奨技を抽出し、アプリ同梱用JSONを更新する。

使い方:
    python3 scripts/update_pvpoke_moves.py

このスクリプトだけがネットワークへアクセスする。アプリ本体は生成済みの
data/pvpoke_movesets.json をサイト経由で読む。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from dataclasses import dataclass

from secure_fetch import fetch_bytes


HERE = os.path.dirname(os.path.abspath(__file__))
# GitHub Pages 配信先（data/）。アプリ同梱版は pokemongo_iv_manager/tools 側で生成する。
OUT = os.path.normpath(os.path.join(HERE, "..", "data", "pvpoke_movesets.json"))
BASE_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall"


@dataclass(frozen=True)
class LeagueSource:
    key: str
    file_name: str

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.file_name}"


LEAGUES = [
    LeagueSource("great", "rankings-1500.json"),
    LeagueSource("ultra", "rankings-2500.json"),
    LeagueSource("master", "rankings-10000.json"),
]


def fetch_json(source: LeagueSource) -> tuple[list[dict], str | None]:
    data = fetch_bytes(source.url)
    return json.loads(data.decode("utf-8")), None


def moveset_from_entry(entry: dict) -> dict | None:
    moveset = entry.get("moveset") or []
    if len(moveset) < 2:
        return None
    return {
        "fastId": moveset[0],
        "chargedId1": moveset[1],
        "chargedId2": moveset[2] if len(moveset) >= 3 else None,
    }


def build_league_map(rankings: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for entry in rankings:
        species_id = entry.get("speciesId")
        moveset = moveset_from_entry(entry)
        if not species_id or not moveset:
            continue

        # アプリ側はシャドウを種族とは別管理しているため、通常種族を優先しつつ
        # 通常種族がランキング外の場合だけシャドウの技構成をフォールバックにする。
        base_id = species_id.removesuffix("_shadow")
        if species_id == base_id:
            out[base_id] = moveset
        else:
            out.setdefault(base_id, moveset)
    return dict(sorted(out.items()))


def build_rankings(rankings: list[dict]) -> list[dict]:
    """使用率(PvPoke)順を保持したランキング。シャドウは通常種族に統合し重複を除く。"""
    out: list[dict] = []
    seen: set[str] = set()
    for entry in rankings:
        species_id = entry.get("speciesId")
        if not species_id:
            continue
        base_id = species_id.removesuffix("_shadow")
        if base_id in seen:
            continue
        seen.add(base_id)
        out.append({
            "speciesId": base_id,
            "score": entry.get("score"),
            "rating": entry.get("rating"),
        })
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Update bundled PvPoke moveset recommendations.")
    parser.add_argument("--output", default=OUT, help="Output JSON path")
    args = parser.parse_args()

    leagues: dict[str, dict] = {}
    rankings_out: dict[str, list] = {}
    sources: list[dict] = []
    for source in LEAGUES:
        rankings, last_modified = fetch_json(source)
        leagues[source.key] = build_league_map(rankings)
        rankings_out[source.key] = build_rankings(rankings)
        sources.append({
            "league": source.key,
            "url": source.url,
            "lastModified": last_modified,
        })
        print(f"{source.key}: {len(leagues[source.key])} movesets, {len(rankings_out[source.key])} ranked")

    payload = {
        "source": "PvPoke",
        "updatedAt": dt.datetime.now(dt.UTC).date().isoformat(),
        "sources": sources,
        "leagues": leagues,
        "rankings": rankings_out,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
