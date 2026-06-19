"""M5 风控模块测试 — trader_equation + position_sizing

测试策略:
  1. trader_equation_evaluate — 基本计算与判定
  2. trader_equation_evaluate — 边界与异常
  3. position_size_from_te — 不同判定结果
  4. kelly_variant — 半凯利 + 截断
  5. max_position_per_market_state — 状态映射
  6. position_size_by_trader_equation — 完整链路
"""

import sys
import os
import math

# ── 确保能导入 risk 模块 ──
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from risk.trader_equation import trader_equation_evaluate, position_size_from_te
from risk.position_sizing import (
    kelly_variant,
    max_position_per_market_state,
    position_size_by_trader_equation,
)

PASS = 0
FAIL = 0
TOTAL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL, TOTAL
    TOTAL += 1
    if condition:
        PASS += 1
        print(f"  OK  {name}")
    else:
        FAIL += 1
        msg = f"  FAIL {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)


# ══════════════════════════════════════════
# 1. trader_equation_evaluate — 基本计算
# ══════════════════════════════════════════

def test_te_basic_a():
    """A 级信号, 止损2%, 目标6%, 正常市场"""
    r = trader_equation_evaluate("A", 0.02, 0.06, 1.0)
    # base=0.55, adj=1.0, market=1.0 → win_rate=0.55
    check("A: win_rate", abs(r["win_rate"] - 0.55) < 0.001, f"got {r['win_rate']}")
    # ratio = 0.06/0.02 = 3.0
    check("A: reward_ratio", abs(r["reward_ratio"] - 3.0) < 0.001, f"got {r['reward_ratio']}")
    # EV = 0.55*3 - 0.45*1 = 1.65 - 0.45 = 1.20
    check("A: expected_value > 0.3", r["expected_value"] > 0.3, f"got {r['expected_value']}")
    check("A: verdict=high_quality", r["verdict"] == "high_quality", f"got {r['verdict']}")
    check("A: position_multiplier=1.0", r["position_multiplier"] == 1.0)


def test_te_basic_b():
    """B 级信号, stop 3%, target 3%, 弱势市场"""
    r = trader_equation_evaluate("B", 0.03, 0.03, 0.6)
    # base=0.45, adj=0.8, market=0.6 → win_rate=0.45*0.8*0.6=0.216
    expected_wr = round(0.45 * 0.8 * 0.6, 4)
    check("B: win_rate", abs(r["win_rate"] - expected_wr) < 0.001, f"got {r['win_rate']} vs {expected_wr}")
    # ratio = 1.0
    # EV = 0.216*1 - 0.784*1 = -0.568
    check("B: verdict=reject", r["verdict"] == "reject", f"got {r['verdict']}")
    check("B: expected_value < 0", r["expected_value"] < 0, f"got {r['expected_value']}")
    check("B: position_multiplier=0.0", r["position_multiplier"] == 0.0)


def test_te_with_historical():
    """historical_win_rate 覆盖基线"""
    r = trader_equation_evaluate("C", 0.02, 0.04, 1.0, historical_win_rate=0.60)
    # base=0.60 (from historical), adj=0.6, market=1.0 → win_rate=0.36
    expected_wr = round(0.60 * 0.6 * 1.0, 4)
    check("hist: win_rate", abs(r["win_rate"] - expected_wr) < 0.001, f"got {r['win_rate']} vs {expected_wr}")
    # ratio = 2.0, EV = 0.36*2 - 0.64*1 = 0.72 - 0.64 = 0.08
    check("hist: expected_value ~0.08", abs(r["expected_value"] - 0.08) < 0.01, f"got {r['expected_value']}")
    check("hist: verdict=pass", r["verdict"] == "pass", f"got {r['verdict']}")


# ══════════════════════════════════════════
# 2. trader_equation_evaluate — 边界与异常
# ══════════════════════════════════════════

def test_te_invalid_quality():
    """无效信号质量 → ValueError"""
    try:
        trader_equation_evaluate("D", 0.02, 0.06, 1.0)
        check("bad_quality: should raise", False, "no exception")
    except ValueError:
        check("bad_quality: ValueError raised", True)


def test_te_zero_stop():
    """零止损 → ValueError"""
    try:
        trader_equation_evaluate("A", 0.0, 0.06, 1.0)
        check("zero_stop: should raise", False)
    except ValueError:
        check("zero_stop: ValueError raised", True)


def test_te_negative_market():
    """负市场乘数 → ValueError"""
    try:
        trader_equation_evaluate("A", 0.02, 0.06, -0.5)
        check("neg_market: should raise", False)
    except ValueError:
        check("neg_market: ValueError raised", True)


