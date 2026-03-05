# disclaude

Discord × Claude Code CLI で動く自律型 AI ボット。

メンションするだけで Claude と対話でき、スケジュール実行・チャンネル要約・Heartbeat 自律巡回・ブラウザ操作まで、Claude の能力を Discord 上でフルに活用できる。マルチプラットフォーム対応設計により、将来的に Slack や Notion への展開も可能。

## できること

| 機能 | 概要 |
|------|------|
| **会話** | ボットをメンションするだけで Claude と対話。チャンネルごとにセッションを保持 |
| **マルチモーダル** | テキスト・画像（PNG/JPG/WEBP/GIF）・PDF を添付すると自動で読み取る |
| **スケジュール実行** | cron 式で定期的にプロンプトを実行（日次レポート、定時チェック等） |
| **チャンネル要約** | 大量メッセージを 2 段階フィルタリングで要約 |
| **Heartbeat** | 定期巡回でチェックリストを評価し、日次 Wrap-up を自動生成 |
| **ブラウザ操作** | Chrome を遠隔操作。ログイン済みの X / Gmail 等をそのまま使える |
| **記憶システム** | ファイルベースの永続記憶（人格・ユーザー情報・調査キュー・知識アーカイブ） |
| **自律調査 & レビュー** | 気になったトピックを自分で調査し、知識をカテゴリ別に蓄積。ユーザーがレビュー・フィードバックすることで知識の質を育てられる |
| **スキルシステム** | SKILL.md 形式でスキルを定義。プラットフォームごとにスキルの有効/無効を制御できる |

## 必要なもの

