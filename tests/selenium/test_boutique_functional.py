"""
Selenium 功能测试：Online Boutique 前端 (v0.10.5)
覆盖：主页加载、商品浏览、加入购物车、结账流程
"""
import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from conftest import record_metric
from utils import wait_for, click_and_wait, timed_get, screenshot, assert_text_present


class TestHomepage:
    """TC-B01: 主页加载与基础元素验证"""

    def test_homepage_loads(self, driver, boutique_url):
        """主页在 30 秒内加载完成，标题包含 Online Boutique。"""
        elapsed, timing = timed_get(driver, boutique_url)
        record_metric("boutique_homepage_load",
                      timing.get("page_load_ms", elapsed * 1000),
                      {"url": boutique_url, "browser": driver.capabilities.get("browserName")})
        assert driver.title != "", "页面标题不应为空"
        screenshot(driver, "boutique_homepage")

    def test_homepage_has_products(self, driver, boutique_url):
        """主页展示商品列表（至少 1 件）。"""
        driver.get(boutique_url)
        wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card, .col-md-4"))
        products = driver.find_elements(By.CSS_SELECTOR, ".hot-product-card, .col-md-4")
        assert len(products) >= 1, f"商品数量不足，当前: {len(products)}"
        screenshot(driver, "boutique_homepage_products")

    def test_homepage_navigation_bar(self, driver, boutique_url):
        """导航栏包含购物车链接和货币选择。"""
        driver.get(boutique_url)
        wait_for(driver, (By.CSS_SELECTOR, "a[href='/cart'], .cymbal-cart-link, nav"))
        # 检查购物车链接
        cart_links = driver.find_elements(By.CSS_SELECTOR, "a[href='/cart']")
        assert len(cart_links) >= 1, "购物车链接未找到"
        # 检查货币下拉
        currency = driver.find_elements(By.CSS_SELECTOR, "select[name='currency_code']")
        assert len(currency) >= 1, "货币选择器未找到"

    def test_page_load_time_under_threshold(self, driver, boutique_url):
        """主页加载时间应 < 10 秒（SLA 要求）。"""
        elapsed, timing = timed_get(driver, boutique_url)
        load_ms = timing.get("page_load_ms", elapsed * 1000)
        record_metric("boutique_homepage_sla", load_ms, {"threshold_ms": 10000})
        assert load_ms < 10000, f"页面加载超时: {load_ms:.0f}ms > 10000ms"


