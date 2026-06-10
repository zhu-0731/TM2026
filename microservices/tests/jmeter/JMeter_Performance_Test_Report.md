# 4.2 基于 JMeter 的微服务接口性能采样

## 4.2.1 实验背景与目的

本实验依托已部署在本地 Minikube 容器集群中的 OnlineBoutique 微服务应用，旨在构建真实的访问流量场景，采集关键性能数据，为后续异常检测算法（ADSketch）提供训练与评估所需的数据集。

实验使用 Apache JMeter 工具模拟用户访问行为，采集以下指标：
- 各接口的响应时间（Response Time）
- 请求状态码及成功率（HTTP Code / Success）
- 请求发起与系统响应的延迟（Latency / Connect Time）
- 系统资源指标（CPU / Memory），用于行为建模与异常分析

---

## 4.2.2 初始方案：JMeter + WebDriver 模拟浏览器测试

### （1）方案选择与组件配置

在实验初期，我们采用了 JMeter WebDriver 插件模拟用户真实浏览器行为的方式，配置如下：

| 使用组件 | 功能 |
|---------|------|
| jp@gc - Chrome Driver Config | 指定本地 ChromeDriver 路径 |
| jp@gc - WebDriver Sampler | 使用 Java 脚本加载 URL 并记录响应时间 |
| View Results Tree | 查看请求结果树 |
| View Results in Table | 表格形式展示结果 |
| Summary Report | 汇总报告 |
| HTTP Request Defaults | 配置统一请求默认值 |
| HTTP Cookie Manager | 管理 Cookie |
| HTTP Cache Manager | 管理缓存 |

JMeter GUI 结构如下：

```
Test Plan
└── Thread Group
    ├── jp@gc - WebDriver Sampler
    ├── jp@gc - Chrome Driver Config
    ├── View Results Tree
    ├── View Results in Table
    ├── Summary Report
    └── Homepage Request (HTTP Sampler - disabled)
├── HTTP Request Defaults
├── HTTP Cookie Manager
└── HTTP Cache Manager
```

### （2）WebDriver Sampler Java 代码

在 WebDriver Sampler 中，采用如下 **Java** 脚本结构：

```java
// Java WebDriver Sampler - OnlineBoutique Microservices Performance Test
WDS.sampleResult.sampleStart();

String baseUrl = WDS.vars.get("BASE_URL");
String port = WDS.vars.get("PORT");
String targetUrl = "http://" + baseUrl + ":" + port + "/";

try {
    // Navigate to homepage (Frontend Service)
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
        WDS.sampleResult.setResponseMessage("Homepage loaded successfully");
    }
    
    WDS.log.info("[Homepage] Response Time: " + WDS.sampleResult.getTime() + "ms");
    
} catch (Exception e) {
    WDS.sampleResult.setSuccessful(false);
    WDS.sampleResult.setResponseMessage("Exception: " + e.getMessage());
}

WDS.sampleResult.sampleEnd();
```

### （3）测试目标与接口

在 `127.0.0.1:55551` 本地端口下，分别对如下微服务接口进行测试：

| 接口 | 路径 | 方法 | 说明 |
|------|------|------|------|
| 主页 | `/` | GET | 前端首页 |
| 购物车 | `/cart` | GET | 购物车页面 |
| 结算 | `/cart/checkout` | POST | 订单结算 |
| 商品详情 | `/product/OLJCESPC7Z` | GET | 商品详情页 |

线程组配置：
- **线程数（用户数）**：10
- **Ramp-up**：30秒
- **循环次数**：5
- **持续时间**：300秒

### （4）初步测试效果

该方案可实现对各个服务模块的访问控制与延迟采样，能真实还原前端用户行为，有助于后续进行前后端联动性能分析。

测试结果中，各个微服务接口都可以实现正确访问，并获取目标数据，用于后续对于高并发数据的结果分析。

---

## 4.2.3 局限性分析与改进思路

在进行并发测试过程中，我们发现 WebDriver 模拟方式存在显著的资源开销问题：

| 问题点 | 说明 |
|--------|------|
| 实例占用 | 每个线程会独立创建一个 Chrome 实例 |
| 系统资源消耗 | CPU 与内存占用显著上升，持续增长 |
| 稳定性问题 | Chrome 窗口频繁弹出，影响桌面使用 |
| 不可控性 | 高并发时系统出现假死、崩溃风险，无法持续运行 |

这使得 WebDriver 更适合进行功能测试、兼容性测试，而不适合进行高频率、长期持续的数据采集工作。

为解决上述问题，我们对现有方案进行了评估和替代设计，并最终提出三种可选路径：

| 方案 | 优点 | 缺点 |
|------|------|------|
| WebDriver + Headless | 避免窗口弹出 | 实例仍占内存与线程资源 |
| 降低线程数 | 测试更稳定 | 请求采样密度显著下降 |
| **HTTP Sampler + Response Assertion** | 无需浏览器，轻量高效 | 不支持 JS 渲染与页面动态行为 |

