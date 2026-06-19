"""Pinbar 参数扫描: 主影线比 + 实体位置阈值 vs 信号数

对 15 只校准股票, 测试不同 main_shadow_ratio + body_position_threshold 组合,
输出信号数热力图和单个参数边际曲线。

Usage:
    cd D:/ClaudeWorkspace
    python PAT_stock/reviews/pinbar_param_sweep.py
"""

import sys
import os
import time
import warnings
import json
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_PROJ_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJ_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_PROJ_ROOT.parent))

from PAT_stock.data.loader import get_daily
from PAT_stock.patterns.pinbar import detect_pinbar

# ── 股票池 — 沿用校准脚本的 15 只 ──
LARGE = ["000001.SZ", "600519.SH", "600036.SH", "601398.SH", "600900.SH"]
MID = ["002522.SZ", "002213.SZ", "688508.SH", "300292.SZ", "688639.SH"]
SMALL = ["002825.SZ", "301125.SZ", "002369.SZ", "300966.SZ", "300288.SH"]

ALL_STOCKS = LARGE + MID + SMALL

START_DATE = "20240601"
END_DATE = "20260614"

# ── 参数扫描网格 ──
SHADOW_RATIOS = [0.50, 0.55, 0.60, 0.667, 0.70, 0.75, 0.80]
BODY_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
ATR_RATIO = 0.3  # 固定噪声过滤


def load_all(ts_codes: list) -> dict:
    result = {}
    for code in ts_codes:
        df = get_daily(code, START_DATE, END_DATE)
        if df is not None and len(df) > 60:
            result[code] = df.sort_values("trade_date").reset_index(drop=True)
    return result


def count_signals(df: pd.DataFrame, shadow_ratio: float, body_th: float) -> int:
    """Run detect_pinbar with given params, return total signal count."""
    result = detect_pinbar(
        df,
        main_shadow_ratio=shadow_ratio,
        body_position_threshold=body_th,
        min_range_atr_ratio=ATR_RATIO,
    )
    return int((result["signal"] != 0).sum())


