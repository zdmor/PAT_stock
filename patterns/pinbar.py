"""P1.1 Pinbar 检测 — 单K线反转形态 (向量化实现)

基于许佳聪《裸K线交易法》Pinbar 规则:
  - 最长影线 >= 总振幅的 2/3
  - 实体在 K 线的另一端 (bearish: body_top_pos <= 0.4; bullish: body_bottom_pos >= 0.6)
  - 噪声过滤: total_range / ATR >= min_range_atr_ratio
  - 可选: 关键位关联 (near_key_level)

算法: 全向量化, 禁止逐行循环 (关键位关联的赋值步骤除外)

Usage:
    from patterns.pinbar import detect_pinbar
    df = detect_pinbar(df)
    df = detect_pinbar(df, key_levels=levels)
"""

import numpy as np
import pandas as pd
from typing import Optional, Union

try:
    from ..utils.indicators import body_size, upper_shadow, lower_shadow, atr
except ImportError:
    from PAT_stock.utils.indicators import (
        body_size,
        upper_shadow,
        lower_shadow,
        atr,
    )


def detect_pinbar(
    df: pd.DataFrame,
    main_shadow_ratio: float = 2.0 / 3.0,
    body_position_threshold: float = 0.4,
    min_range_atr_ratio: float = 0.3,
    atr_window: int = 20,
    key_levels: Optional[list] = None,
) -> pd.DataFrame:
    """检测 Pinbar 形态 (向量化)

    Args:
        df: DataFrame, 必须含 open, high, low, close
        main_shadow_ratio: 主影线最小占比 (默认 2/3)
        body_position_threshold: 实体位于对端的最大位置 (默认 0.4)
        min_range_atr_ratio: 最小振幅/ATR 比, 噪声过滤 (默认 0.3)
        atr_window: ATR 计算窗口 (默认 20)
        key_levels: KeyLevel 对象列表, 来自 detect_key_levels(), 可选

    Returns:
        df 追加 7 列: signal, signal_type, pinbar_strength,
                     main_shadow_ratio, near_key_level,
                     key_level_distance, key_level_type
    """
    # ── 输入验证 ──
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"pinbar.detect_pinbar requires columns: "
            f"{', '.join(sorted(required))}"
        )

    if df.empty:
        return _empty_result(df)

    result = df.copy()
    n = len(result)

    # ── 基础量 ──
    body = body_size(result)
    up_shadow = upper_shadow(result)
    lo_shadow = lower_shadow(result)
    total_range = result["high"] - result["low"]

    # ── 输出列初始化 ──
    signal = np.zeros(n, dtype=int)
    signal_type_arr = np.full(n, "", dtype=object)
    strength_arr = np.full(n, "", dtype=object)

    # ── Step 1: zero_range 跳过 ──
    valid_range = total_range > 0

    # ── Step 2: 主影线 & 影线比 ──
    main_shadow = np.maximum(up_shadow, lo_shadow)
    shadow_ratio = np.where(valid_range, main_shadow / total_range, 0.0)

    # ── Step 3: 影线比 >= 2/3 ──
    has_enough_shadow = shadow_ratio >= main_shadow_ratio
    candidate = valid_range & has_enough_shadow

    # ── Step 4: 方向分类 & 实体位置检查 ──
    is_upper_dominant = up_shadow > lo_shadow

    body_top = result[["open", "close"]].max(axis=1)
    body_bottom = result[["open", "close"]].min(axis=1)

    # body_top_pos = (body_top - low) / total_range
    # body_bottom_pos = (body_bottom - low) / total_range
    body_top_pos = np.where(
        valid_range,
        (body_top - result["low"]) / total_range,
        1.0,
    )
    body_bottom_pos = np.where(
        valid_range,
        (body_bottom - result["low"]) / total_range,
        0.0,
    )

    # Bearish: upper > lower, body_top_pos <= 0.4
    bearish_mask = (
        candidate
        & is_upper_dominant
        & (body_top_pos <= body_position_threshold)
    )
    # Bullish: lower >= upper, body_bottom_pos >= (1 - body_position_threshold)
    bullish_mask = (
        candidate
        & (~is_upper_dominant)
        & (body_bottom_pos >= (1 - body_position_threshold))
    )

    # ── Step 5: ATR 噪声过滤 ──
    atr_vals = atr(result, atr_window)
    atr_valid = ~np.isnan(atr_vals.values) & (atr_vals.values > 0)

    noise = atr_valid & (total_range.values / atr_vals.values < min_range_atr_ratio)
    bearish_mask = bearish_mask & ~noise
    bullish_mask = bullish_mask & ~noise

    # ── Step 6: 赋值输出 ──
    signal[bearish_mask] = -1
    signal_type_arr[bearish_mask] = "bearish_pinbar"
    signal[bullish_mask] = 1
    signal_type_arr[bullish_mask] = "bullish_pinbar"

    has_signal = bearish_mask | bullish_mask
    strength_arr[has_signal] = np.where(
        shadow_ratio[has_signal] >= 0.80, "strong", "normal"
    )

    result["signal"] = signal
    result["signal_type"] = pd.Series(signal_type_arr, index=result.index)
    result["pinbar_strength"] = pd.Series(strength_arr, index=result.index)
    result["main_shadow_ratio"] = shadow_ratio

    # ── Step 7: 关键位关联 ──
    _attach_key_levels(result, key_levels, atr_vals)

    return result


