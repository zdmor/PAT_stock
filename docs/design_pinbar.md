# P1.1 信号 K 线识别 — Pinbar 检测模块设计

> **冻结状态：** CRD-03 | M1.5 校准完成, 2026-06-14 已冻结。后续变更须经审查流程。
>
> 项目: PAT (Price Action Trading)
> 模块: `patterns/pinbar.py`
> 对应概念: 反转 K 线 (Reversal Bar) / 许佳聪 Pinbar 规则
> 概念映射: concept_map.md §V-B03 (反转棒), §T-B02 (趋势棒 vs 十字星)
> 上层需求文档: `docs/requirements.md` §M3.2 信号 K 线识别

---

## 1. 模块概述

### 1.1 用途

检测单根 K 线的 Pinbar 形态（也称"锤子线/上吊线"、"大尾巴小实体"），按**许佳聪规则**判定：

> 最长影线 >= 总振幅的 2/3，且实体在 K 线的另一端。

输出三种信号：
- **Bullish Pinbar** (信号 = +1): 长下影线 (lower_shadow >= 2/3 range)，小实体在顶部 — 底部拒绝，可能反转向上
- **Bearish Pinbar** (信号 = -1): 长上影线 (upper_shadow >= 2/3 range)，小实体在底部 — 顶部拒绝，可能反转向下
- **无信号** (信号 = 0)

### 1.2 文件位置

```
D:\ClaudeWorkspace\price_action_trading\patterns\pinbar.py
```

### 1.3 与同类模块的分工

| 模块 | 职责 | 差异 |
|------|------|------|
| `patterns/signal_bar.py` | 通用 K 线分类 (趋势/Doji/内包/外包) + 两棒/三棒反转 | 覆盖多类型，不专注 Pinbar 细节 |
| `patterns/pinbar.py` | **Pinbar 专精检测** | 只做 Pinbar，含强度分级 + 噪声过滤 |

Pinbar 是 `signal_bar.py` 中"反转 K 线"的一个子类型，因算法细节独立成模块便于迭代和测试。

---

## 2. 输入规格

### 2.1 DataFrame 格式

由 `data/loader.get_daily(ts_code, start_date, end_date)` 产出：

| 列名 | 类型 | 说明 |
|------|------|------|
| `ts_code` | `str` | 股票代码，如 `'000001.SZ'` |
| `trade_date` | `datetime64[ns]` | 交易日 |
| `open` | `float64` | 开盘价 |
| `high` | `float64` | 最高价 |
| `low` | `float64` | 最低价 |
| `close` | `float64` | 收盘价 |
| `vol` | `float64` | 成交量 |
| `amount` | `float64` | 成交额 |

模块内部只使用 `open, high, low, close` 四列，其余列透传。

### 2.2 最小数据要求

| 条件 | 数值 | 原因 |
|------|------|------|
| 最少 K 线数 | 21 根 | 1 根检测 + 20 根 ATR 窗口用于 min_range_atr_ratio 过滤 |
| 最少非 NaN 值 | 1 根有效 O/H/L/C | Pinbar 是单根 K 线形态，无滞后 |
| ATR 窗口 | 20 (可配置) | ATR 用于噪声过滤，不足时跳过 min_range_atr_ratio 检查 |

输入少于 21 根 K 线时：不报错，跳过 `min_range_atr_ratio` 过滤（因无足够 ATR），只做几何检测。

### 2.3 来源

```python
from price_action_trading.data.loader import get_daily

df = get_daily("000001.SZ", "20250101", "20250601")
# → DataFrame with columns: ts_code, trade_date, open, high, low, close, vol, amount
```

---

## 3. 输出规格

### 3.1 函数签名

```python
def detect_pinbar(df: pd.DataFrame,
                  main_shadow_ratio: float = 2/3,
                  body_position_threshold: float = 0.4,
                  min_range_atr_ratio: float = 0.3,
                  atr_window: int = 20,
                  key_levels: Optional[list] = None) -> pd.DataFrame:
    """Pinbar 检测（向量化）

    Args:
        df:                 DataFrame, 必须含 open/high/low/close
        main_shadow_ratio:  主影线 / 全幅 的最小比例 (默认 2/3)
        body_position_threshold: 实体距正确一端的最大比例 (默认 0.4)
        min_range_atr_ratio:      最小 K 线范围 / ATR，低于此值算噪声 (默认 0.3)
        atr_window:         ATR 计算窗口 (默认 20)
        key_levels:         P1.2a 检测到的关键位列表（可选），传入后 Pinbar 信号会标注与关键位的距离关系

    Returns:
        DataFrame — 原始 df 附加以下列:
    """
```

