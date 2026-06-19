# 审查报告：design_always_in.md
- 审查人：枢
- 日期：2026-06-14
- 审查对象：`docs/design_always_in.md`（827行）+ `state/market_state.py`（465行）
- 关联文档：`requirements.md` L289-L564, `project_charter.md` §M2.1, `design_module_protocol.md` L1-L100, `concept_map.md` T-B01, `ashare_adaptation.md`

---

## 一、审查结论：[CONDITIONAL] — 有条件通过

design_always_in.md 的算法设计和代码实现整体质量较高，五维加权框架合理、边界处理充分、输出结构清晰。但存在**一项致命缺陷**：未能与上游权威文档 `requirements.md` / `project_charter.md` 保持维度定义一致，且 §1.2 中对其声称的 "project_charter.md 原始规划" 做了**事实性错误描述**。本审查给出 CONDITIONAL 结论——要求在执行以下修正后可升级为 PASS。

---

## 二、三重不一致分析（核心）

### 2.1 三文档维度对比表

| 位次 | requirements.md L342-348 | project_charter.md L161 | design_always_in.md §4.2-4.6 |
|:----:|--------------------------|------------------------|------------------------------|
| 1 (0.30) | **20缺口棒** — >20根K线不触MA→+1 | **20缺口棒** — 同上 | **EMA20斜率** — 最近5bar EMA差分%→score |
| 2 (0.25) | **高/低点结构** — HH+HL→+1 | **高/低点结构** — 同上 | **HH/HL结构** — 同上(名称微调) |
| 3 (0.20) | **K线实体倾向** — 阳实体>60%→+1 | **K线实体倾向** — 同上 | **通道位置** — 最近20bar收盘在EMA上方比例 |
| 4 (0.15) | **回调深度** — <前波33%→+1 | **回调深度** — 同上 | **回调深度** — 基本一致(ATR归一化) |
| 5 (0.10) | **均线位置** — 在EMA20以上→+1 | **均线位置** — 同上 | **缺口棒计数** — 15bar中收盘不触EMA比例 |
| 阈值 | **±0.60** | **±0.60 (隐式)** | **±0.30** |
| 输出 | LONG/SHORT/NONE | LONG/SHORT/NONE | bullish/bearish/oscillating |

### 2.2 差异分析

**事实发现：**
1. `requirements.md` 和 `project_charter.md` **完全一致**——五维定义、权重顺序、阈值 ±0.60 均相同。
2. `design_always_in.md` 的 §1.2 声称 project_charter 原始规划为 "缺口棒计数/高低点结构/EMA20斜率/回调深度/通道位置"，但**实际** `project_charter.md` L161 写的是 "20缺口棒/高/低点结构/K线实体倾向/回调深度/均线位置"。这是一个严重的事实性错误——design_always_in.md 错误地描述了上游文档，自行改写了历史。
3. `concept_map.md` T-B01 仅写 "5维加权评分(0.30/0.25/0.20/0.15/0.10)"，未列出具体维度名，**为不一致留下了空间**。

**实质差异维度（仅 3/5 个维度真正不同）：**

| 比较维度 | requirements/project_charter | design_always_in | 是否实质不同 |
|---------|------------------------------|-----------------|:---:|
| 权重 0.30 | 20缺口棒(二元: 不触MA计数) | EMA20斜率(连续: 差分%量化) | **是** |
| 权重 0.25 | 高/低点结构 | HH/HL结构 | 否(仅命名) |
| 权重 0.20 | K线实体倾向(二元: 实体方向%) | 通道位置(连续: 收盘高于EMA比例) | **是** |
| 权重 0.15 | 回调深度(<33%前波) | 回调深度(ATR归一化) | 否(算法增强) |
| 权重 0.10 | 均线位置(二元: above/below) | 缺口棒计数(连续: 不触EMA比例) | **是** |

### 2.3 结论：以哪个文档为准？

**裁决：以 `requirements.md` 为权威维度定义基准，但采纳 `design_always_in.md` 的算法量化方案作为 P2 增强。**

理由：

