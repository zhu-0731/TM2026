# VeADK 离线诊断 Agent

## 目标

`veadk_app` 的职责是把离线诊断引擎封装成一个可交互、可多轮推理、可调用工具的 `VeADK + LLM` Agent。

它现在主要负责：

1. 读取离线数据窗口
2. 调用内部工具执行异常检测
3. 调用内部工具执行根因分析
4. 生成结构化诊断报告
5. 以对话方式解释诊断结果

说明：

- 当前版本聚焦 `离线模式`
- 实时监控、Prometheus 采集、在线证据补全等能力在 `online/` 中实现

## 文件说明

```text
aiops_agent/veadk_app/
  __init__.py
  agent.py
  prompts.py
  tools.py
  README.md
```

- `agent.py`
  VeADK Agent 入口，支持交互模式和单轮模式。
- `prompts.py`
  离线 Agent 的系统提示词、默认用户请求和欢迎语。
- `tools.py`
  把离线引擎封装成可供 Agent 调用的工具。

## 当前工具

### `run_full_offline_diagnosis_tool`

一步完成：

- 加载窗口
- 异常检测
- 根因分析
- 报告输出

这是最推荐优先调用的主工具。

### `find_anomalous_windows_tool`

扫描数据切分，寻找最可疑的异常窗口。

### `load_window_tool`

单独加载离线时间窗口。

### `detect_anomaly_tool`

对当前窗口执行规则异常检测。

### `diagnose_root_cause_tool`

对当前检测结果执行根因分析。

### `write_report_tool`

将当前诊断结果写成 JSON / Markdown 报告。

## 运行方式

在项目根目录运行：

```powershell
python -m aiops_agent.veadk_app.agent
```

也可以统一通过包入口运行：

```powershell
python -m aiops_agent.main
```

如果只想发起一条单轮请求：

```powershell
python -m aiops_agent.main --prompt "请帮我分析 valid split 的异常窗口"
```

## 设计定位

当前仓库里，离线模式已经默认收口到这个 Agent：

- `offline/` 保留为内部诊断引擎
- `veadk_app/` 作为离线模式唯一推荐入口

因此，后续如果你继续完善离线智能体，优先修改这几个位置：

- `veadk_app/prompts.py`
- `veadk_app/tools.py`
- `offline/detector.py`
- `offline/diagnoser.py`
