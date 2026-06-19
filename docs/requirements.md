# 价格行为交易系统 — 详细阶段需求

> **冻结状态：** M1.5 校准完成, 2026-06-14 已冻结。后续变更须经审查流程。

> 本文档将项目启动书的 8 个阶段逐一展开，每个阶段包含：目标、输入、处理流程、输出、验收标准。

---

## M0: 知识体系整理与需求

### 目标
将 Al Brooks 三本书（6272行蒸馏笔记）中的交易规则转化为可编程的量化逻辑，建立概念↔代码的完整映射。

### 输入

| 编号 | 输入 | 类型 | 来源 |
|------|------|------|------|
| M0-IN-01 | Al_Brooks_价格行为学_完整蒸馏报告.md | Markdown, 490行 | C:\Users\sut-b\Desktop\Trading price action\ |
| M0-IN-02 | Trends_蒸馏笔记.md | Markdown, 1270行 | 同上 |
| M0-IN-03 | Trading_Ranges_蒸馏笔记.md | Markdown, 1011行 | 同上 |
| M0-IN-04 | Reversals 蒸馏笔记 ×8份 | Markdown, 3501行 | 同上 |
| M0-IN-05 | Trading Price Action Trends 原书 PDF | PDF, 479页 | 同上 |
| M0-IN-06 | Trading Ranges 原书 PDF | PDF, 617页 | 同上 |
| M0-IN-07 | Reversals 原书 PDF | PDF, 578页 | 同上 |
| M0-IN-08 | `docs/philosophy_deep_dive.md`（多维审视修正意见） | Markdown | project_charter.md M0 产出 |

### 处理流程

```
蒸馏笔记 → 概念提取 → 分类归入三大域(趋势/区间/反转)
                ↓
        可量化规则筛选 → 伪代码转译
                ↓
        A股特化适配规则
                ↓
        概念↔代码映射表 + 需求文档
```

#### Step 1: 概念提取与分类
逐份蒸馏笔记提取独立概念，归入三大域：
- **趋势域**: Always-In, Spike+Channel, High/Low计数, 回调深度, 趋势强度, 测量移动, 突破回调, 迟到入场
- **区间域**: 区间边界, 铁丝网, 80%突破失败, Breakout Test, 突破失败反向, 双底/双顶线, 区间收缩/扩张
- **反转域**: 楔形三推, 双顶/双底, 更高低点/更低高点, 信号K线, 两棒反转, 趋势线突破, 买入高潮/卖出高潮

#### Step 2: 可量化筛选规则
每条概念标注可量化等级：
- **A级（可直接量化）**: 有明确数值条件（如"回调 < 前波33%"）
- **B级（需简化量化）**: 有定性描述但无数值（如"趋势连续收阳"→"连续3根收阳"）
- **C级（暂不量化）**: 完全依赖主观判断（如"市场情绪"）

M0 只实现 A 级和 B 级。

#### Step 2b: 【新增】Reversals 补充量化

Reversals 蒸馏笔记有 3501 行但未被充分转化为可量化的规则，M0 阶段补充：

**三推楔形变体量化规则：**
- 标准楔形：3 推推进，每推动能递减（实体缩小），趋势线可画且被突破
- 扩张楔形：推幅扩大但动能仍递减（量价背离）
- 收缩楔形：推幅缩小 + 波动率收缩 → 即将突破
- 微楔形：3-5 根 K 线内的微型三推（日线级别少见但 60 分钟有用）

**双顶/双底处理规则：**
- 标准双顶：两顶高度差 < ATR 的 30%，中间回调 > ATR 的 50%
- 微双顶(Micro Double Top)：2-3 根 K 线内形成，相邻 K 线高点接近
- 双顶失败处理：第二顶突破第一顶 1%+ → 双顶失效，变为趋势延续
- 颈线突破确认：收盘在颈线外 + 下一根 K 线确认

**趋势线突破变体：**
- 加速趋势线（更陡）：突破信号更强
- 减速趋势线（趋平）：突破后容易反弹测试
- 内趋势线（Inside Trendline）：突破后常回测

**Micro 形态入场规则：**
- Micro Double Top/Low 1：最可靠的微形态入场
- 量化条件：相邻 K 线高/低点差 < 0.5% ATR

#### Step 3: A股适配规则提取
从蒸馏笔记第3部分（A股落地实操体系）提取：
- T+1 制度下的入场/止损/仓位调整规则
- 涨跌停板的突破/假突破/封板规则
- A股特有形态（炸板、涨停回调等）

### 输出

| 编号 | 输出 | 格式 | 用途 |
|------|------|------|------|
| M0-OUT-01 | `docs/requirements.md` | Markdown | 本文档，全阶段需求 |
| M0-OUT-02 | `docs/concept_map.md` | Markdown | 概念→函数/类映射表 |
| M0-OUT-03 | `docs/ashare_adaptation.md` | Markdown | A股适配规则明细 |

### M0 验收标准
- [ ] 概念分类覆盖三本书 ≥ 80% 的核心概念
- [ ] 映射表中的每个概念都有对应的预计文件名和函数名
- [ ] A股适配规则不少于 15 条
- [ ] 所有 A 级概念已转译为伪代码

---

## M1: 数据基建

### 目标
搭建 K 线数据获取、缓存、预处理管线，为上层分析提供干净的日线数据。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M1-IN-01 | 准我系统的 `loader.py`(复用) | D:\ClaudeWorkspace\zhunwo\data\loader.py |
| M1-IN-02 | Tushare Pro API | pip install tushare |
| M1-IN-03 | 交易日历需求 | project_charter.md §M1 |
| M1-IN-04 | 概念映射表中"基础工具"部分 | concept_map.md |

### 处理流程

```
Tushare Pro API → 日线获取(复权) → CSV本地缓存
                      ↓
              交易日历生成 → 日期索引
                      ↓
              基础工具函数: MA/EMA/ATR/高低点/分位数
                      ↓
              数据完整性校验 → 断点续补
```

### 详细任务

#### 1.1 项目骨架搭建
创建完整目录结构：
```
D:\ClaudeWorkspace\PAT_stock\
├── __init__.py
├── data/__init__.py
├── utils/__init__.py
├── state/__init__.py
├── patterns/__init__.py
├── strategies/__init__.py
├── risk/__init__.py
├── backtest/__init__.py
└── requirements.txt
```

#### 1.2 K线数据获取模块 — `data/loader.py`
复用量准我的 `loader.py` 的核心函数：
- `get_pro()` — Tushare 单例
- `get_daily(ts_code, start, end, adj="qfq")` — 个股日线（前复权）
- `_rate_limit()` — 0.3s 限频
- `_cache_read()` / `_cache_write()` — CSV 缓存

新增函数：
- `get_kline_batch(ts_codes, start, end)` — 批量日线获取
- `get_60min_kline(ts_code, start, end)` — 60 分钟线获取（用于入场时机细化）
- `get_all_trade_dates(start, end)` — 交易日历

#### 1.3 K线缓存模块 — `data/cache.py`
优化缓存的按股票+日期双索引访问：
- `KlineCache.get(ts_code, start, end)` — 获取个股K线
- `KlineCache.get_panel(ts_codes, start, end)` — 多股面板
- `KlineCache.prefetch(trade_dates)` — 预下载全市场
- 缓存增量更新（断点续传）

#### 1.4 交易日历 — `data/calendar.py`
- `TradeCalendar(start, end)` — 交易日生成
- `is_trade_day(date)` — 是否交易日
- `next_trade_day(date)` / `prev_trade_day(date)` — 前后交易日
- `monthly_rebalance_dates()` — 月末交易日

#### 1.5 基础工具函数 — `utils/indicators.py`
价格行为学需要的基础计算，全是向量化 pandas：

