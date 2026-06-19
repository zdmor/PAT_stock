"""陷阱检测 — 合成数据单元测试

覆盖 4 种陷阱类型 + 边界条件 + detect_all_traps。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np
from PAT_stock.patterns.trap import (
    detect_fake_breakout_trap,
    detect_stop_run_trap,
    detect_climax_trap,
    detect_barbwire_trap,
    detect_all_traps,
)


def make_df(rows: list) -> pd.DataFrame:
    """从 dict 列表构建测试 DataFrame"""
    df = pd.DataFrame(rows)
    for col in ["open", "high", "low", "close"]:
        if col not in df.columns:
            df[col] = np.nan
    if "volume" not in df.columns:
        df["volume"] = 1000
    return df


def _background_bars(n: int = 25, base_price: float = 50.0, volatility: float = 0.5) -> list:
    """生成平稳背景 K 线数据"""
    bars = []
    price = base_price
    for _ in range(n):
        o = price
        h = o + np.random.uniform(0.2, volatility)
        l = o - np.random.uniform(0.2, volatility)
        c = o + np.random.uniform(-0.3, 0.3)
        bars.append({
            "open": round(o, 2),
            "high": round(max(h, o, c) + 0.05, 2),
            "low": round(min(l, o, c) - 0.05, 2),
            "close": round(c, 2),
            "volume": int(1000 + np.random.uniform(-200, 200)),
        })
        price = c
    return bars


# ── 1. Fake Breakout Above Resistance ──


def test_fake_breakout_above_resistance():
    """假突破阻力位 → bearish trap"""
    np.random.seed(42)
    bg = _background_bars(22, base_price=50.0)
    # Bar 22: breakout bar — breaks above 51.0 with long upper wick
    bg.append({
        "open": 50.50, "high": 51.80, "low": 50.30, "close": 50.90,
        "volume": 1200,
    })
    # Bar 23: reversal bar — closes back below 51.0
    bg.append({
        "open": 50.70, "high": 50.85, "low": 50.20, "close": 50.40,
        "volume": 1100,
    })
    # Bar 24: continuation down
    bg.append({
        "open": 50.30, "high": 50.50, "low": 49.80, "close": 50.00,
        "volume": 1000,
    })

    df = make_df(bg)
    key_levels = {"resistance": [51.0], "support": []}
    result = detect_fake_breakout_trap(df, key_levels, atr_window=14, reversal_bars=3)

    assert result is not None, "Expected a fake breakout trap"
    assert result["trap_direction"] == "bearish", (
        f"Expected bearish, got {result['trap_direction']}"
    )
    assert result["type"] == "fake_breakout"
    assert result["signal_bar"] == 22, (
        f"Expected signal_bar=22, got {result['signal_bar']}"
    )
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"signal_bar={result['signal_bar']}")
    print("[OK] test_fake_breakout_above_resistance")


# ── 2. Fake Breakdown Below Support ──


def test_fake_breakdown_below_support():
    """假跌破支撑位 → bullish trap"""
    np.random.seed(42)
    bg = _background_bars(22, base_price=50.0)
    # Bar 22: breakdown bar — breaks below 49.0 with long lower wick
    bg.append({
        "open": 49.30, "high": 49.50, "low": 48.20, "close": 49.10,
        "volume": 1300,
    })
    # Bar 23: reversal bar — closes back above 49.0
    bg.append({
        "open": 49.20, "high": 49.80, "low": 49.00, "close": 49.60,
        "volume": 1100,
    })
    # Bar 24
    bg.append({
        "open": 49.50, "high": 50.10, "low": 49.30, "close": 49.90,
        "volume": 1000,
    })

    df = make_df(bg)
    key_levels = {"resistance": [], "support": [49.0]}
    result = detect_fake_breakout_trap(df, key_levels, atr_window=14, reversal_bars=3)

    assert result is not None, "Expected a fake breakdown trap"
    assert result["trap_direction"] == "bullish", (
        f"Expected bullish, got {result['trap_direction']}"
    )
    assert result["type"] == "fake_breakout"
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"signal_bar={result['signal_bar']}")
    print("[OK] test_fake_breakdown_below_support")


# ── 3. Stop Run at Swing High ──


def test_stop_run_at_swing_high():
    """扫止损 — 穿越 swing high 后反转 → bearish trap"""
    np.random.seed(42)
    bg = _background_bars(22, base_price=50.0, volatility=0.4)
    # Bar 22: runs through swing high 51.0, long upper wick
    bg.append({
        "open": 50.80, "high": 51.60, "low": 50.60, "close": 51.10,
        "volume": 1400,
    })
    # Bar 23: immediate reversal
    bg.append({
        "open": 50.90, "high": 51.00, "low": 50.20, "close": 50.40,
        "volume": 1200,
    })
    bg.append({
        "open": 50.30, "high": 50.50, "low": 50.00, "close": 50.10,
        "volume": 1000,
    })

    df = make_df(bg)
    swing_points = {"high": [51.0], "low": []}
    result = detect_stop_run_trap(
        df, swing_points, atr_window=14, reversal_bars=2, run_buffer_atr=0.05
    )

    assert result is not None, "Expected a stop run trap"
    assert result["trap_direction"] == "bearish", (
        f"Expected bearish, got {result['trap_direction']}"
    )
    assert result["type"] == "stop_run"
    assert result["signal_bar"] == 22, (
        f"Expected signal_bar=22, got {result['signal_bar']}"
    )
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"signal_bar={result['signal_bar']}")
    print("[OK] test_stop_run_at_swing_high")


# ── 4. Stop Run at Swing Low ──


def test_stop_run_at_swing_low():
    """扫止损 — 穿越 swing low 后反转 → bullish trap"""
    np.random.seed(42)
    bg = _background_bars(22, base_price=50.0, volatility=0.4)
    # Bar 22: runs through swing low 49.0, long lower wick
    bg.append({
        "open": 49.30, "high": 49.50, "low": 48.30, "close": 49.10,
        "volume": 1500,
    })
    # Bar 23: immediate reversal
    bg.append({
        "open": 49.40, "high": 50.10, "low": 49.20, "close": 49.90,
        "volume": 1300,
    })
    bg.append({
        "open": 50.00, "high": 50.30, "low": 49.70, "close": 50.20,
        "volume": 1000,
    })

    df = make_df(bg)
    swing_points = {"high": [], "low": [49.0]}
    result = detect_stop_run_trap(
        df, swing_points, atr_window=14, reversal_bars=2, run_buffer_atr=0.05
    )

    assert result is not None, "Expected a stop run trap"
    assert result["trap_direction"] == "bullish", (
        f"Expected bullish, got {result['trap_direction']}"
    )
    assert result["type"] == "stop_run"
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"signal_bar={result['signal_bar']}")
    print("[OK] test_stop_run_at_swing_low")


# ── 5. Climax Reversal (Bullish Climax → Bearish Trap) ──


def test_climax_bull_climax_bearish_trap():
    """多头高潮 → bearish trap: 大绿柱+巨量后反转"""
    np.random.seed(42)
    # 背景: 稳定价格 + 温和成交量
    bg = _background_bars(22, base_price=50.0, volatility=0.3)
    for bar in bg:
        bar["volume"] = int(800 + np.random.uniform(-100, 100))

    # Bar 22: 高潮 — 大绿柱, 成交量 3x
    # Body = 52.5 - 50.5 = 2.0, midpoint = 51.5
    bg.append({
        "open": 50.50, "high": 53.00, "low": 50.20, "close": 52.50,
        "volume": 3000,
    })
    # Bar 23: 反转 — 收盘远低于高潮中点 (50.5 < 51.5)
    # engulf depth = (51.5 - 50.5) / 2.0 = 0.5 >= 0.4
    bg.append({
        "open": 52.00, "high": 52.20, "low": 50.30, "close": 50.50,
        "volume": 1500,
    })
    bg.append({
        "open": 50.50, "high": 51.00, "low": 50.20, "close": 50.80,
        "volume": 1200,
    })

    df = make_df(bg)
    # 确保成交量 MA 稳定
    result = detect_climax_trap(
        df, atr_window=14, vol_ma_period=10, body_mult=1.5, vol_mult=1.8, engulf_frac=0.4
    )

    assert result is not None, "Expected a climax trap"
    assert result["trap_direction"] == "bearish", (
        f"Expected bearish, got {result['trap_direction']}"
    )
    assert result["type"] == "climax"
    assert result["signal_bar"] == 22, (
        f"Expected signal_bar=22, got {result['signal_bar']}"
    )
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"engulf_depth={result.get('engulf_depth', 'N/A'):.3f}, "
          f"body_atr_ratio={result.get('body_atr_ratio', 'N/A'):.3f}")
    print("[OK] test_climax_bull_climax_bearish_trap")


# ── 6. Climax Reversal (Bearish Climax → Bullish Trap) ──


def test_climax_bear_climax_bullish_trap():
    """空头高潮 → bullish trap: 大绿..." 大绿柱? No, 大阴柱"""
    np.random.seed(42)
    bg = _background_bars(22, base_price=52.0, volatility=0.3)
    for bar in bg:
        bar["volume"] = int(800 + np.random.uniform(-100, 100))

    # Bar 22: 高潮 — 大阴柱, 成交量 3x
    # Body = 51.5 - 49.5 = 2.0, midpoint = 50.5
    bg.append({
        "open": 51.50, "high": 51.60, "low": 49.00, "close": 49.50,
        "volume": 3200,
    })
    # Bar 23: 反转 — 收盘远高于高潮中点 (51.5 > 50.5)
    # engulf depth = (51.5 - 50.5) / 2.0 = 0.5 >= 0.4
    bg.append({
        "open": 49.80, "high": 51.80, "low": 49.60, "close": 51.50,
        "volume": 1400,
    })
    bg.append({
        "open": 51.00, "high": 51.50, "low": 50.60, "close": 51.30,
        "volume": 1100,
    })

    df = make_df(bg)
    result = detect_climax_trap(
        df, atr_window=14, vol_ma_period=10, body_mult=1.5, vol_mult=1.8, engulf_frac=0.4
    )

    assert result is not None, "Expected a climax trap"
    assert result["trap_direction"] == "bullish", (
        f"Expected bullish, got {result['trap_direction']}"
    )
    assert result["type"] == "climax"
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"engulf_depth={result.get('engulf_depth', 'N/A'):.3f}")
    print("[OK] test_climax_bear_climax_bullish_trap")


