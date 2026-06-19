"""
许佳聪《裸K线交易法》2+2评分系统 — A股日线信号质量验证

验证方法:
  1. 从沪深300随机抽30只，取2022-2024日线
  2. 检测Pinbar并做2+2评分（简化版）
  3. 按分数组统计后续20交易日表现
  4. 三重命中标准：突破入场位 / 达到1:1 / 达到1:2
  5. 输出报告

结论用于决定PAT系统核心路线选择（许佳聪 vs Brooks原版）。
"""

import os
import sys
import json
import random
import math
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from PAT_stock.data.loader import get_pro


# ── 配置 ──
SAMPLE_SIZE = 30
START_DATE = "20220101"
END_DATE = "20241231"
LOOKBACK = 20
HOLD = 20

CACHE_DIR = "D:/ClaudeWorkspace/PAT_stock/data_cache"
os.makedirs(CACHE_DIR, exist_ok=True)



# =============================================================
# 步骤1: 数据获取
# =============================================================

def get_hs300_stocks() -> list:
    """获取沪深300最新成分股列表"""
    pro = get_pro()
    try:
        df = pro.index_weight(index_code="000300.SH")
        latest_date = sorted(df["trade_date"].unique())[-1]
        latest = df[df["trade_date"] == latest_date]
        codes = sorted(latest["con_code"].unique())
        print(f"  HS300 成分股数: {len(codes)}, 日期: {latest_date}")
        return codes
    except Exception as e:
        print(f"  HS300 获取失败: {e}, 使用备选列表")
        return []


def fetch_daily(ts_code: str) -> Optional[pd.DataFrame]:
    """获取单只股票日线数据，带 parquet 缓存"""
    safe_name = ts_code.replace(".", "_")
    cache_file = os.path.join(CACHE_DIR, f"{safe_name}.parquet")

    if os.path.exists(cache_file):
        try:
            df = pd.read_parquet(cache_file)
            return df
        except Exception:
            pass

    pro = get_pro()
    try:
        df = pro.daily(ts_code=ts_code, start_date=START_DATE, end_date=END_DATE)
        if df is None or df.empty:
            print(f"    {ts_code}: 无数据")
            return None

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.sort_values("trade_date").reset_index(drop=True)

        try:
            df.to_parquet(cache_file)
        except Exception:
            pass

        time.sleep(0.15)
        return df
    except Exception as e:
        print(f"    {ts_code} 获取失败: {e}")
        time.sleep(0.5)
        return None


# =============================================================
# 步骤2: Pinbar 检测
# =============================================================

def detect_pinbars(df: pd.DataFrame) -> pd.DataFrame:
    """
    检测所有 Pinbar（看涨+看跌），标注信号类型

    核心定量规则:
    - 主影线 >= K线总长的 2/3
    - 看涨 Pinbar: 长下影线 + 小实体在上端 (close >= open 或接近)
    - 看跌 Pinbar: 长上影线 + 小实体在下端 (close <= open 或接近)
    """
    result = df.copy()
    result["range"] = result["high"] - result["low"]
    result["body"] = (result["close"] - result["open"]).abs()
    result["lower_shadow"] = result[["open", "close"]].min(axis=1) - result["low"]
    result["upper_shadow"] = result["high"] - result[["open", "close"]].max(axis=1)

    # 防除零：取整体 range 的 5% 分位为最低阈值
    min_range = max(result["range"].quantile(0.05), 0.01)

    # 看涨 Pinbar: 下影线 >= range*2/3 且 收盘价在K线上半部
    bullish = (
        (result["range"] > min_range) &
        (result["lower_shadow"] >= result["range"] * 2 / 3) &
        (result["close"] >= result["low"] + result["range"] * 0.4)
    )

    # 看跌 Pinbar: 上影线 >= range*2/3 且 收盘价在K线下半部
    bearish = (
        (result["range"] > min_range) &
        (result["upper_shadow"] >= result["range"] * 2 / 3) &
        (result["close"] <= result["low"] + result["range"] * 0.6)
    )

    result["signal"] = 0
    result.loc[bullish, "signal"] = 1
    result.loc[bearish, "signal"] = -1

    return result


