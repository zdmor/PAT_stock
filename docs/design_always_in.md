# P1.3 Always-In 结构判定设计文档

> **冻结状态：** CRD-02 | M1.5 校准完成, 2026-06-14 已冻结。reverse_sign 参数为设计文档未约束的运行时配置, 不触发冻结变更流程。
>
> 项目: PAT (Price Action Trading)
> 对应里程碑: M2.1 (M2 状态分类引擎 — 第一个子模块)
> 素材来源: Al Brooks — 趋势方向判定核心框架
> 文件: `state/market_state.py`
> 引用: concept_map.md T-A01, T-B01; project_charter.md §M2.1

---

## 目录

1. [Module Overview](#1-module-overview)
2. [Input Specification](#2-input-specification)
3. [Output Specification](#3-output-specification)
4. [Algorithm Details](#4-algorithm-details)
5. [Parameters and Defaults](#5-parameters-and-defaults)
6. [Dependencies](#6-dependencies)
7. [Testing Approach](#7-testing-approach)
8. [Integration](#8-integration)
9. [Workbuddy Prompt](#9-workbuddy-prompt)

---

## 1. Module Overview

### 1.1 Purpose

Always-In 是 Al Brooks 价格行为学的核心概念：**如果必须持有一个头寸且不能退出，当前应该做多还是做空？** 它不是交易信号，而是市场背景判定——决定"允许做什么方向的事"。

本模块基于 Brooks 的 5 维判定框架，将当前市场状态分为三类：

- **bullish** — 顺势方向向上，只考虑做多策略
- **bearish** — 顺势方向向下，只考虑做空策略
- **oscillating** — 无明显趋势方向，允许双向策略但需更严格确认

### 1.2 与 project_charter.md 的关系

| 原始规划 (project_charter.md §M2.1, requirements.md L342-348) | 本设计 |
|:---|---:|
| 5 维加权 (20缺口棒/高/低点结构/K线实体倾向/回调深度/均线位置) | 5 维加权 (EMA20斜率/高低点结构/通道位置/回调深度/缺口棒计数) |
| 权重 0.30/0.25/0.20/0.15/0.10 | 连续置信度 0-1 + 方向三元组 |
| 方向阈值 ±0.60 | 方向阈值 ±0.30 |
| `state/always_in.py` | `state/market_state.py` |

**设计理由:** 本设计对 project_charter.md/requirements.md 的原始维度做了三处替换：20缺口棒计数(0.30)→EMA20斜率(0.30)、K线实体倾向(0.20)→通道位置(0.20)、均线位置(0.10)→缺口棒计数(0.10)。理由详见审查报告 review_design_always_in_shu_2026-06-14.md §2.3。初始 3 维简化版将第 4 维(回调深度)和第 5 维(缺口棒计数)精简以控制过拟合。P2 阶段重新引入完整 5 维 (权重 0.30/0.25/0.20/0.15/0.10)，与 concept_map.md 约束一致，每一维有明确的 Brooks 理论基础且经验证无显著共线性。

### 1.3 文件位置

```
D:\ClaudeWorkspace\price_action_trading\state\market_state.py
```

与 `state/__init__.py` 配合，使其可通过 `from state import determine_always_in` 导入。

---

## 2. Input Specification

### 2.1 主入口参数

```python
def determine_always_in(
    df: pd.DataFrame,
    params: Optional[dict] = None
) -> dict:
```

### 2.2 DataFrame 要求

| 字段 | 类型 | 必须 | 说明 |
|------|------|:----:|------|
| `open` | float | 是 | 开盘价 |
| `high` | float | 是 | 最高价 |
| `low` | float | 是 | 最低价 |
| `close` | float | 是 | 收盘价 |
| `trade_date` | pd.Timestamp | 否 | 日期（用于索引对齐） |

### 2.3 数据约束

- **最少 bar 数: 30**（算法需要至少 30 根 K 线才有意义的 EMA20 和 swing 检测）
- **推荐 bar 数: 60+**（60 根以上才能稳定检测 HH/HL 结构和通道位置）
- **数据源:** `data/loader.get_daily()` 返回的 DataFrame
- **排序:** 必须按 `trade_date` 升序（时间从远到近）
- **前处理:** 不需要额外清洗，但需确保无 NaN open/high/low/close

### 2.4 params 参数覆盖

可选 dict, 支持覆盖[第 5 节](#5-parameters-and-defaults)的所有默认参数。

---

## 3. Output Specification

### 3.1 返回结构

```python
{
    "direction": "bullish",       # "bullish" | "bearish" | "oscillating"
    "confidence": 0.72,           # 0.0 ~ 1.0, 基于五维加权一致程度
    "structure": "HHHL",          # "HHHL" | "LHLL" | "mixed"
    "dimensions": {
        "ema_slope": {
            "score": 0.65,        # -1.0 ~ 1.0
            "direction": "bullish",
            "weight": 0.30
        },
        "hh_hl_structure": {
            "score": 0.80,
            "direction": "bullish",
            "weight": 0.25
        },
        "channel_position": {
            "score": -0.30,
            "direction": "bearish",
            "weight": 0.20
        },
        "retracement_depth": {
            "score": 0.20,
            "direction": "bullish",
            "weight": 0.15
        },
        "gap_bars": {
            "score": 0.30,
            "direction": "bullish",
            "weight": 0.10
        }
    },
    "params_used": {
        "ema_period": 20,
        "swing_lookback": 60,
        "slope_threshold": 0.3,
        "above_ema_threshold": 0.8,
        "retracement_lookback": 60,
        "gap_bar_saturation": 15
    }
}
```

### 3.2 字段说明

| 字段 | 类型 | 值域 | 说明 |
|------|------|------|------|
| `direction` | str | bullish/bearish/oscillating | 最终方向判定 |
| `confidence` | float | [0.0, 1.0] | 置信度 = min(abs(加权总分), 1.0) |
| `structure` | str | HHHL/LHLL/mixed | 高低点结构模式摘要 |
| `dimensions` | dict | — | 每维独立评分, 用于调试和下游置信度校准 |
| `params_used` | dict | — | 实际使用的参数值, 便于审计 |

### 3.3 方向判定规则

| 加权总分范围 | direction | 说明 |
|:---:|:---:|---|
| >= +0.30 | bullish | 五维一致看多或多维强看多 |
| <= -0.30 | bearish | 五维一致看空或多维强看空 |
| (-0.30, +0.30) | oscillating | 维度间冲突或均中性 |

### 3.4 structure 判定规则

| 条件 | structure |
|---|---|
| 最近 3-5 个 swing high 呈 HH + 最近 3-5 个 swing low 呈 HL | HHHL |
| 最近 3-5 个 swing high 呈 LH + 最近 3-5 个 swing low 呈 LL | LHLL |
| 其他组合 | mixed |

---

## 4. Algorithm Details

### 4.1 总体流程

```
df_in → [calc_ema20] → [calc_slope] → Dim1 ema_slope score
       → [detect_swing_points] → [analyze_hh_hl] → Dim2 hh_hl_structure score
       → [calc_channel_position] → Dim3 channel_position score
       → [calc_retracement_depth] → Dim4 retracement_depth score
       → [calc_gap_bars] → Dim5 gap_bars score
       → [weighted_combination] → {direction, confidence, structure}
```

### 4.2 Dimension 1 — EMA20 Direction & Slope (weight 0.30)

```
Input:  close series, ema_period=20, slope_lookback=5, slope_threshold=0.3%
Output: score ∈ [-1.0, 1.0]

Algorithm:
  1. ema = EMA(close, period=ema_period)
  2. 取最近 slope_lookback 根 bar 的 ema 值, 计算 per-bar diff:
     slope = (ema[-1] - ema[-N]) / N
  3. slope_pct = slope / ema[-1] * 100  (%)
  4. 判定:
     if slope_pct > +slope_threshold:  direction = bullish
     elif slope_pct < -slope_threshold: direction = bearish
     else:                              direction = neutral
  5. scale to score:
     normalized = slope_pct / (slope_threshold * 3)  # 3x 阈值处饱和
     score = clip(normalized, -1.0, 1.0)

Edge cases:
  - ema 不足 ema_period 根时: score=0, direction=oscillating
  - slope_lookback 不足 N 根时: 用可用长度
  - 极端 gap 导致 slope 突变: 不特殊处理, 以正常权重参与
```

**判定: 使用简单 diff 方案 (ema[-1] - ema[-n]) / n。**
**理由:**
1. diff 对近期变化更敏感, 符合 Always-In "当前"状态判定目标
2. 计算 O(1), 无额外依赖
3. polyfit 在大 swing 前后会滞后, 不如 diff 及时

如在实盘中发现 diff 过于敏感 (> 30% 的假方向切换), P2 再考虑换用 polyfit。

### 4.3 Dimension 2 — HH/HL Structure (weight 0.25)

```
Input:  df with high/low, swing_left=5, swing_right=5, swing_lookback=30
Output: score ∈ [-1.0, 1.0]

Algorithm:
  1. 计算 swing_high 和 swing_low (复用 indicators.py)
     swing_high_mask = swing_high(df, left=5, right=5)
     swing_low_mask  = swing_low(df, left=5, right=5)

  2. 从最近 swing_lookback 根 bar 中提取 swing points:
     recent_highs = df[swing_high_mask].tail(5)["high"].values  # 最近 5 个 swing high
     recent_lows  = df[swing_low_mask].tail(5)["low"].values    # 最近 5 个 swing low

  3. HH/HL/LH/LL 判定:
     highs_ascending = all(recent_highs[i] > recent_highs[i-1]
                           for i in range(1, len(recent_highs)))
     lows_ascending  = all(recent_lows[i] > recent_lows[i-1]
                           for i in range(1, len(recent_lows)))

     # 更鲁棒: 不要求 "全部" 递进, 用最后 3 个两两比较
     # 至少 2/3 对满足递进即视为 HH/HL

  4. 方向判定:
     if highs_ascending and lows_ascending:   # HH + HL = 强牛
         base_score = 0.8
         structure = "HHHL"
     elif not highs_ascending and not lows_ascending:  # LH + LL = 强熊
         base_score = -0.8
         structure = "LHLL"
     elif highs_ascending:    # HH + LL → 多头占优但低点在下移
         base_score = 0.3
         structure = "mixed"
     elif lows_ascending:     # LH + HL → 空头占优但高点在上移
         base_score = -0.3
         structure = "mixed"
     else:
         base_score = 0.0
         structure = "mixed"

  5. 置信度调整 (基于 swing point 数量):
     n_highs = len(recent_highs)
     n_lows  = len(recent_lows)
     confidence_mult = min((n_highs + n_lows) / 6, 1.0)  # 至少 6 个点才满置信
     score = base_score * confidence_mult

Edge cases:
  - swing point < 2 个: score=0, structure="mixed"
  - 只有 swing high 没有 swing low (或反之): 用已有信息判断
  - 多点在同一价位: 取第一个 (先出现的 swing), 避免重复
```

### 4.4 Dimension 3 — Channel Position (weight 0.20)

```
Input:  close series, ema20 series
        lookback=20, above_ema_threshold=0.8
Output: score ∈ [-1.0, 1.0]

Algorithm:
  1. 取最近 lookback 根 bar:
     recent_close = close.tail(lookback)
     recent_ema   = ema20.tail(lookback)

  2. 计算在 EMA20 上方的比例:
     above_ema = (recent_close > recent_ema).sum()
     ratio = above_ema / lookback

  3. 判定:
     if ratio >= above_ema_threshold:      # >80% 在均线上方
         base_direction = "bullish"
         base_score = (ratio - 0.5) * 2    # 0.8→0.6, 1.0→1.0
     elif ratio <= (1 - above_ema_threshold):  # >80% 在均线下方
         base_direction = "bearish"
         base_score = -( (1 - ratio) - 0.5) * 2  # 0.2→-0.6, 0.0→-1.0
     else:
         base_direction = "oscillating"
         base_score = 0.0

  4. 输出: score = base_score
     (MVP 阶段不做 ATR 通道调整: 理论依据不足, 非 Brooks 概念, P2 阶段重新评估)

Edge cases:
  - lookback 不足: 用可用长度, 但设置 low_data 标志
```

### 4.5 Dimension 4 — Retracement Depth (weight 0.15)

```
Input:  df with high/low/close, ema20 series
        retracement_lookback=60
        retracement_threshold_shallow=0.33, retracement_threshold_deep=0.66
Output: score ∈ [-1.0, 1.0]

Algorithm:
  1. In the last retracement_lookback bars, find the most recent swing high
     (reuse indicators.swing_high with left=5, right=5)
  2. From that swing high to current bar, find the lowest low
  3. Calculate retracement = (swing_high - lowest_low) / ATR(14)
  4. Check if close is above or below EMA20
  5. Score assignment:
     close above EMA:
       retrace < shallow (0.33 ATR)  → shallow pullback in uptrend = strong bullish (0.8)
       retrace < deep (0.66 ATR)     → moderate pullback = mildly bullish (0.3)
       retrace >= deep               → deep pullback = weakening trend (-0.5)
     close below EMA:
       retrace < shallow             → price below EMA + shallow retrace = bearish (-0.3)
       retrace < deep                → bearish (-0.5)
       retrace >= deep               → deep retrace below EMA = possible reversal (0.3)

Edge cases:
  - No swing high found in window: score=0, direction=neutral
  - ATR = 0 or prices = 0: score=0, direction=neutral
  - Fewer than 2 bars from swing high: insufficient data, score=0
```

### 4.6 Dimension 5 — Gap Bars (weight 0.10)

```
Input:  df with close, ema20 series, gap_bar_saturation=15
Output: score ∈ [-1.0, 1.0]

Algorithm:
  1. Take the last gap_bar_saturation bars (default 15)
  2. For each bar, calculate normalized distance from EMA:
     diff = |close - ema20| / ATR(14)
  3. If diff >= 0.1, count as a "gap bar" (price does not touch EMA)
  4. ratio = gap_bar_count / total_valid_bars
  5. Determine net direction: majority of closes above or below EMA
  6. Score:
     closes mostly above EMA: score = +min(ratio, 1.0), direction = bullish
     closes mostly below EMA: score = -min(ratio, 1.0), direction = bearish

Edge cases:
  - All NaN or ATR = 0: score=0, direction=neutral
  - No close clearly away from EMA: ratio → 0, score → 0 (neutral)
```

### 4.7 组合

```python
def _combine_dimensions(dimensions: dict) -> tuple:
    """计算加权总分、方向、置信度

    Returns:
        (direction: str, confidence: float, weighted_score: float)
    """
    weighted_score = 0.0
    for name, dim in dimensions.items():
        weighted_score += dim["score"] * dim["weight"]

    # direction
    if weighted_score >= 0.30:
        direction = "bullish"
    elif weighted_score <= -0.30:
        direction = "bearish"
    else:
        direction = "oscillating"

    # confidence = |weighted_score| capped at 1.0
    confidence = min(abs(weighted_score), 1.0)

    return direction, confidence, weighted_score
```

### 4.8 结构判定 (structure)

```python
def _classify_structure(df: pd.DataFrame, swing_high_mask: pd.Series,
                        swing_low_mask: pd.Series, lookback: int) -> str:
    """返回 "HHHL" | "LHLL" | "mixed"

    判定逻辑: 取最近 N 根内的 swing points, 检查高低点递进方向。
    """
    recent_idx = df.index[-lookback:]
    highs = df.loc[swing_high_mask & df.index.isin(recent_idx), "high"].tail(5).values
    lows  = df.loc[swing_low_mask & df.index.isin(recent_idx), "low"].tail(5).values

    if len(highs) < 2 or len(lows) < 2:
        return "mixed"

    # 至少 2/3 对递进
    hh = sum(highs[i] > highs[i-1] for i in range(1, len(highs))) >= max(len(highs)-2, 1)
    hl = sum(lows[i] > lows[i-1] for i in range(1, len(lows))) >= max(len(lows)-2, 1)

    if hh and hl:
        return "HHHL"
    elif not hh and not hl:
        return "LHLL"
    else:
        return "mixed"
```

---

## 5. Parameters and Defaults

### 5.1 参数表

| 参数名 | 默认值 | 类型 | 说明 | 影响 |
|--------|:------:|:----:|------|------|
| `ema_period` | 20 | int | EMA 计算周期 | 越大越平滑, 响应越慢 |
| `slope_lookback` | 5 | int | 斜率计算用最后 N 根 bar | 越大斜率越平滑 |
| `slope_threshold` | 0.3 | float | 斜率阈值 (%) | 越小对方向变化越敏感 |
| `swing_left` | 5 | int | swing 左侧 bar 数 | 越大 swing 越少, 越保守 |
| `swing_right` | 5 | int | swing 右侧 bar 数 | 同上 |
| `swing_lookback` | 60 | int | 分析 swing 的回看 bar 数 | 越大越关注长期结构 |
| `lookback` | 20 | int | 通道位置分析的回看 bar 数 | 越大越平滑 |
| `above_ema_threshold` | 0.8 | float | 通道位置判定阈值 | 越高越难触发 bullish |
| `retracement_lookback` | 60 | int | 回调深度回看窗口 | 越大越关注长期回调结构 |
| `retracement_threshold_shallow` | 0.33 | float | 浅回调阈值 (ATR 倍数) | 越小越难触发浅回调判定 |
| `retracement_threshold_deep` | 0.66 | float | 深回调阈值 (ATR 倍数) | 越小越易触发深回调判定 |
| `gap_bar_saturation` | 15 | int | 缺口棒计数窗口 | 越大越平滑, 响应越慢 |
| `bullish_threshold` | 0.30 | float | 判定 bullish 的最小加权分 | 越高越保守 |
| `bearish_threshold` | -0.30 | float | 判定 bearish 的最大加权分 | 同上 |
| `min_bars` | 30 | int | 有效运行的最少 bar 数 | 不足时返回 oscillating |

### 5.2 阈值选择理由

选择 0.3% 而非 0.1%: 股价 100 元时对应 EMA20 需在 5 根 K 线内移动 ≥1.5 元才触发方向判定。
日线 ATR 约 1-3% 的环境下, 0.3% 需要至少半天的持续方向性推动, 避免随机波动触发。

### 5.3 阈值来源

`data/thresholds.json` (由 M1.5 数据探测阶段产出) 中的 `always_in` 条目。当前默认值为 Brooks 5 分钟图经验值的日线适配初始值, 需在回测中调优。

---

## 6. Dependencies

### 6.1 内部依赖

| 模块 | 函数 | 用途 |
|------|------|------|
| `utils.indicators` | `ema()` | Dim1 EMA20 计算 |
| `utils.indicators` | `swing_high()`, `swing_low()` | Dim2 swing 点检测 |

### 6.2 外部依赖

| 库 | 用途 | 必要性 |
|----|------|:------:|
| `pandas` | DataFrame 操作 | 已存在 |
| `numpy` | clip, abs | 已存在 |

### 6.3 依赖关系图

```
loader.get_daily()
    ↓
df ──→ indicators.ema() ────────→ Dim1
df ──→ indicators.swing_high() ──┐
df ──→ indicators.swing_low()  ──┼──→ Dim2
df ──→ (close series) ───────────┘──→ Dim3
    ↓
market_state.determine_always_in() → {direction, confidence}
    ↓
pipeline.py / strategies / risk modules
```

---

## 7. Testing Approach

### 7.1 测试场景

| 测试 | 股票示例 | 时间段 | 预期 | 检查点 |
|:----|:---------|:------|:-----|:-------|
| A. 强趋势多头 | 茅台 600519.SH | 2020-2021 | bullish, confidence > 0.6 | 五维一致看多, HHHL |
| B. 强趋势空头 | 宁德时代 300750.SZ | 2022 | bearish, confidence > 0.6 | 五维一致看空, LHLL |
| C. 区间震荡 | 中国石油 601857.SH | 2023-2024 | oscillating, confidence < 0.3 | 二维有冲突 |
| D. 趋势转区间 | 茅台 600519.SH | 2021下半年 | 开始 bullish → 过渡到 oscillating | 置信度逐渐下降 |
| E. 数据不足 | — | < 30 bars | oscillating, confidence=0 | 返回 safe 默认 |
| F. 极端波动 | 连板涨停后 | 连续涨停 | 需检查不崩溃 | 不抛异常 |

### 7.2 测试方法

```python
# 测试文件: tests/test_market_state.py

def test_strong_bullish(stock_data_bullish):
    result = determine_always_in(stock_data_bullish)
    assert result["direction"] == "bullish"
    assert result["confidence"] > 0.6
    assert result["structure"] == "HHHL"
    assert result["dimensions"]["ema_slope"]["score"] > 0
    assert result["dimensions"]["hh_hl_structure"]["score"] > 0

def test_dimension_conflict_drops_confidence(stock_data_mixed):
    result = determine_always_in(stock_data_mixed)
    assert result["direction"] == "oscillating"
    assert result["confidence"] < 0.4

def test_insufficient_data_returns_safe():
    short_df = get_daily("000001.SZ", "20230101", "20230215")  # ~30 bars
    result = determine_always_in(short_df)
    assert result["direction"] in ("bullish", "bearish", "oscillating")
    # 不应抛出异常
```

### 7.3 验收标准

| 指标 | 目标 |
|------|:----:|
| 强趋势日方向正确率 | >= 75% |
| 区间日方向输出为 oscillating 比例 | >= 55% |
| 整体方向判断准确率 | >= 65% |
| 数据不足时安全返回 | 不抛异常 |
| 单股票计算耗时 | < 50ms |

---

## 8. Integration

### 8.1 函数签名

```python
# state/market_state.py

def determine_always_in(
    df: pd.DataFrame,
    params: Optional[dict] = None
) -> dict:
    """Always-In 方向判定 (5 维加权)

    Args:
        df:     OHLC DataFrame, 按 trade_date 升序
        params: 参数覆盖 (可选)

    Returns:
        dict: {direction, confidence, structure, dimensions, params_used}
    """


def get_trend_filter(
    always_in_result: dict,
    mode: str = "strict"
) -> str:
    """将 Always-In 结果转为交易方向过滤器

    Args:
        always_in_result: determine_always_in() 的返回结果
        mode: "strict" | "moderate"
            - strict: 仅 confidence > 0.5 时过滤, 否则 neutral
            - moderate: 仅 oscillating 且 confidence < 0.3 时 neutral

    Returns:
        str: "long_only" | "short_only" | "neutral"

    Rules:
        strict mode:
            direction=bullish, confidence>0.5  → long_only
            direction=bearish, confidence>0.5  → short_only
            otherwise                           → neutral

        moderate mode:
            direction=bullish                    → long_only
            direction=bearish                    → short_only
            direction=oscillating & conf<0.3     → neutral
            direction=oscillating & conf>=0.3     → long_only+short_only 可双向
    """
```

### 8.2 pipeline.py 集成

```python
# pipeline.py 中的调用序列 (M2 阶段)

from state.market_state import determine_always_in, get_trend_filter

def run_single_stock(ts_code: str, date: str) -> dict:
    # Step 1: 获取数据
    df = loader.get_daily(ts_code, start_date=subtract_days(date, 120))

    if len(df) < 30:
        return {"ts_code": ts_code, "always_in": "oscillating",
                "skip": True, "reason": "insufficient_data"}

    # Step 2: Always-In 判定
    ai_result = determine_always_in(df)

    # Step 3: 转为过滤器 (后续 M3-M4 用)
    trend_filter = get_trend_filter(ai_result)

    # Step 4: 下发给模式识别和策略层
    # ...

    return {
        "ts_code": ts_code,
        "always_in": ai_result["direction"],
        "confidence": ai_result["confidence"],
        "trend_filter": trend_filter,
        # ...
    }
```

### 8.3 在全局管线中的位置

```
pipeline.py main()
    │
    ├── 获取全 A 股或监控列表
    │
    ├── for each stock:
    │       ├── data.loader.get_daily()
    │       ├── state.market_state.determine_always_in()    ← 本模块
    │       ├── state.market_state.get_trend_filter()       ← 转换为过滤规则
    │       ├── patterns/*                                   (M3)
    │       ├── strategies/*                                 (M4)
    │       ├── risk/*                                       (M5)
    │       └── 输出信号
    │
    └── 汇总报告
```

### 8.4 与 L3 反馈回路的关系

对于 `state/context_feedback.py` (M2.6):
- 当 L3 形态检测与 Always-In 方向矛盾时, feedback 回路**降低**但不覆盖 Always-In 置信度
- 反馈输出作为 `params_used` 的一部分让下游可见
- 实现细节见 `docs/design_context_feedback.md`

---

## 9. Workbuddy Prompt

下面是完整的 workbuddy 实施提示词, 可直接复制给 workbuddy。

---

```
## 任务: 实现 P1.3 Always-In 结构判定模块

### 目标
实现 `D:\ClaudeWorkspace\price_action_trading\state\market_state.py`。
基于 Al Brooks Always-In 概念, 通过 5 维加权判定当前市场趋势方向。

### 输入格式
- df: pd.DataFrame, 列必须包含: open, high, low, close
- 按 trade_date 升序 (时间从远到近)
- 最少 30 根 bar, 推荐 60+ 根
- 来源: D:\ClaudeWorkspace\price_action_trading\data\loader.py → get_daily()

### 输出格式
```python
{
    "direction": "bullish|bearish|oscillating",
    "confidence": float,         # 0.0 ~ 1.0
    "structure": "HHHL|LHLL|mixed",
    "dimensions": {
        "ema_slope":        {"score": float, "direction": str, "weight": 0.30},
        "hh_hl_structure":  {"score": float, "direction": str, "weight": 0.25},
        "channel_position": {"score": float, "direction": str, "weight": 0.20},
        "retracement_depth":{"score": float, "direction": str, "weight": 0.15},
        "gap_bars":         {"score": float, "direction": str, "weight": 0.10}
    },
    "params_used": {...}
}
```

### 函数签名
```python
def determine_always_in(df: pd.DataFrame, params: Optional[dict] = None) -> dict
def get_trend_filter(always_in_result: dict, mode: str = "strict") -> str
# get_trend_filter 返回 "long_only" | "short_only" | "neutral"
```

### 算法

**Dim1 — EMA20 Direction & Slope (weight 0.30)**
```
calc_ema20 = pandas.ewm(span=20, adjust=False)
slope = (ema[-1] - ema[-5]) / 5  # per-bar diff
slope_pct = slope / ema[-1] * 100
if slope_pct > +0.3:  bullish, score = clip(slope_pct / 0.9, 0, 1.0)
if slope_pct < -0.3:  bearish, score = clip(-slope_pct / 0.9, 0, 1.0)
else:                 neutral,  score = 0
```

**Dim2 — HH/HL Structure (weight 0.25)**
```
复用 indicators.swing_high(df, left=5, right=5), swing_low(df, left=5, right=5)
取最后 60 根内的 swing points → 最近 5 个 high + 最近 5 个 low
检查两两递进关系 (至少 2/3 对递进)
HH+HL=+0.8, LH+LL=-0.8, 混合=±0.3 或 0.0
swing 数量不足 2 个时 score=0
```

**Dim3 — Channel Position (weight 0.20)**
```
最近 20 根 bar 中收盘在 EMA20 上方的比例
>= 80% → bullish, score = (ratio - 0.5) * 2
<= 20% → bearish, score = -( (1-ratio) - 0.5) * 2
之间    → neutral,  score = 0
(MVP 阶段不做 ATR 通道调整: 理论依据不足, 非 Brooks 概念, P2 重新评估)
```

**Dim4 — Retracement Depth (weight 0.15)**
```
在回看窗口(60)内找最近 swing high → 计算到当前位置最低点的回调
retracement = (swing_high - lowest_low) / ATR(14)
close 在 EMA 上方:
  retrace < 0.33 ATR → 浅回调 = 强趋势, score=+0.8
  retrace < 0.66 ATR → 中等回调, score=+0.3
  retrace >= 0.66 ATR → 深回调 = 趋势减弱, score=-0.5
close 在 EMA 下方:
  retrace < 0.33 ATR → bearish, score=-0.3
  retrace < 0.66 ATR → bearish, score=-0.5
  retrace >= 0.66 ATR → 深回调破 EMA = 可能反转, score=+0.3
```

**Dim5 — Gap Bars (weight 0.10)**
```
取最近 gap_bar_saturation(15) 根 bar
diff = |close - EMA20| / ATR(14), diff >= 0.1 视为"缺口棒"(价格不触EMA)
ratio = 缺口棒数 / 有效 bar 数
收盘多在 EMA 上方 → score = +min(ratio, 1.0), bullish
收盘多在 EMA 下方 → score = -min(ratio, 1.0), bearish
```

**Combination:**
```
weighted_score = 0.30*d1 + 0.25*d2 + 0.20*d3 + 0.15*d4 + 0.10*d5
direction: >= +0.30 → bullish, <= -0.30 → bearish, else oscillating
confidence: min(abs(weighted_score), 1.0)
```

### 依赖
- `from utils.indicators import ema, atr, swing_high, swing_low`
  - 路径: `D:\ClaudeWorkspace\price_action_trading\utils\indicators.py`
- `import numpy as np` (用于 clip)
- `from typing import Optional`
- 所有依赖已存在, 无需新安装

### 函数列表 (精确)
```python
# 导出
determine_always_in(df, params=None)         # 主入口
get_trend_filter(always_in_result, mode)     # 转换过滤器

# 内部
_calc_ema_slope(close, params)               # Dim1
_calc_hh_hl_structure(df, params)            # Dim2
_calc_channel_position(close, ema20, params)  # Dim3
_calc_retracement_depth(df, params)           # Dim4
_calc_gap_bars(df, params)                   # Dim5
_classify_structure(df, swing_high_mask, swing_low_mask, lookback)  # 结构判定
_combine_dimensions(dimensions)               # 加权组合
```

### 参数默认值
```
ema_period=20, slope_lookback=5, slope_threshold=0.3(%)
swing_left=5, swing_right=5, swing_lookback=60
lookback=20, above_ema_threshold=0.8
retracement_lookback=60, retracement_threshold_shallow=0.33, retracement_threshold_deep=0.66
gap_bar_saturation=15
bullish_threshold=0.30, bearish_threshold=-0.30
min_bars=30
```

### 边界条件
1. **数据不足 (< min_bars)**: direction="oscillating", confidence=0, structure="mixed", 各维度 score=0
2. **gap 日**: 不特殊处理, 以正常权重参与; gap 本身是趋势信号, 不应抹平
3. **极端波动 (连板涨停/跌停)**: high=low=close 时 swing 检测在连续同价时不产生 swing point, Dim2 score=0; Dim4 的 ATR 接近 0 时返回 neutral
4. **连续涨停封板**: 所有收盘高于 EMA20, Dim3 overbought; Dim5 gap_bars 达饱和; 但 Dim1/Dim2/Dim4 可能中性 → 加权组合自然降低置信度
5. **NaN 输入**: 上游 `indicators.py` 的 EMA/ATR/swing 函数已处理 NaN (前 N 行 NaN), 本模块只需保证不主动传入 NaN
6. **无 swing 点**: Dim4 在 retracement_lookback 内找不到 swing high 时 score=0, neutral
7. **全缺口或全触EMA**: Dim5 的 gap_ratio 达 1.0 或 0.0 时 score 饱和, 不额外衰减

### 测试方法
```python
# 保存为 D:\ClaudeWorkspace\price_action_trading\tests\test_market_state.py

# 测试 A: 强趋势多头 (茅台 2020-2021)
df = get_daily("600519.SH", "20200101", "20210630")
r = determine_always_in(df)
assert r["direction"] == "bullish", f"Expected bullish, got {r['direction']}"
assert r["confidence"] > 0.6
assert r["structure"] == "HHHL"

# 测试 B: 强趋势空头 (宁德时代 2022)
df = get_daily("300750.SZ", "20220101", "20221231")
r = determine_always_in(df)
assert r["direction"] == "bearish"

# 测试 C: 区间震荡 (中国石油 2023-2024)
df = get_daily("601857.SH", "20230101", "20240630")
r = determine_always_in(df)
# 可能 oscillating 或方向弱
assert r["confidence"] < 0.6

# 测试 D: 数据不足
df = get_daily("000001.SZ", "20240201", "20240315")  # < 30 bars?
r = determine_always_in(df)
assert r["direction"] in ("bullish", "bearish", "oscillating")  # 不抛异常
```

### 测试预期
- 强趋势日方向正确率 >= 75%
- 区间日 oscillating 比例 >= 55%
- 单股票计算耗时 < 50ms

### 实现后检查清单
- [ ] `from state.market_state import determine_always_in` 可导入
- [ ] 三个 pass through test (A/B/C) 全部通过
- [ ] 不足数据测试不抛异常
- [ ] `get_trend_filter` 对 oscillating + low confidence 返回 neutral
- [ ] `get_trend_filter` 对 bullish + high confidence 返回 long_only
```

---

_文档版本: v1.0 | 对应 M2.1 初始实现_
_注意: concept_map.md 中原分配 `state/always_in.py`, 迁移到 `state/market_state.py` 后需更新映射表。_
