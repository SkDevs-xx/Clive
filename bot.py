"""
Discord × Claude Code Bot
"""

import asyncio
import logging
import os
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.config import (
    BASE_DIR, LOG_FILE,
    WORKFLOW_DIR, MEMORY_DIR, ATTACHMENTS_DIR, TMP_DIR,
    load_config, load_schedules, save_schedules, save_channel_name,
    get_channel_session, save_channel_session,
)
from core.claude import run_claude
from core.embeds import make_error_embed, make_info_embed, split_message
from core.attachments import process_attachment
from browser.manager import BrowserManager

# ─────────────────────────────────────────────
# ログ設定
# ─────────────────────────────────────────────
logger = logging.getLogger("discord_bot")
logger.setLevel(logging.INFO)
_fh = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
_sh = logging.StreamHandler()
_sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_fh)
logger.addHandler(_sh)


# ─────────────────────────────────────────────
# ボット本体
# ─────────────────────────────────────────────
class ClaudeBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.channel_locks: dict[int, asyncio.Lock] = {}
        self.running_tasks: dict[int, asyncio.Task] = {}  # channel_id -> Task
        self.running_processes: dict[int, asyncio.subprocess.Process] = {}  # channel_id -> Claude Process
        self.scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
        self.browser_manager: BrowserManager | None = None

    def get_channel_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self.channel_locks:
            self.channel_locks[channel_id] = asyncio.Lock()
        return self.channel_locks[channel_id]

    async def setup_hook(self):
        for ext in [
            "cogs.utility",
            "cogs.schedule",
            "cogs.summarize",
            "cogs.heartbeat",
            "cogs.review",
        ]:
            await self.load_extension(ext)
        await self.tree.sync()
        logger.info("Slash commands synced")

        self._reload_schedules()
        self.scheduler.start()

        cfg = load_config()
        if cfg.get("browser_enabled", False):
            port = cfg.get("browser_cdp_port", 9222)
            novnc_bind = cfg.get("novnc_bind_address", "localhost")
            self.browser_manager = BrowserManager(cdp_port=port, novnc_bind=novnc_bind)
            await self.browser_manager.start()

    def _reload_schedules(self):
        """schedules.json を読み込んでスケジューラに登録"""
        for job in self.scheduler.get_jobs():
            if job.id.startswith("sched_"):
                job.remove()

        for s in load_schedules():
            if s.get("status") != "active":
                continue
            try:
                trigger = CronTrigger.from_crontab(s["cron"])
                self.scheduler.add_job(
                    self._run_schedule,
                    trigger,
                    id=f"sched_{s['id']}",
                    args=[s],
                    replace_existing=True,
                )
            except Exception as e:
                logger.error("Schedule load error (%s): %s", s.get("id"), e)

    async def _run_schedule(self, s: dict):
        channel_id = int(s["channel_id"])
        channel = self.get_channel(channel_id)
        if not channel:
            logger.warning("Schedule channel not found: %d", channel_id)
            return

        try:
            if s.get("type") == "wrapup":
                from core.wrapup import run_wrapup
                summary = await run_wrapup(self, channel_id)
                if summary is None:
                    await channel.send(embed=make_info_embed("ラップアップ", "該当する会話履歴がありませんでした。"))
                else:
                    for chunk in split_message(re.sub(r'\n{2,}', '\n', summary), max_len=2000):
                        await channel.send(content=chunk)
            else:
                # 後方互換: 旧 "mode" キーを model+thinking に変換
                sched_model = s.get("model", "sonnet")
                sched_thinking = s.get("thinking", s.get("mode") == "planning")
                async with self.get_channel_lock(channel_id):
                    response, timed_out = await run_claude(s["prompt"], model=sched_model, thinking=sched_thinking)

                if timed_out:
                    await channel.send(embed=make_error_embed("スケジュールタスクがタイムアウトしました。"))
                else:
                    for chunk in split_message(re.sub(r'\n{2,}', '\n', response), max_len=2000):
                        await channel.send(content=chunk)
        except Exception as e:
            logger.exception("Schedule execution error (%s / %s): %s", s.get("id"), s.get("name"), e)
        finally:
            # run_count / last_run は成功・失敗に関わらず更新
            schedules = load_schedules()
            for item in schedules:
                if item["id"] == s["id"]:
                    item["run_count"] = item.get("run_count", 0) + 1
                    item["last_run"] = datetime.now(timezone.utc).isoformat()
            save_schedules(schedules)

    async def close(self):
        if self.browser_manager:
            await self.browser_manager.stop()
        await super().close()

    async def on_ready(self):
        logger.info("Bot ready: %s (ID: %s)", self.user, self.user.id)
        for guild in self.guilds:
            for channel in guild.channels:
                if isinstance(channel, (discord.TextChannel, discord.Thread, discord.ForumChannel)):
                    save_channel_name(channel.id, channel.name)
            # ギルドコマンドの重複をクリア（グローバルのみに統一）
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Cleared guild commands for: %s", guild.name)
        logger.info("Channel names cached: %d channels", sum(len(g.channels) for g in self.guilds))

    async def on_message(self, message: discord.Message):
        logger.info(
            "[on_message] author=%s (id=%s, bot=%s) channel=%s(%s) content_len=%d",
            message.author,
            message.author.id,
            message.author.bot,
            message.channel,
            type(message.channel).__name__,
            len(message.content or ""),
        )

        if message.author.bot:
            return

        await self.process_commands(message)

        if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
            logger.info("[on_message] skipped: channel type %s", type(message.channel).__name__)
            return

        cfg = load_config()
        no_mention = set(cfg.get("no_mention_channels", []))
        if self.user not in message.mentions and str(message.channel.id) not in no_mention:
            return

        allowed = cfg.get("allowed_user_ids", [])
        if str(message.author.id) not in allowed:
            logger.info("[on_message] skipped: user %s not in allowlist %s", message.author.id, allowed)
            return

        channel_id = message.channel.id
        save_channel_name(channel_id, message.channel.name)

        content_raw = message.content or ""
        if self.user:
            content_raw = re.sub(rf"<@!?{self.user.id}>", "", content_raw)
        user_content = content_raw.strip()

        if not user_content and not message.attachments:
            logger.warning(
                "Empty message from %s in ch %d — "
                "Discord Developer Portal で 'Message Content Intent' が有効か確認してください。",
                message.author,
                channel_id,
            )
            return

        injected_text = ""
        image_paths: list[Path] = []
        for att in message.attachments:
            text_part, image_path = await process_attachment(att)
            if text_part:
                injected_text += text_part
            if image_path is not None:
                image_paths.append(image_path)

        if not user_content and not injected_text:
            return

        full_prompt = user_content + injected_text

        try:
            async with message.channel.typing():
                async with self.get_channel_lock(channel_id):
                    session_id = get_channel_session(channel_id)
                    is_new = session_id is None
                    if is_new:
                        session_id = str(uuid.uuid4())
                        save_channel_session(channel_id, session_id)

                    task = asyncio.current_task()
                    self.running_tasks[channel_id] = task

                    model = cfg.get("model", "sonnet")
                    thinking = cfg.get("thinking", False)
                    response, timed_out = await run_claude(
                        full_prompt, model=model, thinking=thinking,
                        session_id=session_id,
                        is_new_session=is_new,
                        on_process=lambda p: self.running_processes.__setitem__(channel_id, p),
                    )

                    self.running_tasks.pop(channel_id, None)
                    self.running_processes.pop(channel_id, None)

            if timed_out:
                await message.reply(embed=make_error_embed(
                    "タイムアウトしました。`/cancel` で再試行するか、少し待ってから再送してください。"
                ))
                return

            # Discord 表示用: 連続改行を単一改行に正規化
            display_response = re.sub(r'\n{2,}', '\n', response)
            chunks = split_message(display_response, max_len=2000)
            await message.reply(chunks[0])
            for chunk in chunks[1:]:
                await message.channel.send(chunk)
        finally:
            # workspace/temp/ の画像ファイルをクリーンアップ
            for p in image_paths:
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    logger.warning("画像クリーンアップ失敗: %s", p)

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        logger.exception("App command error: %s", error)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                embed=make_error_embed(f"コマンドエラー: {error}"), ephemeral=True
            )


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────
def main():
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token or token == "your_token_here":
        logger.error(".env に DISCORD_BOT_TOKEN が設定されていません。")
        return

    for d in [WORKFLOW_DIR, MEMORY_DIR, ATTACHMENTS_DIR, TMP_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    bot = ClaudeBot()
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
