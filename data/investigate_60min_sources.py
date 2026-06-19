"""60 分钟 K 线数据源调查 — PAT Phase 1.1

测试 4 个候选数据源在 10 只样本股票上的 60 分钟数据获取能力。
输出 JSON 报告, 包含各数据源的成功率、耗时、数据量、字段完整性对比。

候选数据源:
  1. AKShare stock_zh_a_hist_min_em — 东方财富分钟接口
  2. AKShare stock_zh_a_minute — 新浪分钟接口
  3. 新浪 K-line API — 直接 HTTP 调用
  4. Tushare Pro — stk_mins (付费, 2000 积分版)

Usage:
    cd D:/ClaudeWorkspace
    python PAT_stock/data/investigate_60min_sources.py
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

# Remove script dir from sys.path to avoid PAT_stock/data/calendar.py shadowing stdlib
_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if p != _script_dir]

import akshare as ak
import numpy as np
import pandas as pd
import requests

# ── 样本股票 ──────────────────────────────────────────

SAMPLE_SYMBOLS = [
    "000001",  # 平安银行 SZ
    "600000",  # 浦发银行 SH
    "300001",  # 特锐德 SZ(创业板)
    "688001",  # 华兴源创 SH(科创板)
    "000858",  # 五粮液 SZ
    "002001",  # 新和成 SZ
    "600519",  # 贵州茅台 SH
    "000002",  # 万科A SZ
    "601318",  # 中国平安 SH
    "000333",  # 美的集团 SZ
]

LOOKBACK_DAYS = 60  # 拉取最近 60 个交易日的 60 分钟数据
MIN_ROWS = 10       # 最少行数才算成功


def _ts_code(symbol: str) -> str:
    """6 位代码 → ts_code 格式"""
    if symbol.startswith("6"):
        return f"{symbol}.SH"
    return f"{symbol}.SZ"


def _code_pair(symbol: str) -> tuple:
    """返回 (sh/sz 前缀, 纯6位代码)"""
    if symbol.startswith("6"):
        return ("sh", symbol)
    return ("sz", symbol)


# ════════════════════════════════════════════════════════
# 数据源 1: AKShare — 东方财富分钟接口
# ════════════════════════════════════════════════════════

def source_ak_em_minute(symbol: str) -> dict:
    """AKShare stock_zh_a_hist_min_em — 东方财富分钟K线

    参数: symbol, period="60", start_date, end_date, adjust="qfq"
    """
    t0 = time.time()
    try:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        raw = ak.stock_zh_a_hist_min_em(
            symbol=symbol,
            period="60",
            start_date=start_str,
            end_date=end_str,
            adjust="qfq",
        )
        elapsed = time.time() - t0

        if raw is None or raw.empty:
            return {
                "source": "ak_em_minute",
                "symbol": symbol,
                "success": False,
                "rows": 0,
                "elapsed_sec": round(elapsed, 2),
                "error": "empty response",
                "columns": [],
                "date_range": None,
            }

        # 标准化列名
        col_map = {
            "时间": "timestamp",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
        }
        raw = raw.rename(columns=col_map)
        raw["timestamp"] = pd.to_datetime(raw["timestamp"])

        required = {"open", "high", "low", "close", "volume", "timestamp"}
        available = set(raw.columns) & required

        return {
            "source": "ak_em_minute",
            "symbol": symbol,
            "success": True,
            "rows": len(raw),
            "elapsed_sec": round(elapsed, 2),
            "error": None,
            "columns": sorted(raw.columns.tolist()),
            "date_range": {
                "start": raw["timestamp"].min().strftime("%Y-%m-%d %H:%M"),
                "end": raw["timestamp"].max().strftime("%Y-%m-%d %H:%M"),
            },
            "fields_complete": sorted(available),
            "fields_missing": sorted(required - available),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "source": "ak_em_minute",
            "symbol": symbol,
            "success": False,
            "rows": 0,
            "elapsed_sec": round(elapsed, 2),
            "error": f"{type(e).__name__}: {e}"[:200],
            "columns": [],
            "date_range": None,
        }


# ════════════════════════════════════════════════════════
# 数据源 2: AKShare — 新浪分钟接口
# ════════════════════════════════════════════════════════

def source_ak_sina_minute(symbol: str) -> dict:
    """AKShare stock_zh_a_minute — 新浪分钟K线

    参数: symbol="sz000001", period="60", adjust="qfq"
    """
    t0 = time.time()
    try:
        prefix, code = _code_pair(symbol)
        aksym = f"{prefix}{code}"

        raw = ak.stock_zh_a_minute(
            symbol=aksym,
            period="60",
            adjust="qfq",
        )
        elapsed = time.time() - t0

        if raw is None or raw.empty:
            return {
                "source": "ak_sina_minute",
                "symbol": symbol,
                "success": False,
                "rows": 0,
                "elapsed_sec": round(elapsed, 2),
                "error": "empty response",
                "columns": [],
                "date_range": None,
            }

        col_map = {
            "day": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }
        raw = raw.rename(columns=col_map)

        required = {"open", "high", "low", "close", "volume", "date"}
        available = set(raw.columns) & required

        return {
            "source": "ak_sina_minute",
            "symbol": symbol,
            "success": True,
            "rows": len(raw),
            "elapsed_sec": round(elapsed, 2),
            "error": None,
            "columns": sorted(raw.columns.tolist()),
            "date_range": {
                "start": str(raw["date"].iloc[0]) if "date" in raw.columns else None,
                "end": str(raw["date"].iloc[-1]) if "date" in raw.columns else None,
            },
            "fields_complete": sorted(available),
            "fields_missing": sorted(required - available),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "source": "ak_sina_minute",
            "symbol": symbol,
            "success": False,
            "rows": 0,
            "elapsed_sec": round(elapsed, 2),
            "error": f"{type(e).__name__}: {e}"[:200],
            "columns": [],
            "date_range": None,
        }


# ════════════════════════════════════════════════════════
# 数据源 3: 新浪 K-line API — 直接 HTTP
# ════════════════════════════════════════════════════════

SINA_KLINE_URL = (
    "https://money.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/CN_MarketData.getKLineData"
)


def source_sina_direct(symbol: str) -> dict:
    """新浪 K-line API 直接调用

    URL: money.finance.sina.com.cn/quotes_service/api/json_v2.php/...
    参数: symbol, scale=60, ma=no, datalen=2000
    """
    t0 = time.time()
    try:
        prefix, code = _code_pair(symbol)
        sina_sym = f"{prefix}{code}"

        params = {
            "symbol": sina_sym,
            "scale": "60",
            "ma": "no",
            "datalen": "2000",
        }
        resp = requests.get(SINA_KLINE_URL, params=params, timeout=15)

        if resp.status_code != 200:
            elapsed = time.time() - t0
            return {
                "source": "sina_direct",
                "symbol": symbol,
                "success": False,
                "rows": 0,
                "elapsed_sec": round(elapsed, 2),
                "error": f"HTTP {resp.status_code}",
                "columns": [],
                "date_range": None,
            }

        data = resp.json()
        elapsed = time.time() - t0

        if not data or not isinstance(data, list):
            return {
                "source": "sina_direct",
                "symbol": symbol,
                "success": False,
                "rows": 0,
                "elapsed_sec": round(elapsed, 2),
                "error": "non-list response" if data else "empty list",
                "columns": [],
                "date_range": None,
            }

        df = pd.DataFrame(data)
        df = df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
            "day": "date",
        })

        required = {"open", "high", "low", "close", "volume", "date"}
        available = set(df.columns) & required

        return {
            "source": "sina_direct",
            "symbol": symbol,
            "success": True,
            "rows": len(df),
            "elapsed_sec": round(elapsed, 2),
            "error": None,
            "columns": sorted(df.columns.tolist()),
            "date_range": {
                "start": str(df["date"].iloc[0]) if "date" in df.columns else None,
                "end": str(df["date"].iloc[-1]) if "date" in df.columns else None,
            },
            "fields_complete": sorted(available),
            "fields_missing": sorted(required - available),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "source": "sina_direct",
            "symbol": symbol,
            "success": False,
            "rows": 0,
            "elapsed_sec": round(elapsed, 2),
            "error": f"{type(e).__name__}: {e}"[:200],
            "columns": [],
            "date_range": None,
        }


# ════════════════════════════════════════════════════════
# 数据源 4: Tushare Pro — stk_mins
# ════════════════════════════════════════════════════════

def source_tushare_mins(symbol: str) -> dict:
    """Tushare Pro stk_mins — 分钟K线(需积分)

    参数: ts_code, freq="60min", 需要从环境变量获取 token
    """
    t0 = time.time()
    try:
        ts_code = _ts_code(symbol)
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")

        # 尝试从 loader 获取 pro 实例
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from PAT_stock.data.loader import get_pro
            pro = get_pro()
        except (ImportError, Exception) as e:
            return {
                "source": "tushare_mins",
                "symbol": symbol,
                "success": False,
                "rows": 0,
                "elapsed_sec": 0.0,
                "error": f"Cannot init Tushare: {type(e).__name__}",
                "columns": [],
                "date_range": None,
            }

        raw = pro.stk_mins(
            ts_code=ts_code,
            freq="60min",
            start_date=start_str,
            end_date=end_str,
        )
        elapsed = time.time() - t0

        if raw is None or raw.empty:
            return {
                "source": "tushare_mins",
                "symbol": symbol,
                "success": False,
                "rows": 0,
                "elapsed_sec": round(elapsed, 2),
                "error": "empty response (may need higher credit tier)",
                "columns": [],
                "date_range": None,
            }

        required = {"open", "high", "low", "close", "vol", "trade_time"}
        available = set(raw.columns) & required

        return {
            "source": "tushare_mins",
            "symbol": symbol,
            "success": True,
            "rows": len(raw),
            "elapsed_sec": round(elapsed, 2),
            "error": None,
            "columns": sorted(raw.columns.tolist()),
            "date_range": {
                "start": str(raw["trade_time"].min()),
                "end": str(raw["trade_time"].max()),
            },
            "fields_complete": sorted(available),
            "fields_missing": sorted(required - available),
        }
    except Exception as e:
        elapsed = time.time() - t0
        return {
            "source": "tushare_mins",
            "symbol": symbol,
            "success": False,
            "rows": 0,
            "elapsed_sec": round(elapsed, 2),
            "error": f"{type(e).__name__}: {e}"[:200],
            "columns": [],
            "date_range": None,
        }


# ════════════════════════════════════════════════════════
# 聚合与报告
# ════════════════════════════════════════════════════════

SOURCES = [
    ("ak_em_minute", source_ak_em_minute),
    ("ak_sina_minute", source_ak_sina_minute),
    ("sina_direct", source_sina_direct),
    ("tushare_mins", source_tushare_mins),
]


def compute_recommendation(results: list) -> dict:
    """根据测试结果计算推荐数据源

    评分标准:
      - 成功率 (0-40 分)
      - 平均速度 1/elapsed (0-20 分)
      - 数据丰富度 rows/1000 (0-20 分)
      - 字段完整性 (0-20 分)
    """
    source_stats = {}
    for r in results:
        src = r["source"]
        if src not in source_stats:
            source_stats[src] = {
                "tests": 0,
                "successes": 0,
                "total_rows": 0,
                "total_time": 0.0,
                "field_completeness": 0,
            }
        s = source_stats[src]
        s["tests"] += 1
        if r["success"]:
            s["successes"] += 1
            s["total_rows"] += r.get("rows", 0)
            s["total_time"] += r.get("elapsed_sec", 0)
            if "fields_missing" in r:
                s["field_completeness"] += len(r.get("fields_complete", []))

    rankings = []
    for src, s in source_stats.items():
        if s["tests"] == 0:
            continue
        success_rate = s["successes"] / s["tests"]
        avg_rows = s["total_rows"] / max(s["successes"], 1)
        avg_time = s["total_time"] / max(s["successes"], 1)
        field_avg = s["field_completeness"] / max(s["successes"], 1)  # avg fields

        score = (
            success_rate * 40
            + min(avg_rows / 1000, 1.0) * 20
            + min(1.0 / max(avg_time, 0.1), 1.0) * 20
            + (field_avg / 6.0) * 20
        )

        rankings.append({
            "source": src,
            "success_rate": round(success_rate, 2),
            "avg_rows": round(avg_rows, 1),
            "avg_time_sec": round(avg_time, 2),
            "avg_fields_complete": round(field_avg, 1),
            "score": round(score, 1),
        })

    rankings.sort(key=lambda x: x["score"], reverse=True)

    best = rankings[0] if rankings else None
    if best:
        reason = (
            f"{best['source']} scored {best['score']}: "
            f"success_rate={best['success_rate']:.0%}, "
            f"avg {best['avg_rows']} rows in {best['avg_time_sec']}s, "
            f"{best['avg_fields_complete']}/6 fields complete"
        )
        recommendation = {
            "primary": best["source"],
            "reason": reason,
            "fallback": rankings[1]["source"] if len(rankings) > 1 else "none",
            "all_rankings": rankings,
        }
    else:
        recommendation = {
            "primary": "none",
            "reason": "No data source succeeded on any stock",
            "fallback": "none",
            "all_rankings": [],
        }

    return recommendation


def main():
    print("=" * 70)
    print("  60 分钟 K 线数据源调查")
    print(f"  样本: {len(SAMPLE_SYMBOLS)} 只股票")
    print(f"  数据源: {len(SOURCES)} 个")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    all_results = []

    for i, symbol in enumerate(SAMPLE_SYMBOLS):
        print(f"\n[{i+1}/{len(SAMPLE_SYMBOLS)}] {_ts_code(symbol)}")
        for src_name, src_func in SOURCES:
            print(f"  {src_name} ...", end=" ", flush=True)
            result = src_func(symbol)
            status = "OK" if result["success"] else "FAIL"
            detail = f"{result.get('rows', 0)} rows, {result.get('elapsed_sec', 0):.1f}s"
            if result["error"]:
                detail += f" — {result['error']}"
            print(f"{status} ({detail})")
            all_results.append(result)
            time.sleep(0.3)  # 避免请求过快

    # ── 计算推荐 ──
    recommendation = compute_recommendation(all_results)

    # ── 汇总统计 ──
    source_summary = {}
    for r in all_results:
        src = r["source"]
        if src not in source_summary:
            source_summary[src] = {"success": 0, "fail": 0, "errors": []}
        if r["success"]:
            source_summary[src]["success"] += 1
        else:
            source_summary[src]["fail"] += 1
            if r.get("error"):
                source_summary[src]["errors"].append(r["error"])

    # ── 构建最终报告 ──
    report = {
        "metadata": {
            "investigation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_size": len(SAMPLE_SYMBOLS),
            "sources_tested": len(SOURCES),
            "lookback_days": LOOKBACK_DAYS,
        },
        "summary": {
            src: {
                "success": s["success"],
                "fail": s["fail"],
                "success_rate": f"{s['success']}/{s['success']+s['fail']}",
                "common_errors": list(set(s["errors"][:3])) if s["errors"] else [],
            }
            for src, s in source_summary.items()
        },
        "recommendation": recommendation,
        "results": all_results,
    }

    # ── 写入 JSON ──
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "60min_source_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # ── 控制台摘要 ──
    print("\n" + "=" * 70)
    print("  调查结果")
    print("=" * 70)
    for src, s in source_summary.items():
        total = s["success"] + s["fail"]
        rate = f"{s['success']}/{total}"
        print(f"  {src}: {rate} 成功")
        if s["errors"]:
            for err in list(set(s["errors"]))[:3]:
                print(f"    → {err[:100]}")
    print(f"\n  推荐: {recommendation['primary']}")
    print(f"  理由: {recommendation['reason']}")
    print(f"\n  报告已写入: {output_path}")


if __name__ == "__main__":
    main()
