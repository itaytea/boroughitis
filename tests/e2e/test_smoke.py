"""Browser smoke test: make a guess, reload, and check it is restored.

Needs pytest-playwright and a Chromium install. When pytest-playwright is not
installed (as in the plain unit-test workflow) this module is skipped.
"""
import functools
import http.server
import pathlib
import threading

import pytest

pytest.importorskip("pytest_playwright", reason="pytest-playwright not installed")
from playwright.sync_api import Page, expect  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GUESS = "Newark, Essex"


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site_url():
    handler = functools.partial(_QuietHandler, directory=str(REPO_ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)  # port 0 = free port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()


def test_guess_survives_reload(page: Page, site_url: str):
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(site_url)
    rows = page.locator("#guess-grid .row:not(.empty)")
    expect(page.locator("#guess-grid .row")).to_have_count(6)
    expect(rows).to_have_count(0)

    # The how-to dialog opens automatically on a first visit.
    expect(page.locator("#howto-dialog")).to_have_attribute("open", "")
    page.keyboard.press("Escape")
    expect(page.locator("#howto-dialog")).not_to_have_attribute("open", "")

    page.fill("#guess-input", GUESS)
    page.click("#guess-btn")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Newark")

    page.reload()
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Newark")

    assert errors == [], f"console errors: {errors}"


UNSAFE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
  viewBox="0 0 10 10" onload="window.__pwned = 1" style="background:url(x)">
  <image href="http://example.invalid/x.png"/>
  <use xlink:href="#p"/>
  <a href="javascript:window.__pwned=1"><path class="inlink" d="M0 0L1 1"/></a>
  <g onclick="window.__pwned = 1"><path class="real" d="M1 1L9 1L9 9Z" fill="red"
     style="fill:blue" onmouseover="window.__pwned = 1"/></g>
</svg>"""


def test_outline_svg_is_sanitized(page: Page, site_url: str):
    page.route(
        "**/data/outlines/*.svg",
        lambda route: route.fulfill(status=200, content_type="image/svg+xml", body=UNSAFE_SVG),
    )
    page.goto(site_url)
    box = page.locator("#outline-box")
    expect(box.locator("svg path.real")).to_have_count(1)

    for tag in ("image", "use", "a", "foreignObject", "script"):
        expect(box.locator(tag)).to_have_count(0)

    leftover = box.evaluate(
        """el => [el, ...el.querySelectorAll('*')].flatMap(n =>
            Array.from(n.attributes).map(a => n.localName + '@' + a.name))"""
    )
    assert not [a for a in leftover if a.split("@")[1] in ("style", "href", "xlink:href")
                or a.split("@")[1].startswith("on")], leftover
    assert "svg@viewBox" in leftover and "path@d" in leftover and "path@fill" in leftover
    assert page.evaluate("window.__pwned") is None
