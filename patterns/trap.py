"""P1.5 陷阱检测 — Brooks 价格行为学陷阱识别 (向量化实现)

基于 Al Brooks《价格行为学》的四种陷阱类型:
  1. Fake Breakout Trap (假突破陷阱) — 价格突破关键位后迅速反转
  2. Stop Run Trap (扫止损陷阱) — 价格穿越明显 swing point 后立即反转
  3. Climax Reversal Trap (高潮反转陷阱) — 异常大实体+成交量后立即反转
  4. Barbwire Trap (窄区间陷阱) — 窄区间突破后无后续动能

算法: 全向量化, 禁止逐行循环 (关键位/摆动点迭代除外)

Reference:
  - Al Brooks, "Trading Price Action Trends" (2012), Ch.12 (Stop Runs)
  - Al Brooks, "Trading Price Action Trading Ranges" (2012), Ch.3 (Barbwire)
  - Al Brooks, "Trading Price Action Reversals" (2012), Ch.7 (Climax), Ch.8 (Fake Break)

Usage:
    from patterns.trap import detect_all_traps, detect_fake_breakout_trap
    traps = detect_all_traps(df, key_levels, swing_points)
"""

import inspect
import numpy as np
import pandas as pd
from typing import Optional, Dict, List, Any

try:
    from ..utils.indicators import (
        body_size,
        upper_shadow,
        lower_shadow,
        atr,
        ma,
    )
except ImportError:
    from PAT_stock.utils.indicators import (
        body_size,
        upper_shadow,
        lower_shadow,
        atr,
        ma,
    )


# ── 默认参数 ──────────────────────────────────────────

DEFAULT_FAKEOUT_REVERSAL_BARS = 3         # 假突破后反转确认最大 bar 数
DEFAULT_STOP_RUN_REVERSAL_BARS = 2         # 扫止损后反转确认最大 bar 数
DEFAULT_CLIMAX_BODY_ATR_MULT = 2.0         # 高潮实体 ATR 倍数阈值
DEFAULT_CLIMAX_VOL_MA_PERIOD = 20          # 成交量均线周期
DEFAULT_CLIMAX_VOL_MULT = 2.0              # 高潮成交量均量倍数阈值
DEFAULT_CLIMAX_ENGULF_FRAC = 0.5           # 反转吞噬高潮实体比例阈值
DEFAULT_BARBWIRE_RANGE_RATIO = 0.5         # 窄区间振幅/ATR 比阈值
DEFAULT_BARBWIRE_MIN_BARS = 5               # 窄区间最少连续 bar 数
DEFAULT_BARBWIRE_BREAKDOWN_BARS = 2         # 突破后确认失败的 bar 数
DEFAULT_RUN_BUFFER_ATR = 0.1               # 扫止损穿越缓冲区 (ATR 倍数)
DEFAULT_WICK_MIN_RATIO = 0.25              # 最小影线/全幅比


# ── 辅助函数 ──────────────────────────────────────────


def _forward_max(series: pd.Series, n: int) -> pd.Series:
    """前向 N 根 K 线的最大值 (向量化)

    对每个位置 i, 计算 max(series[i+1 : i+n+1])。
    末尾 n 个位置返回 NaN (数据不足)。

    Args:
        series: 输入序列
        n:      前向窗口大小, n >= 1
    """
    result = np.full(len(series), np.nan)
    for j in range(1, n + 1):
        np.fmax(result, series.shift(-j).values.astype(float), out=result)
    return pd.Series(result, index=series.index)


def _forward_min(series: pd.Series, n: int) -> pd.Series:
    """前向 N 根 K 线的最小值 (向量化)

    对每个位置 i, 计算 min(series[i+1 : i+n+1])。
    末尾 n 个位置返回 NaN (数据不足)。

    Args:
        series: 输入序列
        n:      前向窗口大小, n >= 1
    """
    result = np.full(len(series), np.nan)
    for j in range(1, n + 1):
        np.fmin(result, series.shift(-j).values.astype(float), out=result)
    return pd.Series(result, index=series.index)