| 函数 | 用途 | 对应 Brooks 概念 |
|------|------|-----------------|
| `ma(series, n)` | 移动平均 | EMA20 均线 |
| `ema(series, n)` | 指数移动平均 | Brooks 只用 20EMA |
| `atr(high, low, close, n)` | 平均真实波幅 | 波动率度量 |
| `swing_high/low(close, n)` | 摆动高低点 | High/Low 计数基础 |
| `bar_range(high, low)` | K线范围 | K线重叠度 |
| `gap_up/down(close, open)` | 跳空检测 | 缺口K线 |
| `consecutive_direction(close, n)` | 连续同向K线 | 趋势棒连续计数 |
| `retracement_depth(peak, trough, current)` | 回调深度 | 趋势强度核心指标 |

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M1-OUT-01 | `data/loader.py` | Tushare 数据接口（可获取日线+60min线） |
| M1-OUT-02 | `data/cache.py` | K线缓存管理（增量更新） |
| M1-OUT-03 | `data/calendar.py` | 交易日历 |
| M1-OUT-04 | `utils/__init__.py` | 工具模块入口 |
| M1-OUT-05 | `utils/indicators.py` | 8+个基础计算函数 |
| M1-OUT-06 | `requirements.txt` | 依赖清单 |

### M1 验收标准
- [ ] `get_daily()` 可获取任意个股前复权日线
- [ ] `KlineCache` 首次获取后第二次走缓存
- [ ] 交易日历覆盖 2017-01-01 ~ 2026-12-31
- [ ] 所有 indicator 函数有单测（输入输出可验证）
- [ ] 获取 3000 只股票 1 年日线耗时 < 30 分钟（含限频）

---

## M1.5: 数据探测【新增】

### 目标
在正式编写 M2 状态分类逻辑前，基于真实 A 股数据校准阈值，避免直接套用 Brooks 5 分钟图经验值。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M1.5-IN-01 | A 股日线数据 (2018-2026) | M1-OUT-01/02 |
| M1.5-IN-02 | A 股股票列表 | M1-OUT-01 |
| M1.5-IN-03 | 阈值参数清单（回调深度/Spike幅度/区间宽度等） | M0-OUT-02 (concept_map.md) |

### 处理流程

```
股票列表 (4000+只)
    ↓
分层抽样: 大盘/中盘/小盘各 ~70 只 (= 200 只)
    ↓
3 年日线加载 (2018-2026, 覆盖完整牛熊周期)
    ↓
4 类关键统计量计算:
  1. 日均波动率分布 (ATR) → 校准"小回调"阈值
  2. 回调深度分布 (单波最大回撤) → 校准 33%/50% 边界
  3. Spike 幅度分布 (连续大实体涨幅) → 校准 Spike 检测阈值
  4. 区间宽度分布 (Barbwire 判定边界) → 校准窄区间标准
    ↓
输出 data/thresholds.json (25%/50%/75% 分位数 + 推荐值)
```

### 详细任务

#### 1.5.1 分层抽样策略

按流通市值三分位 (大盘/中盘/小盘) 各抽 ~70 只，避免抽样偏差导致阈值对某一市值段失准。

#### 1.5.2 统计量计算 — `utils/calibrate.py`

```python
def sample_stocks(stock_list: pd.DataFrame, n: int = 200) -> List[str]:
    """分层抽样，返回 ts_code 列表 """

def compute_atr_distribution(df_panel: pd.DataFrame) -> dict:
    """返回 ATR 的 25/50/75 分位数 """

def compute_retracement_distribution(df_panel: pd.DataFrame) -> dict:
    """返回回调深度的 25/50/75 分位数 """

def compute_spike_distribution(df_panel: pd.DataFrame) -> dict:
    """返回 Spike 幅度的 25/50/75 分位数 """

def compute_range_width_distribution(df_panel: pd.DataFrame) -> dict:
    """返回区间宽度的 25/50/75 分位数 """

def generate_thresholds(df_panel: pd.DataFrame) -> dict:
    """输出完整的 thresholds.json """
```

#### 1.5.3 输出格式: `data/thresholds.json`

> **`[占位值]`** 以下示例值为占位数据——非实际 A 股统计值。M1.5 阶段用真实 A 股日线数据覆盖。

```json
{
  "atr": {"p25": 0.018, "p50": 0.025, "p75": 0.035, "recommended": 0.025},
  "retracement": {"p25": 0.20, "p50": 0.35, "p75": 0.55, 
                   "strong_trend": 0.33, "medium_trend": 0.50},
  "spike": {"min_consecutive_bars": 2, "min_body_pct": 0.70, 
            "min_magnitude_atr": 3.0},
  "range": {"barbwire_max_width_atr": 0.30}
}
```

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M1.5-OUT-01 | `data/thresholds.json` | A 股专用阈值基线 |
| M1.5-OUT-02 | `utils/calibrate.py` | 统计量计算工具 |

### M1.5 验收标准
- [ ] 抽样覆盖大盘/中盘/小盘各 >= 60 只
- [ ] thresholds.json 包含全部 4 类参数的 25/50/75 分位数
- [ ] 推荐值在 p25~p75 区间内（不应取极端值）
- [ ] M2 模块的默认参数引用此文件

---

## M2: 状态分类引擎

### 目标
对任意个股 + 大盘指数，输出当前市场状态（Always-In 方向 + 趋势强度 + 市场周期位置）。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M2-IN-01 | 个股日线数据 (open/high/low/close/vol) | M1-OUT-01/02 |
| M2-IN-02 | 大盘指数日线 (000300.SH) | M1-OUT-01 |
| M2-IN-03 | 概念映射表中"市场状态"部分 | concept_map.md |
| M2-IN-04 | A股适配规则（状态分类相关） | ashare_adaptation.md |

### 处理流程

```
个股日线 + 大盘日线
        ↓
Always-In判定 (5维加权评分系统)
        ↓
趋势强度量化 (回调深度 + 均线偏离 + 缺口棒)
        ↓
Spike+Channel检测 (尖刺识别 + 通道确认 + 通道分类)
        ↓
市场周期定位 (窄区间→突破→趋势→区间→窄区间)
        ↓
多时间框架协同 (日线+周线信号一致性校验)
        ↓
【Pass 1】→ L3 形态识别
        ↓
【反馈回路】L3 形态结果 → context_feedback 反向调整 L2 置信度
        ↓
【Pass 2】L2-updated → L3 重新确认
        ↓
输出: {股票, 日期, always_in(更新后), trend_strength, 
       spike_channel_status, market_cycle_phase, multi_tf_signal}
```

**管线圈数说明：**
- Pass 1: L2(初始状态) → L3(形态检测)
- 反馈: L3 结果（楔形/陷阱/假突破/高潮反转）→ 调整 L2 Always-In 置信度
- Pass 2: L2(更新后) → L3(重新确认) → 最终结果 → L4 策略
- 仅对 L3 判定导致 Always-In 方向翻转的股票触发重算，避免全量两轮

### 详细任务

#### 2.1 Always-In 判定 — `state/always_in.py`

**Brooks 定义：** "如果你在任何时候都必须持仓，你应该持多还是空？"

**算法（加权评分）：**

| 维度 | 权重 | 评分逻辑 | 理由（Brooks 原文） |
|------|------|---------|-------------------|
| 20 缺口棒 | 0.30 | >20根K线不触MA → +1, 否则 -1 | "极强趋势"标志，信噪比最高 |
| 高/低点结构 | 0.25 | HH+HL → +1, LL+LH → -1, 混合 → 0 | 趋势定义最直观的指标 |
| K 线实体倾向 | 0.20 | 阳实体>60% → +1, 阴实体>60% → -1 | 基础信号，易受单根异常影响 |
| 回调深度 | 0.15 | <前波33% → +1, >50% → -1 | Brooks 自认为"单一最佳量化指标" |
| 均线位置 | 0.10 | 在EMA20以上 → +1, 以下 → -1, 反复穿越 → 0 | 辅助判断 |

