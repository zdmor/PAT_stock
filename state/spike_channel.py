"""Spike+Channel 检测 — T-A04

基于 Al Brooks Spike+Channel 概念:
  - Spike: 连续 2-5 根大实体 K 线, 重叠 < 20%
  - Channel: Spike 后的斜向运行

Usage:
    from state.spike_channel import detect_spike, detect_channel
    spike = detect_spike(df)
    channel = detect_channel(df, spike)
"""

import numpy as np
import pandas as pd
from typing import Optional


# ── 默认参数 ──────────────────────────────────────────

DEFAULT_PARAMS = {
    "min_bodies": 2,            # 最少连续大实体 K 线数
    "max_bodies": 5,            # 最多连续大实体 K 线数
    "body_pct": 0.70,           # 实体占比阈值
    "overlap_threshold": 0.20,  # 重叠比例阈值
    "channel_lookback": 20,     # 通道检测回看
    "channel_min_bars": 3,      # 通道最少 K 线数
    "pre_spike_lookback": 10,   # 分类前置回看
}


# ── Spike 检测 ────────────────────────────────────────


def detect_spike(
    df: pd.DataFrame,
    params: Optional[dict] = None,
) -> Optional[dict]:
    """检测 Spike 形态

    Args:
        df: DataFrame, 必须含 open, high, low, close
        params: 参数字典, 覆盖默认值

    Returns:
        dict or None: {
            "start_idx":   int,          首个 spike bar 的 index
            "end_idx":     int,          最后一个 spike bar 的 index
            "direction":   "bullish" | "bearish",
            "magnitude":   float,        spike 总幅度
            "high":        float,        spike 区间最高
            "low":         float,        spike 区间最低
            "bar_count":   int,          spike 包含的 bar 数
        }
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    n = len(df)

    if n < p["min_bodies"]:
        return None

    highs = df["high"].values
    lows = df["low"].values
    opens = df["open"].values
    closes = df["close"].values
    ranges = highs - lows

    # 避免除零
    valid_range = np.where(ranges > 0, ranges, np.nan)
    body_pcts = np.abs(closes - opens) / valid_range
    directions = np.where(closes >= opens, 1, -1)

    # 连续 bar 范围重叠计算: overlap[i] = overlap between i and i+1
    prev_high = highs[:-1]
    prev_low = lows[:-1]
    curr_high = highs[1:]
    curr_low = lows[1:]

    overlap_amount = np.maximum(
        0, np.minimum(prev_high, curr_high) - np.maximum(prev_low, curr_low)
    )
    min_range = np.minimum(ranges[:-1], ranges[1:])
    overlap_ratio = overlap_amount / np.maximum(min_range, 1e-10)

    # 扫描连续满足条件的 bar 组
    candidates = []
    i = 0

    while i < n:
        if not np.isnan(body_pcts[i]) and body_pcts[i] >= p["body_pct"]:
            direction = directions[i]

            j = i + 1
            while j < n:
                if np.isnan(body_pcts[j]) or body_pcts[j] < p["body_pct"]:
                    break
                if directions[j] != direction:
                    # 方向不一致 → spike 结束
                    break
                if overlap_ratio[j - 1] >= p["overlap_threshold"]:
                    # 重叠过大 → spike 结束
                    break
                j += 1

            run_length = j - i
            if p["min_bodies"] <= run_length <= p["max_bodies"]:
                spike_high = np.max(highs[i:j])
                spike_low = np.min(lows[i:j])

                candidates.append({
                    "start_idx": int(i),
                    "end_idx": int(j - 1),
                    "direction": "bullish" if direction == 1 else "bearish",
                    "magnitude": round(float(spike_high - spike_low), 4),
                    "high": round(float(spike_high), 4),
                    "low": round(float(spike_low), 4),
                    "bar_count": run_length,
                })

            i = j  # 跳过已处理的组
        else:
            i += 1

    if not candidates:
        return None

    # 返回最近的一个 spike
    return candidates[-1]


# ── 通道检测 ──────────────────────────────────────────


def detect_channel(
    df: pd.DataFrame,
    spike: Optional[dict],
    params: Optional[dict] = None,
) -> Optional[dict]:
    """检测 Spike 后的通道

    Args:
        df: DataFrame
        spike: detect_spike() 的返回值
        params: 参数字典

    Returns:
        dict or None: {
            "start_idx":     int,
            "end_idx":       int,
            "direction":     "bullish" | "bearish" | "neutral",
            "slope":         float,
            "avg_range":     float,
            "upper_bound":   float,
            "lower_bound":   float,
            "bar_count":     int,
            "type":          "continuation" | "pullback" | "neutral",
        }
    """
    if spike is None:
        return None

    p = {**DEFAULT_PARAMS, **(params or {})}
    n = len(df)

    start = spike["end_idx"] + 1
    end = min(start + p["channel_lookback"], n)

    if end - start < p["channel_min_bars"]:
        return None

    segment = df.iloc[start:end]
    seg_len = len(segment)

    # 方向判定: 检查 HH/HL 或 LH/LL 比例
    n_hh = sum(
        1 for i in range(1, seg_len)
        if segment["high"].iloc[i] > segment["high"].iloc[i - 1]
    )
    n_hl = sum(
        1 for i in range(1, seg_len)
        if segment["low"].iloc[i] > segment["low"].iloc[i - 1]
    )
    n_lh = seg_len - 1 - n_hh
    n_ll = seg_len - 1 - n_hl

    total_pairs = seg_len - 1
    hh_ratio = n_hh / total_pairs
    hl_ratio = n_hl / total_pairs
    lh_ratio = n_lh / total_pairs
    ll_ratio = n_ll / total_pairs

    threshold = 0.6
    if hh_ratio >= threshold and hl_ratio >= threshold:
        channel_dir = "bullish"
    elif lh_ratio >= threshold and ll_ratio >= threshold:
        channel_dir = "bearish"
    else:
        channel_dir = "neutral"

    # 线性回归拟合斜率
    x = np.arange(seg_len)
    if seg_len >= 3:
        high_coeffs = np.polyfit(x, segment["high"].values, 1)
        low_coeffs = np.polyfit(x, segment["low"].values, 1)
        avg_slope = (high_coeffs[0] + low_coeffs[0]) / 2
    else:
        avg_slope = (segment["close"].iloc[-1] - segment["close"].iloc[0]) / seg_len

    # 通道类型 vs spike 方向
    if channel_dir == "neutral":
        chan_type = "neutral"
    elif channel_dir == spike["direction"]:
        chan_type = "continuation"
    else:
        chan_type = "pullback"

    avg_range = (segment["high"] - segment["low"]).mean()

    return {
        "start_idx": int(start),
        "end_idx": int(end - 1),
        "direction": channel_dir,
        "slope": round(float(avg_slope), 4),
        "avg_range": round(float(avg_range), 4),
        "upper_bound": round(float(segment["high"].max()), 4),
        "lower_bound": round(float(segment["low"].min()), 4),
        "bar_count": seg_len,
        "type": chan_type,
    }


# ── Spike 类型分类 ────────────────────────────────────


def classify_spike_type(
    df: pd.DataFrame,
    spike: Optional[dict],
    params: Optional[dict] = None,
) -> str:
    """Spike 类型分类: continuation / counter_trend / unknown

    比较 spike 方向与 spike 前 lookback 根 bar 的价格变动方向。
    """
    if spike is None:
        return "unknown"

    p = {**DEFAULT_PARAMS, **(params or {})}
    lb = p["pre_spike_lookback"]
    start = max(0, spike["start_idx"] - lb)
    pre = df.iloc[start:spike["start_idx"]]

    if len(pre) < 3:
        return "unknown"

    pre_change = pre["close"].iloc[-1] - pre["close"].iloc[0]
    pre_dir = "bullish" if pre_change > 0 else "bearish"

    return "continuation" if spike["direction"] == pre_dir else "counter_trend"


# ── 通道超射检测 ──────────────────────────────────────


def channel_overshoot_check(
    df: pd.DataFrame,
    channel: Optional[dict],
    lookback: int = 10,
) -> Optional[dict]:
    """通道线超射检测 — 价格超出通道边界后通常 5 根内回归"""
    if channel is None:
        return None

    n = len(df)
    start = max(0, n - lookback)
    recent = df.iloc[start:]

    overshoot_high = recent["high"].max() > channel["upper_bound"]
    overshoot_low = recent["low"].min() < channel["lower_bound"]

    if overshoot_high:
        return {
            "direction": "bullish_overshoot",
            "overshoot_amount": round(
                float(recent["high"].max() - channel["upper_bound"]), 4
            ),
        }
    elif overshoot_low:
        return {
            "direction": "bearish_overshoot",
            "overshoot_amount": round(
                float(channel["lower_bound"] - recent["low"].min()), 4
            ),
        }

    return None


# ── Channel 争夺战检测 ────────────────────────────────


def channel_battle_check(
    df: pd.DataFrame,
    lookback: int = 15,
    spike_multiple: float = 0.7,
) -> bool:
    """Channel 争夺战检测

    大阳 spike 后紧跟大阴 spike (或反之), 说明多空激烈争夺。
    """
    n = len(df)
    start = max(0, n - lookback)
    segment = df.iloc[start:]

    seg_high = segment["high"].max()
    seg_low = segment["low"].min()
    seg_range = seg_high - seg_low

    if seg_range <= 0:
        return False

    # 找 segment 中最大阳线和最大阴线
    bull_bodies = segment[segment["close"] >= segment["open"]].copy()
    bear_bodies = segment[segment["close"] < segment["open"]].copy()

    if len(bull_bodies) == 0 or len(bear_bodies) == 0:
        return False

    max_bull = (bull_bodies["close"] - bull_bodies["open"]).max()
    max_bear = (bear_bodies["open"] - bear_bodies["close"]).max()

    # 两个方向都有 significant 大实体
    threshold = seg_range * spike_multiple
    return bool(max_bull >= threshold and max_bear >= threshold)