1. **权威性链条：** `project_charter.md` → `requirements.md` → `design_*.md` → 代码。`project_charter.md` 与 `requirements.md` 一致（2票对1票）。`design_always_in.md` 单方面变更未走任何变更流程、未在 requirements.md 中记录，违反了"需求驱动设计"的基本工程原则。

2. **Brooks 原著忠实度：** requirements.md 的 "20缺口棒" (T-A03) 是 Brooks 明确提出的极强趋势标志，置于最高权重 0.30 有明确的 Brooks 文本依据。design_always_in.md 将其降权到 0.10 且改为 15 bar 饱和版本，**削弱了 Brooks 体系中最独特的趋势判定信号**。

3. **但 design_always_in.md 的算法改进有实质性价值：**
   - "通道位置"（收盘>EMA比例的连续测量）比 "均线位置"（二元 above/below）**粒度更细**，能区分 "刚刚站上均线" 和 "牢牢站稳均线" 两种不同强度
   - "EMA20斜率"（差分百分比）比 "K线实体倾向"（实体方向比例）**对趋势持续性更敏感**——实体倾向受单根异常K线（如大阳吞噬小阴）影响过大
   - ±0.30 阈值比 ±0.60 更适合 A 股——A 股大部分时间震荡，±0.60 会导致 direction 几乎恒为 NONE

4. **解决原则——"取布鲁克斯之魂，不取布鲁克斯之形"：**
   如果 `20缺口棒` 是 Brooks 的 "形"（具体信号），`EMA20斜率` 是 Brooks 的 "魂"（趋势方向判定）。两者可以共存——**保留 requirements.md 的维度清单作为权威清单，采用 design_always_in.md 的量化实现作为算法实现**。

   **最终统一方案：**

| 位次 | 维度名（以 requirements.md 为准） | 权重 | 实施方案 |
|:----:|---------------------------|:----:|---------|
| 1 | EMA20 斜率方向（代替 K 线实体倾向） | 0.30 | 采用 design_always_in.md 算法 |
| 2 | 高/低点结构 | 0.25 | 一致，沿用 |
| 3 | 通道位置（代替均线位置） | 0.20 | 采用 design_always_in.md 算法 |
| 4 | 回调深度 | 0.15 | 一致，沿用 |
| 5 | 20缺口棒计数 | 0.10 | 采用 design_always_in.md 算法 |
| — | 方向阈值 | ±0.30 | 采用 design_always_in.md（A股适配） |

   **待办事项：**
   - [P0] 修正 `design_always_in.md` §1.2 中对 `project_charter.md` 的错误描述（在变更日志中诚实记录维度变更过程）
   - [P1] 更新 `requirements.md` L342-348 的维度表，对齐到统一方案
   - [P1] 更新 `project_charter.md` L161，对齐到统一方案
   - [P1] 更新 `design_module_protocol.md` L71-74（仍标记为"三维详情"的过时注释）
   - [P2] M6 回测中对比 requirements.md 原始方案 vs 统一方案的准确率，以数据最终确认

---

## 三、代码偏差分析

### 3.1 当前代码 vs 设计文档对比

当前 `state/market_state.py` 的 465 行代码实现了**完整的五维加权版本**（文件头部注释："从 3 维升级到 5 维 (P2)"），与 `design_always_in.md` 的算法规范**高度一致**：

| 函数 | 代码行 | 设计文档 § | 一致性 |
|------|:------:|:---------:|:-----:|
| `determine_always_in()` | L52-138 | §2/§4 | ✅ 参数合并、边界处理、加权组合均一致 |
| `_dim_ema_slope()` | L144-187 | §4.2 | ✅ slope_pct 计算、归一化、±0.3% 阈值均一致 |
| `_dim_hh_hl_structure()` | L193-249 | §4.3 | ✅ swing检测、递进判定、2/3比例均一致 |
| `_dim_channel_position()` | L264-305 | §4.4 | ✅ 80%阈值、ratio→score映射一致 |
| `_dim_retracement_depth()` | L311-382 | §4.5 | ✅ 浅/深回调阈值 0.33/0.66、ATR归一化一致 |
| `_dim_gap_bars()` | L388-427 | §4.6 | ✅ 15bar饱和、diff≥0.1缺口判定一致 |
| `_combine_dimensions()` | L100-116 | §4.7 | ✅ 加权组合、±0.30阈值、min(abs,1.0)置信度一致 |
| `get_trend_filter()` | L433-464 | §8.1 | ✅ strict/moderate模式、long_only/short_only/neutral一致 |

