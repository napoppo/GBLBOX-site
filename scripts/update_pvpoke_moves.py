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
import pathlib
from dataclasses import dataclass

from json_output import write_text_if_changed
from secure_fetch import fetch_bytes


HERE = os.path.dirname(os.path.abspath(__file__))
# GitHub Pages 配信先（data/）。アプリ同梱版は pokemongo_iv_manager/tools 側で生成する。
OUT = os.path.normpath(os.path.join(HERE, "..", "data", "pvpoke_movesets.json"))
# 採用順（技ごとの使用数の多い順）。pvpoke_movesets.json とは別ファイルにする。
# アプリ側の検証はキー完全一致で、既存ファイルにキーを足すと配信済みの
# バージョンがファイルごと弾いてしまうため、増やすときは新しいファイルにする。
USAGE_OUT = os.path.normpath(os.path.join(HERE, "..", "data", "pvpoke_move_usage.json"))
# メガバージョンの使用率順。採用順ファイルへキーを足すと、キー完全一致で検証している
# 配信済みのバージョンがファイルごと弾いてしまうため、別ファイルにする。
# 技の採用順（leagues の中身）はメガ形態を足すだけで形が変わらないので同じファイルでよい。
MEGA_RANKINGS_OUT = os.path.normpath(os.path.join(HERE, "..", "data", "pvpoke_mega_rankings.json"))
# リトル（CP500）。既存3ファイルへ little を足すと、リーグキーを突き合わせている
# 配信済みのバージョンがファイルごと弾くため、別ファイルにする。
# 対応したバージョン（2.8.0以降）だけがこれを取りに行く。
LITTLE_OUT = os.path.normpath(os.path.join(HERE, "..", "data", "pvpoke_little.json"))
LITTLE_FILE_NAME = "rankings-500.json"
BASE_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/all/overall"
# メガバージョン用のランキング。通常リーグの方にはメガ形態が入っていないため、
# メガを含む形式の技カウントを出すにはこちらが要る。
MEGA_BASE_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/mega/overall"
# 上位だけで足りる（技カウントは上位50件を出す）。全件持つと配信が重くなる。
MEGA_RANKING_LIMIT = 200


@dataclass(frozen=True)
class LeagueSource:
    key: str
    file_name: str

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.file_name}"

    @property
    def mega_url(self) -> str:
        return f"{MEGA_BASE_URL}/{self.file_name}"


LEAGUES = [
    LeagueSource("great", "rankings-1500.json"),
    LeagueSource("ultra", "rankings-2500.json"),
    LeagueSource("master", "rankings-10000.json"),
]


def fetch_json(source: LeagueSource) -> tuple[list[dict], str | None]:
    data = fetch_bytes(source.url)
    return json.loads(data.decode("utf-8")), None


def normalized_move_id(value: object) -> str | None:
    """空き枠を None に寄せる。

    上流は「2つ目のゲージ技が無い」種族（わるあがきだけの Unown など）に対して、
    枠を省略せず文字列 "none" を入れてくることがある。枠が無い場合と同じ扱いに
    しないと、存在しない技IDとして配信データの検証で落ちる。
    """
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() == "none":
        return None
    return value


def moveset_from_entry(entry: dict) -> dict | None:
    moveset = entry.get("moveset") or []
    if len(moveset) < 2:
        return None
    fast_id = normalized_move_id(moveset[0])
    charged_id1 = normalized_move_id(moveset[1])
    charged_id2 = normalized_move_id(moveset[2]) if len(moveset) >= 3 else None
    # 通常技と1つ目のゲージ技が揃わない構成は、アプリ側で使えないので採用しない。
    if fast_id is None or charged_id1 is None:
        return None
    return {
        "fastId": fast_id,
        "chargedId1": charged_id1,
        "chargedId2": charged_id2,
    }


POKEDEX = os.path.normpath(os.path.join(HERE, "..", "data", "pokedex.json"))
# シャドウ/リトレーン専用。種族の技表には載らないが、実際には使える。
SPECIAL_CHARGED_MOVES = frozenset({"RETURN", "FRUSTRATION"})


def learnable_moves() -> dict[str, tuple[frozenset[str], frozenset[str]]]:
    """Game Master 由来の覚えられる技。PvPoke 側の誤りを落とすために使う。

    実例: メェークル(skiddo) に PvPoke は ROCK_SLIDE を載せているが、
    Game Master の cinematicMoves は BRICK_BREAK と SEED_BOMB だけ。
    そのまま配信するとアプリ側で推奨構成が無効と判定され、
    使用率とは無関係な組み合わせへフォールバックしていた。
    """
    document = json.loads(pathlib.Path(POKEDEX).read_text(encoding="utf-8"))
    species = document["species"] if isinstance(document, dict) and "species" in document else document
    return {
        entry["speciesId"]: (frozenset(entry.get("fastMoves") or []),
                             frozenset(entry.get("chargedMoves") or []))
        for entry in species
        if entry.get("speciesId")
    }


