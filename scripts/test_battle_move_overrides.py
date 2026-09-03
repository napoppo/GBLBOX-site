"""配信する技調整を、いつ出していつ落とすかの判断のテスト。

energy などは公式発表が増減しか言わないため予想値で、外れていればマスターと
永久に一致しない。「マスターと一致したか」ではなく「マスターが発表前の値から
動いたか」で判断していることを固定する。
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 生成スクリプトはネットワーク取得を伴う。判断ロジックだけを見たいので差し替える。
if "secure_fetch" not in sys.modules:
    stub = types.ModuleType("secure_fetch")
    stub.fetch_bytes = lambda url: b""
    sys.modules["secure_fetch"] = stub

import update_battle_master as target


def moves(power: int, energy: int) -> dict:
    return {"BODY_SLAM": {"power": power, "energy": energy, "energyGain": 0, "turns": 1}}


class MoveOverrideRetirementTests(unittest.TestCase):
    table = {"BODY_SLAM": {"power": 65, "energy": 45}}

    def build(self, master: dict, baseline: dict) -> tuple[dict, dict]:
        with patch.object(target, "TWILIGHT_TRAILS_MOVE_OVERRIDES", self.table):
            document, next_baseline = target.build_twilight_trails_overrides(master, baseline)
        return document, next_baseline["moves"]

    def test_未反映なら配信して発表前の値を控える(self):
        document, baseline = self.build(moves(55, 35), {})
        self.assertEqual(len(document["overrides"]), 1)
        self.assertEqual(document["overrides"][0]["power"], 65)
        self.assertEqual(baseline["BODY_SLAM"]["masterThen"], {"energy": 35, "power": 55})
        self.assertNotIn("retired", baseline["BODY_SLAM"])

    def test_予想が外れていてもマスターが動いたら落とす(self):
        _, baseline = self.build(moves(55, 35), {})
        # ゲーム側は 65/40 で実装した。予想の 45 とは一致しないが、発表前の値からは動いた。
        document, next_baseline = self.build(moves(65, 40), baseline)
        self.assertEqual(document["overrides"], [])
        self.assertTrue(next_baseline["BODY_SLAM"]["retired"])

    def test_一度落としたら出し直さない(self):
        _, baseline = self.build(moves(55, 35), {})
        _, baseline = self.build(moves(65, 40), baseline)
        document, next_baseline = self.build(moves(55, 35), baseline)
        self.assertEqual(document["overrides"], [])
        self.assertTrue(next_baseline["BODY_SLAM"]["retired"])

    def test_マスターが調整表に追いついたら出さない(self):
        document, baseline = self.build(moves(65, 45), {})
        self.assertEqual(document["overrides"], [])
        self.assertTrue(baseline["BODY_SLAM"]["retired"])

    def test_調整表を書き換えたら控えを取り直して出す(self):
        _, baseline = self.build(moves(55, 35), {})
        _, baseline = self.build(moves(65, 40), baseline)
        self.assertTrue(baseline["BODY_SLAM"]["retired"])

        # 翌シーズンに同じ技が再調整された。前回ぶんは反映済みなので、控えを
        # 取り直さないと「もう動いた」と見なして新しい調整を出せなくなる。
        with patch.object(target, "TWILIGHT_TRAILS_MOVE_OVERRIDES",
                          {"BODY_SLAM": {"power": 70, "energy": 40}}):
            document, next_baseline = target.build_twilight_trails_overrides(moves(65, 40), baseline)
        self.assertEqual(len(document["overrides"]), 1)
        self.assertEqual(document["overrides"][0]["power"], 70)
        self.assertEqual(next_baseline["moves"]["BODY_SLAM"]["masterThen"], {"energy": 40, "power": 65})

    def test_マスターから消えた技は飛ばして続ける(self):
        with patch.object(target, "TWILIGHT_TRAILS_MOVE_OVERRIDES",
                          {"BODY_SLAM": {"power": 65}, "GONE_MOVE": {"power": 10}}):
            document, next_baseline = target.build_twilight_trails_overrides(moves(55, 35), {})
        self.assertEqual([o["moveId"] for o in document["overrides"]], ["BODY_SLAM"])
        self.assertNotIn("GONE_MOVE", next_baseline["moves"])


if __name__ == "__main__":
    unittest.main()
