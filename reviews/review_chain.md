# PAT 评审证据链

> 目的：每个阶段过渡的审查记录可追溯。
> 结构：按模块组织，每个模块列出经历过哪些审查、谁审的、结论是什么。

---

## 一、M1 数据层 — loader + cache + calendar + indicators

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 编码→测试 | workbuddy | 06-11 | PASS (P1 Pipeline 前置依赖，联调通过即视为验证) | pipeline.py 联调使用 |
| 测试→验收 | Darwin | 06-12 | PASS | audit_20260612.md — 3 只股票数据加载全部正常 |

---

## 二、P1.1 Pinbar — patterns/pinbar.py + test_pinbar.py

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 编码→测试 | workbuddy | 06-12 | A级 (10/10测试全过, 代码质量高) | audit_20260612.md L5 |
| 测试→验收 | Darwin | 06-11 | PASS (4项断言全通过, 交叉验证7项全通过) | audit_20260611.md §一+PASS |
| 验收→联调 | Darwin | 06-12 | PASS (P1三模块联调+验收运行) | audit_20260612.md L6 |

**断言检查（audit_20260611.md）:**

| # | 断言 | 结果 |
|---|------|:----:|
| 1 | 输出列数 = 输入列数 + 7 | PASS |
| 2 | 6个合成测试 signal 匹配预期 | PASS |
| 3 | 向量化（无逐行循环） | PASS |
| 4 | 导入不报错 | PASS |

**交叉验证 vs 设计文档（audit_20260611.md）:**

| 检查项 | 结果 |
|--------|:----:|
| 函数签名含 key_levels 参数 | PASS |
| body_position_threshold=0.4 标注经验值 | PASS |
| 边界条件: total_range==0 | PASS |
| 边界条件: NaN ATR | PASS |
| 边界条件: 空 DataFrame | PASS |
| 边界条件: 缺列 | PASS |

---

## 三、P1.2a 关键位 — patterns/key_levels.py + test_key_levels.py

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 编码→测试 | workbuddy | 06-11 | 冒烟通过 | audit_20260611.md §四 — 缺独立测试文件(已补充) |
| 测试→验收 | Darwin | 06-11 | PASS (4项断言, 交叉验证9项全通过) | audit_20260611.md §一+PASS |
| 验收→联调 | Darwin | 06-12 | PASS | audit_20260612.md L6 |

**断言检查（audit_20260611.md）:**

| # | 断言 | 结果 |
|---|------|:----:|
| 1 | 返回 tuple[list[KeyLevel], dict]，dict 含 quality_warning | PASS |
| 2 | 空 DataFrame → 返回空列表 | PASS |
| 3 | levels_near_price 返回正确 | PASS |
| 4 | 导入不报错 | PASS |

**交叉验证 vs 设计文档（audit_20260611.md）:**

| 检查项 | 结果 |
|--------|:----:|
| 容差自适应 max(1.5%, 0.10元) | PASS |
| swing 密度检查 + quality_warning | PASS |
| KeyLevel 数据结构完整(14字段) | PASS |
| 时效加权 half_life=60 | PASS |
| both_sides 加权 x1.5 | PASS |

**已知未实现项（audit_20260611.md §四）:**
- rejection_count（P1.2b/c 计划）
- quality_score（P2 计划）

---

## 四、P1.3 Always-In — state/market_state.py

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 编码→测试(3维版) | workbuddy | 06-11 | 冒烟通过 | audit_20260611.md §一 |
| 测试→验收(3维版) | Darwin | 06-11 | PASS (4项断言全通过, 交叉验证7项全通过) | audit_20260611.md §一+PASS |
| P2 升级(5维版) | Darwin | 06-12 | PASS (功能验证: 权重和1.0, 5维输出正确, bearish检测正常) | review_20260612.md |
| 测试补充(5维版) | 待补充 | — | 新增 test_weights_sum_to_one | |

---

## 五、P2 Spike+Channel — state/spike_channel.py

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 编码→测试 | Darwin | 06-12 | 12/12 测试通过 | test_spike_channel.py |

**状态: 待第三方评审。** 当前是 Darwin 自编自测，无 workbuddy/qclaw 介入。

---