**判定规则：** 加权总分 `> 0.60` → LONG，`< -0.60` → SHORT，其余 → NONE。

**权重可配置：** 权重矩阵存储在 `config/defaults.py`，M6 回测阶段可调优。

**函数签名：**
```python
def determine_always_in(df: pd.DataFrame, 
                         weights: dict = None) -> str:
    """返回 "LONG" / "SHORT" / "NONE" """
    # weights 默认从 config/defaults.py 读取

def always_in_confidence(df: pd.DataFrame) -> float:
    """返回加权总分 (-1.0 ~ 1.0) """
```

**多时间框架集成：**
```python
def multi_tf_always_in(df_daily: pd.DataFrame, df_weekly: pd.DataFrame) -> dict:
    """返回 {daily: str, weekly: str, combined: str} """
    # combined: 日周一致时用该方向，不一致时取日线
```

#### 2.2 趋势日七分法 — `state/trend_day_classifier.py`【M2.5 降级】

**说明：** 从 M2.2 降级——先通过 2.1, 2.3-2.7 确定"是否在趋势中"（Always-In + 趋势强度 + Spike+Channel + 周期 + 多TF + 反馈），再分类"什么趋势类型"。Always-In = NONE 时跳过此模块。

**Brooks 核心创新：** 不同的趋势日类型需要完全不同的交易策略。必须先判断今天是什么类型的日子，再匹配策略。

**7 种趋势日类型与识别规则：**

| 类型 | 识别规则 | 行为含义 |
|------|---------|---------|
| **小回调趋势日** | 回调 < 日均范围 20%，所有信号棒看起来都很弱，无人敢逆势 | 机构持续买入，没人愿意卖出 |
| **尖刺+通道趋势日** | 早盘 Spike（大实体连续拉升）+ 后续通道（斜向回调可控），最终有两腿结束 | 最常见的趋势日结构 |
| **趋势性区间日** | 开盘区间→突破→形成第二区间，全天可画 2-3 个水平区间 | 区间突破→新区间→再突破 |
| **趋势恢复日** | 早盘趋势→横盘数小时（回调至 EMA20）→尾盘恢复原方向 | 午盘休整，尾盘机构回补 |
| **反转日** | 先走一方向→高潮（异常大实体）→反转两腿走反向 | 机构利用流动性反向建仓 |
| **宽通道/楼梯日** | 多段式运动，每段有趋势性高/低点，通道斜率逐渐变缓 | 趋势末期，多空分歧加大 |
| **开盘趋势日** | 第一根 K 线即打出极值，全天不回头 | 消息驱动，单边轧空/轧多 |

**函数签名：**
```python
def classify_trend_day(df: pd.DataFrame, always_in: str) -> dict:
    """返回 {trend_day_type: str, confidence: float, features: dict}
    
    分类流程:
    1. 先计算特征向量: {开盘范围, 前30分波动率, 信号K线强弱, 回调深度, ...}
    2. 匹配 7 类模板（特征阈值匹配）
    3. 输出最匹配的类型 + 置信度
    """
```

#### 2.3 趋势强度量化 — `state/trend_strength.py`

**Brooks 定义：** 回调深度是趋势强度的单一最佳量化指标。

**算法：**
```
1. 识别最近 swing high/low
2. 计算当前回调幅度 / 前一波幅
3. 判断均线位置关系

趋势强度分级:
  强趋势(AAA): 回调 < 前波33%, 价格在EMA20单侧运行
  中等趋势(AA): 回调 33%-50%, 价格偶尔穿越EMA20
  弱趋势(A):   回调 > 50%, 价格频繁穿越EMA20
  区间(B):     无明显方向, 边界清晰
  下跌趋势(C): 均线压制, 反弹无力
```

**函数签名：**
```python
def classify_trend_strength(df: pd.DataFrame) -> dict:
    """返回 {strength: str, retrace_depth: float, above_ema: bool, ...} """

def measure_retracement_depth(peak: float, trough: float, current: float) -> float:
    """返回回调深度比 (0.0 ~ 1.0+) """
```

#### 2.4 Spike + Channel 检测 — `state/spike_channel.py`

**Brooks 定义：** 所有趋势都由 Spike（尖刺）+ Channel（通道）构成。

**算法：**
```
Spike 检测:
  1. 连续 2-5 根 K 线, 实体占比 > 70%
  2. K 线之间几乎没有重叠 (< 20% 重叠区域)
  3. 累计涨幅 > 最近 20 根 K 线的 ATR 的 3 倍

Channel 检测:
  1. Spike 结束后, 价格沿趋势方向斜向运动
  2. 回调受控 (回撤不超 spike 的 50%)
  3. 通道边界可识别（上轨/下轨近似平行）

Channel 类型:
  - 牛通道: 斜向上, 回调 in 通道
  - 熊通道: 斜向下, 反弹 in 通道
  - 横盘通道: 水平 (实为旗形)
```

**函数签名：**
```python
def detect_spike(df: pd.DataFrame) -> Optional[dict]:
    """返回 {start_idx, end_idx, direction, magnitude} 或 None """

def detect_channel(df: pd.DataFrame, spike: dict) -> Optional[dict]:
    """返回 {type, upper_bound, lower_bound, slope} 或 None """

def spike_channel_analysis(df: pd.DataFrame) -> dict:
    """返回完整 Spike+Channel 分析结果 """
```

#### 2.5 市场周期定位 — `state/market_cycle.py`

**Brooks 定义：** 市场永远在循环：窄区间 → 突破 → 尖刺+通道 → 宽通道 → 区间 → 窄区间

**算法：**
```
周期阶段判定:
  1. 窄区间(Barbwire)阶段: 连续 N 根 K 线范围的宽度 < 阈值
  2. 突破阶段: 价格越过窄区间边界 + 大实体确认
  3. 尖刺+通道阶段: 加速上涨/下跌后进入斜向通道
  4. 宽通道阶段: 通道斜率趋缓, 振幅扩大
  5. 区间阶段: 无明显方向, 边界可识别
  
  6. 重新进入窄区间: 区间再次收缩
```

```python
def identify_market_cycle(df: pd.DataFrame) -> str:
    """返回 "barbwire" / "breakout" / "spike_channel" / "wide_channel" / "trading_range" """
```

#### 2.6 上下文反馈模块 — `state/context_feedback.py`【新增】

**用途：** L2↔L3 反馈回路，解决 Brooks 方法论中"同一根 K 线在不同位置含义不同"的循环性问题。

**反馈规则矩阵 `[占位值]`：**

> ⚠️ **`[占位值]` — 架构核心参数，当前代码不可直接使用。** 以下调幅百分比为初始估计值，无实证依据。L2↔L3 反馈回路是整个架构的核心创新点，调幅的正确性直接决定反馈机制是否有效。必须在 M1.5 数据探测 + M6 网格搜索校准后才能作为生产参数。校准前仅可用于模块接口联调测试。

| L3 检测结果 | 对 L2 的影响 | 调幅 | 影响维度 |
|------------|-------------|------|---------|
| 假突破陷阱 | Always-In 置信度降低 | -30% | 高/低点结构 |
| 高潮反转陷阱 | Always-In 方向可能翻转 | -50% | 方向置信度 |
| 扫止损陷阱 | 趋势强度降级 | -1 级 | 趋势强度 |
| 楔形形态 | 反转信号增强 | +20% 反向 | 方向置信度 |
| 双顶/底确认 | 反转信号增强 | +20% 反向 | 方向置信度 |