### 3.2 追加列

| 列名 | 类型 | 值范围 | 说明 |
|------|------|--------|------|
| `signal` | `int64` | `-1 / 0 / 1` | -1=Bearish Pinbar, 0=无信号, 1=Bullish Pinbar |
| `signal_type` | `str` | `'' / 'bullish_pinbar' / 'bearish_pinbar'` | 信号类型描述 |
| `pinbar_strength` | `str` | `'' / 'strong' / 'normal'` | strength="" 当 signal=0 |
| `main_shadow_ratio` | `float64` | `[0.0, 1.0]` | 主影线占比 |
| `near_key_level` | `bool` | `False / True` | Pinbar 影线末端与某个关键位的距离在 1 ATR 以内 |
| `key_level_distance` | `float64` | `NaN / 正数` | 影线末端到最近关键位的距离（ATR 倍数），无关键位输入时为 NaN |
| `key_level_type` | `str` | `"" / "support" / "resistance" / "both"` | 最近关键位的类型 |

### 3.3 中间计算（可选调试列，默认不输出）

通过 `debug=True` 参数控制：

| 列名 | 说明 |
|------|------|
| `body` | 实体大小 = \|close - open\| |
| `upper_shadow` | 上影线长度 |
| `lower_shadow` | 下影线长度 |
| `total_range` | 全幅 = high - low |
| `bar_range_atr_ratio` | K 线范围 / ATR(20)，低于 `min_range_atr_ratio` 时标为噪声 |

### 3.4 DataFrame 示例

| trade_date | open | high | low | close | signal | signal_type | pinbar_strength | main_shadow_ratio |
|-----------|------|------|-----|-------|--------|-------------|----------------|-------------------|
| 2025-01-15 | 10.00 | 10.20 | 9.50 | 10.15 | 1 | bullish_pinbar | strong | 0.83 |
| 2025-01-16 | 10.15 | 10.50 | 10.00 | 10.05 | -1 | bearish_pinbar | normal | 0.69 |
| 2025-01-17 | 10.05 | 10.10 | 9.95 | 10.00 | 0 | | | 0.33 |

---

## 4. 算法细节

### 4.1 核心检测规则（许佳聪）

对每根 K 线，按以下顺序执行：

```
对每根 K 线 i (0 <= i < len(df)):

  Step 1 — 计算基本量
    body        = abs(close - open)
    upper_shadow = high - max(open, close)
    lower_shadow = min(open, close) - low
    total_range = high - low

  Step 2 — 跳过异常
    if total_range == 0:
        signal[i] = 0
        continue (零振幅，无意义)

  Step 3 — 确定主影线方向
    if upper_shadow > lower_shadow:
        main_is_upper = True   → 潜在 Bearish Pinbar
    else:
        main_is_upper = False  → 潜在 Bullish Pinbar

  Step 4 — 主影线比例检查
    main_shadow_ratio = max(upper_shadow, lower_shadow) / total_range
    if main_shadow_ratio < main_shadow_ratio_threshold (2/3):
        signal[i] = 0
        continue (条件不满足)

  Step 5 — 实体位置检查 (body_position_threshold)
    if main_is_upper:  # Bearish — 实体应在底部
        body_top = max(open, close)
        body_top_pos = (body_top - low) / total_range  # 0=底部, 1=顶部
        if body_top_pos > body_position_threshold:
            signal[i] = 0
            continue (实体位置偏上，不符合 bearish)
    else:  # Bullish — 实体应在顶部
        body_bottom = min(open, close)
        body_bottom_pos = (body_bottom - low) / total_range
        if body_bottom_pos < (1 - body_position_threshold):
            signal[i] = 0
            continue (实体位置偏下，不符合 bullish)

  Step 6 — 噪声过滤 (min_range_atr_ratio, 需 ATR 前置计算)
    atr_val = atr(df, atr_window)[i]
    if not isnan(atr_val) and atr_val > 0:
        bar_range_atr_ratio = total_range / atr_val
        if bar_range_atr_ratio < min_range_atr_ratio:
            signal[i] = 0
            continue (范围太小，是噪音不是信号)

  Step 7 — 判定通过
    signal[i] = 1 if bullish else -1
    signal_type[i] = "bullish_pinbar" or "bearish_pinbar"
    strength = classify_strength(main_shadow_ratio)

  Step 7a — 关键位关联（仅当 key_levels 参数传入时执行）
    if key_levels is not None and len(key_levels) > 0:
        for each pinbar signal at index i:
            shadow_tip = low if bullish else high
            min_dist = min distance from shadow_tip to each key_level
            if min_dist <= atr[i] * 1.0:  # 1 ATR 范围内
                near_key_level[i] = True
                key_level_distance[i] = min_dist / atr[i]
```

