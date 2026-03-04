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
) -> str | None:
    """
    Discord API でサーバー全チャンネルのメッセージを取得し、Claude で要約する。
    date_from / date_to: "YYYY-MM-DD" 形式。両方 None なら昨日1日分。
    date_to 省略時は今日まで。
    """
    from core.claude import run_claude

    # ── 日付範囲の決定 ──
    today = datetime.now(JST).date()
    if date_from is None and date_to is None:
        yesterday = today - timedelta(days=1)
        d_from = yesterday
        d_to = yesterday
    else:
        d_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else today - timedelta(days=1)
        d_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else today

    # Discord API 用: JST 00:00 を UTC に変換
    after_dt = datetime(d_from.year, d_from.month, d_from.day, tzinfo=JST) - timedelta(seconds=1)
    before_dt = datetime(d_to.year, d_to.month, d_to.day, tzinfo=JST) + timedelta(days=1)

    # ── guild 特定 ──
    ch = bot.get_channel(channel_id)
    if ch is None or not hasattr(ch, "guild") or ch.guild is None:
        logger.warning("wrapup: guild not found for channel %d", channel_id)
        return None
    guild = ch.guild
    guild_id = guild.id

    # ── 全テキストチャンネル + スレッドからメッセージを収集 ──
    parts: dict[str, list[str]] = {}  # channel_name -> lines
    total_chars = 0
    total_msgs = 0
    truncated = False

    # テキストチャンネルとアクティブスレッドを統合
    channels: list[discord.abc.Messageable] = list(guild.text_channels)
    channels.extend(guild.threads)

    for text_ch in channels:
        if truncated:
            break
        # スレッドの表示名: "親チャンネル > スレッド名"
        if isinstance(text_ch, discord.Thread) and text_ch.parent:
            ch_label = f"{text_ch.parent.name} > {text_ch.name}"
        else:
            ch_label = text_ch.name
        try:
            async for msg in text_ch.history(after=after_dt, before=before_dt, oldest_first=True):
                if msg.author.bot or not msg.content:
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
        summary, timed_out = await run_claude(prompt, "fast")

    if timed_out or not summary:
        return None

    # ── 新パス: memory/wrapup/{guild_id}/YYYY-MM-DD.md に保存 ──
    guild_dir = WRAPUP_DIR / str(guild_id)
    guild_dir.mkdir(parents=True, exist_ok=True)
    wp_file = daily_wrapup_path(guild_id, d_from)
    wp_file.write_text(f"# {date_label}\n\n{summary}\n", encoding="utf-8")

    return summary