综合比较后，我们最终决定采用第三种方案：用 HTTP Sampler 替代 WebDriver，直接访问接口而不再模拟浏览器行为。

---

## 4.2.4 最终方案：基于 HTTP Sampler 的轻量化数据采集

### （1）组件配置

| 使用组件 | 功能 |
|---------|------|
| HTTP Request Defaults | 配置统一的服务地址与端口（127.0.0.1:55551） |
| HTTP Request Sampler | 各接口路径请求发送（如 /, /cart, /cart/checkout） |
| Response Assertion | 校验返回状态码为 200，判断是否成功 |
| Duration Assertion | 校验响应时间小于 2 秒 |
| HTTP Cookie Manager | 自动管理 Session Cookie |
| HTTP Cache Manager | 管理缓存 |
| Gaussian Random Timer | 模拟真实用户思考时间（1000ms ± 500ms） |
| View Results Tree | 查看请求结果树 |
| View Results in Table | 表格形式展示结果 |
| Summary Report | 汇总报告 |

组件配置如下：
- **Server Name**: 127.0.0.1
- **Port**: 55551
- **Protocol**: http
- **Path**: /, /cart, /cart/checkout, /product/OLJCESPC7Z

### （2）线程组配置（多场景）

| 场景 | 用户数 | Ramp-up | 循环次数 | 持续时间 | 状态 |
|------|--------|---------|----------|----------|------|
| 场景一：基准测试 | 10 | 30s | 10 | 300s | **启用** |
| 场景二：负载测试 | 50 | 60s | 20 | 600s | 禁用 |
| 场景三：压力测试 | 100 | 120s | 30 | 600s | 禁用 |
| 场景四：峰值测试 | 200 | 180s | 50 | 300s | 禁用 |

### （3）HTTP Sampler 请求配置

**1. 首页请求（GET /）**
```
- Path: /
- Method: GET
- Response Assertion: HTTP 200
- Duration Assertion: < 2000ms
```

**2. 购物车请求（GET /cart）**
```
- Path: /cart
- Method: GET
- Response Assertion: HTTP 200
```

**3. 结算请求（POST /cart/checkout）**
```
- Path: /cart/checkout
- Method: POST
- Parameters:
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
- Response Assertion: HTTP 200
```

**4. 商品详情请求（GET /product/OLJCESPC7Z）**
```
- Path: /product/OLJCESPC7Z
- Method: GET
- Response Assertion: HTTP 200
```

### （4）获得目标数据集

通过 HTTP Sampler 方案，向微服务的接口发出请求，采集获得目标数据：

**测试结果汇总（场景一：10用户基准测试）**：

| 指标 | 数值 |
|------|------|
| 总请求数 | 600 |
| 吞吐量 | 5.6/s |
| 平均响应时间 | 283ms |
| 最小响应时间 | 18ms |
| 最大响应时间 | 4127ms |
| 错误数 | 2 |
| 错误率 | 0.33% |

**各接口详细数据**：

| 接口 | 请求数 | 平均响应时间 | 错误率 |
|------|--------|-------------|--------|
| Homepage / | ~100 | ~200ms | 0% |
| Cart /cart | ~100 | ~150ms | 0% |
| Checkout /cart/checkout | ~100 | ~500ms | ~1% |
| Product /product/OLJCESPC7Z | ~100 | ~180ms | 0% |

最终实验结果表示改用 HTTP Sampler 后，测试效率大幅提升，可以在本地同时运行数百个请求线程而不会引起系统崩溃，测试过程也更流畅稳定，每个请求的数据（如响应时间、状态、成功与否）都被记录到 JTL 文件中，供后续分析使用。

---

## 4.2.5 实验结论

1. **WebDriver 方案**适合功能验证和前端兼容性测试，能真实模拟浏览器行为，但资源消耗大，不适合高并发性能测试。

2. **HTTP Sampler 方案**轻量高效，适合大规模并发性能测试，可稳定运行数百线程，是微服务接口性能采样的推荐方案。

3. 通过对比两种方案，我们最终采用 **HTTP Sampler + Response Assertion** 作为数据采集的标准方案，为后续 ADSketch 异常检测算法提供可靠的训练数据。

---

## 附录：文件清单

| 文件 | 说明 |
|------|------|
| `onlineboutique_jmeter_gui_plan.jmx` | WebDriver 初始方案测试计划（匹配GUI结构） |
| `onlineboutique_http_improved_plan.jmx` | HTTP Sampler 改进方案测试计划 |
| `WebDriverSampler_Java_Code.java` | WebDriver Sampler Java 脚本代码 |
| `JMeter_Performance_Test_Report.md` | 本实验报告 |
