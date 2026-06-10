# Coupon Service 集成总结

## 概述

本项目在 Google Cloud 的 Online Boutique（微服务演示应用）基础上，新增了一个 **Coupon Service（优惠券服务）**。用户在结算时输入优惠码（如 `SAVE10`、`WELCOME20`），订单总价会自动打折。

支持三种演示场景：
- **无优惠券**：输入框留空，按原价结算
- **合法优惠券**：输入 `SAVE10` 或 `WELCOME20`，总价自动打折
- **非法优惠券**：输入不存在的码（如 `FAKE99`），订单仍成功但无折扣

---

## 新增/修改的文件清单

### 1. 优惠券服务（Python + FastAPI）

| 文件 | 说明 |
|------|------|
| `src/couponservice/main.py` | 优惠券服务主代码，内置 SAVE10、WELCOME20 等优惠码 |
| `src/couponservice/Dockerfile` | 容器镜像定义（从 alpine 改为 slim，避免 apk 网络问题） |
| `src/couponservice/requirements.txt` | Python 依赖（fastapi、uvicorn、pydantic） |
| `src/couponservice/proto/coupon.proto` | gRPC proto 定义（供参考，实际使用 REST 调用） |
| `src/couponservice/README.md` | 服务说明（空文件） |

### 2. 结算服务（Go + gRPC）

| 文件 | 说明 |
|------|------|
| `src/checkoutservice/main.go` | 新增优惠券调用逻辑，通过 HTTP REST 调用 couponservice，通过 gRPC metadata 传回折扣信息 |
| `src/checkoutservice/Dockerfile` | 未修改（沿用原有 Go 构建流程） |

### 3. 前端服务（Go + HTML Template）

| 文件 | 说明 |
|------|------|
| `src/frontend/handlers.go` | 新增 coupon_code 表单读取、通过 gRPC metadata 传递/接收优惠券信息 |
| `src/frontend/main.go` | 添加启动日志标记（用于验证镜像是否更新） |
| `src/frontend/templates/cart.html` | 新增 Coupon Code 输入框 |
| `src/frontend/templates/order.html` | 新增 Coupon Applied 和 Discount 展示 |
| `src/frontend/Dockerfile` | **关键修改**：显式复制每个文件，避免 `COPY . .` 缓存旧代码 |

### 4. Proto 定义（手动追加字段）

| 文件 | 说明 |
|------|------|
| `src/checkoutservice/genproto/demo.pb.go` | 手动在 `OrderResult` 结构体追加 `CouponCode` 和 `CouponDiscount` 字段 |
| `src/frontend/genproto/demo.pb.go` | 同上 |

> 注：由于本地环境缺少 `protoc`，无法重新生成完整的 protobuf 代码，因此采用手动追加字段 + gRPC metadata 传参的方案。

### 5. Kubernetes 部署配置

| 文件 | 说明 |
|------|------|
| `kubernetes-manifests/couponservice.yaml` | 优惠券服务的 Deployment + Service |
| `kubernetes-manifests/checkoutservice.yaml` | 新增 `COUPON_SERVICE_ADDR` 环境变量，修复缩进 |
| `kubernetes-manifests/frontend.yaml` | 新增 `imagePullPolicy: Never`（确保使用本地镜像） |
| `kubernetes-manifests/kustomization.yaml` | 添加 `couponservice.yaml` |
| `kustomize/base/kustomization.yaml` | 添加 `couponservice.yaml` |
| `kustomize/base/couponservice.yaml` | 复制自 `kubernetes-manifests/couponservice.yaml` |
| `kustomize/components/couponservice/couponservice.yaml` | 优惠券服务组件定义 |

### 6. Helm Chart 配置

| 文件 | 说明 |
|------|------|
| `helm-chart/templates/checkoutservice.yaml` | 新增 `COUPON_SERVICE_ADDR` 环境变量和 Istio Sidecar egress |
| `helm-chart/templates/couponservice.yaml` | 优惠券服务 Helm 模板（已存在） |
| `helm-chart/values.yaml` | 添加 `couponservice.name` |

### 7. 构建配置

| 文件 | 说明 |
|------|------|
| `skaffold.yaml` | 添加 `couponservice` 镜像构建配置 |

