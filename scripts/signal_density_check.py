"""日线信号密度探测 — M1.5 关键关卡

独立运行, 验证 PAT 最根本的前提假设:
  Al Brooks 价格行为信号在日线级别的密度是否足够？

抽样 200 只 A 股 × 2023-2025 日线, 统计:
  - Always-In 判定率 (非 None 占比)
  - High/Low 计数事件频率
  - 信号 K 线频率
  - 综合"信号"密度 (月均 < 3 的股票占比)

Usage:
  cd D:/ClaudeWorkspace
  python PAT_stock/scripts/signal_density_check.py

依赖: AKShare 免费行情数据
"""

import sys
import time
from pathlib import Path
from collections import defaultdict

# 确保 PAT 根目录在 sys.path
_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT))
# ClaudeWorkspace (zhunwo 所在)
_CLAUDE_ROOT = _PROJ_ROOT.parent
if str(_CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_ROOT))

import numpy as np
import pandas as pd

import akshare as ak

# ── 配置 ──────────────────────────────────────────────

SAMPLE_SIZE = 200
START_DATE = "20230101"
END_DATE = "20251231"
MA_PERIOD = 20          # Always-In 用
BODY_RATIO_N = 10       # 最近 N 根 K 线算实体倾向

# ── Step 1: 股票抽样 ──────────────────────────────────

def sample_stocks(n: int = SAMPLE_SIZE) -> list:
    """抽样 n 只 A 股 (东方财富全市场列表)"""
    print(f"[Step 1] 抽样 {n} 只 A 股...")
    df = ak.stock_info_a_code_name()

    # 过滤: 排除北交所 (代码以 4/8/920 开头), 排除ST
    df = df[~df["code"].str.match(r'^(4|8|920)')]
    df = df[~df["name"].str.contains("ST|退", na=False)]

    # 生成 ts_code (东方财富没有后缀区分, 统一按规则映射)
    def _to_ts(code):
        if code.startswith("6"):
            return f"{code}.SH"
        elif code.startswith("920"):
            return f"{code}.BJ"
        else:
            return f"{code}.SZ"

    df["ts_code"] = df["code"].apply(_to_ts)

    # 均匀抽样
    df = df.sort_values("code").reset_index(drop=True)
    if len(df) <= n:
        sample = df["ts_code"].tolist()
    else:
        step = len(df) // n
        indices = [i * step for i in range(n)]
        sample = df.iloc[indices]["ts_code"].tolist()

    print(f"  抽样完成: {len(sample)} 只 (全 A {len(df)} 只)")
    return sample


# ── 数据获取 (东方财富) ────────────────────────────────


def _fetch_eastmoney(ts_code: str) -> pd.DataFrame:
    """获取单只股票日线 (AKShare stock_zh_a_daily)

    使用 sh/sz 前缀格式的接口, 比 stock_zh_a_hist 更稳定。
    """
    symbol = ts_code.split(".")[0]
    prefix = "sh" if symbol.startswith("6") else "sz"
    aksymbol = f"{prefix}{symbol}"

    for attempt in range(3):
        try:
            raw = ak.stock_zh_a_daily(symbol=aksymbol,
                                       start_date=START_DATE,
                                       end_date=END_DATE,
                                       adjust="qfq")
            if raw is None or raw.empty:
                return None

            col_map = {
                "date": "trade_date",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "vol",
                "amount": "amount",
            }
            raw = raw.rename(columns=col_map)
            raw["trade_date"] = pd.to_datetime(raw["trade_date"])
            raw = raw.sort_values("trade_date").reset_index(drop=True)
            return raw[["trade_date", "open", "high", "low", "close", "vol", "amount"]]
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"\n  [RETRY {attempt+1}] {ts_code}: {e} → 等待 {wait}s")
                time.sleep(wait)
                continue
            print(f"\n  [WARN] {ts_code}: 数据获取失败 ({e})")
            return None


# ── Step 2: Always-In 简化版 ──────────────────────────

