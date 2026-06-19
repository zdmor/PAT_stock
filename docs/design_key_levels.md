# P1.2a 水平关键位检测 — 设计文档

> **冻结状态：** CRD-04 | M1.5 校准完成, 2026-06-14 已冻结。后续变更须经审查流程。
>
> 文件: `D:\ClaudeWorkspace\price_action_trading\docs\design_key_levels.md`
> 实现文件: `D:\ClaudeWorkspace\price_action_trading\patterns\key_levels.py`
> 关联: P1.2b 极性切换 (polarity), P1.2c 假突破检测 (fakeout)
> 模块位置: L3 形态识别引擎, 区间形态之前置依赖

---

## 1. 模块概览

### 1.1 用途

从日线 OHLC 数据中, 基于 swing high/low 聚类, 自动检测水平支撑位和阻力位。

这些水平关键位是后续模块的基础输入:
- M3.4 区间边界识别 (`patterns/range.py`)
- M3.6 陷阱识别 (`patterns/trap.py`)
- M3.2 信号K线质量评级 (`patterns/signal_bar.py`)
- M4.2 区间交易策略 (`strategies/range_trading.py`)

### 1.2 与 `patterns/range.py` 的区别

| 模块 | 职责 | 输出 |
|------|------|------|
| `key_levels.py` (本模块) | 纯水平价位聚类, 不判断区间 | 原始关键价位列表 |
| `range.py::identify_range_boundary()` | 基于关键位选出当前区间边界 | 一对支撑/阻力 + 清晰度 |

`key_levels.py` 做底层检测, `range.py` 做高层语义解析。`key_levels.py` 输出供 `range.py`、`trap.py`、`reversal.py` 等模块共享。

### 1.3 文件位置

```
D:\ClaudeWorkspace\price_action_trading\patterns\key_levels.py
```

---

## 2. 输入规范

### 2.1 DataFrame 要求

```python
df: pd.DataFrame
# 必须列: open, high, low, close
# 可选列: vol (成交量, 供强度评分扩展)
# 索引: 无要求 (内部用 iloc)
# 最小行数: 60 (左30+右30+余量, 基于默认 left=5, right=5 的 swing 检测)
```

### 2.2 Swing 点检测输入

复用 `utils/indicators.py` 的现有函数:

```python
from utils.indicators import swing_high, swing_low

sh_mask = swing_high(df, left=5, right=5)   # pd.Series[bool]
sl_mask = swing_low(df, left=5, right=5)     # pd.Series[bool]
```

当前实现使用 `center=True` 滚动窗口, 返回与 `df` 等长的 bool Series。

### 2.3 最小数据量

- **绝对最小**: 30 根 K 线 (刚好覆盖一次 swing 检测窗口)
- **推荐最小**: 120 根 K 线 (约 6 个月 A 股交易日, 得到有统计意义的聚类)
- **低于 30 根**: 返回空列表, 不报错

---

## 3. 输出规范

### 3.1 核心数据结构

```python
@dataclass
class KeyLevel:
    level_price: float          # 聚类中心价 (均值或中位数)
    price_min: float            # 聚类内最低价
    price_max: float            # 聚类内最高价
    strength: int               # 触碰次数 (swing 点数 + 日常触碰)
    swing_count: int            # 聚类中包含的 swing 点数
    touch_count: int            # 全部触碰次数 (用 ATR 缓冲带判定, 含非 swing 触碰)
    recency_weighted_strength: float  # 考虑时效加权的强度分
    both_sides: bool            # 是否从两侧被测试过
    first_date: str             # 首次触碰日期 YYYYMMDD
    last_date: str              # 最近触碰日期 YYYYMMDD
    cluster_prices: list        # 聚类中所有 swing 点价格
    formation_type: str         # "swing_high_cluster" / "swing_low_cluster" / "mixed" — 形成方式，不是当前市场角色

    # P1.2b stub — 极性切换历史
    polarity_flips: list        # [{date, from, to}, ...] (v0 为空)

    # P1.2c stub — 假突破标记
    fakeout_history: list       # [{date, direction, confirmation}, ...] (v0 为空)
```

### 3.2 函数签名

