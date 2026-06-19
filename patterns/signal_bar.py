"""P1.1 信号K线识别 — K线分类 + 信号K线检测 + 多K线反转

基于 Brooks 价格行为交易法:
  - K线分类: 趋势K线 / Doji / 内包 / 外包 / 反转K线
  - 信号K线: 触发入场的前一根K线, 质量评级 A/B/C
  - 两棒反转: (趋势K线 + 反向趋势K线) 实体相当
  - 三棒反转: 趋势 + 内包/Doji + 反向趋势 (1-2-3 模式)

算法: 单K线函数返回 dict; 批量检测使用向量化操作
所有 intra-bar 指标 (body%, tail% 等) 只使用纯比例, 与 timeframe 无关.

Usage:
    from patterns.signal_bar import (
        classify_bar, detect_signal_bar,
        detect_two_bar_reversal, detect_three_bar_reversal,
        detect_signal_bars_batch,
    )
"""

import numpy as np
import pandas as pd
from typing import Optional, Union

try:
    from ..utils.indicators import body_size, upper_shadow, lower_shadow
except ImportError:
    from PAT_stock.utils.indicators import body_size, upper_shadow, lower_shadow


# ── 默认阈值 (所有阈值都是纯比例, 与 timeframe 无关) ──
TREND_BODY_THRESHOLD = 0.70           # 趋势K线: 实体 > 全幅 70%
DOJI_BODY_THRESHOLD = 0.10            # Doji: 实体 < 全幅 10%
REVERSAL_TAIL_BODY_RATIO = 2.0        # 反转K线: 尾巴 > 实体 2 倍
TREND_LOOKBACK = 5                    # 判断趋势方向的回看周期 (bars)
TWO_BAR_BODY_SIMILARITY = 0.6         # 两棒反转: 实体相似度阈值
TWO_BAR_STRONG_SIMILARITY = 0.8       # 两棒反转强信号相似度阈值
SIGNAL_A_BODY_THRESHOLD = 0.35        # A级信号: 实体占比上限
SIGNAL_A_TAIL_THRESHOLD = 0.55        # A级信号: 主影线占比下限
OUTSIDE_TAIL_THRESHOLD = 0.50         # 外包K线信号: 尾巴占比阈值
TREND_BLOCKED_TAIL_THRESHOLD = 0.35   # 趋势受阻信号: 尾巴占比阈值


# ── 内部工具函数 ────────────────────────────────────────

def _validate_df(df: pd.DataFrame) -> None:
    """验证 DataFrame 是否包含所需列

    Raises:
        KeyError: 缺少 open/high/low/close 中任一列
    """
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"signal_bar requires columns: "
            f"{', '.join(sorted(required))}; "
            f"missing: {', '.join(sorted(missing))}"
        )


def _validate_idx(df: pd.DataFrame, idx: int) -> None:
    """验证索引是否在有效范围内

    Raises:
        IndexError: idx 超出 [0, len(df)-1]
    """
    if idx < 0 or idx >= len(df):
        raise IndexError(
            f"idx={idx} 超出 DataFrame 范围 [0, {len(df) - 1}]"
        )


def _local_trend_direction(df: pd.DataFrame, idx: int) -> int:
    """判断局部趋势方向

    通过当前收盘与 TREND_LOOKBACK 根K线前的收盘比较:
    close[idx] - close[idx - TREND_LOOKBACK].

    Args:
        df:  价格 DataFrame
        idx: 当前索引

    Returns:
        1 = 多头 (close 上涨)
       -1 = 空头 (close 下跌)
        0 = 持平或无法判断 (数据不足)
    """
    if idx < TREND_LOOKBACK:
        return 0
    diff = df.iloc[idx]["close"] - df.iloc[idx - TREND_LOOKBACK]["close"]
    if diff > 0:
        return 1
    elif diff < 0:
        return -1
    return 0


# ── 核心 API ────────────────────────────────────────────