# ── 7. Barbwire Breakout Failure ──


def test_barbwire_breakout_failure():
    """窄区间向上突破失败 → bearish trap"""
    np.random.seed(42)
    # 前景: 5 根窄 K 线区间
    bg = _background_bars(15, base_price=50.0, volatility=0.3)
    # Bars 15-19: 窄区间 (5 bars, 小振幅 ~0.1, 确保 is_small 通过)
    for i in range(5):
        o = 50.0 + i * 0.02
        bg.append({
            "open": round(o, 2),
            "high": round(o + 0.05, 2),
            "low": round(o - 0.05, 2),
            "close": round(o + np.random.uniform(-0.02, 0.02), 2),
            "volume": 600,
        })
    # Bar 20: 向上突破 (close > zone_high ~ 50.06)
    bg.append({
        "open": 50.10, "high": 50.30, "low": 50.00, "close": 50.25,
        "volume": 800,
    })
    # Bar 21: 无后续动能 (小阴)
    bg.append({
        "open": 50.20, "high": 50.25, "low": 49.90, "close": 49.95,
        "volume": 700,
    })

    df = make_df(bg)
    result = detect_barbwire_trap(
        df, atr_window=10, range_ratio=0.6, min_bars=4, breakdown_bars=2
    )

    assert result is not None, "Expected a barbwire trap"
    assert result["trap_direction"] == "bearish", (
        f"Expected bearish, got {result['trap_direction']}"
    )
    assert result["type"] == "barbwire"
    print(f"  trap_direction={result['trap_direction']}, "
          f"confidence={result['confidence']}, "
          f"zone_length={result.get('zone_length', 'N/A')}")
    print("[OK] test_barbwire_breakout_failure")


