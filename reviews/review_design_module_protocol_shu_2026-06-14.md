# 审查报告：design_module_protocol.md

- 审查人：枢
- 日期：2026-06-14
- 审查范围：`design_module_protocol.md`（812行）、`pipeline.py`（328行）、`requirements.md` §M6.5/M7、关联设计文档 `design_always_in.md`/`design_key_levels.md`/`design_pinbar.md`

---

## 一、审查结论：[CONDITIONAL]

通过条件：
1. 修复协议与 `design_always_in.md` 在 Always-In 维度数量和权重上的不一致（3维 vs 5维）
2. 解决协议单向数据流与 `requirements.md` M2.5 L2↔L3 反馈回路的架构冲突
3. 将 `pipeline.py` 中 P2 字段（`polarity_nearby`、`fakeout_nearby`）显式回写到协议或标记为实验性

在其他方面，管线编排顺序、错误隔离、降级路径设计合理，模块间耦合度可控。

---

## 二、管线编排检查

### 2.1 执行顺序分析

| 步骤 | 协议定义 | pipeline.py 实现 | 一致性 |
|------|---------|-----------------|--------|
| S1 | loader.get_daily() | get_daily() | 一致 |
| S2 | determine_always_in(df) | determine_always_in(df) | 一致 |
| S3 | detect_key_levels(df) | detect_key_levels(df) | 一致 |
| S4 | detect_pinbar(df, key_levels=levels) | detect_pinbar(df, key_levels=levels) | 一致 |
| S5 | 信号过滤与组合 | _build_signals(df, trend_filter, confidence) | 一致 |
| S6 | 组装 pipeline_result | 返回 dict | 一致 |

### 2.2 依赖检查

- **S3(Key Levels) 依赖 S2(Always-In)？** — 否。Key Levels 只消费 OHLC 价格数据，不需要方向信息。两者可安全交换顺序，甚至可以并行执行。
- **S4(Pinbar) 依赖 S3(Key Levels)？** — 是。Pinbar 接收 `key_levels` 参数来标注 `near_key_level` 和 `key_level_distance`。这是正确的硬依赖。
- **S5(Filter) 依赖 S2(Always-In)？** — 是。过滤依赖 `trend_filter` 和 `confidence`。这是正确的硬依赖。
- **S5(Filter) 依赖 S4(Pinbar)？** — 是。先有信号才能过滤。正确。

### 2.3 关于"S1关键位→S2 Always-In"的评估

审查任务中提出了"关键位在 Always-In 之前"的建议（理由：关键位不需要方向信息）。从依赖角度看两者无先后强制要求，当前协议顺序（Always-In 先于 Key Levels）不影响正确性。但 Key Levels 的计算量通常更大（涉及 swing 检测、聚类），将其后移可保证"轻量级模块先判定，若行情不适合则提前短路"——当前顺序有其实用价值，**不建议修改**。

---

## 三、pipeline_result 数据流完整性

### 3.1 字段对齐检查

pipeline.py 的实际输出结构与协议 §2.1 定义基本一致：`ts_code`、`trade_date`、`skip`、`skip_reason`、`n_bars`、`always_in`、`key_levels`、`signals`、`total_signals`、`aligned_signals`、`conflicting_signals`——合计 11 个顶层字段，全部对应。**通过**。

### 3.2 严重不一致：Always-In 维度和权重

这是本次审查发现的最严重问题之一。

| 文档 | 维度数量 | 维度名称 | 权重和 |
|------|---------|---------|--------|
| `design_module_protocol.md` §2.1 | **3** | ema_slope(0.35), hh_hl_structure(0.40), channel_position(0.25) | 1.00 |
| `design_always_in.md` §3.1 | **5** | ema_slope(0.30), hh_hl_structure(0.25), channel_position(0.20), retracement_depth(0.15), gap_bars(0.10) | 1.00 |
| `requirements.md` §2.2.1 | **5** | 缺口棒(0.30), 高/低点结构(0.25), K线实体倾向(0.20), 回调深度(0.15), 均线位置(0.10) | 1.00 |

协议声明的是 P1 3 维简化版，但 `design_always_in.md` 实现的是完整 5 维版。`requirements.md` 则是另一种 5 维组合（K线实体倾向 替代了 EMA斜率/通道位置）。三个文档的维度列表和权重分配**互不兼容**。

