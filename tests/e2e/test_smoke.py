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