def test_te_not_reject():
    """EV=0 刚好不 reject (pass 边界)"""
    # 目标: EV ≈ 0.0
    # win_rate = x, reward_ratio = 1.0
    # EV = x*1 - (1-x)*1 = 2x - 1 = 0 => x = 0.5
    # We need win_rate = 0.5 exactly
    # With C quality: base=0.35, adj=0.6 → 0.21*mkt = 0.5 → mkt = 0.5/0.21 ≈ 2.38
    # That's outside 0.5~1.5. Let's use historical win rate.
    r = trader_equation_evaluate("B", 0.02, 0.02, 1.0, historical_win_rate=0.5)
    # base=0.5, adj=0.8, mkt=1.0 → wr=0.4
    # EV = 0.4*1 - 0.6*1 = -0.2 → reject
    # Hmm that's still negative. Let me try: wr=0.5, ratio=1.0 → EV=0
    r2 = trader_equation_evaluate("A", 0.02, 0.02, 1.0, historical_win_rate=0.5)
    # base=0.5, adj=1.0, mkt=1.0 → wr=0.5
    # EV = 0.5*1 - 0.5*1 = 0.0 → pass (EV 0~0.3)
    check("ev_zero: verdict=pass", r2["verdict"] == "pass", f"got {r2['verdict']}, ev={r2['expected_value']}")
    check("ev_zero: EV≈0", abs(r2["expected_value"]) < 0.001, f"got {r2['expected_value']}")


# ══════════════════════════════════════════
# 3. position_size_from_te
# ══════════════════════════════════════════

def test_pos_size_high_quality():
    """high_quality 应返回 > 0"""
    te = trader_equation_evaluate("A", 0.02, 0.06, 1.0)
    pos = position_size_from_te(te, 0.02)
    check("pos_hq: > 0", pos > 0, f"got {pos}")
    check("pos_hq: <= 0.20", pos <= 0.20, f"got {pos}")


def test_pos_size_reject():
    """reject 应返回 0.0"""
    te = trader_equation_evaluate("B", 0.03, 0.03, 0.6)
    pos = position_size_from_te(te, 0.02)
    check("pos_reject: == 0.0", pos == 0.0, f"got {pos}")


def test_pos_size_pass():
    """pass 应返回小仓位"""
    te = trader_equation_evaluate("C", 0.02, 0.04, 1.0, historical_win_rate=0.60)
    pos = position_size_from_te(te, 0.02)
    check("pos_pass: >= 0", pos >= 0, f"got {pos}")
    check("pos_pass: < 0.15", pos < 0.15, f"got {pos}")


def test_pos_size_missing_key():
    """缺少键 → KeyError"""
    try:
        position_size_from_te({"verdict": "pass"})
        check("missing_key: should raise", False)
    except KeyError:
        check("missing_key: KeyError raised", True)


# ══════════════════════════════════════════
# 4. kelly_variant
# ══════════════════════════════════════════

def test_kelly_basic():
    """基本半凯利计算"""
    k = kelly_variant(0.55, 3.0)
    # full = 0.55 - 0.45/3 = 0.55 - 0.15 = 0.40
    # half = 0.20
    check("kelly_basic: ~0.20", abs(k - 0.20) < 0.001, f"got {k}")


def test_kelly_capped():
    """全凯利 > 50% → 半凯利后截断到 0.25"""
    k = kelly_variant(0.80, 5.0)
    # full = 0.80 - 0.20/5 = 0.80 - 0.04 = 0.76
    # half = 0.38, cap = 0.25
    check("kelly_capped: ~0.25", abs(k - 0.25) < 0.001, f"got {k}")


def test_kelly_edge_zero_win():
    """win_rate=0 → 0.0"""
    k = kelly_variant(0.0, 3.0)
    check("kelly_wr0: == 0.0", k == 0.0, f"got {k}")


def test_kelly_edge_one_win():
    """win_rate=1 → 0.0 (边界)"""
    k = kelly_variant(1.0, 3.0)
    check("kelly_wr1: == 0.0", k == 0.0, f"got {k}")


def test_kelly_negative_full():
    """全凯利为负 → 返回 0.0"""
    k = kelly_variant(0.3, 1.0)
    # full = 0.3 - 0.7/1 = -0.4
    # half = 0.0
    check("kelly_neg: == 0.0", k == 0.0, f"got {k}")


def test_kelly_zero_ratio():
    """win_loss_ratio=0 → 0.0"""
    k = kelly_variant(0.5, 0.0)
    check("kelly_ratio0: == 0.0", k == 0.0, f"got {k}")


# ══════════════════════════════════════════
# 5. max_position_per_market_state
# ══════════════════════════════════════════

def test_market_state_trend_strong():
    """上涨强趋势 → 0.20"""
    m = max_position_per_market_state("trend_up", "strong")
    check("mkt_trend_up_strong: == 0.20", abs(m - 0.20) < 0.001, f"got {m}")


def test_market_state_volatile_weak():
    """波动弱→ 0.04"""
    m = max_position_per_market_state("volatile", "weak")
    check("mkt_volatile_weak: == 0.04", abs(m - 0.04) < 0.001, f"got {m}")


def test_market_state_invalid():
    """无效 state → ValueError"""
    try:
        max_position_per_market_state("unknown", "strong")
        check("mkt_invalid: should raise", False)
    except ValueError:
        check("mkt_invalid: ValueError raised", True)


