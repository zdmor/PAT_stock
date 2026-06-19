# 审查提示词：design_key_levels.md

- **本提示词路径**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_key_levels_prompt.md`
- **被审查文件**：`D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md`（775 行）
- **审查方式**：阅读本文 + 按路径打开源文件 → 对照设计文档逐项核查 → 输出审查结论

---

## 一、文件基本信息

| 字段 | 值 |
|------|-----|
| 被审查文件 | `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md` |
| 行数 | 775 |
| 阶段归属 | Phase 0 产出（CRD） |
| 对应代码 | `D:\ClaudeWorkspace\PAT_stock\patterns\key_levels.py` |
| 对应测试 | `D:\ClaudeWorkspace\PAT_stock\test\test_key_levels.py`（22/22 ✅） |
| 当前状态 | 已编码，22/22 测试通过，未正式审查冻结 |

---

## 二、背景

关键位（Key Levels）是 Al Brooks 体系中支撑/阻力的实现方式。不同于传统 S/R 画法（直线），Brooks 使用 Swing 高低点聚类来识别"价格停留过的地方"——机构在此位置有订单积累。

设计文档的定位： 定义 Swing 检测 → 价格自适应聚类 → 强度评分 → 质量警告的完整管线。

---

## 审查任务

### 第一优先级（委托人指定）：源文件对应关系与一致性

审查人对 design_key_levels.md 中的每个算法参数、判定规则、数据结构字段，逐一回答以下问题：

① **源文件对应关系**： 这个定义在 Brooks 原著的哪个章节/哪页？Swing 检测窗口=5、聚类容差=1.5%、半衰期=60、触摸缓冲=0.5 ATR——这些参数在原著中有无依据？如果来自经验值/主观判断，是否已标注？

② **多源一致性**： 同一概念在不同文档（design_key_levels.md / requirements.md / concept_map.md）中的定义是否一致？关键位的强度评分逻辑在不同文档中是否有冲突？

③ **理解正确性**： Brooks 的"价格停留过的地方"是否被正确量化为聚类算法？有没有加入 Brooks 体系中不存在的概念？14 个字段各有何出处？

### 第二优先级（审查人补充）：算法设计与实现可行性

- 聚类容差的自适应公式 max(1.5%, 0.10 元) 在不同市值股票上的表现是否合理？
- 时效衰减模型（半衰期=60）是否符合 A 股特点？
- polarity_flips 和 fakeout_history 作为 stub（空列表）的接口预留方式是否合理，后续扩展时是否需要破坏现有接口？
- 当前代码（key_levels.py, 22/22 ✅）与设计文档的实现是否一致？空输入/新股/横盘等边缘情况是否已覆盖？

---

## 三、源文件清单（完整路径）

| 编号 | 文件说明 | 完整路径 |
|------|----------|----------|
| S1 | 被审查设计文档 | `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md` |
| S2 | 上游需求文档 | `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md` |
| S3 | 概念映射文档 | `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md` |
| S4 | 项目启动书 | `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md` |
| S5 | A 股适配规则 | `D:\ClaudeWorkspace\PAT_stock\docs\ashare_adaptation.md` |
| S6-S8 | 原著三件套 | `C:\Users\sut-b\Desktop\Trading price action\`（3 PDF） |
| S9 | 13 份蒸馏笔记 | `C:\Users\sut-b\Desktop\Trading price action\*.md`（6272 行） |
| S10 | 代码实现 | `D:\ClaudeWorkspace\PAT_stock\patterns\key_levels.py` |
| S11 | 单元测试 | `D:\ClaudeWorkspace\PAT_stock\test\test_key_levels.py` |
| S12 | 消费方（pinbar 检测） | `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py` |
| S13 | 消费方（主管线） | `D:\ClaudeWorkspace\PAT_stock\pipeline.py` |
| S14 | 架构设计（模块协议） | `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md` |
| S15 | 已有审查记录 | `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md` |
| S16 | 项目白皮书 | `D:\ClaudeWorkspace\PAT_stock\docs\philosophy.md` |

---

## 四、核心设计决策

### 4.1 Swing 检测

| 参数 | 当前值 | 说明 |
|------|--------|------|
| 检测窗口 | 5 根 K 线 | 标准 swing high/low（左 n 右 n 各 2 根） |
| 方法 | 局部极值 | 连续 N 根 K 线的最高/最低点 |

### 4.2 价格自适应聚类

| 参数 | 当前值 | 说明 |
|------|--------|------|
| 容差公式 | max(1.5%, 0.10 元) | 百分比容差 + 最低绝对值（保护低价股） |
| 合并策略 | 两轮合并 | 第一轮：cluster 间距离 < 容差则合并；第二轮：新高/新低检查 |
| 低价股保护 | 0.10 元保底 | 1.5% 在 2 元股上只有 0.03 元，容差太小 |

### 4.3 KeyLevel 数据结构（14 字段）

```
level_price    float   关键位价格（加权均值）
price_min      float   该关键位最低价
price_max      float   该关键位最高价
strength       int     归属于该关键位的 swing 点数
swing_count    int     swing high + swing low 总数
touch_count    int     价格触摸次数（含 ATR 缓冲判定）
recency_weighted_strength  float  时效加权强度（半衰期=60 根 K 线，约 3 个月）
both_sides     bool    是否同时作为支撑和阻力（×1.5 加权）
first_date     str     首次出现日期
last_date      str     最近出现日期
cluster_prices list    cluster 内所有原始 swing 价格
formation_type str     "high" / "low" / "both"
polarity_flips list    [P1.2b stub] 极性翻转记录
fakeout_history list   [P1.2c stub] 假突破记录
```

### 4.4 强度评分

| 维度 | 算法 |
|------|------|
| 基础强度 | swing_count 和 touch_count 的加权组合 |
| 时效衰减 | 半衰期 60 根 K 线（约 3 个月），越新的 swing 权重越高 |
| both_sides 加成 | 同时做支撑+阻力的关键位 ×1.5 |

### 4.5 触摸计数

- 使用 0.5 × ATR 缓冲区：价格距 level_price ≤ 0.5 ATR 即视为触摸
- 避免"差一分钱没碰上"的 false negative

### 4.6 质量警告

| 条件 | 警告 | 含义 |
|------|------|------|
| 密度 > 0.20 levels/100 bars | high_density | 关键位太多，信号噪音大 |
| swing 点 < 3 个 | low_density | 数据太少，关键位不可靠 |

### 4.7 函数签名

```python
def swing_highs(close: pd.Series, window: int = 5) -> pd.Series:
def swing_lows(close: pd.Series, window: int = 5) -> pd.Series:
def to_clusters(
    swing_highs: pd.Series, swing_lows: pd.Series,
    prices: pd.DataFrame, tolerance: float = 0.015,
    min_abs_tolerance: float = 0.10, half_life: int = 60
) -> tuple[list[KeyLevel], dict]:
def levels_near_price(levels: list, price: float, n: int = 3) -> list:
```

---

## 五、审查清单

### A. 算法正确性

| # | 审查项 | 参考 | 核查内容 |
|---|--------|------|----------|
| 1 | Swing 窗口=5 在日线上是否合理？ | 设计文档 §Swing | 日线 5 根 = 1 周，是否过于敏感？ |
| 2 | 容差 1.5% 在 A 股不同市值段的表现？ | 设计文档 §聚类 | 大盘股(1.5% ≈ 0.5-1元) vs 小盘股(1.5% ≈ 0.05-0.1元) |
| 3 | 0.10 元最低容差是否足够保护低价股？ | 设计文档 §低价保护 | 2 元股的 1.5%=0.03，提至 0.10 会不会合并了不该合并的？ |
| 4 | half_life=60（约 3 个月）的理论依据？ | 设计文档 §时效 | A 股的关键位记忆周期是否更长或更短？ |

### B. 边缘情况覆盖

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | 空 DataFrame → 返回空列表？ | |
| 2 | 只有不到 60 根 K 线的新股如何计算？ | |
| 3 | 价格长时间横盘→大量 swing 点→high_density 警告后的处理？ | |
| 4 | 复权后 swing 点价格变化→cluster 漂移？ | |
| 5 | key_levels 的输入是前复权价格，pinbar.py 用同一口径？ | |

### C. 代码实现一致性

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | KeyLevel 14 字段全部实现？ | 确认 polarity_flips 和 fakeout_history 为 stub（空列表） |
| 2 | 返回格式 tuple[list[KeyLevel], dict] 一致？ | 第二个 dict 含 quality_warning |
| 3 | 空输入→空列表？ | |
| 4 | quality_warning 的 high_density / low_density 阈值实现正确？ | |

### D. 与系统一致性

| # | 审查项 | 核查内容 |
|---|--------|----------|
| 1 | key_levels.py 输出格式被 pinbar.py 正确消费？ | levels_near_price 接口对齐 |
| 2 | 与 pipeline.py 的集成方式？ | pipeline 中 S1 关键位计算→S4 pinbar 检测 |
| 3 | P1.2b 极性转换、P1.2c 假突破识别的 stub 接口设计是否合理？ | 避免后续改动破坏现有接口 |

---

## 六、关键决策点

| # | 决策 | 当前值 | 替代选项 | 影响 |
|---|------|--------|----------|------|
| D1 | Swing 窗口 | 5 | 3 / 7 / 10 | 窗口越小→关键位越多但噪音大 |
| D2 | 聚类容差 | max(1.5%, 0.10元) | 固定 1% / 固定 0.5元 | 自适应合理吗？ |
| D3 | 时效半衰期 | 60（~3个月） | 20 / 120 | 短→新信号主导，长→历史积累更多 |
| D4 | 触摸缓冲 | 0.5 ATR | 0.3 / 1.0 ATR | 太小→漏数，太大→误数 |
| D5 | both_sides 加成 | ×1.5 | ×1.2 / ×2.0 | 对评分排序的影响 |

---

## 七、全部关联文件

- `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md`（被审查文件）
- `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md`（上游需求）
- `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md`（概念映射）
- `D:\ClaudeWorkspace\PAT_stock\patterns\key_levels.py`（代码实现）
- `D:\ClaudeWorkspace\PAT_stock\test\test_key_levels.py`（单元测试）
- `D:\ClaudeWorkspace\PAT_stock\patterns\pinbar.py`（消费方）
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md`（已有审查记录）

---

## 八、审查人指引

- **估计耗时**：阅读设计文档 40min + 对照代码 20min + 输出结论 10min
- **审查重点**：聚类容差参数的自适应逻辑是否合理、时效衰减模型是否符合 A 股特点、stub 接口设计是否为后续扩展留了空间
- **审查报告输出到**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_design_key_levels_<审查人>_<日期>.md`
