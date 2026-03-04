"""
Discord Embed 生成ヘルパー
"""

import re

import discord


def split_message(text: str, max_len: int = 2000) -> list[str]:
    """Markdown 構造を壊さないようにテキストを分割する。
    分割の優先順位: 空行 > 見出し行の手前 > 改行 > 強制切断。
    コードブロック内で切れた場合は閉じ/開きを補う。
    """
    if not text:
        return ["（応答なし）"]
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        # max_len 以内で最適な分割点を探す
        segment = remaining[:max_len]
        cut = -1

        # 1. 空行で分割
        m = list(re.finditer(r"\n\n", segment))
        if m:
            cut = m[-1].end()

        # 2. 見出し行の手前で分割
        if cut == -1:
            m = list(re.finditer(r"\n(?=#{1,3} )", segment))
            if m:
                cut = m[-1].start() + 1  # \n の直後

        # 3. 改行で分割
        if cut == -1:
            idx = segment.rfind("\n")
            if idx > max_len // 4:
                cut = idx + 1

        # 4. 強制切断
        if cut == -1:
            cut = max_len

        chunk = remaining[:cut]
        remaining = remaining[cut:]

        # コードブロックが閉じていなければ補う（行頭 ``` のみカウント）
        in_block = False
        lang_tag = ""
        for line in chunk.split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_block:
                    in_block = True
                    lang_tag = stripped[3:].strip()  # 言語タグを保持
                else:
                    in_block = False
                    lang_tag = ""
        if in_block:
            chunk += "\n```"
            remaining = f"```{lang_tag}\n" + remaining

        chunks.append(chunk)

    return chunks


def make_error_embed(msg: str) -> discord.Embed:
    return discord.Embed(title="エラー", description=msg, color=discord.Color.red())

def make_info_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=discord.Color.green())
