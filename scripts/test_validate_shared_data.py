import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.validate_shared_data import (
    ContractError,
    android_config_from_site,
    android_schedule_core,
    overlay_shared_values,
    semantic_hash,
    validate_announcements,
    validate_app_config,
)


class AppConfigAdsTests(unittest.TestCase):
    def config(self, ads: object) -> dict:
        return {
            "schemaVersion": 1,
            "forceUpdate": {"enabled": True, "minimumSupportedBuild": 1},
            "analytics": {"enabled": True},
            "billing": {"enabled": True},
            "proTrial": {"freeUseLimit": 1, "resetGeneration": 1, "freeIndividualLimit": 50},
            "ads": ads,
        }

    def test_known_banner_size_modes_pass(self) -> None:
        for mode in ("standard50", "large100", "split50_100"):
            validate_app_config(self.config({"bannerSizeMode": mode}), "test")

    def test_typo_in_banner_size_mode_is_rejected(self) -> None:
        # アプリ側は未知値を standard50 へ倒すので、ここで弾かないと無言で効かない。
        with self.assertRaises(ContractError):
            validate_app_config(self.config({"bannerSizeMode": "large_100"}), "test")

    def test_ads_section_is_optional(self) -> None:
        document = self.config({"bannerSizeMode": "standard50"})
        del document["ads"]
        validate_app_config(document, "test")


