"""
OnlineBoutique 功能测试脚本
使用 Selenium 模拟用户操作
"""

import time
import unittest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class OnlineBoutiqueTest(unittest.TestCase):
    """OnlineBoutique 功能测试"""
    
    @classmethod
    def setUpClass(cls):
        """测试前准备"""
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # 有界面模式便于观察
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        cls.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        cls.driver.implicitly_wait(10)
        cls.base_url = "http://localhost:8080"  # 根据实际地址修改
        
    @classmethod
    def tearDownClass(cls):
        """测试后清理"""
        cls.driver.quit()
        
    def test_01_homepage_load(self):
        """测试首页加载"""
        self.driver.get(self.base_url)
        
        # 验证页面标题
        self.assertIn("Online Boutique", self.driver.title)
        
        # 验证商品列表存在
        products = self.driver.find_elements(By.CLASS_NAME, "card")
        self.assertGreater(len(products), 0, "首页应显示商品列表")
        
        print(f"首页加载成功，找到 {len(products)} 个商品")
        
    def test_02_product_detail(self):
        """测试商品详情页"""
        self.driver.get(self.base_url)
        
        # 点击第一个商品
        first_product = self.driver.find_element(By.CSS_SELECTOR, ".card a")
        first_product.click()
        
        # 等待页面加载
        wait = WebDriverWait(self.driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        
        # 验证商品详情存在
        product_name = self.driver.find_element(By.TAG_NAME, "h2").text
        self.assertTrue(len(product_name) > 0, "商品名称应存在")
        
        print(f"商品详情页加载成功: {product_name}")
        
    def test_03_add_to_cart(self):
        """测试添加商品到购物车"""
        self.driver.get(self.base_url)
        
        # 点击第一个商品
        first_product = self.driver.find_element(By.CSS_SELECTOR, ".card a")
        first_product.click()
        
        # 等待并点击 Add to Cart
        wait = WebDriverWait(self.driver, 10)
        add_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        add_button.click()
        
        # 验证跳转到购物车页面
        wait.until(EC.url_contains("/cart"))
        
        # 验证购物车中有商品
        cart_items = self.driver.find_elements(By.CLASS_NAME, "cart-summary-item-row")
        self.assertGreater(len(cart_items), 0, "购物车应有商品")
        
        print(f"添加商品到购物车成功")
        
    def test_04_place_order_without_coupon(self):
        """测试无优惠券下单"""
        # 先添加商品到购物车
        self.driver.get(self.base_url)
        first_product = self.driver.find_element(By.CSS_SELECTOR, ".card a")
        first_product.click()
        
        wait = WebDriverWait(self.driver, 10)
        add_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        add_button.click()
        wait.until(EC.url_contains("/cart"))
        
        # 点击 Place Order
        place_order = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        place_order.click()
        
        # 验证订单完成页
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
        confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
        
        self.assertIn("complete", confirmation.lower())
        print("无优惠券下单成功")
        
    def test_05_place_order_with_coupon(self):
        """测试使用优惠券下单"""
        # 先添加商品到购物车
        self.driver.get(self.base_url)
        first_product = self.driver.find_element(By.CSS_SELECTOR, ".card a")
        first_product.click()
        
        wait = WebDriverWait(self.driver, 10)
        add_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        add_button.click()
        wait.until(EC.url_contains("/cart"))
        
        # 输入优惠券
        coupon_input = wait.until(
            EC.presence_of_element_located((By.ID, "coupon_code"))
        )
        coupon_input.send_keys("SAVE10")
        
        # 点击 Place Order
        place_order = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        place_order.click()
        
        # 验证订单完成页显示优惠券
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
        page_source = self.driver.page_source
        
        self.assertIn("Coupon Applied", page_source, "应显示优惠券信息")
        print("使用优惠券下单成功")
        
    def test_06_page_load_time(self):
        """测试页面加载时间"""
        start_time = time.time()
        self.driver.get(self.base_url)
        load_time = time.time() - start_time
        
        self.assertLess(load_time, 5, "首页加载时间应小于5秒")
        print(f"首页加载时间: {load_time:.2f}秒")


if __name__ == "__main__":
    unittest.main(verbosity=2)