- **Git** -- `git --version` で確認。なければ `sudo apt install git`
- **Python 3.12 以上** -- `python3 --version` で確認
- **Claude Code CLI** -- セットアップ手順内でインストールする
- **Discord Bot Token** -- [Discord Developer Portal](https://discord.com/developers/applications) で Bot を作成して取得

## セットアップ

> 以下の手順は Ubuntu / Debian 系 Linux を想定しています。
> 全て root ユーザーで実行してください（`sudo su -` で root になる）。

### 1. 専用ユーザーの作成

ボット専用のユーザーを作る。Claude は `--dangerously-skip-permissions` で動くため、**万が一暴走しても被害を限定する**ためのセキュリティ対策。

disclaude ユーザーを作成（パスワードなし = パスワードログイン不可）:

```bash
sudo adduser --disabled-password --gecos "disclaude bot" disclaude
```

> パスワードなしでも root から `sudo su - disclaude` で切り替えられる。

### 2. disclaude ユーザーで環境構築

disclaude ユーザーに切り替えてホーム直下にクローン:

```bash
sudo su - disclaude
git clone https://github.com/SkDevs-xx/disclaude.git
cp -r disclaude/. /home/disclaude/
rm -rf /home/disclaude/disclaude/
```

Python 仮想環境を作成して依存パッケージをインストール:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
exit
```

### 3. Claude Code CLI のインストール

自分の PC に Claude Code があっても、サーバーの disclaude ユーザーには別途インストールが必要。disclaude ユーザーで実行:

```bash
curl -fsSL https://claude.ai/install.sh | sh
claude
```

> PATH の警告が出たら: `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc`

> `claude` を実行するとブラウザが開く。VPS の場合は表示される URL を手元の PC で開く。

### 4. Discord Bot Token の設定

`.env` を編集して取得した Bot Token を貼り付ける:

```bash
vi .env
```

```
DISCORD_BOT_TOKEN=ここにあなたのBotTokenを貼る
```

### 5. 設定ファイルの編集

#### config.json

`config.json` を編集する。最低限 `discord.allowed_user_ids` だけ設定すれば動く:

```json
{
  "novnc_bind_address": "localhost",
  "discord": {
    "enabled": true,
    "model": "sonnet",
    "thinking": false,
    "skip_permissions": true,
    "browser_enabled": false,
    "browser_cdp_port": 9222,
    "allowed_user_ids": ["あなたのDiscordユーザーID"],
    "heartbeat_enabled": false,
    "heartbeat_channel_id": "",
    "heartbeat_interval_minutes": 60,
    "no_mention_channels": []
  }
}
```

| キー | 説明 | デフォルト |
|------|------|-----------|
| `discord.enabled` | Discord Bot を起動するか | `false` |
| `discord.model` | Claude のモデル名（`sonnet` / `opus` / `haiku`） | `sonnet` |
| `discord.thinking` | 思考モードの有効化 | `false` |
| `discord.skip_permissions` | Claude CLI の権限確認をスキップ | `true` |
| `discord.browser_enabled` | ブラウザ操作機能の有効化（後述） | `false` |
| `discord.browser_cdp_port` | Chrome DevTools Protocol のポート | `9222` |
| `discord.allowed_user_ids` | ボットに話しかけられるユーザーの Discord ID（配列） | なし（必須） |
| `discord.heartbeat_enabled` | Heartbeat 自律巡回の有効化 | `false` |
| `discord.heartbeat_channel_id` | Heartbeat 通知を送るチャンネル ID | なし |
| `discord.heartbeat_interval_minutes` | Heartbeat の実行間隔（分） | `60` |
| `discord.no_mention_channels` | メンション不要で反応するチャンネル ID（配列） | `[]` |
| `novnc_bind_address` | noVNC のバインド先 IP（後述） | `localhost` |

> Discord ユーザー ID の調べ方: Discord の設定 → 詳細設定 → 開発者モードを ON → 自分のアイコンを右クリック → 「ユーザー ID をコピー」

#### .mcp.json の編集

`/home/disclaude` の部分を **自分の環境の絶対パス** に置き換える（home に配置していればスキップ）:

```json
{
  "mcpServers": {
    "disclaude-browser": {
      "command": "/home/disclaude/venv/bin/python",
      "args": ["-m", "browser"],
      "cwd": "/home/disclaude"
    }
  }
}
```

> 相対パスは使えません。必ず `/home/` から始まる絶対パスを指定してください。

### 6. 動作確認

ここまでで基本機能は使える。disclaude ユーザーのまま手動で起動して確認する:

```bash
source venv/bin/activate
python3 main.py
```

Discord でボットにメンションして返答が来れば OK。`Ctrl+C` で停止し、`exit` で root に戻る。

### 7. systemd でデーモン化（本番運用）

root ユーザーで実行する:

サービスファイルをコピー:

```bash
sudo cp /home/disclaude/disclaude.service /etc/systemd/system/
```

systemd に認識させて起動:

```bash
sudo systemctl daemon-reload
sudo systemctl enable disclaude
sudo systemctl start disclaude
```

> `enable` = OS 起動時に自動スタート、`start` = 今すぐ起動。

#### セキュリティ -- systemd サンドボックス

サービスファイルには以下のサンドボックス設定が含まれている:

| 設定 | 効果 |
|------|------|
| `ProtectSystem=strict` | `/usr`, `/etc` 等のシステムファイルへの書き込みを禁止 |
| `ReadWritePaths=/home/disclaude` | disclaude の home だけ書き込み許可 |
| `PrivateTmp=true` | `/tmp` を他プロセスと分離（覗き見できない） |
| `NoNewPrivileges=true` | 権限昇格（sudo 等）を禁止 |
| `ProtectHome=false` | `ProtectSystem=strict` + `ReadWritePaths` で十分なため無効化 |

これにより、Claude が `--dangerously-skip-permissions` で自由にコマンドを実行しても:

- `/home/disclaude` の外に書き込めない
- 他ユーザーのファイルが見えない
- root 権限を取得できない

設定変更後の再起動:

```bash
sudo systemctl restart disclaude
```

ログの確認:

リアルタイムでログを表示:

```bash
journalctl -u disclaude -f
```

直近 1 時間のログを確認:

```bash
journalctl -u disclaude --since "1 hour ago"
```

### 8. ブラウザ操作（オプション）

Claude に X への投稿や Gmail の確認など、**ログイン済みの Web サービスをブラウザ経由で操作** させたい場合に設定する。

#### 環境別の違い

環境によって必要なセットアップが異なる:

| 環境 | Chrome | 仮想ディスプレイ | VNC / noVNC | 初回ログイン方法 |
|------|--------|-----------------|-------------|-----------------|
| **Windows（GUI あり）** | インストール済みでOK | 不要 | 不要 | Chrome が画面に表示されるので直接ログイン |
| **Linux デスクトップ（GUI あり）** | 要インストール | 不要（DISPLAY が既にある） | 不要 | Chrome が画面に表示されるので直接ログイン |
| **Linux VPS（GUI なし）** | 要インストール | 要（Xtigervnc） | 要（noVNC で遠隔ログイン） | ブラウザから noVNC 経由でログイン |

> `manager.py` は `DISPLAY` 環境変数を自動で検知する。GUI 環境では仮想ディスプレイの起動をスキップし、Chrome だけを立ち上げる。

#### GUI 環境（Windows / Linux デスクトップ）の場合

セットアップはシンプル:

1. Chrome がインストールされていることを確認
2. `config.json` の `discord.browser_enabled` を `true` に変更
3. bot を起動すると Chrome ウインドウが開く
4. 開いた Chrome で X や Gmail にログインする（初回のみ）
5. ログイン後、Chrome はそのまま裏で動き続ける

> Windows の場合、systemd は使えないので `python3 main.py` で直接実行するか、タスクスケジューラで自動起動を設定する。

> Linux デスクトップの場合、日本語フォントがない環境では `sudo apt install fonts-noto-cjk` が必要。

以下の VPS 向け手順は読み飛ばして OK。

---

#### VPS（GUI なし）の場合

VPS にはモニターがないので、Chrome を動かすには「仮想ディスプレイ」が必要。bot が以下を自動で立ち上げる:

| プロセス | 何をするか |
|---|---|
| **Xtigervnc** | モニターの代わりになる仮想ディスプレイ + VNC サーバー |
| **Chrome** | Claude が操作するブラウザ |
| **noVNC** | ブラウザから VNC に接続できる Web 画面（初回ログイン用） |

#### Step 1: 必要パッケージのインストール（root で実行）

```bash
sudo apt install tigervnc-standalone-server novnc google-chrome-stable fonts-noto-cjk
```

各パッケージの役割:

| パッケージ | なぜ必要か |
|---|---|
| `tigervnc-standalone-server` | 仮想ディスプレイ + VNC サーバー（Chrome を動かすために必須） |
| `novnc` | PC のブラウザから VNC に接続する Web クライアント |
| `google-chrome-stable` | Claude が操作するブラウザ本体 |
| `fonts-noto-cjk` | 日本語フォント（ないと Chrome で文字が全部 □ になる） |

#### Step 2: VNC パスワードの設定（disclaude ユーザーで実行）

```bash
sudo su - disclaude
vncpasswd
```

パスワードを入力 → 確認入力 → "Would you like to enter a view-only password?" には `n` と答える。`exit` で root に戻る。

#### Step 3: config.json を編集

`discord.browser_enabled` を `true` に、`novnc_bind_address` をサーバーの IP に変更する:

```json
{
  "novnc_bind_address": "disclaudeサーバーのIPアドレス",
  "discord": {
    "browser_enabled": true,
    "browser_cdp_port": 9222
  }
}
```

| 設定 | 説明 |
|---|---|
| `discord.browser_enabled` | `true` にする |
| `discord.browser_cdp_port` | そのまま `9222` でOK |
| `novnc_bind_address` | noVNC にアクセスするための IP アドレス（下記参照） |

> **複数プラットフォームを同時起動する場合:** `browser_cdp_port` はプラットフォームごとに別々のポートを割り当てること（例: discord=`9222`、slack=`9221`、notion=`9220`）。同じポートを使うと起動時に競合してブラウザが立ち上がらない。

**`novnc_bind_address` に何を入れるか:**

| 環境 | 値 | 理由 |
|------|---|------|
| Tailscale 経由でアクセス | Tailscale の IP（例: `100.x.x.x`） | VPN 内からのみアクセス可能 |
| SSH トンネル経由でアクセス | `localhost` | ローカルからのみアクセス可能 |
| どこからでもアクセス（非推奨） | `0.0.0.0` | VNC パスワードだけで誰でも入れてしまう |

#### Step 4: デーモンを再起動

```bash
sudo systemctl restart disclaude
```

ログで起動を確認:

```bash
journalctl -u disclaude -f
```

以下のようなログが出れば成功:

```
Xtigervnc started on :99, VNC port 5900
Chrome started with CDP port 9222
Chrome CDP ready on port 9222
noVNC started on port 6080
```

#### Step 5: 初回ログイン（1回だけ）

X や Gmail など、Claude に使わせたいサービスにブラウザから手動でログインする。**ログイン情報（Cookie）はサーバーに保存されるので、これは 1 回だけやれば OK。**

1. PC のブラウザで `http://<novnc_bind_addressのIP>:6080/vnc.html` にアクセス
   - 例: Tailscale の場合 `http://100.x.x.x:6080/vnc.html`
2. Step 2 で設定した VNC パスワードを入力
3. Chrome の画面が見える。アドレスバーに URL を入力して X や Gmail にログインする
4. ログインが終わったら VNC 画面のタブを閉じる（Chrome はサーバー上で動き続ける）

> Cookie は `~/.config/disclaude-chrome/` に保存される。Chrome をアップデートしてもログインは維持される。

> Chrome がクラッシュしても自動で再起動する（指数バックオフ: 5秒 → 10秒 → ... → 最大5分）。

SSH トンネル経由でアクセスする場合（`novnc_bind_address` が `localhost` のとき）:

手元の PC からポートフォワード:

```bash
ssh -L 6080:localhost:6080 disclaude@your-server
```

→ `http://localhost:6080/vnc.html` でアクセスできる。

詳細は [browser/README.md](browser/README.md) を参照。

## コマンド一覧

> Discord プラットフォーム限定のコマンドです。
>> SlackやNotion用のコマンドは順次対応予定。

### 基本操作

| コマンド | 説明 |
|----------|------|
| `@bot メッセージ` | Claude と会話（画像・PDF の添付も可） |
| `/model` | モデル（Sonnet / Opus / Haiku）と Thinking ON/OFF を設定 |
| `/status` | 現在のモデル・Thinking・実行中タスクの確認 |
| `/cancel` | 現在のチャンネルで実行中の Claude プロセスを中止 |
| `/mention` | このチャンネルでのメンション要否を設定（OFF にするとメンションなしで反応） |

### スケジュール

| コマンド | 説明 |
|----------|------|
| `/schedule add` | 定期実行タスクの追加（UI フォーム） |
| `/schedule list` | 登録済みスケジュールの一覧・編集・一時停止・削除 |

### 分析

| コマンド | 説明 |
|----------|------|
| `/summarize [prompt]` | チャンネルの会話を Claude に質問・要約（カスタムプロンプト対応） |

### Heartbeat

| コマンド | 説明 |
|----------|------|
| `/heartbeat` | Heartbeat のステータス表示・設定変更・手動実行 |

### レビュー

| コマンド | 説明 |
|----------|------|
| `/review` | 調査済みトピックのレビュー・フィードバック |

## 仕組み

Claude Code CLI をサブプロセスとして実行し、Discord メッセージやスケジュールに応じてプロンプトを渡す。API キーは不要で、Claude Code の月額サブスクリプションで動作する。

- チャンネルごとに非同期ロックで排他制御
- セッション ID でマルチターン会話を維持
- 2000 文字制限は Markdown 構造を保ったまま自動分割
- タイムアウト: fast モード 180 秒 / planning モード 300 秒
- スキルエンジンが SKILL.md を読み込み、プラットフォームに応じた指示を Claude に注入

## プロジェクト構成

```
disclaude/
├── main.py                          # エントリポイント（config.json の enabled で起動）
├── config.json                      # 全設定（グローバル + プラットフォーム別）
├── .env                             # Bot Token テンプレート
├── .mcp.json                        # MCP サーバー登録
│
├── core/                            # プラットフォーム非依存
│   ├── claude.py                    # Claude CLI ラッパー（スキル注入対応）
│   ├── config.py                    # 設定管理（init_workspace で動的パス切替）
│   ├── message.py                   # split_message 等テキストユーティリティ
│   ├── memory.py                    # HEARTBEAT.md / REVIEW.md パース・書き込み
│   ├── wrapup.py                    # 日次 Wrap-up ロジック
│   ├── scheduler.py                 # cron ユーティリティ
│   ├── attachments.py               # 添付ファイル処理
│   └── skills/                      # スキルエンジン
│       ├── models.py                # Skill dataclass
│       ├── loader.py                # SKILL.md パーサー（YAML frontmatter）
│       └── registry.py              # スキル登録・検索・マッチング
│
├── skills/                          # スキル定義（SKILL.md を置く場所）
│   ├── review/SKILL.md
│   └── heartbeat/SKILL.md
│
├── platforms/                       # プラットフォーム固有
│   ├── base.py                      # PlatformAdapter ABC + PlatformContext
│   └── discord/
│       ├── __init__.py              # DISCORD_FORMAT_HINT 定数
│       ├── bot.py                   # ClaudeBot 本体
│       ├── embeds.py                # Discord Embed 生成
│       ├── utils.py                 # get_guild_channels, make_discord_collector
│       ├── cogs/
│       │   ├── utility.py           # /model, /status, /cancel, /mention
│       │   ├── schedule.py          # スケジュール管理
│       │   ├── summarize.py         # チャンネル要約
│       │   ├── heartbeat.py         # 自律巡回エージェント
│       │   └── review.py            # 調査トピックレビュー
│       └── workspace/               # Discord 専用ワークスペース
│           ├── SOUL.md              # AI の人格・価値観
│           ├── USER.md              # ユーザー情報
│           ├── CURIOSITY.md         # 未調査キュー
│           ├── REVIEW.md            # レビュー待ちトピック
│           ├── HEARTBEAT.md         # 巡回チェックリスト
│           ├── EMOTION.md           # 感情バロメーター
│           ├── sessions.json        # チャンネル別セッション ID
│           ├── channel_names.json   # チャンネル名キャッシュ
│           ├── schedules/           # 登録済みスケジュール定義
│           ├── temp/                # 一時ファイル
│           └── memory/
│               ├── curiosity/       # 調査済み知識アーカイブ
│               │   ├── self/        #   自己探求
│               │   ├── tech/        #   技術
│               │   └── business/    #   ビジネス
│               └── wrapup/          # 日次 Wrap-up ログ
│
└── browser/                         # ブラウザ操作
    ├── server.py                    # ブラウザ MCP サーバー
    ├── cdp.py                       # Chrome DevTools Protocol クライアント
    ├── tools.py                     # MCP ツール定義
    └── manager.py                   # Xtigervnc + Chrome + noVNC プロセス管理
```

## マルチプラットフォーム

プラットフォームごとに独立したワークスペース（人格・記憶・設定）を持つ設計。`config.json` の `enabled` フラグで起動するプラットフォームを制御する:

```json
{
  "discord": { "enabled": true, ... },
  "slack":   { "enabled": false, ... }
}
```

新しいプラットフォーム用ワークスペースを初期化:

```bash
source venv/bin/activate
python3 main.py --init-workspace slack --from discord
deactive
```

コピー後に `platforms/slack/workspace/SOUL.md` を編集してプラットフォームに合った人格に調整する。

## スキルシステム

`skills/` ディレクトリに SKILL.md を配置することで、Claude への指示を拡張できる:

```yaml
---
name: review
description: 調査済みトピックのレビューと報告
platforms: [discord, slack]
user-invocable: true
---

# Instructions
ここにLLMへの指示を書く。
```

- `platforms` を省略すると全プラットフォームで有効
- `user-invocable: true` でユーザーが直接呼び出せるスキルとして登録
- スキルの instructions は Claude 呼び出し時にプロンプトの先頭に自動注入される

## アンインストール

disclaude を完全に削除する手順。root ユーザーで実行する。

### 1. サービスの停止・削除

```bash
sudo systemctl stop disclaude
sudo systemctl disable disclaude
sudo rm /etc/systemd/system/disclaude.service
sudo systemctl daemon-reload
```

### 2. disclaude ユーザーとホームディレクトリの削除

ホームディレクトリごと削除（config.json, .env, workspace/ 等すべて消える）:

```bash
sudo userdel -r disclaude
```

> ユーザーだけ消してデータを残したい場合は `-r` を外す。`/home/disclaude/` は手動で削除できる。

### 3. Chrome プロファイルの削除

ブラウザ操作を使っていた場合、Cookie やログイン情報が残っている:

```bash
sudo rm -rf /home/disclaude/.config/disclaude-chrome
```

> Step 2 で `-r` を付けて削除済みなら不要。

### 4. VPS 向けパッケージの削除（任意）

ブラウザ操作用にインストールしたパッケージが不要なら:

```bash
sudo apt remove --purge tigervnc-standalone-server novnc google-chrome-stable
sudo apt autoremove
```

> `fonts-noto-cjk` は他のアプリでも使われるため残しておいてよい。

## ライセンス

MIT - SkDevs-xx 2026
