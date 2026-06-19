# P1.2a 水平关键位检测 — 设计审查报告

> 审查人: Shu (PAT 设计审查人)
> 审查日期: 2026-06-14
> 审查对象: `design_key_levels.md` vs `key_levels.py` vs `test_key_levels.py`
> 关联模块: pinbar.py, pipeline.py, range.py, requirements.md §M3.1/M3.5

---

## 一、审查结论（TL;DR）

**整体评级: C-（设计与实现严重偏离，需回炉对齐）**

设计文档与代码实现之间存在 **7 处核心偏差**，其中函数签名不一致、聚类容差偏差 5 倍、聚类算法策略完全不同、Swing 检测未复用已有工具函数等问题直接影响模块可用性。22 个单元测试全部针对当前实现编写，但并未覆盖设计文档约定行为，导致"测试通过 ≠ 设计正确"的局面。

---

## 二、参数来源追踪

下表对 6 个关键参数逐一标注设计文档声称来源与实际实现的差异：

| 参数 | 设计文档值 | 代码实际值 | 来源评估 |
|------|-----------|-----------|---------|
| **Swing 检测窗口** | `swing_window=5` | `swing_window=5` | ✅ **一致**。设计标注"Brooks 默认 5"，requirement.md §M3.1 同样指定 `n=5`。日线 5 根 = 1 周，在 A 股适用。但设计文档注明"日线可增大到 8-10"，代码未暴露该调节能力 |
| **聚类容差** | `cluster_tolerance=0.015` (1.5%) | `cluster_pct=0.003` (0.3%) | ❌ **严重偏差 (5 倍)**。设计文档 1.5% 配合 `min_absolute_tolerance=0.10` 元做自适应；代码直接用 0.3% 且无保底绝对容差。0.3% 过于严苛，茅台 ~1500 元仅容忍 ±4.5 元，实际日波动 >2% 是常态，会导致大量本应合并的 swing 点被拆分为独立 cluster。此项非 Brooks 概念，属系统自创 |
| **最小绝对容差** | `MIN_ABSOLUTE_TOLERANCE=0.10` 元 | **缺失** | ❌ **设计有代码无**。低价股保护机制完全缺失。工行 ~5 元若仅用 0.3% 容差仅容忍 0.015 元，无法有效聚类 |
| **半衰期** | `recency_half_life=60` | 硬编码 `exp(-0.01*d)` ≈ 半衰期 69 | ❌ **偏差 15%**。`-0.01 * 69.3 = ln(0.5)`，实际半衰期约 69 根而非设计声明的 60 根。且参数不可配置（硬编码 `-0.01`）。设计标注约 3 个月 A 股交易日，69 根约 3.5 个月，偏差不大但不可调是个问题 |
| **触摸缓冲** | `touch_buffer=0.5 ATR` | 直接使用 cluster 价格区间与 bar range 交集判触 | ❌ **设计有代码无**。设计文档 §4.3 详细描述了 ATR 缓冲带触碰判定逻辑及 fallback 策略；代码仅检查 `lows[i] <= price_max_val and highs[i] >= price_min_val`，等价于 0 缓冲。这导致大量穿价不算"触碰"，strength 普遍偏低 |
| **both_sides 加权** | ×1.5 倍 | 代码仅标记 `both_sides=True`，**未应用 1.5 倍加权** | ❌ **设计有代码无**。设计文档 §4.3 明确写"两侧测试过的关键位强度加一档 (权重 x1.5)"；代码仅通过 `formation_type == "mixed"` 标记，strength 计算时未乘 1.5 |
| **high_density 阈值** | `swing_density > 0.20` | 检测逻辑移至 `pipeline.py::_key_levels_quality_warning()` | ⚠️ **逻辑外移**。`key_levels.py` 自身不计算 swing_density、不返回 quality_warning。该逻辑搬迁到 pipeline wrapper 中，设计文档 §4.1 代码示例预期在 `detect_key_levels()` 内部完成。此阈值 0.20（每 5 根 1 个 swing）属经验值，无 Brooks 直接引用 |

### 参数来源综合结论

6 个参数中仅 `swing_window=5` 设计与代码一致；其余 5 个存在实质性差异。参数来源方面，仅 `swing_window`、`recency_half_life` 有 Brooks/A 股经验依据，其余（cluster_tolerance 自适应逻辑、both_sides 加权、high_density 阈值）均属自创规则，设计文档对其来源标注不够充分。

---

## 三、多源一致性（设计文档 vs requirements.md）

### 3.1 Swing Point 检测一致性

