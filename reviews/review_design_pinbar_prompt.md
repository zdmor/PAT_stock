# 审查提示词：design_pinbar.md

- **本提示词路径**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_pinbar_prompt.md`
- **被审查文件**：`D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md`（730 行）
- **审查方式**：阅读本文 + 按路径打开源文件 → 对照设计文档逐项核查 → 输出审查结论

---

## 一、文件基本信息

| 字段 | 值 |
|------|-----|
| 被审查文件 | `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md` |
| 行数 | 730 |
| 阶段归属 | Phase 0 产出（CRD） |
| 对应代码 | `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py` |
| 对应测试 | `D:\ClaudeWorkspace\PAT_stock\test\test_pinbar.py` |
| 当前状态 | 已编码、已测试（10/10），未正式审查冻结 |

---

## 二、背景

Pinbar（Pinocchio Bar / 长影线K线）是 Al Brooks 体系中最基础的信号形态。一根 Pinbar 暗示价格在该方向被拒绝，机构在这个位置反向操作。

设计文档的定位： 将 Brooks 对 Pinbar 的自然语言描述转化为精确的量化算法（几何条件 + 关键位上下文）。

---

## 审查任务

### 第一优先级（委托人指定）：源文件对应关系与一致性

审查人对 design_pinbar.md 中的每个算法参数、判定规则、数据结构字段，逐一回答以下问题：

① **源文件对应关系**： 这个定义在 Brooks 原著的哪个章节/哪页？如果来自 distillation note，在哪个 note 的哪个段落？如果来自经验值/A 股适配，是否明确标注了"经验值"而非伪造成原著来源？

② **多源一致性**： 同一概念在不同文档（design_pinbar.md / requirements.md / concept_map.md / project_charter.md）中的定义是否一致？参数值是否有冲突？

③ **理解正确性**： Brooks 的自然语言→量化规则的转化过程中，是否丢失核心语义？是否加入了 Brooks 体系中不存在的新概念？参数阈值是否标注了来源类型（原著/经验值/占位符）？

### 第二优先级（审查人补充）：算法设计与实现可行性

- 算法设计在技术实现上是否可行？向量化方案是否合理？
- 边缘情况是否被充分覆盖（零范围 K 线、NaN ATR、空 DataFrame、缺列、涨跌停）？
- 模块间接口（pinbar ↔ key_levels ↔ pipeline）是否对齐且无歧义？
- 当前代码（pinbar.py）与设计文档的实现是否一致？

---

## 三、源文件清单（完整路径）

| 编号 | 文件说明 | 完整路径 |
|------|----------|----------|
| S1 | 被审查设计文档 | `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md` |
| S2 | 上游需求文档 | `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md` |
| S3 | 概念映射文档 | `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md` |
| S4 | 项目启动书 | `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md` |
| S5 | A 股适配规则 | `D:\ClaudeWorkspace\PAT_stock\docs\ashare_adaptation.md` |
| S6-S8 | 原著三件套 | `C:\Users\sut-b\Desktop\Trading price action\`（3 PDF） |
| S9 | 13 份蒸馏笔记 | `C:\Users\sut-b\Desktop\Trading price action\*.md`（6272 行） |
| S10 | 代码实现 | `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py` |
| S11 | 单元测试 | `D:\ClaudeWorkspace\PAT_stock\test\test_pinbar.py` |
| S12 | 消费方（主管线） | `D:\ClaudeWorkspace\PAT_stock\pipeline.py` |
| S13 | 输入来源（关键位） | `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md` |
| S14 | 输入来源（关键位实现） | `D:\ClaudeWorkspace\PAT_stock\patterns\key_levels.py` |
| S15 | 已有审查记录 | `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md` |
| S16 | 项目白皮书 | `D:\ClaudeWorkspace\PAT_stock\docs\philosophy.md` |

---

## 四、核心设计决策

### 4.1 Pinbar 判定算法

| 参数 | 当前值 | 来源 | 说明 |
|------|--------|------|------|
| main_shadow_ratio | ≥ 2/3 全幅 (0.667) | Brooks 原著 | 主力影线长度 ≥ K线范围的 2/3 |
| body_position_threshold | 0.4 (40%) | 经验值 | 实体位于 K线对端 40% 范围内 |
| min_range_atr_ratio | 0.3 (30% ATR) | 经验值 | 波幅太小不认，过滤噪音 |
| atr_window | 20 | 标准参数 | ATR 计算窗口 |

### 4.2 信号输出

| 字段 | 值域 | 说明 |
|------|------|------|
| signal | -1 / 0 / 1 | -1=上影线Pinbar(空信号), 1=下影线Pinbar(多信号) |
| signal_type | "bull_pinbar" / "bear_pinbar" / null | 类型标签 |
| pinbar_strength | "strong" / "normal" | 主影线 ≥ 全幅 80% → strong |
| near_key_level | true / false | 影线尖在 1 ATR 内有关键位 |
| key_level_distance | float | 影线尖到最近关键位的 ATR 倍数 |

### 4.3 关键位关联逻辑

- 影线尖距离关键位 ≤ 1 ATR → near_key_level = true
- 支持多关键位：返回最近的关键位距离和方向

### 4.4 边缘情况处理

| 场景 | 处理方式 |
|------|----------|
| total_range == 0（最高=最低） | 返回 signal=0，跳过 |
| NaN ATR | 返回 signal=0，跳过 |
| 空 DataFrame | 返回空结果 |
| 缺列（如缺 high/low/close） | 抛出明确的列名错误 |
| Doji + Pinbar 共存 | 取判定更强者 |
| 涨跌停板 | pinbar 模块做纯几何判定，不过滤留给策略层 |
| Limit up/down 极值K线 | 几何判定仍产生信号，但 danger_zone 标记为 true |

### 4.5 函数签名

```python
def detect_pinbar(
    df: pd.DataFrame,
    key_levels: list = None,
    main_shadow_ratio: float = 2/3,
    body_position_threshold: float = 0.4,
    min_range_atr_ratio: float = 0.3,
    atr_window: int = 20
) -> pd.DataFrame:
    """向量化 Pinbar 检测，返回原 DataFrame + 7 列信号列"""