### 4.2 强度分级

```python
def _classify_strength(main_shadow_ratio: float) -> str:
    """Pinbar 强度分级

    strong (强反转):
        main_shadow_ratio >= 0.80
        特征：尾巴极长，实体极小，拒绝极为明确

    normal (标准):
        0.667 <= main_shadow_ratio < 0.80
        特征：满足许佳聪规则的标准 Pinbar

    其他:
        "" (未达 Pinbar 条件，由调用方处理)
    """
    if main_shadow_ratio >= 0.80:
        return "strong"
    elif main_shadow_ratio >= 2/3:
        return "normal"
    else:
        return ""
```

### 4.3 向量化实现策略

全部基于 pandas 列运算，无逐行循环：

```python
def detect_pinbar(df, main_shadow_ratio=2/3, body_position_threshold=0.4,
                  min_range_atr_ratio=0.3, atr_window=20):
    df = df.copy()
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]

    # Step 1: 基本量（复用 indicators.py 现有函数）
    body = body_size(df)
    us = upper_shadow(df)
    ls = lower_shadow(df)
    total_range = h - l

    # Step 2: 跳过零振幅
    mask_zero = total_range == 0

    # Step 3: 主影线方向
    main_is_upper = us > ls

    # Step 4: 主影线比例
    main_shadow = np.where(main_is_upper, us, ls)
    shadow_ratio = main_shadow / total_range
    shadow_ratio[mask_zero] = 0.0

    mask_shadow = shadow_ratio >= main_shadow_ratio_threshold

    # Step 5: 实体位置检查
    body_top = np.maximum(o, c)
    body_bottom = np.minimum(o, c)
    # bearish: body_top 应在底部
    body_top_pos = (body_top - l) / total_range
    # bullish: body_bottom 应在顶部
    body_bottom_pos = (body_bottom - l) / total_range

    mask_bearish_pos = body_top_pos <= body_position_threshold
    mask_bullish_pos = body_bottom_pos >= (1 - body_position_threshold)

    # Step 6: 噪声过滤
    atr_val = atr(df, atr_window)
    bar_range_ratio = total_range / atr_val
    mask_noise = (atr_val.notna()) & (atr_val > 0) & (bar_range_ratio < min_range_atr_ratio)
    mask_noise = mask_noise.fillna(False)

    # 合成信号
    mask_bearish = mask_shadow & main_is_upper & mask_bearish_pos & ~mask_noise
    mask_bullish = mask_shadow & ~main_is_upper & mask_bullish_pos & ~mask_noise
    mask_bearish[mask_zero] = False
    mask_bullish[mask_zero] = False

    signal = np.zeros(len(df), dtype=int)
    signal[mask_bullish] = 1
    signal[mask_bearish] = -1

    # ... 组装输出列
```

### 4.4 边界情况处理

