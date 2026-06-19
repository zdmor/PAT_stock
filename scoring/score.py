"""P1.4 评分模块 — 信号综合评分 (2+2 评分, 辅助权重)

评分维度:
  1. 信号K线质量 (Signal Bar Quality)         0.0 ~ 0.4
  2. Always-In 方向一致性 (Trend Alignment)    0.0 ~ 0.3
  3. 关键位上下文 (Key Level Context)         0.0 ~ 0.2
  4. 陷阱和形态组合 (Trap + Pattern Confluence) 0.0 ~ 0.1

总分 = sum(4项), 截断到 [0.0, 1.0]

否决条件 (score = 0.0 regardless):
  A. 信号方向与 Always-In high confidence (>0.8) 方向相反
  B. 信号K线质量 = "weak" 且无任何辅助加分 (key_level == 0 && trap == 0)

Usage:
    from PAT_stock.scoring.score import score_signal, score_all_signals, select_top_signals
"""

from typing import Optional


# ── 强度映射 ──

_STRENGTH_SCORE = {
    "strong": 0.4,
    "normal": 0.25,
    "weak": 0.1,
}
_TWO_BAR_REVERSAL_BONUS = 0.05


# ── 主评分函数 ──


def score_signal(
    signal: dict,
    always_in: dict,
    key_level_context: Optional[dict] = None,
    trap_context: Optional[list] = None,
) -> float:
    """对单个信号计算综合评分 [0.0, 1.0]

    Args:
        signal:             信号字典, 必须含 direction / strength / always_in_aligned
                            Pipeline 输出的信号字段: date, direction, strength,
                            entry_trigger, near_key_level, polarity_nearby,
                            fakeout_nearby, always_in_aligned
        always_in:          Always-In 判定结果字典, 含 direction / confidence / trend_filter
        key_level_context:  关键位上下文, 可选 dict.
                            可含 both_sides / near_key_level / fakeout_nearby / polarity_nearby
        trap_context:       陷阱列表, 可选. 每个元素含 trap_direction

    Returns:
        float 评分 [0.0, 1.0]
    """
    # ── 否决检查 A: 信号方向与 Always-In high confidence 方向相反 ──
    if _is_opposite_to_strong_ai(signal, always_in):
        return 0.0

    # ── 1. 信号K线质量 [0.0, 0.4] ──
    bar_quality = _score_bar_quality(signal)

    # ── 2. Always-In 方向一致性 [0.0, 0.3] ──
    trend_alignment = _score_trend_alignment(signal, always_in)

    # ── 3. 关键位上下文 [0.0, 0.2] ──
    key_level_score = _score_key_level_context(signal, key_level_context)

    # ── 4. 陷阱和形态组合 [0.0, 0.1] ──
    trap_score = _score_trap_confluence(signal, trap_context)

    # ── 否决检查 B: weak 信号 + 无辅助加分 ──
    if _is_weak_without_support(signal, key_level_score, trap_score):
        return 0.0

    # ── 合计 ──
    total = bar_quality + trend_alignment + key_level_score + trap_score
    return max(0.0, min(1.0, total))


def score_all_signals(
    signals: list,
    always_in: dict,
    key_levels: Optional[list] = None,
    traps: Optional[list] = None,
) -> list[dict]:
    """批量评分, 给每个信号加入 score 字段

    遍历 signals 列表, 为每个信号调用 score_signal。
    自动提取关键位上下文 (both_sides 等) 和陷阱上下文传给评分函数。

    Args:
        signals:    信号列表, 每个元素是 dict (pipeline._build_signals 输出格式)
        always_in:  Always-In 判定结果
        key_levels: KeyLevel 对象列表 (可选), 用于提取 both_sides 信息
        traps:      陷阱字典列表 (可选), 用于匹配信号方向

    Returns:
        新列表, 每个信号 dict 新增 score 字段 (不修改原列表)
    """
    # 预处理 key_levels 信息: 价格区间 -> has_both_sides
    # 提高多信号场景的查找效率
    kl_both_sides_cache = _build_kl_both_sides_cache(key_levels)

    result = []
    for sig in signals:
        # 为当前信号构建 key_level_context (提取 both_sides)
        kl_ctx = _build_key_level_context(sig, key_levels, kl_both_sides_cache)

        # 计算评分
        score = score_signal(
            signal=sig,
            always_in=always_in,
            key_level_context=kl_ctx,
            trap_context=traps,
        )

        sig_with_score = dict(sig)
        sig_with_score["score"] = score
        result.append(sig_with_score)

    return result