## 六、P1 Pipeline 联调 — pipeline.py

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 编码→测试 | Darwin | 06-12 | 3只股票联调通过 | audit_20260612.md L6 |
| 运行验收 | Darwin | 06-12 | PASS (日均29.8信号, 22/22天) | review_20260612.md |
| 质量验收 | 枢 | 06-12 | PASS (20信号方向一致率100%) | review_20260612.md |
| 对接验收 | Darwin | 06-12 | PASS (303ms/stock, JSON格式) | review_20260612.md |

---

## 零、requirements.md — 全阶段需求文档

| 阶段 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| 需求→冻结 | 枢 | 06-14 | **CONDITIONAL → 文档本体修复完成** | review_requirements_shu_2026-06-14.md |
| 文档本体修复 | 枢 | 06-14 | F1-F10 全部修复，requirements.md 重新冻结 | 修复清单见 §九 |

**P0 阻塞项（必须在 M2 前解决）：**

**文档本体修复（F1-F10, 2026-06-14 已全部修复）：**
| # | 问题 | 修复 |
|---|------|------|
| F1 | 节号错乱：2.1→2.7→2.2 | 重编号为 2.1→2.2→...→2.7 顺序 |
| F2 | 路径笔误：`price_action_tracing` | 修正为 `PAT_stock` |
| F3 | 成交量使用矛盾 | 新增说明块：成交量仅用于陷阱/形态辅助确认，非方向判定 |
| F4 | range.py/trap.py 假突破边界模糊 | 明确分工：range.py 做形态检测，trap.py 做陷阱结论 |
| F5 | 模糊验收标准 | Always-In 增加测量方法；M3 增加召回率/精确率；M4 增加定量条件；M6 增加跑通定义 |
| F6 | 策略权重未定义 | 新增初始权重（0.30/0.25/0.20/0.25），标注 M6 回测校准 |
| F7 | I/O 耦合过粗 | M3/M4/M5 I/O 表引用拆分为具体模块 |
| F8 | 反馈调幅占位值警告不足 | 增强警告：标注为架构核心参数，当前不可直接使用 |
| F9 | 全市场扫描范围未定义 | 新增定义：全A股（含北交所），排除ST/新股 |
| F10 | 郭睿路径笔误 | `guorui_system` → `GR_stock` |

**P0 阻塞项（必须在 M2 前解决）：**
- P0-1: Always-In 5维权重(0.30/0.25/0.20/0.15/0.10)+阈值(±0.60)纯经验估计，无数据支撑
- P0-2: L2↔L3 反馈回路调幅(-30%/-50%/-1级/+20%)全占位值
- P0-3: M4 突破失败反向策略隐含假设（Brooks 美股 5min 数据有效），直接套 A 股日线未经验证

**P1 待解决项（应在 M2-M3 执行中解决）：**
- **Always-In 三重不一致（严重）**：requirements.md(L342-348) / project_charter.md / design_always_in.md(§1.2) 各自定义了不同的维度列表和权重映射。维度名不同、权重对应不同维度——同一个参数的三种定义，编码时该信谁？
- **P1.3 当前实现是 3 维简化版**(权重 0.35/0.40/0.25)，与任何一份文档的 5 维定义都不一致
- 验收标准来源不明（60%/65%/75%等基准无依据）
- 文档内部矛盾：核心原则"不依赖成交量"(L43)，但双顶检测/高潮反转检测依赖成交量(L698/L784)
- M3.5 range.py 假突破检测与 M3.6 trap.py 假突破陷阱功能重叠，边界模糊
- 项目路径笔误：L129 `price_action_tracing` → `PAT_stock`
- 第二处路径错误：L1355 `guorui_system` → `GR_stock`
- M4 信号融合权重未定义（L956 仅给出公式结构）
- M7 交叉验证引用已冻结系统（准我/郭睿），数据可能过时
- 全市场扫描范围未定义（3000+？全部？候选池？）

**P2 建议项（后续迭代优化）：**
- M4-M7 I/O 表引用粒度过粗（"M2-OUT-01~07" 作为整体输入）
- 文档节号错乱（2.7 趋势日七分法出现在 2.2 之前）
- 模糊验收标准：M2 "准确率≥65%"、M4 "能复现原始交易逻辑"、M6 "可完整跑通"

**CONDITIONAL 放行条件：** M1 不阻塞；M1.5 数据校准完成后，P0 项须用真实数据替换占位值，且 Always-In 三份文档定义须统一，方可进入 M2。

---

## 七、P1 设计文档审查（2026-06-14 4 人并行交叉验审）

