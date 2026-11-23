"""Screenshots of every page for the README, from the DEMO database only.

    make demo                                  # demo data on http://localhost:8012
    python scripts/screenshots.py [base_url]   # needs: pip install playwright

Fails if a page logs a console error, so it doubles as a smoke test of the UI.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8012"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
PAGES = {
    "dashboard": "/",
    "trends": "/trends/",
    "insights": "/insights/",
    "transactions": "/transactions/",
    "categories": "/categories/",
    "budget": "/budget/",
    "debt": "/debt/",
    "years": "/years/",
}


def _real(text: str) -> bool:
    # Chrome warns about COOP on any non-localhost http origin (e.g. host.docker.internal).
    return "Cross-Origin-Opener-Policy" not in text


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page.on("console", lambda m: m.type == "error" and _real(m.text) and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        for name, path in PAGES.items():
            page.goto(BASE + path, wait_until="networkidle")
            page.wait_for_timeout(600)  # chart animations
            page.screenshot(path=OUT / f"{name}.png", full_page=name != "dashboard")
        page.close()
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mobile.goto(BASE + "/", wait_until="networkidle")
        mobile.wait_for_timeout(600)
        mobile.screenshot(path=OUT / "dashboard-mobile.png")
        browser.close()
    for e in errors:
        print("console error:", e)
    print(f"{len(PAGES) + 1} screenshots in {OUT}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