# =============================================================
# 步骤3: 2+2 评分（简化版）
# =============================================================

def trend_score(df: pd.DataFrame, idx: int, lookback: int = 20) -> int:
    """
    趋势评分 (0-2)
    2分: 趋势明确 — 前后半段高低点有序排列 + 均线斜率明显
    1分: 趋势模糊
    0分: 无趋势
    """
    start = max(0, idx - lookback)
    window = df.iloc[start:idx+1]
    if len(window) < 10:
        return 0

    closes = window["close"].values
    highs = window["high"].values
    lows = window["low"].values

    x = np.arange(len(closes))
    slope = np.polyfit(x, closes, 1)[0]
    avg_price = np.mean(closes)
    norm_slope = slope / avg_price * 100

    half = len(closes) // 2
    fh_highs, fh_lows = highs[:half], lows[:half]
    sh_highs, sh_lows = highs[half:], lows[half:]

    uptrend = np.mean(sh_highs) > np.mean(fh_highs) and np.mean(sh_lows) > np.mean(fh_lows)
    downtrend = np.mean(sh_highs) < np.mean(fh_highs) and np.mean(sh_lows) < np.mean(fh_lows)

    if abs(norm_slope) > 0.3 and (uptrend or downtrend):
        return 2
    elif abs(norm_slope) > 0.15 or uptrend or downtrend:
        return 1
    else:
        return 0


def key_level_score(df: pd.DataFrame, idx: int, lookback: int = 20) -> int:
    """
    关键位评分 (0-2)
    2分: 影线末端附近有清晰 swing point，且被多次测试
    1分: 有关键位但模糊
    0分: 无明显关键位
    """
    start = max(0, idx - lookback)
    window = df.iloc[start:idx+1]
    if len(window) < 10:
        return 0

    highs = window["high"].values
    lows = window["low"].values
    current_signal = df.iloc[idx]["signal"]

    swing_highs, swing_lows = [], []
    for i in range(2, len(highs) - 2):
        if highs[i] == max(highs[i-2:i+3]):
            swing_highs.append(highs[i])
        if lows[i] == min(lows[i-2:i+3]):
            swing_lows.append(lows[i])

    if current_signal == 1:  # 看涨 -> 看支撑
        pin_low = df.iloc[idx]["low"]
        if len(swing_lows) > 0:
            close_swings = [sl for sl in swing_lows if abs(sl - pin_low) / max(pin_low, 0.01) < 0.015]
            if len(close_swings) >= 2:
                return 2
            elif len(close_swings) >= 1:
                return 1
    elif current_signal == -1:  # 看跌 -> 看阻力
        pin_high = df.iloc[idx]["high"]
        if len(swing_highs) > 0:
            close_swings = [sh for sh in swing_highs if abs(sh - pin_high) / max(pin_high, 0.01) < 0.015]
            if len(close_swings) >= 2:
                return 2
            elif len(close_swings) >= 1:
                return 1

    return 0


def score_signal(df: pd.DataFrame, idx: int) -> dict:
    """对第 idx 根 K 线的信号做 2+2 评分"""
    if idx < LOOKBACK:
        return {"trend": 0, "key_level": 0, "total": 0}

    t_score = trend_score(df, idx, LOOKBACK)
    k_score = key_level_score(df, idx, LOOKBACK)
    total = min(t_score + k_score, 4)

    return {"trend": t_score, "key_level": k_score, "total": total}


# =============================================================
# 步骤4: 三种命中标准的绩效测量
# =============================================================

