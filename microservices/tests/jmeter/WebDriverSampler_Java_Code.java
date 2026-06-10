/**
 * JMeter WebDriver Sampler - Java语言测试脚本
 * OnlineBoutique微服务性能测试
 * 
 * 使用说明：
 * 1. 在JMeter中安装WebDriver插件
 * 2. 添加jp@gc - WebDriver Sampler
 * 3. 语言选择：java
 * 4. 将以下代码粘贴到Script区域
 * 5. 配置jp@gc - Chrome Driver Config（指定ChromeDriver路径）
 */

// ============================================
// 脚本1：首页访问 (Homepage)
// ============================================
WDS.sampleResult.sampleStart();

String baseUrl = WDS.vars.get("BASE_URL");
String port = WDS.vars.get("PORT");
String targetUrl = "http://" + baseUrl + ":" + port + "/";

try {
    WDS.browser.get(targetUrl);
    
    String pageSource = WDS.browser.getPageSource();
    String pageTitle = WDS.browser.getTitle();
    
    if (pageSource.length() == 0) {
        WDS.sampleResult.setSuccessful(false);
        WDS.sampleResult.setResponseMessage("Homepage did not load - empty response");
    } else if (pageTitle.contains("Error") || pageTitle.contains("404")) {
        WDS.sampleResult.setSuccessful(false);
        WDS.sampleResult.setResponseMessage("Homepage returned error: " + pageTitle);
    } else {
        WDS.sampleResult.setSuccessful(true);
        WDS.sampleResult.setResponseMessage("Homepage loaded successfully. Title: " + pageTitle);
    }
    
    WDS.log.info("[Homepage] URL: " + targetUrl + " | Response Time: " + WDS.sampleResult.getTime() + "ms");
    
} catch (Exception e) {
    WDS.sampleResult.setSuccessful(false);
    WDS.sampleResult.setResponseMessage("Exception: " + e.getMessage());
    WDS.log.error("Navigation failed: " + e.getMessage());
}

WDS.sampleResult.sampleEnd();


// ============================================
// 脚本2：购物车页面 (Cart)
// ============================================
WDS.sampleResult.sampleStart();

try {
    String cartUrl = "http://" + WDS.vars.get("BASE_URL") + ":" + WDS.vars.get("PORT") + "/cart";
    WDS.browser.get(cartUrl);
    
    String pageSource = WDS.browser.getPageSource();
    
    if (pageSource.length() == 0) {
        WDS.sampleResult.setSuccessful(false);
        WDS.sampleResult.setResponseMessage("Cart page did not load");
    } else {
        WDS.sampleResult.setSuccessful(true);
        WDS.sampleResult.setResponseMessage("Cart page loaded successfully");
    }
    
    WDS.log.info("[Cart] Response Time: " + WDS.sampleResult.getTime() + "ms");
    
} catch (Exception e) {
    WDS.sampleResult.setSuccessful(false);
    WDS.sampleResult.setResponseMessage("Exception: " + e.getMessage());
}

WDS.sampleResult.sampleEnd();


// ============================================
// 脚本3：结算页面 (Checkout)
// ============================================
WDS.sampleResult.sampleStart();

try {
    String checkoutUrl = "http://" + WDS.vars.get("BASE_URL") + ":" + WDS.vars.get("PORT") + "/cart/checkout";
    WDS.browser.get(checkoutUrl);
    
    String pageSource = WDS.browser.getPageSource();
    
    if (pageSource.length() == 0) {
        WDS.sampleResult.setSuccessful(false);
        WDS.sampleResult.setResponseMessage("Checkout page did not load");
    } else {
        WDS.sampleResult.setSuccessful(true);
        WDS.sampleResult.setResponseMessage("Checkout page loaded successfully");
    }
    
    WDS.log.info("[Checkout] Response Time: " + WDS.sampleResult.getTime() + "ms");
    
} catch (Exception e) {
    WDS.sampleResult.setSuccessful(false);
    WDS.sampleResult.setResponseMessage("Exception: " + e.getMessage());
}

WDS.sampleResult.sampleEnd();


// ============================================
// 脚本4：商品详情页 (Product)
// ============================================
WDS.sampleResult.sampleStart();

try {
    String productUrl = "http://" + WDS.vars.get("BASE_URL") + ":" + WDS.vars.get("PORT") + "/product/OLJCESPC7Z";
    WDS.browser.get(productUrl);
    
    String pageSource = WDS.browser.getPageSource();
    
    if (pageSource.length() == 0) {
        WDS.sampleResult.setSuccessful(false);
        WDS.sampleResult.setResponseMessage("Product page did not load");
    } else {
        WDS.sampleResult.setSuccessful(true);
        WDS.sampleResult.setResponseMessage("Product page loaded successfully");
    }
    
    WDS.log.info("[Product] Response Time: " + WDS.sampleResult.getTime() + "ms");
    
} catch (Exception e) {
    WDS.sampleResult.setSuccessful(false);
    WDS.sampleResult.setResponseMessage("Exception: " + e.getMessage());
}

WDS.sampleResult.sampleEnd();
