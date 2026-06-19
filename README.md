# GBLBOX site

App Store 公開に必要な GBLBOX（ポケモンGO 個体管理アプリ）の公式ページ。

- `index.html` … ランディング
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
- 個体管理・画像解析は端末内処理。GBLスケジュール・大会予定は `data/gbl_schedule.json` で配信する（**schemaVersion 2**: シーズン配列。管理手順は `data/gbl_schedule.README.md`、検証は `python3 scripts/validate_gbl_schedule.py`）。
- 現行アプリ（**1.3.0 以降**）は `data/app_config_v2.json` のみ参照（`forceUpdate` / `analytics.enabled` / `billing.enabled`）。RevenueCat API Key、Pro Entitlement ID、PostHog Token、PostHog Host、AdMob ID はアプリ本体側で管理する。
- `data/app_config.json` は **1.2.x 以前**の互換用に最小限だけ残す（広告ユニット ID・課金フラグ）。1.3.0 以降は読まない。
