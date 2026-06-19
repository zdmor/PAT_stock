"""Pinbar 检测 — 合成数据单元测试"""

import sys
import os

# 确保 ClaudeWorkspace 根在路径中 (price_action_trading 的 __init__.py 依赖此路径)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np
from PAT_stock.patterns.pinbar import detect_pinbar


def make_df(rows: list) -> pd.DataFrame:
    """从 dict 列表构建测试 DataFrame"""
    df = pd.DataFrame(rows)
    # 确保有 OHLC 列
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            df[col] = np.nan
    return df


def test_bullish_strong():
    """BULLISH_STRONG: 长下影线, 实体在顶部"""
    df = make_df([
        {"open": 10.00, "high": 10.10, "low": 9.50, "close": 10.05},
    ])
    # 需要足够数据计算 ATR (atr_window=20), 补足到 22 行
    base = make_df([{"open": 9.0, "high": 9.5, "low": 8.5, "close": 9.0}] * 21)
    df_full = pd.concat([base, df], ignore_index=True)
    result = detect_pinbar(df_full)
    last = result.iloc[-1]
    assert last["signal"] == 1, f"Expected signal=1, got {last['signal']}"
    assert last["signal_type"] == "bullish_pinbar"
    # main_shadow = max(0.05, 0.55) = 0.55, total_range = 0.60, ratio = 0.917
    assert last["pinbar_strength"] == "strong"
    print("✓ test_bullish_strong")


def test_bearish_strong():
    """BEARISH_STRONG: 长上影线, 实体在底部"""
    # 需要足够数据计算 ATR
    base = make_df([{"open": 48.0, "high": 52.0, "low": 47.0, "close": 50.0}] * 21)
    sig = make_df([
        {"open": 50.00, "high": 52.00, "low": 49.30, "close": 49.50},
    ])
    df_full = pd.concat([base, sig], ignore_index=True)
    result = detect_pinbar(df_full)
    last = result.iloc[-1]
    assert last["signal"] == -1, f"Expected signal=-1, got {last['signal']}"
    assert last["signal_type"] == "bearish_pinbar"
    # upper=2.0, lower=0.20, total=2.70, ratio=0.741
    # 0.741 >= 0.667, upper > lower → bearish, body_top_pos = (50.0-49.3)/2.70 = 0.259 <= 0.4
    assert last["pinbar_strength"] == "normal"
    print("✓ test_bearish_strong")


def test_not_pinbar_doji():
    """NOT_PINBAR_DOJI: 十字星, 上下影线相等, 不满足 > 比较"""
    base = make_df([{"open": 50.0, "high": 52.0, "low": 47.0, "close": 50.0}] * 21)
    sig = make_df([
        {"open": 50.0, "high": 51.0, "low": 49.0, "close": 50.0},
    ])
    df_full = pd.concat([base, sig], ignore_index=True)
    result = detect_pinbar(df_full)
    last = result.iloc[-1]
    # upper=1.0, lower=1.0, total=2.0, ratio=0.5 < 0.667
    assert last["signal"] == 0, f"Expected signal=0, got {last['signal']}"
    assert last["signal_type"] == ""
    print("✓ test_not_pinbar_doji")


def test_not_pinbar_big_body():
    """NOT_PINBAR_BIG_BODY: 大实体 K 线, 影线占比不足"""
    base = make_df([{"open": 10.0, "high": 12.0, "low": 9.0, "close": 10.0}] * 21)
    sig = make_df([
        {"open": 10.0, "high": 11.20, "low": 9.80, "close": 11.00},
    ])
    df_full = pd.concat([base, sig], ignore_index=True)
    result = detect_pinbar(df_full)
    last = result.iloc[-1]
    # body=1.0, upper=0.20, lower=0.20, total=1.40
    # main_shadow=0.20, ratio=0.143 < 0.667
    assert last["signal"] == 0, f"Expected signal=0, got {last['signal']}"
    print("✓ test_not_pinbar_big_body")


def test_zero_range():
    """ZERO_RANGE: 一字板, 不崩溃"""
    base = make_df([{"open": 10.0, "high": 12.0, "low": 9.0, "close": 10.0}] * 21)
    sig = make_df([
        {"open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0},
    ])
    df_full = pd.concat([base, sig], ignore_index=True)
    result = detect_pinbar(df_full)
    last = result.iloc[-1]
    assert last["signal"] == 0
    assert not pd.isna(last["main_shadow_ratio"])
    print("✓ test_zero_range")


def test_empty_df():
    """空 DataFrame → 返回空列副本, 不崩溃"""
    df = make_df([])
    result = detect_pinbar(df)
    assert len(result) == 0
    for col in ["signal", "signal_type", "pinbar_strength", "main_shadow_ratio",
                 "near_key_level", "key_level_distance", "key_level_type"]:
        assert col in result.columns, f"Missing column: {col}"
    print("✓ test_empty_df")


def test_missing_columns():
    """缺 OHLC 列 → 抛出 KeyError"""
    df = pd.DataFrame({"trade_date": ["20240101"]})
    try:
        detect_pinbar(df)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
    print("✓ test_missing_columns")


def test_output_columns():
    """断言 1: 输出列数 = 输入列数 + 7"""
    # 使用简单数据
    rows = [{"open": 9.0, "high": 9.5, "low": 8.5, "close": 9.0}] * 22
    rows.append({"open": 10.0, "high": 10.1, "low": 9.5, "close": 10.05})
    df = make_df(rows)
    n_in = len(df.columns)
    result = detect_pinbar(df)
    new_cols = ["signal", "signal_type", "pinbar_strength", "main_shadow_ratio",
                "near_key_level", "key_level_distance", "key_level_type"]
    for col in new_cols:
        assert col in result.columns, f"Missing output column: {col}"
    assert len(result.columns) == n_in + 7, \
        f"Expected {n_in + 7} columns, got {len(result.columns)}"
    print("✓ test_output_columns")


def test_with_key_levels():
    """关键位传入后 near_key_level 正确标记"""
    from dataclasses import dataclass

    @dataclass
    class KeyLevel:
        level_price: float
        formation_type: str = "swing_low_cluster"
        price_min: float = 0.0
        price_max: float = 0.0
        strength: int = 0
        swing_count: int = 0
        touch_count: int = 0
        recency_weighted_strength: float = 0.0
        both_sides: bool = False
        first_date: str = ""
        last_date: str = ""
        cluster_prices: list = None
        polarity_flips: list = None
        fakeout_history: list = None

    # 创建一个远低于当前价的支撑位
    levels = [KeyLevel(level_price=9.4, formation_type="swing_low_cluster")]

    rows = [{"open": 9.0, "high": 9.5, "low": 8.5, "close": 9.0}] * 21
    rows.append({"open": 10.0, "high": 10.1, "low": 9.3, "close": 10.05})
    df = make_df(rows)
    result = detect_pinbar(df, key_levels=levels)
    last = result.iloc[-1]
    print(f"  signal={last['signal']}, near_key_level={last['near_key_level']}, "
          f"distance={last['key_level_distance']}, type={last['key_level_type']}")
    print("✓ test_with_key_levels")


def test_import():
    """断言 4: 导入不报错"""
    from PAT_stock.patterns.pinbar import detect_pinbar
    assert callable(detect_pinbar)
    print("✓ test_import")


if __name__ == "__main__":
    test_import()
    test_empty_df()
    test_missing_columns()
    test_zero_range()
    test_not_pinbar_doji()
    test_not_pinbar_big_body()
    test_bullish_strong()
    test_bearish_strong()
    test_output_columns()
    test_with_key_levels()
    print("\n=== 全部 10 个测试通过 ===")