def _consecutive_run(mask: pd.Series) -> pd.Series:
    """计算连续 True 的运行长度 (向量化)

    每个 True 位置的值为其所在连续 True 段中的序号 (从 1 开始)。
    False 位置值为 0。

    Example:
        mask       = [F, T, T, F, T, T, T]
        run_length = [0, 1, 2, 0, 1, 2, 3]
    """
    # 每次 True↔False 切换产生一个新 group
    group_ids = mask.ne(mask.shift()).cumsum()
    # 组内位置序号
    position = mask.groupby(group_ids).cumcount() + 1
    # False 位置清零
    return position.where(mask, 0)


def _validate_ohlc(df: pd.DataFrame) -> None:
    """验证 DataFrame 包含 OHLC 四列"""
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"trap detector requires OHLC columns: "
            f"{', '.join(sorted(required))}"
        )


def _score_confidence(conditions: List[bool]) -> str:
    """将布尔条件列表映射为置信度字符串

    全部满足 → "high", 多数满足 → "medium", 其余 → "low"
    """
    count = sum(1 for c in conditions if c)
    if count >= 3 or (len(conditions) >= 3 and count == len(conditions)):
        return "high"
    elif count >= 2:
        return "medium"
    return "low"


# ── 1. 假突破陷阱 ────────────────────────────────────