def always_in_simplified(df: pd.DataFrame) -> pd.Series:
    """Always-In 方向判定 (5 维等权简化版)

    每维度 ±1 (Long/Short), 总分映射:
      score >  0.60 →  1 (Long)
      score < -0.60 → -1 (Short)
      其他          →  0 (None)

    Args:
        df: 含 open, high, low, close 的 DataFrame

    Returns:
        pd.Series: 1=Long, -1=Short, 0=None
    """
    close, high, low = df["close"], df["high"], df["low"]
    n = len(df)

    # 维度 1: 20 缺口棒 (close 连续在 MA20 一侧)
    ma20 = close.rolling(MA_PERIOD).mean()
    above_ma = (close > ma20).astype(int)
    below_ma = (close < ma20).astype(int)
    # 连续计数 (简化: 用近期占比)
    recent_above = above_ma.rolling(MA_PERIOD).sum() / MA_PERIOD
    dim1 = np.where(recent_above >= 0.75, 1, np.where(recent_above <= 0.25, -1, 0))

    # 维度 2: 高低点结构 (20 日最高/最低偏移方向)
    hh20 = high.rolling(MA_PERIOD).max()
    ll20 = low.rolling(MA_PERIOD).min()
    # 最近 5 日最高点 vs 前 15 日最高点 → 在抬升还是下降
    hh5 = high.rolling(5).max()
    ll5 = low.rolling(5).min()
    dim2 = np.where((hh5 > hh20.shift(5)) & (ll5 > ll20.shift(5)), 1,
                    np.where((ll5 < ll20.shift(5)) & (hh5 < hh20.shift(5)), -1, 0))

    # 维度 3: K 线实体倾向 (最近 N 根阳线占比)
    body = close - df["open"]
    bull_ratio = (body > 0).rolling(BODY_RATIO_N).sum() / BODY_RATIO_N
    dim3 = np.where(bull_ratio >= 0.7, 1, np.where(bull_ratio <= 0.3, -1, 0))

    # 维度 4: 回调深度 (近 20 日最高点回落幅度)
    max20 = close.rolling(MA_PERIOD).max()
    pullback_pct = (max20 - close) / max20.replace(0, np.nan)
    dim4 = np.where(pullback_pct < 0.05, 1,   # 几乎不回调 → 强势
                    np.where(pullback_pct > 0.15, -1, 0))  # 深回调 → 弱

    # 维度 5: MA 位置 (close vs MA20 的偏差)
    ma_dev = (close - ma20) / ma20.replace(0, np.nan)
    dim5 = np.where(ma_dev > 0.02, 1, np.where(ma_dev < -0.02, -1, 0))

    # 综合打分 (每维 ±1, 总分范围 -5 ~ +5)
    score = dim1.astype(float) + dim2.astype(float) + \
            dim3.astype(float) + dim4.astype(float) + dim5.astype(float)
    score_norm = score / 5.0  # 归一化到 [-1, 1]

    result = np.where(score_norm > 0.60, 1,
                      np.where(score_norm < -0.60, -1, 0))
    return pd.Series(result, index=df.index, dtype=int)


# ── Step 3: High/Low 计数 ──────────────────────────────

def count_high_low(df: pd.DataFrame, ai_series: pd.Series) -> pd.Series:
    """基于 swing 点做 High/Low 计数

    在 Always-In Long 时: 检测回调中的 lower high (H1, H2, ...)
    在 Always-In Short 时: 检测反弹中的 higher low (L1, L2, ...)

    Args:
        df:        含 open, high, low, close
        ai_series: Always-In 结果 (1/-1/0)

    Returns:
        pd.Series — 计数事件 (1=发生一次计数, 0=无)
    """
    close, high, low = df["close"], df["high"], df["low"]
    n = len(df)
    events = pd.Series(0, index=df.index)

    # 用滚动窗口检测局部极值作为 swing proxy
    window = 5
    is_swing_high = (high == high.rolling(window * 2 + 1, center=True,
                                          min_periods=window).max())
    is_swing_low = (low == low.rolling(window * 2 + 1, center=True,
                                       min_periods=window).min())

    prev_swing_high_price = None
    prev_swing_low_price = None

    for i in range(window * 2, n):
        if ai_series.iloc[i] == 0:
            continue

        ai = ai_series.iloc[i]

        if ai == 1 and is_swing_high.iloc[i]:  # Long 回调: 检测 lower high
            cur_high = high.iloc[i]
            if prev_swing_high_price is not None:
                if cur_high < prev_swing_high_price:  # 更低高点 → H 计数
                    # 需要确认回调前有逆势 bar
                    body = close.iloc[i] - df["open"].iloc[i]
                    if body < 0:  # 阴线确认
                        events.iloc[i] = 1
            prev_swing_high_price = cur_high

        elif ai == -1 and is_swing_low.iloc[i]:  # Short 反弹: 检测 higher low
            cur_low = low.iloc[i]
            if prev_swing_low_price is not None:
                if cur_low > prev_swing_low_price:  # 更高低点 → L 计数
                    body = close.iloc[i] - df["open"].iloc[i]
                    if body > 0:  # 阳线确认
                        events.iloc[i] = 1
            prev_swing_low_price = cur_low

    return events


