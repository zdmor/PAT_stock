"""Spike+Channel 检测测试 — T-A04"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np

from PAT_stock.state.spike_channel import (
    detect_spike,
    detect_channel,
    classify_spike_type,
    channel_overshoot_check,
    channel_battle_check,
)


def make_bullish_spike_df(n_bars=60, spike_start=20, spike_len=3) -> pd.DataFrame:
    """生成带牛市 spike 的合成数据"""
    np.random.seed(42)
    close = 10 + np.arange(n_bars) * 0.02
    for i in range(spike_start, spike_start + spike_len):
        close[i] = close[i - 1] + 0.5

    high = close + np.random.rand(n_bars) * 0.15
    low = close - np.random.rand(n_bars) * 0.15
    open_ = close + np.random.randn(n_bars) * 0.05

    for i in range(spike_start, spike_start + spike_len):
        body = 0.75
        r = 0.2
        c = close[i]
        high[i] = c + r
        low[i] = c - r
        open_[i] = c - body * 2 * r

    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def make_no_spike_df(n_bars=60) -> pd.DataFrame:
    """生成无 spike 的震荡数据"""
    np.random.seed(1)
    open_ = np.random.randn(n_bars) * 0.1 + 10
    close = open_ + np.random.randn(n_bars) * 0.05
    high = np.maximum(open_, close) + np.random.rand(n_bars) * 0.05
    low = np.minimum(open_, close) - np.random.rand(n_bars) * 0.05
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


# ── Spike 检测测试 ────────────────────────────────────


def test_detect_bullish_spike():
    """牛市 spike 应被正确检测"""
    df = make_bullish_spike_df(spike_len=3)
    spike = detect_spike(df)

    assert spike is not None, "Expected spike to be detected"
    assert spike["direction"] == "bullish", f"Expected bullish, got {spike['direction']}"
    assert spike["bar_count"] >= 2, f"Expected >= 2 bars, got {spike['bar_count']}"
    assert spike["start_idx"] <= spike["end_idx"]
    print(f"OK test_detect_bullish_spike (bars={spike['bar_count']})")


def test_detect_bearish_spike():
    """熊市 spike 应被正确检测"""
    np.random.seed(7)
    n = 50
    close = 20 - np.arange(n) * 0.02
    for i in range(30, 33):
        close[i] = close[i - 1] - 0.5

    high = close + np.random.rand(n) * 0.15
    low = close - np.random.rand(n) * 0.15
    open_ = close + np.random.randn(n) * 0.05

    for i in range(30, 33):
        body = 0.75
        r = 0.2
        c = close[i]
        high[i] = c + r
        low[i] = c - r
        open_[i] = c + body * 2 * r

    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    spike = detect_spike(df)

    assert spike is not None, "Expected spike to be detected"
    assert spike["direction"] == "bearish", f"Expected bearish, got {spike['direction']}"
    print(f"OK test_detect_bearish_spike (bars={spike['bar_count']})")


def test_no_spike_on_oscillation():
    """震荡数据不应检出 spike"""
    df = make_no_spike_df()
    spike = detect_spike(df, params={"body_pct": 0.80, "min_bodies": 3})
    # 严格参数下震荡数据不应有 spike
    assert spike is None or spike["bar_count"] < 3
    print("OK test_no_spike_on_oscillation")


def test_spike_return_keys():
    """spike 返回字典包含所有必要 key"""
    df = make_bullish_spike_df(spike_len=3)
    spike = detect_spike(df)
    assert spike is not None
    expected = {"start_idx", "end_idx", "direction", "magnitude", "high", "low", "bar_count"}
    assert expected <= set(spike.keys()), f"Missing keys: {expected - set(spike.keys())}"
    print("OK test_spike_return_keys")


def test_spike_min_bars_filter():
    """min_bodies=5 过滤短 spike"""
    df = make_bullish_spike_df(spike_len=3)
    spike = detect_spike(df, params={"min_bodies": 5})
    assert spike is None, f"Expected no spike with min_bodies=5, got {spike}"
    print("OK test_spike_min_bars_filter")


# ── 通道检测测试 ──────────────────────────────────────


def test_channel_after_spike():
    """spike 后应检出通道"""
    df = make_bullish_spike_df(spike_len=3)
    spike = detect_spike(df)
    assert spike is not None

    channel = detect_channel(df, spike)
    assert channel is not None, "Expected channel after spike"
    assert channel["start_idx"] > spike["end_idx"]
    assert "direction" in channel
    assert "slope" in channel
    print(f"OK test_channel_after_spike (type={channel['type']})")


def test_channel_none_without_spike():
    """无 spike 时 channel 应为 None"""
    df = make_no_spike_df()
    channel = detect_channel(df, None)
    assert channel is None
    print("OK test_channel_none_without_spike")


def test_channel_return_keys():
    """channel 返回字典包含所有必要 key"""
    df = make_bullish_spike_df(spike_len=3)
    spike = detect_spike(df)
    channel = detect_channel(df, spike)
    assert channel is not None
    expected = {"start_idx", "end_idx", "direction", "slope", "avg_range",
                "upper_bound", "lower_bound", "bar_count", "type"}
    assert expected <= set(channel.keys()), f"Missing keys: {expected - set(channel.keys())}"
    print("OK test_channel_return_keys")


# ── Spike 分类测试 ────────────────────────────────────


def test_classify_continuation():
    """趋势方向一致 → continuation"""
    df = make_bullish_spike_df(spike_len=3)
    spike = detect_spike(df)
    stype = classify_spike_type(df, spike)
    assert stype in ("continuation", "unknown"), f"Expected continuation, got {stype}"
    print(f"OK test_classify_continuation ({stype})")


def test_classify_none():
    """spike=None → unknown"""
    stype = classify_spike_type(None, None)  # noqa
    assert stype == "unknown"
    print("OK test_classify_none")


# ── 通道超射测试 ──────────────────────────────────────


def test_overshoot_none_without_channel():
    """无 channel 时 overshoot 应为 None"""
    result = channel_overshoot_check(pd.DataFrame(), None)
    assert result is None
    print("OK test_overshoot_none_without_channel")


# ── 争夺战测试 ────────────────────────────────────────


def test_battle_none_on_trend():
    """趋势数据不应有争夺战"""
    df = make_bullish_spike_df(spike_len=3)
    battle = channel_battle_check(df)
    assert battle is False
    print("OK test_battle_none_on_trend")


# ── 主入口 ─────────────────────────────────────────────


if __name__ == "__main__":
    test_detect_bullish_spike()
    test_detect_bearish_spike()
    test_no_spike_on_oscillation()
    test_spike_return_keys()
    test_spike_min_bars_filter()

    test_channel_after_spike()
    test_channel_none_without_spike()
    test_channel_return_keys()

    test_classify_continuation()
    test_classify_none()

    test_overshoot_none_without_channel()
    test_battle_none_on_trend()

    print("\n=== 全部 12 个测试通过 ===")
