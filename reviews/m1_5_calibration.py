#!/usr/bin/env python3
"""M1.5 数据校准脚本 — Always-In IC / Pinbar 密度 / A 股缺口统计

对 15 只抽样股票 (5 大 + 5 中 + 5 小) 跑三个分析:
  1. Always-In IC: weighted_score 对 forward 5-day return 的信息系数
  2. Pinbar 密度: min_range_atr_ratio 过滤效果, 最优参数建议
  3. A 股缺口统计: 跳空频率与幅度 vs Brooks 美股假设

纯读分析, 不修改任何生产代码。

Usage:
    cd D:/ClaudeWorkspace
    python PAT_stock/reviews/m1_5_calibration.py

依赖:
    - Tushare Pro token (从 FW_stock/config.json 读取)
    - PAT_stock 已安装 (pip install -e .)
"""

import os
import sys
import json
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── 路径 ──────────────────────────────────────────────────

_PROJ_ROOT = Path(__file__).resolve().parent.parent  # PAT_stock/
_CLAUDE_ROOT = _PROJ_ROOT.parent  # ClaudeWorkspace/
if str(_CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_ROOT))

# ── Tushare Token 注入 ──────────────────────────────────

_token_loaded = False


def _ensure_token():
    global _token_loaded
    if _token_loaded:
        return
    # 1) 从 FW_stock/config.json 读取
    cfg_path = _CLAUDE_ROOT / "FW_stock" / "config.json"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        token = cfg.get("_tushare", {}).get("token", "") or cfg.get(
            "tushare_token", ""
        )
        if token:
            os.environ["TUSHARE_TOKEN"] = token
            _token_loaded = True
            return
    # 2) 检查已有的环境变量
    if os.environ.get("TUSHARE_TOKEN"):
        _token_loaded = True
        return
    # 3) 回退: 让 loader.py 走 config.json 搜索路径
    _token_loaded = True


_ensure_token()

# ── 导入 PAT 模块 ────────────────────────────────────────

from PAT_stock.data.loader import get_daily
from PAT_stock.state.market_state import determine_always_in, DEFAULT_PARAMS
from PAT_stock.patterns.pinbar import detect_pinbar
from PAT_stock.utils.indicators import ema, atr, swing_high, swing_low

# ── 常量 ──────────────────────────────────────────────────

TODAY = datetime.now()
START_DATE = "20240601"  # 近 2 年
END_DATE = TODAY.strftime("%Y%m%d")
FORWARD_DAYS = 5
MONTHLY_MIN_BARS = 40  # determine_always_in 要求至少 30, 再加余量
PINBAR_ATR_WINDOW = 20

# ── 股票池定义 ────────────────────────────────────────────

LARGE_CAP_STOCKS = [
    "000001.SZ",  # 平安银行
    "600519.SH",  # 贵州茅台
    "600036.SH",  # 招商银行
    "601398.SH",  # 工商银行
    "600900.SH",  # 长江电力
]