---

## 项目目录结构（关键部分）

```
microservices-demo/
├── kubernetes-manifests/
│   ├── couponservice.yaml          # 新增：优惠券服务 K8s 部署
│   ├── checkoutservice.yaml        # 修改：添加 COUPON_SERVICE_ADDR
│   ├── frontend.yaml               # 修改：添加 imagePullPolicy: Never
│   └── kustomization.yaml          # 修改：添加 couponservice
├── kustomize/
│   └── base/
│       ├── couponservice.yaml      # 新增
│       └── kustomization.yaml      # 修改：添加 couponservice
├── helm-chart/
│   ├── templates/
│   │   ├── checkoutservice.yaml    # 修改：添加优惠券服务地址
│   │   └── couponservice.yaml      # 已存在
│   └── values.yaml                 # 修改：添加 couponservice.name
├── src/
│   ├── couponservice/              # 新增服务
│   │   ├── main.py                 # FastAPI 优惠券服务
│   │   ├── Dockerfile              # 从 alpine 改为 slim
│   │   ├── requirements.txt        # Python 依赖
│   │   ├── proto/
│   │   │   └── coupon.proto        # gRPC 定义（参考用）
│   │   └── README.md
│   ├── checkoutservice/
│   │   ├── main.go                 # 修改：调用优惠券服务
│   │   └── genproto/
│   │       └── demo.pb.go          # 修改：手动追加 CouponCode/CouponDiscount
│   └── frontend/
│       ├── main.go                 # 修改：添加启动日志
│       ├── handlers.go             # 修改：处理优惠券表单和 metadata
│       ├── Dockerfile              # 关键修改：显式复制文件避免缓存
│       ├── templates/
│       │   ├── cart.html           # 修改：添加 Coupon Code 输入框
│       │   └── order.html          # 修改：展示 Coupon Applied 和 Discount
│       └── genproto/
│           └── demo.pb.go          # 修改：手动追加 CouponCode/CouponDiscount
├── protos/
│   └── demo.proto                  # 修改：添加 CouponService 定义
└── skaffold.yaml                   # 修改：添加 couponservice 构建
```

---

## 关键修改详解

### 1. couponservice/main.py - 优惠券服务

```python
# 内置优惠码数据库
COUPONS = {
    "SAVE10": {"discount_type": "percent", "value": 10, "description": "全场9折", "min_order": 0.0},
    "SAVE20": {"discount_type": "percent", "value": 20, "description": "全场8折", "min_order": 30.0},
    "WELCOME20": {"discount_type": "percent", "value": 20, "description": "新用户专享8折", "min_order": 0.0},
    "OFF5": {"discount_type": "fixed", "value": 5, "description": "立减 $5", "min_order": 20.0},
    "OFF15": {"discount_type": "fixed", "value": 15, "description": "立减 $15", "min_order": 60.0},
    "FREESHIP": {"discount_type": "shipping", "value": 0, "description": "免运费", "min_order": 0.0},
}

# /apply 接口：应用优惠券，返回折扣后价格
@app.post("/apply")
def apply_coupon(req: ApplyRequest):
    code = req.code.strip().upper()
    if code not in COUPONS:
        raise HTTPException(status_code=404, detail=f"优惠码 '{code}' 不存在或已失效")
    # ... 计算折扣逻辑
```

### 2. checkoutservice/main.go - 调用优惠券服务

```go
// 从 gRPC metadata 读取优惠码
var couponCode string
if md, ok := metadata.FromIncomingContext(ctx); ok {
    if vals := md.Get("x-coupon-code"); len(vals) > 0 {
        couponCode = vals[0]
    }
}

// 调用 Coupon Service 计算折扣
var couponDiscount *pb.Money
if couponCode != "" && cs.couponSvcAddr != "" {
    discount, err := cs.applyCoupon(ctx, couponCode, &subtotal)
    if err != nil {
        log.Warnf("coupon application failed: %+v", err)
    } else if discount != nil {
        couponDiscount = discount
        discountedSubtotal = money.Must(money.Sum(subtotal, money.Negate(*discount)))
    }
}

// 通过 gRPC metadata 传回优惠券信息（proto 手动追加字段序列化会丢失）
if couponCode != "" && couponDiscount != nil {
    grpc.SetHeader(ctx, metadata.Pairs(
        "x-coupon-code", couponCode,
        "x-coupon-discount-units", fmt.Sprintf("%d", couponDiscount.GetUnits()),
        "x-coupon-discount-nanos", fmt.Sprintf("%d", couponDiscount.GetNanos()),
    ))
}
```