```

---

## 五、审查清单

### A. 算法正确性

| # | 审查项 | 参考 | 核查内容 |
|---|--------|------|----------|
| 1 | 主影线比例 2/3 是否有 Brooks 原文依据？ | design_pinbar.md §算法 | Brooks 说"long tail"——2/3 是合理阈值还是过于严格？ |
| 2 | body_position_threshold=0.4 的出处？ | 无出处，标注经验值 | 这个值在 A 股日线上是否应该调整？ |
| 3 | min_range_atr_ratio=0.3，过滤掉多少日线？ | 无 A 股数据支撑 | M1.5 数据探测后才能回答——但代码已用此值 |
| 4 | 近关键位判定：1 ATR 阈值是否合理？ | 设计文档 §关键位关联 | 过大→随便一个关键位都 near，过小→关联不到 |

### B. 边缘情况覆盖

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 零范围 K 线（一字板）是否正确处理？ | |
| 2 | 复权后出现负价或极端值的处理？ | |
| 3 | 上市首日无 ATR 的股票如何处理？ | |
| 4 | DataFrame 索引不连续（跳空交易日）的影响？ | |
| 5 | 关键位列表为空时，near_key_level 是否正常 false？ | |

### C. 代码实现一致性（对照代码）

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 函数签名与设计文档一致？ | 参数名、默认值、返回结构 |
| 2 | 7 个新增列名与文档一致？ | 对齐 review_chain.md 断言检查 |
| 3 | 向量化实现（无显式循环 for/while）？ | |
| 4 | 边界条件覆盖（空/NaN/缺列/零range）？ | |

### D. 与系统一致性

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | pinbar.py 的输出被 pipeline.py 正确消费？ | 列名是否对齐？ |
| 2 | pinbar.py 的 key_levels 参数格式与 key_levels.py 输出一致？ | |
| 3 | pinbar 模块不过滤涨跌停——策略层是否确实有处理？ | 确认 M5 price_limit.py 已实现 |

---

## 六、关键决策点

| # | 决策 | 当前值 | 替代选项 | 影响 |
|---|------|--------|----------|------|
| D1 | 主影线比例 | ≥ 2/3 | ≥ 3/4 / ≥ 1/2 | 越严格信号越少但质量越高 |
| D2 | 关键位距离阈值 | 1 ATR | 0.5 ATR / 2 ATR | 影响 near_key_level 判断 |
| D3 | 最小波幅 | 0.3 ATR | 0.2 / 0.4 / 无限制 | 过小→噪音，过大→漏信号 |
| D4 | 强/普通分档 | 80% 分界 | 75% / 85% | 只影响 pinbar_strength 标签 |
| D5 | 涨跌停处理 | 不过滤 | 直接过滤/标记 danger | 取决于策略层是否信任几何信号 |

---

## 七、全部关联文件

- `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md`（被审查文件）
- `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md`（上游需求）
- `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md`（概念映射）
- `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py`（代码实现）
- `D:\ClaudeWorkspace\PAT_stock\test\test_pinbar.py`（单元测试）
- `D:\ClaudeWorkspace\PAT_stock\patterns\pipeline.py`（消费方）
- `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md`（key_levels 输入来源）
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md`（已有审查记录）

---

## 八、审查人指引

- **估计耗时**：阅读设计文档 30min + 对照代码 20min + 输出结论 10min
- **审查重点**：算法参数的来源依据（哪些是 Brooks 原书数据？哪些是估计？哪些是占位？）、边缘情况覆盖、与 key_levels 模块的接口对齐
- **审查报告输出到**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_pinbar_<审查人>_<日期>.md`