| 检查项 | design_key_levels.md | requirements.md §M3.1 | key_levels.py | 一致性 |
|--------|---------------------|----------------------|---------------|--------|
| Swing 检测窗口 | `left=5, right=5` | `n=5` | `swing_window=5` | ✅ |
| 使用 utils/indicators | `swing_high()`, `swing_low()` | `find_swing_highs()`, `find_swing_lows()` | **自实现 for 循环** | ❌ 代码未复用 |
| Swing 检测逻辑 | 复用 `center=True` 滚动窗口 | 未指定实现 | 严格局部最大值（`>=` vs `<`） | ❌ 算法不同 |

**关键发现**: 设计文档明确要求复用 `utils/indicators.py` 中 `swing_high()` / `swing_low()`，该函数使用 `rolling(window, center=True).max()` 向量化实现。但 `key_levels.py` 自己实现了一套 for 循环检测，且使用了不同的比较逻辑：
- utils/indicators: `high == rolling_max`（等值即判为 swing high，允许多个并列最高）
- key_levels.py: `highs[j] >= highs[i]` → 要求当前值**严格大于**所有邻居

两者对并列高点/低点的处理不同，会产生不同的 swing 点集。

### 3.2 区间形态（M3.5）接口一致性

requirements.md §M3.5 定义的 `identify_range_boundary(df) -> dict` 与 design_key_levels.md §8.4 描述的数据流一致：key_levels.py 输出 levels[] → range.py 从中选取当前区间边界。但 requirements.md §M3.5 的签名未列出 `key_levels` 参数（与设计文档 §8.3 的 `identify_range_boundary(df, key_levels=levels)` 不一致）。需统一对齐。

---

## 四、代码一致性（设计文档 vs key_levels.py）

### 4.1 函数签名偏差

| 项目 | 设计文档 | key_levels.py | 偏差等级 |
|------|---------|---------------|---------|
| 返回值类型 | `tuple[list[KeyLevel], dict]` | `List[KeyLevel]` | 🔴 严重 |
| cluster_tolerance 默认值 | `0.015` | `0.003` | 🔴 严重 |
| recency_half_life 参数 | 有，默认 60 | **无此参数** | 🔴 严重 |
| max_levels 参数 | 有，默认 10 | **无此参数** | 🟡 中等 |
| min_absolute_tolerance | 有，默认 0.10 | **无此参数** | 🔴 严重 |
| lookback 参数 | 无 | 有，默认 120 | 🟡 中等（多余参数） |
| min_touch vs min_touch_count | `min_touch=2`（设计） | `min_touch_count=2`（代码） | 🟢 仅命名差异 |

### 4.2 聚类算法策略差异

设计文档 §4.2 Step 1 明确写"合并所有 swing 点"（high 和 low 混在一起按价格排序后统一聚类）。代码实际将 Swing High 和 Swing Low **分别聚类**，然后再做反向合并（Step 3）。

两种策略产生不同结果：
- **设计策略**（混合统一聚类）: 价格相近的 high 和 low 点天然聚在一起，直接形成 `both_sides=True`
- **代码策略**（分别聚类+合并）: 先各自形成纯 high/low cluster，仅在区间重叠时才合并为 mixed。如果 high 点和 low 点价格接近但 cluster 区间不重叠（例如 high [100.0,100.1], low [100.2,100.3]），它们保持分离

### 4.3 触碰计数差异

| 项目 | 设计文档 | key_levels.py |
|------|---------|---------------|
| 缓冲带 | `touch_buffer * ATR`, 默认 0.5 倍 | 无缓冲，bar range 直接与 cluster range 取交集 |
| ATR 不可用 fallback | 回退到 cluster 半宽 | 无此 fallback |
| 性能优化提示 | 向量化 `(df["low"] <= ...) & (...)` | 逐行循环 |

代码去除了 ATR 依赖（设计文档 §6.1 标注 ATR 为弱依赖），这简化了实现但也降低了触碰检测的精度。

### 4.4 极性切换与假突破——预期 stub vs 实际实现

设计文档 §4.4/§4.5 明确标记 P1.2b 极性切换和 P1.2c 假突破为 **v0 stub（返回空列表）**，附带了未来实现的详细设计思路。但代码中 `_detect_polarity_flips()` 和 `_detect_fakeouts()` 已 **完整实现**：

- 极性切换: 基于 close 价格在 `[price_min, price_max]` 上下方判断支撑/阻力角色，检测连续触发的角色切换
- 假突破: 检测价格突破 0.1% 后 3 根 K 线内收回，记录方向和穿透深度

