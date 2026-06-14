#!/usr/bin/env python3
"""pvpoke_movesets.json の最低限の妥当性チェック。

CI で壊れたデータを配信しないためのガード。失敗時は非0で終了する。

使い方:
    python3 scripts/validate_pvpoke_movesets.py data/pvpoke_movesets.json
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/pvpoke_movesets.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for key in ("source", "updatedAt", "leagues", "rankings"):
        assert key in data, f"missing top-level key: {key}"

    for league in ("great", "ultra", "master"):
        movesets = data["leagues"].get(league)
        rankings = data["rankings"].get(league)
        assert movesets, f"empty leagues.{league}"
        assert rankings, f"empty rankings.{league}"
        assert all("speciesId" in entry for entry in rankings), \
            f"rankings.{league} has an entry without speciesId"

    print(
        f"OK: {path} | updatedAt={data['updatedAt']} | "
        f"great rankings={len(data['rankings']['great'])} "
        f"ultra={len(data['rankings']['ultra'])} master={len(data['rankings']['master'])}"
    )


if __name__ == "__main__":
    main()