```python
def detect_key_levels(
    df: pd.DataFrame,
    swing_window: int = 5,
    cluster_tolerance: float = 0.015,
    min_touch: int = 2,
    max_levels: int = 10,
    recency_half_life: int = 60,
) -> tuple[list[KeyLevel], dict]:
    """检测水平关键位

    Args:
        df:                OHLC DataFrame
        swing_window:      swing 检测左右窗口
        cluster_tolerance: 聚类容差 (价格比例, 默认 1.5%)
        min_touch:         最小触碰次数 (低于此值被过滤)
        max_levels:        返回的最大 level 数 (按强度排序)
        recency_half_life: 时效半衰期 (K线数)

    Returns:
        (levels, metadata)
        levels: list[KeyLevel] — 检测到的关键位
        metadata: dict — {swing_count, swing_density, quality_warning, total_bars}
    """

def key_levels_summary(levels: list[KeyLevel], price_current: float) -> str:
    """生成人类可读的摘要

    格式示例:
    ┌ 关键位 (按强度降序, 当前价 15.32)
    │ R3  15.80 - 15.95  强度 5  最近 2026-06-01  两侧测试
    │ R2  15.55 - 15.60  强度 3  最近 2026-05-20
    │ R1  15.40 - 15.45  强度 4  最近 2026-06-05  ⚡ 最近高频
    │ ── 当前价 15.32 ──
    │ S1  15.10 - 15.20  强度 6  最近 2026-06-08  ⚡ 两侧测试
    │ S2  14.80 - 14.90  强度 2  最近 2026-04-15
    │ S3  14.55 - 14.60  强度 3  最近 2026-05-10
    └
    """
```

### 3.3 附加辅助函数

```python
def levels_near_price(levels: list[KeyLevel], price: float, 
                      threshold: float = 0.01) -> list[KeyLevel]:
    """返回当前价附近 threshold (1%) 范围内的关键位"""

def nearest_level(levels: list[KeyLevel], price: float) -> Optional[KeyLevel]:
    """返回离当前价最近的关键位"""

def level_touch_timeline(level: KeyLevel, df: pd.DataFrame) -> pd.Series:
    """返回该关键位在 DataFrame 中每次被触碰的 bool Series"""
```

---

## 4. 算法细节

### 4.1 Swing 点识别

复用 `utils/indicators.swing_high()` / `swing_low()`。

补充处理:
```python
# 从 bool mask 提取 (index, price) 对
swing_highs = [(i, df.loc[i, "high"]) for i in sh_mask[sh_mask].index]
swing_lows  = [(i, df.loc[i, "low"])  for i in sl_mask[sl_mask].index]
```

对边界的处理:
- 数据前 `left` 行和后 `right` 行必定为 False (`center=True` 滚动窗口)
- 不填充边界值, 避免引入不可靠的 swing 点

Swing 点质量检查:
```python
total_bars = len(df)
swing_count = len(swing_highs) + len(swing_lows)
swing_density = swing_count / total_bars

quality_warning = None  # 默认无警告
if swing_density > 0.20:   # 每 5 根 K 线就有一个 swing → 密度过高
    quality_warning = "high_density"
elif swing_count < 3:      # 整个数据区间不到 3 个 swing → 密度过低
    quality_warning = "low_density"

# 当 quality_warning 非 None 时：
# - 记录到返回结果中
# - 不阻断执行（下游用 quality_warning 自行决定是否信任）
```

### 4.2 聚类算法

聚类是整个模块的核心。步骤如下:

#### Step 1: 合并所有 swing 点

```python
points = []  # [(index, price, type)]
for idx in sh_idx:
    points.append((idx, df.loc[idx, "high"], "high"))
for idx in sl_idx:
    points.append((idx, df.loc[idx, "low"], "low"))

# 按价格排序
points.sort(key=lambda x: x[1])  # 按 price 升序
```

#### Step 2 — 一次扫描聚类（使用价格自适应容差）

```python
MIN_ABSOLUTE_TOLERANCE = 0.10  # 元, 保护低价股

clusters = []
current = [points[0]]  # 当前聚类中的点

for p in points[1:]:
    # 计算当前聚类均值
    cluster_mean = mean([pt[1] for pt in current])
    adaptive_tolerance = max(cluster_tolerance * cluster_mean, MIN_ABSOLUTE_TOLERANCE)

    # 条件: EITHER 相对距离 < 1.5% OR 绝对距离 < 0.10 元 — 两者任一满足即合并
    if abs(p[1] - cluster_mean) / cluster_mean < cluster_tolerance or \
       abs(p[1] - cluster_mean) < MIN_ABSOLUTE_TOLERANCE:
        current.append(p)
    else:
        # 保存当前聚类, 开始新聚类
        clusters.append(current)
        current = [p]

clusters.append(current)  # 最后一个
```