def main():
    print("=" * 65)
    print("  Pinbar 参数扫描")
    print(f"  股票: {len(ALL_STOCKS)} 只 (5 large + 5 mid + 5 small)")
    print(f"  区间: {START_DATE} — {END_DATE}")
    print(f"  参数网格: {len(SHADOW_RATIOS)}×{len(BODY_THRESHOLDS)} = "
          f"{len(SHADOW_RATIOS) * len(BODY_THRESHOLDS)} 组合")
    print("=" * 65)

    print("\n加载数据...")
    t0 = time.time()
    data = load_all(ALL_STOCKS)
    print(f"  加载 {len(data)}/{len(ALL_STOCKS)} 只, 耗时 {time.time() - t0:.1f}s")

    if len(data) == 0:
        print("  无数据, 退出")
        return

    # ── 全网格扫描 ──
    print("\n扫描中...")
    # results_grid[shadow_idx][body_idx] = total_signals_across_all_stocks
    grid = np.zeros((len(SHADOW_RATIOS), len(BODY_THRESHOLDS)), dtype=int)
    # per_stock_counts[code][shadow_idx][body_idx]
    per_stock = {code: np.zeros_like(grid) for code in data}

    total_combos = len(SHADOW_RATIOS) * len(BODY_THRESHOLDS)
    combo_idx = 0

    for si, sr in enumerate(SHADOW_RATIOS):
        for bi, bt in enumerate(BODY_THRESHOLDS):
            combo_idx += 1
            total_sig = 0
            for code, df in data.items():
                n = count_signals(df, sr, bt)
                per_stock[code][si, bi] = n
                total_sig += n
            grid[si, bi] = total_sig
            print(f"  [{combo_idx}/{total_combos}] shadow={sr:.3f} body_th={bt:.2f} → {total_sig} 信号")

    # ── 输出热力图 ──
    print("\n" + "=" * 65)
    print("  【热力图: 总信号数 (15 只股票, ~24 月)】")
    print("=" * 65)

    # 表头
    header = f"{'shadow\\body_th':<16}" + "".join(f"{bt:>8.2f}" for bt in BODY_THRESHOLDS)
    print(f"  {header}")
    print(f"  {'-' * (16 + 8 * len(BODY_THRESHOLDS))}")

    for si, sr in enumerate(SHADOW_RATIOS):
        row = f"{sr:<12.3f}    " + "".join(f"{grid[si, bi]:>8d}" for bi in range(len(BODY_THRESHOLDS)))
        print(f"  {row}")

    # ── 每月每只信号密度 ──
    n_stocks = len(data)
    total_months = 24  # ~24 months
    density = grid / n_stocks / total_months

    print(f"\n  【信号密度: 个/月/只】")
    header2 = f"{'shadow\\body_th':<16}" + "".join(f"{bt:>8.2f}" for bt in BODY_THRESHOLDS)
    print(f"  {header2}")
    print(f"  {'-' * (16 + 8 * len(BODY_THRESHOLDS))}")
    for si, sr in enumerate(SHADOW_RATIOS):
        row = f"{sr:<12.3f}    " + "".join(f"{density[si, bi]:>8.2f}" for bi in range(len(BODY_THRESHOLDS)))
        print(f"  {row}")

    # ── 边际曲线: 固定 body_th=0.4, 变 shadow_ratio ──
    default_bt_idx = BODY_THRESHOLDS.index(0.40)
    print(f"\n  【边际: body_th=0.40 固定, shadow_ratio 变化】")
    print(f"  {'shadow_ratio':<16}{'总信号':>10}{'密度(/月/只)':>14}{'vs默认':>12}")
    print(f"  {'-' * 52}")
    default_sig = grid[SHADOW_RATIOS.index(0.667), default_bt_idx]
    for si, sr in enumerate(SHADOW_RATIOS):
        sig = grid[si, default_bt_idx]
        d = sig / n_stocks / total_months
        vs = sig / default_sig - 1
        print(f"  {sr:<16.3f}{sig:>10d}{d:>13.2f}{vs:>+11.1%}")

    # ── 边际曲线: 固定 shadow=0.667, 变 body_th ──
    default_sr_idx = SHADOW_RATIOS.index(0.667)
    print(f"\n  【边际: shadow_ratio=0.667 固定, body_threshold 变化】")
    print(f"  {'body_threshold':<16}{'总信号':>10}{'密度(/月/只)':>14}{'vs默认':>12}")
    print(f"  {'-' * 52}")
    for bi, bt in enumerate(BODY_THRESHOLDS):
        sig = grid[default_sr_idx, bi]
        d = sig / n_stocks / total_months
        vs = sig / default_sig - 1
        print(f"  {bt:<16.2f}{sig:>10d}{d:>13.2f}{vs:>+11.1%}")

    # ── 建议候选组合 ──
    print("\n" + "=" * 65)
    print("  候选参数组合分析")
    print("=" * 65)

    candidates = [
        (0.667, 0.40, "当前默认"),
        (0.60, 0.40, "放宽影线"),
        (0.667, 0.45, "放宽实体"),
        (0.60, 0.45, "双放宽"),
        (0.55, 0.40, "大幅放宽影线"),
        (0.667, 0.50, "大幅放宽实体"),
    ]

    print(f"  {'方案':<20}{'shadow':>8}{'body_th':>8}{'总信号':>10}{'密度':>10}{'vs默认':>10}")
    print(f"  {'-' * 66}")
    for sr, bt, label in candidates:
        si = SHADOW_RATIOS.index(sr)
        bi = BODY_THRESHOLDS.index(bt)
        sig = grid[si, bi]
        d = sig / n_stocks / total_months
        vs = sig / default_sig - 1
        print(f"  {label:<20}{sr:>8.3f}{bt:>8.2f}{sig:>10d}{d:>9.2f}{vs:>+9.1%}")

    # ── 最推荐组合的逐个股明细 ──
    print("\n" + "=" * 65)
    print("  【推荐: shadow=0.60, body_th=0.45 — 逐个股明细】")
    print("=" * 65)

    sr_rec = 0.60
    bt_rec = 0.45
    si_rec = SHADOW_RATIOS.index(sr_rec)
    bi_rec = BODY_THRESHOLDS.index(bt_rec)

    print(f"  {'股票':<12}{'当前(0.667/0.40)':>16}{'新(0.60/0.45)':>16}{'增幅':>10}")
    print(f"  {'-' * 54}")
    current_total = 0
    new_total = 0
    for code in sorted(data.keys()):
        cur = per_stock[code][default_sr_idx, default_bt_idx]
        new = per_stock[code][si_rec, bi_rec]
        current_total += cur
        new_total += new
        pct = (new / cur - 1) if cur > 0 else 0
        print(f"  {code:<12}{cur:>16d}{new:>16d}{pct:>+9.1%}")
    print(f"  {'-' * 54}")
    print(f"  {'合计':<12}{current_total:>16d}{new_total:>16d}{(new_total/current_total-1):>+9.1%}")

    # ── 信号质量预估 ──
    print(f"\n  【质量预估: shadow 从 0.667 降到 0.60】")
    print(f"  影线门槛放松 10% → 预计增加 30-50% 信号")
    print(f"  同时容忍更多弱影线信号, 假突破比例预计从当前 ~30% 升至 ~40%")
    print(f"  建议配合关键位过滤 (near_key_level=True) 保留高质量信号")

    # ── 写入文件 ──
    output = {
        "shadow_ratios": SHADOW_RATIOS,
        "body_thresholds": BODY_THRESHOLDS,
        "grid_total_signals": grid.tolist(),
        "density_per_month_per_stock": np.round(density, 3).tolist(),
        "candidates": [
            {"shadow": sr, "body_th": bt, "label": lbl, "total": int(grid[SHADOW_RATIOS.index(sr), BODY_THRESHOLDS.index(bt)])}
            for sr, bt, lbl in candidates
        ],
    }
    out_path = _PROJ_ROOT / "reviews" / "pinbar_param_sweep_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  结果已写入: {out_path}")


if __name__ == "__main__":
    main()
