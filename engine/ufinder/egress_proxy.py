"""The only way out, and it is off by default.

A small CONNECT proxy that allows exactly the hosts the owner named. It runs only
under the `egress` Compose profile. Without it, engine containers have no route
to anything outside their internal network.
"""
from __future__ import annotations

import asyncio
import logging
import os

ALLOW = {h.strip().lower() for h in os.environ.get("UFINDER_EGRESS_ALLOW", "").split(",") if h.strip()}
PORT = int(os.environ.get("UFINDER_EGRESS_PORT", "8899"))
log = logging.getLogger("ufinder.egress")


async def pump(reader, writer):
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def absolute_form(first: bytes, reader, writer):
    """Plain HTTP through a proxy: GET http://host:port/path HTTP/1.1"""
    method, url, version = first.decode().split()
    target = url.split("://", 1)[1]
    hostport, _, path = target.partition("/")
    host, _, port = hostport.partition(":")
    if host.lower() not in ALLOW:
        log.warning("denied %s", host)
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()
        return
    log.info("allowed %s", host)
    up_r, up_w = await asyncio.open_connection(host, int(port or 80))
    up_w.write(f"{method} /{path} {version}\r\n".encode())
    await up_w.drain()
    await asyncio.gather(pump(reader, up_w), pump(up_r, writer))


async def handle(reader, writer):
    try:
        first = (await reader.readline()).strip()
        if not first.startswith(b"CONNECT "):
            await absolute_form(first, reader, writer)
            return
        target = first.split()[1].decode()
        host, _, port = target.partition(":")
        while (await reader.readline()).strip():
            pass
        if host.lower() not in ALLOW:
            log.warning("denied %s", host)
            writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        log.info("allowed %s", host)
        up_r, up_w = await asyncio.open_connection(host, int(port or 443))
        writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
        await writer.drain()
        await asyncio.gather(pump(reader, up_w), pump(up_r, writer))
    except Exception as exc:
        log.warning("proxy error: %s", exc)
        writer.close()


async def main():
    logging.basicConfig(level="INFO", format="%(asctime)s %(name)s %(message)s")
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    log.info("allow list: %s", sorted(ALLOW))
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
