"""M5 仓位管理 — Brooks仓位公式（交易者方程应用）

提供三个核心工具:
  1. kelly_variant — 半凯利 + 上限截断
  2. max_position_per_market_state — 市场状态仓位上限
  3. position_size_by_trader_equation — 交易者方程仓位计算

Usage:
    from risk.position_sizing import (
        kelly_variant,
        max_position_per_market_state,
        position_size_by_trader_equation,
    )
    kelly = kelly_variant(0.55, 3.0)
    max_pos = max_position_per_market_state("trend_up", "strong")
    pos = position_size_by_trader_equation(0.65, 0.06, 0.02)
"""

from typing import Optional

# ── 市场状态仓位上限映射 ──
# state: {trend_strength: max_allocation}
_MARKET_STATE_LIMITS = {
    "trend_up": {
        "strong": 0.20,
        "moderate": 0.15,
        "weak": 0.10,
    },
    "trend_down": {
        "strong": 0.05,
        "moderate": 0.08,
        "weak": 0.10,
    },
    "range": {
        "strong": 0.12,
        "moderate": 0.10,
        "weak": 0.06,
    },
    "volatile": {
        "strong": 0.08,
        "moderate": 0.06,
        "weak": 0.04,
    },
    "quiet": {
        "strong": 0.15,
        "moderate": 0.12,
        "weak": 0.08,
    },
}


def kelly_variant(win_rate: float, win_loss_ratio: float) -> float:
    """凯利变体 (Brooks保守版: 半凯利 + 上限截断)

    Kelly% = win_rate - (1 - win_rate) / win_loss_ratio
    返回值 = max(0, min(kelly%, 0.25)) / 2  (半凯利 + 上限25%)

    Args:
        win_rate: 胜率 (0.0~1.0)
        win_loss_ratio: 盈亏比 (>0)

    Returns:
        float: 建议仓位比例 (0.0~0.25)
    """
    # ── 输入验证 ──
    if win_rate <= 0.0 or win_rate >= 1.0:
        return 0.0
    if win_loss_ratio <= 0.0:
        return 0.0

    # ── 全凯利 ──
    kelly_full = win_rate - (1.0 - win_rate) / win_loss_ratio

    # ── 半凯利 + 上限截断 ──
    kelly_half = max(0.0, kelly_full) / 2.0
    kelly_capped = min(kelly_half, 0.25)

    return round(kelly_capped, 4)


def max_position_per_market_state(state: str, trend_strength: str) -> float:
    """根据市场状态返回最大仓位限制

    Args:
        state: 市场状态
            "trend_up" / "trend_down" / "range" / "volatile" / "quiet"
        trend_strength: 趋势强度
            "strong" / "moderate" / "weak"

    Returns:
        float: 最大仓位比例 (0.0~0.20)

    Raises:
        ValueError: 不支持的 state 或 trend_strength
    """
    state_key = state.lower()
    strength_key = trend_strength.lower()

    if state_key not in _MARKET_STATE_LIMITS:
        raise ValueError(
            f"不支持的 market_state: {state!r}. "
            f"可选: {', '.join(sorted(_MARKET_STATE_LIMITS.keys()))}"
        )

    strength_map = _MARKET_STATE_LIMITS[state_key]
    if strength_key not in strength_map:
        raise ValueError(
            f"不支持的 trend_strength: {trend_strength!r} 用于 {state}. "
            f"可选: {', '.join(sorted(strength_map.keys()))}"
        )

    return round(strength_map[strength_key], 4)


def position_size_by_trader_equation(
    confidence: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    account_risk_pct: float = 0.02,
    max_single_pct: float = 0.20,
    t_plus_1: bool = True,
) -> float:
    """Brooks 仓位公式: 基于交易者方程计算建议仓位

    流程:
      1. win_loss_ratio = avg_win_pct / avg_loss_pct
      2. kelly = kelly_variant(confidence, win_loss_ratio)
      3. 按账户风险限额缩放
      4. 按单票上限截断
      5. T+1 市场额外保守乘数

    Args:
        confidence: 成功率 (0.0~1.0)
        avg_win_pct: 平均盈利百分比 (如 0.06 = 6%)
        avg_loss_pct: 平均亏损百分比 (如 0.02 = 2%)
        account_risk_pct: 账户风险限额 (默认 0.02 = 2%)
        max_single_pct: 单票上限 (默认 0.20 = 20%)
        t_plus_1: T+1 市场更保守 (默认 True, 乘 0.8)

    Returns:
        float: 建议仓位百分比 (0.0~1.0)
    """
    # ── 输入验证 ──
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence 须在 [0, 1] 范围内, 收到: {confidence}")
    if avg_win_pct < 0:
        raise ValueError(f"avg_win_pct 不能为负, 收到: {avg_win_pct}")
    if avg_loss_pct < 0:
        raise ValueError(f"avg_loss_pct 不能为负, 收到: {avg_loss_pct}")
    if account_risk_pct <= 0 or account_risk_pct > 1:
        raise ValueError(f"account_risk_pct 须在 (0, 1] 范围内, 收到: {account_risk_pct}")
    if max_single_pct <= 0 or max_single_pct > 1:
        raise ValueError(f"max_single_pct 须在 (0, 1] 范围内, 收到: {max_single_pct}")

    # ── 边界: 亏损为零无法计算盈亏比 ──
    if avg_loss_pct <= 0:
        return 0.0
    if confidence <= 0.0:
        return 0.0
    if avg_win_pct <= 0.0:
        return 0.0

    # ── 盈亏比 ──
    win_loss_ratio = avg_win_pct / avg_loss_pct

    # ── 半凯利 ──
    kelly = kelly_variant(confidence, win_loss_ratio)

    # ── 按账户风险限额缩放 ──
    position = kelly * (account_risk_pct / 0.02)

    # ── 按单票上限截断 ──
    position = min(position, max_single_pct)

    # ── T+1 保守乘数 ──
    if t_plus_1:
        position *= 0.8

    # ── 最终截断 ──
    position = max(0.0, position)

    return round(position, 4)
