# Clive Browser

Claude が永続セッション付きの Chrome を操作するための MCP サーバー。

Playwright MCP と違い、ユーザーが事前にログインした状態（X、Gmail 等）を維持したまま Claude がブラウザを操作できる。

## 仕組み

```
Chrome（永続プロファイル + CDP ポート）
  ↑ WebSocket（CDP 直接接続 + asyncio.Lock で排他制御）
MCP サーバー（browser/server.py）
  ↑ stdin/stdout（MCP プロトコル）
Claude Code
```

## セットアップ

メインの [README.md](../README.md) のセクション 9「ブラウザ操作（オプション）」を参照。

`config.json` で `browser_enabled: true` にすると、bot 起動時に以下が自動で立ち上がる。Discord と Slack は**完全に独立した仮想ディスプレイ**で動く:

| プロセス | Discord デフォルト | Slack デフォルト | 備考 |
|---|---|---|---|
| **Xtigervnc** | ディスプレイ `:99` / VNC ポート `5900` | ディスプレイ `:100` / VNC ポート `5901` | ロックファイル `/tmp/.X{N}-lock` が存在すれば起動をスキップ |
| **Chrome** | CDP `9222` / プロファイル `clive-chrome-discord` | CDP `9221` / プロファイル `clive-chrome-slack` | クラッシュ時は自動再起動（指数バックオフ） |
| **noVNC** | ポート `6080` | ポート `6081` | バインド先は `novnc_bind_address` で設定 |

各ポートと表示番号は `config.json` で変更できる:

| キー | 説明 | Discord デフォルト | Slack デフォルト |
|---|---|---|---|
| `browser_cdp_port` | Chrome DevTools Protocol のポート | `9222` | `9221` |
| `browser_novnc_port` | noVNC Web UI のポート | `6080` | `6081` |
| `browser_vnc_port` | Xtigervnc の VNC ポート | `5900` | `5901` |
| `browser_vnc_display` | Xtigervnc の仮想ディスプレイ番号 | `":99"` | `":100"` |

> 複数プラットフォームを同時起動する場合は、すべてのポートとディスプレイ番号をプラットフォームごとに別々の値にすること。

## MCP ツール一覧

Claude が使えるブラウザ操作ツール（23 個）:

### Navigation

| ツール | 説明 |
|---|---|
| `browser_navigate` | URL に遷移 |
| `browser_back` | ブラウザの「戻る」 |
| `browser_reload` | ページ再読み込み |
| `browser_get_url` | 現在の URL を取得 |

### Interaction

| ツール | 説明 |
|---|---|
| `browser_click` | 座標 (x, y) をクリック |
| `browser_double_click` | 座標 (x, y) をダブルクリック |
| `browser_type` | テキスト入力 |
| `browser_clear_field` | フォーカス中の入力欄をクリア |
| `browser_press_key` | キーを押す（Enter, Tab 等） |
| `browser_scroll` | ページをスクロール（up / down） |

### Inspection

| ツール | 説明 |
|---|---|
| `browser_get_content` | ページのテキスト内容を取得 |
| `browser_find_element` | テキストや CSS セレクタで要素を探して座標を返す |
| `browser_evaluate` | JavaScript 実行 |
| `browser_status` | 接続状態・タブ一覧を確認 |

### Tabs

| ツール | 説明 |
|---|---|
| `browser_tabs` | タブ一覧・切り替え |
| `browser_new_tab` | 新しいタブを開く |
| `browser_close_tab` | 現在のタブを閉じる |

### Forms

| ツール | 説明 |
|---|---|
| `browser_select_option` | ドロップダウンの option を選択 |
| `browser_upload_file` | ファイルをアップロード |

### Waiting

| ツール | 説明 |
|---|---|
| `browser_wait` | ページの読み込み完了を待つ |
| `browser_wait_for_element` | CSS セレクタやテキストの要素が表示されるまで待つ |

### Dialogs

| ツール | 説明 |
|---|---|
| `browser_handle_dialog` | ダイアログ（alert, confirm, 「Leave site?」等）を処理 |

## トラブルシューティング

### Chrome に接続できない

```bash
# Discord
curl http://127.0.0.1:9222/json
# Slack
curl http://127.0.0.1:9221/json
```

レスポンスがなければ Chrome が起動していないか、CDP ポートが違う。`config.json` の `browser_cdp_port` を確認する。

### ログインが消えた

プラットフォームごとのプロファイルディレクトリが存在するか確認:

```bash
ls ~/.config/clive-chrome-discord/
ls ~/.config/clive-chrome-slack/
```

ディレクトリがなければ Cookie が保存されていない。Chrome の `--user-data-dir` パスが変わっていないか確認。

### MCP サーバーのテスト

```bash
venv/bin/python -m browser
```

MCP ハンドシェイクが始まれば正常。Ctrl+C で終了。