单元测试 `test_polarity_flips`, `test_fakeout_above/below/no_return` 验证了这些实现。**这是超前实现，偏离了 v0 stub 设计意图。** 好处是提前验证了算法可行性；风险在于算法未经充分设计审查，参数（如 0.1% 阈值, 3 根确认）的选择依据没有文档支撑。

---

## 五、14 字段完整性检查

| # | 字段 | 类型 | 设计定义 | 代码实现 | 状态 |
|---|------|------|---------|---------|------|
| 1 | `level_price` | float | 聚类均值 | `np.median(prices)` | ⚠️ 设计说均值，代码用中位数 |
| 2 | `price_min` | float | 聚类最低价 | `min(prices)` | ✅ |
| 3 | `price_max` | float | 聚类最高价 | `max(prices)` | ✅ |
| 4 | `strength` | int | 触碰次数 | `min(10, s_count + touch_cnt)` | ✅（但计算逻辑与设计不同） |
| 5 | `swing_count` | int | 聚类内 swing 点数 | `len(points)` | ✅ |
| 6 | `touch_count` | int | 全部触碰（含日常） | bar range 交集数 | ✅（但未使用 ATR 缓冲） |
| 7 | `recency_weighted_strength` | float | 时效加权 | `exp(-0.01*d)` 求和 | ⚠️ 参数不可配 |
| 8 | `both_sides` | bool | 两侧测试 | `formation_type == "mixed"` | ✅ |
| 9 | `first_date` | str | YYYYMMDD | ✅ | ✅ |
| 10 | `last_date` | str | YYYYMMDD | ✅ | ✅ |
| 11 | `cluster_prices` | list | swing 点价格列表 | ✅ | ✅ |
| 12 | `formation_type` | str | 形成方式 | 三个值均已实现 | ✅（但设计注释说"不是当前市场角色"） |
| 13 | `polarity_flips` | list | **v0 stub → []** | **完整实现** | ⚠️ 超前实现 |
| 14 | `fakeout_history` | list | **v0 stub → []** | **完整实现** | ⚠️ 超前实现 |

**14 字段全部实现，但 4 项存在语义/行为偏差：**
1. `level_price` 设计用均值，代码用中位数（中位数更抗离群但设计未同意）
2. `recency_weighted_strength` 硬编码衰减率，不可参数化
3. `polarity_flips` 和 `fakeout_history` 不是 stub 而是完整实现

---

## 六、下游接口对齐

### 6.1 pinbar.py 消费 key_levels

```python
# pinbar.py 消费方式
def detect_pinbar(df, key_levels: Optional[list] = None, ...):
    ...
    _attach_key_levels(result, key_levels, atr_vals)

def _attach_key_levels(df, key_levels, atr_vals):
    kl_prices = np.array([kl.level_price for kl in key_levels])
    kl_types = [kl.formation_type for kl in key_levels]
```

✅ **对齐**。pinbar 访问 `KeyLevel.level_price` 和 `KeyLevel.formation_type`，两个字段均在代码中正确实现。类型注解 `Optional[list]` 与 `List[KeyLevel]` 兼容。

### 6.2 levels_near_price() 接口

设计签名: `levels_near_price(levels: list[KeyLevel], price: float, threshold: float = 0.01) -> list[KeyLevel]`
代码签名: 完全一致 → ✅ **对齐**

### 6.3 pipeline.py 集成顺序

```
Step 3: _detect_key_levels_wrapper(df) → levels, meta  # key_levels
Step 4: detect_pinbar(df, key_levels=levels)            # pinbar
Step 5: _build_signals(df, trend_filter, ..., key_levels=levels)
```

✅ **顺序正确**。关键位 S3 → pinbar S4 → 信号 S5，符合设计文档 §8.2 的编排。但 `_detect_key_levels_wrapper` 作为 adapter 弥补了返回值类型不匹配的问题（设计预期 `tuple[list, dict]`，实际代码返回 `list`）。

### 6.4 range.py 接口前瞻

设计文档 §8.4 描述了 `identify_range_boundary(df, key_levels=levels)`。但 range.py 中尚未看到 key_levels 参数（requirements.md §M3.5 定义 `identify_range_boundary(df) -> dict` 无此参数）。未来集成时需要对齐。

---

## 七、边缘情况审查

