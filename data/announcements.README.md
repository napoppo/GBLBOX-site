# announcements.json 管理ガイド

`announcements.json` は iOS と Android が共有するお知らせ配信データです。
`schemaVersion` は現在 `1` です。

## ビルド条件はOS別

| フィールド | 対象 | 未指定または `null` |
|---|---|---|
| `minimumBuild` | iOS `CURRENT_PROJECT_VERSION` | 下限なし |
| `maximumBuild` | iOS `CURRENT_PROJECT_VERSION` | 上限なし |
| `recommendedBuild` | iOS `CURRENT_PROJECT_VERSION` | 更新促しなし |
| `minimumBuildAndroid` | Android `versionCode` | 下限なし |
| `maximumBuildAndroid` | Android `versionCode` | 上限なし |
| `recommendedBuildAndroid` | Android `versionCode` | 更新促しなし |

iOSのビルド番号とAndroidの`versionCode`は別系列です。Androidは
`minimumBuild` / `maximumBuild`を判定に使わず、Android専用フィールドだけを使います。
既存のお知らせをAndroidにも表示する場合は、Androidフィールドを省略するか`null`にします。
iOSだけに表示する場合は `maximumBuildAndroid: 0` を指定します。
Androidだけに表示する場合は `maximumBuild: 0` を指定します。

```json
{
  "id": "example-1",
  "enabled": true,
  "publishedAt": "2026-07-13",
  "minimumBuild": 187,
  "maximumBuild": null,
  "minimumBuildAndroid": 2,
  "maximumBuildAndroid": null,
  "titleJa": "お知らせ",
  "titleEn": "Notice",
  "bodyJa": "本文",
  "bodyEn": "Body"
}
```

## フィールド

- `id`: 一意で変更しない識別子。
- `enabled`: `false`なら両OSで非表示。
- `publishedAt`: 新着順に使う`YYYY-MM-DD`文字列。
- `titleJa` / `bodyJa`: 必須の日本語本文。
- `titleEn` / `bodyEn`: 任意の英語本文。未指定時は日本語へフォールバック。
- `actionTitleJa` / `actionTitleEn`: 任意のリンク表示文言。
- `actionUrl`: 任意。`https://` URLだけを指定する。
- `recommendedBuild`: 任意。iOSで現在ビルドがこの値未満の場合だけ、詳細画面に非強制の更新案内を追加表示する。
- `recommendedBuildAndroid`: 任意。Androidで現在`versionCode`がこの値未満の場合だけ、起動時ダイアログとお知らせ詳細に非強制の更新案内を追加表示する。
- `updatePromptJa` / `updatePromptEn`: 任意。更新促し文。**iOS / Android で共有**されるため、ストア名を書く場合は両OSで通じる表現にするか、OS別のお知らせに分ける。
- `updateActionTitleJa` / `updateActionTitleEn`: 任意。更新ボタンの文言。未指定時はアプリ側の既定文言（iOS: App Store / Android: Google Play）。**iOS / Android で共有**。
- `updateAppStoreUrl`: 任意。iOSの更新ボタンの遷移先。iOSアプリはGBLBOXのApp Store URLだけを受け付ける。
- `updatePlayStoreUrl`: 任意。Androidの更新ボタンの遷移先。Androidアプリは `https://play.google.com/` のURLだけを受け付ける（例: `https://play.google.com/store/apps/details?id=com.gblbox.android`）。

## 非強制アップデート案内の運用

最新版への誘導は、複数バージョン分を順番に出すのではなく、最新のお知らせ1件にまとめます。
古いビルドだけに出したい場合は `maximumBuild` を `recommendedBuild - 1` にし、
同じお知らせへ `recommendedBuild` と `updateAppStoreUrl` を指定します。
Androidも同様に、`recommendedBuildAndroid` と `updatePlayStoreUrl` を指定します
（Androidは全ビルドに本文を見せたまま、`recommendedBuildAndroid` 未満にだけ更新セクションが付きます）。

例: build 190 を推奨し、189以下にだけ案内する場合。

```json
{
  "id": "2.4.2-190-soft-update",
  "enabled": true,
  "publishedAt": "2026-07-15",
  "minimumBuild": null,
  "maximumBuild": 189,
  "recommendedBuild": 190,
  "titleJa": "GBLBOX 2.4.2 のアップデート",
  "titleEn": "GBLBOX 2.4.2 Update",
  "bodyJa": "更新内容をここにまとめます。",
  "bodyEn": "Summarize the update here.",
  "updatePromptJa": "最新版では改善と不具合修正を利用できます。App Storeからアップデートできます。",
  "updatePromptEn": "The latest version includes improvements and fixes. You can update from the App Store.",
  "updateActionTitleJa": "App Storeでアップデート",
  "updateActionTitleEn": "Update on the App Store",
  "updateAppStoreUrl": "https://apps.apple.com/jp/app/gbl-box/id6776499795"
}
```

変更後は次を実行します。

```bash
python3 scripts/validate_shared_data.py --site-only
```