def detect_fake_breakout_trap(
    df: pd.DataFrame,
    key_levels: Optional[Dict[str, List[float]]] = None,
    atr_window: int = 20,
    reversal_bars: int = DEFAULT_FAKEOUT_REVERSAL_BARS,
    wick_min_ratio: float = DEFAULT_WICK_MIN_RATIO,
) -> Optional[Dict]:
    """检测假突破陷阱 (Fake Breakout Trap)

    Brooks 描述:
        价格突破关键阻力/支撑位, 吸引突破交易者入场,
        然后迅速反转, 套住追突破者。
        Brooks 认为这是交易区间中最常见的陷阱之一。

    检测逻辑 (每根关键位):
        1. 价格向上/下突破关键位
        2. reversal_bars 根 K 线内收盘价回到关键位另一侧
        3. 突破 K 线有足够影线 (表明被拒绝) 或反转 K 线确认

    Args:
        df:         OHLC DataFrame
        key_levels: {"resistance": [p1, p2, ...], "support": [p1, p2, ...]}
                    价格水平列表。None 或空字典返回 None。
        atr_window:     ATR 计算窗口
        reversal_bars:  反转确认最大 bar 数 (默认 3)
        wick_min_ratio: 最小影线/总振幅比, 确认拒绝 (默认 0.25)

    Returns:
        {type, trap_direction, entry_bar, stop_level, confidence, signal_bar}
        或 None (无符合条件的陷阱)

    Reference:
        Al Brooks, "Trading Price Action Reversals", Chapter 8
    """
    _validate_ohlc(df)
    if df.empty or key_levels is None:
        return None

    resistances = key_levels.get("resistance", [])
    supports = key_levels.get("support", [])
    if not resistances and not supports:
        return None

    n = len(df)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    close = df["close"].values.astype(float)
    total_range = np.maximum(high - low, 1e-10)

    # 计算一次 ATR 并复用
    atr_vals = atr(df, atr_window).values.astype(float)

    # 影线占比 (避免除零)
    up_shadow_ratio = upper_shadow(df).values / total_range
    lo_shadow_ratio = lower_shadow(df).values / total_range

    # 止损价辅助函数
    def _stopper(confirm_idx: int, direction: str) -> float:
        if direction == "bearish":
            # bearish trap: 止损在突破高点上方
            return float(high[confirm_idx]) * 1.001
        else:
            # bullish trap: 止损在突破低点下方
            return float(low[confirm_idx]) * 0.999

    best_trap = None  # 存储最近出现的陷阱

    # ── 阻力位突破 (bearish trap) ──
    for level in resistances:
        if not np.isfinite(level) or level <= 0:
            continue

        broke_above = high > level
        # 检查当前 + 未来 N 根 K 线的收盘反转
        curr_close_below = close < level
        future_min_close = _forward_min(df["close"], reversal_bars).values
        future_close_below = future_min_close < level
        any_reversal = curr_close_below | future_close_below

        # 突破 K 线有长上影线 (卖方拒绝)
        has_wick = up_shadow_ratio >= wick_min_ratio

        trap_mask = broke_above & any_reversal & has_wick

        if trap_mask.any():
            indices = np.where(trap_mask)[0]
            idx = indices[-1]  # 最新的

            # 置信度: 反转速度 + 影线强度
            future_min = future_min_close[idx]
            fast_reversal = (
                not np.isnan(future_min) and future_min < level
                and (pd.isna(curr_close_below[idx]) or not curr_close_below[idx])
            )
            strong_wick = up_shadow_ratio[idx] >= 0.5
            conf_score = _score_confidence([
                curr_close_below[idx] or fast_reversal,
                strong_wick,
                np.isfinite(atr_vals[idx]) and atr_vals[idx] > 0,
            ])

            entry_idx = idx + 1
            if entry_idx >= n:
                entry_idx = idx

            this_trap = {
                "type": "fake_breakout",
                "trap_direction": "bearish",
                "entry_bar": int(entry_idx),
                "stop_level": _stopper(idx, "bearish"),
                "confidence": conf_score,
                "signal_bar": int(idx),
                "level_price": float(level),
            }
            if best_trap is None or idx > best_trap["signal_bar"]:
                best_trap = this_trap

    # ── 支撑位跌破 (bullish trap) ──
    for level in supports:
        if not np.isfinite(level) or level <= 0:
            continue

        broke_below = low < level
        curr_close_above = close > level
        future_max_close = _forward_max(df["close"], reversal_bars).values
        future_close_above = future_max_close > level
        any_reversal = curr_close_above | future_close_above

        # 跌破 K 线有长下影线 (买方拒绝)
        has_wick = lo_shadow_ratio >= wick_min_ratio

        trap_mask = broke_below & any_reversal & has_wick

        if trap_mask.any():
            indices = np.where(trap_mask)[0]
            idx = indices[-1]

            future_max = future_max_close[idx]
            fast_reversal = (
                not np.isnan(future_max) and future_max > level
                and (pd.isna(curr_close_above[idx]) or not curr_close_above[idx])
            )
            strong_wick = lo_shadow_ratio[idx] >= 0.5
            conf_score = _score_confidence([
                curr_close_above[idx] or fast_reversal,
                strong_wick,
                np.isfinite(atr_vals[idx]) and atr_vals[idx] > 0,
            ])

            entry_idx = idx + 1
            if entry_idx >= n:
                entry_idx = idx

            this_trap = {
                "type": "fake_breakout",
                "trap_direction": "bullish",
                "entry_bar": int(entry_idx),
                "stop_level": _stopper(idx, "bullish"),
                "confidence": conf_score,
                "signal_bar": int(idx),
                "level_price": float(level),
            }
            if best_trap is None or idx > best_trap["signal_bar"]:
                best_trap = this_trap

    return best_trap


# ── 2. 扫止损陷阱 ────────────────────────────────────