| 边缘情况 | 设计文档预期 | 代码实际行为 | 评估 |
|---------|-------------|-------------|------|
| **空 DataFrame** | 返回 `([], metadata)` | 返回 `[]` | ⚠️ 返回类型不匹配（缺少 metadata） |
| **不足 30 行** | 返回空列表 | `< swing_window*2+1 = 11` 行返回 `[]` | ⚠️ 阈值不一致（设计 30 vs 代码 11）。11 行时仅 swing 窗口边缘各 5 行被跳过，实际可用于 swing 检测的只有 1 根 K 线 |
| **新股不足 60 根** | 推荐 120, 最小 30 | 11 行以上即执行（可能仅检测到 0-1 个 swing） | ⚠️ 设计建议最小 30 行但代码未强制。50 行数据可能仅产生 1-2 个有效 swing 点，聚类无意义 |
| **无 swing 点（平坦 K 线）** | 返回 `[]` | `not swing_highs and not swing_lows` → `[]` | ✅ |
| **长期横盘 high_density** | quality_warning="high_density"，不阻断执行 | pipeline wrapper 计算 quality_warning | ⚠️ 处理存在但位置外移 |
| **复权导致 cluster 漂移** | 未提及 | 未处理 | ❌ 盲区。若数据未复权（如分红除权后价格跳变），cluster 会出现虚假偏移。建议在调用前强制要求前复权数据 |
| **所有 swing 点价格相同** | 返回 1 个包含全部的 cluster | 取决于 cluster_pct 设置 | ✅（0.3% 容差下必然合并） |
| **cluster 仅 1 点且 min_swing_count≥2** | 被过滤 | 被过滤 | ✅ |
| **同时同价位的 high 和 low（十字星 swing）** | both_sides=True | 需要区间重叠才会判 mixed | ⚠️ 十字星场景：若 swing high 价格=swing low 价格，分别聚类后区间 [p,p] 会因重叠而合并为 mixed。但若 min_swing_count=2，单一十字星无法形成有效 cluster |

---

## 八、测试覆盖评估

当前 22 个测试用例覆盖：
- ✅ 导入、空数据、不足数据、无 swing 点、缺失列
- ✅ Swing High/Low 聚类、Mixed 合并
- ✅ 时效加权、极性转换、假突破（向上/向下/未收回）
- ✅ levels_near_price / nearest_level / key_levels_summary
- ✅ KeyLevel 14 字段完整性、trade_date 集成

**测试盲区:**
1. 未测试设计文档定义的 `tuple[list[KeyLevel], dict]` 返回格式
2. 未测试 `cluster_tolerance=0.015` 的默认值行为
3. 未测试 ATR 缓冲触碰计数（因代码未实现）
4. 未测试 high_density / low_density 警告逻辑
5. 未测试 both_sides 的 ×1.5 加权
6. 未包含真实数据回归测试（601398.SH, 600900.SH, 600519.SH）

---

## 九、总体评价

### 设计文档质量: B+
设计文档结构清晰，算法描述详尽，参数有合理范围说明。不足在于 6 个自创参数中有 4 个未标注充分的理论/实证依据；P1.2b/P1.2c stub 设计与实际超前实现脱节。

### 代码实现质量: C
核心问题: **设计与实现的偏离并非细节打磨不足，而是函数签名、核心参数、聚类策略三大结构性不一致**。代码中 swing 检测未复用已有工具函数，增加了维护成本和逻辑分歧风险。

### 测试质量: B
22 个用例覆盖面广，合成数据工厂设计合理。但测试对代码实现而非设计文档负责，无法发现"实现错了"的问题。

### 建议修复优先级

| 优先级 | 修复项 | 影响范围 |
|--------|--------|---------|
| 🔴 P0 | 对齐函数签名：`-> tuple[list[KeyLevel], dict]`，补充 metadata 返回 | 破坏 pipeline.py adapter |
| 🔴 P0 | 调整 `cluster_pct` 默认值：`0.003 → 0.015` 并补充 `min_absolute_tolerance` | 聚类结果大幅变化 |
| 🔴 P0 | 复用 `utils/indicators.swing_high()/swing_low()` 替代自实现 for 循环 | Swing 点集变化 |
| 🟡 P1 | 添加 `recency_half_life` 参数，替换硬编码 `-0.01` | 时效加权可调 |
| 🟡 P1 | 添加 `max_levels` 参数 | 控制返回数量 |
| 🟡 P1 | 决定 polarity_flips / fakeout_history: 保持完整实现并更新设计文档 vs 回退为 stub | P1.2b/P1.2c 范围 |
| 🟢 P2 | 补充 ATR 缓冲触碰计数逻辑 | touch_count 更准确 |
| 🟢 P2 | 补充 both_sides ×1.5 加权逻辑 | strength 更准确 |
| 🟢 P2 | 添加真实数据回归测试 | 验证生产可用性 |

---

*报告结束*
