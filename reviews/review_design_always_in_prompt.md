# 审查提示词：design_always_in.md

- **本提示词路径**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_always_in_prompt.md`
- **被审查文件**：`D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md`（827 行）
- **审查方式**：阅读本文 + 按路径打开源文件 → 对照设计文档逐项核查 → 输出审查结论

⚠️ **注意**：本设计文档是 Always-In 判定算法的核心定义。requirements.md 审查已发现三重不一致——requirements.md、project_charter.md、design_always_in.md 三份文档的维度列表和权重映射各不相同。审查时需以本文件为准，统一另外两份。

---

## 一、文件基本信息

| 字段 | 值 |
|------|-----|
| 被审查文件 | `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md` |
| 行数 | 827 |
| 阶段归属 | Phase 0 产出（CRD） |
| 对应代码 | `D:\ClaudeWorkspace\PAT_stock\state\market_state.py` |
| 当前状态 | 已编码（3 维简化版/5 维版两版），未正式审查冻结 |

---

## 二、背景

Always-In 是 Al Brooks 价格行为学的核心概念："如果必须持有一个头寸且不能退出，当前应该做多还是做空？" 它不是交易信号，而是市场背景判定——决定"允许做什么方向的事"。

设计文档的定位： 定义 5 维加权评分的完整算法，含维度定义、权重分配、阈值判定、置信度计算、多时间框架协同。

---

## 审查任务

### 第一优先级（委托人指定）：源文件对应关系与一致性

审查人对 design_always_in.md 中的每个维度定义、权重分配、判定阈值，逐一回答以下问题：

① **源文件对应关系**： 五维加权系统（EMA20 斜率 0.30、高低点结构 0.25、通道位置 0.20、回调深度 0.15、Gap 棒 0.10）——每个维度和权重在 Brooks 原著的哪个章节有定义？±0.30 阈值在原著中是否有依据？置信度公式 min(abs(score), 1.0) 来自哪里？

② **多源一致性——这是当前最严重的问题**： requirements.md（L342-348）、project_charter.md、design_always_in.md（§1.2）三份文档定义了三套不同的维度-权重映射，但权重数字完全一样（0.30/0.25/0.20/0.15/0.10）。审查人需确认：以哪份文档为准？其他文档如何统一？

③ **理解正确性**： Brooks 的 Always-In 概念是否被正确量化为加权评分模型？有没有简化过度或加入不存在的新维度？当前代码实现的是 3 维版（权重 0.35/0.40/0.25），与任何文档都不一致——这是设计变更还是编码偏差？

### 第二优先级（审查人补充）：算法设计与 A 股适配

- 阈值 ±0.30 在 A 股大部分时间震荡的背景下，是否会导致 NONE 比例过高（> 50%）？
- 新股（< 20 根 K 线）无 EMA20 时如何降级？连续涨跌停是否扭曲判定？
- 趋势强度分类（AAA/AA/A/B/C）的条件是否可量化、可复现？
- 多时间框架协同（周线+日线）的接口是否已定义？冲突时如何裁决？

---

## 三、源文件清单（完整路径）

| 编号 | 文件说明 | 完整路径 |
|------|----------|----------|
| S1 | 被审查设计文档 | `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md` |
| S2 | 上游需求文档（维度定义冲突源 #1） | `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md` |
| S3 | 项目启动书（维度定义冲突源 #2） | `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md` |
| S4 | 概念映射文档 | `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md` |
| S5 | A 股适配规则 | `D:\ClaudeWorkspace\PAT_stock\docs\ashare_adaptation.md` |
| S6-S8 | 原著三件套 | `C:\Users\sut-b\Desktop\Trading price action\`（3 PDF） |
| S9 | 13 份蒸馏笔记 | `C:\Users\sut-b\Desktop\Trading price action\*.md`（6272 行） |
| S10 | 代码实现（3 维版，与任何文档不一致） | `D:\ClaudeWorkspace\PAT_stock\state\market_state.py` |
| S11 | 消费方（主管线） | `D:\ClaudeWorkspace\PAT_stock\pipeline.py` |
| S12 | 消费方（陷阱检测） | `D:\ClaudeWorkspace\PAT_stock\patterns\trap.py` |
| S13 | 架构设计（模块协议） | `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md` |
| S14 | 已有审查记录 | `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md` |
| S15 | 项目白皮书 | `D:\ClaudeWorkspace\PAT_stock\docs\philosophy.md` |

---

## 四、核心设计决策

### 4.1 五维加权系统（design_always_in.md §1.2 定义）

| 维度 | 权重 | 评分逻辑 |
|------|------|----------|
| EMA20 斜率 | 0.30 | 均线方向向上/向下 → 核心趋势信号 |
| 高/低点结构 | 0.25 | HH+HL=+1, LL+LH=-1, 混合=0 |
| 通道位置 | 0.20 | 价格在通道中的相对位置（上轨/下轨/中轨） |
| 回调深度 | 0.15 | < 前波 33% → +1, > 50% → -1 |
| Gap 棒 | 0.10 | 跳空方向（向上=+1, 向下=-1, 无=0） |

判定规则： 加权总分 > +0.30 → 多头市场，< -0.30 → 空头市场，中间 → 震荡

置信度： confidence = min(abs(weighted_score), 1.0)

### 4.2 三重不一致（⚠️ 关键问题）

| 来源 | 维度列表 | 权重分配 |
|------|----------|----------|
| requirements.md L342-348 | 20缺口棒 / 高/低点结构 / K线实体倾向 / 回调深度 / 均线位置 | 0.30/0.25/0.20/0.15/0.10 |
| project_charter.md | 缺口棒 / 高低点 / EMA20斜率 / 回调深度 / 通道位置 | 0.30/0.25/0.20/0.15/0.10 |
| design_always_in.md §1.2 | EMA20斜率 / 高低点结构 / 通道位置 / 回调深度 / Gap棒 | 0.30/0.25/0.20/0.15/0.10 |

维度名不同、权重对应不同维度——同一个参数三种定义。审查时需确认以 design_always_in.md 为准，或会议统一。

### 4.3 当前代码实现（3 维简化版）

当前 market_state.py 实现的是 3 维加权（权重 0.35/0.40/0.25），与任何文档的 5 维定义都不一致。

### 4.4 趋势强度分类

| 级别 | 条件 |
|------|------|
| 强趋势(AAA) | 回调 < 前波 33%，价格在 EMA20 单侧运行 |
| 中等趋势(AA) | 回调 33%-50%，偶尔穿越 EMA20 |
| 弱趋势(A) | 回调 > 50%，频繁穿越 EMA20 |
| 区间(B) | 无明显方向，边界清晰 |
| 下跌趋势(C) | 均线压制，反弹无力 |

### 4.5 函数签名

```python
def determine_always_in(
    df: pd.DataFrame,
    weights: dict = None  # 默认从 config 读取
) -> tuple[str, float]:
    """返回 (direction: "LONG"/"SHORT"/"NONE", confidence: float) """

