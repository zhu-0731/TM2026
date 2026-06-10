# OnlineBoutique 微服务性能测试 - 功能覆盖说明

## 项目架构

OnlineBoutique 是一个由 Google 开源的微服务演示项目，包含以下核心服务：

| 微服务 | 功能 | 对应测试请求 |
|--------|------|-------------|
| **frontend** | 前端服务，处理所有HTTP请求 | 所有请求的入口 |
| **productcatalogservice** | 商品目录服务 | GET /product/{id} |
| **cartservice** | 购物车服务 | POST /cart, GET /cart |
| **checkoutservice** | 结算服务 | POST /cart/checkout |
| **currencyservice** | 货币转换服务 | POST /setCurrency |
| **recommendationservice** | 推荐服务 | GET / (首页推荐) |
| **adservice** | 广告服务 | GET / (首页广告) |
| **shippingservice** | 配送服务 | POST /cart/checkout |
| **emailservice** | 邮件服务 | POST /cart/checkout |
| **paymentservice** | 支付服务 | POST /cart/checkout |

---

## 测试覆盖的功能场景

### 场景1：用户浏览商品（Browse Products）

```
用户行为：访问首页 → 浏览商品详情
对应请求：
  1. GET /              → 加载首页（Frontend + Recommendation + Ad）
  2. GET /product/OLJCESPC7Z  → 查看商品详情（ProductCatalog）
```

**测试的微服务交互：**
- frontend 接收请求
- productcatalogservice 返回商品信息
- recommendationservice 返回相关推荐
- adservice 返回广告内容

---

### 场景2：切换货币（Switch Currency）

```
用户行为：在页面上选择不同货币
对应请求：
  1. POST /setCurrency (currency_code=EUR)  → 切换为欧元
  2. POST /setCurrency (currency_code=USD)  → 切换为美元
  3. POST /setCurrency (currency_code=JPY)  → 切换为日元
```

**支持的货币：** EUR, USD, JPY, GBP, TRY, CAD

**测试的微服务交互：**
- frontend 接收请求
- currencyservice 进行货币转换计算

---

### 场景3：添加购物车（Add to Cart）

```
用户行为：在商品页点击"Add To Cart"
对应请求：
  1. GET /product/OLJCESPC7Z   → 先访问商品页
  2. POST /cart (product_id=OLJCESPC7Z, quantity=1)  → 添加到购物车
```

**测试的微服务交互：**
- frontend 接收请求
- cartservice 存储购物车数据（Redis）

---

### 场景4：查看购物车（View Cart）

```
用户行为：点击购物车图标
对应请求：
  1. GET /cart  → 查看购物车内容
```

**测试的微服务交互：**
- frontend 接收请求
- cartservice 读取购物车数据
- productcatalogservice 获取商品详情
- currencyservice 计算总价

---

### 场景5：下单结算（Place Order）

```
用户行为：填写订单信息并提交
对应请求：
  1. GET /cart              → 先查看购物车
  2. POST /cart/checkout    → 提交订单
     参数：
     - email: test@example.com
     - street_address: 1600 Amphitheatre Parkway
     - zip_code: 94043
     - city: Mountain View
     - state: CA
     - country: United States
     - credit_card_number: 4432801561520454
     - credit_card_expiration_month: 12
     - credit_card_expiration_year: 2027
     - credit_card_cvv: 672
```

**测试的微服务交互（最复杂的调用链）：**
```
frontend → checkoutservice → cartservice (获取购物车)
                         → productcatalogservice (获取商品)
                         → currencyservice (货币转换)
                         → shippingservice (计算运费)
                         → paymentservice (处理支付)
                         → emailservice (发送确认邮件)
```

---

## 商品列表（9个商品）

| 商品ID | 商品名称 | 价格 |
|--------|---------|------|
| OLJCESPC7Z | Sunglasses | $19.99 |
| 66VCHSJNUP | Tank Top | $18.99 |
| 1YMWWN1N4O | Watch | $109.99 |
| L9ECAV7KIM | Loafers | $89.99 |
| 2ZYFJ3GM2N | Hairdryer | $24.99 |
| 0PUK6V6EV0 | Candle Holder | $18.99 |
| LS4PSXUNUM | Salt & Pepper Shakers | $18.49 |
| 9SIQT8TOJO | Bamboo Glass Jar | $5.49 |
| 6E92ZMYYFZ | Mug | $8.99 |

---

## 测试场景设计

### 场景一：基准测试（10用户）
- **模拟行为**：正常用户浏览、加购、下单
- **线程数**：10
- **Ramp-up**：30秒
- **循环**：10次
- **持续时间**：300秒
- **覆盖功能**：首页、商品详情、货币切换、加购、查看购物车、下单

### 场景二：负载测试（50用户）
- **模拟行为**：中等并发用户同时访问
- **线程数**：50
- **Ramp-up**：60秒
- **循环**：20次
- **持续时间**：600秒
- **覆盖功能**：首页、商品详情、加购、查看购物车、下单

### 场景三：压力测试（100用户）
- **模拟行为**：高并发压力测试
- **线程数**：100
- **Ramp-up**：120秒
- **循环**：30次
- **持续时间**：600秒

### 场景四：峰值测试（200用户）
- **模拟行为**：突发流量峰值
- **线程数**：200
- **Ramp-up**：180秒
- **循环**：50次
- **持续时间**：300秒

---

## 性能监控指标

| 指标 | 说明 | 采集方式 |
|------|------|---------|
| 响应时间 (Response Time) | 从请求到响应的总时间 | JMeter自动采集 |
| 延迟 (Latency) | 服务器处理时间 | JMeter自动采集 |
| 连接时间 (Connect Time) | TCP连接建立时间 | JMeter自动采集 |
| 吞吐量 (Throughput) | 每秒处理请求数 | JMeter聚合报告 |
| 错误率 (Error Rate) | 失败请求占比 | JMeter断言统计 |
| 发送字节 (Sent Bytes) | 请求数据大小 | JMeter自动采集 |
| 接收字节 (Received Bytes) | 响应数据大小 | JMeter自动采集 |

---

## 断言验证

| 断言类型 | 验证内容 | 作用 |
|---------|---------|------|
| Response Assertion | HTTP状态码 = 200 | 验证请求成功 |
| Duration Assertion | 响应时间 < 2000ms | 验证性能达标 |

---

## 为什么这样设计测试？

1. **覆盖完整用户旅程**：从浏览到下单的完整购物流程
2. **覆盖所有微服务**：每个请求都会触发不同的后端服务
3. **模拟真实场景**：包含思考时间（Gaussian Random Timer）
4. **Cookie关联**：使用Cookie Manager保持会话，确保购物车功能正常
5. **多场景对比**：从基准到峰值，逐步加压测试系统极限
