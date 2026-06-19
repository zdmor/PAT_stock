"""P1.3+P2 Always-In 结构判定 — 5 维加权方向 (A 股均值回复版)

基于 Al Brooks Always-In 概念, 通过 5 维加权判定当前市场趋势方向:
  1. EMA20 斜率 (weight 0.30)    — 基础方向
  2. HH/HL 结构  (weight 0.25)    — 趋势性高低点递进
  3. 通道位置     (weight 0.20)    — K 线在 EMA 上方比例
  4. 回调深度     (weight 0.15)    — T-A06 Brooks"单一最佳指标"
  5. 缺口棒计数   (weight 0.10)    — T-A03 连续不触EMA

A 股适配: reverse_sign=True 为生产默认值。
  M1.5 校准发现 5 维分数与日线 forward 5-day 收益呈负相关 (IC=-0.20, HR=41.6%)。
  翻转后 IC=+0.20, HR=56.7%。60-min 线同样负 IC, 不支持换时间尺度。
  详见 PAT_stock/reviews/verify_ic.py。

审查已修复:
  - 修复 _dim_ema_slope 熊市返回正分数的 bug (P2)
  - 从 3 维升级到 5 维 (P2)
  - 权重从 0.35/0.40/0.25 → 0.30/0.25/0.20/0.15/0.10 (与 concept_map.md 一致)

Usage:
    from state.market_state import determine_always_in, get_trend_filter
    ai = determine_always_in(df)                # reverse_sign=True (默认)
    ai_orig = determine_always_in(df, {"reverse_sign": False})  # 原始 Brooks 方向
    direction = ai["direction"]    # bullish | bearish | oscillating
    filter = get_trend_filter(ai, mode="strict")   # long_only | short_only | neutral
"""

import numpy as np
import pandas as pd
from typing import Optional

from PAT_stock.utils.indicators import ema, swing_high, swing_low


# ── 默认参数 ──────────────────────────────────────────

DEFAULT_PARAMS = {
    "ema_period": 20,
    "slope_lookback": 5,
    "slope_threshold": 0.3,              # %, 每日斜率阈值
    "swing_left": 5,
    "swing_right": 5,
    "swing_lookback": 60,                # bar, swing_window=5 需 60 才能捕获足够 swing 点
    "lookback": 20,                       # 通道位置回看窗口
    "above_ema_threshold": 0.80,         # 80% 收盘在 EMA 上方 → bullish
    "retracement_lookback": 60,          # 回调深度回看窗口
    "retracement_threshold_shallow": 0.33,  # 浅回调 = <33%
    "retracement_threshold_deep": 0.66,     # 深回调 = >66%
    "gap_bar_saturation": 15,            # 连续 15 根=满分
    "bullish_threshold": 0.30,           # 加权分数 >= 0.30 → bullish
    "bearish_threshold": -0.30,          # 加权分数 <= -0.30 → bearish
    "reverse_sign": True,               # A 股均值回复适配: 日线5d趋势跟踪呈负IC, 翻转后IC=+0.20
    "min_bars": 30,
}


# ── 主入口 ────────────────────────────────────────────