def keeping_learnable_moveset(species_id: str, moveset: dict,
                              learnable: dict[str, tuple[frozenset[str], frozenset[str]]],
                              charged_by_usage: list[str]) -> dict | None:
    """覚えられない技を落とした技構成。通常技が無い／ゲージ技が全滅したら None。

    落とした枠は、その種族の採用順（使用数の多い順）から埋め直す。埋めずに空けると
    ゲージ技が1つだけの推奨構成になり、アプリ側のフォールバックより悪くなる。

    アプリ側の別名解決（pvpoke ID → アプリの種族ID）はここでは持たないため、
    図鑑に無いIDはそのまま通す。アプリが実行時に無効な構成を弾く。
    """
    known = learnable.get(species_id)
    if known is None:
        return moveset
    fast_moves, charged_moves = known
    if moveset["fastId"] not in fast_moves:
        return None

    def usable(move: str | None) -> bool:
        return bool(move) and (move in charged_moves or move in SPECIAL_CHARGED_MOVES)

    kept = [move for move in (moveset["chargedId1"], moveset["chargedId2"]) if usable(move)]
    for move in charged_by_usage:
        if len(kept) >= 2:
            break
        if usable(move) and move not in kept:
            kept.append(move)
    if not kept:
        return None
    return {
        "fastId": moveset["fastId"],
        "chargedId1": kept[0],
        "chargedId2": kept[1] if len(kept) > 1 else None,
    }


def keeping_learnable_usage(species_id: str, usage: dict,
                            learnable: dict[str, tuple[frozenset[str], frozenset[str]]]) -> dict | None:
    """覚えられない技を落とした採用順。両方空になったら None。"""
    known = learnable.get(species_id)
    if known is None:
        return usage
    fast_moves, charged_moves = known
    fast_ids = [move for move in usage["fastIds"] if move in fast_moves]
    charged_ids = [move for move in usage["chargedIds"]
                   if move in charged_moves or move in SPECIAL_CHARGED_MOVES]
    if not fast_ids and not charged_ids:
        return None
    return {"fastIds": fast_ids, "chargedIds": charged_ids}


def charged_ids_by_usage(entry: dict) -> list[str]:
    """その種族のゲージ技を採用数の多い順に並べたID。落とした枠の埋め直しに使う。"""
    ranked = sorted((entry.get("moves") or {}).get("chargedMoves") or [],
                    key=lambda m: -(m.get("uses") or 0))
    return [move for move in (normalized_move_id(m.get("moveId")) for m in ranked) if move]