def select_top_signals(
    signals: list,
    top_n: int = 5,
    min_score: float = 0.15,
) -> list[dict]:
    """按评分过滤排序, 取 Top N

    步骤:
      1. 过滤 score >= min_score
      2. 按 score 降序排列
      3. 取前 top_n 个

    Args:
        signals:   含 score 字段的信号列表
        top_n:     最多返回 N 个 (默认 5)
        min_score: 最低评分阈值 (默认 0.15)

    Returns:
        按 score 降序排列的信号子集, 长度 <= top_n
    """
    # 过滤
    filtered = [s for s in signals if s.get("score", 0.0) >= min_score]
    # 降序
    filtered.sort(key=lambda s: s.get("score", 0.0), reverse=True)
    # 截断
    return filtered[:top_n]


# ══════════════════════════════════════════════════════════
# 内部评分维度
# ══════════════════════════════════════════════════════════


def _score_bar_quality(signal: dict) -> float:
    """信号K线质量评分 [0.0, 0.4]

    映射:
      pinbar_strength "strong"  → 0.4
      pinbar_strength "normal"  → 0.25
      pinbar_strength "weak"    → 0.1
      其他                     → 0.0
    two_bar_reversal 信号额外 +0.05 (不超过 0.4)
    """
    strength = signal.get("strength", "")
    score = _STRENGTH_SCORE.get(strength, 0.0)

    if signal.get("is_two_bar_reversal", False):
        score = min(0.4, score + _TWO_BAR_REVERSAL_BONUS)

    return score


def _score_trend_alignment(signal: dict, always_in: dict) -> float:
    """Always-In 方向一致性 [0.0, 0.3]

    映射:
      aligned + confidence > 0.7  → 0.3
      aligned + confidence 0.3~0.7 → 0.2
      aligned + confidence < 0.3  → 0.1
      not aligned + trend_filter=neutral → 0.1 (中立市场不扣分)
      not aligned + trend_filter!=neutral → 0.0
    """
    aligned = signal.get("always_in_aligned", False)
    confidence = always_in.get("confidence", 0.0)
    trend_filter = always_in.get("trend_filter", "neutral")

    if aligned:
        if confidence > 0.7:
            return 0.3
        elif confidence >= 0.3:
            return 0.2
        else:
            return 0.1

    # not aligned
    if trend_filter == "neutral":
        return 0.1
    return 0.0


def _score_key_level_context(
    signal: dict,
    key_level_context: Optional[dict],
) -> float:
    """关键位上下文评分 [0.0, 0.2]

    取最高分 (非累加):
      near_key_level + both_sides → 0.2
      near_key_level             → 0.15
      fakeout_nearby             → 0.1
      polarity_nearby            → 0.05

    优先读 key_level_context 中的值, 如果没有则回退到 signal 自身的字段。
    """
    near_kl = signal.get("near_key_level", False)
    if key_level_context and "near_key_level" in key_level_context:
        near_kl = key_level_context["near_key_level"]

    both_sides = False
    if key_level_context:
        both_sides = key_level_context.get("both_sides", False)

    # 如果 key_level_context 提供了 both_sides=True, 自动 implied near_key_level=True
    # (你不可能 both_sides 但不在关键位附近)
    if both_sides:
        near_kl = True

    fakeout = signal.get("fakeout_nearby", False)
    if key_level_context and "fakeout_nearby" in key_level_context:
        fakeout = key_level_context["fakeout_nearby"]

    polarity = signal.get("polarity_nearby", False)
    if key_level_context and "polarity_nearby" in key_level_context:
        polarity = key_level_context["polarity_nearby"]

    if near_kl and both_sides:
        return 0.2
    if near_kl:
        return 0.15
    if fakeout:
        return 0.1
    if polarity:
        return 0.05

    return 0.0