def detect_stop_run_trap(
    df: pd.DataFrame,
    swing_points: Optional[Dict[str, List[float]]] = None,
    atr_window: int = 20,
    reversal_bars: int = DEFAULT_STOP_RUN_REVERSAL_BARS,
    run_buffer_atr: float = DEFAULT_RUN_BUFFER_ATR,
    wick_min_ratio: float = DEFAULT_WICK_MIN_RATIO,
) -> Optional[Dict]:
    """检测扫止损陷阱 (Stop Run Trap)

    Brooks 描述:
        价格快速穿越明显 swing point, 触发上方/下方的止损单,
        然后立即反转, 套住追突破者和被扫止损后反手追单者。
        这是 Brooks 认为最强的反转信号之一。

    与假突破的区别:
        - 假突破: 穿越的是支撑/阻力关键位 (水平位 cluster)
        - 扫止损: 穿越的是单个 swing point (人人放止损的位置)

    检测逻辑 (每个 swing point):
        1. 价格穿越 swing point + buffer ATR (确保触发止损)
        2. reversal_bars 根 K 线内收盘价回到 swing point 另一侧
        3. 穿越 K 线有足够影线或吞没形态确认

    Args:
        df:             OHLC DataFrame
        swing_points:   {"high": [p1, p2, ...], "low": [p1, p2, ...]}
                        摆动高点和低点价格。None 返回 None。
        atr_window:     ATR 计算窗口
        reversal_bars:  反转确认最大 bar 数 (默认 2)
        run_buffer_atr: 穿越缓冲区, ATR 倍数 (默认 0.1)
        wick_min_ratio: 最小影线/总振幅比 (默认 0.25)

    Returns:
        {type, trap_direction, entry_bar, stop_level, confidence, signal_bar}
        或 None

    Reference:
        Al Brooks, "Trading Price Action Trends", Chapter 12
    """
    _validate_ohlc(df)
    if df.empty or swing_points is None:
        return None

    swing_highs = swing_points.get("high", [])
    swing_lows = swing_points.get("low", [])
    if not swing_highs and not swing_lows:
        return None

    n = len(df)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    close = df["close"].values.astype(float)
    total_range = np.maximum(high - low, 1e-10)

    atr_vals = atr(df, atr_window).values.astype(float)

    up_shadow_ratio = upper_shadow(df).values / total_range
    lo_shadow_ratio = lower_shadow(df).values / total_range

    best_trap = None

    # ── 穿越 swing high (bearish trap) ──
    for s_high in swing_highs:
        if not np.isfinite(s_high) or s_high <= 0:
            continue

        buffer = run_buffer_atr * atr_vals
        ran_above = high > (s_high + buffer)

        curr_close_below = close < s_high
        future_min_close = _forward_min(df["close"], reversal_bars).values
        future_close_below = future_min_close < s_high
        any_reversal = curr_close_below | future_close_below

        has_wick = up_shadow_ratio >= wick_min_ratio

        trap_mask = ran_above & any_reversal & has_wick

        if trap_mask.any():
            indices = np.where(trap_mask)[0]
            idx = indices[-1]

            future_min = future_min_close[idx]
            fast_reversal = (
                not np.isnan(future_min) and future_min < s_high
                and (pd.isna(curr_close_below[idx]) or not curr_close_below[idx])
            )
            strong_wick = up_shadow_ratio[idx] >= 0.5
            conf_score = _score_confidence([
                curr_close_below[idx] or fast_reversal,
                strong_wick,
                np.isfinite(atr_vals[idx]) and atr_vals[idx] > 0,
            ])

            entry_idx = idx + 1
            if entry_idx >= n:
                entry_idx = idx

            this_trap = {
                "type": "stop_run",
                "trap_direction": "bearish",
                "entry_bar": int(entry_idx),
                "stop_level": float(high[idx]) * 1.001,
                "confidence": conf_score,
                "signal_bar": int(idx),
                "swing_price": float(s_high),
            }
            if best_trap is None or idx > best_trap["signal_bar"]:
                best_trap = this_trap

    # ── 穿越 swing low (bullish trap) ──
    for s_low in swing_lows:
        if not np.isfinite(s_low) or s_low <= 0:
            continue

        buffer = run_buffer_atr * atr_vals
        ran_below = low < (s_low - buffer)

        curr_close_above = close > s_low
        future_max_close = _forward_max(df["close"], reversal_bars).values
        future_close_above = future_max_close > s_low
        any_reversal = curr_close_above | future_close_above

        has_wick = lo_shadow_ratio >= wick_min_ratio

        trap_mask = ran_below & any_reversal & has_wick

        if trap_mask.any():
            indices = np.where(trap_mask)[0]
            idx = indices[-1]

            future_max = future_max_close[idx]
            fast_reversal = (
                not np.isnan(future_max) and future_max > s_low
                and (pd.isna(curr_close_above[idx]) or not curr_close_above[idx])
            )
            strong_wick = lo_shadow_ratio[idx] >= 0.5
            conf_score = _score_confidence([
                curr_close_above[idx] or fast_reversal,
                strong_wick,
                np.isfinite(atr_vals[idx]) and atr_vals[idx] > 0,
            ])

            entry_idx = idx + 1
            if entry_idx >= n:
                entry_idx = idx

            this_trap = {
                "type": "stop_run",
                "trap_direction": "bullish",
                "entry_bar": int(entry_idx),
                "stop_level": float(low[idx]) * 0.999,
                "confidence": conf_score,
                "signal_bar": int(idx),
                "swing_price": float(s_low),
            }
            if best_trap is None or idx > best_trap["signal_bar"]:
                best_trap = this_trap

    return best_trap