def _attach_key_levels(
    df: pd.DataFrame,
    key_levels: Optional[list],
    atr_vals: pd.Series,
) -> None:
    """将关键位信息附加到 Pinbar 信号行 (距离计算向量化, 赋值按行)

    边界条件:
      - key_levels=None 或无信号行 → 三列保持默认值, 直接返回
      - NaN ATR → 跳过该行
      - 距离 <= 1.0 ATR → 标记 near_key_level
    """
    df["near_key_level"] = False
    df["key_level_distance"] = np.nan
    df["key_level_type"] = ""

    if key_levels is None or len(key_levels) == 0:
        return

    signal_mask = df["signal"].values != 0
    if not signal_mask.any():
        return

    # 预处理关键位
    kl_prices = np.array([kl.level_price for kl in key_levels])
    kl_types = [kl.formation_type for kl in key_levels]

    TYPE_MAP = {
        "swing_high_cluster": "resistance",
        "swing_low_cluster": "support",
        "mixed": "both",
    }

    signal_indices = np.where(signal_mask)[0]
    signals = df["signal"].values[signal_indices]

    # 影线尖端: bullish(1) → low, bearish(-1) → high
    tips = np.where(
        signals == 1,
        df["low"].values[signal_indices],
        df["high"].values[signal_indices],
    )

    # 距离矩阵 (n_signals × n_levels) — 向量化广播
    dists = np.abs(kl_prices[np.newaxis, :] - tips[:, np.newaxis])
    min_indices = np.argmin(dists, axis=1)
    min_dists = dists[np.arange(len(signal_indices)), min_indices]

    atr_for_signals = atr_vals.values[signal_indices]

    # 赋值 (DataFrame .at 无法完全向量化, 按行写入)
    for j, (orig_idx, atr_val, min_dist, min_idx) in enumerate(
        zip(signal_indices, atr_for_signals, min_dists, min_indices)
    ):
        if pd.isna(atr_val) or atr_val <= 0:
            continue
        min_dist_atr = min_dist / atr_val
        if min_dist_atr <= 1.0:
            df.at[df.index[orig_idx], "near_key_level"] = True
            df.at[df.index[orig_idx], "key_level_distance"] = float(min_dist_atr)
            df.at[df.index[orig_idx], "key_level_type"] = TYPE_MAP.get(
                kl_types[min_idx], ""
            )


def _empty_result(df: pd.DataFrame) -> pd.DataFrame:
    """空 DataFrame → 返回带空列的副本"""
    result = df.copy()
    result["signal"] = pd.Series(dtype="int64")
    result["signal_type"] = pd.Series(dtype="str")
    result["pinbar_strength"] = pd.Series(dtype="str")
    result["main_shadow_ratio"] = pd.Series(dtype="float64")
    result["near_key_level"] = pd.Series(dtype="bool")
    result["key_level_distance"] = pd.Series(dtype="float64")
    result["key_level_type"] = pd.Series(dtype="str")
    return result
