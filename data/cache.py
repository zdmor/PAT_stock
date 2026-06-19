"""K 线本地缓存 — parquet 持久化 + 增量追加

Usage:
    cache = KlineCache()
    df = cache.get_daily("000001.SZ", "20260101", "20260610")
    df = cache.get_60min("000001.SZ", "20260101", "20260610")
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd

from .loader import get_daily as _fetch_daily
from .loader import get_60min as _fetch_60min


class KlineCache:
    """K 线本地缓存管理器

    缓存策略:
      - 日线:   daily_{ts_code}.parquet
      - 60分钟: min60_{ts_code}.parquet
      - 增量追加: 已缓存的日期范围不重复请求, 只请求缺失区间
    """

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir is None:
            cache_dir = str(
                Path(__file__).resolve().parent / "cache"
            )
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── 日线 ──────────────────────────────────────────

    def _daily_path(self, ts_code: str) -> Path:
        safe = ts_code.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"daily_{safe}.parquet"

    def get_daily(self, ts_code: str, start_date: str,
                  end_date: Optional[str] = None) -> pd.DataFrame:
        """获取日线 (缓存优先, 增量追加)

        Args:
            ts_code:    股票代码
            start_date: 起始日 YYYYMMDD
            end_date:   结束日 YYYYMMDD (默认当日)

        Returns:
            DataFrame columns: ts_code, trade_date, open, high, low, close, vol, amount
        """
        from datetime import datetime

        end = end_date or datetime.now().strftime("%Y%m%d")
        path = self._daily_path(ts_code)

        # 读取已有缓存
        cached = self._read_cache(path)

        # 确定需要请求的日期范围
        if cached is not None and not cached.empty:
            cached_start = cached["trade_date"].min()
            cached_end = cached["trade_date"].max()

            # 计算缺失区间
            needed_ranges = []
            req_start, req_end = pd.Timestamp(start_date), pd.Timestamp(end)

            if cached_start > req_start:
                needed_ranges.append((
                    start_date,
                    (cached_start - pd.Timedelta(days=1)).strftime("%Y%m%d")
                ))
            if cached_end < req_end:
                needed_ranges.append((
                    (cached_end + pd.Timedelta(days=1)).strftime("%Y%m%d"),
                    end
                ))

            if not needed_ranges:
                return self._filter_range(cached, start_date, end)

            # 请求缺失数据
            new_frames = []
            for s, e in needed_ranges:
                df = _fetch_daily(ts_code, s, e)
                if df is not None and not df.empty:
                    new_frames.append(df)

            if new_frames:
                merged = pd.concat([cached] + new_frames, ignore_index=True)
                merged = merged.drop_duplicates(
                    subset=["trade_date"]).sort_values("trade_date")
                self._write_cache(path, merged)
                return self._filter_range(merged, start_date, end)

            return self._filter_range(cached, start_date, end)

        # 无缓存, 全量请求
        df = _fetch_daily(ts_code, start_date, end)
        if df is not None and not df.empty:
            self._write_cache(path, df)
        return df if df is not None else pd.DataFrame()

    # ── 60 分钟线 ──────────────────────────────────────

    def _min60_path(self, ts_code: str) -> Path:
        safe = ts_code.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"min60_{safe}.parquet"

    def get_60min(self, ts_code: str, start_date: str,
                  end_date: Optional[str] = None) -> pd.DataFrame:
        """获取 60 分钟线 (缓存优先, 增量追加)

        Args:
            ts_code:    股票代码
            start_date: 起始日 YYYYMMDD
            end_date:   结束日 YYYYMMDD (默认当日)

        Returns:
            DataFrame columns: ts_code, trade_date, trade_time, open, high, low, close, vol
        """
        from datetime import datetime

        end = end_date or datetime.now().strftime("%Y%m%d")
        path = self._min60_path(ts_code)

        # 读取已有缓存
        cached = self._read_cache(path)

        # 60分钟线按 trade_date 过滤
        if cached is not None and not cached.empty:
            cached_start = cached["trade_date"].min()
            cached_end = cached["trade_date"].max()

            needed_ranges = []
            req_start, req_end = pd.Timestamp(start_date), pd.Timestamp(end)

            if cached_start > req_start:
                needed_ranges.append((
                    start_date,
                    (cached_start - pd.Timedelta(days=1)).strftime("%Y%m%d")
                ))
            if cached_end < req_end:
                needed_ranges.append((
                    (cached_end + pd.Timedelta(days=1)).strftime("%Y%m%d"),
                    end
                ))

            if not needed_ranges:
                return self._filter_range(cached, start_date, end)

            # 请求缺失区间
            new_frames = []
            for s, e in needed_ranges:
                df = _fetch_60min(ts_code, s, e)
                if df is not None and not df.empty:
                    new_frames.append(df)

            if new_frames:
                merged = pd.concat([cached] + new_frames, ignore_index=True)
                # 60分钟线用 trade_time 去重
                time_col = "trade_time" if "trade_time" in merged.columns else None
                if time_col:
                    merged = merged.drop_duplicates(
                        subset=[time_col]).sort_values(time_col)
                self._write_cache(path, merged)
                return self._filter_range(merged, start_date, end)

            return self._filter_range(cached, start_date, end)

        # 无缓存, 全量请求
        df = _fetch_60min(ts_code, start_date, end)
        if df is not None and not df.empty:
            self._write_cache(path, df)
        return df if df is not None else pd.DataFrame()

    # ── 内部工具 ───────────────────────────────────────

    @staticmethod
    def _read_cache(path: Path) -> Optional[pd.DataFrame]:
        """读取 parquet 缓存"""
        if not path.exists():
            return None
        try:
            df = pd.read_parquet(path)
            return df if not df.empty else None
        except Exception:
            return None

    @staticmethod
    def _write_cache(path: Path, df: pd.DataFrame):
        """写入 parquet 缓存"""
        if df is not None and not df.empty:
            df.to_parquet(path, index=False)

    @staticmethod
    def _filter_range(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
        """按日期范围过滤"""
        if df is None or df.empty:
            return df
        date_col = "trade_date" if "trade_date" in df.columns else "trade_time"
        df[date_col] = pd.to_datetime(df[date_col])
        mask = (df[date_col] >= pd.Timestamp(start)) & (df[date_col] <= pd.Timestamp(end))
        return df[mask].reset_index(drop=True)
