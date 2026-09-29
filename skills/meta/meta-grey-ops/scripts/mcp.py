#!/usr/bin/env python3
"""Talk to the official Meta Ads MCP (https://mcp.facebook.com/ads) with a bearer token.

    python3 mcp.py tools                       # list tool names (+ --schema NAME for one schema)
    python3 mcp.py accounts                    # ads_get_ad_accounts → is_ads_mcp_enabled per account
    python3 mcp.py call ads_get_ad_entities '{"ad_account_id":"123","level":"campaign","fields":["name"]}'

Needs META_TOKEN with scope `ads_mcp_management` (02 §5). Streamable HTTP: initialize once, keep
Mcp-Session-Id. Errors arrive as result.isError with Graph error_code/error_subcode, localised
messages — branch on the numbers. Traffic takes the same META_PROXY exit as graph.py (no-proxy
only with META_ALLOW_NO_PROXY=1) and never carries META_COOKIES. `call` enforces a read-only tool allowlist; every MCP create,
update, delete, upload, boost, and activation tool is rejected. Never prints the token.
"""
from __future__ import annotations

import json
import os
import re
import sys

import graph

URL = "https://mcp.facebook.com/ads"
TOKEN = os.environ.get("META_TOKEN", "")
READ_ONLY_TOOL = re.compile(
    r"^ads_(?:"
    r"account_get_activity_logs|"
    r"get_[a-z0-9_]+|"
    r"insights_[a-z0-9_]+|"
    r"library_search|"
    r"catalog_(?:get|list|search)_[a-z0-9_]+|"
    r"experiment_(?:check_eligibility|list_tests|abtest_get_test|lift_get_test)|"
    r"pixel_(?:event|parameter)_read"
    r")$"
)


def require_read_only_tool(name: str) -> None:
    if not READ_ONLY_TOOL.fullmatch(name):
        raise SystemExit(
            f"MCP tool {name!r} is not on the read-only allowlist; all mutations must use "
            "workspace-bound metaops commands"
        )


def _post(method: str, params: dict | None, sid: str | None, rid: int):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid:
        h["Mcp-Session-Id"] = sid
    body = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        body["params"] = params
    # graph.plain_session(): same proxy gate as every Graph call (exits when META_PROXY is
    # unset and META_ALLOW_NO_PROXY is not 1), env proxies ignored, no Cookie header.
    graph.register_secret(TOKEN)
    try:
        r = graph.plain_session().post(URL, data=json.dumps(body).encode(), headers=h, timeout=120)
    except Exception as e:  # noqa: BLE001 - transport errors may embed proxy credentials
        raise SystemExit(f"MCP transport error: {graph.redact(str(e))}") from None
    if r.status_code >= 400:
        raise SystemExit(f"HTTP {r.status_code}: {graph.redact(r.text[:300])}\n"
                         "401 here = token lacks ads_mcp_management or app lacks the MCP use case (02 §5)")
    raw = r.content.decode()
    msgs = [
        json.loads(line[5:].strip())
        for line in raw.splitlines()
        if line.startswith("data:")
    ]
    return r.headers.get("Mcp-Session-Id"), (msgs[0] if msgs else json.loads(raw))


def session() -> str:
    sid, _ = _post("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                  "clientInfo": {"name": "meta-grey-ops", "version": "1"}}, None, 1)
    if not sid:
        raise SystemExit("no Mcp-Session-Id returned")
    return sid


def call(sid: str, name: str, args: dict) -> dict:
    require_read_only_tool(name)
    _, msg = _post("tools/call", {"name": name, "arguments": args}, sid, 2)
    if "error" in msg:
        return {"isError": True, "rpc_error": msg["error"]}
    res = msg["result"]
    return res.get("structuredContent") or {"isError": res.get("isError"), "content": res.get("content")}


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tools"
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if not TOKEN:
        raise SystemExit("META_TOKEN not set")
    if cmd == "call":
        if len(sys.argv) < 3:
            raise SystemExit("mcp.py call requires a tool name")
        require_read_only_tool(sys.argv[2])
    sid = session()
    if cmd == "tools":
        _, msg = _post("tools/list", None, sid, 2)
        tools = msg["result"]["tools"]
        if "--schema" in sys.argv:
            want = sys.argv[sys.argv.index("--schema") + 1]
            print(json.dumps(next(t for t in tools if t["name"] == want), indent=1))
        else:
            print(len(tools), "tools")
            for t in tools:
                print(" ", t["name"])
    elif cmd == "accounts":
        for a in call(sid, "ads_get_ad_accounts", {}).get("ad_accounts", []):
            print(f"  act_{a['ad_account_id']:<18} {a['ad_account_name'][:24]:<24} mcp={a['is_ads_mcp_enabled']} "
                  f"queryable={a['is_queryable']} {a['currency']} {a.get('is_ads_mcp_disabled_reason') or ''}")
    elif cmd == "call":
        out = call(sid, sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else {})
        print(json.dumps(out, ensure_ascii=False, indent=1).replace(TOKEN, "<TOKEN>"))
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
