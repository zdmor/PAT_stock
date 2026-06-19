# 审查提示词：requirements.md

- **本提示词文件路径**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_requirements_prompt.md`
- **被审查文件**：`D:\ClaudeWorkspace\PAT_stock\docs\requirements.md`（1674行，M0-M7）
- **审查方式**：阅读本文 + 按路径打开源文件 → 对照需求文档逐项核查 → 输出审查结论
- **用途**：供枢或第三方审查人评审 PAT 系统需求文档

---

## 一、文件基本信息

| 字段 | 值 |
|------|-----|
| 被审查文件 | `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md` |
| 行数 | 1674 行，覆盖 M0（知识整理）到 M7（集成验证）共 9 个阶段 |
| 阶段归属 | M0 阶段产出 |
| 当前状态 | 已编码但未正式审查冻结 |
| 生成方式 | AI 根据 Brooks 蒸馏笔记 + 概念映射表 + A股适配规则生成，未经正式评审 |

---

## 二、背景：为什么建 PAT 系统

### 2.1 初衷

现有 3 个系统各有局限，都不具备"裸 K 线信号级交易决策"能力：

- **准我（因子量化）**：因子选股，不关注入场时机
- **非我 / 郭睿（Wyckoff）**：已冻结，精力不足维护
- **三者缺的共同能力**：基于裸 K 线的信号级交易决策

PAT 定位：**纯价格行为信号系统**——不从因子、不从指标，只从 K 线形态和市场结构出发，输出可执行交易信号。

### 2.2 愿景

> 基于 Al Brooks 价格行为学，构建一套可量化、可验证、可执行的 A 股交易信号系统。

每日全市场扫描 → 输出 ≤ 5 只选股 → 附带入场价/止损价/仓位建议 → 供枢决策参考。

### 2.3 核心原则

1. **纯 K 线，不依赖指标**——除 EMA20 用于趋势判定外，不使用任何技术指标
2. **不预测，只跟随**——Always-In 是当前状态快照，不是预测
3. **倾向派驱动，频率派约束**——方向判断（做什么）> 仓位管理（做多少）
4. **分类质量重于参数优化**——状态分对了，参数糙点也能赚钱
5. **A 股适配优先**——T+1、涨跌停、无做空机制必须处理
6. **可证伪**——每个组件最终能回答"什么条件下你是错的"

---

## 三、源文件索引（全部带本地路径）

### 3.1 一级源文件——原始知识

| 编号 | 文件 | 路径 | 内容 |
|------|------|------|------|
| S1 | Brooks 三部曲原著（3 本 PDF） | `C:\Users\sut-b\Desktop\Trading price action\Trading Price Action Trends (Al Brooks).pdf`<br>`C:\Users\sut-b\Desktop\Trading price action\Trading Price Action - Trading Ranges (Al Brooks).pdf`<br>`C:\Users\sut-b\Desktop\Trading price action\Trading Price Action - Reversals (Al Brooks).pdf` | Trends 479页 + Trading Ranges 617页 + Reversals 578页 = 1674页 |
| S2 | 蒸馏笔记（13 份 .md） | `C:\Users\sut-b\Desktop\Trading price action\` | 6272 行精读笔记。Trends 1270行 + Trading Ranges 1011行 + Reversals 3501行 |
| S3 | philosophy_deep_dive.md | `D:\ClaudeWorkspace\PAT_stock\docs\philosophy_deep_dive.md` | 基于 S2 的多维哲学分析，含市场本体论、认知论、Always-In 框架 |

### 3.2 二级源文件——M0 阶段其他产出（与 requirements.md 同级）

| 编号 | 文件 | 路径 | 内容 |
|------|------|------|------|
| S4 | concept_map.md | `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md` | 三书 102 概念 → Python 函数映射。A级43/B级36/C级23 |
| S5 | ashare_adaptation.md | `D:\ClaudeWorkspace\PAT_stock\docs\ashare_adaptation.md` | A 股适配规则 20 条，分 P0/P1/P2 三级 |
| S6 | project_charter.md | `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md` | 项目启动书：架构、里程碑(30天)、风险、决策日志 |

### 3.3 三级源文件——设计文档（requirements.md 定义的下游输出）

| 编号 | 文件 | 路径 | 内容 |
|------|------|------|------|
| S7 | design_pinbar.md | `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md` | Pinbar 检测算法详细设计（731行） |
| S8 | design_key_levels.md | `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md` | 关键位聚类算法详细设计（776行） |
| S9 | design_always_in.md | `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md` | Always-In 5维加权判定详细设计（828行） |
| S10 | design_module_protocol.md | `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md` | 模块间接口协议、数据流、管线编排 |

---

## 四、方法论

### 4.1 核心方法论：Al Brooks 价格行为学

三个核心事实（引自 philosophy_deep_dive.md §1.1）：

1. **市场 = 机构集合**——90%+ 交易量由机构完成，零和博弈
2. **价格行为 = 订单流视觉呈现**——K 线已包含所有供需信息，不依赖成交量/指标/新闻
3. **市场是分形的**——尖刺+通道是所有趋势的 DNA，tick 级到月线级一致

市场只有三种状态，永恒循环：**区间(~70%) → 趋势(~20%) → 突破(~10%) → 回到区间**

### 4.2 核心认知工具：Always-In 框架

"如果你在任何时候都必须持仓，你应该持多还是空？"
这不是预测，是当前状态的快照。5 维加权判定（设计文档：S9）：

| 维度 | 权重 | 理由 |
|------|------|------|
| EMA20 斜率（20缺口棒） | 0.30 | 极强趋势标志，信噪比最高 |
| HH/HL 结构 | 0.25 | 趋势定义最直观 |
| 通道位置 | 0.20 | 价格在通道内的相对位置 |
| 回调深度 | 0.15 | Brooks 自认"单一最佳量化指标" |
| Gap 棒 | 0.10 | 跳空方向，辅助 |

### 4.3 从 Brooks 到代码的完整翻译链

```
原著 PDF（S1，1674页）
    → 蒸馏笔记（S2，6272行）
        → concept_map（S4，102概念→函数签名）
        → philosophy_deep_dive（S3，体系理解）
        → ashare_adaptation（S5，A股特化）
            → requirements.md（本文件，阶段拆分+I/O定义）
                → design_*.md（S7-S10，详细算法）
                    → 编码实现
