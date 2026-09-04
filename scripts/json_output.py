"""生成したJSONを「中身が変わったときだけ」書き出すための共通処理。

配信データの生成スクリプトは毎日走るが、上流に変化がない日でも `updatedAt` に
その日の日付を入れてしまうため、内容が同じでもファイルが書き換わる。すると
GitHub Actions が毎日コミットし、アプリ同梱のコピーとの照合（validate_shared_data）が
常に赤くなる。赤が固定化すると本物のズレを見落とすので、日付だけの差分では
既存ファイルをそのまま残す。

`updatedAt` はアプリの「データ更新日」表示に使われる。ここを凍結することで、
表示の意味が「ジョブが走った日」から「データが実際に変わった日」になる。
取得日時は別に `lastFetchDate` として持っているので、情報は失われない。
"""
from __future__ import annotations

import json
import os
from typing import Callable, Iterable

VOLATILE_KEYS: tuple[str, ...] = ("updatedAt",)


def drop_keys(document: object, keys: Iterable[str]) -> object:
    """トップレベルの指定キーを落とす。dict でなければそのまま返す。"""
    if not isinstance(document, dict):
        return document
    dropped = set(keys)
    return {k: v for k, v in document.items() if k not in dropped}


def write_text_if_changed(
    path: str,
    text: str,
    volatile_keys: Iterable[str] = VOLATILE_KEYS,
    normalize: Callable[[object], object] | None = None,
) -> bool:
    """比較対象から揺れる値を除いて既存ファイルと同じなら書かない。書いたら True。

    `normalize` を渡すとトップレベルの `volatile_keys` の代わりにそれを使う。
    既存ファイルが無い・JSONとして読めない場合は必ず書き直す。
    """
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)

    if normalize is None:
        keys = tuple(volatile_keys)

        def normalize(document: object) -> object:  # noqa: F811
            return drop_keys(document, keys)

    try:
        with open(path, encoding="utf-8") as handle:
            existing = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    else:
        if normalize(existing) == normalize(json.loads(text)):
            return False

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return True
