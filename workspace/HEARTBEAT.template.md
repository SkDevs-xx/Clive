# Heartbeat Checklist

このファイルに厳密に従うこと。推測や過去の会話からタスクを作り出さないこと。
報告事項がなければ `HEARTBEAT_OK` だけを返すこと。

## State
last_updated: 2000-01-01
wrapup_done: false
wrapup_time: "05:00"
last_wrapup_compressed: 2000-01-01
last_weekly_compressed: 2000-01-01

## 毎回チェック
- [ ] CURIOSITYリスト（`workspace/CURIOSITY.md`）に未調査トピックがあれば1件調べて結果を追記する

## Wrap-up 確認
- [ ] State の wrapup_done が false かつ 現在時刻が wrapup_time 以降なら WRAPUP_NEEDED を返す
  - （Python側がWrap-upを実行し、wrapup_done を true に更新する）

## 応答ルール
- すべてのチェックが問題なく、特に報告事項がない場合: `HEARTBEAT_OK` だけを返す
- 報告事項がある場合: 内容を送信する（HEARTBEAT_OK は使わない）
