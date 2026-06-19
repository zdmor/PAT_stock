"""60-min IC 测试: 验证 Always-In 在 60 分钟线上是否仍为负 IC

使用 Sina 60-min K-line API 获取数据，调用 determine_always_in() 滚动窗口。
"""

import sys
import os
import time
import warnings
import requests
import json
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PAT_stock.state.market_state import determine_always_in

STOCKS = {
    "Large": "601398.SH",
    "Mid": "002522.SZ",
    "Small": "002825.SZ",
}

SINA_SYMBOLS = {
    "601398.SH": "sh601398",
    "002522.SZ": "sz002522",
    "002825.SZ": "sz002825",
}


def fetch_sina_60min(sina_symbol: str) -> pd.DataFrame:
    """Fetch 60-min kline data from Sina API."""
    url = (f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/'
           f'CN_MarketData.getKLineData?symbol={sina_symbol}&scale=60&ma=no&datalen=2000')
    r = requests.get(url, timeout=15)
    data = r.json()
    if not data:
        return None

    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["day"])
    df = df.sort_values("time").reset_index(drop=True)
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    df["trade_date"] = df["time"].dt.strftime("%Y%m%d")
    return df


def compute_forward_return(close: np.ndarray, days: int) -> np.ndarray:
    n = len(close)
    fwd = np.full(n, np.nan)
    for i in range(n - days):
        fwd[i] = (close[i + days] / close[i] - 1) * 100
    return fwd


def compute_scores(df: pd.DataFrame, min_bars: int = 30, reverse_sign: bool = False):
    """Compute always-in scores for all bars using expanding window."""
    n = len(df)
    scores = np.full(n, np.nan)
    regimes = np.full(n, "", dtype=object)

    for i in range(min_bars, n):
        segment = df.iloc[: i + 1]
        params = {"reverse_sign": reverse_sign} if reverse_sign else {}
        ai = determine_always_in(segment, params)

        dims = ai.get("dimensions", {})
        score = 0.0
        for d in dims.values():
            score += d.get("score", 0.0) * d.get("weight", 0.0)
        scores[i] = score
        regimes[i] = ai.get("direction", "oscillating")

    return scores, regimes


def compute_ic(scores, fwd_ret):
    from scipy.stats import spearmanr

    valid = ~(np.isnan(scores) | np.isnan(fwd_ret))
    s = scores[valid]
    r = fwd_ret[valid]

    if len(s) < 10:
        return 0.0, 1.0, 0.0, 0

    ic, pval = spearmanr(s, r)
    nonzero = s != 0
    if nonzero.sum() > 0:
        r_dir = r[nonzero]
        s_dir = s[nonzero]
        hits = ((s_dir > 0) & (r_dir > 0)) | ((s_dir < 0) & (r_dir < 0))
        hr = float(hits.mean())
    else:
        hr = 0.0

    return float(ic), float(pval), hr, int(valid.sum())


def run_test(ts_code: str, label: str, fwd_days: int, reverse: bool = False) -> dict:
    sina = SINA_SYMBOLS[ts_code]
    print(f"\n  [{label}] {ts_code}...")
    df = fetch_sina_60min(sina)
    if df is None or len(df) < 100:
        print(f"    — 跳过 (数据不足)")
        return None

    n = len(df)
    close = df["close"].values
    fwd_ret = compute_forward_return(close, fwd_days)

    scores, regimes = compute_scores(df, min_bars=30, reverse_sign=reverse)
    ic, pval, hr, n_obs = compute_ic(scores, fwd_ret)

    # Regime 分布
    from collections import Counter
    cnt = Counter(regimes[30:])
    total = sum(cnt.values())

    tag = " (reverse)" if reverse else ""
    print(f"    IC={ic:.4f} (p={pval:.4f}) HR={hr:.1%} obs={n_obs}{tag}")
    print(f"    bars={n} | Regime: ", end="")
    for reg, c in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"{reg}={c/total*100:.0f}% ", end="")
    print()

    return {
        "ts_code": ts_code, "label": label, "fwd_days": fwd_days,
        "ic": ic, "pval": pval, "hr": hr, "n_obs": n_obs,
        "reverse": reverse, "n_bars": n,
    }


def print_experiment_header(title, fwd_days):
    print("\n" + "=" * 65)
    print(f"  {title}")
    print(f"  Forward: {fwd_days} 60-min bar(s) | 方法: determine_always_in() 滚动窗口")
    print("=" * 65)


def main():
    print("=" * 65)
    print("  60-min Always-In IC 测试")
    print("  验证: 60分钟线上趋势跟踪是否有效 (vs 日线负IC)")
    print("  股票: 601398.SH, 002522.SZ, 002825.SZ")
    print("=" * 65)

    # 测试 3 个 forward 窗口: 1天(4根) / 2天(8根) / 5天(20根)
    fwd_options = [4, 8, 20]

    all_results = []

    for fwd in fwd_options:
        label = fwd == 4 and "1-day(~4 bars)" or fwd == 8 and "2-day(~8 bars)" or "5-day(~20 bars)"
        print_experiment_header(f"60-min Forward {fwd} bars ({label})", fwd)
        t0 = time.time()
        for stock_label, code in STOCKS.items():
            r = run_test(code, stock_label, fwd, reverse=False)
            if r:
                all_results.append(r)
        print(f"  耗时: {time.time() - t0:.1f}s")

    # 也用 60-min 测 reverse sign
    print_experiment_header("60-min Reverse Sign (fwd=20 bars)", 20)
    t0 = time.time()
    for stock_label, code in STOCKS.items():
        r = run_test(code, stock_label, 20, reverse=True)
        if r:
            r["mode_key"] = "60min_reverse"
            all_results.append(r)
    print(f"  耗时: {time.time() - t0:.1f}s")

    # 汇总
    print("\n" + "=" * 65)
    print("  汇总对比")
    print("=" * 65)
    print(f"  {'方案':<30} {'IC':>8} {'p值':>8} {'命中率':>8} {'obs':>6}")
    print(f"  {'-'*65}")
    for r in all_results:
        mode = f"60min_{r.get('fwd_days')}bars{' rev' if r.get('reverse') else ''}"
        print(f"  {mode:<30} {r['ic']:>8.4f} {r['pval']:>8.4f} {r['hr']:>7.1%} {r['n_obs']:>6}")

    # 分组 Pooled
    print("\n  Pooled IC (简单平均):")
    for fwd in fwd_options:
        group = [r for r in all_results if r.get("fwd_days") == fwd and not r.get("reverse")]
        if group:
            avg_ic = np.mean([r["ic"] for r in group])
            avg_hr = np.mean([r["hr"] for r in group])
            bars_label = f"60-min fwd={fwd} bars"
            print(f"    {bars_label:<30}: IC={avg_ic:.4f}  HR={avg_hr:.1%}")

    rev_group = [r for r in all_results if r.get("reverse")]
    if rev_group:
        avg_ic = np.mean([r["ic"] for r in rev_group])
        avg_hr = np.mean([r["hr"] for r in rev_group])
        print(f"    {'60-min fwd=20 reverse':<30}: IC={avg_ic:.4f}  HR={avg_hr:.1%}")


if __name__ == "__main__":
    main()