def measure_signal_outcome(df: pd.DataFrame, idx: int, hold: int = 20) -> dict:
    """
    三重命中标准:
    H1: 价格触及入场位（突破 Pinbar 高/低点）
    H2: 价格达到 1:1 R:R
    H3: 价格达到 1:2 R:R
    """
    signal = df.iloc[idx]["signal"]
    entry_bar = df.iloc[idx]

    end = min(idx + hold + 1, len(df))
    future = df.iloc[idx+1:end]
    if len(future) < 5:
        return {
            "hit_entry": False, "hit_rr1": False, "hit_rr2": False,
            "max_rr": 0.0, "days_to_entry": None, "close_above_entry": False
        }

    if signal == 1:  # 做多
        entry_price = entry_bar["high"]
        stop_price = entry_bar["low"]
        risk = entry_price - stop_price
        if risk <= 0:
            return {
                "hit_entry": False, "hit_rr1": False, "hit_rr2": False,
                "max_rr": 0.0, "days_to_entry": None, "close_above_entry": False
            }

        max_price = future["high"].max()
        actual_max_rr = (max_price - entry_price) / risk
        last_close = future.iloc[-1]["close"]

        hit_entry = future["high"].max() >= entry_price
        hit_rr1 = future["high"].max() >= entry_price + risk * 1.0
        hit_rr2 = future["high"].max() >= entry_price + risk * 2.0

        days_to_entry = None
        if hit_entry:
            hit_idx = future[future["high"] >= entry_price].index[0]
            days_to_entry = int(hit_idx - idx)

        close_above_entry = last_close >= entry_price

    elif signal == -1:  # 做空
        entry_price = entry_bar["low"]
        stop_price = entry_bar["high"]
        risk = stop_price - entry_price
        if risk <= 0:
            return {
                "hit_entry": False, "hit_rr1": False, "hit_rr2": False,
                "max_rr": 0.0, "days_to_entry": None, "close_above_entry": False
            }

        min_price = future["low"].min()
        actual_max_rr = (entry_price - min_price) / risk
        last_close = future.iloc[-1]["close"]

        hit_entry = future["low"].min() <= entry_price
        hit_rr1 = future["low"].min() <= entry_price - risk * 1.0
        hit_rr2 = future["low"].min() <= entry_price - risk * 2.0

        days_to_entry = None
        if hit_entry:
            hit_idx = future[future["low"] <= entry_price].index[0]
            days_to_entry = int(hit_idx - idx)

        close_above_entry = last_close <= entry_price

    else:
        return {
            "hit_entry": False, "hit_rr1": False, "hit_rr2": False,
            "max_rr": 0.0, "days_to_entry": None, "close_above_entry": False
        }

    return {
        "hit_entry": hit_entry,
        "hit_rr1": hit_rr1,
        "hit_rr2": hit_rr2,
        "max_rr": round(actual_max_rr, 2),
        "days_to_entry": days_to_entry,
        "close_above_entry": close_above_entry,
    }


# =============================================================
# 主流程
# =============================================================

def process_stock(ts_code: str) -> list:
    """处理单只股票的全部信号"""
    df = fetch_daily(ts_code)
    if df is None or len(df) < 60:
        return []

    df = detect_pinbars(df)

    signal_rows = []
    signal_indices = df[df["signal"] != 0].index.tolist()

    for idx in signal_indices:
        if idx < LOOKBACK or idx > len(df) - HOLD - 5:
            continue

        sig_type = df.iloc[idx]["signal"]
        scores = score_signal(df, idx)
        outcome = measure_signal_outcome(df, idx, HOLD)

        row = {
            "ts_code": ts_code,
            "trade_date": df.iloc[idx]["trade_date"],
            "open": df.iloc[idx]["open"],
            "high": df.iloc[idx]["high"],
            "low": df.iloc[idx]["low"],
            "close": df.iloc[idx]["close"],
            "signal_type": "bullish" if sig_type == 1 else "bearish",
            "trend_score": scores["trend"],
            "key_level_score": scores["key_level"],
            "total_score": scores["total"],
        }
        row.update(outcome)
        signal_rows.append(row)

    return signal_rows