# ── 3. 高潮反转陷阱 ──────────────────────────────────


def detect_climax_trap(
    df: pd.DataFrame,
    atr_window: int = 14,
    vol_ma_period: int = DEFAULT_CLIMAX_VOL_MA_PERIOD,
    body_mult: float = DEFAULT_CLIMAX_BODY_ATR_MULT,
    vol_mult: float = DEFAULT_CLIMAX_VOL_MULT,
    engulf_frac: float = DEFAULT_CLIMAX_ENGULF_FRAC,
) -> Optional[Dict]:
    """检测高潮反转陷阱 (Climax Reversal Trap)

    Brooks 描述:
        市场在趋势末端出现异常大实体 K 线 (高潮/高潮反转),
        同时伴随巨大成交量, 代表买/卖力量在短时间内耗尽。
        下一根 K 线立即反转, 吞噬高潮 K 线实体的大部分。

    检测逻辑:
        1. K 线实体 > body_mult * ATR (异常大)
        2. 成交量 > vol_mult * MA(volume, vol_ma_period) (异常大)
        3. 下一根 K 线收盘价吞噬高潮实体超过 engulf_frac

    Args:
        df:             OHLC DataFrame, 需含 volume 列 (若无则返回 None)
        atr_window:     ATR 周期 (默认 14)
        vol_ma_period:  成交量均线周期 (默认 20)
        body_mult:      实体 ATR 倍数阈值 (默认 2.0)
        vol_mult:       成交量均量倍数阈值 (默认 2.0)
        engulf_frac:    吞噬比例阈值 (默认 0.5)

    Returns:
        {type, trap_direction, entry_bar, stop_level, confidence, signal_bar}
        或 None

    Reference:
        Al Brooks, "Trading Price Action Reversals", Chapter 7
    """
    _validate_ohlc(df)
    if df.empty:
        return None
    if "volume" not in df.columns:
        return None

    n = len(df)
    open_ = df["open"].values.astype(float)
    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    volume = df["volume"].values.astype(float)

    # ── 高潮 K 线条件 ──
    body = body_size(df).values.astype(float)
    atr_vals = atr(df, atr_window).values.astype(float)

    # 成交量均线
    vol_ma_vals = ma(df["volume"], vol_ma_period).values.astype(float)

    atr_ok = np.isfinite(atr_vals) & (atr_vals > 1e-10)
    vol_ok = np.isfinite(vol_ma_vals) & (vol_ma_vals > 1e-10)

    # 条件 1: 异常大实体
    body_ratio = np.where(atr_ok, body / atr_vals, 0.0)
    big_body = body_ratio >= body_mult

    # 条件 2: 异常大量
    vol_ratio = np.where(vol_ok, volume / vol_ma_vals, 0.0)
    big_vol = vol_ratio >= vol_mult

    climax_candidates = big_body & big_vol

    if not climax_candidates.any():
        return None

    # ── 条件 3: 下一根 K 线吞噬 ──
    # 高潮方向: bullish (close > open) 或 bearish (close < open)
    is_bullish_climax = close > open_
    # 高潮实体 midpoint
    midpoint = (open_ + close) / 2.0

    # 下一根 K 线的收盘
    next_close = np.roll(close, -1)
    next_close[-1] = np.nan

    # 对 bullish climax (绿柱高潮): 下一根收盘应低于 mid x% 以上
    bull_engulfed = is_bullish_climax & (next_close < midpoint)
    # 对 bearish climax (红柱高潮): 下一根收盘应高于 mid x% 以上
    bear_engulfed = (~is_bullish_climax) & (next_close > midpoint)

    # 计算吞噬深度
    climax_range = np.abs(close - open_)
    # 吞噬量: 收盘反转幅度相对于高潮实体比例
    engulf_depth = np.where(
        climax_range > 1e-10,
        np.abs(next_close - midpoint) / climax_range,
        0.0,
    )
    deep_enough = engulf_depth >= engulf_frac

    # 最终高潮陷阱信号
    bull_trap_mask = climax_candidates & is_bullish_climax & bull_engulfed & deep_enough
    bear_trap_mask = climax_candidates & (~is_bullish_climax) & bear_engulfed & deep_enough

    best_trap = None

    # ── Bullish climax (绿柱高潮 → bearish trap) ──
    if np.any(bull_trap_mask):
        indices = np.where(bull_trap_mask)[0]
        idx = indices[-1]

        entry_idx = idx + 1
        if entry_idx >= n:
            entry_idx = idx

        conf_score = _score_confidence([
            body_ratio[idx] >= 3.0,           # 极强高潮
            vol_ratio[idx] >= 3.0,             # 极高成交量
            engulf_depth[idx] >= 0.75,         # 深度吞噬
        ])

        best_trap = {
            "type": "climax",
            "trap_direction": "bearish",
            "entry_bar": int(entry_idx),
            "stop_level": float(high[idx]) * 1.001,
            "confidence": conf_score,
            "signal_bar": int(idx),
            "engulf_depth": float(engulf_depth[idx]),
            "body_atr_ratio": float(body_ratio[idx]),
            "vol_ratio": float(vol_ratio[idx]),
        }

    # ── Bearish climax (红柱高潮 → bullish trap) ──
    if np.any(bear_trap_mask):
        indices = np.where(bear_trap_mask)[0]
        idx = indices[-1]

        this_conf_score = _score_confidence([
            body_ratio[idx] >= 3.0,
            vol_ratio[idx] >= 3.0,
            engulf_depth[idx] >= 0.75,
        ])

        entry_idx = idx + 1
        if entry_idx >= n:
            entry_idx = idx

        this_trap = {
            "type": "climax",
            "trap_direction": "bullish",
            "entry_bar": int(entry_idx),
            "stop_level": float(low[idx]) * 0.999,
            "confidence": this_conf_score,
            "signal_bar": int(idx),
            "engulf_depth": float(engulf_depth[idx]),
            "body_atr_ratio": float(body_ratio[idx]),
            "vol_ratio": float(vol_ratio[idx]),
        }
        if best_trap is None or idx > best_trap["signal_bar"]:
            best_trap = this_trap

    return best_trap