**发现的微小偏差：**

| 偏差项 | 设计文档 | 代码实现 | 严重度 |
|--------|---------|---------|:---:|
| 回调深度寻找 swing high | 取最近 1 个 swing high | `tail(3).values`（取最多 3 个） | 低 |
| 通道位置方向名 | "neutral"/"oscillating" 混用 | 代码用 "neutral" | 低 |
| 缺口棒方向判定 | "多数收盘在 EMA 上方" | `sum > valid/2`（严格多数） | 低 |
| 结构判定 | 独立函数 `_classify_structure()` | 内联在 `determine_always_in` L119-124 | 低 |
| design_module_protocol.md | 五维 | 仍描述为"三维详情" L71-74 | **中** |

### 3.2 是设计变更还是编码偏差？

**判断：P2 阶段的有意升级，属于设计变更，但变更流程不完整。**

证据：
1. 文件头部注释明确记录："从 3 维升级到 5 维 (P2)"
2. 注释中写了变更理由："权重从 0.35/0.40/0.25 → 0.30/0.25/0.20/0.15/0.10 (与 concept_map.md 一致)"
3. 代码质量较高，不是仓促复制粘贴

**缺失项：** 没有变更日志（CHANGELOG）、没有 updating requirements.md、design_always_in.md §1.2 对 project_charter 的描述仍是错的。

---

## 四、迁移方案

### 4.1 3维→5维迁移评估

当前代码**已经是5维版本**，不需要代码迁移。需要的是**文档对齐**。

### 4.2 文档对齐优先级

| 序号 | 任务 | 文件 | 优先级 | 风险 |
|:---:|------|------|:---:|------|
| 1 | 修正 §1.2 对 project_charter 的错误描述 | design_always_in.md | **P0** | 低 |
| 2 | 在 §1.2 或新增 §1.4 中记录维度变更的完整理由 | design_always_in.md | **P0** | 低 |
| 3 | 更新 L342-348 维度表对齐统一方案 | requirements.md | **P1** | 中（需保持与M6验收标准一致） |
| 4 | 更新 L161 维度定义 | project_charter.md | **P1** | 中 |
| 5 | 更新 L71-74 "三维详情"注释→五维 | design_module_protocol.md | **P1** | 低 |
| 6 | 更新 "5维加权评分(0.30/0.25/0.20/0.15/0.10)" 添加维度名 | concept_map.md | **P2** | 低 |
| 7 | M6 回测中 AB 测试两种维度方案 | M6 回测脚本 | **P2** | 高（需额外测试数据） |

### 4.3 不推荐的迁移方案

**不推荐将代码回退到 requirements.md 原始方案**（K线实体倾向+均线位置+±0.60阈值），理由：
- 破坏现有实现，改造成本高
- K线实体倾向和均线位置均为二元判定，在 A 股震荡市中几乎恒为中性
- ±0.60 阈值过高，超过 80% 的交易日会输出 NONE，失去 Always-In 的实用价值

---

## 五、参数来源追踪

### 5.1 五个权重 (0.30/0.25/0.20/0.15/0.10)

**Brooks 原著量化依据：无。**

Brooks 的原著《Trading Price Action Trends》中提出了这些概念（20缺口棒、高低点结构、回调深度等），但**从未给出任何量化权重**。Brooks 的方法是主观综合判断，靠交易员经验做定性加权。

权重 0.30/0.25/0.20/0.15/0.10 的来源追踪：
1. `project_charter.md` 变更日志 L458 记录了从"等权"改为"加权"，理由是"20缺口棒信噪比最高，等权会稀释高信噪比信号"
2. 具体的 0.30/0.25/0.20/0.15/0.10 数值**完全是初始估计值**，无实证依据
3. design_always_in.md 在权重分配时做了主观重排：将 EMA20 斜率推到 0.30（理由：ema_slope 对方向变化最敏感）、将缺口棒降到 0.10（理由：日线级别的 20 根缺口棒需要 1 个月数据，响应过慢）

