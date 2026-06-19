"""信号K线识别 — 合成数据单元测试

覆盖 classify_bar / detect_signal_bar / detect_two_bar_reversal /
detect_three_bar_reversal / detect_signal_bars_batch.

共 13 个测试, 运行: python test_signal_bar.py
"""

import sys
import os

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

import pandas as pd
import numpy as np
from PAT_stock.patterns.signal_bar import (
    classify_bar,
    detect_signal_bar,
    detect_two_bar_reversal,
    detect_three_bar_reversal,
    detect_signal_bars_batch,
)


def make_df(rows: list) -> pd.DataFrame:
    """从 dict 列表构建测试 DataFrame"""
    df = pd.DataFrame(rows)
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            df[col] = np.nan
    return df


# ── classify_bar ────────────────────────────────────────

def test_classify_trend_bar():
    """趋势K线: body_pct >= 70% → type='trend'"""
    df = make_df([
        {"open": 100.0, "high": 115.0, "low": 98.0, "close": 113.0},
    ])
    # body=13, range=17, body_pct=0.765 → trend
    result = classify_bar(df, 0)
    assert result["type"] == "trend", f"Expected trend, got {result['type']}"
    assert result["is_trend"] == True
    assert result["body_pct"] >= 0.70
    assert result["is_bullish"] == True
    print("  bar: body_pct={:.3f} type={}".format(result["body_pct"], result["type"]))
    print("  PASS: test_classify_trend_bar")


def test_classify_doji():
    """Doji: body_pct < 10% → type='doji'"""
    df = make_df([
        {"open": 100.0, "high": 105.0, "low": 95.0, "close": 100.5},
    ])
    # body=0.5, range=10, body_pct=0.05 → doji
    result = classify_bar(df, 0)
    assert result["type"] == "doji", f"Expected doji, got {result['type']}"
    assert result["is_doji"] == True
    assert result["body_pct"] < 0.10
    print("  bar: body_pct={:.3f} type={}".format(result["body_pct"], result["type"]))
    print("  PASS test_classify_doji")


