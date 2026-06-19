"""P1.4 评分模块单元测试

测试覆盖:
  1. 强信号 + 完美对齐 = 高分 (>= 0.8)
  2. 弱信号 + 无任何辅助 = 低分 (< 0.2)
  3. 方向相反 + high confidence Always-In = 否决 (0.0)
  4. weak 信号 + 无辅助加分 = 否决 (0.0)
  5. 空信号列表 = 空列表
  6. select_top_n 正确截断
  7. select_top_n 不够 N 个时不补齐
  8. select_top_n min_score 过滤

可直接运行: python test_score.py
"""

import sys
import os

# ── 导入被测模块 ──
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PAT_stock.scoring.score import (
    score_signal,
    score_all_signals,
    select_top_signals,
)


# ══════════════════════════════════════════════════════════
# 测试数据工厂
# ══════════════════════════════════════════════════════════

_ALWAYS_IN_BULLISH_HIGH = {
    "direction": "up",
    "confidence": 0.85,
    "trend_filter": "long_only",
}

_ALWAYS_IN_BULLISH_MEDIUM = {
    "direction": "up",
    "confidence": 0.50,
    "trend_filter": "long_only",
}

_ALWAYS_IN_BULLISH_LOW = {
    "direction": "up",
    "confidence": 0.20,
    "trend_filter": "long_only",
}

_ALWAYS_IN_OSCILLATING = {
    "direction": "oscillating",
    "confidence": 0.0,
    "trend_filter": "neutral",
}

_ALWAYS_IN_BEARISH_HIGH = {
    "direction": "down",
    "confidence": 0.85,
    "trend_filter": "short_only",
}


