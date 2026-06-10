# 阶段二 & 三：监控、故障注入与测试实验报告

## 一、实验环境

- **集群**: Minikube (docker driver)
- **应用**: OnlineBoutique 微服务系统（含 Coupon Service）
- **监控**: Prometheus + Grafana
- **故障注入**: ChaosMesh
- **功能测试**: Selenium
- **性能测试**: JMeter

---

## 二、阶段二：Prometheus & Grafana 监控部署

### 2.1 部署 Prometheus

#### 2.1.1 创建命名空间

```bash
kubectl create namespace monitoring
```

#### 2.1.2 创建 RBAC 权限

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: prometheus
  namespace: monitoring
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: prometheus
rules:
  - apiGroups: [""]
    resources: ["nodes", "nodes/proxy", "services", "endpoints", "pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["extensions"]
    resources: ["ingresses"]
    verbs: ["get", "list", "watch"]
  - nonResourceURLs: ["/metrics"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: prometheus
subjects:
  - kind: ServiceAccount
    name: prometheus
    namespace: monitoring
EOF
```

#### 2.1.3 创建 Prometheus 配置 ConfigMap

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: monitoring
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
      evaluation_interval: 15s

    scrape_configs:
      - job_name: 'prometheus'
        static_configs:
          - targets: ['localhost:9090']

      - job_name: 'kubernetes-pods'
        kubernetes_sd_configs:
          - role: pod
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
            action: replace
            target_label: __metrics_path__
            regex: (.+)
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: \$1:\$2
            target_label: __address__
          - action: labelmap
            regex: __meta_kubernetes_pod_label_(.+)

      - job_name: 'onlineboutique-services'
        kubernetes_sd_configs:
          - role: pod
            namespaces:
              names:
                - default
        relabel_configs:
          - source_labels: [__meta_kubernetes_pod_label_app]
            action: keep
            regex: (frontend|checkoutservice|cartservice|productcatalogservice|currencyservice|paymentservice|shippingservice|emailservice|adservice|recommendationservice|couponservice|loadgenerator)
          - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
            action: keep
            regex: true
          - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
            action: replace
            regex: ([^:]+)(?::\d+)?;(\d+)
            replacement: \$1:\$2
            target_label: __address__
EOF
```

#### 2.1.4 部署 Prometheus

```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      serviceAccountName: prometheus
      containers:
        - name: prometheus
          image: prom/prometheus:v3.2.1
          ports:
            - containerPort: 9090
          volumeMounts:
            - name: config
              mountPath: /etc/prometheus
          args:
            - '--config.file=/etc/prometheus/prometheus.yml'
            - '--storage.tsdb.path=/prometheus'
      volumes:
        - name: config
          configMap:
            name: prometheus-config
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: monitoring
spec:
  type: NodePort
  selector:
    app: prometheus
  ports:
    - port: 9090
      targetPort: 9090
      nodePort: 30090
EOF
```

#### 2.1.5 访问 Prometheus

```bash
# 方式一：port-forward
kubectl port-forward svc/prometheus -n monitoring 9090:9090
# 浏览器访问 http://localhost:9090

# 方式二：minikube service
minikube service prometheus -n monitoring --url
```

### 2.2 部署 Grafana

#### 2.2.1 部署 Grafana

```bash
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: grafana
  template:
    metadata:
      labels:
        app: grafana
    spec:
      containers:
        - name: grafana
          image: grafana/grafana:11.3.1
          ports:
            - containerPort: 3000
          env:
            - name: GF_SECURITY_ADMIN_PASSWORD
              value: "admin"
---
apiVersion: v1
kind: Service
metadata:
  name: grafana
  namespace: monitoring
spec:
  type: NodePort
  selector:
    app: grafana
  ports:
    - port: 3000
      targetPort: 3000
      nodePort: 30030
EOF
```

#### 2.2.2 配置 Prometheus 数据源

1. 访问 Grafana: `minikube service grafana -n monitoring --url`
2. 登录: admin / admin
3. **Configuration** → **Data Sources** → **Add data source**
4. 选择 **Prometheus**
5. URL 填写: `http://prometheus:9090`
6. 点击 **Save & Test**

#### 2.2.3 导入 Dashboard

**方式一：导入官方 Dashboard**
1. **Create** → **Import**
2. Dashboard ID: `747` (Kubernetes 集群监控)
3. 选择 Prometheus 数据源

**方式二：自定义 OnlineBoutique Dashboard**
1. **Create** → **Dashboard** → **Add new panel**
2. 常用监控指标:
   - 请求速率: `rate(http_requests_total[5m])`
   - 响应时间: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`
   - 错误率: `rate(http_requests_total{status=~"5.."}[5m])`
   - CPU 使用率: `rate(container_cpu_usage_seconds_total[5m])`
   - 内存使用: `container_memory_usage_bytes`

### 2.3 为微服务添加监控指标暴露

#### 2.3.1 修改微服务 Deployment 添加 annotations

以 frontend 为例，修改 `kubernetes-manifests/frontend.yaml`:

```yaml
spec:
  template:
    metadata:
      annotations:
        sidecar.istio.io/rewriteAppHTTPProbers: "true"
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
```

**对所有微服务都添加上述 annotations**。

#### 2.3.2 重新部署

```bash
kubectl apply -k kubernetes-manifests/
```

### 2.4 验证监控

```bash
# 查看 Prometheus Targets
kubectl port-forward svc/prometheus -n monitoring 9090:9090
# 浏览器访问 http://localhost:9090/targets
# 确认 onlineboutique-services 下的 Pod 都是 UP 状态
```

---

## 三、阶段二：ChaosMesh 故障注入

### 3.1 安装 ChaosMesh

#### 3.1.1 使用 Helm 安装

```bash
# 添加 ChaosMesh Helm repo
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

# 安装 ChaosMesh
helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-testing \
  --create-namespace \
  --version 2.7.0 \
  --set dashboard.create=true
```

#### 3.1.2 验证安装

```bash
kubectl get pods -n chaos-testing
# 应看到 chaos-controller-manager, chaos-daemon, chaos-dashboard 都在 Running
```

#### 3.1.3 访问 ChaosMesh Dashboard

```bash
kubectl port-forward svc/chaos-dashboard -n chaos-testing 2333:2333
# 浏览器访问 http://localhost:2333
```

### 3.2 故障注入实验

#### 3.2.1 Pod 故障注入（杀死 Pod）

```bash
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: kill-couponservice
  namespace: chaos-testing
spec:
  action: pod-kill
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: couponservice
  scheduler:
    cron: "@every 5m"
EOF
```

#### 3.2.2 网络延迟注入

```bash
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: NetworkChaos
metadata:
  name: delay-checkoutservice
  namespace: chaos-testing
spec:
  action: delay
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: checkoutservice
  delay:
    latency: "500ms"
    correlation: "100"
    jitter: "0ms"
  duration: "5m"
EOF
```

#### 3.2.3 CPU 压力注入

```bash
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: cpu-stress-frontend
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: frontend
  stressors:
    cpu:
      workers: 2
      load: 80
  duration: "5m"
EOF
```

#### 3.2.4 内存压力注入

```bash
cat <<EOF | kubectl apply -f -
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: memory-stress-cartservice
  namespace: chaos-testing
spec:
  mode: one
  selector:
    namespaces:
      - default
    labelSelectors:
      app: cartservice
  stressors:
    memory:
      workers: 2
      size: "256Mi"
  duration: "5m"
EOF
```

### 3.3 观察故障影响

#### 3.3.1 在 Prometheus 中观察指标变化

```bash
# 查看错误率是否上升
rate(http_requests_total{status=~"5.."}[5m])

# 查看响应时间是否增加
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# 查看 Pod 重启次数
kube_pod_container_status_restarts_total
```

#### 3.3.2 在 Grafana 中查看 Dashboard

1. 打开 Grafana Dashboard
2. 观察故障注入期间的指标变化曲线
3. 截图保存作为实验记录

#### 3.3.3 删除故障实验

```bash
kubectl delete podchaos kill-couponservice -n chaos-testing
kubectl delete networkchaos delay-checkoutservice -n chaos-testing
kubectl delete stresschaos cpu-stress-frontend -n chaos-testing
kubectl delete stresschaos memory-stress-cartservice -n chaos-testing
```

---

## 四、阶段三：Selenium 功能测试

### 4.1 环境准备

#### 4.1.1 安装 Python 和依赖

```bash
pip install selenium webdriver-manager
```

#### 4.1.2 下载浏览器驱动

```bash
# ChromeDriver（自动下载）
# 使用 webdriver-manager 自动管理
```

### 4.2 编写 Selenium 测试脚本

创建 `tests/selenium/test_onlineboutique.py`:

```python
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
        options.add_argument('--headless')  # 无头模式
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
        self.test_03_add_to_cart()
        
        # 点击 Place Order
        wait = WebDriverWait(self.driver, 10)
        place_order = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        place_order.click()
        
        # 验证订单完成页
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h3")))
        confirmation = self.driver.find_element(By.TAG_NAME, "h3").text
        
        self.assertIn("complete", confirmation.lower())
        print("无优惠券下单成功")
        
    def test_05_place_order_with_coupon(self):
        """测试使用优惠券下单"""
        # 先添加商品到购物车
        self.test_03_add_to_cart()
        
        # 输入优惠券
        wait = WebDriverWait(self.driver, 10)
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
```

### 4.3 运行 Selenium 测试

```bash
# 确保前端可访问
kubectl port-forward svc/frontend 8080:80 &

# 运行测试
python tests/selenium/test_onlineboutique.py
```

---

## 五、阶段三：JMeter 性能测试

### 5.1 环境准备

#### 5.1.1 下载 JMeter

```bash
# 下载 JMeter 5.6.3
wget https://dlcdn.apache.org//jmeter/binaries/apache-jmeter-5.6.3.zip
unzip apache-jmeter-5.6.3.zip
cd apache-jmeter-5.6.3/bin
```

### 5.2 创建 JMeter 测试计划

#### 5.2.1 使用 GUI 创建测试计划

```bash
./jmeter.sh
```

**测试计划配置**:

1. **Test Plan** → 右键 → **Add** → **Threads (Users)** → **Thread Group**
   - Number of Threads: 100 (虚拟用户数)
   - Ramp-up period: 10 (10秒内启动100个用户)
   - Loop Count: 10 (每个用户循环10次)

2. **Thread Group** → 右键 → **Add** → **Sampler** → **HTTP Request**
   - Name: `Homepage`
   - Protocol: `http`
   - Server Name: `localhost`
   - Port: `8080`
   - Path: `/`

3. **Thread Group** → 右键 → **Add** → **Sampler** → **HTTP Request**
   - Name: `Product Detail`
   - Path: `/product/OLJCESPC7Z`

4. **Thread Group** → 右键 → **Add** → **Sampler** → **HTTP Request**
   - Name: `Cart`
   - Path: `/cart`

5. **Thread Group** → 右键 → **Add** → **Listener** → **View Results Tree**
6. **Thread Group** → 右键 → **Add** → **Listener** → **Summary Report**
7. **Thread Group** → 右键 → **Add** → **Listener** → **Graph Results**

#### 5.2.2 保存测试计划

保存为 `tests/jmeter/onlineboutique_load_test.jmx`

### 5.3 命令行运行 JMeter 测试

```bash
# 非 GUI 模式运行（推荐用于正式测试）
./jmeter.sh -n -t tests/jmeter/onlineboutique_load_test.jmx \
  -l tests/jmeter/results.jtl \
  -e -o tests/jmeter/report

# 参数说明
# -n: 非 GUI 模式
# -t: 测试计划文件
# -l: 结果日志文件
# -e: 测试结束后生成报告
# -o: 报告输出目录
```

### 5.4 关键性能指标

| 指标 | 说明 | 预期值 |
|-----|------|--------|
| Average Response Time | 平均响应时间 | < 500ms |
| 90% Line | 90%请求响应时间 | < 1000ms |
| Throughput | 吞吐量 | > 100/sec |
| Error Rate | 错误率 | < 1% |

### 5.5 不同负载场景测试

#### 5.5.1 低负载测试

```bash
# 50 用户，持续 60 秒
./jmeter.sh -n -t tests/jmeter/onlineboutique_load_test.jmx \
  -Jthreads=50 -Jduration=60 \
  -l tests/jmeter/low_load.jtl
```

#### 5.5.2 中负载测试

```bash
# 200 用户，持续 120 秒
./jmeter.sh -n -t tests/jmeter/onlineboutique_load_test.jmx \
  -Jthreads=200 -Jduration=120 \
  -l tests/jmeter/medium_load.jtl
```

#### 5.5.3 高负载测试

```bash
# 500 用户，持续 300 秒
./jmeter.sh -n -t tests/jmeter/onlineboutique_load_test.jmx \
  -Jthreads=500 -Jduration=300 \
  -l tests/jmeter/high_load.jtl
```

### 5.6 结合 ChaosMesh 进行压力+故障测试

```bash
# 1. 启动 JMeter 高负载测试
./jmeter.sh -n -t tests/jmeter/onlineboutique_load_test.jmx \
  -Jthreads=500 -Jduration=300 \
  -l tests/jmeter/chaos_load.jtl &

# 2. 注入 Pod 故障
kubectl apply -f chaos-experiments/pod-kill-couponservice.yaml

# 3. 观察 JMeter 结果中的错误率和响应时间变化
# 4. 在 Grafana 中观察系统指标变化
```

---

## 六、实验数据收集与分析

### 6.1 Prometheus 数据导出

```bash
# 查询特定时间范围的指标
curl -G 'http://localhost:9090/api/v1/query_range' \
  --data-urlencode 'query=rate(http_requests_total[5m])' \
  --data-urlencode 'start=2026-06-02T00:00:00Z' \
  --data-urlencode 'end=2026-06-02T01:00:00Z' \
  --data-urlencode 'step=15s'
```

### 6.2 Grafana 截图保存

1. 打开 Grafana Dashboard
2. 选择时间范围（故障注入前后各5分钟）
3. 截图保存关键面板:
   - 请求速率
   - 响应时间
   - 错误率
   - CPU/内存使用率

### 6.3 JMeter 报告分析

```bash
# 生成 HTML 报告
./jmeter.sh -g tests/jmeter/results.jtl -o tests/jmeter/html_report

# 查看关键指标
# - Average Response Time
# - Throughput
# - Error Rate
# - 90th Percentile
```

---

## 七、常见问题排查

### 7.1 Prometheus 无法抓取 Pod 指标

**原因**: Pod 没有暴露 `/metrics` 端点或缺少 annotations

**解决**:
```bash
# 检查 Pod annotations
kubectl get pod <pod-name> -o yaml | grep -A 5 annotations

# 确认应用暴露 metrics（如使用 OpenTelemetry 或 Prometheus client）
```

### 7.2 Grafana 无法连接 Prometheus

**原因**: 数据源配置错误或网络不通

**解决**:
```bash
# 测试连接
kubectl exec -it deployment/grafana -n monitoring -- wget -qO- http://prometheus:9090/api/v1/status/targets
```

### 7.3 ChaosMesh 实验无效果

**原因**: selector 配置错误或权限不足

**解决**:
```bash
# 检查 ChaosMesh 日志
kubectl logs -l app.kubernetes.io/component=controller-manager -n chaos-testing

# 验证 selector 匹配
kubectl get pods -l app=couponservice -n default
```

### 7.4 Selenium 测试失败

**原因**: 元素定位失败或页面加载超时

**解决**:
```python
# 增加等待时间
WebDriverWait(driver, 20).until(...)

# 使用更稳定的定位方式
# 避免使用 class name，改用 data-testid 或 CSS selector
```

---

## 八、实验报告模板

### 8.1 监控部署报告

| 项目 | 内容 |
|-----|------|
| Prometheus 版本 | v3.2.1 |
| Grafana 版本 | 11.3.1 |
| 监控目标数 | 12 个微服务 |
| 抓取间隔 | 15s |
| Dashboard 数量 | 2 |

### 8.2 故障注入报告

| 实验名称 | 目标服务 | 故障类型 | 持续时间 | 影响 |
|---------|---------|---------|---------|------|
| kill-couponservice | couponservice | Pod 杀死 | 5min | 订单折扣失败 |
| delay-checkoutservice | checkoutservice | 500ms 延迟 | 5min | 响应时间增加 |
| cpu-stress-frontend | frontend | CPU 80% | 5min | 页面加载变慢 |

### 8.3 性能测试报告

| 场景 | 并发用户 | 持续时间 | 平均响应时间 | 吞吐量 | 错误率 |
|-----|---------|---------|-------------|--------|--------|
| 低负载 | 50 | 60s | XXX ms | XXX/s | X% |
| 中负载 | 200 | 120s | XXX ms | XXX/s | X% |
| 高负载 | 500 | 300s | XXX ms | XXX/s | X% |
| 高负载+故障 | 500 | 300s | XXX ms | XXX/s | X% |