def test_classify_inside_bar():
    """内包K线: h<prev_h & l>prev_l → type='inside'"""
    df = make_df([
        {"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0},
        {"open": 103.0, "high": 107.0, "low": 97.0, "close": 104.0},
    ])
    # Bar 1: h=107<110 PASS, l=97>95 PASS → inside
    result = classify_bar(df, 1)
    assert result["is_inside"] == True, "Expected is_inside=True"
    assert result["type"] == "inside", f"Expected inside, got {result['type']}"
    print("  bar: h={} prev_h={} l={} prev_l={}".format(
        df.iloc[1]["high"], df.iloc[0]["high"],
        df.iloc[1]["low"], df.iloc[0]["low"]))
    print("  PASS test_classify_inside_bar")


def test_classify_outside_bar():
    """外包K线: h>prev_h & l<prev_l → type='outside'"""
    df = make_df([
        {"open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0},
        {"open": 102.0, "high": 115.0, "low": 93.0, "close": 108.0},
    ])
    # Bar 1: h=115>110 PASS, l=93<95 PASS → outside
    result = classify_bar(df, 1)
    assert result["is_outside"] == True, "Expected is_outside=True"
    assert result["type"] == "outside", f"Expected outside, got {result['type']}"
    print("  bar: h={} prev_h={} l={} prev_l={}".format(
        df.iloc[1]["high"], df.iloc[0]["high"],
        df.iloc[1]["low"], df.iloc[0]["low"]))
    print("  PASS test_classify_outside_bar")


def test_classify_reversal_bar():
    """反转K线: 尾巴 > 实体2倍 + 与趋势相反 → type='reversal'"""
    # 5根上涨趋势 + 1根长上影反转
    data = {
        "open":  [100.0, 101.0, 103.0, 105.0, 107.0, 110.0],
        "high":  [102.0, 104.0, 106.0, 108.0, 110.0, 120.0],
        "low":   [99.0,  100.0, 102.0, 104.0, 106.0, 108.0],
        "close": [101.0, 103.0, 105.0, 107.0, 109.0, 109.0],
    }
    df = make_df(data)
    # Bar 5: body=1, range=12, body_pct=0.083
    #        up_shadow=10, lo_shadow=1, main_tail=upper
    #        max_tail=10 >= body*2=2 PASS, trend_dir>0 PASS
    result = classify_bar(df, 5)
    assert result["is_reversal"] == True, "Expected is_reversal=True"
    assert result["type"] == "reversal", f"Expected reversal, got {result['type']}"
    assert result["main_tail"] == "upper"
    print("  bar: body_pct={:.3f} tail_pct={:.3f} main_tail={}".format(
        result["body_pct"], result["tail_pct"], result["main_tail"]))
    print("  PASS test_classify_reversal_bar")


# ── detect_signal_bar ──────────────────────────────────

def test_detect_signal_bar_reversal():
    """反转K线应被 detect_signal_bar 检出"""
    data = {
        "open":  [100.0, 101.0, 103.0, 105.0, 107.0, 110.0],
        "high":  [102.0, 104.0, 106.0, 108.0, 110.0, 120.0],
        "low":   [99.0,  100.0, 102.0, 104.0, 106.0, 108.0],
        "close": [101.0, 103.0, 105.0, 107.0, 109.0, 109.0],
    }
    df = make_df(data)
    result = detect_signal_bar(df, 5)
    assert result["is_signal"] == True, "Expected is_signal=True"
    assert result["direction"] == -1, "Expected bearish (-1)"
    # body_pct=0.083 <= 0.35, tail_pct=10/12=0.833 >= 0.55 → A级
    assert result["quality"] == "A", f"Expected quality A, got {result['quality']}"
    print("  signal: dir={} quality={} reason='{}'".format(
        result["direction"], result["quality"], result["reason"]))
    print("  PASS test_detect_signal_bar_reversal")


def test_detect_signal_bar_always_in_filter():
    """always_in='long' 过滤空头信号, always_in='short' 保留"""
    data = {
        "open":  [100.0, 101.0, 103.0, 105.0, 107.0, 110.0],
        "high":  [102.0, 104.0, 106.0, 108.0, 110.0, 120.0],
        "low":   [99.0,  100.0, 102.0, 104.0, 106.0, 108.0],
        "close": [101.0, 103.0, 105.0, 107.0, 109.0, 109.0],
    }
    df = make_df(data)

    # always_in='long' → direction=-1 (空头) 被过滤
    result_long = detect_signal_bar(df, 5, always_in="long")
    assert result_long["is_signal"] == False, (
        f"always_in='long' 应过滤空头信号, 但 is_signal={result_long['is_signal']}"
    )

    # always_in='short' → direction=-1 通过
    result_short = detect_signal_bar(df, 5, always_in="short")
    assert result_short["is_signal"] == True
    assert result_short["direction"] == -1

    # always_in='' → 所有信号通过
    result_empty = detect_signal_bar(df, 5, always_in="")
    assert result_empty["is_signal"] == True
    assert result_empty["direction"] == -1

    print("  long: is_signal={} short: is_signal={} empty: is_signal={}".format(
        result_long["is_signal"], result_short["is_signal"], result_empty["is_signal"]))
    print("  PASS test_detect_signal_bar_always_in_filter")


# ── detect_two_bar_reversal ────────────────────────────

def test_two_bar_reversal():
    """两棒反转: 趋势K线 + 反向趋势K线, 实体相当"""
    df = make_df([
        {"open": 100.0, "high": 115.0, "low": 98.0,  "close": 113.0},  # trend bullish
        {"open": 113.0, "high": 114.0, "low": 100.0, "close": 101.0},  # trend bearish
    ])
    # Bar 0: body=13, range=17, body_pct=0.765 → trend
    # Bar 1: body=12, range=14, body_pct=0.857 → trend
    # similarity: 12/13=0.923 >= 0.6 PASS
    result = detect_two_bar_reversal(df, 1)
    assert result is not None, "Expected two-bar reversal, got None"
    assert result["direction"] == -1, f"Expected bearish(-1), got {result['direction']}"
    assert result["strength"] == "strong", (
        f"Expected strong (0.923>=0.8), got {result['strength']}"
    )
    print("  dir={} strength={} bars=({}, {})".format(
        result["direction"], result["strength"],
        result["first_bar_type"], result["second_bar_type"]))
    print("  PASS test_two_bar_reversal")


# ── detect_three_bar_reversal ──────────────────────────

def test_three_bar_reversal():
    """三棒反转 (1-2-3模式): 趋势+调整/Doji+反向趋势"""
    df = make_df([
        {"open": 100.0, "high": 115.0, "low": 98.0,  "close": 113.0},  # 0: trend bullish
        {"open": 110.0, "high": 112.0, "low": 108.0, "close": 110.3},  # 1: inside+doji
        {"open": 100.0, "high": 102.0, "low": 88.0,  "close": 90.0},   # 2: trend bearish
    ])
    # Bar 1: body=0.3, range=4, body_pct=0.075 → doji PASS
    #        h=112<115, l=108>98 → inside PASS
    # Bar 2: body=10, range=14, body_pct=0.714 → trend PASS, bearish
    result = detect_three_bar_reversal(df, 2)
    assert result is not None, "Expected three-bar reversal, got None"
    assert result["pattern"] == "1-2-3 reversal"
    assert result["direction"] == -1, f"Expected bearish(-1), got {result['direction']}"
    assert result["strength"] == "strong", (
        "Bar 1 is inside, expected strength='strong'"
    )
    print("  dir={} strength={} bars=({}, {}, {})".format(
        result["direction"], result["strength"],
        result["first_bar"], result["second_bar"], result["third_bar"]))
    print("  PASS test_three_bar_reversal")


# ── detect_signal_bars_batch ──────────────────────────

def test_batch_detection():
    """批量检测: 返回正确的列结构和信号标记"""
    df = make_df([
        {"open": 100.0, "high": 102.0, "low": 99.0,  "close": 101.0},
        {"open": 101.0, "high": 104.0, "low": 100.0, "close": 103.0},
        {"open": 103.0, "high": 106.0, "low": 102.0, "close": 105.0},
        {"open": 105.0, "high": 108.0, "low": 104.0, "close": 107.0},
        {"open": 107.0, "high": 110.0, "low": 106.0, "close": 109.0},
        # idx=5: reversal bar (uptrend + long upper shadow)
        {"open": 110.0, "high": 120.0, "low": 108.0, "close": 109.0},
        # idx=6: inside bar (h<120 & l>108)
        {"open": 112.0, "high": 115.0, "low": 109.0, "close": 113.0},
    ])
    result = detect_signal_bars_batch(df)

    # 检查列存在
    expected_cols = [
        "bar_type", "body_pct", "tail_pct", "is_inside", "is_outside",
        "is_doji", "is_trend", "is_reversal", "is_signal_bar",
        "signal_bar_quality", "signal_bar_direction", "signal_bar_reason",
    ]
    for col in expected_cols:
        assert col in result.columns, f"Missing column: {col}"

    # 列数 = 输入列数 + 12
    assert len(result.columns) == len(df.columns) + len(expected_cols), (
        f"Expected {len(df.columns) + len(expected_cols)} columns, "
        f"got {len(result.columns)}"
    )

    # idx=5: 反转K线, 应为信号
    assert result.iloc[5]["is_reversal"] == True, "Bar 5 should be reversal"
    assert result.iloc[5]["is_signal_bar"] == True, "Bar 5 should be signal"
    assert result.iloc[5]["signal_bar_direction"] == -1
    assert result.iloc[5]["signal_bar_quality"] in ("A", "B")

    # idx=6: 内包K线, 不是信号
    assert result.iloc[6]["bar_type"] == "inside", "Bar 6 should be inside"
    assert result.iloc[6]["is_signal_bar"] == False, "Bar 6 should not be signal"

    print("  columns added: {}".format(len(expected_cols)))
    print("  bar[5]: type={} signal={} dir={} quality={}".format(
        result.iloc[5]["bar_type"], result.iloc[5]["is_signal_bar"],
        result.iloc[5]["signal_bar_direction"], result.iloc[5]["signal_bar_quality"]))
    print("  bar[6]: type={} signal={}".format(
        result.iloc[6]["bar_type"], result.iloc[6]["is_signal_bar"]))
    print("  PASS test_batch_detection")


# ── 边界情况 ───────────────────────────────────────────

def test_empty_df():
    """空 DataFrame → 返回空列副本, 不崩溃"""
    df = make_df([])
    result = detect_signal_bars_batch(df)
    assert len(result) == 0
    for col in ["bar_type", "body_pct", "is_signal_bar", "signal_bar_quality",
                "signal_bar_direction", "signal_bar_reason"]:
        assert col in result.columns, f"Missing column: {col}"
    print("  PASS test_empty_df")


def test_missing_columns():
    """缺 OHLC 列 → 抛出 KeyError"""
    df = pd.DataFrame({"trade_date": ["20240101"]})
    try:
        classify_bar(df, 0)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
    try:
        detect_signal_bars_batch(df)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
    print("  PASS test_missing_columns")


def test_invalid_always_in():
    """无效 always_in 参数 → 抛出 ValueError"""
    df = make_df([{"open": 100, "high": 105, "low": 95, "close": 102}])
    try:
        detect_signal_bar(df, 0, always_in="invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("  PASS test_invalid_always_in")


def test_idx_bounds():
    """越界 idx → 抛出 IndexError"""
    df = make_df([{"open": 100, "high": 105, "low": 95, "close": 102}])
    try:
        classify_bar(df, 10)
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    try:
        detect_two_bar_reversal(df, 0)  # idx=0 < 1
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    try:
        detect_three_bar_reversal(df, 1)  # idx=1 < 2
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    print("  PASS test_idx_bounds")


def test_two_bar_reversal_none():
    """非匹配场景返回 None (同向趋势K线)"""
    df = make_df([
        {"open": 100.0, "high": 115.0, "low": 98.0,  "close": 113.0},  # trend bullish
        {"open": 105.0, "high": 118.0, "low": 103.0, "close": 116.0},  # trend bullish (同向)
    ])
    result = detect_two_bar_reversal(df, 1)
    assert result is None, "同向趋势K线应返回 None"
    print("  PASS test_two_bar_reversal_none")


def test_three_bar_reversal_none():
    """非匹配场景返回 None (第一棒非趋势)"""
    df = make_df([
        {"open": 100.0, "high": 105.0, "low": 98.0,  "close": 102.0},  # normal
        {"open": 102.0, "high": 107.0, "low": 100.0, "close": 105.0},  # normal
        {"open": 105.0, "high": 108.0, "low": 103.0, "close": 106.0},  # normal
    ])
    result = detect_three_bar_reversal(df, 2)
    assert result is None, "第一棒非趋势应返回 None"
    print("  PASS test_three_bar_reversal_none")


if __name__ == "__main__":
    test_classify_trend_bar()
    test_classify_doji()
    test_classify_inside_bar()
    test_classify_outside_bar()
    test_classify_reversal_bar()
    test_detect_signal_bar_reversal()
    test_detect_signal_bar_always_in_filter()
    test_two_bar_reversal()
    test_three_bar_reversal()
    test_batch_detection()
    test_empty_df()
    test_missing_columns()
    test_invalid_always_in()
    test_idx_bounds()
    test_two_bar_reversal_none()
    test_three_bar_reversal_none()
    print("\n=== 全部 16 个测试通过 ===")