### 3. frontend/handlers.go - 处理表单和 metadata

```go
// 读取表单中的优惠码
couponCode := r.FormValue("coupon_code")

// 通过 gRPC metadata 传递给 checkoutservice
ctx := r.Context()
if couponCode != "" {
    ctx = metadata.AppendToOutgoingContext(ctx, "x-coupon-code", couponCode)
}

// 调用 PlaceOrder，同时读取 response header
var header metadata.MD
order, err := pb.NewCheckoutServiceClient(fe.checkoutSvcConn).
    PlaceOrder(ctx, &pb.PlaceOrderRequest{...}, grpc.Header(&header))

// 从 response metadata 读取折扣信息
var couponDiscount *pb.Money
if h := header; len(h.Get("x-coupon-code")) > 0 {
    units, _ := strconv.ParseInt(h.Get("x-coupon-discount-units")[0], 10, 64)
    nanos, _ := strconv.ParseInt(h.Get("x-coupon-discount-nanos")[0], 10, 32)
    couponDiscount = &pb.Money{...}
}

// 渲染模板时传入优惠券信息
templates.ExecuteTemplate(w, "order", injectCommonTemplateData(r, map[string]interface{}{
    ...
    "coupon_code":     couponCode,
    "coupon_discount": couponDiscount,
}))
```

### 4. frontend/templates/cart.html - 输入框

```html
<div class="row">
    <div class="col">
        <h3>Coupon Code</h3>
    </div>
</div>
<div class="form-row">
    <div class="col cymbal-form-field">
        <label for="coupon_code">Enter Coupon (e.g. SAVE10, WELCOME20)</label>
        <input type="text" id="coupon_code" name="coupon_code" placeholder="SAVE10">
    </div>
</div>
```

### 5. frontend/templates/order.html - 展示折扣

```html
{{ if .coupon_code }}
<div class="row border-bottom-solid padding-y-24">
    <div class="col-6 pl-md-0">Coupon Applied</div>
    <div class="col-6 pr-md-0 text-right">{{.coupon_code}}</div>
</div>
<div class="row border-bottom-solid padding-y-24">
    <div class="col-6 pl-md-0">Discount</div>
    <div class="col-6 pr-md-0 text-right">-{{renderMoneyPtr .coupon_discount}}</div>
</div>
{{ end }}
```

### 6. frontend/Dockerfile - 关键修改避免缓存

```dockerfile
# 原方案（会导致缓存旧代码）
# COPY . .

# 新方案（显式复制每个文件）
COPY main.go .
COPY handlers.go .
COPY rpc.go .
COPY middleware.go .
COPY deployment_details.go .
COPY packaging_info.go .
COPY go.mod .
COPY go.sum .
COPY ./templates ./templates
COPY ./static ./static
COPY ./money ./money
COPY ./genproto ./genproto
COPY ./validator ./validator

# 验证代码是否最新
RUN grep -q "COUPON SUPPORT" main.go && echo "CODE IS FRESH" || exit 1
RUN grep -q "DEBUG header" handlers.go && echo "HANDLERS IS FRESH" || exit 1
```

---

## 关键部署命令

### 环境准备

```powershell
# 启动 minikube（Windows）
minikube start --cpus=4 --memory 4096 --disk-size 32g --driver=docker

# 验证连接
kubectl get nodes
```

### 构建镜像（本地 Docker → 导入 minikube）

```powershell
cd "E:\Testing and Maintenance\microservices-demo"

# 构建三个修改过的服务
docker build --no-cache -t couponservice:latest src/couponservice
docker build --no-cache -t checkoutservice:latest src/checkoutservice
docker build --no-cache -t frontend:latest src/frontend

# 导入 minikube
minikube image load couponservice:latest --overwrite
minikube image load checkoutservice:latest --overwrite
minikube image load frontend:latest --overwrite
```