# ── 4. 窄区间陷阱 ────────────────────────────────────


def detect_barbwire_trap(
    df: pd.DataFrame,
    atr_window: int = 14,
    range_ratio: float = DEFAULT_BARBWIRE_RANGE_RATIO,
    min_bars: int = DEFAULT_BARBWIRE_MIN_BARS,
    breakdown_bars: int = DEFAULT_BARBWIRE_BREAKDOWN_BARS,
) -> Optional[Dict]:
    """检测窄区间陷阱 (Barbwire Trap)

    Brooks 描述:
        铁丝网 (窄幅震荡) 代表市场在某一价格区间的犹豫不决。
        突破发生时, 如果无后续动能 (阳线后接阴线/小实体),
        则突破是陷阱, 价格会反转回来。
        Barbwire 也可以被看作是价格的休息区 (trend pause)。

    检测逻辑:
        1. 识别窄区间: 连续 min_bars 根 K 线振幅 < range_ratio * ATR
        2. 区间结束时出现突破 K 线 (收盘价超出区间极值)
        3. 突破后 breakdown_bars 根 K 线无持续动能
            (即: 突破方向未被确认)

    Args:
        df:              OHLC DataFrame
        atr_window:      ATR 周期 (默认 14)
        range_ratio:     窄区间振幅/ATR 比阈值 (默认 0.5)
        min_bars:        窄区间最少连续 K 线数 (默认 5)
        breakdown_bars:  突破后确认失败的 bar 数 (默认 2)

    Returns:
        {type, trap_direction, entry_bar, stop_level, confidence, signal_bar}
        或 None

    Reference:
        Al Brooks, "Trading Price Action Trading Ranges", Chapter 3
    """
    _validate_ohlc(df)
    if df.empty:
        return None

    n = len(df)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    close = df["close"].values.astype(float)
    total_range = high - low

    atr_vals = atr(df, atr_window).values.astype(float)
    atr_ok = np.isfinite(atr_vals) & (atr_vals > 1e-10)

    # ── Step 1: 识别窄 K 线 ──
    is_small = np.where(atr_ok, total_range < range_ratio * atr_vals, False)

    # ── Step 2: 连续运行 — 使用 groupby 找完整的小 bar 段 ──
    small_series = pd.Series(is_small, index=df.index)
    # 每次 is_small 切换为一个新组
    small_group_ids = small_series.ne(small_series.shift()).cumsum()
    # 每组内 small bar 的个数
    small_run_count = small_series.groupby(small_group_ids).transform("sum")
    # 整段都标记为 barbwire (只要段长度 >= min_bars)
    in_barbwire = small_series & (small_run_count >= min_bars)

    if not in_barbwire.any():
        return None

    # ── Step 3: 找每个 barbwire 区间的边界 ──
    # 用 in_barbwire 切换点生成组标签
    zone_group_ids = (~in_barbwire).cumsum()
    zone_groups = in_barbwire.groupby(zone_group_ids)

    # 记录每个 barbwire 区间: (start_idx, end_idx, zone_high, zone_low)
    zones = []
    for _, group in zone_groups:
        if not group.any():
            continue
        indices = group.index[group.values]
        start_idx = indices[0]
        end_idx = indices[-1]
        zone_high = float(high[start_idx:end_idx + 1].max())
        zone_low = float(low[start_idx:end_idx + 1].min())
        zones.append((start_idx, end_idx, zone_high, zone_low))

    if not zones:
        return None

    # ── Step 4: 检查每个 barbwire 区间的突破是否失败 ──
    best_trap = None

    for start_idx, end_idx, zone_high, zone_low in zones:
        breakout_idx = end_idx + 1  # 区间结束后第一根 K 线
        if breakout_idx >= n:
            continue

        # 突破方向判断: 收盘价超出区间范围
        breakout_close = close[breakout_idx]
        if breakout_close > zone_high:
            breakout_direction = "bullish"  # 向上突破
        elif breakout_close < zone_low:
            breakout_direction = "bearish"  # 向下突破
        else:
            continue  # 未突破

        # ── Step 5: 突破后检查 follow-through ──
        # 突破后 breakdown_bars 根 K 线 (不包括突破 K 线本身)
        lookahead_end = min(breakout_idx + breakdown_bars, n - 1)
        if lookahead_end <= breakout_idx:
            continue

        # 向上突破后: 检查是否有确认 (后续阳线/高点更高)
        if breakout_direction == "bullish":
            # 失败: 突破后没有持续上涨
            # 条件: 后续并没有收盘于突破收盘价之上
            subsequent_close = close[breakout_idx + 1:lookahead_end + 1]
            failure = np.all(subsequent_close <= breakout_close)
            # 更严格: 至少有一根阴线吞没突破 K 线的部分
            any_reversal_bar = np.any(
                subsequent_close < zone_high
            )
        else:
            # 向下突破后: 检查是否有确认
            subsequent_close = close[breakout_idx + 1:lookahead_end + 1]
            failure = np.all(subsequent_close >= breakout_close)
            any_reversal_bar = np.any(
                subsequent_close > zone_low
            )

        if not failure and not any_reversal_bar:
            continue

        # ── 构建结果 ──
        if breakout_direction == "bullish":
            trap_direction = "bearish"  # 向上突破失败 → bearish trap
            stop_level = float(high[breakout_idx]) * 1.001
        else:
            trap_direction = "bullish"  # 向下突破失败 → bullish trap
            stop_level = float(low[breakout_idx]) * 0.999

        # 置信度: 区间长度 + 反转强度
        zone_length = end_idx - start_idx + 1
        conf_conditions = [
            zone_length >= min_bars + 2,               # 更长的盘整
            failure,                                     # 完全无后续
            any_reversal_bar,                            # 有反转 bar
        ]
        conf_score = _score_confidence(conf_conditions)

        entry_idx = breakout_idx + 1
        if entry_idx >= n:
            entry_idx = breakout_idx

        this_trap = {
            "type": "barbwire",
            "trap_direction": trap_direction,
            "entry_bar": int(entry_idx),
            "stop_level": stop_level,
            "confidence": conf_score,
            "signal_bar": int(breakout_idx),
            "zone_length": zone_length,
            "zone_high": zone_high,
            "zone_low": zone_low,
        }

        if best_trap is None or breakout_idx > best_trap["signal_bar"]:
            best_trap = this_trap

    return best_trap


