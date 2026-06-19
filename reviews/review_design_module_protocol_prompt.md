# 审查提示词：design_module_protocol.md

- **本提示词路径**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_module_protocol_prompt.md`
- **被审查文件**：`D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md`（812 行）
- **审查方式**：阅读本文 + 按路径打开源文件 → 对照设计文档逐项核查 → 输出审查结论

---

## 一、文件基本信息

| 字段 | 值 |
|------|-----|
| 被审查文件 | `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md` |
| 行数 | 812 |
| 阶段归属 | Phase 0 产出（CRD） |
| 对应代码 | `D:\ClaudeWorkspace\PAT_stock\pipeline.py` |
| 当前状态 | 已编码，未正式审查冻结 |

---

## 二、背景

本文件定义 PAT 系统所有模块之间的接口契约、数据流方向、管线编排顺序。它不是某个具体算法的设计，而是整个系统的"接线图"。

设计文档的定位： 确保各模块各自独立开发后，合入 pipeline 时能无缝衔接。任何新增模块必须先过此协议。

---

## 审查任务

### 第一优先级（委托人指定）：源文件对应关系与一致性

审查人对 design_module_protocol.md 中的管线编排顺序、pipeline_result 数据结构、模块接口定义，逐一回答以下问题：

① **源文件对应关系**： 6 步执行顺序（S1→S6）的依据来自哪里？每步的输入输出是否能在对应的设计文档（design_key_levels.md / design_always_in.md / design_pinbar.md）中找到准确定义？pipeline_result 的各字段是否能在各模块设计文档中找到对应？

② **多源一致性**： pipeline_result 的字段名和类型，是否与各设计文档中的函数签名输出一致？例如 market_state 的输出格式在 design_always_in.md 和 design_module_protocol.md 中是否对齐？

③ **理解正确性**： "单向数据流 L1→L6" 是否是 Brooks 体系的要求，还是架构设计层面的选择？"追加不覆盖"原则是否可能在后续版本中导致数据冗余？降级路径（软降级用默认值）是否会掩盖 bug？

### 第二优先级（审查人补充）：架构合理性与可扩展性

- 模块间耦合度是否合理？risk 模块是否需要所有上游数据？
- 新增一个策略模块的接入成本是多少？需改多少文件？
- 60 分钟线加入后，当前 pipeline_result 结构是否需要重构？
- 回测引擎如何接入同一管线——是复用 pipeline.py 还是独立实现？
- 错误隔离策略（每个模块捕获自身异常）是否确实做到了"一个模块挂了不影响其他"？

---

## 三、源文件清单（完整路径）

| 编号 | 文件说明 | 完整路径 |
|------|----------|----------|
| S1 | 被审查设计文档 | `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md` |
| S2 | 上游需求文档 | `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md` |
| S3 | 关键位设计文档（S1 定义） | `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md` |
| S4 | Always-In 设计文档（S2 定义） | `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md` |
| S5 | Pinbar 设计文档（S3-S4 定义） | `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md` |
| S6 | 主管线代码 | `D:\ClaudeWorkspace\PAT_stock\pipeline.py` |
| S7 | 关键位实现 | `D:\ClaudeWorkspace\PAT_stock\patterns\key_levels.py` |
| S8 | Always-In 实现 | `D:\ClaudeWorkspace\PAT_stock\state\market_state.py` |
| S9 | Pinbar 实现 | `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py` |
| S10 | A 股适配规则 | `D:\ClaudeWorkspace\PAT_stock\docs\ashare_adaptation.md` |
| S11 | 概念映射文档 | `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md` |
| S12 | 项目启动书 | `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md` |
| S13-S15 | 原著三件套 | `C:\Users\sut-b\Desktop\Trading price action\`（3 PDF） |
| S16 | 13 份蒸馏笔记 | `C:\Users\sut-b\Desktop\Trading price action\*.md`（6272 行） |
| S17 | 已有审查记录 | `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md` |
| S18 | 项目白皮书 | `D:\ClaudeWorkspace\PAT_stock\docs\philosophy.md` |

---

## 四、核心设计决策

### 4.1 管线执行顺序（6 步）

```
S1: key_levels.compute()       → 关键位计算
S2: market_state.analyze()     → Always-In 判定
S3: signal_bar.detect()       → 信号K线识别
S4: pinbar.detect_pinbar()    → Pinbar 检测
S5: trap.detect_all()         → 陷阱识别
S6: risk 模块                  → 仓位+止损计算
```

每步追加输出到 pipeline_result dict，不覆盖。

### 4.2 pipeline_result 数据结构

```python
pipeline_result = {
    "stock_code": str,
    "date": str,
    "key_levels": {
        "levels": list[KeyLevel],
        "quality_warning": dict
    },
    "market_state": {
        "always_in": str,           # "LONG"/"SHORT"/"NONE"
        "confidence": float,        # 0.0~1.0
        "trend_strength": str,      # "AAA"/"AA"/"A"/"B"/"C"
        "spike_channel": dict,
        "market_cycle": str
    },
    "signal_bars": pd.DataFrame,
    "pinbar": pd.DataFrame,         # 原 df + 7 列信号
    "traps": list[dict],            # 所有检测到的陷阱
    "risk": {
        "position_size": float,
        "stop_loss": float,
        "target": float,
        "te_verdict": str           # "high_quality"/"pass"/"reject"
    }
}
```

### 4.3 模块接口契约原则

1. **单向数据流**：L1→L2→L3→L4→L5→L6，不反向回写
2. **追加不覆盖**：每步只增加字段，不改已有字段
3. **独立可测**：每个模块可脱离 pipeline 独立运行
4. **缺省降级**：上游模块输出缺失时，下游模块有合理的默认行为

### 4.4 降级路径

| 场景 | 行为 |
|------|------|
| 数据加载失败 | 跳过该股票，记入错误日志 |
| 关键位计算失败 | 使用简单 S/R（swing high/low 直接标注） |
| Always-In 判定失败 | 默认 NONE，趋势强度默认 B |
| Pinbar 检测失败 | 返回空信号列 |
| 陷阱检测失败 | 返回空陷阱列表 |
| 风控计算失败 | 仓位设为 0 |

### 4.5 错误传播

- 每个模块捕获自己的异常，不向 pipeline 上层抛出
- 错误信息记入 pipeline_result["errors"] 列表
- pipeline 主流程不受单模块错误影响

---

## 五、审查清单

### A. 管线编排

| # | 审查项 | 参考 | 核查内容 |
|---|--------|------|----------|
| 1 | 6 步执行顺序是否合理？是否有模块前置依赖错乱？ | §执行顺序 | Always-In(S2) 在关键位(S1)之后——正确吗？ |
| 2 | 每步的输入输出是否与各设计文档一致？ | S2-S4 | 字段名、类型对齐 |
| 3 | 模块间是否有不必要的耦合？ | §pipeline_result | 例如 risk 模块是否需要所有上游数据？ |

### B. pipeline_result 数据流

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 所有下游模块需要的字段是否都有定义？ | |
| 2 | 是否有重复字段或命名不一致？ | |
| 3 | pd.DataFrame 在模块间传递的兼容性（列名一致性）？ | |

### C. 异常处理与降级

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 降级行为是否合理？极端 case 全部降级后的输出是什么？ | |
| 2 | 错误日志是否包含足够的诊断信息（股票代码、模块名、异常类型）？ | |
| 3 | "一个模块挂了不影响其他"——是否真的做到了？ | |

### D. 可扩展性

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 新增一个策略模块（如 Best Trade 评分）的接入成本？ | |
| 2 | 接口契约是否必须版本化？ | |
| 3 | 60 分钟线加入后，数据结构是否需要重构？ | |
| 4 | 回测引擎如何接入同一管线？是复用 pipeline.py 还是独立实现？ | |

### E. 与代码实现一致性

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | pipeline.py 的 import 列表和调用顺序与文档一致？ | |
| 2 | pipeline_result 的 key 名与文档一致？ | |
| 3 | 错误处理逻辑（try/except 范围）与文档一致？ | |
| 4 | 降级逻辑是否实现？还是抛异常了事？ | |

---

## 六、关键决策点

| # | 决策 | 当前选择 | 替代选项 | 影响 |
|---|------|----------|----------|------|
| D1 | 数据流方向 | 单向 L1→L6 | L3→L2 反馈回路 | 反馈回路是架构创新，但当前协议未定义实现方式 |
| D2 | 追加不覆盖 | 每步追加字段 | 重写整个 dict | 追加不会丢失前序输出 |
| D3 | 错误隔离 | 每个模块捕获自身异常 | 谁调谁负责 | 隔离性更好但 debug 困难 |
| D4 | 降级策略 | 软降级（默认值） | 硬失败（抛异常） | 管线更健壮，但可能掩盖 bug |
| D5 | 数据结构 | 嵌套 dict | pandas DataFrame / dataclass | dict 灵活但无类型检查 |

---

## 七、全部关联文件

- `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md`（被审查文件）
- `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md`（模块接口）
- `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md`（模块接口）
- `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md`（模块接口）
- `D:\ClaudeWorkspace\PAT_stock\pipeline.py`（主管线代码）
- `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py`（模块实现）
- `D:\ClaudeWorkspace\PAT_stock\patterns\key_levels.py`（模块实现）
- `D:\ClaudeWorkspace\PAT_stock\state\market_state.py`（模块实现）
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md`（已有审查记录）

---

## 八、审查人指引

- **估计耗时**：阅读设计文档 30min + 对照各模块接口 20min + 输出结论 10min
- **审查重点**：
  - 模块间接口是否足够松耦合
  - 降级路径是否合理（降级过多=无声失败）
  - 新增模块的接入成本是否可控
  - L2↔L3 反馈回路在协议中的实现方式
- **审查报告输出到**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_module_protocol_<审查人>_<日期>.md`