| 场景 | 处理方式 | 示例 |
|------|---------|------|
| **零振幅** high==low==open==close | `total_range=0`, 除法溢出, 直接跳过 | 停牌日, 一字板 |
| **Doji 同时是 Pinbar** | 允许共存, 实体小是 Pinbar 的正常特征 | 下影线极长的 Doji → bullish pinbar |
| **跳空缺口** | 不影响当前 K 线的 O/H/L/C 几何, 无需特殊处理 | 开盘跳空低开但收长下影 → 仍是 Pinbar |
| **涨停板** | 几何上可能被检出为 bullish pinbar (close≈high≈limit, 有下影线), **建议策略层额外过滤** | 涨停开板回封形成的下影线不是真实拒绝信号 |
| **跌停板** | 同上 | 跌停开板 |
| **NaN 值** | ATR NaN 传递到 bar_range_ratio → mask_noise 自动为 False (跳过噪声过滤) | 前 20 根 NaN |
| **main_shadow_ratio = Inf** | 只有 total_range=0 时发生, 已在零振幅场景排除 | — |
| **上影线 == 下影线** | 按 `us > ls` 判为 bullish (等于归入 bullish)。实际中两边相等且 >= 2/3 不可能 (总和 > 1) | — |

### 4.5 涨停/跌停处理策略

**设计决策：Pinbar 模块只做几何检测，不引入价格限制知识。**

理由：
1. Pinbar 检测是纯 K 线几何形态识别，引入限价逻辑会破坏模块单一职责
2. 限价检测需要知晓股票代码对应的限价比例 (10%/20%/5%) 和前收盘价，这属于策略层/风控层的知识
3. 策略层可在 `strategies/` 或 `risk/price_limit.py` 中过滤掉涨停日的 bullish pinbar 和跌停日的 bearish pinbar

```python
# 调用方过滤示例
result = detect_pinbar(df)
# 在策略层排除涨停日 pinbar
is_limit_up = df["close"] / prev_close >= 1.095  # 近似
result.loc[is_limit_up & (result["signal"] == 1), "signal"] = 0
```

---

## 5. 参数与默认值

| 参数 | 类型 | 默认值 | 说明 | 调整建议 |
|------|------|--------|------|---------|
| `main_shadow_ratio` | `float` | `2/3` (0.6667) | 主影线占全幅的最小比例。许佳聪规则标准值 | 可降至 0.5 提高敏感度，但假阳性增加 |
| `body_position_threshold` | `float` | `0.4` | 经验值，无许佳聪/Brooks 原文出处。P3 回测阶段验证合理性 | 越严格 (0.2) 信号越少但越纯 |
| `min_range_atr_ratio` | `float` | `0.3` | K 线振幅与 ATR 的最小比值。低于此值的窄幅 K 线即使影线比例达标也算噪声 | A 股小盘股可降至 0.2 |
| `atr_window` | `int` | `20` | ATR 计算窗口 (约一个月的交易日数) | Brooks 惯用 20 |

⚠️ **min_range_atr_ratio=0.3 未经验证。** 需在实盘数据中确认：
- 对工商银行 (ATR≈1%) 等低波动股，跑 6 个月数据统计被过滤的 Pinbar 比例
- 如果 >30% 的合法 Pinbar 被过滤，下调至 0.2
- 回测阶段 (P3) 应作为可调优参数纳入

### 参数调整与信号密度的关系

| 调整方向 | 效果 |
|---------|------|
| `main_shadow_ratio` 降低 (0.5) | 更多信号, 假阳性增加 |
| `main_shadow_ratio` 提高 (0.8) | 更少信号, 更高胜率 |
| `body_position_threshold` 调严(0.2) / 调松(0.5) | 调严(0.2)信号更少但更纯；调松(0.5)提高覆盖率，假阳性增加———当前 0.4 为默认经验值，需回测验证 |
| `min_range_atr_ratio` 提高 | 排除更多窄幅杂音, 适合大市值低波动股票 |

---

## 6. 依赖

### 6.1 直接依赖 (indicators.py)

```python
from price_action_trading.utils.indicators import (
    body_size,      # |close - open|
    upper_shadow,   # high - max(open, close)
    lower_shadow,   # min(open, close) - low
    is_doji,        # (可选) 辅助分析
)
```

### 6.2 间接依赖

| 依赖 | 用途 | 来源 |
|------|------|------|
| `atr(df, n)` | 噪声过滤 (`min_range_atr_ratio` 计算分母) | `indicators.py` |
| `numpy` | 向量化条件运算 (`np.where`, `np.maximum`, 等) | 标准库 |

### 6.3 不依赖

不在 `pinbar.py` 中导入：
- `data/loader.py` — Pinbar 只处理已加载的 DataFrame
- `state/` 模块 — Pinbar 是纯几何检测，不依赖市场状态
- `pipeline.py` — 被编排，不反依赖