def compute_stats(subset: pd.DataFrame) -> dict:
    """计算一组信号的统计量"""
    n = len(subset)
    if n == 0:
        return {"count": 0, "entry_hit_rate": 0, "rr1_rate": 0, "rr2_rate": 0,
                "close_win_rate": 0, "avg_max_rr": 0, "avg_days": 0}
    return {
        "count": n,
        "entry_hit_rate": round(subset["hit_entry"].mean() * 100, 1),
        "rr1_rate": round(subset["hit_rr1"].mean() * 100, 1),
        "rr2_rate": round(subset["hit_rr2"].mean() * 100, 1),
        "close_win_rate": round(subset["close_above_entry"].mean() * 100, 1),
        "avg_max_rr": round(subset["max_rr"].mean(), 2),
        "avg_days": round(subset["days_to_entry"].dropna().mean(), 1),
    }


def main():
    print("=" * 60)
    print("许佳聪 2+2 评分系统验证")
    print(f"抽样: 沪深300 {SAMPLE_SIZE} 只 | 区间: {START_DATE} ~ {END_DATE}")
    print("=" * 60)

    # ---- 获取样本 ----
    print("\n[步骤1] 获取沪深300成分股...")
    all_stocks = get_hs300_stocks()
    if len(all_stocks) == 0:
        print("  使用备选股票列表")
        all_stocks = [
            "000001.SZ", "000002.SZ", "000333.SZ", "000651.SZ", "000858.SZ",
            "002415.SZ", "002475.SZ", "300059.SZ", "300124.SZ", "300274.SZ",
            "300308.SZ", "300413.SZ", "300502.SZ", "300750.SZ", "600000.SH",
            "600036.SH", "600309.SH", "600406.SH", "600519.SH", "600585.SH",
            "600690.SH", "600809.SH", "600887.SH", "600900.SH", "601012.SH",
            "601166.SH", "601318.SH", "601398.SH", "601857.SH", "603259.SH",
        ]

    random.seed(42)
    sampled = random.sample(all_stocks, min(SAMPLE_SIZE, len(all_stocks)))
    print(f"  抽中 {len(sampled)} 只: {', '.join(sampled[:5])}...")

    # ---- 获取日线并检测信号 ----
    print("\n[步骤2-3] 获取日线 + Pinbar检测 + 2+2评分...")
    all_signals = []
    stock_count = 0

    for i, code in enumerate(sampled):
        print(f"  [{i+1}/{len(sampled)}] {code}")
        signals = process_stock(code)
        if signals:
            all_signals.extend(signals)
            stock_count += 1

    total_signal_count = len(all_signals)
    print(f"\n  有效样本股票: {stock_count}")
    print(f"  总信号数: {total_signal_count}")

    if total_signal_count == 0:
        print("  无信号，无法继续")
        return

    # ---- 按分数组统计 ----
    print("\n[步骤4] 绩效统计...")
    df_sig = pd.DataFrame(all_signals)
    df_sig["group"] = df_sig["total_score"].apply(
        lambda x: "4" if x == 4 else ("3" if x == 3 else ("2" if x == 2 else "0-1"))
    )

    group_labels = ["4", "3", "2", "0-1"]

    stats_rows = []
    for g in group_labels:
        subset = df_sig[df_sig["group"] == g]
        stats_rows.append((f"总分={g}", compute_stats(subset)))

    high = df_sig[df_sig["total_score"] >= 3]
    low = df_sig[df_sig["total_score"] < 3]
    stats_rows.append((">=3分合并", compute_stats(high)))
    stats_rows.append(("<3分合并", compute_stats(low)))

    # ---- 信号密度 ----
    months = 36
    density = total_signal_count / stock_count / months if stock_count > 0 else 0

    # ---- 生成报告 ----
    print("\n[步骤5] 生成报告...")

    lines = []
    lines.append("# 许佳聪 2+2 信号质量验证报告")
    lines.append("")
    lines.append("## 验证目的")
    lines.append("验证许佳聪《裸K线交易法》2+2评分系统在A股日线的信号质量，决定PAT系统核心路线选择。")
    lines.append("")
    lines.append("## 数据概况")
    lines.append(f"- **验证区间**: {START_DATE} ~ {END_DATE}")
    lines.append(f"- **样本来源**: 沪深300成分股随机抽样 {stock_count} 只")
    lines.append(f"- **总K线数**: ~{stock_count * 730} (估算，730日/只)")
    lines.append(f"- **总信号数**: {total_signal_count}")
    lines.append(f"- **月均信号/只**: {density:.2f}")
    n_bull = len(df_sig[df_sig["signal_type"] == "bullish"])
    n_bear = len(df_sig[df_sig["signal_type"] == "bearish"])
    lines.append(f"- **信号类型**: 看涨 {n_bull} | 看跌 {n_bear}")
    lines.append("")
    lines.append("## 三重命中标准说明")
    lines.append("")
    lines.append("| 标准 | 定义 | 意义 |")
    lines.append("|------|------|------|")
    lines.append("| H1-入场突破 | 20日内价格触及Pinbar高/低点(入场位) | 信号有效性——能否触发入场 |")
    lines.append("| H2-盈亏比1:1 | 20日内价格移动达到1倍风险 | 信号质量——是否走出有意义行情 |")
    lines.append("| H3-盈亏比1:2 | 20日内价格移动达到2倍风险 | 许佳聪系统最低盈亏比门槛 |")
    lines.append("| 收盘胜率 | 持有期末收盘价在入场位之上/之下 | 信号持续性——行情能否维持 |")
    lines.append("")
    lines.append("## 按分组统计")

    # 表头
    header = "| 分组 | 信号数 | H1-入场突破 | H2-盈亏比1:1 | H3-盈亏比1:2 | 收盘胜率 | 平均最大R:R | 平均达标天数 |"
    sep = "|------|--------|------------|-------------|-------------|---------|------------|------------|"
    lines.append("")
    lines.append(header)
    lines.append(sep)
    for label, s in stats_rows:
        lines.append(
            f"| {label} | {s['count']} | {s['entry_hit_rate']}% | {s['rr1_rate']}% | "
            f"{s['rr2_rate']}% | {s['close_win_rate']}% | {s['avg_max_rr']} | {s['avg_days']} |"
        )

    lines.append("")
    lines.append("## 评分分解")

    lines.append("")
    lines.append("### 趋势分维度")
    for s_val in [0, 1, 2]:
        sub = df_sig[df_sig["trend_score"] == s_val]
        if len(sub) == 0:
            continue
        st = compute_stats(sub)
        lines.append(
            f"- 趋势分={s_val}: {st['count']}个信号 | "
            f"H1={st['entry_hit_rate']}% H2={st['rr1_rate']}% H3={st['rr2_rate']}% "
            f"收盘={st['close_win_rate']}% | 平均R:R={st['avg_max_rr']}"
        )

    lines.append("")
    lines.append("### 关键位分维度")
    for s_val in [0, 1, 2]:
        sub = df_sig[df_sig["key_level_score"] == s_val]
        if len(sub) == 0:
            continue
        st = compute_stats(sub)
        lines.append(
            f"- 关键位分={s_val}: {st['count']}个信号 | "
            f"H1={st['entry_hit_rate']}% H2={st['rr1_rate']}% H3={st['rr2_rate']}% "
            f"收盘={st['close_win_rate']}% | 平均R:R={st['avg_max_rr']}"
        )

    lines.append("")
    lines.append("## 结论")
    lines.append("")

    high_entry = high["hit_entry"].mean() * 100
    low_entry = low["hit_entry"].mean() * 100
    high_rr2 = high["hit_rr2"].mean() * 100
    low_rr2 = low["hit_rr2"].mean() * 100
    high_close = high["close_above_entry"].mean() * 100
    low_close = low["close_above_entry"].mean() * 100
    high_rr = high["max_rr"].mean()
    low_rr = low["max_rr"].mean()

    lines.append("### 核心发现")
    lines.append("")
    diff_h1 = high_entry - low_entry
    diff_rr2 = high_rr2 - low_rr2
    diff_close = high_close - low_close

    lines.append(f"**H1-入场突破**: >=3分组 {high_entry:.1f}% vs <3分组 {low_entry:.1f}% (差距 {diff_h1:.1f}pp)")
    lines.append(f"**H3-盈亏比1:2**: >=3分组 {high_rr2:.1f}% vs <3分组 {low_rr2:.1f}% (差距 {diff_rr2:.1f}pp)")
    lines.append(f"**收盘胜率**: >=3分组 {high_close:.1f}% vs <3分组 {low_close:.1f}% (差距 {diff_close:.1f}pp)")
    lines.append(f"**平均最大R:R**: >=3分组 {high_rr:.2f} vs <3分组 {low_rr:.2f}")
    lines.append("")

    # 判断区分度
    if diff_rr2 > 8 or diff_close > 5:
        lines.append("**判定: 2+2评分系统具有实际区分度**")
        lines.append(f"- 高分组在多个维度上显著优于低分组")
        lines.append("- 建议将2+2评分作为信号过滤器纳入PAT系统")
    elif diff_rr2 > 3 or diff_close > 2:
        lines.append("**判定: 区分度有限**")
        lines.append("- 高分组略优于低分组，但差距不足以支撑独立决策")
        lines.append("- 建议作为辅助参考维度，不单独使用")
    else:
        lines.append("**判定: 区分度不足**")
        lines.append("- 2+2评分在本次验证中未能有效区分优劣信号")
        lines.append("- 简化版评分（均线斜率+HH/HL + swing proximity）可能与许佳聪原版存在偏差")
        lines.append("- 建议回退到 Brooks 原版 2B/123/趋势线突破等信号体系")

    # 信号密度判断
    lines.append("")
    lines.append("### 信号密度")
    lines.append(f"- 月均 {density:.2f} 个/只")
    if density >= 1.5:
        lines.append("- 信号充足，可支撑交易频率")
    elif density >= 0.8:
        lines.append("- 信号密度中等，可配合其他过滤器")
    else:
        lines.append("- 信号稀疏")
    lines.append("")

    # 路线建议
    lines.append("### 路线建议")
    lines.append("")
    if high_rr2 > 40 and diff_rr2 > 5:
        lines.append("**建议: 走许佳聪路线**")
        lines.append("- 2+2评分系统在A股日线具有有效区分度，尤其是盈亏比1:2命中率")
        lines.append("- 建议将评分细化并纳入PAT系统的信号过滤层")
        lines.append("- 注意: 本验证使用简化版评分，实际部署前需与许佳聪原版对齐")
    else:
        lines.append("**建议: 倾向Brooks原版路线**")
        lines.append("- 2+2评分系统在本次验证中区分度不足，不足以支撑路线选择")
        lines.append("- 基于数据，建议以 Brooks 原版 2B/123/趋势线突破为主体信号")
        if diff_rr2 > 0 or diff_h1 > 0:
            lines.append("- 许佳聪的Pinbar定义和评分思想可作为辅助过滤器")
            lines.append("- 评分改进方向: 使用更精确的趋势判别（分形维度、ADX）、关键位识别（VVTL、订单流）")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*注意: 本验证使用简化版评分（趋势=均线斜率+HH/HL结构，关键位=swing proximity），可能与许佳聪原版存在偏差*")
    lines.append("*三重命中标准旨在克服A股高波动环境下单一碰触指标的局限性*")

    report = "\n".join(lines)

    output_path = "D:/ClaudeWorkspace/PAT_stock/results/xu_validation_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n  报告已写入: {output_path}")
    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)

    # 控制台摘要
    print("\n[摘要]")
    print(f"  股票: {stock_count} | 信号: {total_signal_count} | 密度: {density:.2f}/月/只")
    print(f"  >=3分: {len(high)}个 | H1={high_entry:.1f}% H2={high_rr2:.1f}% 收盘={high_close:.1f}% R:R={high_rr:.2f}")
    print(f"  <3分:  {len(low)}个 | H1={low_entry:.1f}% H2={low_rr2:.1f}% 收盘={low_close:.1f}% R:R={low_rr:.2f}")
    print(f"  判定: 区分度{'有效' if diff_rr2 > 8 or diff_close > 5 else '有限' if diff_rr2 > 3 or diff_close > 2 else '不足'}")


if __name__ == "__main__":
    main()
