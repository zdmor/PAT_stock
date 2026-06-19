"""PAT 每日运行入口 — 定时任务/手动触发的盘后全流程

Usage:
  python run_daily.py              # 当日扫描 (含健康检查)
  python run_daily.py --date 20260609  # 指定日期
  python run_daily.py --health-only    # 仅运行健康检查
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# 统一 sys.path: 确保 D:\ClaudeWorkspace 可 import (zhunwo 等)
_CLAUDE_ROOT = Path(__file__).resolve().parent.parent
if str(_CLAUDE_ROOT) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_ROOT))

# ── 健康检查 ──────────────────────────────────────────

ENABLE_60MIN = True   # 全局标志: 60 分钟线是否可用
ENABLE_DAILY = True   # 全局标志: 日线 API 是否可用


def health_check():
    """启动时验证数据 API 可用性

    检查项:
      1. Tushare daily API — 用 000001.SZ 测试
      2. 60 分钟线 API (AKShare Sina) — 用 000001.SZ 测试

    不可用时输出清晰警告, 设置全局标志供下游模块降级。
    """
    global ENABLE_DAILY, ENABLE_60MIN
    print("[health_check] 验证数据 API 可用性...")

    # 1. 日线 API (Tushare)
    try:
        from PAT_stock.data.loader import get_pro
        pro = get_pro()
        df = pro.daily(ts_code="000001.SZ", start_date="20260601", end_date="20260610")
        if df is not None and not df.empty:
            print("  [OK] Tushare daily API — 正常")
            ENABLE_DAILY = True
        else:
            print("  [FAIL] Tushare daily API — 返回空数据, Token 可能失效")
            ENABLE_DAILY = False
    except Exception as e:
        print(f"  [FAIL] Tushare daily API — 不可用: {e}")
        ENABLE_DAILY = False

    # 2. 60 分钟线 (AKShare Sina)
    try:
        from PAT_stock.data.loader import get_60min
        df60 = get_60min("000001.SZ", "20260601", "20260610")
        if df60 is not None and not df60.empty:
            print("  [OK] 60 分钟线 API (AKShare Sina) — 正常")
            ENABLE_60MIN = True
        else:
            print("  [WARN] 60 分钟线 API — 返回空数据, M2-M4 60min 功能将降级")
            ENABLE_60MIN = False
    except Exception as e:
        print(f"  [WARN] 60 分钟线 API — 不可用: {e}")
        ENABLE_60MIN = False

    # 汇总
    if not ENABLE_DAILY:
        print("[health_check] CRITICAL: 日线 API 不可用, 系统无法运行!")
    elif not ENABLE_60MIN:
        print("[health_check] WARNING: 60 分钟线不可用, 仅日线模式")
    else:
        print("[health_check] 全部 API 正常")

    return ENABLE_DAILY


# ── 主入口 ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PAT 每日运行")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y%m%d"),
                        help="运行日期 (默认当日)")
    parser.add_argument("--health-only", action="store_true",
                        help="仅运行健康检查")
    args = parser.parse_args()

    # 健康检查 (始终运行)
    daily_ok = health_check()
    if args.health_only:
        return

    if not daily_ok:
        print("[PAT] 日线 API 不可用, 终止运行")
        return

    print(f"\n[PAT] ====== 日线扫描: {args.date} ======")

    # 1. 交易日判断
    from data.calendar import is_trade_day
    if not is_trade_day(args.date):
        print(f"[PAT] {args.date} 非交易日, 跳过")
        return

    # 2. 运行流水线
    print("[PAT] 启动流水线...")
    # TODO: M2+ pipeline 接入


if __name__ == "__main__":
    main()
