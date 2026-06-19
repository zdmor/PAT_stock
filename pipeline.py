"""PAT 主流水线 — P1: Always-In + Key Levels + Pinbar

模块编排流程:
  Step 1: data/loader.py     — 获取 K 线数据
  Step 2: state/market_state — Always-In 方向判定
  Step 3: patterns/key_levels — 水平关键位检测
  Step 4: patterns/pinbar     — Pinbar 形态检测 (携带 key_levels 上下文)
  Step 5: 信号过滤与组合      — Always-In 方向过滤
  Step 6: 组装输出            → pipeline_result dict

Usage:
  python pipeline.py                      # 盘后批量扫描
  python pipeline.py --watch 002050.SZ    # 单股监控
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# 直接运行时加入父目录到 sys.path
if __name__ == "__main__":
    _parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent not in sys.path:
        sys.path.insert(0, _parent)

from PAT_stock.data.loader import get_daily
from PAT_stock.state.market_state import (
    determine_always_in,
    get_trend_filter,
)
from PAT_stock.patterns.key_levels import (
    detect_key_levels,
    key_levels_summary,
)
from PAT_stock.patterns.pinbar import detect_pinbar
from PAT_stock.patterns.trap import detect_all_traps, detect_stop_run_trap
from PAT_stock.scoring.score import score_all_signals, select_top_signals
from PAT_stock.utils.indicators import swing_high, swing_low


def run_single_stock(
    ts_code: str,
    date: str,
    lookback_days: int = 120,
    min_bars: int = 30,
) -> dict:
    """单只股票的全部分析 (P1 管线 Steps 1-6)

    Args:
        ts_code:       股票代码, 如 "000001.SZ"
        date:          分析日期 YYYYMMDD
        lookback_days: 回看天数 (含 1.5 倍余量)
        min_bars:      最小有效 K 线数

    Returns:
        pipeline_result dict
    """
    # ── Step 1: 获取数据 ──
    start = (
        datetime.strptime(date, "%Y%m%d")
        - timedelta(days=int(lookback_days * 1.5))
    ).strftime("%Y%m%d")

    try:
        df = get_daily(ts_code, start, date)
    except Exception as e:
        return _skip_result(ts_code, f"data_load_failed: {e}")

    if df is None or len(df) < min_bars:
        return _skip_result(ts_code, "insufficient_data",
                            detail=f"got {len(df) if df is not None else 0} bars, need {min_bars}")

    if "trade_date" in df.columns:
        df = df.sort_values("trade_date").reset_index(drop=True)

    # ── Step 2: Always-In 判定 ──
    ai_result = _safe_call(
        "always_in",
        determine_always_in,
        df,
        default={"direction": "oscillating", "confidence": 0.0,
                 "structure": "mixed", "dimensions": {}},
    )
    trend_filter = get_trend_filter(ai_result, mode="strict")

    # ── Step 3: Key Levels 检测 ──
    levels, kl_meta = _safe_call(
        "key_levels",
        _detect_key_levels_wrapper,
        df,
        default=([], {"swing_count": 0, "swing_density": 0.0, "quality_warning": "detection_failed"}),
    )
    kl_summary = _safe_call(
        "key_levels_summary",
        key_levels_summary,
        levels, df["close"].iloc[-1],
        default="",
    )

    # ── Step 3.5: 陷阱检测 ──
    swing_highs = []
    swing_lows = []
    try:
        sh_mask = swing_high(df, left=5, right=5)
        sl_mask = swing_low(df, left=5, right=5)
        swing_highs = [float(df.iloc[i]["high"]) for i in range(len(df)) if sh_mask.iloc[i]]
        swing_lows = [float(df.iloc[i]["low"])  for i in range(len(df)) if sl_mask.iloc[i]]
    except Exception:
        pass

    swing_points = {"high": swing_highs, "low": swing_lows}
    trap_levels_dict = _safe_call(
        "trap_convert",
        _key_levels_to_trap_dict, levels,
        default={"resistance": [], "support": []},
    )
    traps = _safe_call(
        "trap",
        detect_all_traps, df,
        key_levels=trap_levels_dict,
        swing_points=swing_points,
        default=[],
    )

    # ── Step 4: Pinbar 检测 (携带 key_levels 上下文) ──
    df = _safe_call(
        "pinbar",
        detect_pinbar,
        df,
        key_levels=levels,
        default=df,
    )

    if "signal" not in df.columns:
        df["signal"] = 0
        df["signal_type"] = ""
        df["pinbar_strength"] = ""
        df["near_key_level"] = False
        df["key_level_distance"] = None

    # ── Step 5: 信号过滤与组合 ──
    signals = _build_signals(df, trend_filter, ai_result["confidence"], key_levels=levels)

    # ── Step 5b: 评分与排序 ──
    ai_for_scoring = dict(ai_result)
    ai_for_scoring["trend_filter"] = trend_filter
    signals = _safe_call(
        "scoring",
        score_all_signals, signals, ai_for_scoring,
        key_levels=levels, traps=traps,
        default=signals,
    )
    scored = _safe_call(
        "scoring_top",
        select_top_signals, signals,
        top_n=5, min_score=0.15,
        default=signals[:5],
    )

    # ── Step 6: 组装输出 ──
    total = len(scored)
    aligned = sum(1 for s in scored if s["always_in_aligned"])

    return {
        "ts_code": ts_code,
        "trade_date": date,
        "skip": False,
        "skip_reason": "",
        "n_bars": len(df),

        "always_in": {
            "direction": ai_result["direction"],
            "confidence": ai_result["confidence"],
            "structure": ai_result.get("structure", "mixed"),
            "trend_filter": trend_filter,
            "dimensions": ai_result.get("dimensions", {}),
        },

        "key_levels": {
            "levels": levels,
            "metadata": kl_meta,
            "summary": kl_summary,
        },

        "traps": traps,

        "signals": scored,
        "total_signals": total,
        "aligned_signals": aligned,
        "conflicting_signals": total - aligned,
    }


def _skip_result(ts_code: str, reason: str, detail: str = "") -> dict:
    return {
        "ts_code": ts_code,
        "trade_date": "",
        "skip": True,
        "skip_reason": f"{reason}{' (' + detail + ')' if detail else ''}",
        "n_bars": 0,
        "always_in": {"direction": "oscillating", "confidence": 0.0,
                       "structure": "mixed", "trend_filter": "neutral",
                       "dimensions": {}},
        "key_levels": {"levels": [], "metadata": {},
                        "summary": ""},
        "traps": [],
        "signals": [],
        "total_signals": 0,
        "aligned_signals": 0,
        "conflicting_signals": 0,
    }


def _safe_call(module_name: str, func, *args, default=None, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[WARN] {module_name} module failed: {e}")
        return default


def _detect_key_levels_wrapper(df: pd.DataFrame) -> tuple:
    """薄包装: detect_key_levels 已返回正确的 (levels, metadata)"""
    return detect_key_levels(df)


def _key_levels_to_trap_dict(levels: list) -> dict:
    """将 KeyLevel 对象列表转换为陷阱检测器所需的 {resistance, support} 格式"""
    resistance, support = [], []
    for kl in levels:
        if kl.formation_type in ("swing_high_cluster", "mixed"):
            resistance.append(float(kl.level_price))
        if kl.formation_type in ("swing_low_cluster", "mixed"):
            support.append(float(kl.level_price))
    return {"resistance": resistance, "support": support}


def _build_signals(df: pd.DataFrame, trend_filter: str, confidence: float, key_levels=None, max_signals: int = 10) -> list:
    if "signal" not in df.columns:
        return []

    signals = []
    signal_rows = df[df["signal"] != 0].tail(max_signals)

    for idx, row in signal_rows.iterrows():
        sig_dir = "bullish" if row["signal"] == 1 else "bearish"

        # 检查信号附近关键位的极性转换和假突破
        polarity_nearby = False
        fakeout_nearby = False
        if key_levels:
            signal_price = float(row["high"] if row["signal"] == 1 else row["low"])
            for kl in key_levels:
                if kl.price_min <= signal_price <= kl.price_max:
                    if kl.polarity_flips:
                        polarity_nearby = True
                    if kl.fakeout_history:
                        fakeout_nearby = True
                    break

        sig = {
            "date": str(row.get("trade_date", "")),
            "direction": sig_dir,
            "strength": row.get("pinbar_strength", ""),
            "entry_trigger": float(row["high"] if row["signal"] == 1 else row["low"]),
            "stop_loss": None,
            "near_key_level": bool(row.get("near_key_level", False)),
            "key_level_distance": row.get("key_level_distance", None),
            "always_in_aligned": _is_aligned(sig_dir, trend_filter, confidence),
            "polarity_nearby": polarity_nearby,
            "fakeout_nearby": fakeout_nearby,
            "score": 0.0,
        }
        signals.append(sig)

    return signals


def _is_aligned(direction: str, trend_filter: str, confidence: float) -> bool:
    if trend_filter == "neutral":
        return True
    if confidence <= 0.3:
        return True
    if confidence > 0.7:
        if trend_filter == "long_only" and direction == "bullish":
            return True
        if trend_filter == "short_only" and direction == "bearish":
            return True
        return False
    if trend_filter == "long_only" and direction == "bullish":
        return True
    if trend_filter == "short_only" and direction == "bearish":
        return True
    return False


def run_batch(ts_codes: list, date: str) -> list:
    results = []
    for code in ts_codes:
        result = run_single_stock(code, date)
        results.append(result)
        if not result["skip"]:
            n_sig = result["total_signals"]
            n_ali = result["aligned_signals"]
            print(f"  {code}: {n_sig} signals ({n_ali} aligned)")
    return results


def run_watchlist(date: str) -> list:
    watchlist = [
        "000001.SZ",
        "600519.SH",
        "300750.SZ",
    ]
    return run_batch(watchlist, date)


def _print_result(result: dict):
    if result["skip"]:
        print(f"  跳过: {result['skip_reason']}")
        return

    ai = result["always_in"]
    kl = result["key_levels"]
    traps = result.get("traps", [])
    print(f"  Always-In: {ai['direction']} "
          f"(conf={ai['confidence']:.2f}, filter={ai['trend_filter']})")
    print(f"  Key Levels: {len(kl['levels'])} levels detected")
    if kl["summary"]:
        print(kl["summary"])
    if traps:
        for trap in traps:
            t_dir = trap.get("trap_direction", "?")
            t_conf = trap.get("confidence", "?")
            print(f"  Trap: {trap['type']} {t_dir} (conf={t_conf})")
    print(f"  Signals: {result['total_signals']} total, "
          f"{result['aligned_signals']} aligned")
    for sig in result["signals"]:
        align = "[OK]" if sig["always_in_aligned"] else "[--]"
        kl_mark = " [KL]" if sig["near_key_level"] else ""
        score_str = f" score={sig['score']:.2f}" if sig.get("score", 0) > 0 else ""
        print(f"    {sig['date']} {sig['direction']:>7} "
              f"{sig['strength']:>6}{kl_mark} "
              f"trigger={sig['entry_trigger']:.2f}  {align}{score_str}")


def main():
    parser = argparse.ArgumentParser(description="PAT 流水线 — P1")
    parser.add_argument("--watch", type=str, help="单股监控 (ts_code)")
    parser.add_argument("--date", type=str,
                        default=datetime.now().strftime("%Y%m%d"),
                        help="扫描日期 (默认当日)")
    args = parser.parse_args()

    print(f"[PAT] P1 管线启动 — {args.date}")
    print(f"[PAT] 模块: Always-In + Key Levels + Pinbar")

    if args.watch:
        print(f"[PAT] 单股: {args.watch}")
        result = run_single_stock(args.watch, args.date)
        _print_result(result)
    else:
        print(f"[PAT] 盘后批量扫描")
        results = run_watchlist(args.date)
        active = [r for r in results if not r["skip"] and r["total_signals"] > 0]
        print(f"\n[PAT] 完成: {len(active)}/{len(results)} 只有信号")
        for r in active:
            print(f"  {r['ts_code']}: {r['total_signals']} signals "
                  f"({r['aligned_signals']} aligned)  "
                  f"AI={r['always_in']['direction']}")


if __name__ == "__main__":
    main()