**函数签名：**
```python
def feedback_adjust(
    always_in: str,           # 当前 Always-In 方向
    confidence: float,         # 当前 Always-In 加权总分
    l3_results: list,          # L3 形态识别结果列表
    trend_strength: str        # 当前趋势强度
) -> dict:
    """返回 {always_in_updated, confidence_updated, 
             trend_strength_updated, adjustments: [{reason, delta}, ...]}"""
```

#### 2.7 多时间框架协同 — `state/multi_tf.py`

**Brooks 原文：** 同一模式在所有时间框架重复出现（分形结构），但不同时间框架的信号可能冲突。

**用途：** 当周线级别是上升趋势，日线级别是回调时，策略应该倾向做多而非做空。

**算法：**
```
多框架信号规则:
  1. 日线 Always-In + 周线 Always-In 方向一致：
      → 方向为当前主要交易方向
  2. 日线趋势但周线区间：
      → 可做日线方向，但仓位减半
  3. 日线区间但周线趋势：
      → 顺周线方向做突破，逆周线方向做区间
  4. 日线 + 周线方向相反：
      → 不交易（等待共振或一方结束）
```

**函数签名：**
```python
def multi_tf_alignment(df_daily: pd.DataFrame, df_weekly: pd.DataFrame) -> dict:
    """返回 {daily_ai: str, weekly_ai: str, alignment: str, 
             position_multiplier: float}
    alignment: "aligned" / "neutral" / "conflict"
    position_multiplier: 1.0(一致) / 0.5(中性) / 0.0(冲突)
    """
```

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M2-OUT-01 | `state/always_in.py` | Always-In 判定模块（5 维加权） |
| M2-OUT-02 | `state/trend_strength.py` | 趋势强度量化模块 |
| M2-OUT-03 | `state/spike_channel.py` | Spike+Channel 检测模块 |
| M2-OUT-04 | `state/market_cycle.py` | 市场周期定位模块 |
| M2-OUT-05 | `state/context_feedback.py` | **【新增】** L2↔L3 反馈回路 |
| M2-OUT-06 | `state/multi_tf.py` | 多时间框架协同 |
| M2-OUT-07 | `state/trend_day_classifier.py` | **【M2.5降级】** 趋势日七分法 |
| M2-OUT-08 | `test/test_state.py` | 状态分类单元测试 |

### M2 验收标准
- [ ] Always-In 方向判断准确率整体 >= 65%（分层：强趋势日 >= 75%、区间日 >= 55%）
  - **测量方法：** 在 500 只样本股票 × 2018-2026 区间上，对每个交易日输出 Always-In 方向，与次日实际收盘方向对比。强趋势日/区间日按 M2.2 分类结果分层统计。双人标注 Kappa 系数作为人类一致率基线。
- [ ] Always-In 加权模块权重可从 config 读取和修改
- [ ] 趋势强度五级分类在人工标注样本上 >= 60% 一致率
- [ ] 趋势日七分法在人工标注样本上 >= 60% 一致率
- [ ] 多时间框架协同在周线/日线冲突时正确输出 conflict 状态
- [ ] 反馈回路: L3 检测到假突破/高潮反转时 Always-In 置信度被正确调整
- [ ] Spike+Channel 在明显趋势中能正确识别
- [ ] 市场周期定位在 2018-2026 完整区间内可运行
- [ ] 单只股票分析耗时 < 0.1s（有缓存后）

---

## M3: 形态识别引擎

### 目标
在已知市场状态的基础上，识别具体的价格行为形态（High/Low 计数、信号K线、反转形态、区间形态），为策略层提供信号触发。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M3-IN-01 | 个股日线数据 | M1-OUT-01/02 |
| M3-IN-02 | M2 状态分类结果 | M2-OUT-01 (Always-In) + M2-OUT-03 (趋势强度) + M2-OUT-04 (Spike+Channel) + M2-OUT-07 (趋势日类型) |
| M3-IN-03 | 概念映射表中"形态识别"部分 | concept_map.md |
| M3-IN-04 | 反转蒸馏笔记（楔形、双顶/双底等） | Al_Brooks_完整蒸馏报告.md |

### 处理流程

```
个股日线 + 状态分类 (L2)
        ↓
Swing Point检测 → 关键高/低点列表
        ↓
High/Low计数系统 (在趋势中计数回调/反弹段数)
        ↓
信号K线识别 (趋势K线/Doji/内包/外包/反转K线)
        ↓
反转形态识别 (楔形/双顶底/旗形/三角形)
        ↓
区间形态识别 (铁丝网/区间边界/假突破)
        ↓
陷阱识别 (假突破/扫止损/高潮反转/窄区间陷阱)
        ↓
→ 结果反馈至 L2 context_feedback
        ↓
输出: {信号K线列表, High/Low计数, 形态列表, 陷阱列表, 关键位}
```

### 详细任务

#### 3.1 Swing Point 检测 — `utils/indicators.py`（补充）

所有形态识别的基础。新增函数：

```python
def find_swing_highs(close: pd.Series, n: int = 5) -> pd.Series:
    """返回 boolean Series: True 表示该位置是 swing high """

def find_swing_lows(close: pd.Series, n: int = 5) -> pd.Series:
    """返回 boolean Series: True 表示该位置是 swing low """

def get_key_levels(high: pd.Series, low: pd.Series, n: int = 5) -> dict:
    """返回 {support_levels: [...], resistance_levels: [...]} """
```

#### 3.2 High/Low 计数系统 — `patterns/high_low.py`

**Brooks 核心：** 回调中的反弹高点计数（High 1/2/3）判断趋势回调是否结束。

**算法：**
```
在牛市中:
  - 确定 swing low（回调低点）
  - 从该低点反弹:
    第一次反弹高点 = High 1
    第二次反弹高点 = High 2
    第三次反弹高点 = High 3
  - High 计数越低, 趋势越强
  - High 1/2 在强趋势中有效 → 可入场
  - High 3/4 在弱趋势/区间中才需要 → 入场需谨慎

在熊市中:
  - 确定 swing high（反弹高点）
  - 从该高点回落:
    第一次回落低点 = Low 1
    第二次回落低点 = Low 2
    第三次回落低点 = Low 3
```

**函数签名：**
```python
def count_highs(df: pd.DataFrame, trend: str) -> pd.Series:
    """在牛市中, 每根 K 线返回当前 High 计数 (0,1,2,3,4) """

def count_lows(df: pd.DataFrame, trend: str) -> pd.Series:
    """在熊市中, 每根 K 线返回当前 Low 计数 (0,1,2,3,4) """

def high_low_signal(df: pd.DataFrame, always_in: str) -> dict:
    """返回 {high_count, low_count, signal_valid, entry_trigger} """
```

#### 3.3 信号K线识别 — `patterns/signal_bar.py`

**Brooks 定义：** 触发入场的前一根 K 线 = 信号棒。信号棒质量决定交易胜率。

**算法：**
```
K线分类:
  趋势K线: 实体 > 70% 全幅, 影线 < 30% 全幅
  Doji:       实体 < 10% 全幅
  内包K线:    高点 < 前高 且 低点 > 前低
  外包K线:    高点 > 前高 且 低点 < 前低
  反转K线:    尾巴 > 实体 2 倍 + 方向与趋势相反

信号K线质量评级:
  A级: 大尾巴小实体 + 关键位 + 多因素共振
  B级: 反转K线 + 关键位
  C级: 仅单根信号K线

两棒反转检测:
  (趋势K线 + 反向趋势K线) 实体相当 → 强反转
```