def classify_bar(df: pd.DataFrame, idx: int) -> dict:
    """分类单根K线

    返回K线的完整分类信息, 包括 K线类型、各项比例、内包/外包判断等。

    分类优先级 (高→低):
      reversal > trend > outside > inside > doji > normal

    一个 K线可以同时满足多个分类条件 (如 inside + doji),
    主 type 按上述优先级选取, 同时保留所有布尔标记。

    Args:
        df:  DataFrame, 必须含 open, high, low, close
        idx: K线索引位置 (0-based)

    Returns:
        dict, 包含:
        - type (str):        主分类 | "reversal" | "trend" | "outside"
                               | "inside" | "doji" | "normal"
        - body_pct (float):  实体占全幅比例 [0, 1]
        - tail_pct (float):  最大影线占全幅比例 [0, 1]
        - is_inside (bool):  是否内包K线 (h < prev_h & l > prev_l)
        - is_outside (bool): 是否外包K线 (h > prev_h & l < prev_l)
        - is_bullish (bool): 是否阳线 (close > open)
        - is_doji (bool):    是否十字星 (body_pct < 10%)
        - is_trend (bool):   是否趋势K线 (body_pct >= 70%)
        - is_reversal (bool):是否反转K线
        - body_size (float): |close - open|
        - upper_shadow (float): high - max(open, close)
        - lower_shadow (float): min(open, close) - low
        - total_range (float):  high - low
        - upper_tail_pct (float): 上影线占全幅比 [0, 1]
        - lower_tail_pct (float): 下影线占全幅比 [0, 1]
        - main_tail (str):    "upper" | "lower" | "none" — 主影线方向

    Raises:
        IndexError: idx 越界
        KeyError:   缺少必要列
    """
    _validate_df(df)
    _validate_idx(df, idx)

    bar = df.iloc[idx]
    o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]

    total_range = h - l
    body = abs(c - o)
    up_shadow = h - max(o, c)
    lo_shadow = min(o, c) - l

    # ── 比例计算 ──
    if total_range > 0:
        body_pct = body / total_range
        up_tail_pct = up_shadow / total_range
        lo_tail_pct = lo_shadow / total_range
    else:
        body_pct = 1.0
        up_tail_pct = 0.0
        lo_tail_pct = 0.0

    tail_pct = max(up_tail_pct, lo_tail_pct)
    if up_shadow > lo_shadow:
        main_tail = "upper"
    elif lo_shadow > up_shadow:
        main_tail = "lower"
    else:
        main_tail = "none"

    # ── 内包/外包 (需前一根K线) ──
    is_inside = False
    is_outside = False
    if idx > 0:
        prev = df.iloc[idx - 1]
        is_inside = h < prev["high"] and l > prev["low"]
        is_outside = h > prev["high"] and l < prev["low"]

    # ── 布尔标记 ──
    is_bullish = c > o
    is_doji_flag = body_pct < DOJI_BODY_THRESHOLD and total_range > 0
    is_trend_flag = body_pct >= TREND_BODY_THRESHOLD

    # ── 反转K线: 尾巴 > 实体 2 倍 + 方向与趋势相反 ──
    is_reversal_flag = False
    if body > 0 and total_range > 0:
        max_tail = max(up_shadow, lo_shadow)
        if max_tail >= body * REVERSAL_TAIL_BODY_RATIO:
            trend_dir = _local_trend_direction(df, idx)
            if trend_dir > 0 and main_tail == "upper":
                # 多头趋势 + 长上影 → 价格在上方被拒绝 → 反转向下
                is_reversal_flag = True
            elif trend_dir < 0 and main_tail == "lower":
                # 空头趋势 + 长下影 → 价格在下方被拒绝 → 反转向上
                is_reversal_flag = True

    # ── 主类型 (单一标签, 按优先级) ──
    if is_reversal_flag:
        primary_type = "reversal"
    elif is_trend_flag:
        primary_type = "trend"
    elif is_outside:
        primary_type = "outside"
    elif is_inside:
        primary_type = "inside"
    elif is_doji_flag:
        primary_type = "doji"
    else:
        primary_type = "normal"

    return {
        "type": primary_type,
        "body_pct": body_pct,
        "tail_pct": tail_pct,
        "is_inside": is_inside,
        "is_outside": is_outside,
        "is_bullish": is_bullish,
        "is_doji": is_doji_flag,
        "is_trend": is_trend_flag,
        "is_reversal": is_reversal_flag,
        "body_size": body,
        "upper_shadow": up_shadow,
        "lower_shadow": lo_shadow,
        "total_range": total_range,
        "upper_tail_pct": up_tail_pct,
        "lower_tail_pct": lo_tail_pct,
        "main_tail": main_tail,
    }


