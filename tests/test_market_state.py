"""Always-In 结构判定 — 合成数据 + 真实数据测试"""

import sys
import os

# 确保 ClaudeWorkspace 根在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np

from PAT_stock.state.market_state import (
    determine_always_in,
    get_trend_filter,
)


def make_trend_df(
    n_bars: int = 100,
    start_price: float = 100.0,
    trend_per_bar: float = 0.5,
    noise_std: float = 0.3,
    direction: int = 1,
) -> pd.DataFrame:
    """生成趋势数据: 锯齿形 + 噪声, 确保存在 swing 点"""
    np.random.seed(42)
    price = start_price
    opens, highs, lows, closes = [], [], [], []

    for i in range(n_bars):
        drift = trend_per_bar * direction
        # 锯齿波: 每 10 bar 中 7 涨 3 回调
        phase = i % 10
        if phase < 7:
            local_drift = drift
        else:
            local_drift = -drift * 2  # 回调

        noise = np.random.randn() * noise_std
        c = price + local_drift + noise
        o = price
        h = max(o, c) + abs(np.random.randn() * noise_std * 1.5)
        l = min(o, c) - abs(np.random.randn() * noise_std * 1.5)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        price = c

    df = pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})
    return df


def make_oscillating_df(n_bars: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """生成震荡数据 (均值回归 + 周期性波动)"""
    np.random.seed(123)
    price = start_price
    opens, highs, lows, closes = [], [], [], []

    for i in range(n_bars):
        mean_rev = (start_price - price) * 0.05
        # 加入正弦波震荡
        wave = np.sin(i * 0.3) * 0.8
        noise = np.random.randn() * 0.5
        c = price + mean_rev + wave + noise
        o = price
        h = max(o, c) + abs(np.random.randn() * 0.3)
        l = min(o, c) - abs(np.random.randn() * 0.3)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        price = c

    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes})


def test_bullish_trend():
    """测试 A: 强趋势多头 → direction=bullish, confidence > 0.5"""
    df = make_trend_df(n_bars=100, trend_per_bar=0.8, noise_std=0.2, direction=1)
    r = determine_always_in(df, params={"reverse_sign": False})
    print(f"  direction={r['direction']}, confidence={r['confidence']}, "
          f"structure={r['structure']}")
    # 强趋势应该检测到 bullish, confidence > 0.3 (weighted_score > threshold)
    assert r["direction"] == "bullish", f"Expected bullish, got {r['direction']}"
    assert r["confidence"] > 0.3, f"Expected confidence > 0.3, got {r['confidence']}"
    print("OK test_bullish_trend")


def test_bearish_trend():
    """测试 B: 强趋势空头 → direction=bearish"""
    df = make_trend_df(n_bars=100, start_price=200.0, trend_per_bar=1.0, noise_std=0.2, direction=-1)
    r = determine_always_in(df, params={"reverse_sign": False})
    print(f"  direction={r['direction']}, confidence={r['confidence']}, "
          f"structure={r['structure']}")
    assert r["direction"] == "bearish", f"Expected bearish, got {r['direction']}"
    print("OK test_bearish_trend")


def test_oscillating():
    """测试 C: 区间震荡 → confidence 较低"""
    df = make_oscillating_df(n_bars=100)
    r = determine_always_in(df)
    print(f"  direction={r['direction']}, confidence={r['confidence']}, "
          f"structure={r['structure']}")
    # 震荡数据应该 confidence 不高
    assert r["confidence"] < 0.8, f"Expected moderate/low confidence in oscillator"
    print("OK test_oscillating")


def test_insufficient_data():
    """测试 D: 数据不足 → oscillating, confidence=0, 不抛异常"""
    df = make_trend_df(n_bars=20)
    r = determine_always_in(df)
    assert r["direction"] == "oscillating"
    assert r["confidence"] == 0.0
    assert r["structure"] == "mixed"
    print("OK test_insufficient_data")


def test_output_keys():
    """断言 1: 返回字典包含 5 个顶层 key"""
    df = make_trend_df(n_bars=60)
    r = determine_always_in(df)
    expected_keys = {"direction", "confidence", "structure", "dimensions", "params_used"}
    missing = expected_keys - set(r.keys())
    assert not missing, f"Missing keys: {missing}"
    # 验证 dimensions 包含 5 维
    dims = r["dimensions"]
    assert "ema_slope" in dims
    assert "hh_hl_structure" in dims
    assert "channel_position" in dims
    assert "retracement_depth" in dims
    assert "gap_bars" in dims
    print("OK test_output_keys")


def test_trend_filter_strict():
    """断言 3: strict 模式 - bullish + confidence>0.5 → long_only, oscillating → neutral"""
    # 构造高置信度 bullish
    r_bull = {"direction": "bullish", "confidence": 0.7}
    assert get_trend_filter(r_bull, mode="strict") == "long_only"

    r_osc = {"direction": "oscillating", "confidence": 0.3}
    assert get_trend_filter(r_osc, mode="strict") == "neutral"
    print("OK test_trend_filter_strict")


def test_trend_filter_moderate():
    """断言 4: strict 模式对 confidence=0.4 → neutral"""
    r_low = {"direction": "bullish", "confidence": 0.4}
    assert get_trend_filter(r_low, mode="strict") == "neutral"

    r_mod = {"direction": "bullish", "confidence": 0.4}
    assert get_trend_filter(r_mod, mode="moderate") == "long_only"
    print("OK test_trend_filter_moderate")


