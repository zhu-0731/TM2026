#!/bin/bash
# 为所有微服务添加 Prometheus 监控注解

set -e

echo "为微服务添加 Prometheus 监控注解..."

# 需要添加注解的服务列表（名称:端口）
declare -A SERVICES=(
    ["frontend"]="8080"
    ["checkoutservice"]="5050"
    ["cartservice"]="7070"
    ["productcatalogservice"]="3550"
    ["currencyservice"]="7000"
    ["paymentservice"]="50051"
    ["shippingservice"]="50051"
    ["emailservice"]="8080"
    ["adservice"]="9555"
    ["recommendationservice"]="8080"
    ["couponservice"]="8080"
)

for svc in "${!SERVICES[@]}"; do
    port="${SERVICES[$svc]}"
    echo ""
    echo "处理服务: $svc (端口: $port)"
    
    # 检查 Deployment 是否存在
    if ! kubectl get deployment "$svc" -n default &>/dev/null; then
        echo "  警告: Deployment $svc 不存在，跳过"
        continue
    fi
    
    # 添加注解
    kubectl patch deployment "$svc" -n default --type merge -p "{
        \"spec\": {
            \"template\": {
                \"metadata\": {
                    \"annotations\": {
                        \"prometheus.io/scrape\": \"true\",
                        \"prometheus.io/port\": \"$port\",
                        \"prometheus.io/path\": \"/metrics\"
                    }
                }
            }
        }
    }"
    
    if [ $? -eq 0 ]; then
        echo "  成功: 已添加注解"
    else
        echo "  失败: 无法添加注解"
    fi
done

echo ""
echo "等待 Pod 滚动更新..."
sleep 5

# 验证注解是否添加成功
echo ""
echo "验证注解..."
kubectl get pods -n default -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations.prometheus\.io/scrape}{"\n"}{end}'

echo ""
echo "完成！请等待约 30 秒让 Prometheus 重新抓取指标。"