def detect_signal_bar(
    df: pd.DataFrame,
    idx: int,
    always_in: str = "",
    body_threshold_a: float = SIGNAL_A_BODY_THRESHOLD,
    tail_threshold_a: float = SIGNAL_A_TAIL_THRESHOLD,
) -> dict:
    """检测信号K线并评级

    基于 Brooks 规则: 信号K线是触发入场的前一根K线.
    信号来源: 反转K线 / 外包K线+长影线 / 趋势K线受阻.

    质量评级:
      A级: 大尾巴 + 小实体 + 反转 (body_pct <= body_threshold_a
           + tail_pct >= tail_threshold_a + is_reversal)
      B级: 反转K线 (不满足 A 级条件)
      C级: 其他信号K线 (外包K线+长影线 / 趋势K线受阻)

    always_in 决定信号方向的有效性:
      "long"  → 只有 direction=1 (多头) 的信号通过
      "short" → 只有 direction=-1 (空头) 的信号通过
      ""      → 所有信号均有效

    Args:
        df:               DataFrame, 含 open, high, low, close
        idx:              K线索引
        always_in:        "long" | "short" | "" (默认 "")
        body_threshold_a: A级信号实体占比上限 (默认 0.35)
        tail_threshold_a: A级信号主影线占比下限 (默认 0.55)

    Returns:
        dict, 包含:
        - is_signal (bool):  是否为有效信号K线
        - quality (str):     "A" | "B" | "C" | "" (空 = 非信号)
        - direction (int):    1 (多头) | -1 (空头) | 0 (无)
        - reason (str):       判断理由文本
        - classification (dict): classify_bar 的结果 (含所有子字段)

    Raises:
        IndexError: idx 越界
        KeyError:   缺少必要列
        ValueError: always_in 参数值无效
    """
    _validate_df(df)
    _validate_idx(df, idx)

    if always_in not in ("long", "short", ""):
        raise ValueError(
            f"always_in 必须是 'long', 'short' 或 ''; 实际: '{always_in}'"
        )

    cl = classify_bar(df, idx)

    result = {
        "is_signal": False,
        "quality": "",
        "direction": 0,
        "reason": "",
        "classification": cl,
    }

    # ── 判断是否为信号K线 ──
    is_signal = False
    direction = 0
    reasons = []

    if cl["is_reversal"]:
        # 反转K线 → 强信号
        is_signal = True
        if cl["main_tail"] == "upper":
            direction = -1  # 空头信号
            reasons.append("上影线反转")
        elif cl["main_tail"] == "lower":
            direction = 1   # 多头信号
            reasons.append("下影线反转")
    elif cl["is_outside"] and cl["tail_pct"] >= OUTSIDE_TAIL_THRESHOLD and cl["main_tail"] != "none":
        # 外包K线 + 长尾巴 → 弱信号
        is_signal = True
        if cl["main_tail"] == "upper":
            direction = -1
            reasons.append("外包K线+上影线扩张")
        elif cl["main_tail"] == "lower":
            direction = 1
            reasons.append("外包K线+下影线扩张")
    elif cl["is_trend"] and cl["tail_pct"] >= TREND_BLOCKED_TAIL_THRESHOLD and cl["main_tail"] != "none":
        # 趋势K线 + 尾巴 → 趋势受阻信号
        is_signal = True
        if cl["main_tail"] == "upper":
            direction = -1
            reasons.append("趋势K线+上影线受阻")
        elif cl["main_tail"] == "lower":
            direction = 1
            reasons.append("趋势K线+下影线受阻")

    if not is_signal:
        return result

    # ── 质量评级 ──
    quality = "C"
    if cl["is_reversal"]:
        if cl["body_pct"] <= body_threshold_a and cl["tail_pct"] >= tail_threshold_a:
            quality = "A"
            reasons.append("大尾巴小实体")
        else:
            quality = "B"
            reasons.append("反转阻力位")

    # ── always_in 过滤 ──
    if always_in == "long" and direction != 1:
        return result
    if always_in == "short" and direction != -1:
        return result

    result["is_signal"] = True
    result["quality"] = quality
    result["direction"] = direction
    result["reason"] = " + ".join(reasons)

    return result


