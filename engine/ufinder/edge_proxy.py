"""Forwards one published port to the gateway, and does nothing else.

The gateway holds user data and keys, so it stays on the sealed network with no
route out. This container is the only one that can touch the LAN. It holds no
data, no keys and no credentials. It passes bytes to one fixed address.
"""
from __future__ import annotations

import asyncio
import os

TARGET = os.environ.get("UFINDER_EDGE_TARGET", "gateway")
PORT = int(os.environ.get("UFINDER_EDGE_PORT", "8787"))


async def pump(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
        except ConnectionError:
            pass


async def handle(reader, writer):
    try:
        up_r, up_w = await asyncio.open_connection(TARGET, PORT)
    except OSError:
        writer.close()
        return
    await asyncio.gather(pump(reader, up_w), pump(up_r, writer))


async def main():
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