**评价：权重分配方案合理但缺乏 M6 回测验证。** 五个权重应标记为 `[占位值]` 并在 M6 网格搜索校准。

### 5.2 阈值 ±0.30（vs requirements.md 的 ±0.60）

**A 股适配角度：±0.30 比 ±0.60 更合理。**

量化分析：
- 五维得分都在 [-1, 1] 区间，加权总分理论范围 [-1, 1]
- 实际运行中，各维度很难全部达到极端值（5 个 +1 或 5 个 -1 在自然市场几乎不发生）
- 假设每维得分均匀分布 [-0.5, 0.5]，则加权总分的标准差约为：`√(0.30² + 0.25² + 0.20² + 0.15² + 0.10²) × 0.5/√3 ≈ 0.47 × 0.29 ≈ 0.14`
- ±0.30 约 2.1σ，意味着约 3.5% 的样本判定为 bullish、3.5% 为 bearish、93% 为 oscillating——符合 A 股"大部分时间震荡"的特征
- ±0.60 约 4.3σ，意味着仅约 0.002% 触发方向判定——**几乎永远输出 NONE，失去了实用价值**

**结论：±0.30 是经过考量的合理选择。** 但需要 M6 回测验证实际方向判定比例，目标：bullish+bearish 占比 10%-20%（每周至少 1 个方向信号）。

### 5.3 置信度公式 `min(abs(score), 1.0)`

**依据：简单直接的线性映射，无 Brooks 或统计理论支撑。**

这个公式的隐含假设：加权总分的绝对值直接等于置信度。这是一个合理的约定——当五维一致时 scores 绝对值大→置信度高，维度冲突时 scores 相消→绝对值小→置信度低。但存在理论缺陷：
- 当五维中四维为 0、仅一维达到 +0.8 时：加权分 = 0.30×0.8 = 0.24 → confidence = 0.24（尽管有一维强信号）
- 更合理的方案：`confidence = 1 - variance(scores)` 或考虑各维度的"一致程度"而非仅加权总和

**建议：M6 网格搜索中测试 `confidence = min(abs(score) + agreement_bonus, 1.0)` 变体。**

---

## 六、A 股适配检查

### 6.1 新股/次新股处理

| 检查项 | 当前实现 | 是否符合 A 股适配 | 评分 |
|--------|---------|:---:|:---:|
| < 30 根 K 线降级 | ✅ L75-82: direction="oscillating", confidence=0 | 是 | ✅ |
| 新股排除策略 | ❌ `market_state.py` 只在数据不足时默认为 oscillating，但未在 pipeline 层按 ASH-18 主动排除 | 否（属于 pipeline 层责任） | ⚠️ |
| EMA20 不足时的处理 | ✅ `_dim_ema_slope` L155-156: lookback 不足时返回 score=0 | 是 | ✅ |

`ashare_adaptation.md` ASH-18 规定："list_date + 60天 < date → 可纳入"，这应在 `pipeline.py` 的选股层实现，非 market_state.py 的职责。当前 market_state.py 的降级策略正确——数据不足时安全返回 oscillating 而不抛异常。

### 6.2 连续涨跌停

| 检查项 | 当前实现 | 是否符合 A 股适配 | 评分 |
|--------|---------|:---:|:---:|
| 涨停封死→Always-In 不可执行 | ❌ `market_state.py` 未实现 ASH-07 的涨停降权 | 否 | ❌ |
| 连续涨停 Always-In 降权 | ❌ 未实现 ASH-09 的 `score × 1/(N+1)` 公式 | 否 | ❌ |
| 极端波动不崩溃 | ✅ 边界条件中有 "连续涨停封板→加权组合自然降低置信度" 但这是被动依赖，非主动处理 | 部分 | ⚠️ |

