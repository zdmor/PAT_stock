"""KeyLevel 水平关键位检测 — 合成数据单元测试

测试覆盖 22 个用例:
  - KeyLevel 数据类 14 字段完整性
  - 空 DataFrame / 数据不足 / 平坦无 swing / 缺失列
  - Swing High / Swing Low 聚类
  - Mixed 聚类 (反向合并)
  - Recency weighting
  - Polarity flip (支撑→阻力)
  - Fakeout (向上 / 向下 / 未收回)
  - levels_near_price / nearest_level / key_levels_summary
  - 集成: 含 trade_date 列
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np
from PAT_stock.patterns.key_levels import (
    detect_key_levels,
    KeyLevel,
    key_levels_summary,
    levels_near_price,
    nearest_level,
    _detect_polarity_flips,
    _detect_fakeouts,
)


# ── 测试数据工厂 ──────────────────────────────────────────


def build_flat_df(n_bars: int = 120, base_price: float = 100.0) -> pd.DataFrame:
    """创建一个近乎平坦的 OHLC DataFrame（轻微上升趋势，避免意外 swing 点）。"""
    t = np.arange(n_bars, dtype=float)
    close = base_price + t * 0.001  # 极缓上升趋势，防止产生意外局部极值
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = close + 0.15
    low = close - 0.15
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


def force_swing_high(df: pd.DataFrame, idx: int, price: float, window: int = 5):
    """强制 idx 位置为 swing high：price 高于左右各 window 根的所有邻居。"""
    n = len(df)
    df.loc[idx, "high"] = price
    start = max(0, idx - window)
    end = min(n, idx + window + 1)
    for j in range(start, end):
        if j != idx:
            df.loc[j, "high"] = price - 0.1


def force_swing_low(df: pd.DataFrame, idx: int, price: float, window: int = 5):
    """强制 idx 位置为 swing low：price 低于左右各 window 根的所有邻居。"""
    n = len(df)
    df.loc[idx, "low"] = price
    start = max(0, idx - window)
    end = min(n, idx + window + 1)
    for j in range(start, end):
        if j != idx:
            df.loc[j, "low"] = price + 0.1


# ── 1. 导入 ──────────────────────────────────────────────


def test_import():
    """导入不报错"""
    from PAT_stock.patterns.key_levels import detect_key_levels, KeyLevel
    assert callable(detect_key_levels)
    print("  [PASS] test_import")


# ── 2. 边界条件 ───────────────────────────────────────────


def test_empty_df():
    """空 DataFrame → 返回空列表"""
    levels, meta = detect_key_levels(pd.DataFrame())
    assert levels == []
    assert meta.get("quality_warning") == "insufficient_data"
    print("  [PASS] test_empty_df")


def test_insufficient_data():
    """不足 swing_window*2+1 (11) 行 → 返回空列表"""
    df = pd.DataFrame([{"open": 10, "high": 11, "low": 9, "close": 10}] * 8)
    levels, meta = detect_key_levels(df)
    assert levels == []
    print("  [PASS] test_insufficient_data")


def test_no_swing_points():
    """单调递增价格 → 无局部极值 → 无 swing 点 → 返回空列表"""
    n_bars = 60
    df = pd.DataFrame({
        "open": np.linspace(50.0, 51.0, n_bars),
        "high": np.linspace(50.1, 51.1, n_bars),
        "low": np.linspace(49.9, 50.9, n_bars),
        "close": np.linspace(50.0, 51.0, n_bars),
    })
    levels, meta = detect_key_levels(df)
    assert levels == []
    print("  [PASS] test_no_swing_points")


def test_missing_columns():
    """缺少 OHLC 列 → 抛出 KeyError（需 >= 11 行绕过早期 guard）"""
    df = pd.DataFrame({"trade_date": [f"202401{i:02d}" for i in range(20)]})
    try:
        detect_key_levels(df)
        assert False, "Should have raised KeyError"
    except KeyError:
        pass
    print("  [PASS] test_missing_columns")


# ── 3. 基础聚类 ──────────────────────────────────────────


def test_single_swing_high_cluster():
    """多个 swing high 价格接近 → 聚类为一个 swing_high_cluster"""
    df = build_flat_df(n_bars=120)
    force_swing_high(df, idx=20, price=100.0)
    force_swing_high(df, idx=45, price=100.1)
    force_swing_high(df, idx=70, price=99.95)

    levels, _ = detect_key_levels(df)

    sh_levels = [l for l in levels if l.formation_type == "swing_high_cluster"]
    assert len(sh_levels) >= 1, (
        f"Expected at least 1 swing_high_cluster, "
        f"got types: {[l.formation_type for l in levels]}"
    )

    best = min(sh_levels, key=lambda l: abs(l.level_price - 100))
    assert abs(best.level_price - 100) < 0.3, \
        f"level_price {best.level_price:.4f} too far from 100"
    assert best.swing_count >= 2, \
        f"expected swing_count >= 2, got {best.swing_count}"
    assert best.formation_type == "swing_high_cluster"
    assert not best.both_sides, \
        "pure swing_high_cluster should not have both_sides=True"
    print("  [PASS] test_single_swing_high_cluster")


def test_single_swing_low_cluster():
    """多个 swing low 价格接近 → 聚类为一个 swing_low_cluster"""
    df = build_flat_df(n_bars=120)
    force_swing_low(df, idx=30, price=98.0)
    force_swing_low(df, idx=55, price=98.05)
    force_swing_low(df, idx=80, price=97.95)

    levels, _ = detect_key_levels(df)

    sl_levels = [l for l in levels if l.formation_type == "swing_low_cluster"]
    assert len(sl_levels) >= 1, (
        f"Expected at least 1 swing_low_cluster, "
        f"got types: {[l.formation_type for l in levels]}"
    )

    best = min(sl_levels, key=lambda l: abs(l.level_price - 98))
    assert abs(best.level_price - 98) < 0.3, \
        f"level_price {best.level_price:.4f} too far from 98"
    assert best.swing_count >= 2
    assert best.formation_type == "swing_low_cluster"
    assert not best.both_sides, \
        "pure swing_low_cluster should not have both_sides=True"
    print("  [PASS] test_single_swing_low_cluster")


def test_mixed_cluster():
    """swing high 与 swing low 区间重叠 → 反向合并为 mixed"""
    df = build_flat_df(n_bars=120)

    # High cluster 价格区间 [100.00, 100.05]
    force_swing_high(df, idx=20, price=100.0)
    force_swing_high(df, idx=50, price=100.05)

    # Low cluster 价格区间 [99.98, 100.01] → 与 high 重叠
    force_swing_low(df, idx=35, price=100.01)
    force_swing_low(df, idx=65, price=99.98)

    levels, _ = detect_key_levels(df)

    mixed = [l for l in levels if l.formation_type == "mixed"]
    assert len(mixed) >= 1, (
        f"Expected at least 1 mixed level, "
        f"got types: {[l.formation_type for l in levels]}"
    )
    for m in mixed:
        assert m.both_sides, "mixed level should have both_sides=True"
        assert m.swing_count >= 3, \
            f"merged mixed should have >= 3 swing points, got {m.swing_count}"
    print("  [PASS] test_mixed_cluster")


# ── 4. 属性计算 ──────────────────────────────────────────


def test_recency_weighting():
    """recency_weighted_strength > 0，新触点贡献更高"""
    df = build_flat_df(n_bars=120)
    force_swing_high(df, idx=20, price=100.0)
    force_swing_high(df, idx=110, price=100.0)  # 靠近末端

    levels, _ = detect_key_levels(df)

    sh_levels = [l for l in levels if l.formation_type == "swing_high_cluster"]
    assert len(sh_levels) >= 1

    best = min(sh_levels, key=lambda l: abs(l.level_price - 100))
    assert best.recency_weighted_strength > 0, \
        f"recency_weighted_strength should be > 0, got {best.recency_weighted_strength}"
    print("  [PASS] test_recency_weighting")


# ── 5. 极性转换 (P1.2b) ──────────────────────────────────


def test_polarity_flips():
    """支撑→阻力连续触碰 → 正确记录极性转换"""
    df = build_flat_df(n_bars=60)

    df.loc[:34, "close"] = 99.0    # < price_min → support
    df.loc[35:, "close"] = 101.0   # > price_max → resistance

    touch_indices = [25, 35]
    price_min, price_max = 99.5, 100.5
    has_date = False

    flips = _detect_polarity_flips(df, touch_indices, price_min, price_max, has_date)

    assert len(flips) == 1, f"Expected 1 polarity flip, got {len(flips)}: {flips}"
    assert flips[0]["from"] == "support", f"Expected from=support, got {flips[0]}"
    assert flips[0]["to"] == "resistance", f"Expected to=resistance, got {flips[0]}"
    # has_date=False → 日期为 str(int(idx))
    assert flips[0]["date"] == "35", f"Expected date='35', got {flips[0]['date']}"
    print("  [PASS] test_polarity_flips")


def test_polarity_flips_no_flip():
    """只有一次触碰 → 无极性转换"""
    df = build_flat_df(n_bars=30)
    flips = _detect_polarity_flips(df, [10], 99.5, 100.5, False)
    assert flips == [], f"Expected empty flips, got {flips}"
    print("  [PASS] test_polarity_flips_no_flip")


# ── 6. 假突破检测 (P1.2c) ────────────────────────────────


def test_fakeout_above():
    """向上假突破: high 突破 >0.1% 后 3 根 K 线内收盘价收回"""
    df = build_flat_df(n_bars=60)
    price_min, price_max = 99.0, 101.0

    # idx=30: 向上突破
    df.loc[30, "high"] = 101.5       # > 101.0*1.001=101.101
    df.loc[30, "close"] = 100.8
    # idx=31: 收盘回到 price_max 以内
    df.loc[31, "close"] = 100.5      # <= 101.0 → returned

    has_date = False
    fakeouts = _detect_fakeouts(df, [30], price_min, price_max, has_date)

    assert len(fakeouts) >= 1, f"Expected fakeout, got {fakeouts}"
    assert fakeouts[0]["direction"] == "above", \
        f"Expected direction=above, got {fakeouts[0]}"
    assert fakeouts[0]["depth_pct"] > 0, \
        f"depth_pct should be > 0, got {fakeouts[0]['depth_pct']}"
    print("  [PASS] test_fakeout_above")


def test_fakeout_below():
    """向下假突破: low 突破 <0.1% 后 3 根 K 线内收盘价收回"""
    df = build_flat_df(n_bars=60)
    price_min, price_max = 99.0, 101.0

    # idx=30: 向下突破 (确保高不触发上突破)
    df.loc[30, "high"] = 100.0       # <= 101.101 → 不触发向上
    df.loc[30, "low"] = 98.5         # < 99.0*0.999=98.901
    df.loc[30, "close"] = 99.5
    # idx=31: 收盘回到 price_min 以上
    df.loc[31, "close"] = 99.5       # >= 99.0 → returned

    has_date = False
    fakeouts = _detect_fakeouts(df, [30], price_min, price_max, has_date)

    assert len(fakeouts) >= 1, f"Expected fakeout, got {fakeouts}"
    assert fakeouts[0]["direction"] == "below", \
        f"Expected direction=below, got {fakeouts[0]}"
    assert fakeouts[0]["depth_pct"] > 0, \
        f"depth_pct should be > 0, got {fakeouts[0]['depth_pct']}"
    print("  [PASS] test_fakeout_below")


def test_no_fakeout_no_return():
    """突破后未收回 → 不计为假突破"""
    df = build_flat_df(n_bars=60)
    price_min, price_max = 99.0, 101.0

    df.loc[30, "high"] = 101.5       # 突破
    df.loc[30, "close"] = 102.0
    df.loc[31, "close"] = 102.0      # 未收回
    df.loc[32, "close"] = 102.0
    df.loc[33, "close"] = 102.0

    has_date = False
    fakeouts = _detect_fakeouts(df, [30], price_min, price_max, has_date)
    assert fakeouts == [], f"Expected no fakeout, got {fakeouts}"
    print("  [PASS] test_no_fakeout_no_return")


# ── 7. 便捷接口 ──────────────────────────────────────────


def test_levels_near_price():
    """levels_near_price 正确返回 < threshold 的关键位"""
    levels = [
        KeyLevel(level_price=100.0),
        KeyLevel(level_price=105.0),
        KeyLevel(level_price=110.0),
    ]
    near = levels_near_price(levels, price=101.0, threshold=0.03)
    # 100 在 101 ± 3% 内 (diff ≈ 0.99%),
    # 105 不在 (diff ≈ 3.96%)
    assert len(near) == 1, \
        f"Expected 1 near level, got {len(near)}: {[l.level_price for l in near]}"
    assert near[0].level_price == 100.0
    print("  [PASS] test_levels_near_price")


def test_levels_near_price_empty():
    """空列表 → 返回空列表"""
    assert levels_near_price([], 100.0) == []
    print("  [PASS] test_levels_near_price_empty")


def test_nearest_level():
    """nearest_level 返回最近的关键位"""
    levels = [
        KeyLevel(level_price=100.0),
        KeyLevel(level_price=105.0),
        KeyLevel(level_price=110.0),
    ]
    nearest = nearest_level(levels, price=103.0)
    assert nearest is not None
    assert nearest.level_price == 105.0, f"Expected 105.0, got {nearest.level_price}"
    print("  [PASS] test_nearest_level")


def test_nearest_level_none():
    """空列表 → 返回 None"""
    assert nearest_level([], 100.0) is None
    print("  [PASS] test_nearest_level_none")


def test_key_level_summary():
    """key_levels_summary 输出包含当前价和方向标记"""
    levels = [
        KeyLevel(level_price=100.0, price_min=99.5, price_max=100.5,
                 strength=5, last_date="20260601"),
        KeyLevel(level_price=95.0, price_min=94.5, price_max=95.5,
                 strength=3, last_date="20260515"),
    ]
    summary = key_levels_summary(levels, price_current=97.5)
    assert "current" in summary or "──" in summary, \
        "Summary should contain current price marker"
    assert "97.50" in summary, f"Summary should contain current price:\n{summary}"
    assert "R1" in summary, f"Summary should contain R1 (above price):\n{summary}"
    assert "S1" in summary, f"Summary should contain S1 (below price):\n{summary}"
    print("  [PASS] test_key_level_summary")


def test_key_level_summary_empty():
    """空列表 → 'No key levels detected.'"""
    assert key_levels_summary([], 100.0) == "No key levels detected."
    print("  [PASS] test_key_level_summary_empty")


# ── 8. KeyLevel 数据类完整性 ─────────────────────────────


def test_key_level_dataclass():
    """KeyLevel 数据类包含全部 14 个字段"""
    kl = KeyLevel(
        level_price=100.0,
        formation_type="swing_high_cluster",
        price_min=99.5,
        price_max=100.5,
        strength=5,
        swing_count=3,
        touch_count=10,
        recency_weighted_strength=2.5,
        both_sides=True,
        first_date="20260101",
        last_date="20260601",
        cluster_prices=[99.8, 100.0, 100.2],
        polarity_flips=[{"date": "20260301", "from": "support", "to": "resistance"}],
        fakeout_history=[{"date": "20260401", "direction": "above", "depth_pct": 0.5}],
    )

    assert isinstance(kl.level_price, float)
    assert abs(kl.level_price - 100.0) < 1e-9
    assert kl.formation_type == "swing_high_cluster"
    assert isinstance(kl.price_min, float) and abs(kl.price_min - 99.5) < 1e-9
    assert isinstance(kl.price_max, float) and abs(kl.price_max - 100.5) < 1e-9
    assert isinstance(kl.strength, int) and kl.strength == 5
    assert isinstance(kl.swing_count, int) and kl.swing_count == 3
    assert isinstance(kl.touch_count, int) and kl.touch_count == 10
    assert isinstance(kl.recency_weighted_strength, float)
    assert abs(kl.recency_weighted_strength - 2.5) < 1e-9
    assert isinstance(kl.both_sides, bool) and kl.both_sides is True
    assert isinstance(kl.first_date, str) and kl.first_date == "20260101"
    assert isinstance(kl.last_date, str) and kl.last_date == "20260601"
    assert isinstance(kl.cluster_prices, list) and len(kl.cluster_prices) == 3
    assert isinstance(kl.polarity_flips, list) and len(kl.polarity_flips) == 1
    assert isinstance(kl.fakeout_history, list) and len(kl.fakeout_history) == 1
    print("  [PASS] test_key_level_dataclass")


# ── 9. 集成 ──────────────────────────────────────────────


def test_integration_with_trade_date():
    """包含 trade_date 列时，日期格式为 YYYYMMDD"""
    df = build_flat_df(n_bars=120)
    df["trade_date"] = [f"2025{str(i%12+1).zfill(2)}01" for i in range(120)]

    force_swing_high(df, idx=20, price=100.0)
    force_swing_high(df, idx=50, price=100.05)

    levels, _ = detect_key_levels(df)
    sh_levels = [l for l in levels if l.formation_type == "swing_high_cluster"]
    assert len(sh_levels) >= 1

    best = min(sh_levels, key=lambda l: abs(l.level_price - 100))
    assert len(best.first_date) == 8, \
        f"Expected YYYYMMDD first_date, got {best.first_date}"
    assert len(best.last_date) == 8, \
        f"Expected YYYYMMDD last_date, got {best.last_date}"
    print("  [PASS] test_integration_with_trade_date")


# ── 执行 ────────────────────────────────────────────────


if __name__ == "__main__":
    tests = [
        ("导入",                            test_import),
        ("空 DataFrame",                    test_empty_df),
        ("数据不足 (<11 行)",               test_insufficient_data),
        ("无 Swing 点 (平坦)",              test_no_swing_points),
        ("缺失 OHLC 列",                    test_missing_columns),
        ("Swing High 聚类",                 test_single_swing_high_cluster),
        ("Swing Low 聚类",                  test_single_swing_low_cluster),
        ("Mixed 聚类 (反向合并)",            test_mixed_cluster),
        ("时效加权",                        test_recency_weighting),
        ("极性转换 (支撑→阻力)",             test_polarity_flips),
        ("无极性转换 (1 次触碰)",            test_polarity_flips_no_flip),
        ("向上假突破",                      test_fakeout_above),
        ("向下假突破",                      test_fakeout_below),
        ("突破未收回 → 不计假突破",          test_no_fakeout_no_return),
        ("levels_near_price",               test_levels_near_price),
        ("levels_near_price (空列表)",       test_levels_near_price_empty),
        ("nearest_level",                   test_nearest_level),
        ("nearest_level (空列表 → None)",    test_nearest_level_none),
        ("key_levels_summary 文本",          test_key_level_summary),
        ("key_levels_summary (空 → 缺省文本)", test_key_level_summary_empty),
        ("KeyLevel 数据类 14 字段",          test_key_level_dataclass),
        ("集成: 含 trade_date 列",           test_integration_with_trade_date),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1

    print(f"\n=== {passed} 通过, {failed} 失败 ===")
    sys.exit(1 if failed else 0)