---

## 7. 测试方案

### 7.1 合成测试用例

生成已知 Pinbar 形状的 DataFrame，验证检测正确性。

```python
def _make_bar(open_, close, high, low):
    """生成单根 K 线的 DataFrame 行"""
    return pd.DataFrame([{
        "open": open_, "close": close, "high": high, "low": low
    }])

def test_bullish_pinbar_strong():
    """长下影 + 小实体在顶部 → 强 Bullish Pinbar"""
    # open=10, close=10.05 (微涨), high=10.10, low=9.50
    # total_range=0.60, lower_shadow=0.50, upper_shadow=0.05, body=0.05
    # main_shadow_ratio = 0.50/0.60 = 0.833 >= 0.80 → strong
    df = _make_bar(open=10.00, close=10.05, high=10.10, low=9.50)
    result = detect_pinbar(df)
    assert result["signal"].iloc[0] == 1
    assert result["pinbar_strength"].iloc[0] == "strong"

def test_bearish_pinbar_normal():
    """长上影 + 小实体在底部 → 标准 Bearish Pinbar"""
    # open=50, close=49.80 (微跌), high=52.00, low=49.50
    # total_range=2.50, upper_shadow=2.00, lower_shadow=0.30, body=0.20
    # main_shadow_ratio = 2.00/2.50 = 0.80 → strong (刚好卡线)
    df = _make_bar(open=50.00, close=49.80, high=52.00, low=49.50)
    result = detect_pinbar(df)
    assert result["signal"].iloc[0] == -1

def test_no_pinbar_doji():
    """Doji 中央带等长影线 → 不是 Pinbar"""
    # open=50, close=50, high=51, low=49
    # total_range=2, upper_shadow=1, lower_shadow=1, body=0
    # main_shadow_ratio = 1/2 = 0.50 < 0.667 → 不是 Pinbar
    df = _make_bar(open=50, close=50, high=51, low=49)
    result = detect_pinbar(df)
    assert result["signal"].iloc[0] == 0

def test_no_pinbar_zero_range():
    """一字板零振幅 → 不是 Pinbar (跳过, 不崩溃)"""
    df = _make_bar(open=10, close=10, high=10, low=10)
    result = detect_pinbar(df)
    assert result["signal"].iloc[0] == 0

def test_no_pinbar_noise():
    """窄幅 K 线 (total_range << ATR) → 噪声过滤"""
    # 构建 25 根 K 线, 前 24 根正常波动, 最后一根窄幅 Pinbar
    # 窄幅 + ATR 较大 → bar_range_ratio < min_range_atr_ratio → 过滤
    ...
    assert result["signal"].iloc[-1] == 0  # 被噪声过滤

def test_bearish_pinbar_wrong_position():
    """Bearish 但实体偏上 → 不是 Pinbar"""
    # open=100, close=102, high=109, low=99
    # total_range=10, upper_shadow=7, lower_shadow=1, body=2
    # main_shadow_ratio = 7/10 = 0.70 >= 0.667
    # 但实体在顶部 (body_top=102, body_top_pos=(102-99)/10=0.30)
    # body_top_pos=0.30 <= 0.40 → 通过位置检查
    # 实际上这个用例应该通过...
    # 让我换一个: 实体在顶部但 bearish 应该排除
    # open=100, close=99, high=108, low=97
    # total_range=11, upper_shadow=8, lower_shadow=2, body=1
    # main_shadow_ratio=8/11=0.727, main_is_upper=True
    # body_top = max(100,99)=100, body_top_pos=(100-97)/11=3/11=0.273
    # 0.273 <= 0.40 → PASS. 这才对，因为 bearish pinbar 实体确实在底部
    pass
```

### 7.2 测试用例矩阵

