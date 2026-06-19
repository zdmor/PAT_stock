"""K 线数据获取模块 — Tushare 日线 + AKShare 60 分钟线

Tushare 连接自包含, 不依赖其他系统。
Token 来源: 环境变量 TUSHARE_TOKEN → trading_system/config.json
"""

import json
import os
import time
from typing import Optional

import pandas as pd

# ── Tushare Pro 单例 ────────────────────────────────────

_pro = None
_last_api_call = 0.0
_RATE_LIMIT = 0.3


def get_pro():
    """获取 Tushare Pro 单例"""
    global _pro
    if _pro is not None:
        return _pro
    import tushare as ts

    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        cfg_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__),
                         "..", "..", "..", "trading_system", "config.json"))
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                cfg = json.load(f)
            token = cfg.get("_tushare", {}).get("token", "")
    if token:
        ts.set_token(token)
    _pro = ts.pro_api()
    return _pro

# ── 限频 ──────────────────────────────────────────────

_last_api_call = 0.0
_RATE_LIMIT = 0.3  # 秒


def _rate_limit():
    """API 调用间隔 >= _RATE_LIMIT 秒"""
    global _last_api_call
    now = time.time()
    elapsed = now - _last_api_call
    if elapsed < _RATE_LIMIT:
        time.sleep(_RATE_LIMIT - elapsed)
    _last_api_call = time.time()


# ── 日线 ──────────────────────────────────────────────

def get_daily(ts_code: str, start_date: str,
              end_date: Optional[str] = None) -> pd.DataFrame:
    """获取个股日线数据

    Args:
        ts_code:    股票代码, 如 '000001.SZ'
        start_date: 起始日期, YYYYMMDD
        end_date:   结束日期, YYYYMMDD (默认当日)

    Returns:
        DataFrame columns: ts_code, trade_date, open, high, low, close, vol, amount
    """
    from datetime import datetime
    end = end_date or datetime.now().strftime("%Y%m%d")

    pro = get_pro()
    _rate_limit()
    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end)

    if df is None or df.empty:
        return pd.DataFrame(
            columns=["ts_code", "trade_date", "open", "high",
                     "low", "close", "vol", "amount"])

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date").reset_index(drop=True)

    cols = ["ts_code", "trade_date", "open", "high", "low", "close",
            "vol", "amount"]
    existing = [c for c in cols if c in df.columns]
    return df[existing]


# ── 60 分钟线 (AKShare Sina, 免费) ────────────────────

# ts_code → Sina symbol 映射
_SINA_MAP = {"SH": "sh", "SZ": "sz", "BJ": "bj"}
_SINA_CACHE = {}  # symbol → df 缓存, 避免重复请求同一只


def _ts_code_to_sina(ts_code: str) -> str:
    """将 '000001.SZ' 转为 'sh000001'"""
    code, market = ts_code.split(".")
    prefix = _SINA_MAP.get(market.upper(), "sh")
    return f"{prefix}{code}"


def get_60min(ts_code: str, start_date: str,
              end_date: Optional[str] = None) -> pd.DataFrame:
    """获取个股 60 分钟 K 线

    数据源: AKShare Sina (免费, 无需积分, 历史 ~2 年)
    限频: 每次调用间隔 1s (Sina 无官方限频要求, 保守)

    Args:
        ts_code:    股票代码, 如 '000001.SZ'
        start_date: 起始日期, YYYYMMDD
        end_date:   结束日期, YYYYMMDD (默认当日)

    Returns:
        DataFrame columns: ts_code, trade_date, trade_time, open, high, low, close, vol
    """
    from datetime import datetime

    end = end_date or datetime.now().strftime("%Y%m%d")
    symbol = _ts_code_to_sina(ts_code)

    # 全量拉取 Sina (该接口无 start_date/end_date 参数)
    if symbol not in _SINA_CACHE:
        try:
            import akshare as ak
            raw = ak.stock_zh_a_minute(symbol=symbol, period="60", adjust="qfq")
            if raw is None or raw.empty:
                return pd.DataFrame(columns=["ts_code", "trade_date", "trade_time",
                                              "open", "high", "low", "close", "vol"])
            raw.columns = [c.lower() for c in raw.columns]
            # day → trade_time
            raw.rename(columns={"day": "trade_time", "volume": "vol"}, inplace=True)
            raw["trade_time"] = pd.to_datetime(raw["trade_time"])
            raw = raw.sort_values("trade_time").reset_index(drop=True)
            raw["ts_code"] = ts_code
            _SINA_CACHE[symbol] = raw
            _rate_limit()
        except Exception as e:
            print(f"  [WARN] Sina 60min 获取失败 {symbol}: {e}")
            return pd.DataFrame(columns=["ts_code", "trade_date", "trade_time",
                                          "open", "high", "low", "close", "vol"])

    df = _SINA_CACHE[symbol].copy()
    df["trade_date"] = df["trade_time"].dt.strftime("%Y%m%d")

    # 按日期区间过滤
    t_start = pd.Timestamp(start_date)
    t_end = pd.Timestamp(end)
    mask = (df["trade_time"] >= t_start) & (df["trade_time"] <= t_end)
    result = df[mask].reset_index(drop=True)

    if result.empty:
        return pd.DataFrame(columns=["ts_code", "trade_date", "trade_time",
                                      "open", "high", "low", "close", "vol"])

    cols = ["ts_code", "trade_date", "trade_time", "open", "high",
            "low", "close", "vol"]
    return result[cols]


def clear_60min_cache():
    """清空 Sina 60 分钟线内存缓存"""
    _SINA_CACHE.clear()
