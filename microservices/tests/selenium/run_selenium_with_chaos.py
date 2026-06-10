"""
Selenium + ChaosMesh 集成测试脚本
=================================
自动化执行：注入故障 -> 运行 Selenium 测试 -> 停止故障 -> 生成对比报告

用法：
    python run_selenium_with_chaos.py --experiment cpu_stress
    python run_selenium_with_chaos.py --experiment memory_stress
    python run_selenium_with_chaos.py --experiment network_delay
    python run_selenium_with_chaos.py --experiment pod_kill
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SELENIUM_DIR = os.path.join(PROJECT_ROOT, 'tests', 'selenium')
CHAOS_DIR = os.path.join(PROJECT_ROOT, 'chaos-experiments')

# 故障实验配置文件映射
EXPERIMENT_FILES = {
    'cpu_stress': 'cpu-stress-frontend.yaml',
    'memory_stress': 'memory-stress-cartservice.yaml',
    'network_delay': 'network-delay-checkoutservice.yaml',
    'pod_kill': 'pod-kill-couponservice.yaml'
}


def run_command(cmd, description="", timeout=60):
    """执行 shell 命令"""
    print(f"\n[执行] {description or cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 and result.stderr:
        print(f"  警告: {result.stderr.strip()[:200]}")
    if result.stdout:
        print(f"  输出: {result.stdout.strip()[:300]}")
    return result.returncode == 0


def inject_chaos(experiment_name):
    """注入故障"""
    filename = EXPERIMENT_FILES.get(experiment_name)
    if not filename:
        print(f"[错误] 未知的实验类型: {experiment_name}")
        print(f"  可用选项: {', '.join(EXPERIMENT_FILES.keys())}")
        return False
    
    filepath = os.path.join(CHAOS_DIR, filename)
    if not os.path.exists(filepath):
        print(f"[错误] 配置文件不存在: {filepath}")
        return False
    
    print(f"\n{'='*60}")
    print(f"注入故障: {experiment_name}")
    print(f"配置文件: {filename}")
    print(f"{'='*60}")
    
    return run_command(f"kubectl apply -f {filepath}", f"应用故障配置 {filename}")


def stop_chaos(experiment_name):
    """停止故障"""
    filename = EXPERIMENT_FILES.get(experiment_name)
    if not filename:
        return False
    
    filepath = os.path.join(CHAOS_DIR, filename)
    print(f"\n{'='*60}")
    print(f"停止故障: {experiment_name}")
    print(f"{'='*60}")
    
    return run_command(f"kubectl delete -f {filepath} --ignore-not-found=true", f"删除故障配置")


def run_baseline_test(browser='chrome'):
    """运行基线测试（无故障）"""
    print(f"\n{'='*60}")
    print(f"运行基线测试（浏览器: {browser}）")
    print(f"{'='*60}")
    
    env = os.environ.copy()
    env['TEST_BROWSER'] = browser
    env['TEST_MODE'] = 'baseline'
    env['FRONTEND_URL'] = 'http://localhost:18080'
    
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 
         os.path.join(SELENIUM_DIR, 'test_selenium_performance.py'),
         '-v', '--tb=short'],
        env=env, capture_output=True, text=True, timeout=300
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0


def run_chaos_test(experiment_name, browser='chrome'):
    """运行故障期间测试"""
    print(f"\n{'='*60}")
    print(f"运行故障期间测试（{experiment_name}, 浏览器: {browser}）")
    print(f"{'='*60}")
    
    env = os.environ.copy()
    env['TEST_BROWSER'] = browser
    env['TEST_MODE'] = 'chaos'
    env['CHAOS_TYPE'] = experiment_name
    env['FRONTEND_URL'] = 'http://localhost:18080'
    
    result = subprocess.run(
        [sys.executable, '-m', 'pytest',
         os.path.join(SELENIUM_DIR, 'test_selenium_chaos.py'),
         '-v', '--tb=short'],
        env=env, capture_output=True, text=True, timeout=300
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0


def find_latest_json(prefix, directory=SELENIUM_DIR):
    """查找最新的 JSON 数据文件"""
    files = [f for f in os.listdir(directory) if f.startswith(prefix) and f.endswith('.json')]
    if not files:
        return None
    files.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
    return os.path.join(directory, files[0])


def generate_comparison_report(experiment_name, browser='chrome'):
    """生成基线与故障期间的对比报告"""
    print(f"\n{'='*60}")
    print(f"生成对比报告")
    print(f"{'='*60}")
    
    # 查找最新的数据文件
    baseline_file = find_latest_json(f'selenium_baseline_{browser}')
    chaos_file = find_latest_json(f'selenium_chaos_{experiment_name}_{browser}')
    
    if not baseline_file or not chaos_file:
        print("[警告] 未找到基线或故障数据文件，跳过对比")
        return None
    
    with open(baseline_file, 'r', encoding='utf-8') as f:
        baseline_data = json.load(f)
    with open(chaos_file, 'r', encoding='utf-8') as f:
        chaos_data = json.load(f)
    
    # 对比分析
    comparison = {
        'experiment': experiment_name,
        'browser': browser,
        'timestamp': datetime.now().isoformat(),
        'baseline_summary': baseline_data.get('summary', {}),
        'chaos_summary': chaos_data.get('summary', {}),
        'operation_comparison': []
    }
    
    # 按操作对比响应时间
    baseline_ops = {m['operation']: m for m in baseline_data.get('details', [])}
    chaos_ops = {m['operation']: m for m in chaos_data.get('details', [])}
    
    for op_name in set(list(baseline_ops.keys()) + list(chaos_ops.keys())):
        baseline_metric = baseline_ops.get(op_name, {})
        chaos_metric = chaos_ops.get(op_name, {})
        
        baseline_time = baseline_metric.get('duration_ms', 0)
        chaos_time = chaos_metric.get('duration_ms', 0)
        
        if baseline_time > 0:
            change_pct = ((chaos_time - baseline_time) / baseline_time) * 100
        else:
            change_pct = 0
        
        comparison['operation_comparison'].append({
            'operation': op_name,
            'baseline_ms': baseline_time,
            'chaos_ms': chaos_time,
            'change_percent': round(change_pct, 2),
            'baseline_status': baseline_metric.get('status', 'unknown'),
            'chaos_status': chaos_metric.get('status', 'unknown')
        })
    
    # 保存对比报告
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = os.path.join(SELENIUM_DIR, f'selenium_comparison_{experiment_name}_{browser}_{timestamp}.json')
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] 对比报告已保存: {os.path.basename(report_file)}")
    
    # 打印摘要
    print(f"\n{'='*60}")
    print("对比摘要")
    print(f"{'='*60}")
    print(f"  实验类型: {experiment_name}")
    print(f"  浏览器: {browser}")
    
    baseline_pass = baseline_data.get('summary', {}).get('pass_rate', 'N/A')
    chaos_pass = chaos_data.get('summary', {}).get('pass_rate', 'N/A')
    print(f"  基线通过率: {baseline_pass}")
    print(f"  故障通过率: {chaos_pass}")
    
    print(f"\n  各操作响应时间对比:")
    for op in comparison['operation_comparison']:
        arrow = "↑" if op['change_percent'] > 0 else "↓" if op['change_percent'] < 0 else "→"
        print(f"    {op['operation']}: {op['baseline_ms']}ms -> {op['chaos_ms']}ms ({arrow}{abs(op['change_percent']):.1f}%)")
    
    return report_file


def main():
    parser = argparse.ArgumentParser(description='Selenium + ChaosMesh 集成测试')
    parser.add_argument('--experiment', required=True,
                        choices=list(EXPERIMENT_FILES.keys()),
                        help='故障实验类型')
    parser.add_argument('--browser', default='chrome',
                        choices=['chrome', 'edge'],
                        help='测试浏览器（默认 chrome）')
    parser.add_argument('--skip-baseline', action='store_true',
                        help='跳过基线测试')
    parser.add_argument('--chaos-duration', type=int, default=60,
                        help='故障持续时间（秒，默认 60）')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print("Selenium + ChaosMesh 集成测试")
    print(f"{'='*60}")
    print(f"实验: {args.experiment}")
    print(f"浏览器: {args.browser}")
    print(f"故障持续时间: {args.chaos_duration}秒")
    
    # 步骤 1: 基线测试
    if not args.skip_baseline:
        baseline_ok = run_baseline_test(args.browser)
        if not baseline_ok:
            print("\n[警告] 基线测试有失败，继续执行...")
    else:
        print("\n[跳过] 基线测试")
    
    # 步骤 2: 注入故障
    if not inject_chaos(args.experiment):
        print("[错误] 故障注入失败，退出")
        return 1
    
    # 等待故障生效
    print(f"\n[等待] 等待故障生效（5秒）...")
    time.sleep(5)
    
    # 步骤 3: 故障期间测试
    chaos_ok = run_chaos_test(args.experiment, args.browser)
    
    # 步骤 4: 等待故障持续一段时间
    if args.chaos_duration > 0:
        print(f"\n[等待] 故障持续 {args.chaos_duration} 秒...")
        time.sleep(args.chaos_duration)
    
    # 步骤 5: 停止故障
    stop_chaos(args.experiment)
    
    # 步骤 6: 生成对比报告
    if not args.skip_baseline:
        generate_comparison_report(args.experiment, args.browser)
    
    # 步骤 7: 等待系统恢复
    print(f"\n[等待] 等待系统恢复（10秒）...")
    time.sleep(10)
    
    print(f"\n{'='*60}")
    print("测试完成！")
    print(f"{'='*60}")
    
    return 0 if chaos_ok else 1


if __name__ == "__main__":
    sys.exit(main())