def test_market_state_invalid_strength():
    """有效 state 但无效 strength → ValueError"""
    try:
        max_position_per_market_state("trend_up", "extreme")
        check("mkt_bad_str: should raise", False)
    except ValueError:
        check("mkt_bad_str: ValueError raised", True)


# ══════════════════════════════════════════
# 6. position_size_by_trader_equation
# ══════════════════════════════════════════

def test_pos_by_te_high_conf():
    """高置信度 + 优盈亏比 → 合理仓位"""
    pos = position_size_by_trader_equation(0.65, 0.06, 0.02, 0.02, 0.20, False)
    # kelly_full = 0.65 - 0.35/3 = 0.65 - 0.1167 = 0.5333
    # half = 0.2667, cap = 0.25
    # scale by (0.02/0.02) = 1.0 → 0.25
    # cap 0.20 → 0.20
    check("te_high: <= 0.20", pos <= 0.20, f"got {pos}")
    check("te_high: > 0.10", pos > 0.10, f"got {pos}")


def test_pos_by_te_low_conf():
    """低置信度 → 小仓位"""
    pos = position_size_by_trader_equation(0.20, 0.06, 0.02, 0.02, 0.20, True)
    # kelly_full = 0.20 - 0.80/3 = 0.20 - 0.2667 = -0.0667
    # half = 0.0
    check("te_low: == 0.0", pos == 0.0, f"got {pos}")


def test_pos_by_te_risk_scaling():
    """更高的账户风险 → 更大仓位"""
    pos_low = position_size_by_trader_equation(0.65, 0.06, 0.02, 0.01, 0.20, False)
    pos_high = position_size_by_trader_equation(0.65, 0.06, 0.02, 0.03, 0.20, False)
    check("te_risk: higher_risk_bigger", pos_high >= pos_low, f"{pos_high} vs {pos_low}")


def test_pos_by_te_tplus1():
    """T+1 模式比非 T+1 小"""
    pos_none = position_size_by_trader_equation(0.65, 0.06, 0.02, 0.02, 0.20, False)
    pos_t1 = position_size_by_trader_equation(0.65, 0.06, 0.02, 0.02, 0.20, True)
    check("te_t1: t1 <= no_t1", pos_t1 <= pos_none, f"{pos_t1} vs {pos_none}")
    if pos_none > 0:
        check("te_t1: ratio ~0.8", abs(pos_t1 / pos_none - 0.8) < 0.01, f"{pos_t1}/{pos_none}")


def test_pos_by_te_zero_loss():
    """avg_loss_pct=0 → 0.0"""
    pos = position_size_by_trader_equation(0.65, 0.06, 0.0, 0.02, 0.20)
    check("te_zero_loss: == 0.0", pos == 0.0, f"got {pos}")


def test_pos_by_te_invalid_confidence():
    """confidence 超出范围 → ValueError"""
    try:
        position_size_by_trader_equation(1.5, 0.06, 0.02)
        check("te_bad_conf: should raise", False)
    except ValueError:
        check("te_bad_conf: ValueError raised", True)


# ══════════════════════════════════════════
# 执行
# ══════════════════════════════════════════

if __name__ == "__main__":
    print(f"{'='*60}")
    print(f"  M5 风控模块测试")
    print(f"{'='*60}\n")

    # 1
    print("[trader_equation_evaluate — 基本计算]")
    test_te_basic_a()
    test_te_basic_b()
    test_te_with_historical()
    print()

    # 2
    print("[trader_equation_evaluate — 边界与异常]")
    test_te_invalid_quality()
    test_te_zero_stop()
    test_te_negative_market()
    test_te_not_reject()
    print()

    # 3
    print("[position_size_from_te]")
    test_pos_size_high_quality()
    test_pos_size_reject()
    test_pos_size_pass()
    test_pos_size_missing_key()
    print()

    # 4
    print("[kelly_variant]")
    test_kelly_basic()
    test_kelly_capped()
    test_kelly_edge_zero_win()
    test_kelly_edge_one_win()
    test_kelly_negative_full()
    test_kelly_zero_ratio()
    print()

    # 5
    print("[max_position_per_market_state]")
    test_market_state_trend_strong()
    test_market_state_volatile_weak()
    test_market_state_invalid()
    test_market_state_invalid_strength()
    print()

    # 6
    print("[position_size_by_trader_equation]")
    test_pos_by_te_high_conf()
    test_pos_by_te_low_conf()
    test_pos_by_te_risk_scaling()
    test_pos_by_te_tplus1()
    test_pos_by_te_zero_loss()
    test_pos_by_te_invalid_confidence()
    print()

    # ── 汇总 ──
    print(f"{'='*60}")
    print(f"  结果: {PASS}/{TOTAL} 通过", end="")
    if FAIL > 0:
        print(f", {FAIL} 失败", end="")
    print()
    print(f"{'='*60}")
    sys.exit(0 if FAIL == 0 else 1)
