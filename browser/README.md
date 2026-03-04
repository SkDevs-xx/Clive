# disclaude Browser

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

`config.json` で `browser_enabled: true` にすると、bot 起動時に以下が自動で立ち上がる:

| プロセス | 役割 | 備考 |
|---|---|---|
| **Xtigervnc** | 仮想ディスプレイ `:99` + VNC サーバー（ポート 5900） | GUI 環境では起動しない |
| **Chrome** | CDP ポート 9222 で待機 | クラッシュ時は自動再起動（指数バックオフ） |
| **noVNC** | Web VNC クライアント（ポート 6080） | バインド先は `novnc_bind_address` で設定 |

> GUI 環境（Windows / Linux デスクトップ）では `DISPLAY` 環境変数が既にあるため、Xtigervnc と noVNC の起動はスキップされる。

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
| `browser_screenshot` | スクリーンショット（base64 JPEG、quality 指定可） |
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
curl http://127.0.0.1:9222/json
```

レスポンスがなければ Chrome が起動していないか、ポートが違う。

### ログインが消えた

`~/.config/disclaude-chrome/` が存在するか確認。Chrome の `--user-data-dir` パスが変わっていないか確認。

### MCP サーバーのテスト

```bash
venv/bin/python -m browser
```

MCP ハンドシェイクが始まれば正常。Ctrl+C で終了。