# ── 8. No Trap — Clean Trend ──


def test_no_trap_clean_trend():
    """无陷阱: 平稳上升趋势, 无反转"""
    np.random.seed(42)
    bars = _background_bars(30, base_price=50.0, volatility=0.4)
    # Smooth uptrend with no reversal
    for i in range(5):
        o = 52.0 + i * 0.5
        bars.append({
            "open": round(o, 2),
            "high": round(o + 0.8, 2),
            "low": round(o - 0.2, 2),
            "close": round(o + 0.4, 2),
            "volume": 1000,
        })

    df = make_df(bars)

    # Fake breakout — no key levels
    result_fb = detect_fake_breakout_trap(df, key_levels={"resistance": [55.0], "support": []})
    assert result_fb is None or result_fb["signal_bar"] < 25, (
        f"Unexpected fake breakout: {result_fb}"
    )

    # Climax — no climax bars (volume too low)
    # Reduce thresholds slightly but should still detect nothing if volume is normal
    # Actually our background has normal volume, so no climax
    result_climax = detect_climax_trap(
        df, atr_window=10, vol_ma_period=10, body_mult=3.0, vol_mult=3.0
    )
    assert result_climax is None, f"Unexpected climax: {result_climax}"

    print("[OK] test_no_trap_clean_trend")


