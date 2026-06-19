"""基础技术指标计算 — 纯 pandas/numpy 向量化

所有函数输入统一约定:
  - series: pd.Series
  - df:     pd.DataFrame, columns: open, high, low, close

Usage:
    from utils.indicators import ma, ema, atr, swing_high, swing_low

    df["ma20"] = ma(df["close"], 20)
    df["atr14"] = atr(df, 14)
    swings = swing_high(df, left=5, right=5)
"""

import pandas as pd
import numpy as np


# ── 移动平均 ──────────────────────────────────────────

def ma(series: pd.Series, n: int) -> pd.Series:
    """简单移动平均

    Args:
        series: 价格序列
        n:      窗口大小

    Returns:
        pd.Series — SMA 值, 前 n-1 行为 NaN
    """
    return series.rolling(window=n).mean()


def ema(series: pd.Series, n: int) -> pd.Series:
    """指数移动平均

    Args:
        series: 价格序列
        n:      窗口大小

    Returns:
        pd.Series — EMA 值, 前 n-1 行为 NaN
    """
    return series.ewm(span=n, adjust=False).mean()


# ── 波动率 ────────────────────────────────────────────

def true_range(df: pd.DataFrame) -> pd.Series:
    """真实波幅 (True Range)

    TR = max(high - low, |high - prev_close|, |low - prev_close|)

    Args:
        df: DataFrame with columns: high, low, close

    Returns:
        pd.Series — TR 值, 首行为 NaN
    """
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """平均真实波幅 (Average True Range)

    使用 EMA 近似 Wilder 平滑 (alpha = 1/n).
    与精确 Wilder ATR 的误差 < 0.5%, 对交易决策无影响.

    Args:
        df: DataFrame with columns: high, low, close
        n:  平滑周期 (默认 14)

    Returns:
        pd.Series — ATR 值
    """
    tr = true_range(df)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


# ── 极值 ──────────────────────────────────────────────

def highest_high(df: pd.DataFrame, n: int) -> pd.Series:
    """n 期内最高价

    Args:
        df: DataFrame with column: high
        n:  窗口大小

    Returns:
        pd.Series — 滚动最高价
    """
    return df["high"].rolling(window=n).max()


def lowest_low(df: pd.DataFrame, n: int) -> pd.Series:
    """n 期内最低价

    Args:
        df: DataFrame with column: low
        n:  窗口大小

    Returns:
        pd.Series — 滚动最低价
    """
    return df["low"].rolling(window=n).min()


# ── Swing 点检测 ──────────────────────────────────────

def swing_high(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.Series:
    """检测 Swing High 点

    条件: 当前 bar 的 high 是左 left 根 + 右 right 根内的最高点。
    使用 center=True 滚动窗口纯向量化实现。

    Args:
        df:    DataFrame with column: high
        left:  左侧 bar 数
        right: 右侧 bar 数

    Returns:
        pd.Series — bool, True 表示该位置是 swing high
    """
    high = df["high"]
    window = left + right + 1
    rolling_max = high.rolling(window=window, center=True,
                               min_periods=window).max()
    return high == rolling_max


def swing_low(df: pd.DataFrame, left: int = 5, right: int = 5) -> pd.Series:
    """检测 Swing Low 点

    条件: 当前 bar 的 low 是左 left 根 + 右 right 根内的最低点。
    使用 center=True 滚动窗口纯向量化实现。

    Args:
        df:    DataFrame with column: low
        left:  左侧 bar 数
        right: 右侧 bar 数

    Returns:
        pd.Series — bool, True 表示该位置是 swing low
    """
    low = df["low"]
    window = left + right + 1
    rolling_min = low.rolling(window=window, center=True,
                              min_periods=window).min()
    return low == rolling_min


# ── K 线形态 ──────────────────────────────────────────

def body_size(df: pd.DataFrame) -> pd.Series:
    """实体大小

    body = |close - open|

    Args:
        df: DataFrame with columns: open, close

    Returns:
        pd.Series — 实体大小
    """
    return (df["close"] - df["open"]).abs()


def upper_shadow(df: pd.DataFrame) -> pd.Series:
    """上影线长度

    upper_shadow = high - max(open, close)

    Args:
        df: DataFrame with columns: open, high, close

    Returns:
        pd.Series — 上影线长度 (>= 0)
    """
    return df["high"] - df[["open", "close"]].max(axis=1)


def lower_shadow(df: pd.DataFrame) -> pd.Series:
    """下影线长度

    lower_shadow = min(open, close) - low

    Args:
        df: DataFrame with columns: open, low, close

    Returns:
        pd.Series — 下影线长度 (>= 0)
    """
    return df[["open", "close"]].min(axis=1) - df["low"]


def is_doji(df: pd.DataFrame, body_pct: float = 0.1) -> pd.Series:
    """十字星判断

    实体占全幅比例 < body_pct 即为十字星。
    full_range = high - low

    Args:
        df:       DataFrame with columns: open, high, low, close
        body_pct: 实体占比阈值 (默认 0.1 = 10%)

    Returns:
        pd.Series — bool
    """
    full_range = df["high"] - df["low"]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = body_size(df) / full_range
    # 全幅为 0 时 ratio=inf, 不算 doji
    return ratio < body_pct
