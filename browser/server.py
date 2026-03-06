"""Clive Browser MCP Server — Chrome CDP 経由のブラウザ操作を AI に提供する。"""

from mcp.server.fastmcp import FastMCP

from .tools import register_tools

mcp = FastMCP("clive-browser")
register_tools(mcp)


def main():
    import asyncio
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