# ── Step 4: 信号 K 线识别 ──────────────────────────────

def detect_signal_bars(df: pd.DataFrame, ai_series: pd.Series) -> pd.Series:
    """检测信号 K 线

    条件:
      - 方向与 Always-In 一致
      - 实体 > 80% 全幅 (趋势 K 线)
      或
      - 长尾 + 小实体 + 方向指向趋势方向 (反转 K 线)

    Args:
        df:        含 open, high, low, close, vol
        ai_series: Always-In 结果

    Returns:
        pd.Series — True=信号K线
    """
    open_, high, low, close, vol = (
        df["open"], df["high"], df["low"], df["close"], df["vol"])

    body = (close - open_).abs()
    full_range = high - low
    with np.errstate(divide="ignore", invalid="ignore"):
        body_pct = body / full_range

    upper_tail = high - np.maximum(open_, close)
    lower_tail = np.minimum(open_, close) - low

    is_bull = close > open_
    is_bear = close < open_

    # 趋势 K 线: 实体 > 80% 全幅 + 方向正确
    trend_bar = (body_pct > 0.80) & (full_range > 0)
    trend_bull = trend_bar & is_bull & (ai_series == 1)
    trend_bear = trend_bar & is_bear & (ai_series == -1)

    # 反转 K 线: 长影线 (> 60% 全幅) + 小实体 (< 30% 全幅) + 方向正确
    max_tail = np.maximum(upper_tail, lower_tail)
    with np.errstate(divide="ignore", invalid="ignore"):
        tail_pct = max_tail / full_range
    rev_bar = (tail_pct > 0.60) & (body_pct < 0.30) & (full_range > 0)
    # 反转 K 线: 在 Long 中找下影线长 (买方吸收), Short 中找上影线长 (卖方吸收)
    rev_bull = rev_bar & is_bull & (ai_series == 1) & (lower_tail > upper_tail)
    rev_bear = rev_bar & is_bear & (ai_series == -1) & (upper_tail > lower_tail)

    # 放量确认: vol > 20 日均量
    avg_vol = vol.rolling(20).mean()
    vol_confirm = vol > avg_vol * 1.3

    return (trend_bull | trend_bear | rev_bull | rev_bear) & vol_confirm


# ── Step 5: 综合信号判定 ──────────────────────────────

def detect_signals(df: pd.DataFrame) -> pd.DataFrame:
    """对单只股票执行完整检测流程

    Returns:
        含所有检测结果的 DataFrame
    """
    df = df.copy()
    df["ai"] = always_in_simplified(df)
    df["hl_event"] = count_high_low(df, df["ai"])
    df["signal_bar"] = detect_signal_bars(df, df["ai"])

    # 综合信号: Always-In 有方向 AND (High/Low 计数 OR 信号 K 线)
    df["signal"] = (df["ai"] != 0) & (df["hl_event"] | df["signal_bar"])

    return df


# ── Step 6: 聚合统计 ──────────────────────────────────

def aggregate_stats(all_results: dict) -> dict:
    """聚合所有股票的月度信号统计

    Args:
        all_results: {ts_code: DataFrame (含 signal 列)}

    Returns:
        统计字典
    """
    monthly_signals = defaultdict(int)  # (ts_code, year_month) → count
    stock_total_signals = defaultdict(int)  # ts_code → total

    for ts_code, df in all_results.items():
        if df is None or df.empty:
            continue
        if "signal" not in df.columns or "trade_date" not in df.columns:
            continue
        df["trade_date_dt"] = pd.to_datetime(df["trade_date"])
        df["year_month"] = df["trade_date_dt"].dt.strftime("%Y-%m")

        for ym, grp in df.groupby("year_month"):
            cnt = int(grp["signal"].sum())
            monthly_signals[(ts_code, ym)] = cnt
            stock_total_signals[ts_code] += cnt

    return {
        "monthly_signals": monthly_signals,
        "stock_totals": stock_total_signals,
    }