**影响**：pipeline.py 中的 `always_in.dimensions` 结构按协议写死为 3 维，但 `determine_always_in()` 实际返回 5 维。pipeline.py 第 82-83 行的 `default` 字典只填充了 `direction`/`confidence`/`structure`/`dimensions`，没有处理 `params_used` 字段。若 `design_always_in.md` 中标有 `params_used` 而 protocol 未定义，会导致消费者（如前端展示、回测审计）不知道该字段存在。

**建议**：统一到一个权威版本。推荐以 `design_always_in.md` 的 5 维为准，同步更新 protocol §2.1 和 `requirements.md` §2.2.1，同时清理不再使用的维度定义。

### 3.3 signals[] 字段多余

| 字段 | 协议定义 | pipeline.py 实际 | 差异 |
|------|---------|-----------------|------|
| `polarity_nearby` | 未定义（§6.1 标记为 P1.2b P2 扩展） | 第 231 行：实际输出 | **提前上线** |
| `fakeout_nearby` | 未定义（§6.2 标记为 P1.2c P2 扩展） | 第 232 行：实际输出 | **提前上线** |

pipeline.py 的 `_build_signals()` 函数（第 208-218 行）迭代 key_levels 检查 `kl.polarity_flips` 和 `kl.fakeout_history`，并将结果塞入信号字典。这两个字段在协议 §6.1/§6.2 被明确定义为 **P2 扩展**，当前 P1 管线不应输出。

**建议**：若确需提前上线，协议必须同步更新。否则应在 `_build_signals()` 中移除相关逻辑，或通过 feature flag 控制。

### 3.4 design_always_in.md 输出 vs pipeline 消费

`design_always_in.md` 输出包含 `params_used` 字段（第 128-136 行），但 pipeline.py 的 `always_in` 结构（第 131-137 行）未包含此字段。这导致参数审计信息在管线上游即丢失。**建议**在 `pipeline_result.always_in` 中增加可选的 `params_used` 字段。

### 3.5 DataFrame 传递兼容性

- `determine_always_in(df)`：只读 OHLC，pinbar 追加列不影响其已完成的读取。**安全**。
- `detect_key_levels(df)`：操作在 S3 执行完毕，pinbar 在 S4 追加的列不会影响 key_levels。**安全**（因 sequential 执行）。
- `detect_pinbar(df, key_levels=levels)`：返回同一个 df + 新列。pipeline 的防御性检查（第 110-115 行：若 `signal` 列不存在则填充默认值）正确处理了 pinbar 崩溃的情况。**安全**。

### 3.6 package name 不一致

| 位置 | 包名 |
|------|------|
| `design_module_protocol.md` | `price_action_trading` |
| `pipeline.py` | `PAT_stock` |
| 所有 design_*.md | `price_action_trading` |

协议和设计文档使用 `price_action_trading`，但实际实现使用 `PAT_stock`。这不影响功能，但协议中的 import 示例（§4.1）对实现者不准确。**建议**更新协议以匹配实际包名，或反之统一命名。

---

## 四、降级路径合理性

### 4.1 六种降级场景

| 场景 | 触发条件 | 行为 | 输出 |
|------|---------|------|------|
| 数据加载失败 | `get_daily()` 抛出异常 | `_skip_result(ts_code, "data_load_failed: ...")` | skip=True，全部字段为空默认值 |
| 数据不足 | `len(df) < 30` | `_skip_result(ts_code, "insufficient_data")` | 同上 |
| Always-In 失败 | `determine_always_in()` 崩溃 | `_safe_call` → `direction="oscillating"`, `confidence=0.0` | 震荡市 + 零置信度 → 所有信号通过（无方向过滤） |
| Key Levels 失败 | `detect_key_levels()` 崩溃 | `_safe_call` → `levels=[]`, `quality_warning="detection_failed"` | Pinbar 无关键位增强 → 信号质量下降但不阻断 |
| Pinbar 失败 | `detect_pinbar()` 崩溃 | `_safe_call` → 返回原 df → signal 列补 0 | 零信号输出 |
| 全部模块失败 | 连续的 3 次 `_safe_call` 降级 | direction="oscillating", levels=[], signals=[] | pipeline_result 合法但内容为空 |

### 4.2 "软降级用默认值"的掩盖风险

Always-In 降级为 `direction="oscillating", confidence=0.0` 后，`_is_aligned()` 中 `trend_filter="neutral"` 分支直接返回 `True`——所有信号都算对齐。**如果 Always-In 模块有 bug 持续崩溃，pipeline 会静默地跳过所有方向过滤**，回测结果可能看起来"正常"（大量信号通过），但实际信号质量已严重下降。