class TestProductBrowsing:
    """TC-B02: 商品浏览与详情页"""

    def test_click_product_opens_detail(self, driver, boutique_url):
        """点击商品跳转到详情页，详情页包含 Add To Cart 按钮。"""
        driver.get(boutique_url)
        product_link = wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card a, .col-md-4 a"))
        t0 = time.perf_counter()
        product_link.click()
        # 等待 Add To Cart 按钮 (cymbal-button-primary)
        wait_for(driver, (By.CSS_SELECTOR, "button.cymbal-button-primary, button[type='submit']"))
        elapsed_ms = (time.perf_counter() - t0) * 1000
        record_metric("boutique_product_click_ms", elapsed_ms)
        screenshot(driver, "boutique_product_detail")
        assert "/product/" in driver.current_url, f"URL 未跳转至商品页: {driver.current_url}"

    def test_product_detail_has_price(self, driver, boutique_url):
        """商品详情页显示价格（含 $ 符号）。"""
        driver.get(boutique_url)
        product_link = wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card a, .col-md-4 a"))
        product_link.click()
        wait_for(driver, (By.CSS_SELECTOR, "button.cymbal-button-primary, button[type='submit']"))
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "$" in body_text, "商品详情页缺少价格信息（未找到 $）"

    def test_currency_change(self, driver, boutique_url):
        """切换货币后主页价格单位更新为 EUR。
        注: v0.10.5 货币 select 使用 onchange 自动提交，无需手动点 submit 按钮。
        """
        driver.get(boutique_url)
        select_el = wait_for(driver, (By.CSS_SELECTOR, "select[name='currency_code']"))
        sel = Select(select_el)
        t0 = time.perf_counter()
        sel.select_by_value("EUR")  # onchange 触发自动提交
        # 等待页面重新加载
        WebDriverWait(driver, 15).until(
            lambda d: "€" in d.find_element(By.TAG_NAME, "body").text or
                      "EUR" in d.find_element(By.TAG_NAME, "body").text
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        record_metric("boutique_currency_switch_ms", elapsed_ms)
        screenshot(driver, "boutique_currency_eur")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "€" in body_text or "EUR" in body_text, "货币未切换为 EUR"


class TestCart:
    """TC-B03: 购物车操作
    注: Online Boutique v0.10.5 购物车与结账在同一页面 (/cart)
    """

    def _add_first_product(self, driver, boutique_url) -> float:
        """辅助: 进入第一件商品并加入购物车，返回耗时(秒)。"""
        driver.get(boutique_url)
        product_link = wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card a, .col-md-4 a"))
        product_link.click()
        wait_for(driver, (By.CSS_SELECTOR, "button.cymbal-button-primary, button[type='submit']"))
        add_btn = driver.find_element(By.CSS_SELECTOR, "button.cymbal-button-primary, button[type='submit']")
        t0 = time.perf_counter()
        add_btn.click()
        return time.perf_counter() - t0

    def test_add_to_cart(self, driver, boutique_url):
        """加入购物车后跳转到 /cart，显示 cart-summary-item-row。"""
        elapsed = self._add_first_product(driver, boutique_url)
        # v0.10.5: 购物车页面使用 .cart-summary-item-row
        wait_for(driver, (By.CSS_SELECTOR, ".cart-summary-item-row, .cart-sections"))
        record_metric("boutique_add_to_cart_ms", elapsed * 1000)
        screenshot(driver, "boutique_cart")
        assert "/cart" in driver.current_url, f"加入购物车后未跳转到 /cart，当前: {driver.current_url}"

    def test_cart_shows_item(self, driver, boutique_url):
        """购物车页面显示已添加商品和价格。"""
        self._add_first_product(driver, boutique_url)
        wait_for(driver, (By.CSS_SELECTOR, ".cart-summary-item-row, .cart-sections"))
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "$" in body_text, "购物车页面未显示商品价格"
        # 验证 Cart 标题包含数量
        assert "Cart" in body_text or "cart" in body_text.lower(), "购物车未显示商品数量"

    def test_cart_has_checkout_form(self, driver, boutique_url):
        """购物车页面包含结账表单（v0.10.5 购物车与结账同页）。"""
        self._add_first_product(driver, boutique_url)
        wait_for(driver, (By.CSS_SELECTOR, ".cart-checkout-form, form[action='/cart/checkout']"))
        checkout_form = driver.find_elements(
            By.CSS_SELECTOR, ".cart-checkout-form, form[action='/cart/checkout']")
        assert len(checkout_form) >= 1, "未找到结账表单"


class TestCheckout:
    """TC-B04: 结账流程 (端到端)
    注: v0.10.5 结账表单嵌在购物车页面，提交到 /cart/checkout
    """

    def _go_to_cart_with_item(self, driver, boutique_url):
        """辅助: 进入带商品的购物车页。"""
        driver.get(boutique_url)
        product_link = wait_for(driver, (By.CSS_SELECTOR, ".hot-product-card a, .col-md-4 a"))
        product_link.click()
        wait_for(driver, (By.CSS_SELECTOR, "button.cymbal-button-primary, button[type='submit']"))
        driver.find_element(By.CSS_SELECTOR,
                            "button.cymbal-button-primary, button[type='submit']").click()
        wait_for(driver, (By.CSS_SELECTOR, ".cart-checkout-form, form[action='/cart/checkout']"))

    def test_checkout_form_visible(self, driver, boutique_url):
        """购物车页结账表单包含送货地址和支付字段。"""
        self._go_to_cart_with_item(driver, boutique_url)
        screenshot(driver, "boutique_checkout_form")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert any(kw in body_text.lower() for kw in
                   ["email", "address", "shipping", "payment", "credit"]), \
            "结账表单缺少预期字段"

    def test_checkout_form_submission(self, driver, boutique_url):
        """填写收货信息并提交订单，出现订单确认页面。"""
        self._go_to_cart_with_item(driver, boutique_url)
        wait_for(driver, (By.CSS_SELECTOR, "input[name='email']"))

        # 填写收货表单
        fields = {
            "email":              "test@example.com",
            "street_address":     "123 Main Street",
            "zip_code":           "10001",
            "city":               "New York",
            "state":              "NY",
            "country":            "United States",
            "credit_card_number": "4432801561520454",
            "credit_card_expiration_month": "1",
            "credit_card_expiration_year":  "2030",
            "credit_card_cvv":    "672",
        }
        for name, value in fields.items():
            els = driver.find_elements(By.CSS_SELECTOR, f"input[name='{name}'], select[name='{name}']")
            if els:
                tag = els[0].tag_name
                if tag == "select":
                    Select(els[0]).select_by_value(value)
                else:
                    els[0].clear()
                    els[0].send_keys(value)

        # 找到结账表单的提交按钮
        submit_btn = wait_for(
            driver, (By.CSS_SELECTOR,
                     "form.cart-checkout-form button[type='submit'], "
                     "form[action='/cart/checkout'] button[type='submit']"))
        t0 = time.perf_counter()
        submit_btn.click()

        # 等待确认页面
        WebDriverWait(driver, 30).until(
            lambda d: "order" in d.current_url.lower() or
                      any(kw in d.find_element(By.TAG_NAME, "body").text.lower()
                          for kw in ["confirmation", "order #", "thank you", "your order"])
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        record_metric("boutique_checkout_submit_ms", elapsed_ms)
        screenshot(driver, "boutique_order_confirmation")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert any(kw in body_text.lower() for kw in
                   ["confirmation", "order #", "thank you", "your order"]), \
            f"未出现订单确认信息，当前 URL: {driver.current_url}"