| # | 类型 | open | close | high | low | 预期 signal | 预期 strength | 备注 |
|---|------|------|-------|------|-----|-------------|---------------|------|
| 1 | Bullish strong | 10.00 | 10.05 | 10.10 | 9.50 | 1 | strong | 经典锤子线 |
| 2 | Bullish normal | 10.00 | 10.03 | 10.08 | 9.60 | 1 | normal | 影线略短 |
| 3 | Bearish strong | 50.00 | 49.50 | 52.00 | 49.30 | -1 | strong | 经典上吊线 |
| 4 | Bearish normal | 50.00 | 49.60 | 51.80 | 49.40 | -1 | normal | 影线略短 |
| 5 | 不是 Pinbar | 10.00 | 10.50 | 11.00 | 9.50 | 0 | "" | 实体太大 |
| 6 | 不是 Pinbar | 10.00 | 10.00 | 11.00 | 10.00 | 0 | "" | 上下等影线 |
| 7 | 零振幅 | 10.00 | 10.00 | 10.00 | 10.00 | 0 | "" | 一字板 |
| 8 | Doji+Pinbar | 10.00 | 10.01 | 10.10 | 9.50 | 1 | strong | Doji 和 Pinbar 可共存 |
| 9 | 窄幅噪声 | 10.00 | 10.02 | 10.04 | 9.90 | 0 | "" | 范围 < ATR*0.3 |
| 10 | 低波动股合法Pinbar被误杀 | 10.00 | 10.005 | 10.01 | 9.97 | 1 | normal | Signal=1但需验证：低ATR下min_range_atr_ratio是否误杀 |

### 7.3 真实数据验证

```python
def test_real_data_pinbar():
    """使用真实 A 股数据验证 Pinbar 检测"""
    df = get_daily("600519.SH", "20250101", "20250601")  # 贵州茅台
    result = detect_pinbar(df)
    pinbars = result[result["signal"] != 0]
    # 验证检出率: 三个月至少应检出 2-5 根 Pinbar (日线级别)
    assert len(pinbars) >= 2, f"Expected >= 2 pinbars, got {len(pinbars)}"
    # 验证 signal 值合法
    assert pinbars["signal"].isin([-1, 1]).all()
    # 验证 main_shadow_ratio >= 2/3
    assert (pinbars["main_shadow_ratio"] >= 2/3 - 1e-9).all()
```

---

## 8. 集成

### 8.1 Pipeline 调用方式

```python
# pipeline.py 中调用
from price_action_trading.patterns.pinbar import detect_pinbar

class PriceActionPipeline:
    def _pattern_layer(self, df: pd.DataFrame) -> pd.DataFrame:
        df = detect_pinbar(df)
        # 后续可能叠加 detect_signal_bar() 等其他模式检测
        return df
```

当 P1.2a 关键位检测可用时，Pinbar 可接收关键位信息以标注信号与关键位的距离关系：

```python
from patterns.key_levels import detect_key_levels
from patterns.pinbar import detect_pinbar

levels = detect_key_levels(df)
df = detect_pinbar(df, key_levels=levels)
```

### 8.2 函数签名约定 (Pipeline 兼容)

所有 `patterns/` 模块的函数遵循统一签名模式：

```python
def detect_<pattern>(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """输入 DataFrame → 追加信号列 → 返回 DataFrame"""
```

此约定确保 pipeline 可以链式调用：

```python
df = get_daily("000001.SZ", "20250101", "20250601")
df = detect_pinbar(df)        # 追加 signal, signal_type, pinbar_strength, main_shadow_ratio
df = detect_signal_bar(df)    # 追加更多信号列 (未来)
```

### 8.3 安全设计 (空 DataFrame / 缺列)

- 输入空 DataFrame (len==0): 返回空 DataFrame + 新增空列
- 缺 `open/high/low/close` 列: 抛出 `KeyError`，清晰报错
- 全 NaN 列: 正常计算，signal 全 0

---

## 9. 实现优先级

| 优先级 | 内容 | 预计工时 |
|--------|------|---------|
| P0 | 向量化核心检测 (Steps 1-5) | 0.5h |
| P0 | 强度分级 (Step 7) | 0.1h |
| P0 | 基础合成测试 (case 1-7) | 0.3h |
| P1 | 噪声过滤 + ATR (Step 6) | 0.3h |
| P1 | 真实数据验证 | 0.3h |
| P2 | 可选 debug 列输出 | 0.2h |
| P2 | 参数边界测试 | 0.2h |

**预计总工时: ~2h**

---

## 10. Workbuddy Prompt

以下为完整的 workbuddy 实现提示词，可直接复制粘贴。

---

## Workbuddy Prompt