def _score_trap_confluence(
    signal: dict,
    trap_context: Optional[list],
) -> float:
    """陷阱和形态组合评分 [0.0, 0.1]

    信号附近有陷阱确认 (trap_direction == signal.direction) → +0.1
    """
    if not trap_context:
        return 0.0

    signal_dir = signal.get("direction", "")
    for trap in trap_context:
        if trap.get("trap_direction", "") == signal_dir:
            return 0.1

    return 0.0


# ══════════════════════════════════════════════════════════
# 否决检查
# ══════════════════════════════════════════════════════════


def _is_opposite_to_strong_ai(signal: dict, always_in: dict) -> bool:
    """信号方向与 Always-In high confidence (>0.8) 方向相反?"""
    ai_dir = always_in.get("direction", "oscillating")
    sig_dir = signal.get("direction", "")
    confidence = always_in.get("confidence", 0.0)

    if confidence <= 0.8:
        return False

    # 映射 Always-In 方向到统一标识
    ai_bullish = ai_dir in ("up", "long", "bullish")
    ai_bearish = ai_dir in ("down", "short", "bearish")

    if not ai_bullish and not ai_bearish:
        return False  # oscillating / mixed → no veto

    if ai_bullish and sig_dir == "bearish":
        return True
    if ai_bearish and sig_dir == "bullish":
        return True

    return False


def _is_weak_without_support(
    signal: dict,
    key_level_score: float,
    trap_score: float,
) -> bool:
    """weak 信号且无任何辅助加分?"""
    strength = signal.get("strength", "")
    if strength != "weak":
        return False
    return key_level_score == 0.0 and trap_score == 0.0


# ══════════════════════════════════════════════════════════
# 内部工具
# ══════════════════════════════════════════════════════════


def _build_kl_both_sides_cache(
    key_levels: Optional[list],
) -> dict:
    """预计算 key_levels 中每个价格区间是否具有 both_sides

    返回 { (price_min, price_max): bool }
    便于在 _build_key_level_context 中快速查找。
    """
    cache = {}
    if not key_levels:
        return cache

    for kl in key_levels:
        price_min = getattr(kl, "price_min", None)
        price_max = getattr(kl, "price_max", None)
        if price_min is not None and price_max is not None:
            both_sides = getattr(kl, "both_sides", False)
            cache[(price_min, price_max)] = both_sides

    return cache


def _build_key_level_context(
    signal: dict,
    key_levels: Optional[list],
    both_sides_cache: Optional[dict] = None,
) -> dict:
    """从信号和关键位列表构建 key_level_context

    检查信号触发价格 (entry_trigger) 附近的关键位是否有 both_sides 属性。

    Args:
        signal:           信号字典
        key_levels:       KeyLevel 对象列表
        both_sides_cache: 预计算的 {(price_min, price_max): bool} 缓存

    Returns:
        dict, 可能含 both_sides 等字段
    """
    ctx = {}
    signal_price = signal.get("entry_trigger")
    if signal_price is None or not key_levels:
        return ctx

    use_cache = both_sides_cache is not None

    for kl in key_levels:
        if use_cache:
            price_min = getattr(kl, "price_min", None)
            price_max = getattr(kl, "price_max", None)
            if price_min is not None and price_max is not None:
                if price_min <= signal_price <= price_max:
                    ctx["near_key_level"] = True
                    key = (price_min, price_max)
                    if both_sides_cache.get(key, False):
                        ctx["both_sides"] = True
                    break
        else:
            price_min = getattr(kl, "price_min", None)
            price_max = getattr(kl, "price_max", None)
            if price_min is not None and price_max is not None:
                if price_min <= signal_price <= price_max:
                    ctx["near_key_level"] = True
                    if getattr(kl, "both_sides", False):
                        ctx["both_sides"] = True
                    break

    return ctx
