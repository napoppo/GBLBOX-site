"""上流未反映時の追加技と、上流反映後の優先順位を検証する。"""
import unittest

from update_battle_master import build_moves, build_pokedex


class MegaSquadsMovesTests(unittest.TestCase):
    def test_missing_upstream_moves_have_pvp_stats_and_buff(self):
        moves = build_moves({"moves": []}, lambda _: None)
        fell = moves["FELL_STINGER_PLUS"]
        dark = moves["DARK_PULSE_PLUS"]
        self.assertEqual((fell["power"], fell["energy"]), (40, 35))
        self.assertEqual((fell["buffs"], fell["buffTarget"], fell["buffChance"]),
                         ([1, 0], "self", 1.0))
        self.assertEqual((dark["power"], dark["energy"]), (60, 50))
        self.assertNotIn("buffs", dark)

    def test_upstream_values_take_precedence(self):
        upstream = {"moveId": "DARK_PULSE_PLUS", "power": 65, "energy": 45}
        move = build_moves({"moves": [upstream]}, lambda _: None)["DARK_PULSE_PLUS"]
        self.assertEqual((move["power"], move["energy"]), (65, 45))

    def test_only_mega_forms_receive_additional_move_without_duplicates(self):
        pokemon = [
            {"speciesId": species, "speciesName": species, "dex": dex,
             "baseStats": {"atk": 1, "def": 1, "hp": 1}, "chargedMoves": charges}
            for species, dex, charges in [
                ("beedrill", 15, ["FELL_STINGER"]),
                ("beedrill_mega", 15, ["FELL_STINGER", "FELL_STINGER_PLUS"]),
                ("houndoom", 229, ["FOUL_PLAY"]),
                ("houndoom_mega", 229, ["FOUL_PLAY"]),
            ]
        ]
        result = {p["speciesId"]: p["chargedMoves"]
                  for p in build_pokedex({"pokemon": pokemon}, {})}
        self.assertEqual(result["beedrill"], ["FELL_STINGER"])
        self.assertNotIn("DARK_PULSE_PLUS", result["houndoom"])
        self.assertEqual(result["beedrill_mega"].count("FELL_STINGER_PLUS"), 1)
        self.assertEqual(result["houndoom_mega"].count("DARK_PULSE_PLUS"), 1)


if __name__ == "__main__":
    unittest.main()
