"""交叉验证 + 3 种改进方案测试

交叉验证: 用 determine_always_in() 直接计算 IC (滚动窗口)
方案 1: 1-day forward window
方案 2: Reverse Always-In sign (-score)
方案 3: Regime-only mode (仅趋势市, 跳过震荡)
"""

import sys
import os
import time
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PAT_stock.data.loader import get_daily
from PAT_stock.state.market_state import determine_always_in


STOCKS = {
    "Large": "601398.SH",
    "Mid": "002522.SZ",
    "Small": "002825.SZ",
}

START_DATE = "20240601"
END_DATE = "20260614"


def compute_forward_return(close: np.ndarray, days: int) -> np.ndarray:
    n = len(close)
    fwd = np.full(n, np.nan)
    for i in range(n - days):
        fwd[i] = (close[i + days] / close[i] - 1) * 100
    return fwd


def compute_scores_and_regimes(df: pd.DataFrame, min_bars: int = 30):
    """Compute always-in scores and regimes for all bars using expanding window."""
    n = len(df)
    scores = np.full(n, np.nan)
    regimes = np.full(n, "", dtype=object)

    for i in range(min_bars, n):
        segment = df.iloc[: i + 1]
        ai = determine_always_in(segment)

        dims = ai.get("dimensions", {})
        score = 0.0
        for d in dims.values():
            score += d.get("score", 0.0) * d.get("weight", 0.0)
        scores[i] = score

        regimes[i] = ai.get("direction", "oscillating")

    return scores, regimes


def compute_ic(scores, fwd_ret):
    """Compute Spearman IC and hit rate."""
    from scipy.stats import spearmanr

    valid = ~(np.isnan(scores) | np.isnan(fwd_ret))
    s = scores[valid]
    r = fwd_ret[valid]

    if len(s) < 10:
        return 0.0, 1.0, 0.0, 0

    ic, pval = spearmanr(s, r)

    # 方向命中率
    nonzero = s != 0
    if nonzero.sum() > 0:
        r_dir = r[nonzero]
        s_dir = s[nonzero]
        hits = ((s_dir > 0) & (r_dir > 0)) | ((s_dir < 0) & (r_dir < 0))
        hit_rate = float(hits.mean())
    else:
        hit_rate = 0.0

    return float(ic), float(pval), hit_rate, int(valid.sum())


def load_and_prepare(ts_code: str):
    df = get_daily(ts_code, START_DATE, END_DATE)
    if df is None or len(df) < 60:
        return None
    return df.sort_values("trade_date").reset_index(drop=True)


def run_baseline(ts_code: str, label: str, fwd_days: int = 5) -> dict:
    """原始方案: 加权分数 vs forward return"""
    df = load_and_prepare(ts_code)
    if df is None:
        return None

    close = df["close"].values
    fwd_ret = compute_forward_return(close, fwd_days)
    scores, _ = compute_scores_and_regimes(df)
    ic, pval, hr, n = compute_ic(scores, fwd_ret)

    return {"ts_code": ts_code, "label": label, "fwd_days": fwd_days,
            "ic": ic, "pval": pval, "hit_rate": hr, "n_obs": n, "mode": "baseline"}


def run_reverse_sign(ts_code: str, label: str, fwd_days: int = 5) -> dict:
    """方案 2: Reverse sign — 用 -score 代替 +score"""
    df = load_and_prepare(ts_code)
    if df is None:
        return None

    close = df["close"].values
    fwd_ret = compute_forward_return(close, fwd_days)
    scores, _ = compute_scores_and_regimes(df)
    scores = -scores  # 反转
    ic, pval, hr, n = compute_ic(scores, fwd_ret)

    return {"ts_code": ts_code, "label": label, "fwd_days": fwd_days,
            "ic": ic, "pval": pval, "hit_rate": hr, "n_obs": n, "mode": "reverse_sign"}


def run_regime_only(ts_code: str, label: str, fwd_days: int = 5) -> dict:
    """方案 3: Regime-only — 仅趋势市信号, 震荡市跳过。regime_score: bullish=+1, bearish=-1, oscillating=0"""
    df = load_and_prepare(ts_code)
    if df is None:
        return None

    close = df["close"].values
    fwd_ret = compute_forward_return(close, fwd_days)
    _, regimes = compute_scores_and_regimes(df)

    # regime → numeric score
    regime_score = np.full(len(regimes), np.nan)
    for i in range(len(regimes)):
        d = regimes[i]
        if d == "bullish":
            regime_score[i] = 1.0
        elif d == "bearish":
            regime_score[i] = -1.0
        # oscillating → NaN (跳过)

    # 仅振荡排除版: regime_score=0 时参与 IC (无方向预期)
    scores_all = np.where(regime_score == -1, -1.0,
                          np.where(regime_score == 1, 1.0, 0.0))
    ic, pval, hr, n = compute_ic(scores_all, fwd_ret)

    # 仅趋势版: 只算 regime_score != 0 的部分
    trend_only_mask = ~np.isnan(regime_score)
    scores_trend = regime_score[trend_only_mask]
    fwd_trend = fwd_ret[trend_only_mask]
    ic_t, pval_t, hr_t, n_t = compute_ic(scores_trend, fwd_trend)

    return {"ts_code": ts_code, "label": label, "fwd_days": fwd_days,
            "ic": ic, "pval": pval, "hit_rate": hr, "n_obs": n,
            "ic_trend_only": ic_t, "hr_trend_only": hr_t, "n_trend_only": n_t,
            "mode": "regime_only"}