**函数签名：**
```python
def classify_bar(df: pd.DataFrame, idx: int) -> dict:
    """返回 {type, body_pct, tail_pct, is_inside, is_outside, ...} """

def detect_signal_bar(df: pd.DataFrame, idx: int, always_in: str) -> dict:
    """返回 {is_signal, quality, direction, reason, ...} """

def detect_two_bar_reversal(df: pd.DataFrame, idx: int) -> Optional[dict]:
    """返回 {direction, strength} 或 None """

def detect_three_bar_reversal(df: pd.DataFrame, idx: int) -> Optional[dict]:
    """返回 {direction, strength} 或 None """
```

#### 3.4 反转形态识别 — `patterns/reversal.py`

| 形态 | 检测逻辑 |
|------|---------|
| 楔形(Wedge) | 3 推推进, 动能递减(实体缩小), 趋势线可画 |
| 双顶 | 两个相近高点, 中间一个回调低点, 第二顶量能缩小 |
| 双底 | 两个相近低点, 中间一个反弹高点, 第二底量能缩小 |
| 微双顶/底 | 2-3 根 K 线级别的小双顶/底 |
| 旗形(Flag) | 趋势中短暂横盘, K 线重叠, 无反向趋势 |
| 三角形 | 收敛形态, 高点降低 + 低点抬高 |
| 更高低点(Higher Low) | 熊转牛确认信号 |
| 更低高点(Lower High) | 牛转熊确认信号 |

**函数签名：**
```python
def detect_wedge(df: pd.DataFrame) -> Optional[dict]:
    """返回 {type(bull/bear), push_count, start_idx, end_idx} """

def detect_double_top(df: pd.DataFrame) -> Optional[dict]:
    """返回 {top1, top2, neckline, status} """

def detect_double_bottom(df: pd.DataFrame) -> Optional[dict]:
    """返回 {bottom1, bottom2, neckline, status} """

def detect_flag(df: pd.DataFrame, always_in: str) -> Optional[dict]:
    """返回 {direction, start, end, breakout_direction} """

def detect_higher_low(df: pd.DataFrame) -> Optional[int]:
    """返回 higher low 的 index 或 None """

def detect_lower_high(df: pd.DataFrame) -> Optional[int]:
    """返回 lower high 的 index 或 None """

def detect_all_patterns(df: pd.DataFrame, always_in: str) -> list:
    """返回 [{pattern_type, direction, confidence, ...}, ...] """
```

#### 3.5 区间形态识别 — `patterns/range.py`

**算法：**
```
区间边界自动识别:
  1. 最近 N 根 K 线的 swing high 中位数 → 阻力位
  2. 最近 N 根 K 线的 swing low 中位数 → 支撑位
  3. 边界清晰度评分

铁丝网(Barbwire)检测:
  1. 连续 N 根 K 线, 高低范围 < 平均ATR的30%
  2. K 线之间高度重叠

假突破检测（区间形态层）:
  1. 价格突破边界
  2. 突破后 N 根 K 线内回到边界内
  3. 突破 K 线有长影线
  → 输出到 trap.py 做陷阱判定（本模块只做形态检测，不做陷阱结论）
```

**函数签名：**
```python
def identify_range_boundary(df: pd.DataFrame) -> dict:
    """返回 {support, resistance, clarity_score} """

def detect_barbwire(df: pd.DataFrame) -> Optional[dict]:
    """返回 {start_idx, end_idx, width} 或 None """

def detect_fake_breakout(df: pd.DataFrame) -> Optional[dict]:
    """返回 {direction, breakout_idx, failure_idx} 或 None """
```

#### 3.6 【新增】陷阱识别 — `patterns/trap.py`

**Brooks 体系的精髓：** 识别"市场在做什么陷阱"是 Brooks 区别于其他技术分析的核心。

> **成交量使用说明：** Brooks 方法论核心是纯 K 线分析，不依赖成交量做方向判断。但 Brooks 原著在高潮反转陷阱和双顶/底确认时确实参考成交量作为辅助确认信号（异常放量 = 高潮特征）。本模块仅在陷阱识别阶段使用成交量作为辅助确认，不用于趋势判定或信号生成。双顶/底检测中的"量能缩小"同理——仅用于形态确认，非必要条件。若成交量数据不可用（如部分免费数据源不提供成交量），相关检测降级为仅基于 K 线形态。

**算法：**
```
陷阱类型识别:

1. 假突破陷阱(Fake Breakout Trap):
   - **前置条件：** range.py 的 detect_fake_breakout() 先检出一个"疑似假突破"形态
   - **陷阱确认：** 在此基础上验证：突破后 N 根 K 线内回到突破位另一侧 + 反向信号K线确认
   - **分工：** range.py 做形态检测（"价格突破又回来了"），trap.py 做陷阱结论（"这是机构故意设的陷阱"）

2. 扫止损陷阱(Stop Run Trap):
   - 价格快速穿越明显 swing point（人人放止损的位置）
   - 穿越后立即反转（留长影线或吞没形态）
   - 常见于 High/Low 1/2 的触发位置
   → 陷阱方向: 与穿越方向相反

3. 高潮反转陷阱(Climax Reversal Trap):
   - 异常大实体 K 线（实体 > 均值的 2 倍 ATR）
   - 伴随成交量异常放大（> 20 日均量 2 倍）
   - 下一根 K 线立即反向吞噬高潮 K 线的 50%+
   → 陷阱方向: 与高潮方向相反

4. 窄区间陷阱(Barbwire Trap):
   - 铁丝网结束时向一个方向突破
   - 但突破无后续动能（阳线后接阴线/小实体）
   → 陷阱方向: 与首次突破方向相反
```

**函数签名：**
```python
def detect_fake_breakout_trap(df: pd.DataFrame, key_levels: dict) -> Optional[dict]:
    """返回 {trap_direction, entry_bar, stop_level, confidence} """

def detect_stop_run_trap(df: pd.DataFrame, swing_points: dict) -> Optional[dict]:
    """返回 {trap_direction, run_bar, reversal_bar, confidence} """

def detect_climax_trap(df: pd.DataFrame) -> Optional[dict]:
    """返回 {trap_direction, climax_bar, reversal_bar, confidence} """

def detect_barbwire_trap(df: pd.DataFrame) -> Optional[dict]:
    """返回 {trap_direction, breakout_bar, failure_confirmation} """

def detect_all_traps(df: pd.DataFrame, key_levels: dict, swing_points: dict) -> list:
    """返回所有检测到的陷阱 [{type, direction, confidence}, ...] """
```

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M3-OUT-01 | `patterns/high_low.py` | High/Low 计数系统 |
| M3-OUT-02 | `patterns/signal_bar.py` | 信号K线识别 |
| M3-OUT-03 | `patterns/reversal.py` | 反转形态 |
| M3-OUT-04 | `patterns/range.py` | 区间形态 |
| M3-OUT-05 | `patterns/trap.py` | **【新增】** 陷阱识别 |
| M3-OUT-06 | `utils/indicators.py`(更新) | 新增 swing point 函数 |
| M3-OUT-07 | `test/test_patterns.py` | 形态识别单元测试 |

### M3 验收标准
- [ ] High/Low 计数在已知趋势数据上计数正确
- [ ] 信号K线分类（趋势K线/Doji/内包/外包）准确率 >= 80%
- [ ] 楔形识别：在 100 只人工标注含楔形的样本上，召回率 >= 70%、精确率 >= 60%
- [ ] 双顶/双底识别：在标准形态样本上召回率 >= 70%、精确率 >= 60%
- [ ] 区间边界识别在明显区间结构上偏差 < 5%
- [ ] **陷阱识别在假突破/扫止损/高潮反转样本上至少识别 3 类**
- [ ] 单只股票全形态扫描耗时 < 0.2s

---

## M4: 策略层