**自适应逻辑:**
```
tolerance_price = max(cluster_tolerance * mean_price, MIN_ABSOLUTE_TOLERANCE)

其中:
  cluster_tolerance = 0.015 (1.5%, 可配置)
  MIN_ABSOLUTE_TOLERANCE = 0.10 元 (固定值, 保护低价股)
  mean_price = 当前聚类中点的平均价格
```

合并条件: **EITHER** 相对距离 < 1.5% (cluster_tolerance) **OR** 绝对距离 < 0.10 元 — 两者任一满足即合并。这确保了高价股（如茅台 ~1500）使用 1.5% 容差（22.5 元），而低价股（如工行 ~5）使用 0.10 元保底容差，避免 300x 的绝对容差差异。

#### Step 2b — 第二遍合并近邻 cluster

    # 检查相邻 cluster 的中心距离，如果 < cluster_tolerance 则合并
    i = 0
    while i < len(clusters) - 1:
        center_i = mean(clusters[i] prices)
        center_next = mean(clusters[i+1] prices)
        if abs(center_next - center_i) / center_i < cluster_tolerance:
            # 合并两个 cluster
            clusters[i] = clusters[i] + clusters[i+1]
            del clusters[i+1]
        else:
            i += 1

#### Step 3: 过滤不足够的聚类

```python
# 过滤掉只有 1 个 swing 点的聚类 (除非 min_touch=1)
clusters = [c for c in clusters if len(c) >= min_touch]
```

#### Step 4: 计算聚类统计量

```python
for c in clusters:
    prices = [pt[1] for pt in c]
    indices = [pt[0] for pt in c]
    types = [pt[2] for pt in c]  # "high" / "low"

    level = KeyLevel(
        level_price=np.mean(prices),  # 均值
        price_min=min(prices),
        price_max=max(prices),
        swing_count=len(c),
        # touch_count 需额外计算
        # recency_weighted_strength 需额外计算
        # both_sides 需额外计算
        ...
    )
```

### 4.3 强度评分

#### 触碰次数 (touch_count)

除了 swing 点计入, 还要计算价格在日常运行中"触达"该价位的次数:

```python
def count_touches(df: pd.DataFrame, level_price: float,
                  touch_buffer: float = 0.5, atr_series: pd.Series = None) -> int:
    """计算 K 线触达该价位的次数

    触碰判定: 如果 K 线的 high/low 范围与 level_price 的距离在 touch_buffer * ATR 以内，视为触碰。
    例如 touch_buffer=0.5, ATR=0.20 → 只要 low <= level_price + 0.10 且 high >= level_price - 0.10 即算触碰。

    如果 atr_series 不可用，退回到使用 cluster 半宽作为缓冲带。
    """
    touches = 0
    for i in range(len(df)):
        high = df.iloc[i]["high"]
        low = df.iloc[i]["low"]
        if atr_series is not None and not pd.isna(atr_series.iloc[i]):
            buffer = touch_buffer * atr_series.iloc[i]
        else:
            buffer = 0  # fallback: no buffer
        if low <= level_price + buffer and high >= level_price - buffer:
            touches += 1
    return touches
```

注: 当前实现使用逐行循环。数据量 < 5000 行时性能可接受（< 10ms）。
如后续需要优化可改为向量化实现：
    mask = (df["low"] <= level_price + buffer) & (df["high"] >= level_price - buffer)
    touches = mask.sum()

- 缓冲带使用 `touch_buffer * ATR` 作为动态范围 (默认 0.5 倍 ATR), 对应参数表中的 `touch_buffer_atr`
- 如果 ATR 不可用, 退回到 0 缓冲 (仅统计价格精确穿过 level_price 的 K 线)
- 如果触摸范围等于聚类自身范围, 则触碰计数 = 聚类内的原始 swing 点数

#### 时效加权 (recency_weighted_strength)

```
权重 = exp(-i / recency_half_life)

其中 i = 从该触碰位置到数据末尾的距离 (K 线数)
recency_half_life = 60 (约 3 个月 A 股交易日)

最近触碰权重 ~ 1.0
60 根前触碰权重 ~ 0.5
120 根前触碰权重 ~ 0.25
```

