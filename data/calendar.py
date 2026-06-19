"""交易日历模块 — Tushare trade_cal 封装 + parquet 缓存

Usage:
    from data.calendar import get_trade_cal, is_trade_day, prev_trade_day, next_trade_day

    days = get_trade_cal("20260101", "20260610")
    is_trade_day("20260610")          # True/False
    prev_trade_day("20260610")        # '20260609'
    next_trade_day("20260610")        # '20260611'
    trade_days_between("20260601", "20260610")  # 7
"""

import os
from pathlib import Path
from typing import Optional, List

import pandas as pd

from .loader import get_pro, _rate_limit

# ── 缓存路径 ──────────────────────────────────────────

_CAL_CACHE = Path(__file__).resolve().parent / "trade_cal.parquet"


def _read_cal_cache() -> Optional[pd.DataFrame]:
    """读取交易日历缓存"""
    if not _CAL_CACHE.exists():
        return None
    try:
        df = pd.read_parquet(_CAL_CACHE)
        df["cal_date"] = pd.to_datetime(df["cal_date"])
        return df
    except Exception:
        return None


def _write_cal_cache(df: pd.DataFrame):
    """写入交易日历缓存"""
    if df is not None and not df.empty:
        df.to_parquet(_CAL_CACHE, index=False)


# ── 公开 API ──────────────────────────────────────────

def get_trade_cal(start_date: str = "20170101",
                  end_date: str = "20270101") -> List[str]:
    """获取交易日列表 (YYYYMMDD 格式)

    优先从本地 parquet 读取, 缓存未覆盖的区间走 Tushare API。
    结果合并写入缓存。

    Args:
        start_date: 起始日 YYYYMMDD
        end_date:   结束日 YYYYMMDD

    Returns:
        交易日字符串列表, 按日期升序排列
    """
    req_start = pd.Timestamp(start_date)
    req_end = pd.Timestamp(end_date)
    cached = _read_cal_cache()

    if cached is not None and not cached.empty:
        cached_start = cached["cal_date"].min()
        cached_end = cached["cal_date"].max()

        # 缓存完全覆盖
        if cached_start <= req_start and cached_end >= req_end:
            days = cached["cal_date"]
            mask = (days >= req_start) & (days <= req_end)
            return sorted(days[mask].dt.strftime("%Y%m%d").tolist())

        # 部分覆盖 — 请求缺失部分
        fetch_start = (cached_end + pd.Timedelta(days=1)).strftime("%Y%m%d") \
            if cached_end >= req_start else start_date
        fetch_end = end_date

        # 前方也有缺失吗? 仅当请求起点早于缓存起点
        if req_start < cached_start:
            fetch_start = start_date
            fetch_end = end_date  # 重新拉全量 (简单策略)

        # 后方缺失
        new_df = _fetch_trade_cal(fetch_start, fetch_end)
        if new_df is not None and not new_df.empty:
            merged = pd.concat([cached, new_df], ignore_index=True)
            merged = merged.drop_duplicates(subset=["cal_date"])
            merged = merged.sort_values("cal_date")
            _write_cal_cache(merged)

            days = merged["cal_date"]
            mask = (days >= req_start) & (days <= req_end)
            return sorted(days[mask].dt.strftime("%Y%m%d").tolist())

        # 获取失败, 退回已有缓存
        days = cached["cal_date"]
        mask = (days >= req_start) & (days <= req_end)
        return sorted(days[mask].dt.strftime("%Y%m%d").tolist())

    # 无缓存, 全量请求
    df = _fetch_trade_cal(start_date, end_date)
    if df is None or df.empty:
        return []
    _write_cal_cache(df)
    days = pd.to_datetime(df["cal_date"])
    return sorted(days.dt.strftime("%Y%m%d").tolist())


def is_trade_day(date: str) -> bool:
    """判断某日是否为交易日

    Args:
        date: YYYYMMDD 格式日期

    Returns:
        bool
    """
    days = get_trade_cal(
        start_date=_surround_start(date, 30),
        end_date=_surround_end(date, 30),
    )
    return date in days


def prev_trade_day(date: str) -> Optional[str]:
    """获取前一个交易日

    Args:
        date: YYYYMMDD

    Returns:
        前一日 YYYYMMDD, 无则 None
    """
    start = _surround_start(date, 60)
    end = _surround_end(date, 30)
    days = get_trade_cal(start, end)
    ts = pd.Timestamp(date)
    prev = [d for d in days if pd.Timestamp(d) < ts]
    return prev[-1] if prev else None


def next_trade_day(date: str) -> Optional[str]:
    """获取后一个交易日

    Args:
        date: YYYYMMDD

    Returns:
        后一日 YYYYMMDD, 无则 None
    """
    start = _surround_start(date, 30)
    end = _surround_end(date, 60)
    days = get_trade_cal(start, end)
    ts = pd.Timestamp(date)
    nxt = [d for d in days if pd.Timestamp(d) > ts]
    return nxt[0] if nxt else None


def trade_days_between(start: str, end: str) -> int:
    """区间内交易日数 (含首尾)

    Args:
        start: YYYYMMDD
        end:   YYYYMMDD

    Returns:
        int — 交易日数量
    """
    days = get_trade_cal(start, end)
    return len(days)


# ── 内部 ──────────────────────────────────────────────

def _fetch_trade_cal(start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """从 Tushare API 获取交易日历 — 使用 loader 统一限频"""
    try:
        pro = get_pro()
        _rate_limit()
        df = pro.trade_cal(exchange="SSE", start_date=start_date,
                           end_date=end_date, is_open="1")
        if df is not None and not df.empty:
            df["cal_date"] = pd.to_datetime(df["cal_date"])
            df = df.sort_values("cal_date").reset_index(drop=True)
        return df
    except Exception:
        return None


def _surround_start(date: str, days_before: int) -> str:
    """计算 date 前 N 天的日期字符串"""
    return (pd.Timestamp(date) - pd.Timedelta(days=days_before)).strftime("%Y%m%d")


def _surround_end(date: str, days_after: int) -> str:
    """计算 date 后 N 天的日期字符串"""
    return (pd.Timestamp(date) + pd.Timedelta(days=days_after)).strftime("%Y%m%d")
