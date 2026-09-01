# gbl_schedule.json 管理ガイド

GBL スケジュール・フォーマットルール・大会情報を配信する JSON。  
iOSは `https://gblbox.com/data/gbl_schedule.json`、GitHub raw、GitHub Pagesの順で取得し、失敗時はキャッシュまたは同梱データへフォールバックする。Android同梱データは `scripts/validate_shared_data.py --sync` でこの配信正本から再生成する。

## ファイル構造（schemaVersion 2）

```json
{
  "schemaVersion": 2,
  "currentSeasonId": "forever_forward_2026",
  "seasons": [
    {
      "id": "forever_forward_2026",
      "nameJa": "新たな歩み",
      "nameEn": "Forever Forward",
      "sourceUpdatedJa": "2026年6月5日確認",
      "sourceUpdatedEn": "Checked June 5, 2026",
      "formatRules": [ ... ],
      "schedule": [ ... ],
      "tournamentEvents": [ ... ]
    }
  ]
}
```

| 項目 | 説明 |
|------|------|
| `currentSeasonId` | アプリが表示するシーズン。`seasons` 内の `id` と一致させる |
| `seasons[].formatRules` | そのシーズンで使うリーグ・カップ定義 |
| `seasons[].schedule` | 週次ローテーション（`formatIds` は同シーズンの `formatRules[].id` を参照） |
| `seasons[].tournamentEvents` | そのシーズン期間の公式大会（任意） |

**アプリの挙動:** `currentSeasonId` に一致するシーズンを現行として表示し、`seasons` に残っている過去シーズンも予定画面のシーズン選択から閲覧できる。ウィジェットは常に現行シーズンを表示する。

## よくある更新

### 週次スケジュールを1週追加

`currentSeasonId` のシーズン → `schedule` 配列の末尾に追加。

```json
{
  "id": "2026-09-08",
  "start": "2026-09-08T20:00:00Z",
  "end": "2026-09-15T20:00:00Z",
  "formatIds": ["great", "ultra", "master"],
  "stardustBonus": true
}
```

- `id`: 開始日（`YYYY-MM-DD`）推奨
- `start` / `end`: UTC の ISO8601（通常 火曜 20:00 UTC = 水曜 05:00 JST）
- `formatIds`: 先頭がアプリのデフォルト選択リーグ
- `stardustBonus`: 星の砂2倍週なら `true`

更新後、`sourceUpdatedJa` / `sourceUpdatedEn` も書き換える。

### 新しいカップを追加

同じシーズンの `formatRules` に定義を追加 → `schedule` の `formatIds` で参照。

### 新シーズン開始

1. `seasons` に新ブロックを追加（下記テンプレートをコピー）
2. `currentSeasonId` を新シーズンの `id` に変更
3. 旧シーズンは削除せず JSON 内に残す（参照用）

## 新シーズンテンプレート

```json
{
  "id": "next_season_2026",
  "nameJa": "シーズン名（日本語）",
  "nameEn": "Season Name (English)",
  "sourceUpdatedJa": "2026年○月○日確認",
  "sourceUpdatedEn": "Checked Month DD, 2026",
  "formatRules": [
    {
      "id": "great",
      "nameJa": "スーパーリーグ",
      "nameEn": "Great League",
      "league": "great",
      "cpCap": 1500
    },
    {
      "id": "ultra",
      "nameJa": "ハイパーリーグ",
      "nameEn": "Ultra League",
      "league": "ultra",
      "cpCap": 2500
    },
    {
      "id": "master",
      "nameJa": "マスターリーグ",
      "nameEn": "Master League",
      "league": "master",
      "cpCap": null
    }
  ],
  "schedule": [],
  "tournamentEvents": []
}
```

## formatRules の主なフィールド

| フィールド | 用途 |
|------------|------|
| `league` | `great` / `ultra` / `master` |
| `cpCap` | CP上限（マスターは `null`） |
| `allowedTypes` | 使用可能タイプ（特殊カップ） |
| `bannedTypes` | 禁止タイプ |
| `bannedSpeciesIds` | 禁止種族 ID（pokedex の speciesId） |
| `megaAllowed` | メガ参加可 |
| `requiresMiddleEvolution` | 進化カップ（中間進化のみ） |
| `regulationLinesJa` / `regulationLinesEn` | レギュレーション説明（箇条書き・表示専用。自動判定には使わない） |
| `unsupportedNoteJa` / `unsupportedNoteEn` | アプリが自動判定できない旨の注意 |
| `officialUrlJa` / `officialUrlEn` | 公式お知らせ URL |

### レギュレーション文の追加例

`formatRules` の各カップに、構造化フィールドで表せないルールを箇条書きで書けます。

```json
"regulationLinesJa": [
  "伝説・幻ポケモンは使用できません",
  "同一種族は1匹まで"
],
"regulationLinesEn": [
  "Legendary and Mythical Pokemon are not allowed",
  "Only one Pokemon per species"
]
```

アプリの GBL タブ → ルール概要カードに表示されます。  
参加可否の自動判定に使うのは `allowedTypes` / `bannedSpeciesIds` など既存フィールドです。

## 検証

```bash
python3 scripts/validate_gbl_schedule.py
```

- JSON 構文
- `currentSeasonId` の存在
- `schedule[].formatIds` が `formatRules` に存在するか
- 週次 `id` の重複

## 互換

- **schemaVersion 2** … 現行（シーズン配列）
- **schemaVersion 1** … 旧形式（ルート直下に `seasonNameJa` 等）。アプリは後方互換で読めるが、新規編集は v2 を使う

## サイトからのルール更新（アプリ更新不要）

`formatRules` に新カップを追加し、`schedule` の `formatIds` で参照すれば反映されます。

| やりたいこと | フィールド |
|-------------|-----------|
| 禁止ポケモン（自動判定） | `bannedSpeciesIds` |
| タイプ制限 | `allowedTypes` / `bannedTypes` |
| ルール説明（表示のみ） | `regulationLinesJa` / `regulationLinesEn` |
| 自動判定できない注意 | `unsupportedNoteJa` / `unsupportedNoteEn` |

**v1.4.0 以降のアプリ**が `gbl_schedule.json` から `formatRules` 全体を読み込みます。  
`regulationLines` は GBL タブのルール概要カードに表示されます（参加可否の自動判定には使いません）。

## デプロイ

`main` に push すると GitHub Pages 経由で配信される。
アプリは最大6時間キャッシュするため、反映確認は少し待つかアプリ再起動が必要。
