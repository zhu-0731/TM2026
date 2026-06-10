# OnlineBoutique 微服务系统测试实践 - PPT草稿框架

---

## 第1页：封面

**标题**：OnlineBoutique 微服务系统性能测试与故障注入实践

**副标题**：基于 JMeter、Selenium、ChaosMesh 的全链路测试与监控

**内容**：
- 项目名称：OnlineBoutique 微服务电商平台
- 技术栈：Kubernetes + Minikube + JMeter + Selenium + ChaosMesh + Prometheus + Grafana
- 报告人信息

**展示内容**：
- 项目Logo（OnlineBoutique图标）
- 微服务架构简图

---

## 第2页：项目背景与目标

**标题**：项目背景与实验目标

**内容**：
- **背景**：微服务架构已成为现代应用开发的主流，但分布式系统带来了复杂的测试挑战
- **目标**：
  1. 部署完整的微服务电商系统（OnlineBoutique）
  2. 使用 JMeter 进行多场景性能测试
  3. 使用 Selenium 进行端到端功能测试
  4. 使用 ChaosMesh 进行故障注入
  5. 使用 Prometheus + Grafana 进行监控可视化

**展示内容**：
- 微服务 vs 单体架构对比图
- 实验流程图：部署 → 测试 → 故障注入 → 监控

---

## 第3页：OnlineBoutique 系统介绍

**标题**：OnlineBoutique 微服务系统架构

**内容**：
- **项目来源**：Google Cloud 开源微服务演示项目
- **业务场景**：在线精品店，支持商品浏览、购物车、结账、优惠券等功能
- **技术栈**：
  - 前端：Go (Frontend)
  - 后端：Go + Python (gRPC)
  - 部署：Kubernetes + Minikube

**微服务列表（11个服务）**：
| 服务名 | 语言 | 功能 |
|--------|------|------|
| Frontend | Go | 前端网关，聚合所有服务 |
| RecommendationService | Go | 商品推荐 |
| AdService | Go | 广告投放 |
| ProductCatalogService | Go | 商品目录管理 |
| CurrencyService | Go | 货币转换 |
| CartService | Go | 购物车管理 |
| CheckoutService | Go | 结账流程编排 |
| PaymentService | Go | 支付处理 |
| ShippingService | Go | 物流计算 |
| EmailService | Go | 邮件通知 |
| CouponService | Python | 优惠券验证与应用 |

**展示内容**：
- 微服务架构拓扑图
- 服务间调用关系图（Frontend → 各后端服务）
- 数据流图：用户请求 → Frontend → gRPC → 各Service

---

## 第4页：系统部署展示

**标题**：系统部署与运行状态

**内容**：
- **部署环境**：Minikube v1.38.1（本地Kubernetes集群）
- **部署命令**：
  ```bash
  minikube start
  kubectl apply -f kubernetes-manifests/
  minikube service frontend-external --url
  ```
- **运行状态**：所有11个服务正常运行

**展示内容**：
- Minikube 集群状态截图：`minikube status`
- Pod 运行状态截图：`kubectl get pods`
- Service 暴露截图：`kubectl get services`
- 系统首页截图（浏览器访问 http://127.0.0.1:PORT/）

---

## 第5页：优惠券功能开发（如有）

**标题**：优惠券功能开发与集成

**内容**：
- **功能说明**：新增 CouponService 微服务，支持6种优惠码
- **优惠码列表**：
  | 优惠码 | 类型 | 折扣 |
  |--------|------|------|
  | SAVE10 | 百分比 | 9折 |
  | SAVE20 | 百分比 | 8折 |
  | WELCOME20 | 百分比 | 新用户8折 |
  | OFF5 | 固定金额 | 减$5 |
  | OFF15 | 固定金额 | 减$15 |
  | FREESHIP | 免运费 | 运费$0 |

- **服务交互**：
  ```
  Frontend → CheckoutService → CouponService (gRPC)
                              → PaymentService
                              → ShippingService
                              → EmailService
  ```

**展示内容**：
- CouponService 代码截图（Python FastAPI）
- 优惠券应用流程图
- 前端购物车页面截图（含优惠券输入框）
- 订单确认页面截图（显示折扣信息）

---

## 第6页：Selenium 自动化测试

**标题**：Selenium 端到端功能测试

**内容**：
- **测试目标**：验证系统核心业务流程在Chrome/Edge/Firefox浏览器中的正确性
- **测试场景**：
  1. 用户浏览首页
  2. 查看商品详情
  3. 添加商品到购物车
  4. 应用优惠券
  5. 填写订单信息并结账
  6. 验证订单确认页面

- **测试结果**：
  | 浏览器 | 测试用例 | 通过 | 失败 |
  |--------|---------|------|------|
  | Chrome | 14 | 14 | 0 |
  | Edge | 14 | 14 | 0 |
  | Firefox | 14 | 14 | 0 |

**展示内容**：
- Selenium 测试代码截图
- 三浏览器测试执行截图
- 测试报告截图（14/14全部通过）
- 浏览器中订单确认页面截图

