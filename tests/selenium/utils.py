"""
Shared helpers: wait utilities, timing wrappers, screenshot capture.
"""
import time
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

SCREENSHOT_DIR = Path(__file__).parent / "results" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def wait_for(driver, locator, timeout=15):
    """Wait until element is visible; raise AssertionError with screenshot on timeout."""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located(locator)
        )
    except TimeoutException:
        _screenshot(driver, f"timeout_{locator[1][:30]}")
        raise AssertionError(f"Element {locator} not visible after {timeout}s")


def click_and_wait(driver, locator, timeout=15):
    el = wait_for(driver, locator, timeout)
    el.click()
    return el


def timed_get(driver, url: str) -> tuple[float, dict]:
    """Navigate to URL, return (elapsed_seconds, nav_timing_dict)."""
    t0 = time.perf_counter()
    driver.get(url)
    elapsed = time.perf_counter() - t0
    timing = _safe_nav_timing(driver)
    return elapsed, timing


def timed_action(fn, *args, **kwargs) -> float:
    """Time any callable; return elapsed seconds."""
    t0 = time.perf_counter()
    fn(*args, **kwargs)
    return time.perf_counter() - t0


def _safe_nav_timing(driver) -> dict:
    try:
        js = """
        const t = performance.timing;
        const nav = performance.getEntriesByType('navigation')[0] || {};
        return {
            dns_ms:       t.domainLookupEnd - t.domainLookupStart,
            tcp_ms:       t.connectEnd - t.connectStart,
            ttfb_ms:      t.responseStart - t.requestStart,
            dom_load_ms:  t.domContentLoadedEventEnd - t.navigationStart,
            page_load_ms: t.loadEventEnd - t.navigationStart,
        };
        """
        return driver.execute_script(js)
    except Exception:
        return {}


def _screenshot(driver, name: str):
    path = SCREENSHOT_DIR / f"{name}.png"
    driver.save_screenshot(str(path))
    return path


def screenshot(driver, name: str) -> Path:
    return _screenshot(driver, name)


def assert_text_present(driver, text: str):
    body = driver.find_element(By.TAG_NAME, "body").text
    assert text.lower() in body.lower(), f"Expected '{text}' in page body"