def print_report(stats: dict, n_stocks: int, n_months: int):
    """输出统计报告"""
    monthly_signals = stats["monthly_signals"]
    stock_totals = stats["stock_totals"]

    print("\n" + "=" * 60)
    print("  日线信号密度探测报告")
    print("=" * 60)
    print(f"  样本:       {n_stocks} 只股票")
    print(f"  时间范围:   {START_DATE} — {END_DATE}")
    print(f"  覆盖月数:   {n_months} 个月")
    print(f"  总信号数:   {sum(monthly_signals.values())}")

    # 按月均信号分组统计
    if stock_totals:
        month_avg = {code: total / max(n_months, 1)
                     for code, total in stock_totals.items()}
        avg_vals = list(month_avg.values())

        print(f"\n  月均信号分布:")
        print(f"    中位数:   {np.median(avg_vals):.2f}")
        print(f"    均值:     {np.mean(avg_vals):.2f}")
        print(f"    标准差:   {np.std(avg_vals):.2f}")

        pcts = [10, 25, 50, 75, 90]
        print(f"    分位数:")
        for p in pcts:
            print(f"      P{p}: {np.percentile(avg_vals, p):.2f}")

        # 核心指标: < 3 的股票占比
        below_3 = sum(1 for v in avg_vals if v < 3)
        below_pct = below_3 / len(avg_vals) * 100
        print(f"\n  >>> 月均信号 < 3 的股票: {below_3}/{len(avg_vals)} "
              f"({below_pct:.1f}%)")

        # 分段统计
        bins = [(0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 100)]
        print(f"\n  分段分布 (月均信号):")
        for lo, hi in bins:
            cnt = sum(1 for v in avg_vals if lo <= v < hi)
            print(f"    [{lo:>2}, {hi:>3}): {cnt:>4} 只 ({cnt/len(avg_vals)*100:5.1f}%)")

        # 判定
        print(f"\n  ┌{'─' * 56}┐")
        if below_pct > 70:
            print(f"  │ VERDICT: FAIL — {below_pct:.0f}% 股票月均 < 3 信号                │")
            print(f"  │ 建议: 转 60 分钟线为主时间框架, 或降低信号密度标准         │")
        elif below_pct > 40:
            print(f"  │ VERDICT: MARGINAL — {below_pct:.0f}% 股票月均 < 3                 │")
            print(f"  │ 建议: 筛选高流动性股票池, 或引入 60 分钟线辅助             │")
        else:
            print(f"  │ VERDICT: PASS — 仅 {below_pct:.0f}% 股票月均 < 3                     │")
            print(f"  │ 日线信号密度足够, 继续 M2 开发                            │")
        print(f"  └{'─' * 56}┘")

    # Always-In 判定率
    print(f"\n  Always-In 判定率 (非 None 占比):")
    # 在所有已处理数据中统计
    # (这个统计在 process_stocks 里做)


# ── 主流程 ────────────────────────────────────────────

def process_stocks(stocks: list) -> dict:
    """批量处理股票, 返回结果字典"""
    results = {}
    total = len(stocks)
    ai_non_none_rates = []

    for idx, ts_code in enumerate(stocks):
        print(f"\r  [{idx+1:>3}/{total}] {ts_code} ...", end="", flush=True)

        df = _fetch_eastmoney(ts_code)
        if df is None or len(df) < MA_PERIOD * 3:
            continue

        try:
            df = detect_signals(df)
        except Exception as e:
            print(f"\n  [ERR] {ts_code}: 检测失败 ({e})")
            continue

        # Always-In 统计
        if "ai" in df.columns:
            rate = (df["ai"] != 0).mean()
            ai_non_none_rates.append(rate)

        results[ts_code] = df

    print()
    if ai_non_none_rates:
        median_ai_rate = np.median(ai_non_none_rates)
        print(f"\n  Always-In 非 None 判定率: "
              f"中位数 {median_ai_rate:.2%}, "
              f"均值 {np.mean(ai_non_none_rates):.2%}")
    return results


def main():
    t0 = time.time()

    # Step 1: 抽样
    stocks = sample_stocks(SAMPLE_SIZE)

    # Step 2-5: 逐个处理
    print(f"\n[Step 2-5] 数据获取 + 信号检测...")
    results = process_stocks(stocks)

    n_processed = len(results)
    if n_processed == 0:
        print("\n[FATAL] 没有成功处理任何股票, 请检查数据源")
        return

    # Step 6: 统计
    n_months = len(pd.date_range(START_DATE, END_DATE, freq="MS"))
    stats = aggregate_stats(results)
    print_report(stats, n_processed, n_months)

    elapsed = time.time() - t0
    print(f"\n总耗时: {elapsed:.0f}s ({n_processed} 只股票)")


if __name__ == "__main__":
    main()
