"""
Pytest fixtures: browser setup, base URLs, metrics collection.
"""
import os
import time
import json
import pytest
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

# ── URLs (override via environment variables) ──────────────────────────────
BOUTIQUE_URL  = os.getenv("BOUTIQUE_URL",  "http://localhost:8080")
SOCKSHOP_URL  = os.getenv("SOCKSHOP_URL",  "http://localhost:8081")
BROWSER       = os.getenv("SELENIUM_BROWSER", "chrome")   # chrome | firefox
HEADLESS      = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
PAGE_TIMEOUT  = int(os.getenv("PAGE_TIMEOUT", "30"))

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Metrics store (per test session) ──────────────────────────────────────
_metrics: list[dict] = []


def _make_chrome(headless: bool) -> webdriver.Chrome:
    opts = ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def _make_firefox(headless: bool) -> webdriver.Firefox:
    opts = FirefoxOptions()
    if headless:
        opts.add_argument("--headless")
    opts.add_argument("--width=1920")
    opts.add_argument("--height=1080")
    # Use cached geckodriver to avoid GitHub API rate limits
    from pathlib import Path as _Path
    import os as _os
    cached = _Path.home() / ".wdm/drivers/geckodriver/win64/v0.35.0/geckodriver.exe"
    if cached.exists():
        gecko_path = str(cached)
    else:
        try:
            gecko_path = GeckoDriverManager(version="v0.35.0").install()
        except Exception:
            gecko_path = GeckoDriverManager().install()
    service = FirefoxService(gecko_path)
    return webdriver.Firefox(service=service, options=opts)


def _create_driver(browser: str, headless: bool) -> webdriver.Remote:
    if browser == "firefox":
        return _make_firefox(headless)
    return _make_chrome(headless)


@pytest.fixture(scope="session")
def boutique_url() -> str:
    return BOUTIQUE_URL


@pytest.fixture(scope="session")
def sockshop_url() -> str:
    return SOCKSHOP_URL


@pytest.fixture
def driver():
    """Single-browser fixture (default browser)."""
    drv = _create_driver(BROWSER, HEADLESS)
    drv.set_page_load_timeout(PAGE_TIMEOUT)
    yield drv
    drv.quit()


@pytest.fixture(params=["chrome", "firefox"])
def multi_browser_driver(request):
    """Fixture that runs tests on BOTH Chrome and Firefox."""
    drv = _create_driver(request.param, HEADLESS)
    drv.set_page_load_timeout(PAGE_TIMEOUT)
    drv.browser_name = request.param
    yield drv
    drv.quit()


def record_metric(name: str, value_ms: float, extra: dict | None = None):
    entry = {"test": name, "value_ms": round(value_ms, 2), **(extra or {})}
    _metrics.append(entry)


def get_nav_timing(driver) -> dict:
    """Extract W3C Navigation Timing metrics from the browser."""
    js = """
    const t = performance.timing;
    return {
        dns_ms:           t.domainLookupEnd - t.domainLookupStart,
        tcp_ms:           t.connectEnd - t.connectStart,
        ttfb_ms:          t.responseStart - t.requestStart,
        dom_load_ms:      t.domContentLoadedEventEnd - t.navigationStart,
        page_load_ms:     t.loadEventEnd - t.navigationStart,
        response_size_b:  performance.getEntriesByType('navigation')[0]?.transferSize || 0
    };
    """
    return driver.execute_script(js)


@pytest.fixture(scope="session", autouse=True)
def save_metrics_on_exit():
    yield
    if _metrics:
        out = RESULTS_DIR / "timing_metrics.json"
        out.write_text(json.dumps(_metrics, indent=2), encoding="utf-8")
        print(f"\n[metrics] Saved {len(_metrics)} records → {out}")