---

## 第7页：JMeter 性能测试设计

**标题**：JMeter 性能测试计划设计

**内容**：
- **测试工具**：Apache JMeter 5.6.3
- **测试场景**：5个ThreadGroup覆盖不同负载

| 场景 | 并发用户 | Ramp-up | 持续时间 | 负载类型 |
|------|---------|---------|---------|---------|
| S1-基线 | 5 | 10s | 60s | 低并发验证 |
| S2-负载 | 20 | 30s | 180s | 日常负载 |
| S3-压力 | 30 | 45s | 180s | 压力测试 |
| S4-峰值 | 50 | 10s | 90s | 峰值测试 |
| S5-优惠券 | 10 | 20s | 120s | 优惠券专项 |

- **覆盖接口**：首页、货币设置、商品详情、购物车、结账（含优惠券）
- **监控组件**：Summary Report、Aggregate Report、Response Time Graph、Throughput Graph

**展示内容**：
- JMeter 测试计划结构图
- ThreadGroup配置截图
- HTTP Sampler配置截图

---

## 第8页：JMeter 性能测试结果

**标题**：性能测试结果与分析

**内容**：
- **总体统计**：
  | 指标 | 数值 |
  |------|------|
  | 总请求数 | 3,408 |
  | 错误数 | 37 |
  | **错误率** | **1.09%** |
  | 平均响应时间 | 1,733 ms |
  | 中位数响应时间 | 1,566 ms |
  | 最大响应时间 | 7,583 ms |
  | 吞吐量 | 32.01 req/s |

- **各场景结果**：
  | 场景 | 并发 | 错误率 | 平均RT | 吞吐量 |
  |------|------|--------|--------|--------|
  | S1-基线 | 5 | 22.73% | 1,972ms | 1.51/s |
  | S2-负载 | 20 | **1.83%** | 1,636ms | 5.83/s |
  | S3-压力 | 30 | **0.38%** | 1,483ms | 15.06/s |
  | S4-峰值 | 50 | **0.00%** | 3,015ms | 23.74/s |
  | S5-优惠券 | 10 | **0.00%** | 1,627ms | 8.33/s |

**展示内容**：
- JMeter Summary Report 截图
- JMeter Aggregate Report 截图
- 各场景对比柱状图

---

## 第9页：性能测试图表分析

**标题**：Throughput Graph 性能分析

**内容**：
- **图像关键指标**：
  | 指标 | 数值 |
  |------|------|
  | No of Samples | 3,406 |
  | Average | 1,745 ms |
  | Median | 1,212 ms |
  | Deviation | 1,829 ms |
  | Throughput | 1,920.635/min |

- **曲线分析**：
  - 蓝色线 (Average)：平均响应时间约1,745ms，预热后趋于平稳
  - 紫色线 (Median)：中位数1,212ms，低于平均值，大多数请求响应良好
  - 红色线 (Deviation)：标准差1,829ms，波动主要来自峰值场景
  - 绿色线 (Throughput)：吞吐量约32 req/s，保持稳定
  - 黄色散点：集中在0-3,000ms区间

- **结论**：
  1. 平均响应时间在可接受范围（<3,000ms）
  2. 50%以上请求响应优于平均水平
  3. 系统在高并发下可持续处理请求
  4. 错误率仅1.09%，稳定性良好

**展示内容**：
- **Throughput Graph 截图**（你提供的那张图）
- 响应时间分布柱状图

---

## 第10页：WebDriver Sampler 代码展示

**标题**：JMeter WebDriver Sampler 浏览器级测试

**内容**：
- **技术方案**：JMeter + WebDriver插件 + ChromeDriver
- **测试语言**：Java / Groovy
- **测试流程**：
  1. 启动Chrome浏览器（无头模式）
  2. 访问首页并验证页面元素
  3. 选择商品并添加到购物车
  4. 输入优惠券码（SAVE10）
  5. 填写结账表单
  6. 提交订单并验证结果

**展示内容**：
- Chrome Driver Config 配置截图
- WebDriver Sampler Java代码截图
- WebDriver Sampler Groovy代码截图
- jp@gc插件安装截图

---

## 第11页：ChaosMesh 故障注入

**标题**：ChaosMesh 故障注入实验

**内容**：
- **工具介绍**：ChaosMesh 是云原生混沌工程平台，用于模拟系统故障
- **实验场景**：
  | 故障类型 | 目标服务 | 注入参数 |
  |---------|---------|---------|
  | CPU压力 | Frontend | 100% CPU，持续5分钟 |
  | 内存压力 | CartService | 内存占用80%，持续5分钟 |
  | 网络延迟 | CheckoutService | 延迟100ms，持续5分钟 |
  | Pod杀死 | CouponService | 随机杀死Pod |

- **实验目的**：验证系统在故障下的容错能力和恢复能力

**展示内容**：
- ChaosMesh 架构图
- 故障注入YAML配置截图
- Chaos Dashboard 截图
- 实验流程图