### 7.1 审查结论概览

| 模块 | 审查人 | 日期 | 结论 | 证据 |
|------|--------|:----:|:----:|------|
| design_pinbar.md | 枢 | 06-14 | **CONDITIONAL** — 1 🔴 阻塞 + 5 项中低 | review_design_pinbar_shu_2026-06-14.md |
| design_key_levels.md | 枢 | 06-14 | **CONDITIONAL** — 7 处核心偏差（6 🔴 P0） | review_design_key_levels_shu_2026-06-14.md |
| design_always_in.md | 枢 | 06-14 | **CONDITIONAL** — 5 项修正后可升级 PASS | review_design_always_in_shu_2026-06-14.md |
| design_module_protocol.md | 枢 | 06-14 | **CONDITIONAL** — 2 严重 + 4 中低 | review_design_module_protocol_shu_2026-06-14.md |

### 7.2 pinbar 审查发现

| 严重度 | 问题 | 详情 |
|:------:|------|------|
| 🔴 | 函数签名缺失两个参数 | `main_shadow_ratio` 和 `body_position_threshold` 被硬编码，不可调优，违悖设计文档 §5 |
| 🟡 | 概念不一致 | requirements.md "反转K线"（Brooks: 尾巴>实体2倍）与 design_pinbar.md "Pinbar"（许佳聪: 主影线≥2/3全幅）是不等价的几何条件，多文档混用 |
| 🟡 | concept_map.md 缺失 Pinbar 条目 | 设计文档引用 §V-B03 实际是"测试极值动量判断"，非反转棒 |
| 🟡 | M5 price_limit.py 不存在 | 设计文档规划的涨停/跌停过滤模块未实现，信号中可能混入假信号 |
| 🟡 | debug 模式未实现 | 设计完备（5 列中间结果）但代码无对应功能 |
| 🟢 | 参数顺序不一致 | `atr_window` 在设计是第5参数，代码是第2参数 |
| 🟢 | 边缘测试用例10未实现 | 低波动股合法 Pinbar 被误杀场景 |

**关键修正**：requirements.md 与 design_pinbar.md 对 Pinbar 的定义等价性未经过验证，概念层存在混用。

### 7.3 key_levels 审查发现（最严重）

**整体评级：C-**——设计与实现严重偏离。

| # | 严重度 | 偏差项 | 设计值 | 代码值 | 影响 |
|:-:|:------:|--------|:------:|:------:|------|
| 1 | 🔴 | 返回类型不匹配 | `tuple[list, dict]` | `list` | 破坏 pipeline adapter |
| 2 | 🔴 | 聚类容差差 5 倍 | `1.5%` | `0.3%` | 聚类粒度完全不同 |
| 3 | 🔴 | 最小绝对容差缺失 | `0.10 元` | 无 | 低价股保护缺失 |
| 4 | 🔴 | 半衰期硬编码 | 参数化 `half_life=60` | `exp(-0.01*d)` ≈ 69 | 不可调优，偏 15% |
| 5 | 🔴 | 未复用 utils/indicators | 复用 `swing_high()/swing_low()` | 自实现 for 循环 | 逻辑分歧 |
| 6 | 🔴 | ATR 触摸缓冲缺失 | `0.5 ATR` buffer | 零缓冲 | touch_count 偏低 |
| 7 | 🔴 | both_sides ×1.5 未应用 | 强度×1.5 | 仅标记 bool | strength 不准确 |
| 🟡 | 聚类策略不同 | 混合统一聚类 | 分别聚类+合并 | cluster 结果集不同 |
| 🟢 | polarity_flips/fakeout_history | 预期 stub（空列表） | 完整超前实现 | 算法未经审查 |

**22 个测试全部针对当前实现编写，未覆盖设计文档约定行为**——"测试通过 ≠ 设计正确"。

### 7.4 always_in 审查发现