def build_league_map(rankings: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    usage_order: dict[str, list[str]] = {}
    for entry in rankings:
        species_id = entry.get("speciesId")
        moveset = moveset_from_entry(entry)
        if not species_id or not moveset:
            continue
        usage_order.setdefault(species_id.removesuffix("_shadow"), charged_ids_by_usage(entry))

        # アプリ側はシャドウを種族とは別管理しているため、通常種族を優先しつつ
        # 通常種族がランキング外の場合だけシャドウの技構成をフォールバックにする。
        base_id = species_id.removesuffix("_shadow")
        if species_id == base_id:
            out[base_id] = moveset
        else:
            out.setdefault(base_id, moveset)
    learnable = learnable_moves()
    kept = {}
    for base_id, moveset in out.items():
        filtered = keeping_learnable_moveset(base_id, moveset, learnable,
                                             usage_order.get(base_id, []))
        if filtered is not None:
            kept[base_id] = filtered
    return dict(sorted(kept.items()))


def fetch_mega_json(source: LeagueSource) -> list[dict]:
    return json.loads(fetch_bytes(source.mega_url).decode("utf-8"))


def build_mega_rankings(rankings: list[dict], limit: int = MEGA_RANKING_LIMIT) -> list[str]:
    """メガバージョンの使用率順。シャドウは通常種族へ統合して重複を除く。"""
    out: list[str] = []
    seen: set[str] = set()
    for entry in rankings:
        species_id = entry.get("speciesId")
        if not species_id:
            continue
        base_id = species_id.removesuffix("_shadow")
        if base_id in seen:
            continue
        seen.add(base_id)
        out.append(base_id)
        if len(out) >= limit:
            break
    return out


def merge_missing_move_usage(base: dict[str, dict], extra: dict[str, dict]) -> dict[str, dict]:
    """通常リーグに無い種族（＝メガ形態）だけ足す。

    通常種族の採用順は通常リーグ側を正とする。メガ版の数字で上書きすると、
    メガ以外の形式で見たときの並びが変わってしまう。
    """
    merged = dict(base)
    for species_id, usage in extra.items():
        merged.setdefault(species_id, usage)
    return dict(sorted(merged.items()))


def build_move_usage(rankings: list[dict]) -> dict[str, dict]:
    """技ごとの使用数の多い順に並べた技IDを、種族別に返す。

    アプリはこの順で技の選択肢を並べる。上流の moveset は上位2つしか無く、
    3つ目以降は強さの目安式に落ちて実際の採用順と食い違っていた。
    """
    out: dict[str, dict] = {}
    for entry in rankings:
        species_id = entry.get("speciesId")
        if not species_id:
            continue
        moves = entry.get("moves") or {}
        usage = {}
        for key, out_key in (("fastMoves", "fastIds"), ("chargedMoves", "chargedIds")):
            ranked = sorted(moves.get(key) or [],
                            key=lambda m: -(m.get("uses") or 0))
            ids = [normalized_move_id(m.get("moveId")) for m in ranked]
            usage[out_key] = [i for i in ids if i]
        if not usage["fastIds"] and not usage["chargedIds"]:
            continue

        # シャドウは通常種族へ統合する（build_league_map と同じ扱い）。
        base_id = species_id.removesuffix("_shadow")
        if species_id == base_id:
            out[base_id] = usage
        else:
            out.setdefault(base_id, usage)
    learnable = learnable_moves()
    kept = {}
    for base_id, usage in out.items():
        filtered = keeping_learnable_usage(base_id, usage, learnable)
        if filtered is not None:
            kept[base_id] = filtered
    return dict(sorted(kept.items()))


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
    parser.add_argument("--usage-output", default=USAGE_OUT, help="Move usage JSON path")
    args = parser.parse_args()

    leagues: dict[str, dict] = {}
    rankings_out: dict[str, list] = {}
    usage_out: dict[str, dict] = {}
    mega_rankings_out: dict[str, list] = {}
    sources: list[dict] = []
    for source in LEAGUES:
        rankings, last_modified = fetch_json(source)
        leagues[source.key] = build_league_map(rankings)
        rankings_out[source.key] = build_rankings(rankings)
        mega_rankings = fetch_mega_json(source)
        usage_out[source.key] = merge_missing_move_usage(build_move_usage(rankings),
                                                         build_move_usage(mega_rankings))
        mega_rankings_out[source.key] = build_mega_rankings(mega_rankings)
        sources.append({
            "league": source.key,
            "url": source.url,
            "lastModified": last_modified,
        })
        print(f"{source.key}: {len(leagues[source.key])} movesets, {len(rankings_out[source.key])} ranked, "
              f"{len(mega_rankings_out[source.key])} mega ranked")

    payload = {
        "source": "PvPoke",
        "updatedAt": dt.datetime.now(dt.UTC).date().isoformat(),
        "sources": sources,
        "leagues": leagues,
        "rankings": rankings_out,
    }

    usage_payload = {
        "schemaVersion": 1,
        "updatedAt": payload["updatedAt"],
        "leagues": usage_out,
    }
    mega_rankings_payload = {
        "schemaVersion": 1,
        "updatedAt": payload["updatedAt"],
        "leagues": mega_rankings_out,
    }

    # リトル（CP500）。PvPoke のメガ版には CP500 が無く（メガは CP500 に出られない）、
    # メガ順位は作らない。
    little_source = LeagueSource("little", LITTLE_FILE_NAME)
    little_rankings, _ = fetch_json(little_source)
    little_payload = {
        "schemaVersion": 1,
        "updatedAt": payload["updatedAt"],
        "source": "PvPoke",
        "url": little_source.url,
        "movesets": build_league_map(little_rankings),
        "rankings": build_rankings(little_rankings),
        "moveUsage": build_move_usage(little_rankings),
    }
    print(f"little: {len(little_payload['movesets'])} movesets, "
          f"{len(little_payload['rankings'])} ranked, "
          f"{len(little_payload['moveUsage'])} usage")

    # PvPoke に変化が無い日でも updatedAt だけが動くため、日付以外が同じなら書かない。
    # 毎日の無意味なコミットと、それによる validate_shared_data の恒常的な赤を防ぐ。
    for path, document in (
        (args.output, payload),
        (args.usage_output, usage_payload),
        (MEGA_RANKINGS_OUT, mega_rankings_payload),
        (LITTLE_OUT, little_payload),
    ):
        text = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if write_text_if_changed(path, text):
            print(f"wrote {path}")
        else:
            print(f"unchanged {path}")


if __name__ == "__main__":
    main()