### 目标
基于 M2（市场状态）和 M3（形态识别）的输出，生成具体的买卖信号和选股清单。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M4-IN-01 | M2 状态分类结果（含趋势日类型） | M2-OUT-01 (Always-In 方向) + M2-OUT-03 (趋势强度) + M2-OUT-07 (趋势日类型) |
| M4-IN-02 | M3 形态识别结果 | M3-OUT-01~05（各形态模块输出列表） |
| M4-IN-03 | 全 A 股日线 | M1-OUT-01/02 |
| M4-IN-04 | 策略概念映射 | concept_map.md §策略部分 |
| M4-IN-05 | 大盘 Always-In 状态 | M2-OUT-01 |

**全市场扫描范围：** 全 A 股（含沪深主板、创业板、科创板、北交所），排除 ST/*ST、上市不足 60 个交易日的新股。若遇 Tushare 限频，按市值降序分批扫描，优先覆盖流动性好的股票。

### 处理流程

```
大盘状态 + 个股状态 + 个股形态
        ↓
【第一步】趋势日类型判定 (来自 M2 trend_day_classifier)
        ↓
【第二步】根据趋势日类型选择主策略:
  小回调趋势日 → 只顺势, 不等回调, 宽止损
  尖刺+通道趋势日 → Spike阶段追, 通道回调入
  趋势性区间日 → 双向剥头皮 + 测量目标反转
  趋势恢复日 → 横盘期布局, 尾盘突破跟进
  反转日 → 识别高潮, 等反转确认后入场
  宽通道/楼梯日 → 双向 + 倾向顺势部分持仓
  开盘趋势日 → 早盘快速判定, 全天持有
        ↓
【第三步】策略信号生成 (主策略优先, 其他辅助)
  趋势跟随策略 → 信号+置信度
  区间交易策略 → 信号+置信度
  反转交易策略 → 信号+置信度
        ↓
【第四步】信号融合 (Confluence评分 + 权重分配)
        ↓
全市场扫描 → 排序 → Top N 选股
        ↓
输出: [{stock, direction, trend_day_type, primary_strategy, 
        confidence, entry, stop, target}]
```

### 详细任务

#### 4.1 趋势跟随策略 — `strategies/trend_following.py`

| 子策略 | 触发条件 | 入场 | 止损 | 目标 |
|--------|---------|------|------|------|
| High 1 买入 | 强牛趋势 + Always-In Long + 第一次浅回调 + 信号K线确认 | 突破High 1高点Stop买入 | 回调低点下方 | 前波高点 |
| 通道回调买入 | 牛通道 + 回调至通道下轨/EMA20 + 牛信号K线 | Limit买入 | 通道下轨外1% | 通道上轨 |
| 突破回调买入 | 突破区间/前高 + 第一次回调 + 缩量企稳 | 突破回调高点Stop买入 | 突破位下方2% | 测量目标 |
| 迟到入场 | 强趋势中未上车 + 二次回调 | 同方向补回 | 信号K线外 | 与原位置相同 |

**函数签名：**
```python
def high1_buy_signal(df: pd.DataFrame, state: dict, patterns: dict) -> Optional[dict]:
    """返回 {entry_price, stop_loss, target, confidence} 或 None """

def channel_pullback_signal(df: pd.DataFrame, state: dict) -> Optional[dict]:
    """返回 {entry, stop, target, confidence} 或 None """

def breakout_pullback_signal(df: pd.DataFrame, patterns: dict) -> Optional[dict]:
    """返回 {entry, stop, target, confidence} 或 None """

def trend_following_signals(df: pd.DataFrame, state: dict, patterns: dict) -> list:
    """返回所有有效的趋势跟随信号 [{...}, ...] """
```

#### 4.2 区间交易策略 — `strategies/range_trading.py`

| 子策略 | 触发条件 | 入场 | 止损 | 目标 |
|--------|---------|------|------|------|
| 区间边界买入 | 区间底部 + 牛信号K线 + 缩量 | Limit买入 | 区间底外2% | 区间顶部 |
| 区间边界卖出 | 区间顶部 + 熊信号K线 + 缩量 | Limit卖出 | 区间顶外2% | 区间底部 |
| 突破失败反向 | 突破后快速回区间 + 假突破确认 | 反向Stop入场 | 突破极值外 | 区间另一侧 |
| 双底线买入 | 二次探底 + 第二底不破 + 反弹 | 突破颈线买入 | 第二底下 | 形态高度 |

**函数签名：**
```python
def range_boundary_signal(df: pd.DataFrame, boundary: dict) -> Optional[dict]:
    """返回 {direction, entry, stop, target} """

def fake_breakout_reversal(df: pd.DataFrame, breakout: dict) -> Optional[dict]:
    """返回 {direction, entry, stop, target} """

def range_trading_signals(df: pd.DataFrame, boundary: dict, patterns: list) -> list:
    """返回所有区间交易信号 [{...}, ...] """
```

#### 4.3 反转交易策略 — `strategies/reversal.py`

| 子策略 | 触发条件 | 入场 | 止损 | 目标 |
|--------|---------|------|------|------|
| 楔形反转 | 三推动能衰减 + 趋势线突破 + 收盘在外 | 突破趋势线Stop入场 | 楔形极值外 | 楔形起点 |
| 双顶/底反转 | 二次测试失败 + 反转K线 | 突破颈线入场 | 顶/底外 | 等距测量 |
| 趋势线突破 | 趋势线被穿越 + 信号K线确认 | 回调至趋势线Limit | 趋势线外 | 前高/低 |

**函数签名：**
```python
def wedge_reversal_signal(df: pd.DataFrame, wedge: dict) -> Optional[dict]:
    """返回 {direction, entry, stop, target} """

def double_top_bottom_signal(df: pd.DataFrame, pattern: dict) -> Optional[dict]:
    """返回 {direction, entry, stop, target} """

def trendline_break_signal(df: pd.DataFrame) -> Optional[dict]:
    """返回 {direction, entry, stop, target} """
```

#### 4.4 信号融合 — `strategies/fusion.py`

**融合逻辑：**
```
Confluence 评分:
  1. 同一股票同时出现多个策略信号 → 加分 (+1 per extra signal)
  2. 方向一致 + 共振 → 高置信度
  3. 大盘状态与信号方向一致 → 加分
  4. 信号K线质量 A/B/C → 分别 1.0/0.7/0.4 乘数

最终排序:
  score = sum(各策略置信度 × 策略权重 × 大盘乘数)
  Top N 选股

**策略权重定义**（初始等权，M6 回测校准）：
  - 趋势跟随策略权重 = 0.30（信号密度高，盈亏比好）
  - 区间交易策略权重 = 0.25（区间占 70% 时间，但胜率较低）
  - 反转交易策略权重 = 0.20（信号稀缺，但盈亏比最高）
  - 陷阱信号加分权重 = 0.25（独立加分项，不与上述争权重）
  M6 阶段按策略贡献度（信号频率 × 胜率 × 盈亏比）重新校准。
```

**函数签名：**
```python
def confluence_score(signals: list, market_state: dict) -> float:
    """返回综合评分 (0.0 ~ 1.0) """

def rank_stocks(all_signals: dict, market_state: dict, top_n: int = 5) -> pd.Series:
    """返回排名后的股票列表 + 分数 """
```

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M4-OUT-01 | `strategies/trend_following.py` | 4个子策略 |
| M4-OUT-02 | `strategies/range_trading.py` | 4个子策略 |
| M4-OUT-03 | `strategies/reversal.py` | 3个子策略 |
| M4-OUT-04 | `strategies/fusion.py` | 信号融合 + 排名 |
| M4-OUT-05 | `test/test_strategies.py` | 策略单元测试 |

### M4 验收标准
- [ ] 每个子策略在满足条件时返回信号，不满足时返回 None
- [ ] 对已知历史数据，策略能复现原始交易逻辑（以 5 只已知股票的历史走势为用例，对比人工标注的入场点：方向一致率 >= 70%、入场偏差 < 5 根 K 线）
- [ ] 信号融合排名在 Top 5 股票上至少有 2 个信号源确认
- [ ] 全市场扫描（3000+只）耗时 < 30s

---

## M5: 风控执行层

### 目标
对 M4 的选股信号施加风控约束，输出最终可执行的仓位建议。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M5-IN-01 | M4 选股信号列表 | M4-OUT-04 (fusion.py 排名结果) + M4-OUT-01~03 (策略原始信号) |
| M5-IN-02 | 个股日线 + 状态 | M1-OUT-01/02 |
| M5-IN-03 | A股适配规则 | ashare_adaptation.md |
| M5-IN-04 | 交易者方程参数 | concept_map.md |

### 处理流程

```
选股信号
    ↓
T+1适配检查: 入场标准 ≥ 70%? 尾盘禁开仓? 
    ↓
涨跌停检查: 涨停板? 炸板风险? 
    ↓
仓位计算: 交易者方程 → 凯利变体
    ↓
止损设置: 信号K线外1tick → 保本 → 追踪
    ↓
输出: {股票, 方向, 仓位%, 入场价, 止损价, 目标价, 置信度}
```

### 详细任务

#### 5.1 【新增】交易者方程实时计算 — `risk/trader_equation.py`

**Brooks 核心数学：** P(win) × Reward > P(loss) × Risk — 每笔交易都应通过此方程过滤。

**算法：**
```
Trader's Equation 实时计算:
  1. 输入:
     - 信号K线质量 (A/B/C → 对应不同胜率基线)
     - 策略历史胜率 (来自信号反馈)
     - 当前止损距离 (入场价 → 止损价)%
     - 目标距离 (入场价 → 目标价)%
  
  2. 计算:
     Win_Rate = base_win_rate × signal_quality_adjustment × market_state_adjustment
     Reward_Ratio = target_distance / stop_distance
     Expected_Value = Win_Rate × Reward_Ratio - (1 - Win_Rate) × 1
  
  3. 决策:
     Expected_Value > 0.3 → 高质量交易
     Expected_Value 0~0.3 → 合格, 降低仓位
     Expected_Value < 0 → 不交易
  
  4. 仓位调整:
     base_size = kelly_variant(Win_Rate, Reward_Ratio)
     final_size = base_size × account_multiplier × t_plus_1_multiplier
```

**函数签名：**
```python
def trader_equation_evaluate(
    signal_quality: str,        # "A" / "B" / "C"
    stop_pct: float,            # 止损百分比
    target_pct: float,          # 目标百分比
    market_multiplier: float,   # 市场状态乘数 (0.5~1.5)
    historical_win_rate: float = None  # 可选: 策略历史胜率
) -> dict:
    """返回 {expected_value, win_rate, reward_ratio, 
             position_multiplier, verdict: str}
    verdict: "high_quality" / "pass" / "reject"
    """

def position_size_from_te(
    te_result: dict,
    account_risk_pct: float = 0.02
) -> float:
    """基于交易者方程结果计算仓位百分比 """
```

#### 5.2 仓位管理 — `risk/position_sizing.py`

**Brooks 仓位公式（交易者方程应用）：**

```python
def position_size_by_trader_equation(
    confidence: float,       # 成功率 (0.0~1.0)
    avg_win_pct: float,      # 平均盈利%
    avg_loss_pct: float,     # 平均亏损%
    account_risk_pct: float, # 账户风险限额 (默认0.02)
    max_single_pct: float,   # 单票上限 (默认0.20)
    t_plus_1: bool = True    # T+1 下更保守
) -> float:
    """返回建议仓位百分比"""
```

**函数签名：**
```python
def kelly_variant(win_rate: float, win_loss_ratio: float) -> float:
    """凯利变体 (Brooks保守版: 半凯利 + 上限截断) """

def max_position_per_market_state(state: str, trend_strength: str) -> float:
    """根据市场状态返回最大仓位限制 """
```

#### 5.3 止损规则 — `risk/stop_loss.py`

```python
def initial_stop(signal_bar: dict, direction: str, buffer_tick: float = 0.01) -> float:
    """初始止损: 信号K线外1 tick """

def breakeven_stop(entry_price: float, current_price: float, risk_amount: float) -> Optional[float]:
    """保本移动: 盈利 >= 风险额时移动到入场价 """

def trailing_stop(current_price: float, highest_price: float, trail_pct: float = 0.05) -> float:
    """追踪止损: 从最高点回落 % """
```

#### 5.4 T+1 适配 — `risk/t_plus_1.py`

```python
def is_t_plus_1_allowed(signal: dict, current_time: str) -> bool:
    """T+1 入场限制检查:
    - 成功率 < 70% → 禁止入场 (标准提高)
    - 时间 > 14:30 (A股收盘前30分) → 禁止新开仓
    - 过夜仓位 > 20% 账户 → 禁止加仓
    """

def t_plus_1_stop_adjustment(stop_price: float, entry_price: float) -> float:
    """T+1 止损放宽: 给次日低开留空间 """
```

#### 5.5 涨跌停适配 — `risk/price_limit.py`

```python
def is_limit_up(code: str, price: float, df: pd.DataFrame) -> bool:
    """判断是否涨停"""

def is_limit_down(code: str, price: float, df: pd.DataFrame) -> bool:
    """判断是否跌停"""

def limit_up_breakout_confirmation(df: pd.DataFrame) -> dict:
    """涨停板突破确认:
    - 封板时间 (早盘封板 > 尾盘封板)
    - 封单量 (需 > 前日成交量的 20%)
    - 是否开板 (开板=假突破)
    """

def price_limit_signal_quality(df: pd.DataFrame) -> str:
    """涨停/跌停信号质量评级: HIGH/MEDIUM/LOW """
```

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M5-OUT-01 | `risk/trader_equation.py` | **【新增】** 交易者方程实时计算 |
| M5-OUT-02 | `risk/position_sizing.py` | 仓位管理 |
| M5-OUT-03 | `risk/stop_loss.py` | 止损规则 |
| M5-OUT-04 | `risk/t_plus_1.py` | T+1 适配 |
| M5-OUT-05 | `risk/price_limit.py` | 涨跌停适配 |
| M5-OUT-06 | `test/test_risk.py` | 风控单元测试 |

### M5 验收标准
- [ ] T+1 规则在尾盘时段正确拦截新开仓信号
- [ ] 仓位输出在 0% ~ 20% 之间（单票上限）
- [ ] 止损价 = 信号K线外 1%（可配置）
- [ ] 涨跌停检测准确率 >= 95%

---

## M6: 回测系统（5天）

### 目标
对 M1-M5 的完整策略管线做 2018-2026 历史回测，验证策略有效性。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M6-IN-01 | M1-M5 全部模块 | M1~M5 Outputs |
| M6-IN-02 | 全A股日线 2017-2026 | M1-OUT-01/02 |
| M6-IN-03 | 沪深300日线 (基准) | M1-OUT-01 |
| M6-IN-04 | 交易费率配置 | project_charter.md |
| M6-IN-05 | 准我回测引擎参考 | D:\ClaudeWorkspace\zhunwo\backtest\engine.py |

### 处理流程

```
M1-M5 管线
    ↓
逐日推进: 数据→状态→形态→策略→风控→信号
    ↓
T+1/涨跌停约束模拟
    ↓
交易记录 → 净值曲线
    ↓
绩效计算 → 按市场状态分组分析
    ↓
回测报告 (Markdown + JSON)
```

### 详细任务

#### 6.1 回测引擎 — `backtest/engine.py`

与准我回测引擎不同，价格行为学回测需要：
- 基于日线逐日推进（不是月度调仓）
- 信号可能在任意交易日出现
- High/Low 计数需要历史K线上下文
- 多策略信号融合

```python
class PriceActionBacktest:
    """价格行为学回测引擎
    
    前视偏差防护规则:
      - 所有需要"确认K线"的信号（两棒反转、陷阱确认等），
        入场必须在确认K线的次日
      - 回测引擎已内置此约束，无需手动检查
    """
    
    def __init__(self, config: dict):
        ...
    
    def run(self, stock_pool: list, start: str, end: str) -> dict:
        """逐日推进全流程 """
    
    def _daily_step(self, date: str):
        """每日: 更新状态 → 检查持仓 → 检查新信号 → 执行 """
    
    def _check_existing_positions(self):
        """持仓管理: 止损/止盈/持仓到期 """
    
    def _evaluate_new_signals(self):
        """全市场扫描 → 信号融合 → 选股 """
```

#### 6.2 绩效评估 — `backtest/performance.py`

```python
def compute_performance(equity_curve: pd.Series, trades: pd.DataFrame) -> dict:
    """收益率/夏普/最大回撤/胜率/盈亏比 """

def performance_by_market_state(equity_curve: pd.Series, 
                                 state_series: pd.Series) -> dict:
    """按市场状态分组绩效 (趋势日 vs 区间日 vs 反转日) """

def performance_by_pattern(trades: pd.DataFrame) -> dict:
    """按策略/形态分组绩效 """
```

#### 6.3 参数优化 — `backtest/optimizer.py`

```python
def optimize_stop_loss(engine, param_range: list) -> pd.DataFrame:
    """止损幅度敏感性测试 """

def optimize_signal_threshold(engine, param_range: list) -> pd.DataFrame:
    """信号置信度阈值优化 """
```

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M6-OUT-01 | `backtest/engine.py` | 回测引擎 |
| M6-OUT-02 | `backtest/performance.py` | 绩效评估 |
| M6-OUT-03 | `backtest/optimizer.py` | 参数优化 |
| M6-OUT-04 | `results/bt_report.md` | 回测报告 |
| M6-OUT-05 | `results/bt_report.json` | 回测数据 |
| M6-OUT-06 | `results/bt_equity.csv` | 净值曲线 |
| M6-OUT-07 | `results/bt_trades.csv` | 交易记录 |

### M6 验收标准
- [ ] 回测引擎在 2018-2026 区间可完整跑通（定义：覆盖至少 200 只股票，无未捕获异常导致中断，输出全部 7 个交付物文件）
- [ ] 净值曲线/交易记录/绩效指标完整输出
- [ ] 费率（佣金+印花税+滑点）已计入
- [ ] T+1 约束在回测中生效
- [ ] 涨跌停约束在回测中生效
- [ ] 前视偏差防护规则已通过单元测试验证

---

## M6.5: 集成冒烟测试【新增】

### 目标
在全周期回测前，用有限数据跑通全管线，提前暴露模块间交互 Bug（6 层架构、20+ 模块的总装风险）。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M6.5-IN-01 | M1-M6 全部模块 | M1~M6 Outputs |
| M6.5-IN-02 | 2024-01 月份全 A 股日线 | M1-OUT-01/02 |

### 处理流程

```
选取 2024-01 月 + Top 200 市值股票
    ↓
L1: 数据加载 → 检查缓存命中率和数据完整性
    ↓
L2: 状态分类 → 检查 Always-In 非空率 (> 80%)
    ↓
L3: 形态识别 → 检查各形态检出率 (不应全为 0)
    ↓
L4: 策略信号 → 检查信号生成率 (> 0 即可)
    ↓
L5: 风控过滤 → 检查过滤率和仓位分布
    ↓
L6: 输出 → 检查输出格式完整性
    ↓
冒烟测试报告: PASS/FAIL + 异常清单
```

### 详细任务

```python
class SmokeTest:
    """全管线冒烟测试 """
    
    def __init__(self, date_range: tuple, stock_pool: list):
        self.start, self.end = date_range
        self.stock_pool = stock_pool[:200]  # Top 200
    
    def run_all(self) -> dict:
        """串行跑通 L1→L6，记录每层通过率 """
    
    def _test_l1(self) -> dict:
        """数据层: 缓存命中率 >= 80% """
    
    def _test_l2(self) -> dict:
        """状态层: Always-In 非空率 >= 80% """
    
    def _test_l3(self) -> dict:
        """形态层: 至少 3 种形态有非零检出 """
    
    def _test_l4(self) -> dict:
        """策略层: 信号生成率 > 0 """
    
    def _test_l5(self) -> dict:
        """风控层: 过滤后至少保留 1 条信号 """
```

### 验收标准
- [ ] 各层通过冒烟检查（L1 数据完整性、L2 Always-In 非空率、L3 形态检出、L4 信号生成、L5 风控过滤）
- [ ] 无 Python 运行时异常
- [ ] 冒烟测试报告中记录所有 WARN/FAIL
- [ ] 修复冒烟测试问题后才启动 M6 全周期回测

---

## M7: 集成与验证（3天）

### 目标
全管线集成，每日运行验证，与现有系统的交叉验证。

### 输入

| 编号 | 输入 | 来源 |
|------|------|------|
| M7-IN-01 | M1-M6 全部模块 | M1~M6 Outputs |
| M7-IN-02 | M0 需求文档 (验收标准) | M0-OUT-01 |
| M7-IN-03 | M6.5 冒烟测试报告 | M6.5-OUT-01 |
| M7-IN-04 | 准我系统选股结果（用于交叉验证） | D:\ClaudeWorkspace\zhunwo\ |
| M7-IN-05 | 郭睿系统选股结果（用于交叉验证） | D:\ClaudeWorkspace\GR_stock\ |

### 处理流程

```
M1-M6 模块集成 → pipeline.py
        ↓
每日全流程运行 (指定日期)
        ↓
输出验证 (信号质量/一致性)
        ↓
与准我/郭睿交叉验证
        ↓
项目复盘 → postmortem.md
```

### 详细任务

#### 7.1 全管线集成 — `pipeline.py`
```python
class PriceActionPipeline:
    """L1 → L6 全流程 """
    
    def run(date: str) -> dict:
        """执行完整分析 """
    
    def _state_layer(self) -> dict:
        """M2: 大盘状态 + 个股状态 """
    
    def _pattern_layer(self) -> dict:
        """M3: 全市场形态识别 """
    
    def _strategy_layer(self) -> list:
        """M4: 信号生成 + 融合 """
    
    def _risk_layer(self) -> list:
        """M5: 风控过滤 + 仓位 """
```

#### 7.2 每日运行 — `run_daily.py`
```python
def run_daily(date: str = None) -> dict:
    pipeline = PriceActionPipeline(date)
    result = pipeline.run()
    generate_daily_report(result)
    return result
```

#### 7.3 交叉验证
- 与准我系统的选股结果对比：信号方向一致性检查
- 与郭睿系统的市场状态对比：Always-In vs Wyckoff 阶段一致性
- 差异超过 30% 时标记分析

### 输出

| 编号 | 输出 | 说明 |
|------|------|------|
| M7-OUT-01 | `pipeline.py` | 主管线 |
| M7-OUT-02 | `run_daily.py` | 每日运行入口 |
| M7-OUT-03 | `docs/postmortem.md` | 项目复盘 |
| M7-OUT-04 | `results/smoke_test_report.md` | 冒烟测试报告 |

### M7 验收标准
- [ ] `run_daily()` 可在 5 分钟内输出全市场分析结果
- [ ] 每日输出 ≤ 5 只选股，附带完整理由
- [ ] 与准我系统在趋势判定方向一致性 >= 60%
- [ ] 月均交易信号 < 3 时自动触发策略复审并输出复审报告
- [ ] 项目复盘记录至少 3 条经验教训