```python
def recency_weight(df_len: int, touch_index: int, half_life: int) -> float:
    bar_distance = df_len - 1 - touch_index
    return math.exp(-bar_distance / half_life)
```

#### 两侧测试 (both_sides)

```python
has_high_touch = any(pt[2] == "high" for pt in cluster)
has_low_touch = any(pt[2] == "low" for pt in cluster)
both_sides = has_high_touch and has_low_touch
```

两侧测试过的关键位强度加一档 (权重 x1.5)。

### 4.4 极性切换 (P1.2b stub)

设计接口, 当前只标记不实现:

```python
def track_polarity_flips(level: KeyLevel, df: pd.DataFrame) -> list:
    """P1.2b: 追踪该关键位的支撑↔阻力切换历史

    v0 返回空列表, 接口预留。
    设计思路:
      - 当价格从上方跌破关键位后, 该关键位从支撑变为阻力
      - 当价格从下方升破关键位后, 该关键位从阻力变为支撑
      - 记录每次切换的日期和方向
    """
    return []  # v0 stub
```

**P1.2b 完整实现 (未来):**
```
输入: KeyLevel + 后续 K 线数据
算法:
  1. 从该 level 首次出现后逐日跟踪
  2. 价格从下向上穿越 level → direction = "resistance→support" 
  3. 价格从上向下穿越 level → direction = "support→resistance"
  4. 连续穿越记录为切换序列
输出: [{date, flip_from, flip_to, breakout_confirm}]
```

### 4.5 假突破检测 (P1.2c stub)

```python
def detect_level_fakeout(level: KeyLevel, df: pd.DataFrame,
                         confirm_bars: int = 3) -> list:
    """P1.2c: 关键位假突破检测

    v0 返回空列表, 接口预留。
    设计思路:
      - 价格穿越关键位超过阈值 (例如 0.5% ATR)
      - 但随后 confirm_bars 内回到关键位另一侧
      - 穿越 K 线有长影线则置信度更高
    """
    return []  # v0 stub
```

**P1.2c 完整实现 (未来):**
```
输入: KeyLevel + OHLC + 参数
算法:
  1. 遍历每根 K 线, 检查是否"穿越"关键位
  2. 定义为: 
     - 阻力位穿越: high > level_price + buffer, 但 close < level_price
     - 支撑位穿越: low < level_price - buffer, 但 close > level_price
  3. 确认: 穿越后 confirm_bars 内收盘价仍回归原侧
  4. 附加信号: 穿越 K 线有上影线/下影线 > 实体 2 倍 → 高置信度
输出: [{date, direction, confidence, penetration_depth}]
```

---

## 5. 参数与默认值

| 参数 | 默认值 | 范围 | 含义 | 调整依据 |
|------|--------|------|------|---------|
| `swing_window` | 5 | 2-20 | swing 检测左右窗口宽度 | Brooks 默认 5, 日线可增大到 8-10 |
| `cluster_tolerance` | 0.015 | 0.005-0.05 | 聚类价格容差 (比例) | 1.5% 适中, 配合 min_absolute_tolerance 保护低价股 |
| `min_absolute_tolerance` | `0.10` | `0.02-0.50` | 最低绝对容差（元），保护低价股 | 对 5 元以下股票必须 > tick 精度 |
| `min_touch` | 2 | 1-5 | 最小 swing 触碰次数 | 2=至少有 2 个 swing 点确认 |
| `max_levels` | 10 | 5-30 | 最多返回 level 数 | 人眼可处理的合理数量 |
| `recency_half_life` | 60 | 20-120 | 时效加权半衰期 (K线) | 60 ≈ 3 个月, A 股约一季 |
| `touch_buffer_atr` | 0.5 | 0.2-2.0 | 触碰判定的 ATR 倍数 | 0.5 倍 ATR 作为价格附近的缓冲带 |

参数配置位置: v0 直接写在函数默认参数中。M6 回测阶段改到 `config/defaults.py`。

---

## 6. 依赖

### 6.1 内部依赖

| 路径 | 用途 | 依赖类型 |
|------|------|---------|
| `utils/indicators` → `swing_high()`, `swing_low()` | Swing 点检测 | 强依赖, 必须 |
| `utils/indicators` → `atr()` | Touch buffer 计算 | 弱依赖, 无之可 fallback 到固定值 |
| `numpy` | `np.mean` 聚类均值 | 强依赖 |
| `dataclasses` | `KeyLevel` 数据结构 | 强依赖 |
| `math` | `math.exp` 时效加权 | 弱依赖, 可简单线性替代 |

