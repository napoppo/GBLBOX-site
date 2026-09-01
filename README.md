# GBLBOX site

App Store 公開に必要な GBLBOX（ポケモンGO 個体管理アプリ）の公式ページ。

- `index.html` … ランディング
- `index-en.html` … 英語ランディング
- `robots.txt` / `sitemap.xml` … 検索エンジン向けのクロール案内
- `marketing_plan_2026-08.md` … Xを中心にした新規ユーザー獲得計画
- `assets/` … ランディングで使うアプリ画面
- `privacy.html` … プライバシーポリシー（日本語 / English）
- `terms.html` … 利用規約（日本語 / English）
- `support.html` … サポート・FAQ・問い合わせ

## 公開（GitHub Pages）

1. GitHub の本リポジトリ **Settings → Pages**
2. **Build and deployment → Source: Deploy from a branch**
3. **Branch: `main` / `/ (root)`** を選択して Save
4. 数分後、`https://napoppo.github.io/GBLBOX-site/` で公開

App Store Connect では次を設定:

- **サポートURL**: `https://napoppo.github.io/GBLBOX-site/support.html`
- **プライバシーポリシーURL**: `https://napoppo.github.io/GBLBOX-site/privacy.html`

独自ドメインを使う場合は、DNS が有効になってから `CNAME` ファイルを追加し、Pages のカスタムドメインに設定する。

## メモ
- 連絡先メールは各ページの `h.nakamura3557@gmail.com` を編集して変更可能。
- 個体管理・画像解析は端末内処理。GBLスケジュール・大会予定は `data/gbl_schedule.json` で配信する（**schemaVersion 2**: シーズン配列。管理手順は `data/gbl_schedule.README.md`、検証は `python3 scripts/validate_gbl_schedule.py`）。アプリ内のお知らせは `data/announcements.json` で配信する（OS別ビルド条件は `data/announcements.README.md`）。
- バトル用マスタは `data/pokedex.json` / `data/moves.json` / `data/pvpoke_movesets.json`、技調整の切替用データは `data/battle_move_overrides.json`、メガ進化レベル仕様は `data/mega_specs.json` で配信する。更新は GitHub Actions の **Update battle data**（毎日）を手動実行するか、定期実行に任せる。メガ仕様は PokeMiners Game Master を正規化し、取得失敗時は既存データを維持する。ローカル更新は `python3 scripts/update_battle_master.py --output-dir data`、`python3 scripts/update_pvpoke_moves.py --output data/pvpoke_movesets.json`、`python3 scripts/update_mega_specs.py --output data/mega_specs.json`、検証は各 `validate_*.py` を実行する。
- `battle_move_overrides.json` は次シーズン開始前の仮調整値を置くためのファイルで、`moves.json` の調整前マスターを上書きしない。公式値が確定したら、このファイルの予想フラグと値を更新する。
- 現行アプリ（**1.3.0 以降**）は `data/app_config_v2.json` のみ参照（`forceUpdate` / `analytics.enabled` / `billing.enabled`）。RevenueCat API Key、Pro Entitlement ID、PostHog Token、PostHog Host、AdMob ID はアプリ本体側で管理する。
- `data/app_config.json` は **1.2.x 以前**の互換用に最小限だけ残す（広告ユニット ID・課金フラグ）。1.3.0 以降は読まない。

## iOS / Android共有データの整合確認

3リポジトリを同じ親ディレクトリへチェックアウトしている場合、次のコマンドで
JSONのスキーマ、意味論的SHA-256、アプリ同梱フォールバックとのドリフトを確認できる。
オブジェクトのキー順と空白は無視し、ランキングやスケジュールなど意味を持つ配列順は保持する。

```bash
python3 scripts/validate_shared_data.py
```

サイトで更新された `moves` / `pokedex` / `pvpoke_movesets` を両アプリへ反映し、
Androidのスケジュールと設定フォールバックを安全に再生成する場合は次を使う。

```bash
python3 scripts/validate_shared_data.py --sync
```

- `data/gbl_schedule.json` が配信正本。
- iOSは同じ現行シーズンをコード内フォールバックとして保持する。
- Android同梱版は配信正本に、iOSと同じ`isArchived=true`の過去カップだけを追加できる。
- Android設定フォールバックは分析・課金・試用回数などの共有運用値だけを同期し、iOS専用のApp Store URL・文言・ビルド番号は取り込まない。
- `cpm.json`と`power_up_costs.json`はリモート配信せず、iOS / Android同梱版を一致させる。
