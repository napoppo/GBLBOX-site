"""日付だけが動いた日に配信データを書き換えないことのテスト。

上流に変化が無くても updatedAt に当日の日付が入るため、素直に書き出すと毎日
コミットが生まれ、アプリ同梱コピーとの照合が恒常的に赤くなる。赤が固定化すると
本物のズレを見落とすので、「中身が変わったときだけ書く」を固定する。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from json_output import drop_keys, write_text_if_changed


def dump(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


class WriteTextIfChangedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = str(Path(self.dir.name) / "out.json")

    def test_日付だけの差分では書かない(self) -> None:
        write_text_if_changed(self.path, dump({"updatedAt": "2026-09-03", "leagues": {"great": [1]}}))
        before = Path(self.path).read_text(encoding="utf-8")

        wrote = write_text_if_changed(self.path, dump({"updatedAt": "2026-09-04", "leagues": {"great": [1]}}))

        self.assertFalse(wrote)
        self.assertEqual(Path(self.path).read_text(encoding="utf-8"), before)

    def test_中身が変わったら書く(self) -> None:
        write_text_if_changed(self.path, dump({"updatedAt": "2026-09-03", "leagues": {"great": [1]}}))

        wrote = write_text_if_changed(self.path, dump({"updatedAt": "2026-09-04", "leagues": {"great": [2]}}))

        self.assertTrue(wrote)
        self.assertEqual(json.loads(Path(self.path).read_text(encoding="utf-8"))["updatedAt"], "2026-09-04")

    def test_ファイルが無ければ書く(self) -> None:
        self.assertTrue(write_text_if_changed(self.path, dump({"updatedAt": "2026-09-04"})))

    def test_壊れたファイルは書き直す(self) -> None:
        Path(self.path).write_text("{こわれている", encoding="utf-8")

        self.assertTrue(write_text_if_changed(self.path, dump({"updatedAt": "2026-09-04"})))

    def test_normalizeで入れ子の版情報も無視できる(self) -> None:
        def without_provenance(document: object) -> object:
            stripped = drop_keys(document, ("updatedAt", "sourceVersion"))
            if isinstance(stripped, dict) and isinstance(stripped.get("entries"), list):
                stripped["entries"] = [drop_keys(e, ("sourceVersion",)) for e in stripped["entries"]]
            return stripped

        old = {"updatedAt": "2026-08-31", "sourceVersion": "1", "entries": [{"speciesId": "a", "sourceVersion": "1"}]}
        new = {"updatedAt": "2026-09-04", "sourceVersion": "2", "entries": [{"speciesId": "a", "sourceVersion": "2"}]}
        write_text_if_changed(self.path, dump(old), normalize=without_provenance)

        wrote = write_text_if_changed(self.path, dump(new), normalize=without_provenance)

        self.assertFalse(wrote)

    def test_normalizeでも中身が変われば書く(self) -> None:
        def without_provenance(document: object) -> object:
            stripped = drop_keys(document, ("updatedAt", "sourceVersion"))
            if isinstance(stripped, dict) and isinstance(stripped.get("entries"), list):
                stripped["entries"] = [drop_keys(e, ("sourceVersion",)) for e in stripped["entries"]]
            return stripped

        old = {"updatedAt": "2026-08-31", "sourceVersion": "1", "entries": [{"speciesId": "a", "sourceVersion": "1"}]}
        new = {"updatedAt": "2026-09-04", "sourceVersion": "2",
               "entries": [{"speciesId": "a", "sourceVersion": "2"}, {"speciesId": "b", "sourceVersion": "2"}]}
        write_text_if_changed(self.path, dump(old), normalize=without_provenance)

        self.assertTrue(write_text_if_changed(self.path, dump(new), normalize=without_provenance))


if __name__ == "__main__":
    unittest.main()