### 6.2 无外部依赖

`math`, `numpy`, `dataclasses` 均为 Python 标准库。`pandas` 是项目全局依赖。

---

## 7. 测试方法

### 7.1 已知 S/R 股测试

挑选 A 股中长期横盘的标的, 人工验证关键位检测:

| 股票 | 代码 | 特征 | 预期 |
|------|------|------|------|
| 工商银行 | 601398.SH | 长期横盘, 支撑/阻力清晰 | 检测到明确水平位, 误差 < 2% |
| 长江电力 | 600900.SH | 长期慢牛, 逐级支撑 | 多个层级支撑位 |
| 贵州茅台 | 600519.SH | 高单价 (>1000), swing 幅度大 | 聚类容差应自适应 |

### 7.2 稳定性测试

```python
def test_level_stability():
    """关键位稳定性测试
    
    条件: 同一股票, 不同时间窗口应产生一致的关键位
    验证:
      - 窗口 2018-2026 vs 2019-2025: 关键位重叠率 >= 60%
      - 窗口 2018-2026 vs 2020-2023: 关键位重叠率 >= 40%
      - 新增数据 (滚动月度更新) 不应导致关键位大幅跳变
    """
```

### 7.3 回归测试

```python
def test_edge_cases():
    """边界条件测试
    - 空 DataFrame → 返回空列表
    - < 30 行 → 返回空列表
    - 所有价格相同 → 返回 1 个 level
    - 只有 2 个 swing 点且价格相距 10% → 返回 0 个 level (min_touch=2)
    - 高波动 (ATR 很大) vs 低波动 → 聚类的有效性
    """
```

### 7.4 人工验证流程

1. 在指定股票上运行 `detect_key_levels()`
2. 在 K 线图上叠加标注检测到的关键位
3. 人工评估: 关键位是否在合理位置? 有无明显遗漏? 有无明显误报?
4. 记录每个股票的: `{ts_code, levels_found, reasonable_rate, false_positive_rate}`

---

## 8. 集成到管线

### 8.1 管线编排位置

```
L1: data/loader.py → get_daily()
    ↓
L2: state/always_in.py → determine_always_in()
    ↓
L3: patterns/key_levels.py → detect_key_levels()    ← P1.2a 在此
    ↓
L3: patterns/range.py → identify_range_boundary()  ← 消费关键位
    ↓
L3: patterns/trap.py → detect_all_traps()           ← 消费关键位
```

### 8.2 pipeline.py 集成

```python
# pipeline.py 中的 _pattern_layer() 扩展

def _pattern_layer(self, df: pd.DataFrame) -> dict:
    """M3 形态识别层"""
    result = {}

    # P1.2a 水平关键位
    from patterns.key_levels import detect_key_levels
    levels, meta = detect_key_levels(df)
    result["key_levels"] = levels
    result["key_levels_meta"] = meta

    # 后续: high_low, signal_bar, reversal, range, trap
    ...
    return result
```

### 8.3 pipeline.py 中完整的函数编排

```python
def analyze_stock(df: pd.DataFrame) -> dict:
    """单股完整分析"""

    # P1.2a: 关键位
    levels, meta = detect_key_levels(
        df,
        swing_window=5,
        cluster_tolerance=0.015,
        min_touch=2
    )
    if meta.get("quality_warning"):
        logger.warning(f"Key level quality issue: {meta['quality_warning']}")

    # 区间边界
    boundary = identify_range_boundary(df, key_levels=levels)

    # 所有陷阱检测
    swing_points = {"highs": ..., "lows": ...}
    traps = detect_all_traps(df, key_levels=levels, swing_points=swing_points)

    return {
        "key_levels": levels,
        "key_levels_meta": meta,
        "boundary": boundary,
        "traps": traps,
        "summary": key_levels_summary(levels, df["close"].iloc[-1])
    }
```

### 8.4 与 `patterns/range.py` 的数据流

```
key_levels.py                          range.py
  detect_key_levels() ──levels[]──→  identify_range_boundary()
                                       ↑
                                       │ 从 levels 中选出:
                                       │  - 最近区间: swing high/low 密集区
                                       │  - 边界清晰度: 触碰最集中 + 两侧最清晰
                                       │
                                       │ 输出: {support, resistance, clarity_score}
```