```

### 4.4 审查人需要的技能

- **Al Brooks 价格行为学基础**——Always-In、HH/HL、Spike+Channel、High/Low 计数、信号K线、陷阱（S2 蒸馏笔记有完整定义）
- **A 股交易规则**——T+1、涨跌停、无做空机制
- **量化交易基础**——回测、前视偏差、夏普/最大回撤/胜率
- **Python 数据栈**——pandas/numpy 向量化计算（审查代码实现时需此技能）

---

## 五、审查流程

### 5.1 推荐阅读顺序

1. **本提示词文件**（了解审查 scope）
2. **S6 project_charter.md**（了解完整项目框架）
3. **S2 蒸馏笔记至少前 5 份**（了解原始素材质量）
4. **S4 concept_map.md + S5 ashare_adaptation.md**（了解 M0 其他产出）
5. **被审查文件 requirements.md**（按阶段逐项审查）

### 5.2 逐阶段审查清单

#### M0：知识体系整理与需求（requirements.md L9-L98）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | M0 目标是否清晰 | requirements.md L9-L98 | 三书概念提取+分类+可量化等级划分是否合理 |
| 2 | M0 输入是否充分使用 | S1+S2 蒸馏笔记 | 13 份笔记是否全部覆盖？哪些概念遗漏了？ |
| 3 | M0 输出三者是否自洽 | S4+S5+本文件 | concept_map(102概念)、ashare_adaptation(20规则)、requirements 互相矛盾吗？ |
| 4 | 验收标准是否可验证 | requirements.md L96-L98 | "概念覆盖率≥80%"怎么测量？ |

#### M1：数据基建（requirements.md L99-L197）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | Tushare 复用路径有效？ | `D:\ClaudeWorkspace\zhunwo\data\loader.py` | 准我 loader.py 是否存在？接口是否兼容？ |
| 2 | 交易日历范围足够？ | requirements.md L161-L165 | 2017-2026 是否覆盖完整牛熊周期？ |
| 3 | 8 个指标对应 Brooks？ | requirements.md L169-L178 | MA/EMA/ATR/swing/gap/retracement——是否都是价格行为学需要的？ |
| 4 | 验收标准：3000只/1年 < 30分钟 | requirements.md L196-L197 | 含限频是否现实？ |

#### M1.5：数据探测（requirements.md L200-L286）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | 分层抽样 200 只合理？ | requirements.md L233-L235 | 大盘/中盘/小盘三等分是否代表全市场？ |
| 2 | 4 类统计量够用？ | requirements.md L238-L253 | 波动率/回调深度/Spike 幅度/区间宽度——这些能校准 M2 全部参数吗？ |
| 3 | 示例阈值合理？ | requirements.md L263-L271 | atr p25=1.8%、retracement p25=20%——在 A 股日线上合理吗？ |
| 4 | 验收标准：推荐值在 p25-p75 内 | requirements.md L282-L285 | 这个约束是否过于宽松？ |

#### M2：状态分类引擎（requirements.md L289-L564）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | Always-In 权重是否有依据？ | S9 + requirements.md L340-L370 | 0.30/0.25/0.20/0.15/0.10 是 Brooks 原书数据还是估计？ |
| 2 | Always-In 阈值 ±0.60 是否合理？ | requirements.md L351 | 太严→信号少，太松→噪音多。有依据吗？ |
| 3 | L2↔L3 反馈回路调幅有依据？ | requirements.md L486-L510 | -30%/-50%/-1级/+20% 是 Brooks 数据还是占位值？ |
| 4 | 多TF协同：信号冲突=不交易是否太保守？ | requirements.md L512-L539 | 日周冲突就放弃？会不会错失机会？ |
| 5 | 趋势日七分法验收标准 60% 来自哪？ | requirements.md L372-L401 | 7 类模板匹配，60% 一致率的 benchmark 是什么？ |
| 6 | 验收标准：整体≥65%、强趋势≥75%、区间≥55% | requirements.md L554-L563 | 这些数字的来源和依据？ |

#### M3：形态识别引擎（requirements.md L567-L832）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | High/Low 计数在日线上样本够？ | S4 T-A13 + requirements.md L620-L655 | Brooks 原本用 5 分钟图，日线级别信号数是否足够？ |
| 2 | 信号K线 A/B/C 评级是否可操作？ | requirements.md L662-L691 | "A 级=大尾巴小实体+关键位+共振"——这能编程吗？ |
| 3 | 4 类陷阱在日线上能否检出？ | requirements.md L762-L810 | 假突破/扫止损/高潮反转/窄区间——日线粒度够识别吗？ |
| 4 | 验收标准：楔形/双顶"能正确检出" | requirements.md L825-L831 | 没有量化指标，怎么算"能正确检出"？ |

#### M4：策略层（requirements.md L835-L984）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | 4 个趋势跟随子策略在日线上的信号频率？ | requirements.md L881-L903 | High 1 买入在日线上可能几个月才一次？ |
| 2 | 突破失败反向标注"80%胜率"有依据？ | requirements.md L909 | 是 Brooks 原书数据还是假设？ |
| 3 | Confluence 评分公式是否合理？ | requirements.md L948-L968 | 各策略权重怎么定？ |
| 4 | 验收标准：Top 5 至少 2 个信号源 | requirements.md L982 | 全市场 3000+只股票，Top 5 这个 N 值合理吗？ |

#### M5：风控执行层（requirements.md L987-L1156）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | 交易者方程 EV 阈值有回测依据？ | requirements.md L1039-L1041 | EV>0.3=高质量、0~0.3=合格、<0=拒绝——合理吗？ |
| 2 | T+1 规则与 ashare_adaptation 一致？ | S5 ASH-01~04 + requirements.md L1108-L1119 | 70%门槛 + 14:30禁开仓——与 S5 一致？ |
| 3 | 涨跌停规则可操作？ | S5 ASH-05~10 + requirements.md L1122-L1139 | "封板确认/炸板检测"——具体怎么判断？ |
| 4 | 半凯利上限截断 20% | requirements.md L1070-L1093 | 单票 20% 在 A 股是否合理？ |
| 5 | 验收标准 | requirements.md L1152-L1156 | 尾盘拦截、仓位 0%-20%、止损 1%、涨跌停≥95%——都可验证？ |

#### M6：回测系统（requirements.md L1158-L1269）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | 回测引擎前视偏差防护充分？ | requirements.md L1193-L1225 | "确认K线的入场必须在确认K线次日"——还有别的漏洞吗？ |
| 2 | 绩效分组维度合理？ | requirements.md L1227-L1249 | 按市场状态 + 按策略分——足够归因吗？ |
| 3 | 验收标准 | requirements.md L1263-L1269 | 费率/T+1/涨跌停/前视偏差——都验证了吗？ |

#### M6.5：集成冒烟测试（requirements.md L1273-L1338）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | 1 个月 + Top 200 足够暴露集成问题？ | requirements.md L1273-L1338 | 覆盖多少种市场状态？ |
| 2 | 各层检查标准合理？ | requirements.md L1314-L1332 | 缓存≥80%、Always-In 非空≥80%、信号>0 |

#### M7：集成与验证（requirements.md L1340-L1423）

| # | 审查项 | 参考来源 | 核查内容 |
|---|--------|----------|----------|
| 1 | 交叉验证方向一致≥60% 合理？ | requirements.md L1403-L1406 | 与准我(`D:\ClaudeWorkspace\zhunwo\`)/郭睿(`D:\ClaudeWorkspace\GR_stock\`)对比 |
| 2 | 月均信号 < 3 自动复审合理？ | requirements.md L1421 | 触发条件可操作吗？ |
| 3 | 验收标准 | requirements.md L1417-L1422 | run_daily() < 5分钟、≤5只选股 |

### 5.3 审查结论输出格式

审查完成后，请创建审查报告文件，按以下格式输出：

```
文件：`D:\ClaudeWorkspace\PAT_stock\reviews\review_requirements_<审查人>_<日期>.md`

