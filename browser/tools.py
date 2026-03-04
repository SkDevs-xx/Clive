"""MCP ツール定義 — Claude に公開するブラウザ操作ツール。"""

import asyncio
import base64
import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .cdp import CDPClient


def _load_port() -> int:
    """config.json から CDP ポートを読み取る。"""
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        return int(cfg.get("browser_cdp_port", 9222))
    except Exception:
        return 9222


# 共有インスタンス
cdp = CDPClient()
_port = _load_port()


def register_tools(mcp: FastMCP) -> None:
    """MCP サーバーにブラウザツールを登録する。"""

    async def _ensure_connected():
        if not cdp.is_connected:
            await cdp.connect(port=_port)

    # ─── Navigation ───

    @mcp.tool(name="browser_navigate", description="指定した URL にブラウザを遷移させる")
    async def browser_navigate(url: str) -> str:
        await _ensure_connected()
        result = await cdp.send("Page.navigate", {"url": url})
        return json.dumps({"navigated": url, "frameId": result.get("frameId", "")}, ensure_ascii=False)

    @mcp.tool(name="browser_back", description="ブラウザの「戻る」ボタンを押す")
    async def browser_back() -> str:
        await _ensure_connected()
        await cdp.send("Runtime.evaluate", {
            "expression": "window.history.back()",
        })
        await asyncio.sleep(0.5)
        return json.dumps({"action": "back"})

    @mcp.tool(name="browser_reload", description="現在のページを再読み込みする")
    async def browser_reload() -> str:
        await _ensure_connected()
        await cdp.send("Page.reload")
        return json.dumps({"action": "reload"})

    @mcp.tool(name="browser_get_url", description="現在のページの URL を取得する")
    async def browser_get_url() -> str:
        await _ensure_connected()
        result = await cdp.send("Runtime.evaluate", {
            "expression": "window.location.href",
            "returnByValue": True,
        })
        url = result.get("result", {}).get("value", "")
        return json.dumps({"url": url}, ensure_ascii=False)

    # ─── Interaction ───

    @mcp.tool(name="browser_click", description="指定座標 (x, y) をクリックする")
    async def browser_click(x: int, y: int) -> str:
        await _ensure_connected()
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
        })
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
        })
        return json.dumps({"clicked": {"x": x, "y": y}})

    @mcp.tool(name="browser_double_click", description="指定座標 (x, y) をダブルクリックする")
    async def browser_double_click(x: int, y: int) -> str:
        await _ensure_connected()
        for click_count in [1, 2]:
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": x, "y": y,
                "button": "left", "clickCount": click_count,
            })
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": x, "y": y,
                "button": "left", "clickCount": click_count,
            })
        return json.dumps({"double_clicked": {"x": x, "y": y}})

    @mcp.tool(name="browser_type", description="テキストを入力する。事前にクリックで入力欄にフォーカスしてから使う")
    async def browser_type(text: str) -> str:
        await _ensure_connected()
        for char in text:
            await cdp.send("Input.dispatchKeyEvent", {"type": "keyDown", "text": char, "key": char})
            await cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": char})
        return json.dumps({"typed": text}, ensure_ascii=False)

    @mcp.tool(name="browser_clear_field", description="現在フォーカスされている入力欄の内容をクリアする")
    async def browser_clear_field() -> str:
        await _ensure_connected()
        await cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "a", "modifiers": 2,
        })
        await cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "a", "modifiers": 2,
        })
        await cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Backspace",
        })
        await cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Backspace",
        })
        return json.dumps({"action": "clear_field"})

    @mcp.tool(name="browser_press_key", description="キーボードのキーを押す（Enter, Tab, Escape 等）")
    async def browser_press_key(key: str) -> str:
        await _ensure_connected()
        await cdp.send("Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
        await cdp.send("Input.dispatchKeyEvent", {"type": "keyUp", "key": key})
        return json.dumps({"pressed": key})

    @mcp.tool(name="browser_scroll", description="ページをスクロールする。direction は 'up' または 'down'。amount はピクセル数（デフォルト 500）")
    async def browser_scroll(direction: str = "down", amount: int = 500) -> str:
        await _ensure_connected()
        delta_y = amount if direction == "down" else -amount
        await cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": 480, "y": 540,
            "deltaX": 0, "deltaY": delta_y,
        })
        return json.dumps({"scrolled": direction, "amount": amount})

    # ─── Inspection ───

    @mcp.tool(name="browser_status", description="ブラウザ接続の状態を確認する")
    async def browser_status() -> str:
        try:
            targets = await cdp.get_targets(port=_port)
            connected = cdp.is_connected
            return json.dumps({
                "connected": connected,
                "cdp_port": _port,
                "tabs": [{"title": t.get("title", ""), "url": t.get("url", "")} for t in targets],
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"connected": False, "error": str(e)}, ensure_ascii=False)

    @mcp.tool(name="browser_screenshot", description="現在のページのスクリーンショットを撮る。base64 JPEG を返す")
    async def browser_screenshot(quality: int = 70) -> str:
        await _ensure_connected()
        result = await cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": quality})
        return result.get("data", "")

    @mcp.tool(name="browser_get_content", description="現在のページのテキスト内容を取得する")
    async def browser_get_content() -> str:
        await _ensure_connected()
        result = await cdp.send("Runtime.evaluate", {
            "expression": "document.body.innerText",
            "returnByValue": True,
        })
        text = result.get("result", {}).get("value", "")
        if len(text) > 50000:
            text = text[:50000] + "\n... (truncated)"
        return text

    @mcp.tool(name="browser_find_element", description="テキストまたは CSS セレクタで要素を探し、座標とテキストを返す。見つからなければ空リスト")
    async def browser_find_element(text: str = "", selector: str = "") -> str:
        await _ensure_connected()
        if selector:
            js = f"""
                (() => {{
                    const els = document.querySelectorAll({json.dumps(selector)});
                    return Array.from(els).slice(0, 10).map(el => {{
                        const r = el.getBoundingClientRect();
                        return {{
                            tag: el.tagName.toLowerCase(),
                            text: el.innerText?.slice(0, 100) || '',
                            x: Math.round(r.x + r.width / 2),
                            y: Math.round(r.y + r.height / 2),
                            width: Math.round(r.width),
                            height: Math.round(r.height),
                        }};
                    }});
                }})()
            """
        elif text:
            js = f"""
                (() => {{
                    const search = {json.dumps(text)}.toLowerCase();
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null
                    );
                    const results = [];
                    while (walker.nextNode() && results.length < 10) {{
                        const node = walker.currentNode;
                        if (node.textContent.toLowerCase().includes(search)) {{
                            const el = node.parentElement;
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {{
                                results.push({{
                                    tag: el.tagName.toLowerCase(),
                                    text: el.innerText?.slice(0, 100) || '',
                                    x: Math.round(r.x + r.width / 2),
                                    y: Math.round(r.y + r.height / 2),
                                    width: Math.round(r.width),
                                    height: Math.round(r.height),
                                }});
                            }}
                        }}
                    }}
                    return results;
                }})()
            """
        else:
            return json.dumps({"error": "text or selector is required"}, ensure_ascii=False)

        result = await cdp.send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        elements = result.get("result", {}).get("value", [])
        return json.dumps({"elements": elements}, ensure_ascii=False, indent=2)

    @mcp.tool(name="browser_evaluate", description="JavaScript を実行して結果を返す")
    async def browser_evaluate(expression: str) -> str:
        await _ensure_connected()
        result = await cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        value = result.get("result", {}).get("value")
        return json.dumps({"result": value}, ensure_ascii=False, default=str)

    # ─── Tabs ───

    @mcp.tool(name="browser_tabs", description="タブ一覧を取得する。tab_index を指定するとそのタブに切り替える")
    async def browser_tabs(tab_index: int = -1) -> str:
        targets = await cdp.get_targets(port=_port)
        tabs = [{"index": i, "title": t.get("title", ""), "url": t.get("url", "")} for i, t in enumerate(targets)]

        if tab_index >= 0:
            await cdp.switch_tab(port=_port, tab_index=tab_index)
            return json.dumps({"switched_to": tab_index, "tabs": tabs}, ensure_ascii=False, indent=2)

        return json.dumps({"tabs": tabs}, ensure_ascii=False, indent=2)

    @mcp.tool(name="browser_new_tab", description="新しいタブを開く。url を指定すればそのページを開く")
    async def browser_new_tab(url: str = "about:blank") -> str:
        await _ensure_connected()
        result = await cdp.send("Target.createTarget", {"url": url})
        target_id = result.get("targetId", "")
        return json.dumps({"new_tab": target_id, "url": url}, ensure_ascii=False)

    @mcp.tool(name="browser_close_tab", description="現在のタブを閉じる")
    async def browser_close_tab() -> str:
        await _ensure_connected()
        targets = await cdp.get_targets(port=_port)
        if not targets:
            return json.dumps({"error": "no tabs found"})
        # 現在接続中のタブを閉じる（get_targets の先頭がアクティブタブ）
        target_id = targets[0].get("id", "")
        await cdp.send("Target.closeTarget", {"targetId": target_id})
        return json.dumps({"closed": target_id})

    # ─── Forms ───

    @mcp.tool(name="browser_select_option", description="<select> 要素の option を選択する。CSS セレクタと value を指定")
    async def browser_select_option(selector: str, value: str) -> str:
        await _ensure_connected()
        js = f"""
            (() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return {{ error: 'element not found' }};
                el.value = {json.dumps(value)};
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return {{ selected: el.value }};
            }})()
        """
        result = await cdp.send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        return json.dumps(result.get("result", {}).get("value", {}), ensure_ascii=False)

    @mcp.tool(name="browser_upload_file", description="ファイルをアップロードする。selector で <input type='file'> を指定し、file_path でローカルファイルパスを指定")
    async def browser_upload_file(selector: str, file_path: str) -> str:
        await _ensure_connected()
        doc = await cdp.send("DOM.getDocument")
        root_id = doc["root"]["nodeId"]
        node = await cdp.send("DOM.querySelector", {
            "nodeId": root_id,
            "selector": selector,
        })
        node_id = node.get("nodeId", 0)
        if node_id == 0:
            return json.dumps({"error": f"element not found: {selector}"}, ensure_ascii=False)

        await cdp.send("DOM.setFileInputFiles", {
            "nodeId": node_id,
            "files": [file_path],
        })
        return json.dumps({"uploaded": file_path, "selector": selector}, ensure_ascii=False)

    # ─── Waiting ───

    @mcp.tool(name="browser_wait", description="ページの読み込み完了を待つ。timeout_sec で最大待機秒数を指定（デフォルト 10）")
    async def browser_wait(timeout_sec: int = 10) -> str:
        await _ensure_connected()
        try:
            result = await cdp.send("Runtime.evaluate", {
                "expression": """
                    new Promise(resolve => {
                        if (document.readyState === 'complete') resolve('complete');
                        else window.addEventListener('load', () => resolve('complete'));
                    })
                """,
                "awaitPromise": True,
                "returnByValue": True,
            }, timeout=float(timeout_sec))
            state = result.get("result", {}).get("value", "unknown")
        except TimeoutError:
            state = "timeout"
        return json.dumps({"readyState": state})

    @mcp.tool(name="browser_wait_for_element", description="指定した CSS セレクタまたはテキストの要素が表示されるまで待つ。SPA やローディング待ちに使う")
    async def browser_wait_for_element(selector: str = "", text: str = "", timeout_sec: int = 10) -> str:
        await _ensure_connected()
        if selector:
            js = f"""
                new Promise((resolve, reject) => {{
                    const sel = {json.dumps(selector)};
                    const el = document.querySelector(sel);
                    if (el) return resolve({{ found: true, tag: el.tagName.toLowerCase() }});
                    const observer = new MutationObserver(() => {{
                        const el = document.querySelector(sel);
                        if (el) {{
                            observer.disconnect();
                            resolve({{ found: true, tag: el.tagName.toLowerCase() }});
                        }}
                    }});
                    observer.observe(document.body, {{ childList: true, subtree: true }});
                    setTimeout(() => {{ observer.disconnect(); resolve({{ found: false }}); }}, {timeout_sec * 1000});
                }})
            """
        elif text:
            js = f"""
                new Promise((resolve, reject) => {{
                    const search = {json.dumps(text)}.toLowerCase();
                    if (document.body.innerText.toLowerCase().includes(search))
                        return resolve({{ found: true }});
                    const observer = new MutationObserver(() => {{
                        if (document.body.innerText.toLowerCase().includes(search)) {{
                            observer.disconnect();
                            resolve({{ found: true }});
                        }}
                    }});
                    observer.observe(document.body, {{ childList: true, subtree: true, characterData: true }});
                    setTimeout(() => {{ observer.disconnect(); resolve({{ found: false }}); }}, {timeout_sec * 1000});
                }})
            """
        else:
            return json.dumps({"error": "selector or text is required"}, ensure_ascii=False)

        result = await cdp.send("Runtime.evaluate", {
            "expression": js,
            "awaitPromise": True,
            "returnByValue": True,
        }, timeout=float(timeout_sec + 2))
        return json.dumps(result.get("result", {}).get("value", {}), ensure_ascii=False)

    # ─── Dialogs ───

    @mcp.tool(name="browser_handle_dialog", description="ダイアログ（alert, confirm, 'Leave site?' 等）を処理する。accept=true で OK/Leave、false で Cancel")
    async def browser_handle_dialog(accept: bool = True) -> str:
        await _ensure_connected()
        await cdp.send("Page.handleJavaScriptDialog", {"accept": accept})
        return json.dumps({"dialog": "accepted" if accept else "dismissed"})