---

## 9. Workbuddy Prompt

以下是可复制给 workbuddy 的完整实现提示词。

---

```
# Workbuddy 任务: 实现 P1.2a 水平关键位检测

## 背景

这是 PAT (Price Action Trading) 项目的 P1.2a 子任务。PAT 是基于 Al Brooks 价格行为学的 A 股交易系统。

本模块位于 L3 形态识别引擎, 检测水平支撑/阻力位, 作为区间边界识别和陷阱识别的前置依赖。

## 参考文件

- `D:\ClaudeWorkspace\price_action_trading\docs\design_key_levels.md` — 本文档, 完整设计
- `D:\ClaudeWorkspace\price_action_trading\utils\indicators.py` — 可复用 swing_high() / swing_low()
- `D:\ClaudeWorkspace\price_action_trading\docs\concept_map.md` — 概念映射 (R-A04 区间边界)
- `D:\ClaudeWorkspace\price_action_trading\docs\requirements.md` — 阶段需求 (§M3 形态识别)

## 实现文件

`D:\ClaudeWorkspace\price_action_trading\patterns\key_levels.py`

## 函数签名

```python
@dataclass
class KeyLevel:
    level_price: float
    price_min: float
    price_max: float
    strength: int
    swing_count: int
    touch_count: int
    recency_weighted_strength: float
    both_sides: bool
    first_date: str
    last_date: str
    cluster_prices: list
    formation_type: str  # "swing_high_cluster" / "swing_low_cluster" / "mixed"
    polarity_flips: list     # v0 stub → 空列表
    fakeout_history: list    # v0 stub → 空列表

def detect_key_levels(
    df: pd.DataFrame,
    swing_window: int = 5,
    cluster_tolerance: float = 0.015,
    min_touch: int = 2,
    max_levels: int = 10,
    recency_half_life: int = 60,
) -> tuple[list[KeyLevel], dict]:

def key_levels_summary(levels: list[KeyLevel], price_current: float) -> str:

def levels_near_price(levels: list[KeyLevel], price: float, threshold: float = 0.01) -> list[KeyLevel]:

def nearest_level(levels: list[KeyLevel], price: float) -> Optional[KeyLevel]:
```

## 输入格式

- `df`: pd.DataFrame, 必须包含列 high, low, close (日线)
- 最小行数: 30 (推荐 120+)
- swing 点检测复用 `utils.indicators.swing_high(df, left=swing_window, right=swing_window)` 和 `swing_low()` 的 bool Series

## 输出格式

返回 `tuple[list[KeyLevel], dict]`:
- `levels`: `list[KeyLevel]`, 按 `recency_weighted_strength` 降序排列
- `metadata`: `dict`, 包含 `{swing_count, swing_density, quality_warning, total_bars}`

`key_levels_summary()` 输出人类可读的文本格式:
```
┌ 关键位 (当前价 15.32)
│ R3  15.80 - 15.95  强度 5  最近 2026-06-01  两侧测试
│ R2  15.55 - 15.60  强度 3  最近 2026-05-20
│ R1  15.40 - 15.45  强度 4  最近 2026-06-05  ⚡ 最近高频
│ ── 当前价 15.32 ──
│ S1  15.10 - 15.20  强度 6  最近 2026-06-08  ⚡ 两侧测试
│ S2  14.80 - 14.90  强度 2  最近 2026-04-15
│ S3  14.55 - 14.60  强度 3  最近 2026-05-10
└
```

## 算法伪代码

```
1. Swing 点提取
   sh_mask = swing_high(df, left=swing_window, right=swing_window)
   sl_mask = swing_low(df, left=swing_window, right=swing_window)
   all_points = [(idx, df.high[idx], "high") for idx in sh_mask] +
                [(idx, df.low[idx], "low") for idx in sl_mask]
   按 price 排序

2. 聚类 (一次扫描)
   clusters = []
   current = [points[0]]
   for p in points[1:]:
       cluster_mean = mean(current prices)
       if abs(p.price - cluster_mean) / cluster_mean < cluster_tolerance:
           current.append(p)
       else:
           clusters.append(current)
           current = [p]
   clusters.append(last current)

3. 过滤
   clusters = [c for c in clusters if len(c) >= min_touch]