| 严重度 | 问题 | 详情 |
|:------:|------|------|
| ❌ 事实错误 | §1.2 对 project_charter 的描述错误 | design_always_in.md 声称 charter 含"EMA20斜率/通道位置"，实际 chart 是"20缺口棒/K线实体倾向/均线位置" |
| 🔴 文档不一致 | 三重不一致已澄清 | **代码已是 5 维版**，与 design_always_in.md 一致。根因是 design_always_in.md 错误描述了上游文档 |
| 🟡 A 股适配 | 连续涨跌停降权未实现 | ASH-09 `score×1/(N+1)` 公式已定义但未在 market_state.py 实现 |
| 🟢 微小偏差 | 5 处细节差异 | 回调深度 swing 取 3 个而非 1 个、通道方向名混用、缺口棒严格多数判定等 |
| 信息 | 阈值 ±0.30 有量化依据 | 统计推导：±0.30 ≈ 2.1σ → 约 7% 交易日有方向信号，±0.60 → 几乎恒为 NONE |

**交叉验证最重要修正**：之前认为 P1.3 是 3 维简化版、与任何文档都不一致 → 实际代码已在 P2 阶段升级为完整 5 维版，与 design_always_in.md 对齐。

**统一方案**：以 requirements.md 的维度清单为权威基准，采纳 design_always_in.md 的量化实现作为算法方案，M6 回测为最终裁判。

### 7.5 module_protocol 审查发现

| 严重度 | 问题 | 详情 |
|:------:|------|------|
| 🔴 | Always-In 维度不一致 | 协议写 3 维(0.35/0.40/0.25)，实际代码返回 5 维 |
| 🔴 | 反馈回路架构冲突 | 协议定义单向 L1→L6，requirements.md M2.5 要求 L2↔L3 双向 |
| 🟡 | P2 字段提前上线 | `polarity_nearby`/`fakeout_nearby` 未在协议中定义但 pipeline.py 已输出 |
| 🟡 | 全降级时 skip=False | 全部模块崩溃后输出"合法但空"的结果，掩盖系统性故障 |
| 🟡 | `_is_aligned` 逻辑同构 | 标准档和高置信度档判断逻辑完全相同，协议描述不清晰 |
| 🟢 | 包名不一致 | 设计文档用 `price_action_trading`，代码用 `PAT_stock` |

**推荐方案**：在协议中增加可选 Step 4.5（反馈回路），设为条件执行（默认关闭），保持向后兼容。

### 7.6 关键交叉验证纠正

**最重要修正**：
1. **Always-In 不是 3 维**——之前认为 P1.3 是 3 维简化版，实际代码已在 P2 升级为完整 5 维版，与 design_always_in.md 一致。三重不一致的根因是 design_always_in.md §1.2 错误描述了 project_charter.md。
2. **key_levels 代码-设计严重偏离**——6 项 P0，最致命的是聚类容差 0.3% vs 1.5%（差 5 倍）。测试全通过但未验证设计正确性。
3. **反馈回路冲突**——协议与需求在架构层面矛盾，需在进入 P2 前决议。
4. **Pinbar 概念混用**——Brooks "反转K线" 与 许佳聪 "Pinbar" 是两个不等价的几何条件。

### 7.7 新增 P0/P1 阻塞项

**新增 P0（必须修复）：**
- key_levels 函数签名、返回类型、聚类容差、min_abs_tolerance 对齐设计文档
- always_in ASH-09 连续涨跌停降权实现
- design_always_in.md §1.2 修正对 project_charter 的错误描述

**新增 P1（P2 前修复）：**
- pinbar 函数签名补充 main_shadow_ratio/body_position_threshold 参数
- 模块协议中为反馈回路预留接口
- 全降级时 skip=True
- price_limit.py 创建（涨跌停过滤）
- debug 模式实现
- 统一包名（price_action_trading → PAT_stock）

## 汇总

| 模块 | 编码审查 | 测试审查 | 设计交叉验证 | 第三方介入 |
|------|:--------:|:--------:|:-----------:|:---------:|
| M1 数据层 | — | — | — | workbuddy(隐式) |
| P1.1 Pinbar | workbuddy ✅ | Darwin ✅ | Darwin ✅ | 双agent |
| P1.2a 关键位 | workbuddy ✅ | Darwin ✅ | Darwin ✅ | 双agent |
| P1.3 Always-In(3D) | workbuddy ✅ | Darwin ✅ | Darwin ✅ | 双agent |
| P1.3→P2 5D升级 | Darwin ⚠️ | Darwin ⚠️ | — | 无 |
| P2 Spike+Channel | Darwin ⚠️ | Darwin ⚠️ | — | 无 |
| Pipeline联调 | Darwin ✅ | 枢 ✅ | — | 枢验收 |

**⚠️ = 自编自审, 无独立第三方**
