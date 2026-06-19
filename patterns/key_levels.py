"""P1.2a 水平关键位检测 — Swing 点聚类 + 反向合并 + 极性 + 假突破

检测水平支撑/阻力位:
  Step 1: 逐 bar 检测 swing high/low (向量化, 复用 utils.indicators)
  Step 2: 按价格分别聚类 (Swing High / Swing Low)
  Step 3: 反向合并 — 重叠区间合并为 mixed 类型
  Step 4: 属性计算 (strength / touch_count / recency / both_sides)
  Step 5: 极性转换记录
  Step 6: 假突破记录

Usage:
    from patterns.key_levels import detect_key_levels, KeyLevel
    levels, meta = detect_key_levels(df)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd

from PAT_stock.utils.indicators import (
    body_size,
    upper_shadow,
    lower_shadow,
    atr,
    swing_high,
    swing_low,
)


# ── 数据类 ────────────────────────────────────────────

@dataclass
class KeyLevel:
    """水平关键位

    14 个字段:
      level_price / formation_type / price_min / price_max
      / strength / swing_count / touch_count
      / recency_weighted_strength / both_sides
      / first_date / last_date / cluster_prices
      / polarity_flips / fakeout_history
    """

    level_price: float                          # 聚类中心价 (中位数)
    formation_type: str = ""                    # "swing_high_cluster" | "swing_low_cluster" | "mixed"
    price_min: float = 0.0                      # 聚类内最低价
    price_max: float = 0.0                      # 聚类内最高价
    strength: int = 0                           # 强度评分 0-10
    swing_count: int = 0                        # 聚类内 swing 点数
    touch_count: int = 0                        # 触及该区间的 bar 总数
    recency_weighted_strength: float = 0.0      # 时效加权强度
    both_sides: bool = False                    # 是否两侧测试
    first_date: str = ""                        # 首次出现 YYYYMMDD
    last_date: str = ""                         # 最近日期 YYYYMMDD
    cluster_prices: list = field(default_factory=list)        # 聚类所有 swing 价格
    polarity_flips: list = field(default_factory=list)        # [{date, from, to}]
    fakeout_history: list = field(default_factory=list)       # [{date, direction, depth_pct}]


# ── 主检测函数 ────────────────────────────────────────


def detect_key_levels(
    df: pd.DataFrame,
    swing_window: int = 5,
    cluster_tolerance: float = 0.015,
    min_absolute_tolerance: float = 0.10,
    min_swing_count: int = 2,
    recency_half_life: int = 60,
) -> Tuple[List[KeyLevel], dict]:
    """检测水平关键位

    Args:
        df:                    OHLC DataFrame
        swing_window:          swing 检测左右窗口 (默认 5)
        cluster_tolerance:     聚类容差 (比例, 默认 0.015 = 1.5%)
        min_absolute_tolerance:最小绝对容差 (元, 默认 0.10), 保护低价股
        min_swing_count:       聚类最少 swing 点数 (低于此值过滤)
        recency_half_life:     时效半衰期 (bar 数, 默认 60 ≈ 3 个月)

    Returns:
        Tuple[List[KeyLevel], dict] — (关键位列表, 元信息)
        meta: {swing_count, swing_density, quality_warning, total_bars}
    """
    # ── 边界: 空 DataFrame / 数据不足 ──
    n = len(df)
    if df.empty or n < swing_window * 2 + 1:
        return [], {"swing_count": 0, "swing_density": 0.0,
                     "quality_warning": "insufficient_data", "total_bars": n}

    # ── 输入验证 ──
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise KeyError(
            f"key_levels.detect_key_levels requires columns: "
            f"{', '.join(sorted(required))}"
        )

    has_date = "trade_date" in df.columns

    # ── Step 1: Swing High / Swing Low 检测 (向量化, 复用 utils.indicators) ──
    sh_mask = swing_high(df, left=swing_window, right=swing_window)
    sl_mask = swing_low(df, left=swing_window, right=swing_window)

    highs = df["high"].values
    lows = df["low"].values

    swing_highs = [(i, float(highs[i])) for i in range(n) if sh_mask.iloc[i]]
    swing_lows  = [(i, float(lows[i]))  for i in range(n) if sl_mask.iloc[i]]

    n_swing = len(swing_highs) + len(swing_lows)
    swing_density = n_swing / max(n, 1)

    # Quality warning based on swing density (design §4.1)
    quality_warning = ""
    if swing_density > 0.20:
        quality_warning = "high_density"
    elif n_swing < 3:
        quality_warning = "low_density"

    # 平坦数据 / 无波动过滤: swing 点过多 (超过一半 bar) → 视为无有效 swing
    FLAT_DATA_THRESHOLD = 0.5
    if len(swing_highs) > n * FLAT_DATA_THRESHOLD or len(swing_lows) > n * FLAT_DATA_THRESHOLD:
        return [], {"swing_count": 0, "swing_density": round(swing_density, 4),
                     "quality_warning": "flat_data", "total_bars": n}

    if not swing_highs and not swing_lows:
        return [], {"swing_count": 0, "swing_density": round(swing_density, 4),
                     "quality_warning": quality_warning, "total_bars": n}

    # ── Step 2: 水平聚类 (Swing High / Swing Low 分别聚类) ──

    def _cluster_points(points, tol, min_abs_tol, min_count):
        """按价格排序后一次扫描聚类 (EITHER 相对 OR 绝对容差)

        使用聚类均值作为参考价格，比末点更稳定。
        合并条件: 相对距离 < tol 或者 绝对距离 < min_abs_tol。
        """
        if not points:
            return []
        points_sorted = sorted(points, key=lambda x: x[1])
        clusters = []
        current = [points_sorted[0]]
        current_prices = [points_sorted[0][1]]

        for p in points_sorted[1:]:
            cluster_mean = sum(current_prices) / len(current_prices)
            rel_dist = abs(p[1] - cluster_mean) / cluster_mean if cluster_mean > 0 else 0
            abs_dist = abs(p[1] - cluster_mean)
            if rel_dist <= tol or abs_dist <= min_abs_tol:
                current.append(p)
                current_prices.append(p[1])
            else:
                if len(current) >= min_count:
                    clusters.append(current)
                current = [p]
                current_prices = [p[1]]

        if len(current) >= min_count:
            clusters.append(current)

        return clusters

    high_clusters = _cluster_points(swing_highs, cluster_tolerance, min_absolute_tolerance, min_swing_count)
    low_clusters  = _cluster_points(swing_lows,  cluster_tolerance, min_absolute_tolerance, min_swing_count)

    # ── Step 3: 反向合并 (重叠区间 → mixed) ──

    def _cluster_range(points):
        prices = [p[1] for p in points]
        return float(min(prices)), float(max(prices))

    def _overlaps(r1, r2):
        """两个价格区间是否重叠"""
        return r1[1] >= r2[0] and r2[1] >= r1[0]

    # 预处理: 计算每个 cluster 的价格区间
    h_ranges = [_cluster_range(c) for c in high_clusters]
    l_ranges = [_cluster_range(c) for c in low_clusters]

    merged_h = set()   # 已合并的高位 cluster 索引
    merged_l = set()   # 已合并的低位 cluster 索引
    all_clusters = []  # [(formation_type, [(index, price), ...])]

    for hi, hc in enumerate(high_clusters):
        if hi in merged_h:
            continue
        hr = h_ranges[hi]
        # 查找所有重叠的 low cluster
        overlap_indices = []
        for li, lc in enumerate(low_clusters):
            if li in merged_l:
                continue
            if _overlaps(hr, l_ranges[li]):
                overlap_indices.append(li)

        if overlap_indices:
            # 合并
            merged_points = list(hc)
            for li in overlap_indices:
                merged_points.extend(low_clusters[li])
                merged_l.add(li)
            merged_h.add(hi)
            all_clusters.append(("mixed", merged_points))
        else:
            merged_h.add(hi)
            all_clusters.append(("swing_high_cluster", hc))

    # 未合并的 low clusters
    for li, lc in enumerate(low_clusters):
        if li not in merged_l:
            all_clusters.append(("swing_low_cluster", lc))

    # ── Step 4: 属性计算 ──

    # ATR 用于触摸缓冲
    atr_vals = atr(df).values

    key_levels = []

    for formation_type, points in all_clusters:
        prices = [p[1] for p in points]
        level_price = float(np.median(prices))
        price_min_val = float(min(prices))
        price_max_val = float(max(prices))
        s_count = len(points)

        # touch_count: bar range 与 level_price ± buffer 有交集
        # 缓冲 = 0.5 × ATR; ATR NaN 时退回到 cluster 半宽
        cluster_half_width = (price_max_val - price_min_val) / 2
        buffer_vals = np.where(
            np.isnan(atr_vals),
            cluster_half_width,
            0.5 * atr_vals,
        )
        touch_mask = (lows <= level_price + buffer_vals) & (highs >= level_price - buffer_vals)
        touch_indices = np.where(touch_mask)[0].tolist()
        touch_cnt = int(touch_mask.sum())

        # strength: min(10, swing_count + touch_count), both_sides ×1.5
        strength_val = min(10, s_count + touch_cnt)

        # both_sides: mixed 类型即为两侧测试
        both_sides = formation_type == "mixed"

        # both_sides ×1.5 加权
        if both_sides:
            strength_val = min(10, int(strength_val * 1.5))

        # recency_weighted_strength: 指数衰减, 半衰期 recency_half_life
        last_bar = n - 1
        lam = np.log(2) / recency_half_life
        recency = 0.0
        for idx in touch_indices:
            recency += np.exp(-lam * (last_bar - idx))

        # 日期
        cluster_indices = [p[0] for p in points]
        if has_date:
            first_date = str(df["trade_date"].iloc[min(cluster_indices)])
            last_date = str(df["trade_date"].iloc[max(cluster_indices)])
        else:
            first_date = str(int(min(cluster_indices)))
            last_date = str(int(max(cluster_indices)))

        # ── Step 5: 极性转换记录 ──
        polarity_flips = _detect_polarity_flips(
            df, touch_indices, price_min_val, price_max_val, has_date
        )

        # ── Step 6: 假突破记录 ──
        fakeout_history = _detect_fakeouts(
            df, touch_indices, price_min_val, price_max_val, has_date
        )

        key_levels.append(KeyLevel(
            level_price=level_price,
            formation_type=formation_type,
            price_min=price_min_val,
            price_max=price_max_val,
            strength=strength_val,
            swing_count=s_count,
            touch_count=touch_cnt,
            recency_weighted_strength=round(recency, 4),
            both_sides=both_sides,
            first_date=first_date,
            last_date=last_date,
            cluster_prices=[float(p) for p in prices],
            polarity_flips=polarity_flips,
            fakeout_history=fakeout_history,
        ))

    # ── 输出元信息 ──
    meta = {
        "swing_count": n_swing,
        "swing_density": round(swing_density, 4),
        "quality_warning": quality_warning,
        "total_bars": n,
    }

    return key_levels, meta


# ── 极性转换检测 ──────────────────────────────────────


def _detect_polarity_flips(
    df: pd.DataFrame,
    touch_indices: list,
    price_min: float,
    price_max: float,
    has_date: bool,
) -> list:
    """检测关键位的支撑↔阻力极性转换

    规则:
      对相同关键位的连续两次测试:
        - 第一次为支撑 (价格从下方触及) 且第二次为阻力 (价格从上方触及)
          → 记录 polarity_flip {date, from: support, to: resistance}
        - 反之亦然
    """
    if len(touch_indices) < 2:
        return []

    closes = df["close"].values
    # 分类每次触碰
    events = []
    for idx in sorted(touch_indices):
        c = closes[idx]
        if c < price_min:
            events.append({"idx": idx, "type": "support"})
        elif c > price_max:
            events.append({"idx": idx, "type": "resistance"})
        # close 在区间内 → 不参与极性判断

    flips = []
    for j in range(len(events) - 1):
        first = events[j]
        second = events[j + 1]
        if first["type"] != second["type"]:
            date_str = (
                str(df["trade_date"].iloc[second["idx"]])
                if has_date
                else str(int(second["idx"]))
            )
            flips.append({
                "date": date_str,
                "from": first["type"],
                "to": second["type"],
            })

    return flips


# ── 假突破检测 ────────────────────────────────────────


def _detect_fakeouts(
    df: pd.DataFrame,
    touch_indices: list,
    price_min: float,
    price_max: float,
    has_date: bool,
) -> list:
    """检测关键位的假突破

    规则:
      - 价格突破 price_max 或 price_min 超过 0.1%
      - 随后 3 根 K 线内收盘价回到区间内
      → 记录为假突破
    """
    if not touch_indices:
        return []

    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)

    fakeouts = []
    for idx in sorted(touch_indices):
        h = highs[idx]
        l = lows[idx]

        broke_above = price_max > 0 and h > price_max * 1.001
        broke_below = price_min > 0 and l < price_min * 0.999

        if broke_above:
            depth_pct = round((h - price_max) / price_max * 100, 2)
            # 检查 3 根 K 线内是否收回
            returned = False
            for k in range(idx + 1, min(idx + 4, n)):
                if closes[k] <= price_max:
                    returned = True
                    break
            if returned:
                date_str = (
                    str(df["trade_date"].iloc[idx])
                    if has_date
                    else str(int(idx))
                )
                fakeouts.append({
                    "date": date_str,
                    "direction": "above",
                    "depth_pct": depth_pct,
                })

        elif broke_below:
            depth_pct = round((price_min - l) / price_min * 100, 2)
            returned = False
            for k in range(idx + 1, min(idx + 4, n)):
                if closes[k] >= price_min:
                    returned = True
                    break
            if returned:
                date_str = (
                    str(df["trade_date"].iloc[idx])
                    if has_date
                    else str(int(idx))
                )
                fakeouts.append({
                    "date": date_str,
                    "direction": "below",
                    "depth_pct": depth_pct,
                })

    return fakeouts


# ── 下游便捷接口 ──────────────────────────────────────


def key_levels_summary(levels: List[KeyLevel], price_current: float) -> str:
    """生成人类可读的关键位摘要"""
    if not levels:
        return "No key levels detected."

    above = [kl for kl in levels if kl.level_price > price_current]
    below = [kl for kl in levels if kl.level_price < price_current]

    above.sort(key=lambda kl: kl.level_price)
    below.sort(key=lambda kl: kl.level_price, reverse=True)

    lines = []
    for i, kl in enumerate(reversed(above)):
        tag = f"R{i+1}"
        bs = " [S/R]" if kl.both_sides else ""
        lines.append(
            f"  {tag}  {kl.price_min:.2f} - {kl.price_max:.2f}  "
            f"strength={kl.strength}  last={kl.last_date}{bs}"
        )

    lines.append(f"  ── current {price_current:.2f} ──")

    for i, kl in enumerate(below):
        tag = f"S{i+1}"
        bs = " [S/R]" if kl.both_sides else ""
        lines.append(
            f"  {tag}  {kl.price_min:.2f} - {kl.price_max:.2f}  "
            f"strength={kl.strength}  last={kl.last_date}{bs}"
        )

    return "\n".join(lines)


def levels_near_price(
    levels: List[KeyLevel],
    price: float,
    threshold: float = 0.01,
) -> List[KeyLevel]:
    """返回价格附近的关键位 (相对距离 < threshold)"""
    if not levels:
        return []
    return [
        kl for kl in levels
        if abs(kl.level_price - price) / price < threshold
    ]


def nearest_level(levels: List[KeyLevel], price: float) -> Optional[KeyLevel]:
    """返回离当前价最近的关键位"""
    if not levels:
        return None
    return min(levels, key=lambda kl: abs(kl.level_price - price))
