"""
pytest 配置文件
配置 HTML 测试报告和测试元数据
兼容 pytest-html 4.x 版本
"""

import pytest


def pytest_configure(config):
    """配置 pytest 测试报告元数据"""
    # pytest-html 4.x 使用 stash 存储元数据
    try:
        config.stash['metadata'] = {
            'Project': 'OnlineBoutique Selenium Test',
            'Phase': 'Phase 3 - Frontend Automation Testing',
            'Description': '基于 Selenium 的微服务前端功能与性能测试',
            'Test Items': '页面加载、货币切换、商品浏览、购物车、订单提交',
            'Browsers': 'Chrome, Edge, Firefox'
        }
    except (AttributeError, KeyError):
        pass


def pytest_html_report_title(report):
    """设置 HTML 报告标题"""
    report.title = "OnlineBoutique Selenium 测试报告"


def pytest_html_results_summary(prefix, summary, postfix):
    """自定义报告摘要"""
    prefix.extend([
        '<p><strong>测试阶段:</strong> 阶段三 - 前端自动化测试</p>',
        '<p><strong>测试工具:</strong> Selenium WebDriver</p>',
        '<p><strong>测试目标:</strong> 验证 OnlineBoutique 前端功能与性能</p>'
    ])
