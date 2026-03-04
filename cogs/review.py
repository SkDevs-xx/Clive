"""
ReviewCog: /review — 調査済みトピックのフィードバックレビュー
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.config import (
    WORKFLOW_DIR,
    get_channel_session,
    save_channel_session,
)
from core.claude import run_claude
from core.embeds import make_info_embed, make_error_embed, split_message

REVIEW_FILE = WORKFLOW_DIR / "REVIEW.md"
CURIOSITY_DIR = WORKFLOW_DIR / "memory" / "curiosity"
MAX_REVIEW_ITEMS = 3
_ARCHIVE_PATH_RE = re.compile(r"`(memory/curiosity/[\w./-]+\.md)`")


def _resolve_archive(relative: str) -> Path | None:
    """REVIEW.md 記載の相対パスを実ファイルに解決する。"""
    full = WORKFLOW_DIR / relative
    if full.exists():
        return full
    # フォールバック: サブディレクトリを順に探す
    fname = full.name
    for sub in ("self", "tech", "business"):
        candidate = CURIOSITY_DIR / sub / fname
        if candidate.exists():
            return candidate
    return None


def _parse_pending_reviews(text: str) -> list[dict]:
    """REVIEW.md から未レビュー（[ ]）行を解析する。"""
    items: list[dict] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- [ ]"):
            continue
        # トピック名: "- [ ] " の後からアーカイブパス参照の前まで
        topic_part = stripped.removeprefix("- [ ]").strip()
        # " → `memory/..." の手前で切る
        topic = re.split(r"\s*→\s*`", topic_part)[0].strip()
        # アーカイブパス
        path_m = _ARCHIVE_PATH_RE.search(stripped)
        archive_rel = path_m.group(1) if path_m else None
        items.append({"topic": topic, "archive_rel": archive_rel, "line": stripped})
    return items


class ReviewCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="review", description="調査済みトピックをレビューする")
    async def review_command(self, interaction: discord.Interaction):
        if not REVIEW_FILE.exists():
            await interaction.response.send_message(
                embed=make_info_embed("レビュー", "REVIEW.md が見つかりません。"),
                ephemeral=True,
            )
            return

        text = REVIEW_FILE.read_text(encoding="utf-8")
        items = _parse_pending_reviews(text)

        if not items:
            await interaction.response.send_message(
                embed=make_info_embed("レビュー", "レビュー待ちの項目はないよ。"),
                ephemeral=True,
            )
            return

        selected = items[:MAX_REVIEW_ITEMS]

        # アーカイブ内容を読み込む
        sections: list[str] = []
        for i, item in enumerate(selected, 1):
            header = f"## {i}. {item['topic']}"
            content = ""
            if item["archive_rel"]:
                path = _resolve_archive(item["archive_rel"])
                if path:
                    content = path.read_text(encoding="utf-8")
                else:
                    content = "（アーカイブファイルが見つかりませんでした）"
            else:
                content = "（アーカイブパスが記載されていません）"
            sections.append(f"{header}\n（アーカイブ: {item['archive_rel'] or '不明'}）\n\n{content}")

        body = "\n\n---\n\n".join(sections)
        prompt = (
            "以下はこれまでの調査結果です。各トピックの要点をわかりやすく要約して提示し、"
            "ユーザに感想や意見を聞いてください。\n\n"
            "【重要】ユーザからフィードバックを受けたときの応答ルール:\n"
            "1. 必ず最初に、各フィードバックに対するあなた自身の感想・考え・気づきを述べること（これが最優先）\n"
            "2. 共感、新たな視点、関連する知見など、会話として自然に反応すること\n"
            "3. 感想を述べた後で、アーカイブへの記録とREVIEW.mdの更新を行うこと\n"
            "4. 記録作業は裏で行い、ユーザへの応答では感想と対話を中心にすること\n\n"
            "記録手順: 該当アーカイブに「## ユーザフィードバック」として記録し、"
            "REVIEW.md の該当行を「未レビュー」から「フィードバック済み」セクションに移動して [x] に変更する。\n\n"
            f"---\n\n{body}"
        )

        await interaction.response.defer()

        channel_id = interaction.channel_id
        session_id = get_channel_session(channel_id)
        is_new = session_id is None
        if is_new:
            session_id = str(uuid.uuid4())
            save_channel_session(channel_id, session_id)

        from core.config import get_model_config
        model, thinking = get_model_config()
        response, timed_out = await run_claude(
            prompt,
            model=model,
            thinking=thinking,
            session_id=session_id,
            is_new_session=is_new,
        )

        if timed_out:
            await interaction.followup.send(
                embed=make_error_embed("タイムアウトしました。もう一度お試しください。")
            )
            return

        display = re.sub(r"\n{2,}", "\n", response)
        chunks = split_message(display, max_len=2000)
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.channel.send(chunk)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReviewCog(bot))