---

## 第12页：Prometheus + Grafana 监控

**标题**：系统监控与可视化

**内容**：
- **监控方案**：
  - Prometheus：指标采集与存储
  - Grafana：可视化仪表盘
  - JMeter Backend Listener：测试指标推送

- **监控指标**：
  | 指标类型 | 具体指标 |
  |---------|---------|
  | 应用指标 | QPS、响应时间、错误率 |
  | 资源指标 | CPU、内存、网络、磁盘 |
  | 业务指标 | 订单量、购物车数量、优惠券使用 |

**展示内容**：
- Prometheus 配置截图
- Grafana 仪表盘截图（含多个面板）
- 系统资源监控图（CPU、内存）
- 应用性能监控图（QPS、响应时间）

---

## 第13页：故障注入与监控联动

**标题**：故障注入期间的系统表现

**内容**：
- **实验过程**：
  1. 正常状态：系统运行平稳，错误率<2%
  2. 注入CPU压力（Frontend）：响应时间上升，吞吐量下降
  3. 注入网络延迟（Checkout）：结账接口超时增加
  4. 杀死CouponService Pod：优惠券功能短暂不可用
  5. 恢复后：系统自动恢复，指标回归正常

- **关键发现**：
  - Frontend在CPU压力下仍能保持服务（降级处理）
  - CheckoutService网络延迟影响订单提交成功率
  - CouponService Pod被杀死后，Kubernetes自动重启恢复

**展示内容**：
- 故障注入时间线图表
- Grafana监控曲线（故障前后对比）
  - CPU使用率突增截图
  - 响应时间上升截图
  - 错误率波动截图
- Kubernetes Pod重启截图

---

## 第14页：问题发现与优化建议

**标题**：测试发现的问题与优化方案

**内容**：
- **发现的问题**：
  | 问题 | 影响 | 根因 |
  |------|------|------|
  | S1基线断言失败率高 | 22.73% | Duration Assertion阈值过严 |
  | 峰值场景响应时间长 | 3,015ms | 50并发超出系统最优负载 |
  | 优惠券服务偶发500 | 早期测试 | 高并发下数据库连接不足 |

- **优化建议**：
  1. **系统层面**：增加CheckoutService/CouponService副本数，引入Redis缓存
  2. **配置层面**：调整断言阈值，增加预热阶段
  3. **架构层面**：添加熔断降级机制（Hystrix/Resilience4j）
  4. **监控层面**：完善告警规则，实现自动扩缩容

**展示内容**：
- 问题对比表格
- 优化前后数据对比
- 熔断器代码示例

---

## 第15页：实验总结与收获

**标题**：实验总结与技术收获

**内容**：
- **实验成果**：
  1. 成功部署11个微服务的完整电商系统
  2. JMeter性能测试：5场景、3400+请求、1.09%错误率
  3. Selenium端到端测试：3浏览器、42用例、100%通过
  4. ChaosMesh故障注入：4种故障场景
  5. Prometheus+Grafana：完整监控体系

- **技术收获**：
  - 微服务架构设计与部署实践
  - 性能测试工具链（JMeter + WebDriver）
  - 混沌工程与故障注入方法
  - 云原生监控体系搭建

- **后续计划**：
  - 引入服务网格（Istio）进行流量管理
  - 实现自动扩缩容（HPA）
  - 完善分布式链路追踪（Jaeger）

**展示内容**：
- 实验成果汇总图
- 技术栈全景图
- 团队合影（如有）

---

## 第16页：Q&A / 结束页

**标题**：Q&A

**内容**：
- 感谢聆听
- 联系方式
- 项目开源地址：https://github.com/GoogleCloudPlatform/microservices-demo

**展示内容**：
- 项目GitHub二维码
- 联系方式

---

## 附录：每页PPT建议的图表/截图清单

| 页码 | 必须展示 | 可选补充 |
|------|---------|---------|
| 1 | 项目Logo | 学校/公司Logo |
| 2 | 实验流程图 | 技术栈图标 |
| 3 | 微服务架构图 | 服务调用链图 |
| 4 | Pod状态截图 | Service列表截图 |
| 5 | 优惠券页面截图 | 代码片段 |
| 6 | Selenium报告截图 | 三浏览器对比 |
| 7 | JMeter结构图 | 配置详情 |
| 8 | Summary Report | Aggregate Report |
| 9 | **Throughput Graph** | 响应时间分布图 |
| 10 | WebDriver代码 | ChromeDriver配置 |
| 11 | Chaos Dashboard | 故障YAML |
| 12 | Grafana仪表盘 | Prometheus Targets |
| 13 | 故障前后对比图 | Pod重启日志 |
| 14 | 优化对比表 | 架构改进图 |
| 15 | 成果汇总 | 技术收获列表 |
| 16 | 二维码 | 联系方式 |

---

## 备注：演讲时间建议

- 总时长：15-20分钟
- 每页：1-1.5分钟
- 重点页（3、8、9、13）：2分钟
- Q&A：3-5分钟