## 一、审查结论：[PASS] / [CONDITIONAL] / [FAIL]

## 二、通过项
（列出所有通过的阶段 + 简要理由）

## 三、问题项
| # | 阶段 | 问题描述 | 严重度 | 建议修复 |
|---|------|----------|:------:|----------|
| 1 | M2 | Always-In 阈值 ±0.60 无实证依据 | 中 | M1.5 数据探测后校准 |
| 2 | ... | ... | 高/中/低 | ... |

## 四、未覆盖项
（需求文档应该覆盖但没有覆盖的内容）

## 五、总体评价
（200-500 字，核心结论）
```

---

## 六、关键决策点

以下是 requirements.md 涉及的关键决策，需特别关注：

| # | 决策 | 当前选择 | 替代选项 | 影响 |
|---|------|----------|----------|------|
| D1 | 主时间框架 | 日线 | 60分钟线辅助 | 信号密度 vs 可靠性折衷 |
| D2 | Always-In 权重 | 0.30/0.25/0.20/0.15/0.10 | 等权 / 其他分配 | 影响所有下游判断 |
| D3 | Always-In 阈值 | ±0.60 | ±0.50 / ±0.70 | 阈值越严信号越少 |
| D4 | 是否引入因子辅助 | 纯价格行为 | 可混合因子 | 独立性 vs 丰富度 |
| D5 | 每日选股数量 | Top N（N 未定） | 固定 5 只 | 质量 vs 数量平衡 |
| D6 | T+1 成功率门槛 | ≥70% | ≥60% / ≥80% | 安全边际高低 |
| D7 | 回测区间 | 2018-2026 | 更长 / 更短 | 周期覆盖 vs 数据质量 |
| D8 | 管线线圈数 | Pass1→反馈→Pass2 | 单次 / 多次 | 计算成本 vs 精度 |

---

## 七、全部关联文件清单

### 被审查文件
- `D:\ClaudeWorkspace\PAT_stock\docs\requirements.md`

### 源文件（审查必读）
- `C:\Users\sut-b\Desktop\Trading price action\`（蒸馏笔记 13 份，6272 行）
- `C:\Users\sut-b\Desktop\Trading price action\Trading Price Action Trends (Al Brooks).pdf`
- `C:\Users\sut-b\Desktop\Trading price action\Trading Price Action - Trading Ranges (Al Brooks).pdf`
- `C:\Users\sut-b\Desktop\Trading price action\Trading Price Action - Reversals (Al Brooks).pdf`
- `D:\ClaudeWorkspace\PAT_stock\docs\philosophy_deep_dive.md`
- `D:\ClaudeWorkspace\PAT_stock\docs\concept_map.md`
- `D:\ClaudeWorkspace\PAT_stock\docs\ashare_adaptation.md`
- `D:\ClaudeWorkspace\PAT_stock\docs\project_charter.md`

### 设计文件（被审查文档引用的下游输出）
- `D:\ClaudeWorkspace\PAT_stock\docs\design_pinbar.md`
- `D:\ClaudeWorkspace\PAT_stock\docs\design_key_levels.md`
- `D:\ClaudeWorkspace\PAT_stock\docs\design_always_in.md`
- `D:\ClaudeWorkspace\PAT_stock\docs\design_module_protocol.md`

### 引用代码路径（验真用）
- `D:\ClaudeWorkspace\zhunwo\data\loader.py`（M1 复用目标）
- `D:\ClaudeWorkspace\zhunwo\`（M7 交叉验证用）
- `D:\ClaudeWorkspace\GR_stock\`（M7 交叉验证用）

### 审查相关文件
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_requirements_prompt.md`（本提示词文件）
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_template.md`（审查模板）
- `D:\ClaudeWorkspace\PAT_stock\reviews\review_chain.md`（已有审查记录）

---

## 八、审查人指引

- **估计耗时**：阅读源文件 2-3 小时 + 逐项审查 1-2 小时
- **审查重点**：
  - 阶段拆分粒度是否合理
  - I/O 表是否完整可追溯
  - 验收标准是否可量化验证
  - 关键决策 D1-D8 是否有充足理由
  - 每项需求是否可追溯到 Brooks 概念
- **复查问题示例**：
  - "M2 验收标准 Always-In≥65%——来源是什么？"
  - "M4 突破失败反向标 80% 胜率——Brooks 原书数据还是假设？"
  - "M5 交易者方程 EV>0.3 阈值——有回测支持吗？"
- **审查报告输出到**：`D:\ClaudeWorkspace\PAT_stock\reviews\review_requirements_<审查人>_<日期>.md`

---

## 九、审查发现汇总（基于 requirements.md 本体通读）

以下为通读 requirements.md 1674 行后发现的文档本身问题，供审查人参考验证：

| # | 位置 | 问题 | 严重度 |
|---|------|------|:------:|
| F1 | M2 §2.1→§2.7→§2.2 | **节号错乱**：2.1 Always-In 后直接跳到 2.7 趋势日七分法，再回到 2.2 趋势强度。应把 2.7 移到 2.6 之后 | 低 |
| F2 | L129 | **路径笔误**：`price_action_tracing` → 应为 `PAT_stock` 或 `price_action_trading` | 低 |
| F3 | L43 vs L698/L784 | **内部矛盾**：核心原则"不依赖任何技术指标"，但双顶检测依赖"量能缩小"，高潮反转检测依赖"成交量异常放大"。需统一说明 | 中 |
| F4 | M3.5 vs M3.6 | **功能重叠**：`range.py` 的 `detect_fake_breakout()` 与 `trap.py` 的 `detect_fake_breakout_trap()` 都在做假突破检测，边界模糊 | 中 |
| F5 | M2/M3/M4/M6 验收标准 | **模糊验收**："准确率≥65%"（如何定义）、"能复现原始交易逻辑"（不可量化）、"可完整跑通"（何为跑通）、"能正确检出"（检出率？） | 中 |
| F6 | M4 L956 | **权重未定义**：信号融合公式 `score = sum(各策略置信度 × 策略权重 × 大盘乘数)` 中，"策略权重"全文未出现 | 中 |
| F7 | M4-M7 I/O 表 | **耦合过粗**：引用 "M2-OUT-01~07" 作为整体输入，M4 可能只需其中部分输出 | 低 |
| F8 | M2 L488-490 | **架构核心参数全占位**：L2↔L3 反馈回路是整个架构的创新点，但调幅 (-30%/-50%/-1级/+20%) 全是占位值 | 高 |
| F9 | M4 L982, M7 L1418 | **范围未定义**："全市场扫描"未定义具体范围——全部 A 股？沪深 300？候选池？ | 中 |
| F10 | M7 L1354-1355 | **前提不可靠**：引用准我(`zhunwo\`)和郭睿(`guorui_system\`)做交叉验证，两个系统已冻结，数据可能过时。路径 `guorui_system` 应为 `GR_stock` | 中 |

**与审查提示词前三节的关系**：以上 F1-F10 是文档本身的问题，前三节是跨文档决策审查。两者互补，交叉验证时可同时使用。