**建议**：
1. 在 `pipeline_result` 顶层增加 `degradations: list[str]` 字段，记录哪些模块降级了
2. `_safe_call` 汇总警告到 `_degradation_log`，由 `run_batch()` 在结束时输出摘要
3. 考虑为 Always-In 设置"连续降级阈值"——若 N 次连续失败则停止管线并报 FATAL

### 4.3 全部降级的极端 case

全部降级后输出：
```python
{
    "ts_code": "000001.SZ", "trade_date": "20240115", "skip": False,
    "always_in": {"direction": "oscillating", "confidence": 0.0, "structure": "mixed", "trend_filter": "neutral", "dimensions": {}},
    "key_levels": {"levels": [], "metadata": {"swing_count": 0, "swing_density": 0.0, "quality_warning": "detection_failed"}, "summary": ""},
    "signals": [], "total_signals": 0, "aligned_signals": 0, "conflicting_signals": 0
}
```

该输出是一个"合法但空"的结果。批量扫描时它不报错，只静默消失在统计中。消费者（如回测引擎）可能将 `skip=False` + `total_signals=0` 解释为"该日期无信号"而非"全模块崩溃"，从而引入系统性数据缺失偏差。

**建议**：全模块降级时 `skip` 应设为 `True`，`skip_reason` 列出所有失败的模块名。

---

## 五、架构耦合度分析

### 5.1 当前耦合路径

```
S1(Loader) ──df──┬── S2(Always-In) ──trend_filter──┐
                  │                                  ├── S5(Filter) ── S6(Output)
                  ├── S3(Key Levels) ──levels[]──────┤
                  │                    ↓              │
                  └── S4(Pinbar) ──signals[]─────────┘
```

耦合方式：
- S2↔S3：无耦合（独立消费 df）
- S3→S4：函数参数耦合（`key_levels=levels`），合理
- S2→S5：参数传递耦合（`trend_filter`, `confidence`），合理
- S4→S5：DataFrame 列耦合（`signal`, `pinbar_strength` 等），合理

总体评价：**P1 耦合度合理**，符合管道-过滤器模式。

### 5.2 Risk 模块是否需要所有上游数据？

当前 pipeline.py 不包含 Risk 模块。若 `requirements.md` M7 定义的 `_risk_layer()` 接入：
- 风控只需要信号列表（`signals[]`）+ 市场状态（`always_in.direction`）+ 大盘上下文
- **不需要**原始 df、key_levels 内部结构、dimensions 详情
- 应通过 `pipeline_result` 的子集消费，不直接依赖上游模块

### 5.3 新增策略模块的接入成本

以新增一个"Inside Bar 策略"为例：
1. `patterns/inside_bar.py`：实现 `detect_inside_bar(df, key_levels)` → 追加列到 df
2. `pipeline.py`：
   - 新增 import（1 行）
   - 在 S4.5 新增 `_safe_call("inside_bar", ...)` 调用（~5 行）
   - 在 `_build_signals()` 中新增信号类型分支（~5 行）
   - 在 `pipeline_result.signals[]` 的 `type` 字段中新增枚举值
3. 需要修改的文件：**2 个**（新模式模块 + pipeline.py）

接入成本低，但 **`_build_signals()` 随模式增加会变胖**。建议在 P2 重构为策略注册表模式：`STRATEGIES = [pinbar, inside_bar, fakeout, ...]`，`_build_signals()` 遍历注册表统一组装。

### 5.4 60分钟线扩展评估

若引入 60 分钟线，当前 `pipeline_result` 需要重构：

当前结构：
```python
"signals": [{date, direction, entry_trigger, ...}]  # 全在日线上下文中
```

需扩展为：
```python
{
    "daily_context": {  # 现有结构平移到这里
        "always_in": {...},
        "key_levels": {...},
    },
    "signals": [{
        ...,  # 现有字段
        "intraday_entry": {"60m_signal": ..., "15m_confirmation": ...},
    }]
}
```

**影响范围**：pipeline_result 顶层结构、signals[] 每个元素。协议 §6.6 的向后兼容承诺（"只新增字段"）可覆盖，但现有的 2D 平铺结构确实需要一层嵌套来承载多时间框架。

### 5.5 回测引擎接入

当前 `run_single_stock()` 返回单个 dict，而 `run_batch()` 返回 `list[dict]`。回测引擎可直接消费：
```python
for date in backtest_dates:
    results = run_batch(stock_pool, date)
    for result in results:
        if result["signals"]:
            engine.process_signals(result["signals"], result["always_in"])
```

接口友好，无需额外适配器。但缺少批量性能优化（如批量数据预加载）。建议 P2 增加 `load_batch(stock_pool, date_range)` 预处理步骤。