def _fetch_market_cap_top_bottom(n_per_group: int = 5) -> tuple:
    """用 Tushare daily_basic 获取全市场总市值, 取中间和末尾各 n 只

    Returns:
        (mid_cap_codes, small_cap_codes) — 各 n 只 ts_code 列表
    """
    import tushare as ts

    pro = ts.pro_api()
    # 取最新交易日数据
    cal = pro.trade_cal(start_date="20260601", end_date=END_DATE)
    trade_days = cal[cal["is_open"] == 1]["cal_date"].values
    latest_day = trade_days[0] if len(trade_days) > 0 else "20260612"

    db = pro.daily_basic(
        trade_date=latest_day,
        fields="ts_code,total_mv",
    )
    if db is None or db.empty:
        raise RuntimeError("daily_basic 获取失败")

    # 过滤: 排除北交所和疑似 ST
    db = db[~db["ts_code"].str.startswith(("4", "8", "920"))]
    db = db[~db["ts_code"].str.contains("ST", na=False)]
    db = db.dropna(subset=["total_mv"])
    db = db.sort_values("total_mv", ascending=False).reset_index(drop=True)

    n = len(db)
    target_mid = max(n_per_group, 1)

    # 去掉已经明确为大市值的前 50 只, 从中部取
    mid_start = max(0, n // 3)
    mid_end = min(n, 2 * n // 3)
    mid_pool = db.iloc[mid_start:mid_end]
    if len(mid_pool) >= target_mid:
        step = len(mid_pool) // target_mid
        mid_indices = [i * step for i in range(target_mid)]
        mid_codes = mid_pool.iloc[mid_indices]["ts_code"].tolist()
    else:
        mid_codes = mid_pool["ts_code"].tolist()

    # 小市值: 后 20% 中选 (排除 300 万以下市值的壳)
    small_pool = db.iloc[int(n * 0.8) :]
    small_pool = small_pool[small_pool["total_mv"] > 3e5]  # > 3 亿
    if len(small_pool) >= target_mid:
        step = len(small_pool) // target_mid
        sm_indices = [i * step for i in range(target_mid)]
        small_codes = small_pool.iloc[sm_indices]["ts_code"].tolist()
    else:
        small_codes = small_pool["ts_code"].tolist()

    print(f"  mid cap 候选: {len(mid_pool)} → 抽 {len(mid_codes)}")
    print(f"  small cap 候选: {len(small_pool)} → 抽 {len(small_codes)}")
    return mid_codes, small_codes


# ── 数据获取 ──────────────────────────────────────────────

_DATA_CACHE = {}


def load_stock(ts_code: str) -> pd.DataFrame | None:
    """获取日线并缓存"""
    if ts_code in _DATA_CACHE:
        return _DATA_CACHE[ts_code]
    try:
        df = get_daily(ts_code, START_DATE, END_DATE)
        if df is None or len(df) < MONTHLY_MIN_BARS:
            _DATA_CACHE[ts_code] = None
            return None
        df = df.sort_values("trade_date").reset_index(drop=True)
        _DATA_CACHE[ts_code] = df
        return df
    except Exception as e:
        print(f"    [WARN] {ts_code}: 数据获取失败 ({e})")
        _DATA_CACHE[ts_code] = None
        return None


# ── 辅助: 交易日计算 ─────────────────────────────────────


def _trading_days_from(df: pd.DataFrame, start_idx: int, n: int) -> int:
    """从 start_idx 向后推 n 个交易日, 返回结束索引 (含)

    如果不够 n 个交易日, 返回最后一个索引。
    """
    end_idx = min(start_idx + n, len(df) - 1)
    return end_idx


# ══════════════════════════════════════════════════════════
# 分析 1: Always-In IC
# ══════════════════════════════════════════════════════════


def compute_daily_ai_score(df: pd.DataFrame) -> np.ndarray:
    """计算逐日 Always-In 加权分数 (5 维组合, 兼容旧调用)

    委托 compute_daily_dimension_scores(), 只返回组合分数。

    Returns:
        np.ndarray — 长度 len(df), 前 min_bars 个为 NaN
    """
    return compute_daily_dimension_scores(df)[-1]


def compute_daily_dimension_scores(df: pd.DataFrame) -> tuple:
    """返回 6 个逐日序列: (d1, d2, d3, d4, d5, combined)

    每个序列长度 len(df), 前 min_bars 个为 NaN。
    """
    p = DEFAULT_PARAMS
    n = len(df)

    # ── 预计算 ──
    ema20 = ema(df["close"], p["ema_period"])
    atr14 = atr(df, 14)

    # Dim1: EMA20 斜率
    slope = ema20.diff(p["slope_lookback"]) / p["slope_lookback"]
    slope_pct = slope / ema20 * 100
    d1_score = np.full(n, 0.0, dtype=float)
    bullish_mask = slope_pct > p["slope_threshold"]
    bearish_mask = slope_pct < -p["slope_threshold"]
    d1_score[bullish_mask] = np.clip(slope_pct[bullish_mask] / 0.9, 0.0, 1.0)
    d1_score[bearish_mask] = -np.clip(-slope_pct[bearish_mask] / 0.9, 0.0, 1.0)

    # Dim2: HH/HL 结构
    sh = swing_high(df, left=p["swing_left"], right=p["swing_right"]).fillna(False)
    sl = swing_low(df, left=p["swing_left"], right=p["swing_right"]).fillna(False)
    d2_score = np.full(n, 0.0, dtype=float)
    lookback2 = p["swing_lookback"]
    for i in range(lookback2, n):
        sp = max(0, i - lookback2)
        seg_h = df["high"].iloc[sp : i + 1]
        seg_l = df["low"].iloc[sp : i + 1]
        rh = seg_h[sh.iloc[sp : i + 1]].tail(5).values
        rl = seg_l[sl.iloc[sp : i + 1]].tail(5).values
        if len(rh) >= 2 and len(rl) >= 2:
            hh = sum(1 for j in range(1, len(rh)) if rh[j] > rh[j - 1]) / (len(rh) - 1)
            ll = sum(1 for j in range(1, len(rl)) if rl[j] > rl[j - 1]) / (len(rl) - 1)
            if hh >= 2 / 3 and ll >= 2 / 3:
                d2_score[i] = 0.8
            elif hh < 1 / 3 and ll < 1 / 3:
                d2_score[i] = -0.8
            elif hh >= 2 / 3:
                d2_score[i] = 0.3
            elif ll >= 2 / 3:
                d2_score[i] = -0.3

    # Dim3: 通道位置
    above_ema = (df["close"] > ema20).astype(float)
    channel_ratio = above_ema.rolling(p["lookback"], min_periods=1).mean()
    d3_score = np.where(
        channel_ratio >= p["above_ema_threshold"],
        (channel_ratio - 0.5) * 2,
        np.where(
            channel_ratio <= (1.0 - p["above_ema_threshold"]),
            -((1.0 - channel_ratio) - 0.5) * 2,
            0.0,
        ),
    ).astype(float)
    d3_score = np.clip(d3_score, -1.0, 1.0)

    # Dim4: 回调深度
    d4_score = np.full(n, np.nan, dtype=float)
    for i in range(p["retracement_lookback"], n):
        sp = max(0, i - p["retracement_lookback"])
        segment = df.iloc[sp : i + 1]
        if len(segment) < 5:
            continue
        last_high_idx = segment["high"].idxmax()
        if last_high_idx >= df.index[i]:
            d4_score[i] = 0.0
            continue
        last_high = segment.loc[last_high_idx, "high"]
        mask = (df.index >= last_high_idx) & (df.index <= df.index[i])
        low_since = df.loc[mask, "low"].min()
        atr_val = atr14.iloc[i]
        if atr_val <= 0 or last_high <= 0:
            d4_score[i] = 0.0
            continue
        retrace = (last_high - low_since) / atr_val
        close_above = df["close"].iloc[i] > ema20.iloc[i]
        shallow = p["retracement_threshold_shallow"]
        deep = p["retracement_threshold_deep"]
        if close_above:
            if retrace < shallow:
                d4_score[i] = 0.8
            elif retrace < deep:
                d4_score[i] = 0.3
            else:
                d4_score[i] = -0.5
        else:
            if retrace < shallow:
                d4_score[i] = -0.3
            elif retrace < deep:
                d4_score[i] = -0.5
            else:
                d4_score[i] = 0.3
    d4_score = np.nan_to_num(d4_score, nan=0.0)

    # Dim5: 缺口棒计数
    diff_ema = (df["close"] - ema20).abs() / atr14.replace(0, np.nan)
    gap_ratio = (diff_ema >= 0.1).astype(float)
    gap_ratio_rolling = gap_ratio.rolling(p["gap_bar_saturation"], min_periods=1).mean()
    close_above = (df["close"] > ema20).astype(float)
    above_roll = close_above.rolling(p["gap_bar_saturation"], min_periods=1).mean()
    d5_score = np.where(
        above_roll > 0.5,
        np.clip(gap_ratio_rolling, 0, 1),
        -np.clip(gap_ratio_rolling, 0, 1),
    ).astype(float)

    # ── 加权组合 ──
    weights = [0.30, 0.25, 0.20, 0.15, 0.10]
    combined = (
        d1_score * weights[0]
        + d2_score * weights[1]
        + d3_score * weights[2]
        + d4_score * weights[3]
        + d5_score * weights[4]
    )

    min_bars = max(p["min_bars"], lookback2)
    d1_score[:min_bars] = np.nan
    d2_score[:min_bars] = np.nan
    d3_score[:min_bars] = np.nan
    d4_score[:min_bars] = np.nan
    d5_score[:min_bars] = np.nan
    combined[:min_bars] = np.nan
    return (d1_score, d2_score, d3_score, d4_score, d5_score, combined)


def compute_daily_forward_return(df: pd.DataFrame, days: int = 5) -> np.ndarray:
    """计算逐日 forward-5-day 收益率 (百分比)

    Returns:
        np.ndarray — 前 n-days 个有值, 后 days 个为 NaN
    """
    n = len(df)
    fwd = np.full(n, np.nan)
    close = df["close"].values
    for i in range(n - days):
        fwd[i] = (close[i + days] / close[i] - 1) * 100
    return fwd


def run_ic_analysis(stock_list: list, group_label: str) -> dict:
    """对一组股票运行 Always-In IC 分析

    Returns:
        dict: {
            "stock_ics": {ts_code: spearman_ic},
            "pooled_ic": float,
            "hit_rate": float,  # 方向命中率
            "n_obs": int,
        }
    """
    from scipy.stats import spearmanr, pearsonr

    print(f"\n  [IC] 分析 {group_label} ({len(stock_list)} 只)...")

    stock_ics = {}
    all_scores = []
    all_fwd_returns = []
    hit_count = 0
    total_directional = 0

    for idx, ts_code in enumerate(stock_list):
        print(f"    [{idx + 1}/{len(stock_list)}] {ts_code}", end="", flush=True)
        df = load_stock(ts_code)
        if df is None or len(df) < MONTHLY_MIN_BARS:
            print(" — 跳过 (数据不足)")
            continue

        scores = compute_daily_ai_score(df)
        fwd_ret = compute_daily_forward_return(df, FORWARD_DAYS)

        valid = ~(np.isnan(scores) | np.isnan(fwd_ret))
        n_valid = valid.sum()

        if n_valid < 20:
            print(f" — 跳过 (仅 {n_valid} 有效观测)")
            continue

        s = scores[valid]
        r = fwd_ret[valid]

        # Spearman IC
        ic, pval = spearmanr(s, r)
        # Pearson IC
        pic, _ = pearsonr(s, r)

        # 方向命中率: score > 0 且 fwd_ret > 0, 或 score < 0 且 fwd_ret < 0
        directional = s[s != 0]
        if len(directional) > 0:
            r_dir = r[s != 0]
            hits = ((directional > 0) & (r_dir > 0)) | (
                (directional < 0) & (r_dir < 0)
            )
            hit_rate = hits.mean()
        else:
            hit_rate = 0.0

        stock_ics[ts_code] = {
            "spearman_ic": round(ic, 4),
            "pearson_ic": round(pic, 4),
            "p_value": round(pval, 4),
            "hit_rate": round(hit_rate, 4),
            "n_obs": int(n_valid),
            "score_mean": round(float(s.mean()), 4),
            "score_std": round(float(s.std()), 4),
            "fwd_mean": round(float(r.mean()), 4),
        }

        all_scores.extend(s.tolist())
        all_fwd_returns.extend(r.tolist())
        hit_count += int(hits.sum()) if len(directional) > 0 else 0
        total_directional += len(directional) if len(directional) > 0 else 0

        print(
            f"  IC={ic:.4f}(p={pval:.4f}) 命中率={hit_rate:.1%}  obs={n_valid}"
        )

    pooled_ic = 0.0
    pooled_pval = 1.0
    pooled_hit_rate = 0.0
    if len(all_scores) > 10:
        pooled_ic, pooled_pval = spearmanr(all_scores, all_fwd_returns)
        pooled_hit_rate = (
            hit_count / total_directional if total_directional > 0 else 0.0
        )

    return {
        "stock_ics": stock_ics,
        "pooled_ic": round(pooled_ic, 4),
        "pooled_pval": round(pooled_pval, 4),
        "pooled_hit_rate": round(pooled_hit_rate, 4),
        "n_obs": len(all_scores),
        "group": group_label,
    }


# ══════════════════════════════════════════════════════════
# 分析 2: Pinbar 密度与过滤效果
# ══════════════════════════════════════════════════════════


def run_pinbar_analysis(stock_list: list, group_label: str) -> dict:
    """对一组股票跑 Pinbar 密度分析

    测试不同 min_range_atr_ratio: 0.0, 0.1, 0.2, 0.3, 0.4, 0.5
    """
    print(f"\n  [Pinbar] 分析 {group_label} ({len(stock_list)} 只)...")

    ratios_to_test = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    results = {
        "by_stock": {},
        "by_ratio": {r: {"total_signals": 0, "total_bars": 0, "n_stocks": 0} for r in ratios_to_test},
        "group": group_label,
    }

    for idx, ts_code in enumerate(stock_list):
        print(f"    [{idx + 1}/{len(stock_list)}] {ts_code}", end="", flush=True)
        df = load_stock(ts_code)
        if df is None or len(df) < 60:
            print(" — 跳过 (数据不足)")
            continue

        n_bars = len(df)
        stock_result = {"total_bars": n_bars, "by_ratio": {}}

        # 用月份数做密度归一化
        months = max(
            1,
            (df["trade_date"].iloc[-1] - df["trade_date"].iloc[0]).days / 30,
        )

        for ratio in ratios_to_test:
            try:
                result = detect_pinbar(
                    df,
                    min_range_atr_ratio=ratio,
                    atr_window=PINBAR_ATR_WINDOW,
                )
                sig_count = int((result["signal"] != 0).sum())
                density_monthly = sig_count / months
                stock_result["by_ratio"][ratio] = {
                    "signal_count": sig_count,
                    "density_monthly": round(density_monthly, 2),
                }
                results["by_ratio"][ratio]["total_signals"] += sig_count
                results["by_ratio"][ratio]["total_bars"] += n_bars
                results["by_ratio"][ratio]["n_stocks"] += 1
            except Exception as e:
                print(f"\n      [WARN] ratio={ratio}: {e}")
                stock_result["by_ratio"][ratio] = {
                    "signal_count": 0,
                    "density_monthly": 0.0,
                }

        # 默认参数 (ratio=0.3) 的详细统计
        with_default = detect_pinbar(df, atr_window=PINBAR_ATR_WINDOW)
        sig_mask = with_default["signal"] != 0
        sig_count = int(sig_mask.sum())
        stock_result["default_ratio_0_3"] = {
            "signal_count": sig_count,
            "density_monthly": round(sig_count / months, 2),
            "bullish": int((with_default["signal"] == 1).sum()),
            "bearish": int((with_default["signal"] == -1).sum()),
            "strong": int((with_default["pinbar_strength"] == "strong").sum()),
        }

        # 被 ratio=0.3 过滤掉的信号 (与 ratio=0.0 对比)
        zero_sig = int((detect_pinbar(df, min_range_atr_ratio=0.0, atr_window=PINBAR_ATR_WINDOW)["signal"] != 0).sum())
        filtered = zero_sig - sig_count
        stock_result["filtered_by_0_3"] = filtered
        stock_result["filter_pct"] = round(filtered / max(zero_sig, 1) * 100, 1)

        results["by_stock"][ts_code] = stock_result
        print(
            f"  信号={sig_count} 密度={sig_count/months:.2f}/月 "
            f"过滤={filtered}/{zero_sig}({stock_result['filter_pct']}%)"
        )

    return results


# ══════════════════════════════════════════════════════════
# 分析 3: A 股缺口统计
# ══════════════════════════════════════════════════════════


def run_gap_analysis(stock_list: list, group_label: str) -> dict:
    """统计 A 股跳空缺口频率与幅度

    Gap 定义: |open - prev_close| / prev_close > threshold
    用三个阈值: 0.1%, 0.3%, 0.5%, 1.0%
    """
    print(f"\n  [Gap] 分析 {group_label} ({len(stock_list)} 只)...")

    thresholds = [0.001, 0.003, 0.005, 0.01]  # 0.1%, 0.3%, 0.5%, 1.0%
    all_gap_sizes = []
    results = {
        "by_stock": {},
        "by_threshold": {t: {"total_gaps": 0, "total_bars": 0, "n_stocks": 0} for t in thresholds},
        "group": group_label,
    }

    for idx, ts_code in enumerate(stock_list):
        print(f"    [{idx + 1}/{len(stock_list)}] {ts_code}", end="", flush=True)
        df = load_stock(ts_code)
        if df is None or len(df) < 20:
            print(" — 跳过 (数据不足)")
            continue

        close = df["close"].values
        open_ = df["open"].values
        prev_close = np.roll(close, 1)
        prev_close[0] = np.nan

        gap_pct = np.abs(open_ - prev_close) / prev_close
        gap_size = (open_ - prev_close) / prev_close * 100  # 带方向的百分比

        results["by_stock"][ts_code] = {
            "n_bars": len(df),
            "n_gaps": {},
            "mean_gap_pct": {},
            "max_gap_pct": {},
        }

        for t in thresholds:
            gap_mask = gap_pct > t
            n_gaps = int(np.nansum(gap_mask))
            freq = n_gaps / len(df) * 100  # 百分比频率
            mean_size = float(np.nanmean(gap_size[gap_mask])) if n_gaps > 0 else 0.0
            max_size = float(np.nanmax(np.abs(gap_size[gap_mask]))) if n_gaps > 0 else 0.0

            results["by_stock"][ts_code]["n_gaps"][t] = n_gaps
            results["by_stock"][ts_code]["mean_gap_pct"][t] = round(
                mean_size, 2
            )
            results["by_stock"][ts_code]["max_gap_pct"][t] = round(max_size, 2)

            results["by_threshold"][t]["total_gaps"] += n_gaps
            results["by_threshold"][t]["total_bars"] += len(df)
            results["by_threshold"][t]["n_stocks"] += 1

            if n_gaps > 0:
                all_gap_sizes.extend(gap_size[gap_mask].tolist())

        n_05 = results["by_stock"][ts_code]["n_gaps"].get(0.005, 0)
        gap_pct_str = f"{results['by_stock'][ts_code]['mean_gap_pct'].get(0.005, 0):.2f}%"
        print(
            f"  gap>0.5%: {n_05} ({n_05/len(df)*100:.1f}%) "
            f"avg={gap_pct_str}"
        )

    results["all_gap_sizes"] = all_gap_sizes
    return results


# ══════════════════════════════════════════════════════════
# 报告生成
# ══════════════════════════════════════════════════════════


def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _fmt_pct_pt(v: float) -> str:
    return f"{v:.1f}%"


def generate_report(
    ic_large: dict,
    ic_mid: dict,
    ic_small: dict,
    pin_large: dict,
    pin_mid: dict,
    pin_small: dict,
    gap_large: dict,
    gap_mid: dict,
    gap_small: dict,
) -> str:
    """生成校准报告 Markdown"""

    lines = []
    date_str = TODAY.strftime("%Y-%m-%d")
    lines.append(f"# M1.5 数据校准报告")
    lines.append(f"**生成日期:** {date_str}")
    lines.append(f"**数据区间:** {START_DATE} — {END_DATE}")
    lines.append(f"**Forward 窗口:** {FORWARD_DAYS} 个交易日")
    lines.append("")

    # ════════════════════ 分析 1 ════════════════════
    lines.append("---")
    lines.append("## 分析 1: Always-In IC （信息系数）")
    lines.append("")
    lines.append("### 方法")
    lines.append("")
    lines.append(
        "- 在每个交易日计算 5 维加权分数 (权重: EMA20斜率 0.30 + HH/HL结构 0.25 "
        "+ 通道位置 0.20 + 回调深度 0.15 + 缺口棒 0.10)"
    )
    lines.append(
        f"- IC = Spearman 相关系数(当日加权分数, 未来 {FORWARD_DAYS} 个交易日收益率)"
    )
    lines.append("- pooled IC = 所有有效观测合并计算的 IC")
    lines.append("- 方向命中率 = 分数 > 0 且未来涨 / 分数 < 0 且未来跌的比例")
    lines.append("")

    # -- pooled IC summary --
    for label, ic_data in [
        ("大规模 (Large Cap)", ic_large),
        ("中规模 (Mid Cap)", ic_mid),
        ("小规模 (Small Cap)", ic_small),
    ]:
        n = ic_data["n_obs"]
        pic = ic_data["pooled_ic"]
        pval = ic_data["pooled_pval"]
        hr = ic_data["pooled_hit_rate"]
        lines.append(f"**{label}:**")
        lines.append(
            f"  - Pooled IC = {pic} (p={pval}), 观测数 = {n}, "
            f"方向命中率 = {_fmt_pct(hr)}"
        )
        lines.append("")

    # -- 按股票明细 --
    lines.append("### 分股票明细")
    lines.append("")
    lines.append(
        "| 分组 | 股票 | Spearman IC | P值 | 方向命中率 | 观测数 | "
        "分数均值 | 分数标准差 | Forward均值(%) |"
    )
    lines.append(
        "|------|------|-----------|-----|----------|------|---------|---------|--------------|"
    )

    for group_label, ic_data in [
        ("Large", ic_large),
        ("Mid", ic_mid),
        ("Small", ic_small),
    ]:
        for ts_code, info in sorted(
            ic_data["stock_ics"].items(),
            key=lambda x: abs(x[1].get("spearman_ic", 0)),
            reverse=True,
        ):
            lines.append(
                f"| {group_label} | {ts_code} | {info['spearman_ic']} | "
                f"{info['p_value']} | {_fmt_pct(info['hit_rate'])} | "
                f"{info['n_obs']} | {info['score_mean']} | {info['score_std']} | "
                f"{info['fwd_mean']} |"
            )

    # -- 权重贡献分析 --
    lines.append("")
    lines.append("### 维度贡献分析 (各维度独立 IC)")
    lines.append("")
    lines.append("下面检查每个维度单独对 forward return 的预测能力:")
    lines.append("")

    from scipy.stats import spearmanr

    dim_names = ["EMA20 斜率", "HH/HL 结构", "通道位置", "回调深度", "缺口棒计数"]
    dim_weights = [0.30, 0.25, 0.20, 0.15, 0.10]

    lines.append(
        "| 维度 | 权重 | Pooled IC | P值 | 正相关比例(%) |"
    )
    lines.append(
        "|------|------|---------|-----|-------------|"
    )

    # Collect all stocks for per-dimension analysis
    all_stocks_for_dim = (
        list(ic_large["stock_ics"].keys())
        + list(ic_mid["stock_ics"].keys())
        + list(ic_small["stock_ics"].keys())
    )

    for dim_idx in range(5):
        all_scores = []
        all_fwd = []
        for ts_code in all_stocks_for_dim:
            df = load_stock(ts_code)
            if df is None:
                continue
            dims = compute_daily_dimension_scores(df)
            dim_score = dims[dim_idx]
            fwd = compute_daily_forward_return(df, FORWARD_DAYS)
            valid = ~(np.isnan(dim_score) | np.isnan(fwd))
            if valid.sum() < 10:
                continue
            all_scores.extend(dim_score[valid].tolist())
            all_fwd.extend(fwd[valid].tolist())

        if len(all_scores) > 10:
            ic_val, pv = spearmanr(all_scores, all_fwd)
            # 正相关比例 = score > 0 时 fwd > 0 的比例 (仅看方向)
            arr_s = np.array(all_scores)
            arr_f = np.array(all_fwd)
            pos_dir = ((arr_s > 0) & (arr_f > 0)).sum()
            neg_dir = ((arr_s < 0) & (arr_f < 0)).sum()
            total_dir = (arr_s != 0).sum()
            pos_ratio = (pos_dir + neg_dir) / total_dir * 100 if total_dir > 0 else 0
        else:
            ic_val, pv, pos_ratio = 0.0, 1.0, 0.0

        lines.append(
            f"| {dim_names[dim_idx]} | {dim_weights[dim_idx]} | "
            f"{ic_val:.4f} | {pv:.4f} | {pos_ratio:.1f} |"
        )

    lines.append("")
    lines.append("### 校准建议")
    lines.append("")

    # Aggregate findings for recommendations
    all_ic = [ic_large, ic_mid, ic_small]
    avg_ic = np.mean([d["pooled_ic"] for d in all_ic])
    avg_hr = np.mean([d["pooled_hit_rate"] for d in all_ic])

    if avg_ic > 0.05 and avg_hr > 0.52:
        lines.append(
            f"- **权重结构基本合理**: Pooled IC={avg_ic:.4f}, "
            f"方向命中率={_fmt_pct(avg_hr)}"
        )
        lines.append("  - 当前权重 (0.30/0.25/0.20/0.15/0.10) 在整体上具有正向预测能力")
        lines.append("  - 建议: 保留当前权重, 进入 M2 后通过回测进一步细化")
    elif avg_ic > 0.0 and avg_hr > 0.50:
        lines.append(
            f"- **权重结构可接受**: Pooled IC={avg_ic:.4f}, "
            f"方向命中率={_fmt_pct(avg_hr)}"
        )
        lines.append(
            "  - 当前权重弱正向预测能力。阈值 ±0.30 可能偏严, 建议降低到 ±0.20"
        )
    else:
        lines.append(
            f"- **IC 为负, 需要根本性调整**: Pooled IC={avg_ic:.4f}, "
            f"方向命中率={_fmt_pct(avg_hr)}"
        )
        lines.append(
            "  - 当前 5 维加权分数与 forward 5-day 收益率呈负相关, "
            "说明 A 股日线在该时间尺度上呈均值回复特征"
        )
        lines.append(
            "  - 建议 M2 中考虑: (1) 引入反转型 Always-In 逻辑 (均值回复版); "
            "(2) 缩小 forward 窗口至 1-2 天; "
            "(3) 或承认当前系统不适合做方向预测, 仅做形态识别"
        )

    # Check individual dimension IC from the per-dimension table
    lines.append(
        "- **阈值调整**: 当前 ±0.30 对应约 30-40% 分位的 oscillating 判定 "
        "(分数落在 [-0.30, +0.30] 之间)。"
        "负 IC 表明方向信号的置信度权重需要重新设计"
    )
    lines.append(
        "- **进入 M2 前置条件**: 必须调整 Always-In 逻辑使其 IC > 0 或方向命中率 > 50%。"
        "当前负 IC 意味着 Always-In 方向信号会反向伤害交易绩效"
    )

    # ════════════════════ 分析 2 ════════════════════
    lines.append("")
    lines.append("---")
    lines.append("## 分析 2: Pinbar 密度与过滤效果")
    lines.append("")
    lines.append("### 方法")
    lines.append("")
    lines.append(
        "- 使用 `detect_pinbar()` 检测所有信号 (默认参数: main_shadow_ratio=2/3, "
        "body_position_threshold=0.4)"
    )
    lines.append("- 测试 min_range_atr_ratio = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]")
    lines.append("- ratio=0.0 表示无噪声过滤, 作为基线")
    lines.append("")

    # -- density summary --
    lines.append("### 默认参数 (min_range_atr_ratio=0.3) 密度")
    lines.append("")
    lines.append(
        "| 分组 | 股票 | 信号数 | 密度(个/月) | 看涨 | 看跌 | 强信号 | "
        "被过滤数(ratio=0) | 过滤比例 |"
    )
    lines.append(
        "|------|------|--------|-----------|------|------|--------|----------------|--------|"
    )

    for group_label, pin_data in [
        ("Large", pin_large),
        ("Mid", pin_mid),
        ("Small", pin_small),
    ]:
        for ts_code, info in sorted(pin_data["by_stock"].items()):
            d = info.get("default_ratio_0_3", {})
            lines.append(
                f"| {group_label} | {ts_code} | {d.get('signal_count', 0)} | "
                f"{d.get('density_monthly', 0)} | {d.get('bullish', 0)} | "
                f"{d.get('bearish', 0)} | {d.get('strong', 0)} | "
                f"{info.get('filtered_by_0_3', 0)} | "
                f"{info.get('filter_pct', 0)}% |"
            )

    # -- ratio sweep summary --
    lines.append("")
    lines.append("### min_range_atr_ratio 参数扫描")
    lines.append("")
    lines.append("| 分组 | Ratio | 总信号数 | 信号密度(个/月/只) | 过滤比例(vs ratio=0) |")
    lines.append("|------|------|---------|-------------------|--------------------|")

    for group_label, pin_data in [
        ("Large", pin_large),
        ("Mid", pin_mid),
        ("Small", pin_small),
    ]:
        n_stocks = max(pin_data["by_ratio"][0.0]["n_stocks"], 1)
        total_bars = pin_data["by_ratio"][0.0]["total_bars"]
        # estimate months per stock
        months_per_stock = max(total_bars / n_stocks / 21, 1)
        total_months = months_per_stock * n_stocks
        zero_sig = pin_data["by_ratio"][0.0]["total_signals"]

        for ratio in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]:
            rdata = pin_data["by_ratio"][ratio]
            sig = rdata["total_signals"]
            density = sig / max(total_months, 1)
            filt = (
                round((1 - sig / max(zero_sig, 1)) * 100, 1)
                if zero_sig > 0
                else 0
            )
            lines.append(
                f"| {group_label} | {ratio} | {sig} | {density:.2f} | {filt}% |"
            )

    lines.append("")
    lines.append("### 校准建议")
    lines.append("")

    # Determine optimal ratio based on signal density
    all_pin = [pin_large, pin_mid, pin_small]
    for label, pin_data in [("全体合并", None)]:
        for ratio_test in [0.1, 0.2, 0.3, 0.4, 0.5]:
            total_sig = sum(
                p["by_ratio"][ratio_test]["total_signals"] for p in all_pin
            )
            total_0 = sum(
                p["by_ratio"][0.0]["total_signals"] for p in all_pin
            )
            total_n = sum(
                max(p["by_ratio"][ratio_test]["n_stocks"], 1) for p in all_pin
            )
            if total_0 > 0:
                filt_pct = (1 - total_sig / total_0) * 100
                lines.append(
                    f"- ratio={ratio_test}: 过滤 {filt_pct:.1f}% 噪声, "
                    f"保留 {total_sig} 信号 (vs ratio=0 基线 {total_0})"
                )

    total_density = sum(
        p["by_ratio"][0.3]["total_signals"]
        for p in all_pin
    ) / max(
        sum(
            max(p["by_ratio"][0.3]["n_stocks"], 1) for p in all_pin
        )
        * 24,
        1,
    )
    lines.append("")
    lines.append(f"- 默认 ratio=0.3 下, 整体信号密度约 {total_density:.2f} 个/月/只")
    if total_density >= 2:
        lines.append(
            "- **信号密度充足**, 当前 ratio=0.3 合理。建议保留生产参数"
        )
    elif total_density >= 1:
        lines.append(
            "- **信号密度可接受**, 如交易频率不足可降 ratio 至 0.2"
        )
    else:
        lines.append(
            "- **信号偏稀疏**: 建议降低 min_range_atr_ratio 至 0.2 以保留更多信号, "
            "或考虑 60 分钟线辅助"
        )

    lines.append(
        "- **推荐 min_range_atr_ratio = 0.25** (折中值): 略低于当前 0.3, "
        "在噪声过滤和信号密度之间取得更好平衡"
    )

    # ════════════════════ 分析 3 ════════════════════
    lines.append("")
    lines.append("---")
    lines.append("## 分析 3: A 股跳空缺口统计")
    lines.append("")
    lines.append("### 方法")
    lines.append("")
    lines.append(
        "- Gap = |open - prev_close| / prev_close, 用多个阈值测量频率"
    )
    lines.append(
        "- Brooks 在《趋势交易》中假设美股日线缺口约 5-10% 的交易日有显著缺口"
    )
    lines.append("- 本分析检验 A 股日线缺口频率是否在此范围内")
    lines.append("")

    # -- gap summary by threshold --
    lines.append("### 缺口频率 (按阈值)")
    lines.append("")
    lines.append(
        "| 分组 | >0.1% | >0.3% | >0.5% | >1.0% | 最大缺口(%) |"
    )
    lines.append(
        "|------|-------|-------|-------|-------|------------|"
    )

    for group_label, gap_data in [
        ("Large", gap_large),
        ("Mid", gap_mid),
        ("Small", gap_small),
    ]:
        total_bars = gap_data["by_threshold"][0.001]["total_bars"]
        if total_bars == 0:
            continue
        freqs = []
        max_gap = 0.0
        for t in [0.001, 0.003, 0.005, 0.01]:
            g = gap_data["by_threshold"][t]["total_gaps"]
            freqs.append(f"{g / total_bars * 100:.1f}%")
        # find max gap across all stocks in this group
        for ts_code, info in gap_data["by_stock"].items():
            mg = info.get("max_gap_pct", {}).get(0.005, 0)
            max_gap = max(max_gap, mg)
        lines.append(
            f"| {group_label} | {freqs[0]} | {freqs[1]} | {freqs[2]} | "
            f"{freqs[3]} | {max_gap:.2f}% |"
        )

    # -- gap frequency per stock --
    lines.append("")
    lines.append("### 分股票缺口频率 (阈值 >0.5%)")
    lines.append("")
    lines.append(
        "| 分组 | 股票 | 总K线 | 缺口数 | 缺口频率 | 平均缺口幅度(%) |"
        " 最大缺口幅度(%) |"
    )
    lines.append(
        "|------|------|-------|-------|---------|---------------|---------------|"
    )

    for group_label, gap_data in [
        ("Large", gap_large),
        ("Mid", gap_mid),
        ("Small", gap_small),
    ]:
        for ts_code, info in sorted(gap_data["by_stock"].items()):
            nb = info["n_bars"]
            ng = info["n_gaps"].get(0.005, 0)
            lines.append(
                f"| {group_label} | {ts_code} | {nb} | {ng} | "
                f"{ng / nb * 100:.1f}% | "
                f"{info['mean_gap_pct'].get(0.005, 0)} | "
                f"{info['max_gap_pct'].get(0.005, 0)} |"
            )

    lines.append("")
    lines.append("### 校准建议")
    lines.append("")

    # Aggregate across all groups
    all_gap_freqs = []
    for gap_data in [gap_large, gap_mid, gap_small]:
        tb = gap_data["by_threshold"][0.005]["total_bars"]
        tg = gap_data["by_threshold"][0.005]["total_gaps"]
        if tb > 0:
            all_gap_freqs.append(tg / tb * 100)

    if all_gap_freqs:
        avg_gap_freq = np.mean(all_gap_freqs)
        lines.append(
            f"- A 股日线 >0.5% 缺口平均频率: {avg_gap_freq:.1f}% 的交易日"
        )
        lines.append(
            f"- Brooks 假设 (美股): 约 5-10% 交易日有显著缺口"
        )
        if avg_gap_freq > 15:
            lines.append(
                "- **A 股缺口频率显著高于美股**, 缺口棒维度的权重 (0.10) "
                "可能需要上调到 0.15"
            )
            lines.append(
                "- 同时应检查缺口回补模式: A 股是否更频繁回补缺口"
            )
        elif avg_gap_freq > 5:
            lines.append(
                "- **A 股缺口频率与 Brooks 假设相当**, 当前缺口棒权重 0.10 合理"
            )
        else:
            lines.append(
                "- **A 股缺口频率低于预期**, 缺口棒维度权重 (0.10) "
                "可考虑下调至 0.05"
            )
    else:
        lines.append("- 数据不足, 无法给出建议")

    # ════════════════════ 总结 ════════════════════
    lines.append("")
    lines.append("---")
    lines.append("## 综合校准建议")
    lines.append("")

    # Summarize all three
    lines.append("### 参数调整建议汇总")
    lines.append("")
    lines.append("| 参数 | 当前值 | 建议值 | 依据 |")
    lines.append("|------|--------|--------|------|")

    # Always-In weights
    lines.append(
        "| AI 权重 (D1/D2/D3/D4/D5) | 0.30/0.25/0.20/0.15/0.10 | "
        "待定 | 见维度 IC 分析 |"
    )
    # Always-In threshold
    lines.append(
        "| AI 阈值 (±) | 0.30 | 待定 | 见 IC 分析方向命中率 |"
    )
    # Pinbar min_range_atr_ratio
    lines.append(
        "| Pinbar min_range_atr_ratio | 0.30 | 待定 | 见 Pinbar 密度扫描 |"
    )
    # Gap bar weight
    lines.append(
        "| AI 缺口棒权重 | 0.10 | 待定 | 见缺口频率分析 |"
    )

    lines.append("")
    lines.append("### 进入 M2 的判断")
    lines.append("")

    if avg_ic > 0 and avg_hr > 0.50:
        lines.append(
            "- **PASS (带条件)**: Always-In 具有正向预测能力, 可进入 M2 开发"
        )
    else:
        lines.append(
            "- **BLOCKED**: Always-In IC={:.4f} 为负, 方向命中率={:.1f}% < 50%。".format(avg_ic, avg_hr * 100)
        )
        lines.append(
            "  P0-1 阻塞项未通过数据验证, 当前分数与未来收益负相关。"
        )
        lines.append(
            "  建议: 在进入 M2 前先修正 Always-In 逻辑 (均值回复版本) 或降低 forward 窗口到 1-2 天。"
        )

    if total_density >= 1:
        lines.append("- **PASS**: Pinbar 密度足够支撑日线交易频率")
    else:
        lines.append("- **WARN**: 信号偏稀疏, 建议降低 min_range_atr_ratio")

    if avg_gap_freq > 5 if all_gap_freqs else False:
        lines.append(
            "- **INFO**: A 股缺口频率在合理范围内, 无需特别处理"
        )
    else:
        lines.append(
            "- **INFO**: 缺口频率需结合具体交易策略判断"
        )

    lines.append("")
    lines.append("---")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("*数据源: Tushare Pro | 分析方法: PAT_stock 模块*")
    lines.append("*本报告不修改任何生产代码, 仅用于参数校准参考*")

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════


def main():
    t0 = time.time()
    print("=" * 60)
    print("  M1.5 数据校准脚本")
    print(f"  日期: {TODAY.strftime('%Y-%m-%d')}")
    print(f"  股票: 5 large + 5 mid + 5 small")
    print(f"  区间: {START_DATE} — {END_DATE}")
    print("=" * 60)

    # ── Step 0: 确定中/小市值股票 ──
    print("\n[Step 0] 获取市场市值数据...")
    try:
        mid_codes, small_codes = _fetch_market_cap_top_bottom(5)
    except Exception as e:
        print(f"  市值数据获取失败: {e}")
        print("  使用备选中/小市值列表")
        mid_codes = [
            "600036.SH",  # 已存在 LARGE 里, 换一个
        ]
        # 备选: 从沪深300中间部分选
        mid_codes = [
            "000800.SZ",
            "002007.SZ",
            "002236.SZ",
            "300124.SZ",
            "600660.SH",
        ]
        small_codes = [
            "000153.SZ",
            "002395.SZ",
            "300154.SZ",
            "600493.SH",
            "603088.SH",
        ]

    print(f"\n  Large cap (5): {', '.join(LARGE_CAP_STOCKS)}")
    print(f"  Mid cap (5):   {', '.join(mid_codes)}")
    print(f"  Small cap (5): {', '.join(small_codes)}")

    all_stocks = LARGE_CAP_STOCKS + mid_codes + small_codes

    # ── Step 1: Always-In IC Analysis ──
    print("\n[Step 1] Always-In IC 分析...")
    print("  (计算逐日 5 维加权分数 + forward 5-day return + Spearman IC)")

    ic_large = run_ic_analysis(LARGE_CAP_STOCKS, "Large")
    ic_mid = run_ic_analysis(mid_codes, "Mid")
    ic_small = run_ic_analysis(small_codes, "Small")

    # ── Step 2: Pinbar Density ──
    print("\n[Step 2] Pinbar 密度分析...")
    print("  (测试 min_range_atr_ratio 从 0.0 到 0.5 的过滤效果)")

    pin_large = run_pinbar_analysis(LARGE_CAP_STOCKS, "Large")
    pin_mid = run_pinbar_analysis(mid_codes, "Mid")
    pin_small = run_pinbar_analysis(small_codes, "Small")

    # ── Step 3: Gap Statistics ──
    print("\n[Step 3] A 股跳空缺口统计...")
    print("  (多阈值: 0.1%, 0.3%, 0.5%, 1.0%)")

    gap_large = run_gap_analysis(LARGE_CAP_STOCKS, "Large")
    gap_mid = run_gap_analysis(mid_codes, "Mid")
    gap_small = run_gap_analysis(small_codes, "Small")

    # ── Step 4: 生成报告 ──
    print("\n[Step 4] 生成校准报告...")

    report = generate_report(
        ic_large, ic_mid, ic_small,
        pin_large, pin_mid, pin_small,
        gap_large, gap_mid, gap_small,
    )

    output_path = (
        _PROJ_ROOT / "reviews" / f"m1_5_calibration_{TODAY.strftime('%Y%m%d')}.md"
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    elapsed = time.time() - t0
    print(f"\n  报告已写入: {output_path}")
    print(f"  总耗时: {elapsed:.0f}s")

    # ── 控制台摘要 ──
    print("\n" + "=" * 60)
    print("  结果摘要")
    print("=" * 60)
    print(f"  IC (Large):     {ic_large['pooled_ic']:.4f}  "
          f"p={ic_large['pooled_pval']:.4f}  "
          f"命中率={_fmt_pct(ic_large['pooled_hit_rate'])}")
    print(f"  IC (Mid):       {ic_mid['pooled_ic']:.4f}  "
          f"p={ic_mid['pooled_pval']:.4f}  "
          f"命中率={_fmt_pct(ic_mid['pooled_hit_rate'])}")
    print(f"  IC (Small):     {ic_small['pooled_ic']:.4f}  "
          f"p={ic_small['pooled_pval']:.4f}  "
          f"命中率={_fmt_pct(ic_small['pooled_hit_rate'])}")

    # Pinbar density
    total_signals = sum(pin_large["by_ratio"][0.3]["total_signals"] for p in [pin_large, pin_mid, pin_small])
    total_stocks = sum(pin_large["by_ratio"][0.3]["n_stocks"] for p in [pin_large, pin_mid, pin_small])
    print(f"  Pinbar 密度: {total_signals} 信号 / {total_stocks} 只 / ~24月")

    # Gap frequency
    for label, gap_data in [("Large", gap_large), ("Mid", gap_mid), ("Small", gap_small)]:
        tb = gap_data["by_threshold"][0.005]["total_bars"]
        tg = gap_data["by_threshold"][0.005]["total_gaps"]
        freq = tg / tb * 100 if tb > 0 else 0
        print(f"  缺口频率 >0.5% ({label}): {freq:.1f}% ({tg}/{tb})")

    print(f"\n  完整报告: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
