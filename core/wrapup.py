"""
ラップアップ・メモリ圧縮
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import discord

from core.config import MEMORY_DIR

JST = ZoneInfo("Asia/Tokyo")
logger = logging.getLogger("discord_bot")

WRAPUP_DIR = MEMORY_DIR / "wrapup"


def daily_wrapup_path(guild_id: int, target_date) -> Path:
    """新パス: memory/wrapup/{guild_id}/YYYY-MM-DD.md"""
    return WRAPUP_DIR / str(guild_id) / f"{target_date.strftime('%Y-%m-%d')}.md"


WRAPUP_CHAR_CAP = 800_000  # Discord 収集フェーズの文字数上限


async def run_wrapup(
    bot, channel_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    wrapup_time: str = "00:00",
) -> str | None:
    """
    Discord API でサーバー全テキストチャンネルのメッセージを取得し、Claude で要約する。
    date_from / date_to: "YYYY-MM-DD" 形式。両方 None なら前回 wrapup_time から今回 wrapup_time まで。
    wrapup_time: "HH:MM" 形式。集計の区切り時刻。
    """
    from core.claude import run_claude

    # ── wrapup_time のパース ──
    wt_h, wt_m = (int(x) for x in wrapup_time.split(":"))

    # ── 日付範囲の決定 ──
    now = datetime.now(JST)
    if date_from is None and date_to is None:
        # 前日の wrapup_time 〜 本日の wrapup_time
        end_dt = now.replace(hour=wt_h, minute=wt_m, second=0, microsecond=0)
        start_dt = end_dt - timedelta(days=1)
        d_from = start_dt.date()
        d_to = end_dt.date()
    else:
        today = now.date()
        d_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today - timedelta(days=1)
        d_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today
        start_dt = datetime(d_from.year, d_from.month, d_from.day, wt_h, wt_m, tzinfo=JST)
        end_dt = datetime(d_to.year, d_to.month, d_to.day, wt_h, wt_m, tzinfo=JST)

    # Discord API 用（after は排他なので1秒引く）
    after_dt = start_dt - timedelta(seconds=1)
    before_dt = end_dt

    # ── guild 特定 ──
    ch = bot.get_channel(channel_id)
    if ch is None or not hasattr(ch, "guild") or ch.guild is None:
        logger.warning("wrapup: guild not found for channel %d", channel_id)
        return None
    guild = ch.guild
    guild_id = guild.id

    # ── 全テキストチャンネルからメッセージを収集 ──
    parts: dict[str, list[str]] = {}  # channel_name -> lines
    total_chars = 0
    total_msgs = 0
    truncated = False

    for text_ch in guild.text_channels:
        if truncated:
            break
        ch_label = text_ch.name
        try:
            async for msg in text_ch.history(after=after_dt, before=before_dt, oldest_first=True):
                if not msg.content:
                    continue
                ts = msg.created_at.astimezone(JST).strftime("%Y-%m-%d %H:%M")
                line = f"[{ts}] {msg.author.display_name}: {msg.content}"
                total_chars += len(line) + 1
                total_msgs += 1
                parts.setdefault(ch_label, []).append(line)
                if total_chars >= WRAPUP_CHAR_CAP:
                    truncated = True
                    break
        except discord.Forbidden:
            logger.debug("wrapup: no permission for #%s (%d)", text_ch.name, text_ch.id)
        except Exception as e:
            logger.warning("wrapup: error fetching #%s: %s", text_ch.name, e)

    if not parts:
        return None

    # ── チャンネル別にテキストを組み立て ──
    history_lines = []
    for ch_name, lines in parts.items():
        history_lines.append(f"### #{ch_name}")
        history_lines.extend(lines)
        history_lines.append("")
    history_text = "\n".join(history_lines)

    # ── 期間ラベル ──
    date_label = d_from.strftime("%Y-%m-%d")
    if d_from != d_to:
        date_label += f" 〜 {d_to.strftime('%Y-%m-%d')}"

    logger.info("wrapup: guild=%d period=%s msgs=%d chars=%d truncated=%s",
                guild_id, date_label, total_msgs, total_chars, truncated)

    # ── Claude に要約を依頼 ──
    prompt = (
        f"{date_label} のサーバー「{guild.name}」全チャンネルの会話ログ（{total_msgs}件）です。\n"
        "この期間に話したこと・決めたこと・進んだこと・残ったタスクをチャンネルをまたいで簡潔にまとめてください。\n\n"
        "【出力形式の注意】Discord に直接表示するため、以下のルールに従ってください：\n"
        "- 見出しは # / ## / ### を使用する\n"
        "- テーブル（| 区切り）は使わず、箇条書き（- ）で代替する\n"
        "- 水平線（--- や ***）は使わない\n"
        "- コードは ``` で囲む\n\n"
        + history_text
    )

    async with bot.get_channel_lock(channel_id):
        summary, timed_out = await run_claude(prompt)

    if timed_out or not summary or summary.startswith("エラーが発生しました"):
        return None

    # ── 新パス: memory/wrapup/{guild_id}/YYYY-MM-DD.md に保存 ──
    guild_dir = WRAPUP_DIR / str(guild_id)
    guild_dir.mkdir(parents=True, exist_ok=True)
    wp_file = daily_wrapup_path(guild_id, d_from)
    wp_file.write_text(f"# {date_label}\n\n{summary}\n", encoding="utf-8")

    return summary