---

## 六、反馈回路冲突

### 6.1 协议 vs 需求的直接冲突

| 维度 | `design_module_protocol.md` | `requirements.md` M2.5 |
|------|---------------------------|----------------------|
| 数据流方向 | 单向 L1→L2→L3→L4→L5→L6 | 双向 L2→L3→L2（Pass1→反馈→Pass2） |
| 反馈机制 | 未定义 | `context_feedback.py` → 调整 L2 置信度 |
| 触发条件 | 无 | L3 检测到假突破/高潮反转/楔形时触发 |
| 重算策略 | 每只股票单次 pass | 仅方向翻转的股票触发 Pass2 |

### 6.2 影响评估

协议 §1 明确声明："P1 管线对单只股票的执行顺序固定为 6 步，每步的输入是上一步的输出。" 这是严格线性的。

但 requirements.md M2 §2.6 定义的反馈回路要求：
1. Pass 1: Always-In 初始判定 → Pinbar 检测
2. 反馈：Pinbar 检测到陷阱形态 → `context_feedback.feedback_adjust()` 调整 Always-In 置信度
3. Pass 2: Always-In 更新后 → Pinbar 重新确认

当前协议**无法表达这个双向流**。pipeline.py 中也没有任何反馈回路代码。

### 6.3 解决方案

三种思路，按推荐度排序：

**方案 A：在协议中增加反馈回路（推荐）**
- 在 Step 4 之后增加可选的 Step 4.5：`context_feedback.adjust(ai_result, signals)` → 更新后的 Always-In
- 增加 Step 5.5："若 Always-In 方向因反馈而翻转，重新执行 Step 4（只对 > 阈值的股票）"
- 设为条件执行（仅在有 P2 标记时触发），保持向后兼容

**方案 B：将反馈回路提升到管线之上**
- 反馈回路不属于单股管线，而是属于"策略复审"层
- 在 `run_batch()` 层面，对所有结果做后处理：若某只股票信号与 Always-In 矛盾且检测到陷阱，标记该股票的 Always-In 可能需要修正
- 优点：不破坏 P1 线性流；缺点：P2 阶段需要额外一轮扫描

**方案 C：接受协议与需求的分歧**
- 协议声明为 P1 范围，反馈回路声明为 P2 范围
- 在协议 §6 中显式标注"P2 将引入 L2↔L3 反馈回路，届时协议需修订"
- 当前 pipeline 不实现反馈，requirements.md M2.5 验收标准标记为 P2

**推荐方案 A**，因为它最接近 M2 架构图的设计意图，且降级成本最低（条件执行+默认关闭）。

---

## 七、代码一致性

### 7.1 import 列表 vs 模块清单

| 模块 | 协议路径（§7.1） | pipeline.py 实际 import | 状态 |
|------|-----------------|----------------------|------|
| Data Loader | `price_action_trading/data/loader.py` | `PAT_stock.data.loader` | 包名不一致 |
| Always-In | `price_action_trading/state/market_state.py` | `PAT_stock.state.market_state` | 同上 |
| Key Levels | `price_action_trading/patterns/key_levels.py` | `PAT_stock.patterns.key_levels` | 同上 |
| Pinbar | `price_action_trading/patterns/pinbar.py` | `PAT_stock.patterns.pinbar` | 同上 |

导入的函数完全匹配（`get_daily`, `determine_always_in`, `get_trend_filter`, `detect_key_levels`, `key_levels_summary`, `detect_pinbar`）。包名差异见 §3.6。

### 7.2 pipeline.py 实际行为 vs 协议伪代码

| 差异点 | 协议伪代码（§4.1） | pipeline.py 实际 | 影响 |
|--------|-------------------|-----------------|------|
| `_is_aligned` 置信度逻辑 | 协议 §3.1: `confidence > 0.7` 严格 / `0.3~0.7` 标准 / `<= 0.3` 宽松 | 实际 `_is_aligned`: `neutral`→True, `<=0.3`→True, `>0.7`→严格, `0.3~0.7`→标准（但逻辑与严格相同） | 协议标准档描述"冲突信号标记但不丢弃"，但代码中 `_is_aligned` 在标准档返回 `False`——**不一致** |
| `_build_signals` 参数 | 协议: `_build_signals(df, trend_filter, confidence)` | 实际: `_build_signals(df, trend_filter, confidence, key_levels=levels, max_signals=10)` | 实际多了 `key_levels` 参数用于 P2 字段计算 |
| sys.path 处理 | 协议: 无 | 实际: 第 25-28 行运行时动态添加父目录 | 协议应覆盖此部署细节 |