def detect_two_bar_reversal(df: pd.DataFrame, idx: int) -> Optional[dict]:
    """检测两棒反转形态

    Brooks 定义: (趋势K线 + 反向趋势K线) 实体相当 → 强反转

    条件:
      - bar[idx-1] 是趋势K线 (body_pct >= TREND_BODY_THRESHOLD)
      - bar[idx]   是反向趋势K线 (body_pct >= TREND_BODY_THRESHOLD, 方向相反)
      - 两棒实体大小相当 (小 / 大 >= TWO_BAR_BODY_SIMILARITY)

    Args:
        df:  DataFrame, 含 open, high, low, close
        idx: 第二根K线的索引 (需要 idx >= 1)

    Returns:
        dict | None:
        - direction (int):     反转后方向 | 1 (看涨) | -1 (看跌)
        - strength (str):      "strong" (实体相似度 >= 0.8) | "normal"
        - first_bar_type (str):  第一棒分类
        - second_bar_type (str): 第二棒分类
        当不满足条件时返回 None.

    Raises:
        IndexError: idx < 1 (无法获取前一根K线)
        KeyError:   缺少必要列
    """
    _validate_df(df)
    if idx < 1:
        raise IndexError(
            f"two_bar_reversal: idx={idx} < 1, 无法获取前一根K线"
        )

    b1 = classify_bar(df, idx - 1)
    b2 = classify_bar(df, idx)

    # 必须都是趋势K线
    if not (b1["is_trend"] and b2["is_trend"]):
        return None

    # 方向必须相反
    if b1["is_bullish"] == b2["is_bullish"]:
        return None

    # 实体相似度
    body_small = min(b1["body_size"], b2["body_size"])
    body_large = max(b1["body_size"], b2["body_size"])
    if body_large == 0:
        return None
    similarity = body_small / body_large
    if similarity < TWO_BAR_BODY_SIMILARITY:
        return None

    # 第一棒确定原趋势方向
    if b1["is_bullish"]:
        # 先涨后跌 → 看跌反转
        direction = -1
        strength = "strong" if similarity >= TWO_BAR_STRONG_SIMILARITY else "normal"
    else:
        # 先跌后涨 → 看涨反转
        direction = 1
        strength = "strong" if similarity >= TWO_BAR_STRONG_SIMILARITY else "normal"

    return {
        "direction": direction,
        "strength": strength,
        "first_bar_type": b1["type"],
        "second_bar_type": b2["type"],
    }


def detect_three_bar_reversal(df: pd.DataFrame, idx: int) -> Optional[dict]:
    """检测三棒反转形态 (1-2-3 模式)

    条件:
      - bar[idx-2]: 趋势K线 (方向 A)
      - bar[idx-1]: 调整K线 (非趋势K线; 内包/Doji/普通K线与A相反)
      - bar[idx]:   趋势K线 (方向 B, 与 A 相反)

    这是 Brooks 1-2-3 高/低模式的基础版本:
      1 推 → 2 调整 → 3 反向推 → 趋势反转确认.

    Args:
        df:  DataFrame, 含 open, high, low, close
        idx: 第三根K线索引 (需要 idx >= 2)

    Returns:
        dict | None:
        - pattern (str):     "1-2-3 reversal"
        - direction (int):   反转后方向 | 1 (看涨) | -1 (看跌)
        - strength (str):    "strong" (第二棒是内包K线) | "normal"
        - first_bar (str):   第一棒类型
        - second_bar (str):  第二棒类型
        - third_bar (str):   第三棒类型
        当不满足条件时返回 None.

    Raises:
        IndexError: idx < 2 (无法获取前两根K线)
        KeyError:   缺少必要列
    """
    _validate_df(df)
    if idx < 2:
        raise IndexError(
            f"three_bar_reversal: idx={idx} < 2, 无法获取前两根K线"
        )

    b1 = classify_bar(df, idx - 2)
    b2 = classify_bar(df, idx - 1)
    b3 = classify_bar(df, idx)

    # 第一棒: 趋势K线
    if not b1["is_trend"]:
        return None

    # 第三棒: 趋势K线, 方向与第一棒相反
    if not b3["is_trend"]:
        return None
    if b1["is_bullish"] == b3["is_bullish"]:
        return None

    # 第二棒: 不能是趋势K线
    if b2["is_trend"]:
        return None

    # 第二棒方向过滤:
    #   - Doji 可接受
    #   - 非 Doji 时方向必须与第三棒相反 (相当于回撤而非加速)
    if not b2["is_doji"] and b2["is_bullish"] == b3["is_bullish"]:
        return None

    # 反转方向: 第一棒决定原趋势
    if b1["is_bullish"]:
        direction = -1  # 涨 → 跌 → 涨不动 → 反转向下
    else:
        direction = 1   # 跌 → 涨 → 跌不动 → 反转向上

    return {
        "pattern": "1-2-3 reversal",
        "direction": direction,
        "strength": "strong" if b2["is_inside"] else "normal",
        "first_bar": b1["type"],
        "second_bar": b2["type"],
        "third_bar": b3["type"],
    }


