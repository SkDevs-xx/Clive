"""
UtilityCog: /model, /status, /cancel, /mention
"""

import discord
from discord import app_commands
from discord.ext import commands

from core.config import (
    load_config, save_config,
    get_model_config,
    get_no_mention_channels, set_no_mention,
)
from core.embeds import make_info_embed


MODEL_CHOICES = [
    discord.SelectOption(label="Sonnet", value="sonnet", description="高速・バランス型（デフォルト）"),
    discord.SelectOption(label="Opus", value="opus", description="最高精度・低速"),
    discord.SelectOption(label="Haiku", value="haiku", description="最速・軽量"),
]


class ModelView(discord.ui.View):
    """モデル + Thinking 設定の Embed + Select + ボタン。"""

    def __init__(self, current_model: str, current_thinking: bool):
        super().__init__(timeout=60)
        self.current_model = current_model
        self.current_thinking = current_thinking

        options = [
            discord.SelectOption(
                label=opt.label, value=opt.value,
                description=opt.description,
                default=(opt.value == current_model),
            )
            for opt in MODEL_CHOICES
        ]
        self.model_select = discord.ui.Select(placeholder="モデルを選択", options=options)
        self.model_select.callback = self._on_model_select
        self.add_item(self.model_select)

        self._update_buttons(current_thinking)

    def _update_buttons(self, thinking: bool):
        self.thinking_on_btn.style = discord.ButtonStyle.success if thinking else discord.ButtonStyle.secondary
        self.thinking_off_btn.style = discord.ButtonStyle.success if not thinking else discord.ButtonStyle.secondary

    @staticmethod
    def make_embed(model: str, thinking: bool) -> discord.Embed:
        thinking_label = "ON" if thinking else "OFF"
        return make_info_embed(
            "モデル設定",
            f"**モデル:** {model}\n**Thinking:** {thinking_label}",
        )

    async def _on_model_select(self, interaction: discord.Interaction):
        self.current_model = interaction.data["values"][0]
        for opt in self.model_select.options:
            opt.default = (opt.value == self.current_model)
        cfg = load_config()
        cfg["model"] = self.current_model
        save_config(cfg)
        await interaction.response.edit_message(
            embed=self.make_embed(self.current_model, self.current_thinking), view=self
        )

    @discord.ui.button(label="Thinking ON")
    async def thinking_on_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_thinking = True
        self._update_buttons(True)
        cfg = load_config()
        cfg["thinking"] = True
        save_config(cfg)
        await interaction.response.edit_message(
            embed=self.make_embed(self.current_model, True), view=self
        )

    @discord.ui.button(label="Thinking OFF")
    async def thinking_off_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_thinking = False
        self._update_buttons(False)
        cfg = load_config()
        cfg["thinking"] = False
        save_config(cfg)
        await interaction.response.edit_message(
            embed=self.make_embed(self.current_model, False), view=self
        )


class MentionView(discord.ui.View):
    """メンション要否の ON/OFF ボタン付きビュー。"""

    def __init__(self, channel_id: int, mention_free: bool):
        super().__init__(timeout=60)
        self.channel_id = channel_id
        self._update_buttons(mention_free)

    def _update_buttons(self, mention_free: bool):
        self.on_btn.style = discord.ButtonStyle.success if mention_free else discord.ButtonStyle.secondary
        self.off_btn.style = discord.ButtonStyle.success if not mention_free else discord.ButtonStyle.secondary

    @staticmethod
    def make_embed(mention_free: bool) -> discord.Embed:
        status = "メンション不要" if mention_free else "メンション必要"
        return make_info_embed("メンション設定", f"このチャンネル: **{status}**")

    @discord.ui.button(label="メンション不要")
    async def on_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        set_no_mention(self.channel_id, True)
        self._update_buttons(True)
        await interaction.response.edit_message(embed=self.make_embed(True), view=self)

    @discord.ui.button(label="メンション必要")
    async def off_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        set_no_mention(self.channel_id, False)
        self._update_buttons(False)
        await interaction.response.edit_message(embed=self.make_embed(False), view=self)


class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="model", description="モデルと Thinking を設定する")
    async def model_command(self, interaction: discord.Interaction):
        model, thinking = get_model_config()
        view = ModelView(model, thinking)
        await interaction.response.send_message(
            embed=ModelView.make_embed(model, thinking), view=view, ephemeral=True
        )

    @app_commands.command(name="status", description="現在のステータスを表示する")
    async def status_command(self, interaction: discord.Interaction):
        model, thinking = get_model_config()
        thinking_label = "ON" if thinking else "OFF"

        desc = (
            f"**モデル:** {model}\n"
            f"**Thinking:** {thinking_label}\n"
            f"**Claude実行中:** {'はい' if self.bot.running_tasks else 'いいえ'}"
        )
        await interaction.response.send_message(
            embed=make_info_embed("ステータス", desc), ephemeral=True
        )

    @app_commands.command(name="cancel", description="実行中の Claude Code タスクをキャンセルする")
    async def cancel_command(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        task = self.bot.running_tasks.get(channel_id)
        if task and not task.done():
            proc = self.bot.running_processes.get(channel_id)
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
            task.cancel()
            await interaction.response.send_message(
                embed=make_info_embed("キャンセル", "タスクをキャンセルしました。"), ephemeral=True
            )
        else:
            await interaction.response.send_message(
                embed=make_info_embed("キャンセル", "実行中のタスクはありません。"), ephemeral=True
            )

    @app_commands.command(name="mention", description="このチャンネルでのメンション要否を設定する")
    async def mention_command(self, interaction: discord.Interaction):
        current = str(interaction.channel_id) in get_no_mention_channels()
        view = MentionView(interaction.channel_id, current)
        await interaction.response.send_message(
            embed=MentionView.make_embed(current), view=view, ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
