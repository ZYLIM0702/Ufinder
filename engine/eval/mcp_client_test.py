"""Connect with the official MCP Python SDK, the way a real agent would."""
import asyncio
import json
import os
import sys

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

BASE = os.environ.get("UFINDER_URL", "http://localhost:8787")


async def main():
    c = httpx.Client(base_url=BASE, timeout=60)
    c.post("/api/login", json={"user": "alice", "password": "alice-demo-pass"}).raise_for_status()
    key = c.post("/v1/keys", json={"name": "mcp-client-test", "max_tier": 2, "external": True}).json()
    headers = {"Authorization": f"Bearer {key['token']}"}
    out = {}
    http = create_mcp_http_client(headers=headers)
    async with http, streamable_http_client(f"{BASE}/mcp", http_client=http) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            info = await session.initialize()
            out["server"] = info.server_info.name
            out["protocol"] = info.protocol_version
            tools = await session.list_tools()
            out["tools"] = [t.name for t in tools.tools]
            res = await session.call_tool("search_files", {"query": "late fee on the flour bill", "limit": 3})
            data = json.loads(res.content[0].text)
            out["top_result"] = data["results"][0]["path"]
            out["first_reason"] = data["results"][0]["reasons"][0]["label"]
            fid = data["results"][0]["file_id"]
            rel = await session.call_tool("get_related", {"file_id": fid, "limit": 3})
            out["related_ok"] = not rel.is_error
    try:
        bad = create_mcp_http_client(headers={"Authorization": "Bearer ufd_bad_key"})
        async with bad, streamable_http_client(f"{BASE}/mcp", http_client=bad) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await asyncio.wait_for(session.initialize(), 15)
        out["bad_key_rejected"] = False
    except BaseException:
        out["bad_key_rejected"] = True
    print(json.dumps(out, indent=1))


asyncio.run(main())