def trend_strength(df: pd.DataFrame) -> dict:
    """返回 {strength: str, retrace_depth: float, features: dict} """
```

---

## 五、审查清单

### A. 维度定义与权重

| # | 审查项 | 参考 | 核查内容 |
|---|--------|------|----------|
| 1 | 五维定义是否覆盖 Brooks 原始概念？ | design_always_in.md §1.2 | 缺哪个维度？多哪个维度？ |
| 2 | 权重 0.30/0.25/0.20/0.15/0.10 的来源依据？ | 无数据支撑 | 是 Brooks 原书数据还是作者估计？ |
| 3 | 阈值 ±0.30 是否合理？ | design_always_in.md §判定 | 太严→NONE 太多(大部分A股在震荡)，太松→方向频繁切换 |
| 4 | 各维度的具体评分函数是否合理？ | design_always_in.md §各维度 | 例如 "EMA20 斜率" 的具体算法是什么？ |

### B. 三重不一致修复确认

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 审查后确定以哪个文档为准？ | design_always_in.md / requirements.md / project_charter.md |
| 2 | 其他两份文档是否需要更新适配？ | |
| 3 | 当前代码的 3 维版是否废弃还是保留作为 fallback？ | |

### C. 边缘情况

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 新股（< 20 根 K 线）无 EMA20 的处理？ | |
| 2 | 连续涨跌停期间 Always-In 判定是否被扭曲？ | |
| 3 | 复权导致 EMA20 跳变的处理？ | |
| 4 | 周线级 Always-In 需要多少数据？不足时如何降级？ | |
| 5 | 市场状态判定为 NONE 的频率预期？如果 > 50% 是否说明阈值设计有问题？ | |

### D. 与系统一致性

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | market_state.py 输出被 pipeline.py 正确消费？ | 字段名对齐 |
| 2 | trend_strength 输出被 trap.py / strategies 模块使用？ | |
| 3 | 多时间框架协同（周线+日线）的接口已定义？ | |

---

## 六、关键决策点

| # | 决策 | 当前值 | 替代选项 | 影响 |
|---|------|--------|----------|------|
| D1 | 维度数量 | 5 维 | 3 维（当前代码） / 4 维 / 6 维 | 维度越多精度越高？还是噪音越大？ |
| D2 | 权重分配 | 0.30/0.25/0.20/0.15/0.10 | 等权 / 其他分布 | 权重决定了哪个维度主导判断 |
| D3 | 方向阈值 | ±0.30 | ±0.20 / ±0.40 / ±0.60 | 决定 NONE 比例 |
| D4 | 置信度公式 | min(abs(score), 1.0) | 非线性映射 / sigmoid | 影响下游仓位计算 |
| D5 | 多TF冲突 | 冲突=不交易 | 冲突=减半仓 / 取日线 | 安全性 vs 可操作性 |

---

## 七、全部关联文件

- `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md`（被审查文件）
- `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md`（上游需求，维度定义不一致待统一）
- `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md`（引述，维度定义不一致待统一）
- `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md`（概念映射）
- `D:\ClaudeWorkspace\PAT_stock\state\market_state.py`（代码实现，当前 3 维版）
- `D:\ClaudeWorkspace\PAT_stock\patterns\pipeline.py`（消费方）
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md`（已有审查记录，含三重不一致）

---

## 八、审查人指引

- **估计耗时**：阅读设计文档 40min + 对照代码 20min + 三重不一致分析 15min + 输出结论 10min
- **审查重点**：
  - 必做：确定五维定义的标准版本，统一 requirements.md 和 project_charter.md
  - 必做：确认当前 3 维代码升级到 5 维的迁移方案
  - 权重分配是否有理论或数据依据
  - 阈值选择是否符合 A 股特点（大部分时间震荡）
- **审查报告输出到**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_always_in_<审查人>_<日期>.md`
