# アプリ内通知の下書き

公開前の文面を置く。`data/announcements.json` へは**App Store で公開されたことを確認してから**入れる。
先に入れると、設定内のお知らせ履歴（`enabled` を見ない）に未公開の内容が出てしまう。

入れるときの手順:

1. `data/announcements.json` の先頭へ追加する
2. `publishedAt` を公開日にする
3. 直前の通知を `enabled: false` にする
4. `recommendedBuild` は**実際に公開されたビルド番号**にする（App Store Connect で確認する。
   TestFlight どまりのビルドを指定すると、最新版の利用者にも更新を促してしまう）

---

## 2.7.5 (387) — 2026-09-05 に `data/announcements.json` へ反映済み（App Store 公開ビルドは 387 と確認）

```json
{
  "id": "2.7.5-387",
  "enabled": true,
  "publishedAt": "（公開日）",
  "maximumBuild": 386,
  "maximumBuildAndroid": 0,
  "recommendedBuild": 387,
  "titleJa": "GBLBOX 2.7.5 の配信を開始しました",
  "titleEn": "GBLBOX 2.7.5 is now available",
  "updatePromptJa": "タブ切り替えの引っかかりを解消し、メガのカップに対応した2.7.5が利用できます。アップデートをおすすめします。",
  "updatePromptEn": "Version 2.7.5 removes the tab-switch stutter and adds Mega cup support. We recommend updating.",
  "updateActionTitleJa": "App Storeで2.7.5へ更新",
  "updateActionTitleEn": "Update to 2.7.5",
  "updateAppStoreUrl": "https://apps.apple.com/jp/app/gbl-box/id6776499795"
}
```

bodyJa:

```
GBLBOX 2.7.5 の配信を開始しました。

・ボックスのタブに切り替えるたびに画面が1秒ほど固まっていたのを直しました。ほかのタブを開くときの引っかかりも軽くなります
・メガバージョンのカップで、メガ形態が候補や技の並びに出るようになりました。通常リーグの使用率にメガが入っておらず、これまで出てきませんでした
・シミュレータとブレイク探索でもカップを選べるようになり、リーグ・カップの選択を3画面で共通にしました

そのほか、ブレイク探索と技カウントの細かな不具合を直しています。

気になる点は、設定内の「かんたんフィードバック」からお知らせください。
```

bodyEn:

```
GBLBOX 2.7.5 is now available.

- Fixed the app freezing for about a second when switching to the Box tab. Other tabs open more smoothly too
- Mega forms now appear in the suggestions and move order for Mega Edition cups. They were missing because regular league usage data does not include Mega forms
- League and cup selection moved to a shared header across the simulator, Move Counts, and Breakpoints

Various smaller fixes in Breakpoints and Move Counts are also included.

If something looks off, please let us know from Quick Feedback in Settings.
```