# ── 5. 全检测器 ──────────────────────────────────────


def detect_all_traps(
    df: pd.DataFrame,
    key_levels: Optional[Dict[str, List[float]]] = None,
    swing_points: Optional[Dict[str, List[float]]] = None,
    **kwargs: Any,
) -> List[Dict]:
    """运行所有陷阱检测器, 收集结果

    依次调用 detect_fake_breakout_trap, detect_stop_run_trap,
    detect_climax_trap, detect_barbwire_trap。

    每个检测器只接收其签名支持的参数, 不支持的参数自动忽略。

    Args:
        df:           OHLC DataFrame
        key_levels:   {"resistance": [...], "support": [...]}
        swing_points: {"high": [...], "low": [...]}
        **kwargs:     传递给各检测器的额外参数 (如 reversal_bars, atr_window 等)

    Returns:
        [{type, trap_direction, entry_bar, stop_level, confidence, signal_bar}, ...]
        按 signal_bar 降序排列 (最新在前)

    Usage:
        traps = detect_all_traps(df, key_levels, swing_points, atr_window=20)
        for t in traps:
            print(t["type"], t["trap_direction"], t["confidence"])
    """
    results = []

    def _filter_kwargs(func, all_kwargs):
        sig = inspect.signature(func)
        return {k: v for k, v in all_kwargs.items() if k in sig.parameters}

    detector_specs = [
        ("fake_breakout", detect_fake_breakout_trap,
         {"df": df, "key_levels": key_levels}),
        ("stop_run", detect_stop_run_trap,
         {"df": df, "swing_points": swing_points}),
        ("climax", detect_climax_trap,
         {"df": df}),
        ("barbwire", detect_barbwire_trap,
         {"df": df}),
    ]

    for name, func, base_kw in detector_specs:
        try:
            filtered = _filter_kwargs(func, kwargs)
            merged = {**base_kw, **filtered}
            result = func(**merged)
            if result is not None:
                results.append(result)
        except Exception:
            continue

    # 按 signal_bar 降序排列 (最新在前)
    results.sort(key=lambda r: r.get("signal_bar", 0), reverse=True)
    return results
