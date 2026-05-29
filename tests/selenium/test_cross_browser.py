"""
TC-CB: Online Boutique 跨浏览器兼容性测试（Chrome + Firefox）
同一测试用例在两个浏览器上运行，比较加载时间和功能一致性。
"""
import time
import pytest
from selenium.webdriver.common.by import By
from conftest import record_metric
from utils import wait_for, timed_get, screenshot


class TestCrossBrowser:
    """使用 multi_browser_driver fixture 在 Chrome 和 Firefox 上各运行一次。
    Firefox 需要 geckodriver，若未安装则自动跳过。
    """

    def test_boutique_homepage_cross_browser(self, multi_browser_driver, boutique_url):
        """两种浏览器均能成功加载 Online Boutique 主页。"""
        driver = multi_browser_driver
        browser = getattr(driver, "browser_name", driver.capabilities.get("browserName", "unknown"))
        elapsed, timing = timed_get(driver, boutique_url)
        load_ms = timing.get("page_load_ms", elapsed * 1000)
        record_metric(f"cross_browser_boutique_load_{browser}", load_ms, {"browser": browser})
        assert driver.title != "", f"[{browser}] 页面标题为空"
        screenshot(driver, f"cross_{browser}_boutique_home")
        print(f"\n  [{browser}] 主页加载: {load_ms:.0f}ms")

    def test_boutique_products_cross_browser(self, multi_browser_driver, boutique_url):
        """两种浏览器均能看到商品列表。"""
        driver = multi_browser_driver
        browser = getattr(driver, "browser_name", driver.capabilities.get("browserName", "unknown"))
        t0 = time.perf_counter()
        driver.get(boutique_url)
        wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card, .col-md-4"))
        products = driver.find_elements(By.CSS_SELECTOR, ".hot-product-card, .col-md-4")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        record_metric(f"cross_browser_products_load_{browser}", elapsed_ms, {"browser": browser})
        assert len(products) >= 1, f"[{browser}] 商品列表为空"
        screenshot(driver, f"cross_{browser}_boutique_products")
        print(f"\n  [{browser}] 商品列表: {len(products)} 件，耗时 {elapsed_ms:.0f}ms")

    def test_add_to_cart_cross_browser(self, multi_browser_driver, boutique_url):
        """两种浏览器均能成功加入购物车。"""
        driver = multi_browser_driver
        browser = getattr(driver, "browser_name", driver.capabilities.get("browserName", "unknown"))
        driver.get(boutique_url)
        product_link = wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card a, .col-md-4 a"))
        product_link.click()
        wait_for(driver, (By.CSS_SELECTOR, "button.cymbal-button-primary, button[type='submit']"))
        add_btn = driver.find_element(By.CSS_SELECTOR,
                                     "button.cymbal-button-primary, button[type='submit']")
        t0 = time.perf_counter()
        add_btn.click()
        wait_for(driver, (By.CSS_SELECTOR, ".cart-summary-item-row, .cart-sections"))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        record_metric(f"cross_browser_add_to_cart_{browser}", elapsed_ms, {"browser": browser})
        assert "/cart" in driver.current_url, f"[{browser}] 加购后未跳转到购物车"
        screenshot(driver, f"cross_{browser}_cart")
        print(f"\n  [{browser}] 加入购物车: {elapsed_ms:.0f}ms")

    def test_page_load_time_comparison(self, multi_browser_driver, boutique_url):
        """记录并比较两种浏览器的关键页面性能指标。"""
        driver = multi_browser_driver
        browser = getattr(driver, "browser_name", driver.capabilities.get("browserName", "unknown"))
        elapsed, timing = timed_get(driver, boutique_url)

        metrics_to_record = {
            "dns_ms":       timing.get("dns_ms", 0),
            "tcp_ms":       timing.get("tcp_ms", 0),
            "ttfb_ms":      timing.get("ttfb_ms", 0),
            "dom_load_ms":  timing.get("dom_load_ms", 0),
            "page_load_ms": timing.get("page_load_ms", elapsed * 1000),
        }
        for metric_name, value in metrics_to_record.items():
            record_metric(f"cross_{browser}_{metric_name}", value, {"browser": browser})

        print(f"\n  [{browser}] 性能指标:")
        for k, v in metrics_to_record.items():
            print(f"    {k}: {v:.0f}ms")

        assert metrics_to_record["page_load_ms"] < 15000, \
            f"[{browser}] 页面加载 {metrics_to_record['page_load_ms']:.0f}ms > 15000ms"