def detect_signal_bars_batch(
    df: pd.DataFrame,
    always_in_series: Optional[Union[pd.Series, np.ndarray]] = None,
) -> pd.DataFrame:
    """批量检测所有信号K线 (全向量化实现)

    DataFrame 中的每一行执行分类 + 信号检测, 追加结果列.
    对 classify_bar / detect_signal_bar 的向量化加速版本.

    Args:
        df: DataFrame, 必须含 open, high, low, close
        always_in_series: 可选, 每行的 always_in 状态.
                          pd.Series 或 np.ndarray, 值域 "long"/"short"/"".
                          None 时所有信号均有效.

    Returns:
        DataFrame, 追加以下列:
        - bar_type (str):            K线主分类
        - body_pct (float):          实体占比
        - tail_pct (float):          最大影线占比
        - is_inside (bool):          内包K线
        - is_outside (bool):         外包K线
        - is_doji (bool):            十字星
        - is_trend (bool):           趋势K线
        - is_reversal (bool):        反转K线
        - is_signal_bar (bool):      是否信号K线
        - signal_bar_quality (str):  "A" / "B" / "C" / ""
        - signal_bar_direction (int):  1 / -1 / 0
        - signal_bar_reason (str):   理由文本

    Raises:
        KeyError: 缺少必要列
    """
    _validate_df(df)
    result = df.copy()
    n = len(result)

    if n == 0:
        return _empty_batch_result(result)

    # ── 基础量 (全向量化) ──
    o = result["open"].values.astype(float)
    h = result["high"].values.astype(float)
    l = result["low"].values.astype(float)
    c = result["close"].values.astype(float)

    total_range = h - l
    body = np.abs(c - o)
    up_shadow = h - np.maximum(o, c)
    lo_shadow = np.minimum(o, c) - l

    with np.errstate(divide="ignore", invalid="ignore"):
        body_pct = np.where(total_range > 0, body / total_range, 1.0)
        up_tail_pct = np.where(total_range > 0, up_shadow / total_range, 0.0)
        lo_tail_pct = np.where(total_range > 0, lo_shadow / total_range, 0.0)

    tail_pct = np.maximum(up_tail_pct, lo_tail_pct)
    is_upper_dominant = up_shadow > lo_shadow
    is_lower_dominant = lo_shadow > up_shadow
    has_dominant_tail = is_upper_dominant | is_lower_dominant

    is_bullish = c > o

    # ── K线分类 (向量化) ──
    is_doji = body_pct < DOJI_BODY_THRESHOLD
    is_trend = body_pct >= TREND_BODY_THRESHOLD

    # 内包/外包: 与前一根比较
    prev_h = np.roll(h, 1)
    prev_l = np.roll(l, 1)
    is_inside = (h < prev_h) & (l > prev_l)
    is_outside = (h > prev_h) & (l < prev_l)
    is_inside[0] = False
    is_outside[0] = False

    # ── 局部趋势方向 (向量化) ──
    trend_dir = np.zeros(n, dtype=float)
    if n > TREND_LOOKBACK:
        trend_dir[TREND_LOOKBACK:] = np.sign(
            c[TREND_LOOKBACK:] - c[:-TREND_LOOKBACK]
        )

    # ── 反转K线 ──
    max_tail = np.maximum(up_shadow, lo_shadow)
    has_big_tail = (
        (body > 0)
        & (total_range > 0)
        & (max_tail >= body * REVERSAL_TAIL_BODY_RATIO)
    )

    rev_down = has_big_tail & is_upper_dominant & (trend_dir > 0)
    rev_up = has_big_tail & is_lower_dominant & (trend_dir < 0)
    is_reversal = rev_up | rev_down

    # ── 主类型 (向量化) ──
    type_arr = np.full(n, "normal", dtype=object)
    type_arr[is_reversal] = "reversal"
    type_arr[is_trend & ~is_reversal] = "trend"
    type_arr[is_outside & ~is_trend & ~is_reversal] = "outside"
    type_arr[is_inside & ~is_outside & ~is_trend & ~is_reversal] = "inside"
    type_arr[is_doji & ~is_inside & ~is_outside & ~is_trend & ~is_reversal] = "doji"

    # ── 信号K线检测 ──
    is_signal = np.zeros(n, dtype=bool)
    signal_quality = np.full(n, "", dtype=object)
    signal_dir = np.zeros(n, dtype=int)
    signal_reason = np.full(n, "", dtype=object)

    # --- 1) 反转K线 → 信号 ---
    rev_mask = is_reversal
    is_signal[rev_mask] = True
    signal_dir[rev_mask & is_upper_dominant] = -1
    signal_dir[rev_mask & is_lower_dominant] = 1
    signal_reason[rev_mask & is_upper_dominant] = "上影线反转"
    signal_reason[rev_mask & is_lower_dominant] = "下影线反转"

    # --- 2) 外包K线 + 大尾巴 → 弱信号 ---
    outside_signal = (
        is_outside
        & ~rev_mask
        & (tail_pct >= OUTSIDE_TAIL_THRESHOLD)
        & has_dominant_tail
    )
    is_signal[outside_signal] = True
    signal_dir[outside_signal & is_upper_dominant] = -1
    signal_dir[outside_signal & is_lower_dominant] = 1
    signal_reason[outside_signal & is_upper_dominant] = "外包K线+上影线扩张"
    signal_reason[outside_signal & is_lower_dominant] = "外包K线+下影线扩张"

    # --- 3) 趋势K线受阻 → 弱信号 ---
    trend_blocked = (
        is_trend
        & ~rev_mask
        & ~outside_signal
        & (tail_pct >= TREND_BLOCKED_TAIL_THRESHOLD)
        & has_dominant_tail
    )
    is_signal[trend_blocked] = True
    signal_dir[trend_blocked & is_upper_dominant] = -1
    signal_dir[trend_blocked & is_lower_dominant] = 1
    signal_reason[trend_blocked & is_upper_dominant] = "趋势K线+上影线受阻"
    signal_reason[trend_blocked & is_lower_dominant] = "趋势K线+下影线受阻"

    # ── 质量评级 ──
    # A级: 反转 + 小实体 + 大尾巴
    a_mask = (
        rev_mask
        & (body_pct <= SIGNAL_A_BODY_THRESHOLD)
        & (tail_pct >= SIGNAL_A_TAIL_THRESHOLD)
    )
    signal_quality[a_mask] = "A"
    # B级: 其他反转
    b_mask = rev_mask & ~a_mask
    signal_quality[b_mask] = "B"
    # C级: 其他信号
    c_mask = is_signal & ~rev_mask
    signal_quality[c_mask] = "C"

    # A级追加 "大尾巴小实体" 到理由
    for i in np.where(a_mask)[0]:
        if signal_reason[i]:
            signal_reason[i] = signal_reason[i] + " + 大尾巴小实体"
        else:
            signal_reason[i] = "大尾巴小实体"

    # ── always_in 过滤 ──
    if always_in_series is not None:
        ai = np.asarray(always_in_series)
        filter_long = (ai == "long") & (signal_dir != 1)
        filter_short = (ai == "short") & (signal_dir != -1)
        to_remove = filter_long | filter_short
        is_signal[to_remove] = False
        signal_quality[to_remove] = ""
        signal_dir[to_remove] = 0
        signal_reason[to_remove] = ""

    # ── 写入结果 ──
    result["bar_type"] = pd.Series(type_arr, index=result.index)
    result["body_pct"] = body_pct
    result["tail_pct"] = tail_pct
    result["is_inside"] = is_inside
    result["is_outside"] = is_outside
    result["is_doji"] = is_doji
    result["is_trend"] = is_trend
    result["is_reversal"] = is_reversal
    result["is_signal_bar"] = is_signal
    result["signal_bar_quality"] = pd.Series(signal_quality, index=result.index)
    result["signal_bar_direction"] = signal_dir
    result["signal_bar_reason"] = pd.Series(signal_reason, index=result.index)

    return result


def _empty_batch_result(df: pd.DataFrame) -> pd.DataFrame:
    """空 DataFrame → 返回带空列的副本"""
    result = df.copy()
    result["bar_type"] = pd.Series(dtype="str")
    result["body_pct"] = pd.Series(dtype="float64")
    result["tail_pct"] = pd.Series(dtype="float64")
    result["is_inside"] = pd.Series(dtype="bool")
    result["is_outside"] = pd.Series(dtype="bool")
    result["is_doji"] = pd.Series(dtype="bool")
    result["is_trend"] = pd.Series(dtype="bool")
    result["is_reversal"] = pd.Series(dtype="bool")
    result["is_signal_bar"] = pd.Series(dtype="bool")
    result["signal_bar_quality"] = pd.Series(dtype="str")
    result["signal_bar_direction"] = pd.Series(dtype="int64")
    result["signal_bar_reason"] = pd.Series(dtype="str")
    return result