def determine_always_in(
    df: pd.DataFrame,
    params: Optional[dict] = None,
) -> dict:
    """判定 Always-In 方向

    Args:
        df: DataFrame, 必须含 open, high, low, close
        params: 参数字典, 覆盖默认值

    Returns:
        dict: {
            "direction":    "bullish" | "bearish" | "oscillating",
            "confidence":   float,         # 0.0 ~ 1.0
            "structure":    "HHHL" | "LHLL" | "mixed",
            "dimensions":   {各维详情},
            "params_used":  {实际使用的参数},
        }
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    total_bars = len(df)

    # ── 边界: 数据不足 ──
    if df.empty or total_bars < p["min_bars"]:
        return {
            "direction": "oscillating",
            "confidence": 0.0,
            "structure": "mixed",
            "dimensions": {},
            "params_used": p,
        }

    # ── Dim1: EMA20 斜率 (weight 0.30) ──
    d1 = _dim_ema_slope(df, p)

    # ── Dim2: HH/HL 结构 (weight 0.25) ──
    d2 = _dim_hh_hl_structure(df, p)

    # ── Dim3: 通道位置 (weight 0.20) ──
    d3 = _dim_channel_position(df, p)

    # ── Dim4: 回调深度 (weight 0.15) ──
    d4 = _dim_retracement_depth(df, p)

    # ── Dim5: 缺口棒计数 (weight 0.10) ──
    d5 = _dim_gap_bars(df, p)

    # ── 加权组合 ──
    weighted_score = (
        d1["score"] * d1["weight"] +
        d2["score"] * d2["weight"] +
        d3["score"] * d3["weight"] +
        d4["score"] * d4["weight"] +
        d5["score"] * d5["weight"]
    )

    # A 股均值回复适配: 翻转分数方向
    if p.get("reverse_sign", False):
        weighted_score = -weighted_score

    # 方向判定
    if weighted_score >= p["bullish_threshold"]:
        direction = "bullish"
    elif weighted_score <= p["bearish_threshold"]:
        direction = "bearish"
    else:
        direction = "oscillating"

    confidence = min(abs(weighted_score), 1.0)

    # HH/HL 结构标记
    if d2["score"] >= 0.8:
        structure = "HHHL"
    elif d2["score"] <= -0.8:
        structure = "LHLL"
    else:
        structure = "mixed"

    return {
        "direction": direction,
        "confidence": round(confidence, 4),
        "structure": structure,
        "dimensions": {
            "ema_slope": d1,
            "hh_hl_structure": d2,
            "channel_position": d3,
            "retracement_depth": d4,
            "gap_bars": d5,
        },
        "params_used": p,
    }


# ── Dim1: EMA20 斜率 ──────────────────────────────────


def _dim_ema_slope(df: pd.DataFrame, p: dict) -> dict:
    """EMA20 斜率维度

    slope_pct > +0.3%  → bullish
    slope_pct < -0.3%  → bearish
    之间                 → neutral
    """
    ema20 = ema(df["close"], p["ema_period"])
    n = len(ema20)
    lookback = p["slope_lookback"]

    if n < lookback + 1:
        return {"score": 0.0, "direction": "neutral", "weight": 0.30}

    # 最近 lookback bar 的平均每 bar diff
    recent_ema = ema20.iloc[-lookback - 1:]  # 取 lookback+1 个值
    if recent_ema.isna().any():
        return {"score": 0.0, "direction": "neutral", "weight": 0.30}

    slope = (recent_ema.iloc[-1] - recent_ema.iloc[0]) / lookback
    ref_price = recent_ema.iloc[-1]

    if ref_price <= 0:
        return {"score": 0.0, "direction": "neutral", "weight": 0.30}

    slope_pct = slope / ref_price * 100

    threshold = p["slope_threshold"]
    if slope_pct > threshold:
        # score = clip(slope_pct / 0.9, 0, 1.0)
        score = min(max(slope_pct / 0.9, 0.0), 1.0)
        direction = "bullish"
    elif slope_pct < -threshold:
        score = -min(max(-slope_pct / 0.9, 0.0), 1.0)
        direction = "bearish"
    else:
        score = 0.0
        direction = "neutral"

    return {
        "score": round(score, 4),
        "direction": direction,
        "weight": 0.30,
    }


# ── Dim2: HH/HL 结构 ──────────────────────────────────


def _dim_hh_hl_structure(df: pd.DataFrame, p: dict) -> dict:
    """HH/HL 结构维度

    从最近 swing_lookback bar 中取最近 5 个 swing high / swing low,
    判断高低点是否递进 (HH+HL=强牛, LH+LL=强熊, 其他=分歧)
    """
    total_bars = len(df)

    sh_mask = swing_high(df, left=p["swing_left"], right=p["swing_right"])
    sl_mask = swing_low(df, left=p["swing_left"], right=p["swing_right"])

    sh_mask = sh_mask.fillna(False)
    sl_mask = sl_mask.fillna(False)

    lookback = p["swing_lookback"]
    start_idx = max(0, total_bars - lookback)

    # 取 lookback 范围内的 swing 点
    recent_highs = df.loc[
        (sh_mask) & (df.index >= start_idx), "high"
    ].tail(5).values

    recent_lows = df.loc[
        (sl_mask) & (df.index >= start_idx), "low"
    ].tail(5).values

    # 至少需要 2 个 swing 点
    if len(recent_highs) < 2 or len(recent_lows) < 2:
        return {"score": 0.0, "direction": "neutral", "weight": 0.25}

    # HH / LL 递进判定 (至少 2/3 递进)
    highs_ascending = _ascending_ratio(recent_highs) >= 2/3
    lows_ascending = _ascending_ratio(recent_lows) >= 2/3
    highs_descending = not highs_ascending
    lows_descending = not lows_ascending

    if highs_ascending and lows_ascending:
        score = 0.8
        direction = "bullish"
    elif highs_descending and lows_descending:
        score = -0.8
        direction = "bearish"
    elif highs_ascending:  # HH + LL (分歧)
        score = 0.3
        direction = "bullish"
    elif lows_ascending:    # LH + HL (分歧)
        score = -0.3
        direction = "bearish"
    else:
        score = 0.0
        direction = "neutral"

    return {
        "score": round(score, 4),
        "direction": direction,
        "weight": 0.25,
    }


def _ascending_ratio(values: np.ndarray) -> float:
    """计算递进比例 (v[i] > v[i-1] 的比例)"""
    if len(values) < 2:
        return 0.0
    ascends = sum(1 for i in range(1, len(values))
                  if values[i] > values[i - 1])
    return ascends / (len(values) - 1)


# ── Dim3: 通道位置 ────────────────────────────────────


def _dim_channel_position(df: pd.DataFrame, p: dict) -> dict:
    """通道位置维度

    最近 lookback bar 中收盘在 EMA20 上方的比例
    >= 80% → bullish
    <= 20% → bearish
    之间    → neutral

    MVP 不包含 ATR 通道调整 (非 Brooks 概念, P2 重新评估)
    """
    ema20 = ema(df["close"], p["ema_period"])
    lookback = p["lookback"]
    threshold = p["above_ema_threshold"]

    ema_recent = ema20.tail(lookback)
    close_recent = df["close"].tail(lookback)

    valid = ~(ema_recent.isna() | close_recent.isna())
    if valid.sum() == 0:
        return {"score": 0.0, "direction": "neutral", "weight": 0.20}

    above = (close_recent[valid] > ema_recent[valid]).sum()
    total_valid = valid.sum()
    ratio = above / total_valid if total_valid > 0 else 0.5

    if ratio >= threshold:
        # score = (ratio - 0.5) * 2
        score = (ratio - 0.5) * 2
        direction = "bullish"
    elif ratio <= (1.0 - threshold):
        # score = -((1-ratio) - 0.5) * 2
        score = -((1.0 - ratio) - 0.5) * 2
        direction = "bearish"
    else:
        score = 0.0
        direction = "neutral"

    return {
        "score": round(max(min(score, 1.0), -1.0), 4),
        "direction": direction,
        "weight": 0.20,
    }


# ── Dim4: 回调深度 ──────────────────────────────────


def _dim_retracement_depth(df: pd.DataFrame, p: dict) -> dict:
    """回调深度维度 — T-A06 Brooks"单一最佳指标"

    测量最近一次显著回调的深度:
      - 在回看窗口内找最近的一个 swing high (如果有明确趋势)
      - 计算从 swing high 到最近低点的回调幅度
      - 用 ATR 归一化
    """
    ema20 = ema(df["close"], p["ema_period"])
    lookback = p["retracement_lookback"]
    total_bars = len(df)
    start_idx = max(0, total_bars - lookback)

    # 最近 lookback 范围内的 swing high
    sh_mask = swing_high(df, left=p["swing_left"], right=p["swing_right"])
    sh_mask = sh_mask.fillna(False)
    recent_highs = df.loc[
        (sh_mask) & (df.index >= start_idx), "high"
    ].tail(3).values

    if len(recent_highs) < 1:
        return {"score": 0.0, "direction": "neutral", "weight": 0.15}

    # 最近 swing high → 当前位置的回调
    last_high = recent_highs[-1]
    high_idx = df[df["high"] == last_high].index[-1]
    recent_data = df.loc[high_idx:]

    if len(recent_data) < 2:
        return {"score": 0.0, "direction": "neutral", "weight": 0.15}

    low_since_high = recent_data["low"].min()
    atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]

    if atr <= 0 or last_high <= 0:
        return {"score": 0.0, "direction": "neutral", "weight": 0.15}

    retrace = (last_high - low_since_high) / atr
    shallow = p["retracement_threshold_shallow"]
    deep = p["retracement_threshold_deep"]

    # 浅回调 (< 0.33 ATR) + 价格在 EMA 上方 → 强趋势 bullish
    # 深回调 (> 0.66 ATR) → 趋势减弱
    close_above_ema = df["close"].iloc[-1] > ema20.iloc[-1]

    if close_above_ema:
        if retrace < shallow:
            score = 0.8   # 浅回调 + 价格在 EMA 上 → 强牛
            direction = "bullish"
        elif retrace < deep:
            score = 0.3   # 中等回调 → 轻微 bullish
            direction = "bullish"
        else:
            score = -0.5  # 深回调 → 趋势可能减弱
            direction = "bearish"
    else:
        if retrace < shallow:
            score = -0.3  # 价格在 EMA 下且回调浅 → bearish
            direction = "bearish"
        elif retrace < deep:
            score = -0.5
            direction = "bearish"
        else:
            score = 0.3   # 深回调 + 价格已破 EMA → 可能反转
            direction = "bullish"

    return {
        "score": round(score, 4),
        "direction": direction,
        "weight": 0.15,
        "retracement_atr": round(retrace, 4),
    }


# ── Dim5: 缺口棒计数 ──────────────────────────────────


def _dim_gap_bars(df: pd.DataFrame, p: dict) -> dict:
    """缺口棒计数维度 — T-A03 连续不触EMA

    统计最近 N 根 bar 中收盘不触 EMA 的比例:
      - 收盘与 EMA 的差值 / ATR < 0.1 视为"触EMA"
      - 比例越高 → 趋势越强 (缺口棒多)
    """
    ema20 = ema(df["close"], p["ema_period"])
    saturation = p["gap_bar_saturation"]
    atr = (df["high"] - df["low"]).rolling(14).mean()

    # 取最近 saturation 根 bar
    recent_close = df["close"].tail(saturation)
    recent_ema = ema20.tail(saturation)
    recent_atr = atr.tail(saturation)

    valid = ~(recent_close.isna() | recent_ema.isna() | recent_atr.isna() | (recent_atr == 0))
    if valid.sum() == 0:
        return {"score": 0.0, "direction": "neutral", "weight": 0.10}

    # 归一化差值
    diff = (recent_close[valid] - recent_ema[valid]).abs() / recent_atr[valid]
    gap_bars = (diff >= 0.1).sum()
    ratio = gap_bars / valid.sum()

    close_above_ema = (recent_close[valid] > recent_ema[valid]).sum() > valid.sum() / 2

    if close_above_ema:
        score = min(ratio, 1.0)
        direction = "bullish"
    else:
        score = -min(ratio, 1.0)
        direction = "bearish"

    return {
        "score": round(score, 4),
        "direction": direction,
        "weight": 0.10,
        "gap_ratio": round(ratio, 4),
    }


# ── 趋势过滤器 ────────────────────────────────────────


def get_trend_filter(always_in_result: dict, mode: str = "strict") -> str:
    """将 Always-In 方向转换为趋势过滤器

    Args:
        always_in_result: determine_always_in() 的返回值
        mode: "strict" (confidence > 0.5) | "moderate" (confidence > 0.3)

    Returns:
        "long_only" | "short_only" | "neutral"
    """
    direction = always_in_result.get("direction", "oscillating")
    confidence = always_in_result.get("confidence", 0.0)

    if direction == "oscillating":
        return "neutral"

    if mode == "strict":
        min_conf = 0.5
    elif mode == "moderate":
        min_conf = 0.3
    else:
        min_conf = 0.5

    if confidence < min_conf:
        return "neutral"

    if direction == "bullish":
        return "long_only"
    elif direction == "bearish":
        return "short_only"
    else:
        return "neutral"
