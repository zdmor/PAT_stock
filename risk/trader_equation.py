"""M5 交易者方程实时计算 — Brooks核心数学

P(win) * Reward > P(loss) * Risk — 每笔交易都应通过此方程过滤。

核心流程:
  1. 根据信号质量(A/B/C)确定胜率基线, 可选历史胜率覆盖
  2. 计算 Reward_Ratio = target_distance / stop_distance
  3. Expected_Value = Win_Rate * Reward_Ratio - (1 - Win_Rate) * 1
  4. 判定: >0.3=high_quality, 0~0.3=pass, <0=reject
  5. 仓位调整: 基于判定结果 + 账户风险限额

Usage:
    from risk.trader_equation import trader_equation_evaluate, position_size_from_te
    te = trader_equation_evaluate("A", 0.02, 0.06, 1.0)
    pos = position_size_from_te(te, 0.02)
"""

from typing import Optional

# ── 信号质量映射表 ──
_SIGNAL_QUALITY_MAP = {
    "A": {"base_win_rate": 0.55, "adjustment": 1.0},
    "B": {"base_win_rate": 0.45, "adjustment": 0.8},
    "C": {"base_win_rate": 0.35, "adjustment": 0.6},
}


def trader_equation_evaluate(
    signal_quality: str,
    stop_pct: float,
    target_pct: float,
    market_multiplier: float,
    historical_win_rate: Optional[float] = None,
) -> dict:
    """计算交易者方程, 返回期望值及各分量

    Args:
        signal_quality: 信号K线质量, "A" / "B" / "C"
        stop_pct: 止损百分比 (如 0.02 = 2%)
        target_pct: 目标百分比 (如 0.06 = 6%)
        market_multiplier: 市场状态乘数 (0.5~1.5)
        historical_win_rate: 策略历史胜率, 可选, 覆盖质量基线

    Returns:
        dict {
            "expected_value": float,       # 期望值
            "win_rate": float,             # 最终胜率
            "reward_ratio": float,         # 盈亏比
            "position_multiplier": float,  # 仓位乘数 (0.0, 0.5, 1.0)
            "verdict": str                 # "high_quality" / "pass" / "reject"
        }

    Raises:
        ValueError: signal_quality 不为 A/B/C
        ValueError: stop_pct <= 0, target_pct <= 0, market_multiplier <= 0
    """
    # ── 输入验证 ──
    quality_key = signal_quality.upper()
    if quality_key not in _SIGNAL_QUALITY_MAP:
        raise ValueError(
            f"signal_quality 必须为 A/B/C, 收到: {signal_quality!r}"
        )

    if stop_pct <= 0:
        raise ValueError(f"stop_pct 必须 > 0, 收到: {stop_pct}")
    if target_pct <= 0:
        raise ValueError(f"target_pct 必须 > 0, 收到: {target_pct}")
    if market_multiplier <= 0:
        raise ValueError(f"market_multiplier 必须 > 0, 收到: {market_multiplier}")

    if historical_win_rate is not None and not (0 <= historical_win_rate <= 1):
        raise ValueError(
            f"historical_win_rate 须在 [0, 1] 范围内, 收到: {historical_win_rate}"
        )

    # ── 胜率计算 ──
    qinfo = _SIGNAL_QUALITY_MAP[quality_key]
    base_win_rate = historical_win_rate if historical_win_rate is not None else qinfo["base_win_rate"]
    win_rate = base_win_rate * qinfo["adjustment"] * market_multiplier
    win_rate = max(0.0, min(win_rate, 1.0))  # 截断到 [0, 1]

    # ── 盈亏比 ──
    reward_ratio = target_pct / stop_pct

    # ── 期望值 ──
    expected_value = win_rate * reward_ratio - (1 - win_rate) * 1.0

    # ── 判定 ──
    if expected_value > 0.3:
        verdict = "high_quality"
        position_multiplier = 1.0
    elif expected_value >= 0:
        verdict = "pass"
        position_multiplier = 0.5
    else:
        verdict = "reject"
        position_multiplier = 0.0

    return {
        "expected_value": round(expected_value, 4),
        "win_rate": round(win_rate, 4),
        "reward_ratio": round(reward_ratio, 4),
        "position_multiplier": position_multiplier,
        "verdict": verdict,
    }


def position_size_from_te(
    te_result: dict,
    account_risk_pct: float = 0.02,
) -> float:
    """基于交易者方程结果计算仓位百分比

    Args:
        te_result: trader_equation_evaluate() 返回的字典
        account_risk_pct: 账户风险限额 (默认 0.02 = 2%)

    Returns:
        float: 建议仓位百分比 (0.0~1.0), 如 0.15 = 15%
    """
    # ── 输入验证 ──
    required_keys = {"verdict", "position_multiplier", "expected_value"}
    missing = required_keys - set(te_result.keys())
    if missing:
        raise KeyError(
            f"te_result 缺少必要键: {', '.join(sorted(missing))}"
        )

    verdict = te_result["verdict"]
    position_multiplier = te_result["position_multiplier"]
    expected_value = te_result["expected_value"]

    if verdict == "reject":
        return 0.0

    if account_risk_pct <= 0:
        return 0.0

    # ── 基础仓位: 基于 position_multiplier 和 expected_value ──
    # high_quality → 乘数=1.0, 基础 max 18%
    # pass → 乘数=0.5, 基础 max 10%
    if verdict == "high_quality":
        base = 0.18
    elif verdict == "pass":
        base = 0.10
    else:
        return 0.0

    # 用 expected_value 微调: >0.5 上浮, <0.2 下调
    ev_adjust = min(max((expected_value - 0.15) / 0.4, 0.6), 1.2)
    position = base * position_multiplier * ev_adjust

    # 按账户风险限额缩放
    position *= account_risk_pct / 0.02

    # 截断到 [0, 0.20] (单票上限)
    position = max(0.0, min(position, 0.20))

    return round(position, 4)