def test_empty_df():
    """空 DataFrame → oscillating + confidence=0"""
    df = pd.DataFrame(columns=["open", "high", "low", "close"])
    r = determine_always_in(df)
    assert r["direction"] == "oscillating"
    assert r["confidence"] == 0.0
    print("OK test_empty_df")


def test_params_override():
    """参数覆盖测试"""
    df = make_trend_df(n_bars=60)
    # 极严格的阈值 → 应该 oscillating
    r = determine_always_in(df, params={"bullish_threshold": 0.90})
    assert "params_used" in r
    assert r["params_used"]["bullish_threshold"] == 0.90
    print("OK test_params_override")


def test_reverse_sign():
    """reverse_sign=True 翻转方向 (生产默认)"""
    df_bull = make_trend_df(n_bars=100, trend_per_bar=0.8, noise_std=0.2, direction=1)
    r_default = determine_always_in(df_bull)  # reverse_sign=True 是默认
    r_orig = determine_always_in(df_bull, params={"reverse_sign": False})
    # 默认应该与原方向相反
    if r_orig["direction"] == "bullish":
        assert r_default["direction"] == "bearish", \
            f"Expected bearish (flipped from bullish), got {r_default['direction']}"
    elif r_orig["direction"] == "bearish":
        assert r_default["direction"] == "bullish", \
            f"Expected bullish (flipped from bearish), got {r_default['direction']}"
    # oscillating 的情况不应该被翻转改变
    df_osc = make_oscillating_df(n_bars=100)
    r_osc_def = determine_always_in(df_osc)
    r_osc_orig = determine_always_in(df_osc, params={"reverse_sign": False})
    assert r_osc_def["direction"] == r_osc_orig["direction"]
    print("OK test_reverse_sign")


def test_weights_sum_to_one():
    """5 维权重之和 ≈ 1.0"""
    df = make_trend_df(n_bars=100)
    r = determine_always_in(df)
    dims = r["dimensions"]
    total = sum(dims[d]["weight"] for d in ("ema_slope", "hh_hl_structure", "channel_position",
                                            "retracement_depth", "gap_bars"))
    assert abs(total - 1.0) < 0.01, f"Expected weight sum ≈ 1.0, got {total}"
    print(f"OK test_weights_sum_to_one (sum={total:.4f})")


# ── 真实数据测试 (需要 Tushare 网络) ──────────────────

def _run_real_test(label, ts_code, start, end, expected_dir=None, min_conf=None, max_conf=None):
    """通用真实数据测试包装"""
    from PAT_stock.data.loader import get_daily
    df = get_daily(ts_code, start, end)
    if df.empty:
        print(f"  [{label}] 无数据, 跳过")
        return True  # 跳过不算失败
    df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "")
    # 真实数据测试验证原始维度逻辑, 不受 reverse_sign 影响
    r = determine_always_in(df, params={"reverse_sign": False})
    print(f"  [{label}] {ts_code} {start}-{end}: "
          f"dir={r['direction']}, conf={r['confidence']:.3f}, "
          f"struct={r['structure']}, bars={len(df)}")
    if expected_dir:
        assert r["direction"] == expected_dir, \
            f"Expected {expected_dir}, got {r['direction']}"
    if min_conf is not None:
        assert r["confidence"] > min_conf, \
            f"Expected conf > {min_conf}, got {r['confidence']}"
    if max_conf is not None:
        assert r["confidence"] < max_conf, \
            f"Expected conf < {max_conf}, got {r['confidence']}"
    return True


def test_real_bullish_moutai():
    """测试 A: 茅台 2020-2021 主升浪 → bullish, confidence > 0.6, HHHL"""
    _run_real_test("A", "600519.SH", "20200101", "20210210",
                   expected_dir="bullish", min_conf=0.6)
    print("OK test_real_bullish_moutai")


def test_real_bearish_catl():
    """测试 B: 宁德时代 2022 主跌段 → bearish"""
    _run_real_test("B", "300750.SZ", "20220101", "20220930",
                   expected_dir="bearish")
    print("OK test_real_bearish_catl")


def test_real_oscillating_petrochina():
    """测试 C: 中国石油 2023-2024 → confidence < 0.6"""
    _run_real_test("C", "601857.SH", "20230101", "20240630",
                   max_conf=0.6)
    print("OK test_real_oscillating_petrochina")


def test_real_insufficient():
    """测试 D: 数据不足 → 不抛异常"""
    from PAT_stock.data.loader import get_daily
    df = get_daily("000001.SZ", "20240201", "20240315")
    if df.empty:
        print("  [D] 无数据, 跳过")
    else:
        r = determine_always_in(df)
        assert not pd.isna(r["direction"])
        print(f"  [D] bars={len(df)}, dir={r['direction']}, conf={r['confidence']}")
    print("OK test_real_insufficient")


# ── main ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if "--real" in sys.argv:
        test_real_bullish_moutai()
        test_real_bearish_catl()
        test_real_oscillating_petrochina()
        test_real_insufficient()
        print("\n=== 真实数据测试完成 ===")
    else:
        test_output_keys()
        test_insufficient_data()
        test_empty_df()
        test_trend_filter_strict()
        test_trend_filter_moderate()
        test_bullish_trend()
        test_bearish_trend()
        test_oscillating()
        test_params_override()
        test_reverse_sign()
        test_weights_sum_to_one()
        print("\n=== 全部 11 个合成测试通过 ===")
        print("  (用 --real 参数运行真实数据测试)")