4. 统计计算 (对每个 cluster):
   4a. level_price = mean of cluster prices
   4b. swing_count = len(cluster)
   4c. touch_count = swing_count + 额外日常触碰到缓冲带的 K 线数
   4d. recency_weighted_strength = sum(exp(-dist/half_life) for each touch)
   4e. both_sides = 聚类中同时包含 high 点和 low 点
   4f. formation_type = "swing_low_cluster"(全是low点) / "swing_high_cluster"(全是high点) / "mixed"(混合)
   4g. first_date / last_date = 聚类中最早/最晚触碰的日期

5. 排序: 按 recency_weighted_strength 降序
6. 截断: 取前 max_levels 个
```

## 边界条件

1. **高/低单价股容差自适应** — 高价股（如茅台 ~1500）和低价股（如工行 ~5）使用统一 1.5% 比例容差会导致 300x 的绝对容差差异。v1 使用 `max(cluster_tolerance * mean_price, MIN_ABSOLUTE_TOLERANCE)` 自适应逻辑，条件 EITHER 相对距离 < 1.5% OR 绝对距离 < 0.10 元，任一满足即合并。高价股使用 1.5% 容差（~22.5 元 @ 1500），低价股使用 0.10 元保底容差（~2% @ 5 元）。
2. **空 DataFrame / 不足 30 行** → 返回 []
3. **无 swing 点** → 返回 [] (swing 检测在数据两端必然有 NaN)
4. **所有 swing 点价格相同** → 返回 1 个包含全部点的 cluster
5. **cluster 内仅 1 个点且 min_touch>=2** → 该 cluster 被过滤
6. **只有 2 个点但价格相距 10%** → 2 个独立 cluster, 每个 1 个点 → 被过滤
7. **价格恰好位于 cluster 边界上** → 使用 cluster 的 price_min~price_max 范围判断, 不硬截断
8. **同时同价位的 high 和 low 点 (十字星 swing)** → 计入 both_sides = True
9. **重复 level (两个 cluster 太接近)** → 同一价格附近不应有多个 level, 需要合并。v0 使用一次扫描+第二遍合并，相邻 cluster 在容差内会合并。

## 测试验证

### 人工验证

选以下 A 股验证:

```python
test_stocks = [
    "601398.SH",  # 工商银行 — 长期横盘, 预期有清晰 S/R
    "600900.SH",  # 长江电力 — 慢牛, 逐级支撑
    "600519.SH",  # 贵州茅台 — 高单价, swing 幅度大
]
```

对每只: 用近 2 年日线 → 检测关键位 → 在 K 线图上直观评估合理性

### 自动验证

```python
def test_basic():
    """基本功能测试"""
    df = ...  # 构建测试数据
    levels = detect_key_levels(df)
    assert isinstance(levels, list)
    assert all(isinstance(l, KeyLevel) for l in levels)

def test_empty_data():
    assert detect_key_levels(pd.DataFrame()) == []

def test_few_bars():
    df = pd.DataFrame({"high": [10]*20, "low": [9]*20, "close": [9.5]*20})
    assert detect_key_levels(df) == []

def test_one_level():
    """所有 swing 点都在同一价位"""
    # 构造 50 根 K 线, high=11, low=9, 中间有 3 个 swing high 在 11, 3 个 swing low 在 9
    levels = detect_key_levels(df)
    assert len(levels) >= 2

def test_stability():
    """不同起始日期的关键位稳定性"""
    df = get_daily("601398.SH", "20200101", "20260601")
    levels_1 = detect_key_levels(df)
    levels_2 = detect_key_levels(df.iloc[120:])  # 去掉前半
    # 重叠率 (关键位价格差 < 5%) >= 50%
    overlap_rate = compute_overlap(levels_1, levels_2)
    assert overlap_rate >= 0.5
```

## 输出断言

实现提交后确认:

1. [ASSERT] `detect_key_levels()` 返回 `tuple[list[KeyLevel], dict]`, levels 中每个元素是 KeyLevel 实例
2. [ASSERT] levels 按 recency_weighted_strength 降序
3. [ASSERT] 空 DataFrame 返回 `([], metadata)` 不抛异常
4. [ASSERT] < 30 行返回 `([], metadata)` 不抛异常
5. [ASSERT] `key_levels_summary()` 输出不含文件名、不含代码块标记、直接显示文本表格
6. [ASSERT] 至少 3 个测试用例通过 (basic、empty、stability)
7. [ASSERT] 对 601398.SH (工商银行) 近 2 年日线检测出至少 3 个关键位
```