def print_experiment_header(title, fwd_days):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print(f"  Forward: {fwd_days}-day | 方法: determine_always_in() 滚动窗口")
    print("=" * 65)


def diagnose_regime_frequency(ts_code: str, label: str):
    """诊断各股票上 regime 分布和分数范围"""
    df = load_and_prepare(ts_code)
    if df is None:
        return

    scores, regimes = compute_scores_and_regimes(df)

    from collections import Counter
    cnt = Counter(regimes[30:])  # skip NaN prefix
    total = sum(cnt.values())
    print(f"\n  [{label}] {ts_code} — Regime 分布 ({total} bars):")
    for regime, count in sorted(cnt.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"      {regime}: {count} ({pct:.1f}%)")

    valid_scores = scores[~np.isnan(scores)]
    print(f"      分数范围: [{valid_scores.min():.4f}, {valid_scores.max():.4f}]")
    print(f"      |score|>0.30: {(np.abs(valid_scores) > 0.30).sum()} bars "
          f"({(np.abs(valid_scores) > 0.30).mean()*100:.1f}%)")


def main():
    experiments = [
        # (模式名, key, 函数, forward天数)
        ("基线 (5d)", "baseline_5d", run_baseline, 5),
        ("方案1: 1d Forward", "baseline_1d", run_baseline, 1),
        ("方案2: Reverse Sign", "reverse_sign", run_reverse_sign, 5),
        ("方案3: Regime-Only", "regime_only", run_regime_only, 5),
    ]

    all_results = []

    for mode_name, mode_key, func, fwd_days in experiments:
        print_experiment_header(mode_name, fwd_days)
        t0 = time.time()
        for label, code in STOCKS.items():
            r = func(code, label, fwd_days)
            if r:
                r["mode_key"] = mode_key
                all_results.append(r)
                if r["mode"] == "regime_only":
                    print(f"  [{label}] {code}: IC={r['ic']:.4f} (p={r['pval']:.4f}) "
                          f"HR={r['hit_rate']:.1%} obs={r['n_obs']}")
                    print(f"          趋势仅: IC={r['ic_trend_only']:.4f} HR={r['hr_trend_only']:.1%} "
                          f"obs={r['n_trend_only']}")
                else:
                    print(f"  [{label}] {code}: IC={r['ic']:.4f} (p={r['pval']:.4f}) "
                          f"HR={r['hit_rate']:.1%} obs={r['n_obs']}")
        print(f"  耗时: {time.time() - t0:.1f}s")

    # Regime 频率诊断
    print("\n" + "=" * 65)
    print("  Regime 频率诊断 (为什么方案3全NaN)")
    print("=" * 65)
    for label, code in STOCKS.items():
        diagnose_regime_frequency(code, label)

    # 汇总表
    print("\n" + "=" * 65)
    print("  汇总对比")
    print("=" * 65)
    header = f"{'方案':<22} {'股票':<14} {'IC':>8} {'p值':>8} {'命中率':>8} {'obs':>6}"
    print(f"  {header}")
    print(f"  {'-'*66}")
    for r in all_results:
        if r["mode"] == "regime_only":
            line = (f"  {r['mode_key']:<22} {r['ts_code']:<14} "
                    f"{r['ic']:>8.4f} {r['pval']:>8.4f} {r['hit_rate']:>7.1%} {r['n_obs']:>6}")
            print(line)
            line2 = (f"  {'trend_only':<22} {r['ts_code']:<14} "
                     f"{r['ic_trend_only']:>8.4f} {'':>8} {r['hr_trend_only']:>7.1%} {r['n_trend_only']:>6}")
            print(line2)
        else:
            line = (f"  {r['mode_key']:<22} {r['ts_code']:<14} "
                    f"{r['ic']:>8.4f} {r['pval']:>8.4f} {r['hit_rate']:>7.1%} {r['n_obs']:>6}")
            print(line)

    # pooled IC (简单平均，区分 5d 和 1d)
    print("\n  各方案 Pooled IC:")
    pooling = [
        ("基线 (5d)", "baseline_5d"),
        ("方案1: 1d Forward", "baseline_1d"),
        ("方案2: Reverse Sign", "reverse_sign"),
    ]
    for name, key in pooling:
        group = [r for r in all_results if r["mode_key"] == key]
        if group:
            avg_ic = np.mean([r["ic"] for r in group])
            avg_hr = np.mean([r["hit_rate"] for r in group])
            print(f"    {name:<22}: IC={avg_ic:.4f}  HR={avg_hr:.1%}")


if __name__ == "__main__":
    main()
