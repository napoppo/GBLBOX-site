# gbl_knowledge.json

GBL Box の対策知識の配信ファイルです。

- 正本: `napoppo/GBLBOX-knowledge`（このファイルは手で編集しない）
- 生成: 正本リポジトリで `python3 scripts/build_public_data.py` を実行し、
  `dist/gbl_knowledge.json` をここへコピーする
- 中身: `draft` / `reviewed` / `published` のみ。`stale`（技変更などで検証済みと
  言えなくなったもの）と `rejected` は含まない
- アプリ側: `status` を見て、`published` 以外は「検証中の参考候補」として表示する

アプリは gblbox.com → raw.githubusercontent → github.io の順に取得を試し、
すべて失敗した場合はキャッシュ、次いで同梱データを使う。
