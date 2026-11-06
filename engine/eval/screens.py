"""Take real screenshots of the running Web UI with the installed Chrome."""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8787"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results/shots")
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1500, 1000


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("saved", name)


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(BASE)
    page.fill("#user", "alice")
    page.fill("#pass", "alice-demo-pass")
    page.click("#login-form button")
    page.wait_for_selector("#app:not([hidden])")

    def search(q, name):
        page.fill("#q", q)
        page.press("#q", "Enter")
        page.wait_for_function("document.querySelector('#meta').textContent.includes('connected files in')", timeout=30000)
        page.wait_for_timeout(1500)
        shot(page, name)

    search("a man wearing a UGREEN T-shirt", "search-tshirt")
    search("everything about Project Falcon", "search-falcon")
    search("kids loved the temple", "search-spoken")
    page.click("[data-page=graph]")
    page.wait_for_timeout(9000)
    shot(page, "graph-all")
    page.click("[data-page=missing]")
    page.wait_for_timeout(800)
    shot(page, "missing")
    page.click("[data-page=access]")
    page.wait_for_timeout(1000)
    shot(page, "access")
    page.click("[data-page=status]")
    page.wait_for_timeout(800)
    shot(page, "status")
    falcon = page.evaluate(
        """async () => { const r = await fetch('/v1/search',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({q:'kickoff notes Falcon',limit:1})}); return (await r.json()).results[0].file_id }"""
    )
    page.goto(f"{BASE}/#file={falcon}")
    page.wait_for_timeout(7000)
    shot(page, "graph-local")
    print("page errors:", errors[:5])
    b.close()