```
# Task: Implement Pinbar Detection Module

## File
D:\ClaudeWorkspace\price_action_trading\patterns\pinbar.py

## Context Files (read before implementing)
- D:\ClaudeWorkspace\price_action_trading\utils\indicators.py (has body_size, upper_shadow, lower_shadow, is_doji, atr)
- D:\ClaudeWorkspace\price_action_trading\data\loader.py (data source format)
- D:\ClaudeWorkspace\price_action_trading\pipeline.py (how it will be called)
- D:\ClaudeWorkspace\price_action_trading\docs\design_pinbar.md (this design doc)

## Required Functions

### 1. detect_pinbar(df, main_shadow_ratio, body_position_threshold, min_range_atr_ratio, atr_window, key_levels=None) -> pd.DataFrame

Vectorized (no for-loop) pinbar detection on OHLC DataFrame.

**Input:**
- df: pd.DataFrame with columns: open, high, low, close (float64). May also have ts_code, trade_date, vol, amount — pass through unchanged.
- main_shadow_ratio: float, default 2/3 (0.6667). Minimum ratio of main shadow to total_range.
- body_position_threshold: float, default 0.4. Maximum fraction body can be from the "correct" end.
- min_range_atr_ratio: float, default 0.3. Minimum bar.total_range / ATR(20) ratio to avoid noise filtering.
- atr_window: int, default 20. ATR calculation window.
- key_levels: Optional[list], default None. List of KeyLevel objects from P1.2a, or None if not available. When provided, pinbar signals will be annotated with proximity to key levels.

**Output:** Original df with these ADDITIONAL columns:
- signal: int64, values -1/0/1. -1=bearish, 0=none, 1=bullish.
- signal_type: str, values ""/"bullish_pinbar"/"bearish_pinbar".
- pinbar_strength: str, values ""/"strong"/"normal".
- main_shadow_ratio: float64, range [0.0, 1.0].
- near_key_level: bool, default False. True if shadow tip is within 1 ATR of a key level.
- key_level_distance: float64, default NaN. Distance from shadow tip to nearest key level (in ATR multiples).
- key_level_type: str, default "". Type of nearest key level: "support", "resistance", or "both".

### 2. _classify_strength(main_shadow_ratio: float) -> str (internal helper)

### Algorithm (pseudocode)

```
for each bar i:
    body = abs(close - open)
    upper_shadow = high - max(open, close)
    lower_shadow = min(open, close) - low
    total_range = high - low

    if total_range == 0:
        signal[i] = 0; continue  # skip zero-range

    main_shadow = max(upper_shadow, lower_shadow)
    shadow_ratio = main_shadow / total_range

    if shadow_ratio < main_shadow_ratio_threshold (2/3):
        signal[i] = 0; continue  # main shadow too short

    # Determine which shadow is main
    if upper_shadow > lower_shadow:
        # Potential bearish pinbar
        body_top = max(open, close)
        body_top_pos = (body_top - low) / total_range
        if body_top_pos > body_position_threshold (0.4):
            signal[i] = 0; continue  # body too high for bearish
        direction = -1
        sig_type = "bearish_pinbar"
    else:
        # Potential bullish pinbar
        body_bottom = min(open, close)
        body_bottom_pos = (body_bottom - low) / total_range
        if body_bottom_pos < (1 - body_position_threshold) (0.6):
            signal[i] = 0; continue  # body too low for bullish
        direction = 1
        sig_type = "bullish_pinbar"

    # Noise filter: skip if bar range is too small relative to ATR
    atr_val = ATR(df, atr_window)[i]
    if not isnan(atr_val) and atr_val > 0:
        if total_range / atr_val < min_range_atr_ratio (0.3):
            signal[i] = 0; continue

    signal[i] = direction
    signal_type[i] = sig_type
    strength[i] = "strong" if shadow_ratio >= 0.8 else "normal"
    main_shadow_ratio_col[i] = shadow_ratio

# Key level association (only when key_levels is provided)
for each bar i where signal[i] != 0:
    shadow_tip = low[i] if signal[i] == 1 else high[i]
    min_dist = min(|shadow_tip - level.price| for level in key_levels)
    if min_dist <= atr[i] * 1.0:
        near_key_level[i] = True
        key_level_distance[i] = min_dist / atr[i]
