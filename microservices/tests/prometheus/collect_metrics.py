#!/usr/bin/env python3
"""
Prometheus 数据采集脚本
用于采集正常状态和故障注入期间的性能指标，支持论文复现

使用方法:
    # 采集正常状态数据（5分钟）
    python collect_metrics.py --mode baseline --duration 300
    
    # 采集故障期间数据（配合 ChaosMesh 使用）
    python collect_metrics.py --mode chaos --duration 180 --experiment cpu_stress
    
    # 对比分析
    python collect_metrics.py --mode compare --baseline baseline_metrics.json --chaos chaos_metrics.json
"""

import argparse
import json
import time
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode
import urllib.request
import urllib.error


class PrometheusCollector:
    """Prometheus 数据采集器"""
    
    def __init__(self, prometheus_url="http://localhost:9090"):
        self.prometheus_url = prometheus_url.rstrip('/')
        self.data = {
            'metadata': {
                'prometheus_url': prometheus_url,
                'collection_time': datetime.now().isoformat(),
            },
            'metrics': {}
        }
        
    def query(self, query, start=None, end=None, step='15s'):
        """
        执行 PromQL 查询
        
        Args:
            query: PromQL 查询语句
            start: 开始时间（ISO 格式或 Unix 时间戳）
            end: 结束时间（ISO 格式或 Unix 时间戳）
            step: 查询步长
            
        Returns:
            查询结果字典
        """
        if start and end:
            # 范围查询
            params = {
                'query': query,
                'start': start,
                'end': end,
                'step': step
            }
            url = f"{self.prometheus_url}/api/v1/query_range?{urlencode(params)}"
        else:
            # 瞬时查询
            params = {'query': query, 'time': time.time()}
            url = f"{self.prometheus_url}/api/v1/query?{urlencode(params)}"
            
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            print(f"查询失败: {e}")
            return {'status': 'error', 'error': str(e)}
        except Exception as e:
            print(f"查询异常: {e}")
            return {'status': 'error', 'error': str(e)}
            
    def collect_metric(self, name, query, description=""):
        """
        采集单个指标
        
        Args:
            name: 指标名称
            query: PromQL 查询
            description: 指标描述
        """
        print(f"  采集指标: {name}")
        result = self.query(query)
        
        self.data['metrics'][name] = {
            'query': query,
            'description': description,
            'data': result
        }
        
        if result.get('status') == 'success' and result.get('data', {}).get('result'):
            print(f"    成功: 获取到 {len(result['data']['result'])} 条数据")
        else:
            print(f"    警告: 未获取到数据或查询失败")
            
    def collect_all_metrics(self):
        """采集所有预定义指标"""
        print("\n开始采集指标...")
        
        metrics = [
            # 请求相关指标
            ('http_request_rate', 
             'rate(http_requests_total[5m])',
             'HTTP 请求速率（每秒）'),
            
            ('http_request_duration_avg',
             'rate(request_duration_seconds_sum[5m]) / rate(request_duration_seconds_count[5m])',
             '平均请求响应时间（秒）'),
            
            ('http_request_duration_p95',
             'histogram_quantile(0.95, rate(request_duration_seconds_bucket[5m]))',
             '95 分位响应时间（秒）'),
            
            ('http_error_rate',
             'rate(http_requests_total{status=~"5.."}[5m])',
             'HTTP 5xx 错误率'),
            
            # Pod 资源指标 - 修复: 移除 container 标签过滤
            ('pod_cpu_usage',
             'rate(container_cpu_usage_seconds_total{namespace="default"}[5m])',
             'Pod CPU 使用率'),
            
            ('pod_cpu_usage_frontend',
             'rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[5m])',
             'Frontend Pod CPU 使用率'),
            
            ('pod_cpu_usage_checkout',
             'rate(container_cpu_usage_seconds_total{namespace="default",pod=~"checkoutservice-.*"}[5m])',
             'CheckoutService Pod CPU 使用率'),
            
            ('pod_cpu_usage_cart',
             'rate(container_cpu_usage_seconds_total{namespace="default",pod=~"cartservice-.*"}[5m])',
             'CartService Pod CPU 使用率'),
            
            ('pod_memory_usage',
             'container_memory_usage_bytes{namespace="default"}',
             'Pod 内存使用量（字节）'),
            
            ('pod_memory_working_set',
             'container_memory_working_set_bytes{namespace="default"}',
             'Pod 工作集内存（字节）'),
            
            ('pod_memory_usage_frontend',
             'container_memory_usage_bytes{namespace="default",pod=~"frontend-.*"}',
             'Frontend Pod 内存使用量'),
            
            ('pod_memory_usage_cart',
             'container_memory_usage_bytes{namespace="default",pod=~"cartservice-.*"}',
             'CartService Pod 内存使用量'),
            
            # 网络指标
            ('pod_network_receive',
             'rate(container_network_receive_bytes_total{namespace="default"}[5m])',
             'Pod 网络接收速率（字节/秒）'),
            
            ('pod_network_transmit',
             'rate(container_network_transmit_bytes_total{namespace="default"}[5m])',
             'Pod 网络发送速率（字节/秒）'),
            
            ('pod_network_receive_checkout',
             'rate(container_network_receive_bytes_total{namespace="default",pod=~"checkoutservice-.*"}[5m])',
             'CheckoutService 网络接收速率'),
            
            # 文件系统
            ('pod_fs_usage',
             'container_fs_usage_bytes{namespace="default"}',
             'Pod 文件系统使用量'),
            
            # Kubernetes 指标 - 需要 kube-state-metrics
            ('pod_restarts',
             'kube_pod_container_status_restarts_total{namespace="default"}',
             'Pod 容器重启次数'),
            
            ('pod_status_phase',
             'kube_pod_status_phase{namespace="default"}',
             'Pod 状态'),
            
            ('pod_status_running',
             'kube_pod_status_phase{namespace="default",phase="Running"}',
             'Running 状态 Pod 数量'),
            
            # 服务可用性
            ('service_up',
             'up{job="onlineboutique-services"}',
             '服务可用性（1=up, 0=down）'),
            
            # 应用层指标 - 需要应用暴露
            ('app_http_requests',
             'rate(http_requests_total{namespace="default"}[5m])',
             '应用 HTTP 请求速率'),
            
            ('app_request_duration',
             'histogram_quantile(0.95, rate(request_duration_seconds_bucket{namespace="default"}[5m]))',
             '应用请求延迟 P95'),
            
            ('app_error_rate',
             'rate(http_requests_total{namespace="default",status=~"5.."}[5m])',
             '应用错误率'),
        ]
        
        for name, query, description in metrics:
            self.collect_metric(name, query, description)
            time.sleep(0.5)  # 避免请求过快
            
    def collect_time_series(self, duration_seconds=300, step='15s'):
        """
        采集时间序列数据
        
        Args:
            duration_seconds: 采集持续时间
            step: 查询步长
        """
        end_time = time.time()
        start_time = end_time - duration_seconds
        
        self.data['metadata']['start_time'] = datetime.fromtimestamp(start_time).isoformat()
        self.data['metadata']['end_time'] = datetime.fromtimestamp(end_time).isoformat()
        self.data['metadata']['duration_seconds'] = duration_seconds
        
        print(f"\n采集时间序列数据 ({duration_seconds} 秒)...")
        print(f"时间范围: {datetime.fromtimestamp(start_time)} ~ {datetime.fromtimestamp(end_time)}")
        
        # 关键时间序列指标
        time_series_queries = [
            ('ts_frontend_cpu',
             'rate(container_cpu_usage_seconds_total{namespace="default",pod=~"frontend-.*"}[5m])'),
            
            ('ts_checkout_cpu',
             'rate(container_cpu_usage_seconds_total{namespace="default",pod=~"checkoutservice-.*"}[5m])'),
            
            ('ts_cart_cpu',
             'rate(container_cpu_usage_seconds_total{namespace="default",pod=~"cartservice-.*"}[5m])'),
            
            ('ts_frontend_memory',
             'container_memory_usage_bytes{namespace="default",pod=~"frontend-.*"} / 1024 / 1024'),
            
            ('ts_cart_memory',
             'container_memory_usage_bytes{namespace="default",pod=~"cartservice-.*"} / 1024 / 1024'),
            
            ('ts_checkout_network_rx',
             'rate(container_network_receive_bytes_total{namespace="default",pod=~"checkoutservice-.*"}[5m]) / 1024'),
            
            ('ts_checkout_network_tx',
             'rate(container_network_transmit_bytes_total{namespace="default",pod=~"checkoutservice-.*"}[5m]) / 1024'),
            
            ('ts_pod_restarts',
             'kube_pod_container_status_restarts_total{namespace="default"}'),
        ]
        
        for name, query in time_series_queries:
            print(f"  采集: {name}")
            result = self.query(query, start=start_time, end=end_time, step=step)
            self.data['metrics'][name] = {
                'query': query,
                'data': result
            }
            time.sleep(0.5)
            
    def save(self, filename=None):
        """
        保存采集的数据到文件
        
        Args:
            filename: 输出文件名（默认自动生成）
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            mode = self.data['metadata'].get('mode', 'unknown')
            filename = f"metrics_{mode}_{timestamp}.json"
            
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            
        print(f"\n数据已保存到: {filename}")
        return filename
        
    def print_summary(self):
        """打印数据摘要"""
        print(f"\n{'='*60}")
        print("数据采集摘要")
        print(f"{'='*60}")
        print(f"采集时间: {self.data['metadata']['collection_time']}")
        print(f"Prometheus: {self.data['metadata']['prometheus_url']}")
        
        if 'start_time' in self.data['metadata']:
            print(f"时间范围: {self.data['metadata']['start_time']} ~ {self.data['metadata']['end_time']}")
            print(f"持续时间: {self.data['metadata']['duration_seconds']} 秒")
            
        print(f"\n采集指标数: {len(self.data['metrics'])}")
        
        success_count = 0
        fail_count = 0
        for name, metric in self.data['metrics'].items():
            if metric['data'].get('status') == 'success' and metric['data'].get('data', {}).get('result'):
                status = "成功"
                success_count += 1
            elif metric['data'].get('status') == 'success':
                status = "成功(无数据)"
                success_count += 1
            else:
                status = "失败"
                fail_count += 1
            result_count = len(metric['data'].get('data', {}).get('result', []))
            print(f"  {name}: {status} ({result_count} 条数据)")
            
        print(f"\n成功: {success_count} | 失败: {fail_count} | 总计: {success_count + fail_count}")
        print(f"{'='*60}")


def compare_metrics(baseline_file, chaos_file, output_file=None):
    """
    对比正常状态和故障状态的数据
    
    Args:
        baseline_file: 基线数据文件
        chaos_file: 故障数据文件
        output_file: 输出对比结果文件
    """
    print(f"\n{'='*60}")
    print("对比分析: 正常状态 vs 故障状态")
    print(f"{'='*60}")
    
    with open(baseline_file, 'r', encoding='utf-8') as f:
        baseline = json.load(f)
    with open(chaos_file, 'r', encoding='utf-8') as f:
        chaos = json.load(f)
        
    comparison = {
        'baseline_file': baseline_file,
        'chaos_file': chaos_file,
        'comparison_time': datetime.now().isoformat(),
        'results': {}
    }
    
    # 对比关键指标
    for metric_name in baseline['metrics']:
        if metric_name not in chaos['metrics']:
            continue
            
        baseline_data = baseline['metrics'][metric_name]['data']
        chaos_data = chaos['metrics'][metric_name]['data']
        
        if baseline_data.get('status') != 'success' or chaos_data.get('status') != 'success':
            continue
            
        # 提取数值进行简单对比
        baseline_values = []
        chaos_values = []
        
        for result in baseline_data.get('data', {}).get('result', []):
            if result.get('value'):
                try:
                    baseline_values.append(float(result['value'][1]))
                except (ValueError, IndexError):
                    pass
                    
        for result in chaos_data.get('data', {}).get('result', []):
            if result.get('value'):
                try:
                    chaos_values.append(float(result['value'][1]))
                except (ValueError, IndexError):
                    pass
                    
        if baseline_values and chaos_values:
            baseline_avg = sum(baseline_values) / len(baseline_values)
            chaos_avg = sum(chaos_values) / len(chaos_values)
            
            if baseline_avg != 0:
                change_pct = ((chaos_avg - baseline_avg) / baseline_avg) * 100
            else:
                change_pct = 0
                
            comparison['results'][metric_name] = {
                'baseline_avg': round(baseline_avg, 6),
                'chaos_avg': round(chaos_avg, 6),
                'change_percent': round(change_pct, 2),
                'impact': 'increased' if change_pct > 0 else 'decreased'
            }
            
            direction = "↑" if change_pct > 0 else "↓"
            print(f"\n  {metric_name}:")
            print(f"    基线: {baseline_avg:.6f}")
            print(f"    故障: {chaos_avg:.6f}")
            print(f"    变化: {change_pct:+.2f}% {direction}")
            
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
        print(f"\n对比结果已保存到: {output_file}")
        
    return comparison


def main():
    parser = argparse.ArgumentParser(description='Prometheus 数据采集工具')
    parser.add_argument('--url', default='http://localhost:9090', help='Prometheus URL')
    parser.add_argument('--mode', choices=['baseline', 'chaos', 'compare'], 
                       default='baseline', help='采集模式')
    parser.add_argument('--duration', type=int, default=300, 
                       help='采集持续时间（秒）')
    parser.add_argument('--experiment', default='', 
                       help='故障实验名称（用于文件名）')
    parser.add_argument('--output', default=None, help='输出文件名')
    parser.add_argument('--baseline', default=None, help='基线数据文件（对比模式）')
    parser.add_argument('--chaos', default=None, help='故障数据文件（对比模式）')
    
    args = parser.parse_args()
    
    if args.mode == 'compare':
        if not args.baseline or not args.chaos:
            print("错误: 对比模式需要指定 --baseline 和 --chaos 文件")
            return
        compare_metrics(args.baseline, args.chaos, args.output)
        return
        
    # 创建采集器
    collector = PrometheusCollector(args.url)
    collector.data['metadata']['mode'] = args.mode
    collector.data['metadata']['experiment'] = args.experiment
    
    print(f"\n{'='*60}")
    print(f"Prometheus 数据采集")
    print(f"{'='*60}")
    print(f"模式: {args.mode}")
    print(f"Prometheus: {args.url}")
    print(f"持续时间: {args.duration} 秒")
    if args.experiment:
        print(f"实验: {args.experiment}")
    print(f"{'='*60}")
    
    # 采集指标
    collector.collect_all_metrics()
    collector.collect_time_series(duration_seconds=args.duration)
    
    # 打印摘要
    collector.print_summary()
    
    # 保存数据
    if args.output:
        collector.save(args.output)
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"metrics_{args.mode}_{args.experiment}_{timestamp}.json" if args.experiment else f"metrics_{args.mode}_{timestamp}.json"
        collector.save(filename)


if __name__ == '__main__':
    main()