# ── 9. Empty DataFrame ──


def test_empty_df():
    """空 DataFrame → 不崩溃, 返回 None"""
    df = make_df([])
    for detector in [
        lambda: detect_fake_breakout_trap(df, key_levels={"resistance": [50]}),
        lambda: detect_stop_run_trap(df, swing_points={"high": [50]}),
        lambda: detect_climax_trap(df),
        lambda: detect_barbwire_trap(df),
    ]:
        result = detector()
        assert result is None, f"Expected None for empty df"
    print("[OK] test_empty_df")


# ── 10. Missing OHLC Columns ──


def test_missing_columns():
    """缺 OHLC 列 → 抛出 KeyError"""
    df = pd.DataFrame({"trade_date": ["20240101"]})
    try:
        detect_fake_breakout_trap(df, key_levels={"resistance": [50]})
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
    print("[OK] test_missing_columns")


# ── 11. None / Empty key_levels or swing_points ──


def test_none_levels():
    """key_levels=None 或 swing_points=None → 返回 None"""
    np.random.seed(42)
    df = make_df(_background_bars(25, base_price=50.0))

    assert detect_fake_breakout_trap(df, key_levels=None) is None
    assert detect_fake_breakout_trap(df, key_levels={}) is None
    assert detect_stop_run_trap(df, swing_points=None) is None
    assert detect_stop_run_trap(df, swing_points={}) is None
    print("[OK] test_none_levels")


# ── 12. detect_all_traps ──


def test_detect_all_traps():
    """detect_all_traps 收集所有检测器结果"""
    np.random.seed(42)
    bg = _background_bars(22, base_price=50.0)
    # Fake breakout
    bg.append({
        "open": 50.50, "high": 51.80, "low": 50.30, "close": 50.90,
        "volume": 1200,
    })
    bg.append({
        "open": 50.70, "high": 50.85, "low": 50.20, "close": 50.40,
        "volume": 1100,
    })
    bg.append({
        "open": 50.30, "high": 50.50, "low": 49.80, "close": 50.00,
        "volume": 1000,
    })

    df = make_df(bg)
    key_levels = {"resistance": [51.0], "support": []}
    swing_points = {"high": [], "low": []}

    all_traps = detect_all_traps(
        df,
        key_levels=key_levels,
        swing_points=swing_points,
        atr_window=14,
        reversal_bars=3,
    )

    assert len(all_traps) >= 1, f"Expected at least 1 trap, got {len(all_traps)}"
    found_fake = any(t["type"] == "fake_breakout" for t in all_traps)
    assert found_fake, "Expected fake_breakout in all_traps"
    assert all("trap_direction" in t for t in all_traps)
    assert all("confidence" in t for t in all_traps)
    # Sorted by signal_bar descending
    for i in range(len(all_traps) - 1):
        assert all_traps[i]["signal_bar"] >= all_traps[i + 1]["signal_bar"], (
            "Results not sorted by signal_bar descending"
        )
    print(f"  Found {len(all_traps)} trap(s): "
          f"{[(t['type'], t['trap_direction'], t['confidence']) for t in all_traps]}")
    print("[OK] test_detect_all_traps")


# ── 13. Test import ──


def test_import():
    """导入不报错"""
    from PAT_stock.patterns.trap import (
        detect_fake_breakout_trap,
        detect_stop_run_trap,
        detect_climax_trap,
        detect_barbwire_trap,
        detect_all_traps,
    )
    assert callable(detect_fake_breakout_trap)
    assert callable(detect_stop_run_trap)
    assert callable(detect_climax_trap)
    assert callable(detect_barbwire_trap)
    assert callable(detect_all_traps)
    print("[OK] test_import")


# ── main ──


if __name__ == "__main__":
    np.random.seed(42)

    test_import()
    test_empty_df()
    test_missing_columns()
    test_none_levels()
    test_climax_bull_climax_bearish_trap()
    test_climax_bear_climax_bullish_trap()
    test_stop_run_at_swing_high()
    test_stop_run_at_swing_low()
    test_fake_breakout_above_resistance()
    test_fake_breakdown_below_support()
    test_barbwire_breakout_failure()
    test_no_trap_clean_trend()
    test_detect_all_traps()

    print("\n=== All 13 tests PASSED ===")