**问题：** `design_always_in.md` 边界条件 §7（L777-778）声称"连续涨停封板→加权组合自然降低置信度"，但这一假设不可靠。当连续涨停时：
- Dim1（EMA斜率）：涨停不断推高 EMA，斜率极正→强牛信号
- Dim3（通道位置）：收盘永远在 EMA 上方→100% 触发强牛
- Dim5（缺口棒）：收盘远高于 EMA→缺口棒比例极高→强牛
这三项会给出极高分数，而 Dim2（swing 点检测在连续同价时不产生 swing point→score=0）和 Dim4（回调深度在无回调时 score=0）的中性不会有效抵消。**加权分可能异常高，给出虚假的 bullish 高置信度。**

**必须在 `market_state.py` 或 `ashare_adaptation.py` 中显式实现 ASH-09 降权逻辑。**

### 6.3 趋势强度五级 (AAA/AA/A/B/C) 的可量化性

`requirements.md` L413-418 定义了趋势强度五级：

| 等级 | 条件 | 可量化？ | 当前实现 |
|:---:|------|:---:|------|
| AAA | 回调<33%前波, 价格在EMA单侧运行 | ✅ 可使用 Dim4 回撤深度 + Dim3 通道位置 | market_state.py 不直接输出趋势强度等级 |
| AA | 回调33%-50%, 价格偶尔穿越EMA | ✅ | 同上 |
| A | 回调>50%, 价格频繁穿越EMA | ✅ | 同上 |
| B | 无明显方向, 边界清晰 | ✅ | oscillating + 区间宽度测量 |
| C | 均线压制, 反弹无力 | ✅ | bearish direction |

**可量化性判断：可。** 五级分类的量化映射为：
```python
def strength_from_always_in(ai_result):
    conf = ai_result["confidence"]
    d3 = ai_result["dimensions"]["channel_position"]["score"]
    d4 = ai_result["dimensions"]["retracement_depth"].get("retracement_atr", 0)
    if ai_result["direction"] == "oscillating": return "B"
    if ai_result["direction"] == "bearish" and conf > 0.5: return "C"
    if d4 < 0.33: return "AAA"
    if d4 < 0.50 or d3 > 0.6: return "AA"
    return "A"
```
但此逻辑应在 `state/trend_strength.py` 中独立实现，不应耦合到 `market_state.py`。

---

## 七、总体评价

`design_always_in.md` 是目前 PAT 项目中**最详尽、最完整的设计文档之一**（827行，含9个章节、精确算法伪代码、边界条件、测试方案和 workbuddy 实施提示词）。其五维加权判定框架合理、算法描述严密、代码实现质量较高。各维度的量化实现（EMA斜率差分法、swing递进判定、通道位置比例映射、ATR归一化回调深度、缺口棒饱和计数）均是可复现的确定性算法，不存在"魔法数字"级别的黑盒。

然而，本审查发现的核心问题——**三重文档不一致**——暴露了项目文档管治的漏洞。`design_always_in.md` 在 §1.2 中对 `project_charter.md` 的描述存在事实性错误（声称 project_charter 包含 EMA20 斜率和通道位置，实际并非如此），且在未经变更流程的情况下改动了五个维度中的三个。虽然这些改动在算法层面确有道理（EMA斜率比K线实体更稳健、通道位置比均线位置更细腻），但"正确的结果"不能为"错误的流程"开脱。

**以 requirements.md 为权威基准、design_always_in.md 为算法实现、M6 回测为最终裁判**——这是本次审查推荐的"三权分立"解决方案。具体而言：保持 requirements.md 的维度清单作为"需要什么"的权威声明，认可 design_always_in.md 的量化实现作为"如何做"的工程方案，在 M6 全周期回测中用数据验证权重和阈值的合理性。

A 股适配方面存在一个关键遗漏：连续涨跌停场景下的 Always-In 降权逻辑（ASH-09）虽然已在 `ashare_adaptation.md` 中定义，但**未在 `market_state.py` 中实现**。这可能导致涨停板股票被错误地输出高置信度 bullish 信号，影响下游策略决策。建议在 M2.1 闭环前补齐此项。

**最终评级：CONDITIONAL — 满足 5 项修正条件后可升级为 PASS。**

---

*审查完成时间：2026-06-14*
*报告字数：约 3,500 字*