### 部署到 Kubernetes

```powershell
# 使用 kustomize 部署所有服务
kubectl apply -k kubernetes-manifests/

# 或单独部署
kubectl apply -f kubernetes-manifests/couponservice.yaml
kubectl apply -f kubernetes-manifests/checkoutservice.yaml
kubectl apply -f kubernetes-manifests/frontend.yaml
```

### 验证和调试

```powershell
# 查看 Pod 状态
kubectl get pods -w

# 查看优惠券服务日志
kubectl logs -l app=couponservice -f

# 查看结算服务日志
kubectl logs -l app=checkoutservice -f

# 查看前端日志
kubectl logs -l app=frontend -f

# 暴露前端访问端口
kubectl port-forward svc/frontend 8080:80

# 或获取 minikube 服务 URL
minikube service frontend-external --url
```

### 清理

```powershell
# 删除所有部署
kubectl delete -k kubernetes-manifests/

# 或彻底删除 minikube
minikube delete
```

---

## 遇到的坑与解决方案

### 1. Docker build 缓存问题
**现象**：修改代码后重新 build，但容器里还是旧代码。
**原因**：`COPY . .` 在 Docker 构建上下文中可能缓存旧文件。
**解决**：显式复制每个文件 + `RUN grep` 验证代码 freshness。

### 2. 镜像拉取失败（ImagePullBackOff）
**现象**：Pod 状态为 `ImagePullBackOff`。
**原因**：K8s 默认尝试从 Docker Hub 拉取 `xxx:latest` 镜像，但 Hub 上不存在。
**解决**：在 manifest 中设置 `imagePullPolicy: Never`，强制使用 minikube 本地镜像。

### 3. Protobuf 字段序列化丢失
**现象**：手动追加的 `CouponCode` 和 `CouponDiscount` 字段在 gRPC 传输后为空。
**原因**：`demo.pb.go` 的 `rawDesc`（FileDescriptorProto）没有更新，protobuf 序列化时不知道新字段。
**解决**：通过 gRPC metadata（header）传递优惠券信息，绕过 protobuf message body。

### 4. minikube 内部无外网
**现象**：在 minikube 内部 `docker build` 时无法拉取基础镜像。
**原因**：minikube 的 Docker daemon 没有外网访问。
**解决**：在 Windows 本地 Docker 构建，然后通过 `minikube image load` 导入。

### 5. 镜像源不可用
**现象**：`docker pull python:3.12-alpine` 失败。
**原因**：配置的 Docker 镜像源（中科大）不可用。
**解决**：将 `python:3.12-alpine` 改为 `python:3.12-slim`（Debian 基础，无需 apk）。

---

## 演示流程

1. **打开浏览器**：`http://localhost:8080`
2. **浏览商品**：点击商品进入详情页，点击 **Add to Cart**
3. **进入购物车**：点击右上角购物车图标，进入结算页
4. **场景一 - 无优惠券**：Coupon Code 输入框留空，点击 **Place Order**
   - 订单完成页只显示 Confirmation #、Tracking #、Total Paid
5. **场景二 - 合法优惠券**：在 Coupon Code 输入框输入 `SAVE10`，点击 **Place Order**
   - 订单完成页显示 Coupon Applied: SAVE10、Discount: -$X.XX、Total Paid（折扣后）
6. **场景三 - 非法优惠券**：输入 `FAKE99`，点击 **Place Order**
   - 订单成功完成，但无折扣信息（checkoutservice 日志显示 coupon application failed）

---

## 技术栈

| 服务 | 语言 | 框架/协议 | 通信方式 |
|------|------|-----------|----------|
| couponservice | Python | FastAPI (HTTP REST) | 被 checkoutservice HTTP 调用 |
| checkoutservice | Go | gRPC Server + HTTP Client | gRPC（frontend）+ HTTP（couponservice） |
| frontend | Go | HTTP Server + gRPC Client | HTTP（浏览器）+ gRPC（checkoutservice） |

---

*文档生成时间：2026-06-02*