def _make_signal(**overrides):
    """创建标准测试信号, 支持字段覆盖"""
    base = {
        "date": "20260616",
        "direction": "bullish",
        "strength": "strong",
        "entry_trigger": 100.0,
        "stop_loss": None,
        "near_key_level": False,
        "key_level_distance": None,
        "always_in_aligned": True,
        "polarity_nearby": False,
        "fakeout_nearby": False,
        "score": 0.0,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════
# 测试用例
# ══════════════════════════════════════════════════════════


def test_strong_aligned_high_score():
    """1. 强信号 + 完美对齐 = 高分 (>= 0.8)"""
    signal = _make_signal(
        direction="bullish",
        strength="strong",
        always_in_aligned=True,
        near_key_level=True,
    )
    # strong(0.4) + aligned_high(0.3) + near_kl(0.15) = 0.85
    score = score_signal(signal, _ALWAYS_IN_BULLISH_HIGH)
    assert score >= 0.8, f"Expected >= 0.8, got {score}"
    print(f"  [PASS] test_strong_aligned_high_score: score={score:.2f}")


def test_weak_no_support_low_score():
    """2. 弱信号 + 无任何辅助 = 低分 (< 0.2)"""
    signal = _make_signal(
        direction="bullish",
        strength="weak",
        always_in_aligned=True,
        near_key_level=False,
        polarity_nearby=False,
        fakeout_nearby=False,
    )
    # weak(0.1) + aligned_low(0.1) + 0 + 0 = 0.2, but veto B applies
    # weak + no auxiliary (key_level=0, trap=0) → 0.0
    score = score_signal(signal, _ALWAYS_IN_BULLISH_LOW)
    assert score < 0.2, f"Expected < 0.2, got {score}"
    print(f"  [PASS] test_weak_no_support_low_score: score={score:.2f}")


def test_opposite_direction_veto():
    """3. 方向相反 + high confidence Always-In = 否决 (0.0)"""
    # AI = "up" (bullish), confidence=0.85 > 0.8, signal = "bearish" → veto
    signal = _make_signal(
        direction="bearish",
        strength="strong",
        always_in_aligned=False,
        near_key_level=True,
    )
    score = score_signal(signal, _ALWAYS_IN_BULLISH_HIGH)
    assert score == 0.0, f"Expected 0.0 (veto), got {score}"
    print(f"  [PASS] test_opposite_direction_veto: score={score:.2f}")


def test_weak_no_auxiliary_veto():
    """4. weak 信号 + 无辅助加分 = 否决 (0.0)"""
    signal = _make_signal(
        direction="bullish",
        strength="weak",
        always_in_aligned=True,
        near_key_level=False,
        polarity_nearby=False,
        fakeout_nearby=False,
    )
    score = score_signal(signal, _ALWAYS_IN_BULLISH_LOW)
    # Veto B: weak + no auxiliary (key_level=0, trap=0)
    assert score == 0.0, f"Expected 0.0 (veto), got {score}"
    print(f"  [PASS] test_weak_no_auxiliary_veto: score={score:.2f}")


def test_weak_with_trap_no_veto():
    """weak 信号 + 有陷阱加分 → 不否决"""
    signal = _make_signal(
        direction="bullish",
        strength="weak",
        always_in_aligned=True,
    )
    traps = [
        {"type": "fake_breakout", "trap_direction": "bullish", "confidence": "high"},
    ]
    score = score_signal(signal, _ALWAYS_IN_BULLISH_LOW, trap_context=traps)
    # weak(0.1) + aligned_low(0.1) + 0 + trap(0.1) = 0.3, no veto
    assert score > 0.0, f"Expected > 0.0, got {score}"
    assert abs(score - 0.3) < 1e-6, f"Expected 0.3, got {score}"
    print(f"  [PASS] test_weak_with_trap_no_veto: score={score:.2f}")


def test_weak_with_keylevel_no_veto():
    """weak 信号 + 关键位加分 → 不否决"""
    signal = _make_signal(
        direction="bullish",
        strength="weak",
        always_in_aligned=True,
        near_key_level=True,
    )
    kl_ctx = {"both_sides": True}
    score = score_signal(signal, _ALWAYS_IN_BULLISH_LOW, key_level_context=kl_ctx)
    # weak(0.1) + aligned_low(0.1) + kl_both(0.2) + 0 = 0.4, no veto
    assert score > 0.0, f"Expected > 0.0, got {score}"
    assert abs(score - 0.4) < 1e-6, f"Expected 0.4, got {score}"
    print(f"  [PASS] test_weak_with_keylevel_no_veto: score={score:.2f}")


def test_empty_signal_list():
    """5. 空信号列表 = 空列表"""
    result = score_all_signals([], always_in={})
    assert result == [], f"Expected empty list, got {result}"
    print("  [PASS] test_empty_signal_list")


def test_score_all_signals_basic():
    """score_all_signals 批量评分: 长度一致, score 字段存在"""
    signals = [
        _make_signal(direction="bullish", strength="strong",
                     always_in_aligned=True),
        _make_signal(direction="bearish", strength="weak",
                     always_in_aligned=False),
    ]
    result = score_all_signals(signals, _ALWAYS_IN_BULLISH_HIGH)

    assert len(result) == len(signals), \
        f"Expected {len(signals)} results, got {len(result)}"
    assert "score" in result[0], "Missing score field in result[0]"
    assert "score" in result[1], "Missing score field in result[1]"
    # 信号0: strong(0.4) + aligned_high(0.3) + 0 + 0 = 0.7, no veto
    assert result[0]["score"] > 0.0, f"Expected > 0 for signal 0"
    # 信号1: weak(0.1), AI="up", signal="bearish", confidence=0.85 > 0.8
    # Veto A: opposite direction → 0.0
    assert result[1]["score"] == 0.0, \
        f"Expected 0.0 for signal 1 (opposite+strong AI), got {result[1]['score']}"
    print(f"  [PASS] test_score_all_signals_basic: "
          f"scores={[s['score'] for s in result]}")


def test_score_all_signals_preserves_original():
    """score_all_signals 不修改原始信号列表"""
    signals = [
        _make_signal(direction="bullish", strength="strong"),
    ]
    original_score = signals[0]["score"]
    _ = score_all_signals(signals, _ALWAYS_IN_BULLISH_HIGH)
    assert signals[0]["score"] == original_score, \
        "Original signal was mutated"
    print("  [PASS] test_score_all_signals_preserves_original")


def test_score_all_signals_with_key_levels():
    """score_all_signals 传入 key_levels 时正确提取 both_sides"""
    from PAT_stock.patterns.key_levels import KeyLevel

    signals = [
        _make_signal(direction="bullish", strength="normal",
                     entry_trigger=100.0, near_key_level=False),
    ]
    # 创建一个在 100.0 附近有 both_sides=True 的 KeyLevel
    kl = KeyLevel(
        level_price=100.0,
        formation_type="mixed",
        price_min=99.0,
        price_max=101.0,
        both_sides=True,
        strength=5,
        swing_count=3,
        touch_count=5,
    )
    key_levels = [kl]
    result = score_all_signals(signals, _ALWAYS_IN_OSCILLATING, key_levels=key_levels)
    # normal(0.25) + aligned_low(0.1) + kl_both(0.2) + 0 = 0.55
    assert result[0]["score"] > 0.0, f"Expected > 0, got {result[0]['score']}"
    assert abs(result[0]["score"] - 0.55) < 1e-6, \
        f"Expected 0.55, got {result[0]['score']}"
    print(f"  [PASS] test_score_all_signals_with_key_levels: "
          f"score={result[0]['score']:.2f}")


def test_score_all_signals_with_traps():
    """score_all_signals 传入 traps 时正确匹配"""
    signals = [
        _make_signal(direction="bullish", strength="normal",
                     always_in_aligned=True),
    ]
    traps = [
        {"type": "stop_run", "trap_direction": "bullish", "confidence": "high"},
    ]
    result = score_all_signals(signals, _ALWAYS_IN_BULLISH_LOW, traps=traps)
    # normal(0.25) + aligned_low(0.1) + 0 + trap(0.1) = 0.45
    assert abs(result[0]["score"] - 0.45) < 1e-6, \
        f"Expected 0.45, got {result[0]['score']}"
    print(f"  [PASS] test_score_all_signals_with_traps: "
          f"score={result[0]['score']:.2f}")


def test_select_top_n_cutoff():
    """6. select_top_n 正确截断, 按 score 降序"""
    signals = [
        {"score": 0.8, "direction": "bullish"},
        {"score": 0.6, "direction": "bullish"},
        {"score": 0.4, "direction": "bearish"},
        {"score": 0.3, "direction": "bearish"},
    ]
    top2 = select_top_signals(signals, top_n=2)
    assert len(top2) == 2, f"Expected 2, got {len(top2)}"
    assert top2[0]["score"] >= top2[1]["score"], "Not sorted descending"
    assert top2[0]["score"] == 0.8
    assert top2[1]["score"] == 0.6
    print(f"  [PASS] test_select_top_n_cutoff: {[s['score'] for s in top2]}")


def test_select_top_n_not_enough():
    """7. select_top_n 不够 N 个时不补齐"""
    signals = [
        {"score": 0.8, "direction": "bullish"},
    ]
    top5 = select_top_signals(signals, top_n=5)
    assert len(top5) == 1, f"Expected 1, got {len(top5)}"
    assert top5[0]["score"] == 0.8
    print(f"  [PASS] test_select_top_n_not_enough: {len(top5)} result(s)")


def test_select_top_n_min_score():
    """8. select_top_n min_score 过滤"""
    signals = [
        {"score": 0.5, "direction": "bullish"},
        {"score": 0.2, "direction": "bullish"},
        {"score": 0.1, "direction": "bearish"},
        {"score": 0.0, "direction": "bearish"},
    ]
    top = select_top_signals(signals, top_n=10, min_score=0.3)
    assert len(top) == 1, f"Expected 1, got {len(top)}"
    assert top[0]["score"] == 0.5
    print(f"  [PASS] test_select_top_n_min_score: {[s['score'] for s in top]}")


def test_select_top_signals_empty():
    """select_top_signals 空输入"""
    result = select_top_signals([])
    assert result == [], f"Expected empty, got {result}"
    print("  [PASS] test_select_top_signals_empty")


def test_select_top_signals_all_below_min():
    """所有信号低于 min_score 时返回空列表"""
    signals = [
        {"score": 0.1, "direction": "bullish"},
        {"score": 0.05, "direction": "bearish"},
    ]
    result = select_top_signals(signals, min_score=0.15)
    assert result == [], f"Expected empty, got {result}"
    print("  [PASS] test_select_top_signals_all_below_min")


def test_full_score_breakdown():
    """验证各个维度分项和总分正确 (含 both_sides)"""
    signal = _make_signal(
        direction="bullish",
        strength="strong",
        always_in_aligned=True,
        near_key_level=True,
    )
    kl_ctx = {"both_sides": True}
    score = score_signal(signal, _ALWAYS_IN_BULLISH_HIGH, key_level_context=kl_ctx)
    # bar(0.4) + trend(0.3) + kl_both(0.2) + trap(0) = 0.9
    assert abs(score - 0.9) < 1e-6, f"Expected 0.9, got {score}"
    print(f"  [PASS] test_full_score_breakdown: score={score:.2f}")


def test_score_clamped():
    """总分不超过 1.0"""
    signal = _make_signal(
        direction="bullish",
        strength="strong",
        always_in_aligned=True,
        near_key_level=True,
    )
    kl_ctx = {"both_sides": True}
    traps = [{"trap_direction": "bullish"}]
    score = score_signal(
        signal, _ALWAYS_IN_BULLISH_HIGH,
        key_level_context=kl_ctx, trap_context=traps,
    )
    # bar(0.4) + trend(0.3) + kl(0.2) + trap(0.1) = 1.0
    assert score <= 1.0, f"Expected <= 1.0, got {score}"
    print(f"  [PASS] test_score_clamped: score={score:.2f}")


def test_oscillating_alignment():
    """Always-In oscillating 时 aligned=True → 0.1 (低置信度)"""
    signal = _make_signal(
        direction="bullish",
        strength="normal",
        always_in_aligned=True,
    )
    score = score_signal(signal, _ALWAYS_IN_OSCILLATING)
    # normal(0.25) + aligned_low(0.1) + 0 + 0 = 0.35
    assert abs(score - 0.35) < 1e-6, f"Expected 0.35, got {score}"
    print(f"  [PASS] test_oscillating_alignment: score={score:.2f}")


def test_aligned_medium_confidence():
    """aligned + confidence 0.3~0.7 → 0.2"""
    signal = _make_signal(
        direction="bullish",
        strength="normal",
        always_in_aligned=True,
    )
    score = score_signal(signal, _ALWAYS_IN_BULLISH_MEDIUM)
    # normal(0.25) + aligned_medium(0.2) + 0 + 0 = 0.45
    assert abs(score - 0.45) < 1e-6, f"Expected 0.45, got {score}"
    print(f"  [PASS] test_aligned_medium_confidence: score={score:.2f}")


def test_not_aligned_non_neutral():
    """not aligned + trend_filter != neutral → trend(0.0)"""
    signal = _make_signal(
        direction="bearish",
        strength="strong",
        always_in_aligned=False,
    )
    # AI="up", signal="bearish" → opposite direction
    # confidence=0.5 <= 0.8 → no veto A
    # not aligned + long_only → trend=0.0
    # strong(0.4) + trend(0.0) + 0 + 0 = 0.4
    score = score_signal(signal, _ALWAYS_IN_BULLISH_MEDIUM)
    assert abs(score - 0.4) < 1e-6, f"Expected 0.4, got {score}"
    print(f"  [PASS] test_not_aligned_non_neutral: score={score:.2f}")


def test_not_aligned_neutral():
    """not aligned + trend_filter=neutral → trend(0.1)"""
    signal = _make_signal(
        direction="bearish",
        strength="normal",
        always_in_aligned=False,
    )
    score = score_signal(signal, _ALWAYS_IN_OSCILLATING)
    # normal(0.25) + neutral_aligned(0.1) + 0 + 0 = 0.35
    assert abs(score - 0.35) < 1e-6, f"Expected 0.35, got {score}"
    print(f"  [PASS] test_not_aligned_neutral: score={score:.2f}")


def test_key_level_context_priority():
    """关键位上下文取最高分, 不累加"""
    signal = _make_signal(
        direction="bullish",
        strength="normal",
        always_in_aligned=True,
        near_key_level=True,
        polarity_nearby=True,
        fakeout_nearby=True,
    )
    score = score_signal(signal, _ALWAYS_IN_OSCILLATING)
    # normal(0.25) + aligned_low(0.1) + kl_max(0.15) + 0 = 0.5
    # polarity(0.05) and fakeout(0.1) are lower, so kl(0.15) wins
    assert abs(score - 0.5) < 1e-6, f"Expected 0.5, got {score}"
    print(f"  [PASS] test_key_level_context_priority: score={score:.2f}")


def test_polarity_only():
    """仅 polarity_nearby → 0.05"""
    signal = _make_signal(
        direction="bullish",
        strength="normal",
        always_in_aligned=True,
        near_key_level=False,
        polarity_nearby=True,
        fakeout_nearby=False,
    )
    score = score_signal(signal, _ALWAYS_IN_OSCILLATING)
    # normal(0.25) + aligned_low(0.1) + polarity(0.05) + 0 = 0.4
    assert abs(score - 0.4) < 1e-6, f"Expected 0.4, got {score}"
    print(f"  [PASS] test_polarity_only: score={score:.2f}")


def test_fakeout_only():
    """仅 fakeout_nearby → 0.1"""
    signal = _make_signal(
        direction="bullish",
        strength="normal",
        always_in_aligned=True,
        near_key_level=False,
        polarity_nearby=False,
        fakeout_nearby=True,
    )
    score = score_signal(signal, _ALWAYS_IN_OSCILLATING)
    # normal(0.25) + aligned_low(0.1) + fakeout(0.1) + 0 = 0.45
    assert abs(score - 0.45) < 1e-6, f"Expected 0.45, got {score}"
    print(f"  [PASS] test_fakeout_only: score={score:.2f}")


def test_veto_ai_bearish_high_confidence():
    """Always-In bearish high conf + bullish signal → veto"""
    signal = _make_signal(
        direction="bullish",
        strength="strong",
        always_in_aligned=False,
    )
    score = score_signal(signal, _ALWAYS_IN_BEARISH_HIGH)
    assert score == 0.0, f"Expected 0.0 (veto), got {score}"
    print(f"  [PASS] test_veto_ai_bearish_high_confidence: score={score:.2f}")


def test_no_veto_confidence_exactly_0_8():
    """confidence 恰好 0.8 不触发否决 (threshold 是 > 0.8)"""
    signal = _make_signal(
        direction="bearish",
        strength="strong",
        always_in_aligned=False,
    )
    always_in = {"direction": "up", "confidence": 0.8, "trend_filter": "long_only"}
    score = score_signal(signal, always_in)
    # strong(0.4) + not_aligned(0.0) + 0 + 0 = 0.4, no veto
    assert score > 0.0, f"Expected > 0.0, got {score}"
    print(f"  [PASS] test_no_veto_confidence_exactly_0_8: score={score:.2f}")


# ══════════════════════════════════════════════════════════
# 运行器
# ══════════════════════════════════════════════════════════


def run_all():
    tests = [
        ("强信号+完美对齐=高分", test_strong_aligned_high_score),
        ("弱信号+无辅助=低分", test_weak_no_support_low_score),
        ("方向相反+high conf=否决", test_opposite_direction_veto),
        ("weak+无辅助=否决", test_weak_no_auxiliary_veto),
        ("weak+有陷阱=不否决", test_weak_with_trap_no_veto),
        ("weak+关键位=不否决", test_weak_with_keylevel_no_veto),
        ("空信号列表", test_empty_signal_list),
        ("批量评分基础", test_score_all_signals_basic),
        ("批量评分不修改原列表", test_score_all_signals_preserves_original),
        ("批量评分+key_levels", test_score_all_signals_with_key_levels),
        ("批量评分+traps", test_score_all_signals_with_traps),
        ("select_top_n截断", test_select_top_n_cutoff),
        ("select_top_n不足不补齐", test_select_top_n_not_enough),
        ("select_top_min_score过滤", test_select_top_n_min_score),
        ("select_top空输入", test_select_top_signals_empty),
        ("所有低于最小分", test_select_top_signals_all_below_min),
        ("完整评分分解", test_full_score_breakdown),
        ("总分不超1.0", test_score_clamped),
        ("oscillating对齐", test_oscillating_alignment),
        ("中等置信度对齐", test_aligned_medium_confidence),
        ("不对齐+非中立趋势", test_not_aligned_non_neutral),
        ("不对齐+中立趋势", test_not_aligned_neutral),
        ("关键位上下文取最高分", test_key_level_context_priority),
        ("仅极性转换加分", test_polarity_only),
        ("仅假突破加分", test_fakeout_only),
        ("AI空头高conf否决", test_veto_ai_bearish_high_confidence),
        ("conf=0.8不触发否决", test_no_veto_confidence_exactly_0_8),
    ]

    passed = 0
    failed = 0
    detail_fails = []

    print("=" * 48)
    print("PAT Scoring Module — Unit Tests")
    print("=" * 48)
    print()

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
            detail_fails.append(name)
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            failed += 1
            detail_fails.append(name)

    print()
    print("=" * 48)
    print(f"Result: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        print(f"Failed: {', '.join(detail_fails)}")
    print("=" * 48)
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