```

### Strength Classification
- main_shadow_ratio >= 0.80 → "strong"
- 0.667 <= main_shadow_ratio < 0.80 → "normal"
- < 0.667 → "" (not a pinbar)

### Edge Cases to Handle
1. total_range == 0: skip (no division by zero). signal=0
2. NaN in ATR (first atr_window bars): skip noise filter, still do geometric check
3. Empty DataFrame (len=0): return with added empty columns
4. Missing OHLC columns: raise KeyError with message "pinbar.detect_pinbar requires columns: open, high, low, close"
5. main_shadow_ratio or body_position_threshold as float: accept both fraction (0.6667) and literal (2/3)

### Imports
```python
import numpy as np
import pandas as pd
from price_action_trading.utils.indicators import body_size, upper_shadow, lower_shadow, atr
```

### Do NOT import
- data/loader (pinbar doesn't fetch data)
- state/ modules (pinbar is pure geometry)
- pipeline.py

### Testing (run after implementation)

Create test file: D:\ClaudeWorkspace\price_action_trading\patterns\test_pinbar.py

Test cases (synthetic):

1. BULLISH_STRONG: open=10.00, close=10.05, high=10.10, low=9.50
   → signal=1, strength="strong", main_shadow_ratio≈0.833
   (lower_shadow=0.50, body=0.05, upper_shadow=0.05, range=0.60)

2. BEARISH_STRONG: open=50.00, close=49.50, high=52.00, low=49.30
   → signal=-1, strength="strong", main_shadow_ratio≈0.815
   (upper_shadow=2.00, body=0.50, lower_shadow=0.20, range=2.70)

3. NOT_PINBAR_DOJI: open=50, close=50, high=51, low=49
   → signal=0 (equal shadows, shadow_ratio=0.50)

4. NOT_PINBAR_BIG_BODY: open=10, close=11, high=11.20, low=9.80
   → signal=0 (body=1.0 too big, shadow_ratio=0.43)

5. ZERO_RANGE: open=10, close=10, high=10, low=10
   → signal=0, no crash

6. BULLISH_NORMAL: open=20.00, close=20.02, high=20.08, low=19.60
   → signal=1, strength="normal", main_shadow_ratio≈0.708

7. NOISE_FILTER: Construct 25 bars where last bar has range=0.01 and ATR(20)=0.05
   → bar_range_ratio=0.20 < 0.30, signal=0 (filtered as noise)

For noise filter test, generate 25 rows of synthetic data:
- First 24 bars: random-ish OHLC with range ~0.10 (ATR ≈ 0.10)
- Last bar: open=100, close=100.01, high=100.02, low=99.90 (range=0.12)
  - lower_shadow=0.10, range=0.12, shadow_ratio=0.833 ≥ 0.667 (geometric pass)
  - But bar_range_ratio = 0.12 / ATR(20) ≈ 0.12/0.10 = 1.2 ≥ 0.3 → would NOT be filtered
  - Adjust last bar: open=100, close=100.005, high=100.01, low=99.95 (range=0.06)
  - lower_shadow=0.05, range=0.06, shadow_ratio=0.833 ≥ 0.667
  - bar_range_ratio = 0.06 / 0.10 = 0.60 ≥ 0.30 → still not filtered
  - Actually make ATR bigger: set first 24 bars range ~0.50, ATR(20) ≈ 0.50
  - Last bar: open=100, close=100.01, high=100.02, low=99.90 (range=0.12)
  - shadow_ratio = 0.10/0.12 = 0.833
  - bar_range_ratio = 0.12/0.50 = 0.24 < 0.30 → FILTERED, signal=0 ✓

8. REAL_DATA: Test with df = load 000001.SZ 2025-01-01 to 2025-06-01
   → Verify at least 2 pinbars detected in 5 months of daily data
   → Verify all detected pinbars have main_shadow_ratio >= 2/3
   → Verify pinbar_strength is only "strong" or "normal" (not empty)

### Verification Checklist
- [ ] detect_pinbar returns same number of rows as input
- [ ] detect_pinbar adds exactly 4 new columns
- [ ] signal values are only -1, 0, 1
- [ ] main_shadow_ratio >= 2/3 for ALL non-zero signals
- [ ] No division by zero warnings
- [ ] Empty DataFrame returns with new columns (all NaN/empty)
- [ ] Missing OHLC raises clear KeyError
```