class SharedDataContractTests(unittest.TestCase):
    def test_object_key_order_and_whitespace_are_not_semantic(self) -> None:
        first = {"b": 2, "a": {"d": 4, "c": 3}}
        second = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(semantic_hash(first), semantic_hash(second))

    def test_array_order_remains_semantic(self) -> None:
        self.assertNotEqual(semantic_hash({"rankings": ["a", "b"]}), semantic_hash({"rankings": ["b", "a"]}))

    def test_shared_overlay_retains_android_extensions(self) -> None:
        android = {
            "forceUpdate": {"minimumSupportedBuild": 0, "minimumSupportedBuildAndroid": 7},
            "billing": {"enabled": False, "monthlyProductId": "monthly"},
        }
        site = {
            "forceUpdate": {"minimumSupportedBuild": 185},
            "billing": {"enabled": True},
        }

        merged = overlay_shared_values(android, site)

        self.assertEqual(185, merged["forceUpdate"]["minimumSupportedBuild"])
        self.assertEqual(7, merged["forceUpdate"]["minimumSupportedBuildAndroid"])
        self.assertTrue(merged["billing"]["enabled"])
        self.assertEqual("monthly", merged["billing"]["monthlyProductId"])

    def test_android_config_does_not_import_ios_force_update_copy(self) -> None:
        android = {
            "schemaVersion": 1,
            "forceUpdate": {
                "enabled": False,
                "minimumSupportedBuild": 0,
                "appStoreUrl": "",
                "messageJa": "Play ストアから更新",
                "messageEn": "Update from Google Play",
            },
            "analytics": {"enabled": False},
            "billing": {"enabled": False, "monthlyProductId": "monthly"},
            "proTrial": {"freeUseLimit": 1, "resetGeneration": 1, "freeIndividualLimit": 1},
        }
        site = {
            "schemaVersion": 1,
            "forceUpdate": {
                "enabled": True,
                "minimumSupportedBuild": 185,
                "minimumSupportedBuildAndroid": 0,
                "appStoreUrl": "https://apps.apple.com/example",
                "messageJa": "App Storeから更新",
                "messageEn": "Update from the App Store",
            },
            "analytics": {"enabled": True},
            "billing": {"enabled": True},
            "proTrial": {"freeUseLimit": 999, "resetGeneration": 4, "freeIndividualLimit": 50},
        }

        merged = android_config_from_site(android, site)

        self.assertFalse(merged["forceUpdate"]["enabled"])
        self.assertEqual(0, merged["forceUpdate"]["minimumSupportedBuildAndroid"])
        self.assertEqual("Play ストアから更新", merged["forceUpdate"]["messageJa"])
        self.assertEqual(4, merged["proTrial"]["resetGeneration"])
        self.assertEqual("monthly", merged["billing"]["monthlyProductId"])

    def test_android_schedule_core_removes_only_archived_rules(self) -> None:
        document = {
            "schemaVersion": 2,
            "currentSeasonId": "s1",
            "seasons": [{
                "id": "s1",
                "formatRules": [
                    {"id": "great"},
                    {"id": "little", "isArchived": True},
                ],
                "schedule": [{"id": "week", "formatIds": ["great"]}],
            }],
        }

        core, archived = android_schedule_core(document)

        self.assertEqual([{"id": "great"}], core["seasons"][0]["formatRules"])
        self.assertEqual([{"id": "little", "isArchived": True}], archived)

    def test_soft_update_announcement_fields_are_validated(self) -> None:
        document = {
            "schemaVersion": 1,
            "announcements": [{
                "id": "2.4.2-190-soft-update",
                "enabled": True,
                "publishedAt": "2026-07-15",
                "maximumBuild": 189,
                "recommendedBuild": 190,
                "titleJa": "GBLBOX 2.4.2 のアップデート",
                "titleEn": "GBLBOX 2.4.2 Update",
                "bodyJa": "更新内容",
                "bodyEn": "Release notes",
                "updatePromptJa": "最新版をおすすめします。",
                "updatePromptEn": "The latest version is recommended.",
                "updateActionTitleJa": "App Storeでアップデート",
                "updateActionTitleEn": "Update on the App Store",
                "updateAppStoreUrl": "https://apps.apple.com/jp/app/gbl-box/id6776499795",
            }],
        }

        validate_announcements(document, "test announcements")

    def test_soft_update_app_store_url_requires_recommended_build(self) -> None:
        document = {
            "schemaVersion": 1,
            "announcements": [{
                "id": "bad-soft-update",
                "enabled": True,
                "publishedAt": "2026-07-15",
                "titleJa": "案内",
                "bodyJa": "本文",
                "updateAppStoreUrl": "https://apps.apple.com/jp/app/gbl-box/id6776499795",
            }],
        }

        with self.assertRaises(ContractError):
            validate_announcements(document, "test announcements")

    def test_soft_update_app_store_url_rejects_other_apps(self) -> None:
        document = {
            "schemaVersion": 1,
            "announcements": [{
                "id": "bad-url",
                "enabled": True,
                "publishedAt": "2026-07-15",
                "recommendedBuild": 190,
                "titleJa": "案内",
                "bodyJa": "本文",
                "updateAppStoreUrl": "https://apps.apple.com/jp/app/example/id1234567890",
            }],
        }

        with self.assertRaises(ContractError):
            validate_announcements(document, "test announcements")

    def _android_announcement(self, **overrides: object) -> dict:
        announcement = {
            "id": "android-1.0.0-39",
            "enabled": True,
            "publishedAt": "2026-07-25",
            "maximumBuild": 0,
            "recommendedBuildAndroid": 39,
            "titleJa": "GBL Box 1.0.0 (39) のアップデート",
            "bodyJa": "内部テスト版ビルド39を配信しました。",
            "updatePlayStoreUrl": "https://play.google.com/store/apps/details?id=com.gblbox.android",
        }
        announcement.update(overrides)
        return {"schemaVersion": 1, "announcements": [announcement]}

    def test_android_announcement_excluding_ios_is_accepted(self) -> None:
        validate_announcements(self._android_announcement(), "test announcements")

    def test_android_announcement_requires_explicit_ios_range(self) -> None:
        # maximumBuild が無いと iOS 側の isRelevant を素通りし、全 iOS ユーザーに
        # 「Google Play から更新してください」が出てしまう。
        document = self._android_announcement()
        del document["announcements"][0]["maximumBuild"]

        with self.assertRaises(ContractError):
            validate_announcements(document, "test announcements")

    def test_play_store_url_requires_recommended_build_android(self) -> None:
        document = self._android_announcement()
        del document["announcements"][0]["recommendedBuildAndroid"]

        with self.assertRaises(ContractError):
            validate_announcements(document, "test announcements")

    def test_play_store_url_rejects_other_apps(self) -> None:
        document = self._android_announcement(
            updatePlayStoreUrl="https://play.google.com/store/apps/details?id=com.example.other",
        )

        with self.assertRaises(ContractError):
            validate_announcements(document, "test announcements")

    def test_announcement_without_any_platform_targeting_is_rejected(self) -> None:
        document = {
            "schemaVersion": 1,
            "announcements": [{
                "id": "no-targeting",
                "enabled": True,
                "publishedAt": "2026-07-25",
                "titleJa": "案内",
                "bodyJa": "本文",
            }],
        }

        with self.assertRaises(ContractError):
            validate_announcements(document, "test announcements")


if __name__ == "__main__":
    unittest.main()