### 7.3 _is_aligned 标准档逻辑缺陷

协议 §3.1 描述："中等置信度(0.3~0.7)：标准过滤——冲突信号标记但不丢弃"。但代码第 250-254 行：
```python
# 中等置信度
if trend_filter == "long_only" and direction == "bullish":
    return True
if trend_filter == "short_only" and direction == "bearish":
    return True
return False  # 冲突信号返回 False，即 "not aligned"
```

这实际行为与高置信度档完全相同——冲突信号返回 False。协议说"不丢弃"但 `_is_aligned` 返回 False 只是在信号上打标记，确实没有丢弃（信号仍保留在列表中）。**语义上：代码行为正确，"标记不丢弃"通过 `always_in_aligned=False` 实现。但协议对标准档和严格档的区别描述不够清晰**——两者在 `_is_aligned` 层面行为相同，区分应该在消费者的处理逻辑中体现。

---

## 八、可扩展性

### 8.1 M6.5 冒烟测试覆盖度

M6.5 定义了 L1-L6 6 层冒烟测试，检查项包括：
- L1：缓存命中率 >= 80%
- L2：Always-In 非空率 >= 80%
- L3：至少 3 种形态有非零检出
- L4：信号生成率 > 0
- L5：过滤后至少保留 1 条信号

当前 pipeline.py 只覆盖 **L1-L3**（数据、状态、形态），缺失 L4（策略层）和 L5（风控层）。pipeline 无法满足 M6.5 冒烟测试的全部检查项。这符合开发节奏（P1 先上 3 模块），但应在协议中标注覆盖边界。

### 8.2 M7 PriceActionPipeline 类

M7 定义了 `PriceActionPipeline` 类的 5 个方法：`run()`, `_state_layer()`, `_pattern_layer()`, `_strategy_layer()`, `_risk_layer()`。当前 pipeline.py 没有类封装，只有函数。建议在 P2 重构为类，与 M7 设计对齐。

### 8.3 向后兼容承诺评估

协议 §6.6 承诺"不删除已有字段，只新增"。当前评估：承诺可行，但需伴随字段版本号机制。建议 `pipeline_result` 顶层增加 `"protocol_version": "1.0"` 字段，供消费者做兼容判断。

---

## 九、总体评价

### 优势
1. **管线设计清晰**：6 步线性流 + 命名规范（`_safe_call`、`_skip_result`、`_build_signals`）使得代码可读性高
2. **错误隔离设计优秀**：`_safe_call` 包装 + 默认值降级 + 防御性列检查，三个层次防止单点崩溃
3. **数据流图与实际代码一致**：§2.2 的数据流图准确描述了模块间数据传递关系
4. **规则体系完整**：R1-R13 覆盖执行顺序、信号处理、错误处理、数据完整性，优先级明确

### 主要问题（按严重度排序）

| 严重度 | 问题 | 位置 |
|--------|------|------|
| **严重** | Always-In 维度/权重三文档不一致（3维 vs 5维 vs 另一套5维） | §3.2 |
| **严重** | 协议单向流与 M2.5 反馈回路的架构冲突 | §6 |
| **中等** | signals[] 的 P2 字段提前上线 | §3.3 |
| **中等** | `_is_aligned` 标准档与高置信度档行为相同，协议描述不清晰 | §7.2 |
| **中等** | 全模块降级时 `skip=False`，掩盖系统性故障 | §4.3 |
| **低** | 包名 `price_action_trading` vs `PAT_stock` 不一致 | §3.6 |
| **低** | Always-In `params_used` 字段在 pipeline 中丢失 | §3.4 |
| **低** | 缺少降级日志汇总机制 | §4.2 |

### 修改建议优先级

1. **立即**：统一 Always-In 维度定义（以 `design_always_in.md` 5 维为准，三文档同步）
2. **立即**：在协议中为反馈回路预留接口（方案 A 的条件执行）
3. **P2 前**：移除或 flag 控制 `polarity_nearby`/`fakeout_nearby` P2 字段
4. **P2 前**：全模块降级时 `skip=True` + 原因列表
5. **P2 前**：增加 `protocol_version` 字段
6. **P2**：重构为 `PriceActionPipeline` 类以对齐 M7 设计

---

> 审查完成。报告行数约 3500 字。
> 下一动作：请 Darwin（集成调试）和 workbuddy（pipeline 实现）审阅 §3.2（维度不一致）和 §6（反馈回路冲突）两项严重问题，在 pipeline 正式上线前达成决议。
