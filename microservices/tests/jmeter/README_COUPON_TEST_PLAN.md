# OnlineBoutique 完整性能测试计划（含优惠券功能）

## 测试计划文件

- `onlineboutique_complete_with_coupon.jmx` - 完整测试计划（HTTP Sampler）
- `webdriver_test_plan.jmx` - WebDriver 测试计划（Java）

## 测试场景概览

### Scenario 1: User Browse Flow（用户浏览流）- 已启用
- **并发用户**: 10
- **Ramp-up**: 30秒
- **持续时间**: 300秒
- **循环次数**: 10次/用户
- **覆盖服务**: Frontend, Recommendation, Ad, Currency, ProductCatalog, Cart, Checkout, Payment, Shipping, Email
- **测试步骤**:
  1. 访问首页 `/` (GET)
  2. 设置货币 `/setCurrency` (POST, EUR)
  3. 查看商品详情 `/product/OLJCESPC7Z` (GET)
  4. 添加商品到购物车 `/cart` (POST)
  5. 查看购物车 `/cart` (GET)
  6. 提交订单 `/cart/checkout` (POST, 含 SAVE10 优惠券)

### Scenario 2: Coupon Test - Percent Discount（百分比折扣）- 已禁用
- **并发用户**: 20
- **Ramp-up**: 45秒
- **持续时间**: 400秒
- **循环次数**: 15次/用户
- **优惠券**: SAVE20 (20% off)
- **测试步骤**:
  1. 添加商品到购物车
  2. 使用 SAVE20 优惠券结账

### Scenario 3: Coupon Test - Fixed Discount（固定金额折扣）- 已禁用
- **并发用户**: 20
- **Ramp-up**: 45秒
- **持续时间**: 400秒
- **循环次数**: 15次/用户
- **优惠券**: OFF15 ($15 off)
- **测试步骤**:
  1. 添加多件商品到购物车
  2. 使用 OFF15 优惠券结账

### Scenario 4: Coupon Test - Free Shipping（免运费）- 已禁用
- **并发用户**: 20
- **Ramp-up**: 45秒
- **持续时间**: 400秒
- **循环次数**: 15次/用户
- **优惠券**: FREESHIP
- **测试步骤**:
  1. 添加商品到购物车
  2. 使用 FREESHIP 优惠券结账

## 全局配置

### 用户自定义变量
- `BASE_URL`: 127.0.0.1
- `PORT`: 55551

### HTTP 请求默认值
- 协议: http
- 域名: `${BASE_URL}`
- 端口: `${PORT}`
- 并发连接池: 6

### 其他管理器
- HTTP Cookie Manager（自动处理 Session）
- HTTP Cache Manager
- HTTP Header Manager（User-Agent, Accept）

## 断言与验证

每个 HTTP 请求包含：
- **Response Assertion**: 验证 HTTP 200 状态码
- **Duration Assertion**: 首页响应时间 < 2秒

## 监控指标

每个场景包含：
- **View Results Tree**（GUI 调试用）
- **View Results in Table**（GUI 调试用）
- **Summary Report**（吞吐量、平均响应时间等）
- **Aggregate Report**（聚合统计）
- **Response Time Graph**（响应时间图表）

## 使用步骤

### 1. 更新服务地址
在 JMeter GUI 中：
1. 打开 `onlineboutique_complete_with_coupon.jmx`
2. 在 **Test Plan > User Defined Variables** 中更新：
   - `BASE_URL`: 你的 Minikube 服务 IP（如 127.0.0.1）
   - `PORT`: 你的 Minikube 服务端口（如 55551）

获取当前端口：
```bash
minikube service frontend-external --url -n default
```

### 2. GUI 验证（可选）
1. 启动 JMeter GUI
2. 打开测试计划
3. 选择 **Scenario 1**，点击运行按钮
4. 在 **View Results Tree** 中验证请求是否成功

### 3. 设置线程数
根据需要调整各场景的并发数：
- **Scenario 1**: 10 用户（基线测试）
- **Scenario 2-4**: 20 用户（优惠券压力测试）

### 4. CLI 执行
```bash
# 基线测试（Scenario 1）
jmeter -n -t onlineboutique_complete_with_coupon.jmx -l results/baseline.jtl

# 优惠券百分比折扣测试（启用 Scenario 2）
# 在 GUI 中启用 Scenario 2，禁用其他场景，然后：
jmeter -n -t onlineboutique_complete_with_coupon.jmx -l results/coupon_percent.jtl

# 生成 HTML 报告
jmeter -g results/baseline.jtl -o results/html_report
```

## 优惠券代码参考

| 优惠码 | 类型 | 折扣 | 最低订单金额 |
|--------|------|------|-------------|
| SAVE10 | percent | 10% | - |
| SAVE20 | percent | 20% | - |
| WELCOME20 | percent | 20% | - |
| OFF5 | fixed | $5 | - |
| OFF15 | fixed | $15 | - |
| FREESHIP | shipping | 免运费 | - |

## 测试结果分析

### 关键指标
- **吞吐量 (Throughput)**: 每秒处理的请求数
- **平均响应时间**: 所有请求的平均响应时间
- **错误率**: 失败请求百分比
- **90% Line**: 90% 请求的响应时间低于此值

### 预期结果
- 错误率应接近 0%
- 首页响应时间 < 2秒
- 购物车/结账响应时间 < 5秒

## 故障排除

### 服务连接失败
- 确认 Minikube 服务正在运行
- 检查 `BASE_URL` 和 `PORT` 配置
- 验证防火墙设置

### 优惠券测试失败
- 确认 couponservice 正在运行
- 检查优惠券代码是否正确
- 验证最低订单金额要求

### JMeter 内存不足
编辑 `jmeter.bat`，增加 JVM 内存：
```bash
set HEAP=-Xms2g -Xmx4g
```
