# P1: Cross-Module Interaction Protocol

> 项目: PAT (Price Action Trading)
> 用途: 定义 P1 三个模块 (Pinbar, Key Levels, Always-In) 之间的通信契约、执行顺序、输出组合方式
> 阅读者: workbuddy (pipeline 实现), Darwin (集成调试)
> 依赖: `design_pinbar.md`, `design_key_levels.md`, `design_always_in.md`

---

## 1. Pipeline Run Order (Single Stock)

P1 管线对单只股票的执行顺序固定为 6 步，每步的输入是上一步的输出。

```
Step 1: loader.get_daily(ts_code, start, end) → df (pd.DataFrame)

Step 2: market_state.determine_always_in(df) → ai_result dict
        │
        ├── direction: "bullish"|"bearish"|"oscillating"
        ├── confidence: float [0, 1]
        └── trend_filter (via get_trend_filter()): "long_only"|"short_only"|"neutral"

Step 3: key_levels.detect_key_levels(df) → (levels[], meta_dict)
        │
        ├── levels: list[KeyLevel]  (sorted by strength)
        └── metadata: {swing_count, swing_density, quality_warning}

Step 4: pinbar.detect_pinbar(df, key_levels=levels) → df (with signal columns)
        │
        ├── signal: -1/0/1  (bearish/none/bullish)
        ├── signal_type: str
        ├── pinbar_strength: str
        ├── near_key_level: bool (from key_levels context)
        └── key_level_distance: float (from key_levels context)

Step 5: Combine: for each pinbar signal, filter by Always-In direction
        │
        ├── aligned signals: pass through (always_in_aligned=True)
        ├── conflicting signals: still reported but marked (always_in_aligned=False)
        └── score estimation: optional combined rating

Step 6: Output: formatted signal list → pipeline_result dict
```

**时间维度说明:** 所有模块使用同一段 `df` (同一时间窗口)，不存在滚动窗口内的异步更新。Step 2-4 在同一个 DataFrame 上做不同视角的分析。

---

## 2. Central Data Flow

### 2.1 Pipeline Context — 单只股票的完整分析结果

```python
pipeline_result = {
    # ——— 标识 ———
    "ts_code": str,                    # 如 "000001.SZ"
    "trade_date": str,                 # 分析日期 YYYYMMDD
    "skip": bool,                      # 是否跳过 (数据不足等)
    "skip_reason": str,                # 跳过原因 (可选)

    # ——— Step 1: 原始数据 ———
    # df 不直接进 result (体积大), 但各步骤的结果字段携带所需信息
    "n_bars": int,                     # K 线数 (调试用)

    # ——— Step 2: Always-In ———
    "always_in": {
        "direction": str,              # "bullish" | "bearish" | "oscillating"
        "confidence": float,           # 0.0 ~ 1.0
        "structure": str,              # "HHHL" | "LHLL" | "mixed"
        "trend_filter": str,           # "long_only" | "short_only" | "neutral"
        "dimensions": {                # 三维详情, 调试用
            "ema_slope":       {"score": float, "direction": str, "weight": 0.35},
            "hh_hl_structure": {"score": float, "direction": str, "weight": 0.40},
            "channel_position":{"score": float, "direction": str, "weight": 0.25}
        },
    },

    # ——— Step 3: Key Levels ———
    "key_levels": {
        "levels": list,                # list[KeyLevel], 见 design_key_levels.md
        "metadata": {                  # 统计信息
            "swing_count": int,        # 总 swing 点数量
            "swing_density": float,    # swing 点密度 (点数 / K 线数)
            "quality_warning": str,    # 质量警告 (可选): "too_few_levels" / "low_density" / ""
        },
        "summary": str,                # key_levels_summary() 的人类可读文本
    },

    # ——— Step 4 + 5: 信号列表 (过滤后) ———
    "signals": [
        {
            "date": str,               # YYYYMMDD
            "direction": str,          # "bullish" | "bearish"
            "strength": str,           # "strong" | "normal"
            "entry_trigger": float,    # 突破价 (bullish=high, bearish=low)
            "stop_loss": float,        # 止损价 (可选, 由策略层填充)
            "near_key_level": bool,    # Pinbar 是否在关键位附近
            "key_level_distance": float,  # 距最近关键位的 ATR 倍数 (None 若无)
            "always_in_aligned": bool, # 信号方向与 Always-In 一致
            "score": float,            # 综合评分 (可选, 当前版本默认 0.0)
        }
    ],
    "total_signals": int,              # signals 长度
    "aligned_signals": int,            # always_in_aligned=True 的数量
    "conflicting_signals": int,        # always_in_aligned=False 的数量
}
```

### 2.2 数据流图

```
loader.get_daily()
  │
  │  df  ↓
  ├──────────────────────────────────────────────────────────┐
  │                                                          │
  │  determine_always_in(df)          detect_key_levels(df)  │
  │    │                                 │                   │
  │    │ ai_result                       │ levels[]          │
  │    ▼                                 ▼                   │
  │  get_trend_filter()          detect_pinbar(df,           │
  │    │                          key_levels=levels)         │
  │    │                          │                          │
  │    │ trend_filter              │ df + signal columns     │
  │    ▼                          ▼                          │
  │  └─────────→  Signal Filter ←───────────┘               │
  │                    │                                     │
  │                    │ signals[]                           │
  │                    ▼                                     │
  │              pipeline_result                             │
  └──────────────────────────────────────────────────────────┘
```

---

## 3. Module Interface Contracts

### 3.1 Always-In → Downstream (Signal Filtering)

| 项目 | 内容 |
|------|------|
| **输出模块** | `state.market_state.determine_always_in()` |
| **消费步骤** | Step 5 — 信号过滤 |
| **消费模块** | Pipeline 的信号过滤逻辑 (在 `run_single_stock` 中) |

**消费方式:**

```python
# pipeline.py 信号过滤逻辑 (伪代码)
def _filter_signal(signal_dir: str, trend_filter: str, confidence: float) -> bool:
    """信号是否与 Always-In 方向对齐?"""
    if trend_filter == "neutral":
        return True  # 震荡市允许双向, 但信号需额外确认
    if trend_filter == "long_only" and signal_dir == "bullish":
        return True
    if trend_filter == "short_only" and signal_dir == "bearish":
        return True
    return False
```

**关键消费字段:**

| 字段 | 类型 | 何时使用 | 对下游的影响 |
|------|------|---------|-------------|
| `direction` | str | 信号方向判定 | "oscillating" 时不过滤, 但 score 打折 |
| `confidence` | float | 过滤严格度调节 | > 0.5 严格过滤, <= 0.5 宽松 |
| `trend_filter` | str | 主过滤依据 | long_only/short_only/neutral 直接决定信号是否对齐 |
| `dimensions` | dict | 调试 / 审计 | 下游不消费, 仅透传查看 |

**置信度与过滤严格度的映射:**

```
confidence > 0.7  →  严格过滤: 信号方向必须与 Always-In 一致
0.3 < confidence ≤ 0.7  →  标准过滤: 冲突信号标记但不丢弃
confidence ≤ 0.3  →  宽松: 所有信号通过, 但 score 乘 0.5
```

**非对齐信号的处理规则:**

```
非对齐信号不被丢弃, 而是标记 always_in_aligned=False。
目的是:
  1. 允许复盘查看"如果忽略 Always-In 会怎样"
  2. 为 P2 反馈回路提供训练数据 (当前 Always-In 判错的案例)
  3. 不遗漏可能的反转信号 (趋势末期的 Pinbar 反转往往是真信号)
```

### 3.2 Key Levels → Pinbar

| 项目 | 内容 |
|------|------|
| **输出模块** | `patterns.key_levels.detect_key_levels()` |
| **消费步骤** | Step 4 — Pinbar 检测 |
| **消费模块** | `patterns.pinbar.detect_pinbar()` |

**调用方式:**

```python
# pipeline.py 中调用 (pipeline 负责桥接)
levels, kl_meta = detect_key_levels(df)
df = detect_pinbar(df, key_levels=levels)
```

Pinbar 模块接收 `key_levels` 参数后, 在检测到 Pinbar 信号时额外计算:
- `near_key_level`: bool — 该 Pinbar 的主影线尖端是否触及或非常接近某个关键位
- `key_level_distance`: float — 距最近关键位的距离 (以 ATR 倍数计)

**关键消费字段:**

| KeyLevel 字段 | 类型 | Pinbar 如何使用 |
|---------------|------|----------------|
| `level_price` | float | 计算 signal K 线距关键位的距离 |
| `price_min` | float | 判断信号 K 线是否在关键位簇的范围内 |
| `price_max` | float | 同上 |
| `formation_type` | str | 标记信号 K 线靠近的是 swing_high_cluster 还是 swing_low_cluster |

**Pinbar + KeyLevel 组合的信号增强规则:**

```
Bullish Pinbar + near_key_level = True:
  → 更可靠的底部拒绝信号 (关键位支撑 + 长下影线)

Bearish Pinbar + near_key_level = True:
  → 更可靠的顶部拒绝信号 (关键位阻力 + 长上影线)

Bullish Pinbar + ALWAYS_IN = bullish + near_key_level:
  → 三重确认: 方向一致 + 关键位支撑 + K 线拒绝形态
  → 最高优先级信号

Bearish Pinbar + key_level_distance >> ATR:
  → 远离关键位的 Pinbar 信号较弱 (无支撑/阻力配合)
```

### 3.3 Pinbar → Output

| 项目 | 内容 |
|------|------|
| **输出模块** | `patterns.pinbar.detect_pinbar()` |
| **消费步骤** | Step 5-6 — 信号生成和输出 |
| **消费模块** | Pipeline 的信号组装逻辑 |

**消费方式:**

```python
# pipeline.py 信号组装伪代码
for idx, row in signal_rows.iterrows():
    sig_dir = "bullish" if row["signal"] == 1 else "bearish"

    signals.append({
        "date": row["trade_date"],
        "direction": sig_dir,
        "strength": row["pinbar_strength"],
        "near_key_level": row.get("near_key_level", False),
        "key_level_distance": row.get("key_level_distance", None),
        "always_in_aligned": _check_alignment(sig_dir, trend_filter, confidence),
        "entry_trigger": row["high"] if row["signal"] == 1 else row["low"],
    })
```

**关键消费字段:**

| Pinbar 输出列 | 类型 | 映射到 pipeline_result 的字段 |
|---------------|------|-------------------------------|
| `signal` | int | `direction` (1→bullish, -1→bearish) |
| `pinbar_strength` | str | `signals[].strength` |
| `near_key_level` | bool | `signals[].near_key_level` (由 Pinbar 填入) |
| `key_level_distance` | float | `signals[].key_level_distance` |
| `trade_date` | str | `signals[].date` |
| `high` / `low` | float | `entry_trigger` |

---

## 4. Integration in pipeline.py

### 4.1 完整实现: `run_single_stock()`

```python
"""
D:\ClaudeWorkspace\price_action_trading\pipeline.py

P1 核心管线 — 单只股票全部分析流程。
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from price_action_trading.data.loader import get_daily
from price_action_trading.state.market_state import (
    determine_always_in,
    get_trend_filter,
)
from price_action_trading.patterns.key_levels import (
    detect_key_levels,
    key_levels_summary,
)
from price_action_trading.patterns.pinbar import detect_pinbar


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
        lookback_days: 回看天数 (含 1.5 倍余量, 实际 K 线数约 lookback_days)
        min_bars:      最小有效 K 线数

    Returns:
        pipeline_result dict (see §2.1)

    Error handling:
        - 数据不足 → 返回 {"ts_code": ts_code, "skip": True, "skip_reason": "..."}
        - 单模块崩溃 → 该模块字段为 None/空, 其他模块继续 (graceful degradation)
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

    # 确保时间升序 (loader 通常已保证, 但防御性检查)
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

    # ── Step 4: Pinbar 检测 (携带 key_levels 上下文) ──
    df = _safe_call(
        "pinbar",
        detect_pinbar,
        df,
        key_levels=levels,
        default=df,  # 即使失败也返回原 df (无信号列)
    )

    # 确保信号列存在 (模块崩溃时 fallback df 可能没有)
    if "signal" not in df.columns:
        df["signal"] = 0
        df["signal_type"] = ""
        df["pinbar_strength"] = ""
        df["near_key_level"] = False
        df["key_level_distance"] = None

    # ── Step 5: 信号过滤与组合 ──
    signals = _build_signals(df, trend_filter, ai_result["confidence"])

    # ── Step 6: 组装输出 ──
    total = len(signals)
    aligned = sum(1 for s in signals if s["always_in_aligned"])

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

        "signals": signals,
        "total_signals": total,
        "aligned_signals": aligned,
        "conflicting_signals": total - aligned,
    }


# ═══════════════════════════════════════════
#   Internal Helpers
# ═══════════════════════════════════════════


def _skip_result(ts_code: str, reason: str, detail: str = "") -> dict:
    """数据不足/加载失败时的跳过结果"""
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
        "signals": [],
        "total_signals": 0,
        "aligned_signals": 0,
        "conflicting_signals": 0,
    }


def _safe_call(module_name: str, func, *args, default=None, **kwargs):
    """安全调用模块函数, 崩溃时返回默认值并打印警告"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[WARN] {module_name} module failed: {e}")
        return default


def _detect_key_levels_wrapper(df: pd.DataFrame) -> tuple:
    """包装 detect_key_levels 以统一返回格式 (list, dict)"""
    from price_action_trading.patterns.key_levels import detect_key_levels
    levels = detect_key_levels(df)
    swing_count = sum(lvl.swing_count for lvl in levels)
    meta = {
        "swing_count": swing_count,
        "swing_density": round(swing_count / max(len(df), 1), 4),
        "quality_warning": _key_levels_quality_warning(levels, len(df)),
    }
    return levels, meta


def _key_levels_quality_warning(levels: list, n_bars: int) -> str:
    """关键位质量警告"""
    if len(levels) == 0:
        return "no_levels_detected"
    if len(levels) < 2:
        return "too_few_levels"
    return ""


def _build_signals(
    df: pd.DataFrame,
    trend_filter: str,
    confidence: float,
    max_signals: int = 10,
) -> list:
    """从 Pinbar 结果构建信号列表 (Step 4→5)"""
    if "signal" not in df.columns:
        return []

    signals = []
    signal_rows = df[df["signal"] != 0].tail(max_signals)

    for idx, row in signal_rows.iterrows():
        sig_dir = "bullish" if row["signal"] == 1 else "bearish"

        sig = {
            "date": str(row.get("trade_date", "")),
            "direction": sig_dir,
            "strength": row.get("pinbar_strength", ""),
            "entry_trigger": float(
                row["high"] if row["signal"] == 1 else row["low"]
            ),
            "stop_loss": None,   # 策略层填充
            "near_key_level": bool(row.get("near_key_level", False)),
            "key_level_distance": row.get("key_level_distance", None),
            "always_in_aligned": _is_aligned(sig_dir, trend_filter, confidence),
            "score": 0.0,        # 默认 0, P2 加权评分
        }
        signals.append(sig)

    return signals


def _is_aligned(direction: str, trend_filter: str, confidence: float) -> bool:
    """检查信号方向与 Always-In 是否对齐"""
    if trend_filter == "neutral":
        return True
    if confidence <= 0.3:
        return True  # 低置信度时不过滤
    if confidence > 0.7:
        # 高置信度: 严格过滤
        if trend_filter == "long_only" and direction == "bullish":
            return True
        if trend_filter == "short_only" and direction == "bearish":
            return True
        return False
    # 中等置信度
    if trend_filter == "long_only" and direction == "bullish":
        return True
    if trend_filter == "short_only" and direction == "bearish":
        return True
    # 冲突但置信度不是极高: 标记非对齐但不丢弃
    return False
```

### 4.2 批量扫描

```python
def run_batch(ts_codes: list[str], date: str) -> list[dict]:
    """批量扫描多只股票

    Args:
        ts_codes: 股票代码列表
        date:     分析日期 YYYYMMDD

    Returns:
        list[pipeline_result]
    """
    results = []
    for code in ts_codes:
        result = run_single_stock(code, date)
        results.append(result)
        # 可选: 打印进度
        if not result["skip"]:
            n_sig = result["total_signals"]
            n_ali = result["aligned_signals"]
            print(f"  {code}: {n_sig} signals ({n_ali} aligned)")
    return results


def run_watchlist(date: str) -> list[dict]:
    """扫描监控列表 (读取外部 watchlist 文件)"""
    # TODO: 从 config/watchlist.csv 读取
    # 当前硬编码测试股
    watchlist = [
        "000001.SZ",   # 平安银行
        "600519.SH",   # 贵州茅台
        "300750.SZ",   # 宁德时代
    ]
    return run_batch(watchlist, date)
```

### 4.3 main() 集成

```python
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
        # 筛选有信号的股票
        active = [r for r in results if not r["skip"] and r["total_signals"] > 0]
        print(f"\n[PAT] 完成: {len(active)}/{len(results)} 只有信号")
        for r in active:
            print(f"  {r['ts_code']}: {r['total_signals']} signals "
                  f"({r['aligned_signals']} aligned)  "
                  f"AI={r['always_in']['direction']}")


def _print_result(result: dict):
    """打印单股结果摘要"""
    if result["skip"]:
        print(f"  跳过: {result['skip_reason']}")
        return

    ai = result["always_in"]
    kl = result["key_levels"]
    print(f"  Always-In: {ai['direction']} "
          f"(conf={ai['confidence']:.2f}, filter={ai['trend_filter']})")
    print(f"  Key Levels: {len(kl['levels'])} levels detected")
    if kl["summary"]:
        print(kl["summary"])
    print(f"  Signals: {result['total_signals']} total, "
          f"{result['aligned_signals']} aligned")
    for sig in result["signals"]:
        align = "✓" if sig["always_in_aligned"] else "✗"
        kl_mark = " [KL]" if sig["near_key_level"] else ""
        print(f"    {sig['date']} {sig['direction']:>7} "
              f"{sig['strength']:>6}{kl_mark} "
              f"trigger={sig['entry_trigger']:.2f}  {align}")
```

---

## 5. Pipeline Coordination Rules

### 5.1 执行顺序 (不可违反)

| 规则 | 说明 | 违反后果 |
|------|------|---------|
| **R1: Always-In first** | Step 2 必须在 Step 5 之前完成 — direction context 必须可用 | 信号缺乏方向背景, 无法过滤 |
| **R2: Key Levels before Pinbar** | Step 3 必须在 Step 4 之前完成 — levels 必须传到 Pinbar | Pinbar 无法标记 near_key_level |
| **R3: Pinbar before filtering** | Step 4 必须在 Step 5 之前完成 — 信号必须先检测再过滤 | 无信号可过滤 |

### 5.2 信号处理规则

| 规则 | 说明 |
|------|------|
| **R4: 过滤但不删除** | 非对齐信号 still reported, `always_in_aligned=False`, 不丢弃 |
| **R5: 对齐=有效** | 一个信号被视为 "valid" 的前提是 `always_in_aligned=True` |
| **R6: 最少 K 线数** | `len(df) < min_bars(30)` → 跳过所有后续步骤, 返回 skip result |
| **R7: 数据不足跳过链** | Step 1 数据不足 → Step 2-6 全部跳过, 不尝试部分运行 |

### 5.3 错误处理规则

| 规则 | 说明 |
|------|------|
| **R8: 错误隔离** | 单个模块崩溃不阻断整个管线。该模块字段为 None/空列表, 其余模块继续 |
| **R9: 降级优先于崩溃** | `_safe_call` 包装所有模块调用, 失败时返回默认值 + 打印警告 |
| **R10: 警告可追溯** | 模块失败时打印 `[WARN] <module_name> failed: <reason>` |

### 5.4 数据完整性规则

| 规则 | 说明 |
|------|------|
| **R11: 共享 df 引用** | Steps 2-4 操作同一个 df 对象 (Pinbar 会追加列, 不影响 Key Levels/Always-In 的只读使用) |
| **R12: 时间升序保证** | df 进入管线前按 `trade_date` 升序排列 (loader 负责, pipeline 双重保证) |
| **R13: 列不存在保护** | Pinbar 崩溃导致 `signal` 列不存在时, `_build_signals` 返回空列表 |

### 5.5 规则优先级

```
R6 (数据不足跳过) > R4 (过滤不删除) > R8 (错误隔离) > R1-R3 (执行顺序) > R11-R13 (数据完整性)
```

---

## 6. Future Extensions (P2)

### 6.1 P1.2b Polarity Switching

**变化范围:** 仅限于 `key_levels` 模块内部和输出层。

| 组件 | 变化 |
|------|------|
| `KeyLevel` dataclass | `polarity_flips` 字段从空列表变为有数据 |
| `key_levels.detect_key_levels()` | 新增 `track_polarity_flips=True` 参数, 开启极性追踪 |
| `pipeline_result.key_levels` | 每个 KeyLevel 的 `polarity_flips` 携带历史记录 |
| `pipeline_result.signals[]` | 新增 `polarity_flip_nearby: bool` 字段 (信号附近有极性切换) |

**协议变化:**
```
No structural change to the pipeline protocol.
Polarity data flows through the existing key_levels channel.
```

### 6.2 P1.2c Fakeout Detection

**变化范围:** 新增信号类型, 需扩展 signals[] 结构。

| 组件 | 变化 |
|------|------|
| `key_levels.detect_key_levels()` | 新增 `detect_fakeout=True` 参数 |
| `pipeline_result.signals[].type` | 新增值 `"fakeout_bullish"` / `"fakeout_bearish"` |
| `pipeline_result.fakeout_signals` | 新增顶层字段: 独立存放假突破信号 (与 Pinbar 信号并列) |

**协议变化:**
```python
# P2 signals[] 扩展
pipeline_result["signals"][i] = {
    ...,  # P1 fields
    "type": "pinbar",               # "pinbar" | "fakeout_bullish" | "fakeout_bearish"
    "fakeout_confidence": None,     # float if type=fakeout
    "polarity_flip_nearby": False,  # P1.2b
}
```

### 6.3 P2.1 Always-In 5-dim

**变化范围:** `always_in` 模块内部, 输出层扩展。

| 组件 | 变化 |
|------|------|
| `determine_always_in()` | 从 3 维 → 5 维 (新增 momentum + retracement depth) |
| `pipeline_result.always_in` | 结构不变, `dimensions` 中新增 2 个条目 |
| `trend_filter` | 从 3 档 → 5 档 (新增 strongly_long / strongly_short) |

### 6.4 P2.4 Best Trade

**变化范围:** 信号评分逻辑。

| 组件 | 变化 |
|------|------|
| `pipeline_result.signals[].score` | 从默认 0.0 变为多条件加权评分 |
| 新增: `_score_signal()` | 综合 Pinbar 强度 + Key Level 靠近度 + Always-In 对齐度 + ... |

**评分函数原型 (P2):**

```python
def _score_signal(
    sig: dict,
    ai_confidence: float,
    levels_quality: str,
) -> float:
    """P2.4: 多条件综合评分

    Components:
      - Pinbar strength: strong=+3, normal=+1
      - Near key level: +2
      - Always-In aligned: +2
      - Always-In confidence > 0.7: +1
      - Key levels quality "good": +1
    Max: 9
    """
    score = 0.0
    if sig["strength"] == "strong":
        score += 3
    elif sig["strength"] == "normal":
        score += 1
    if sig["near_key_level"]:
        score += 2
    if sig["always_in_aligned"]:
        score += 2
    if ai_confidence > 0.7:
        score += 1
    if levels_quality == "good":
        score += 1
    return score
```

### 6.5 P1.4 2+2 Scoring (辅助权重)

| 组件 | 变化 |
|------|------|
| 新增: `scoring/pat_score.py` | 许佳聪 2+2 趋势分 + 关键位分计算 |
| `pipeline_result.signals[].score` | 2+2 评分作为权重因子, 非主过滤器 |

### 6.6 向后兼容承诺

P2 所有扩展遵守以下约束:
1. `pipeline_result` 顶层结构不删除已有字段, 只新增
2. `signals[]` 每项不删除已有字段, 只新增
3. 所有新增字段有默认值 (None/0/False), 不破坏现有消费者

---

## 7. Quick Reference

### 7.1 模块文件清单

| 模块 | 文件路径 | P1 状态 |
|------|---------|---------|
| Data Loader | `price_action_trading/data/loader.py` | 已完成 |
| Always-In | `price_action_trading/state/market_state.py` | 待实现 |
| Key Levels | `price_action_trading/patterns/key_levels.py` | 待实现 |
| Pinbar | `price_action_trading/patterns/pinbar.py` | 待实现 |
| Pipeline | `price_action_trading/pipeline.py` | 待实现 (本文件定义) |

### 7.2 函数调用树

```
pipeline.main()
  └── run_single_stock(ts_code, date)
        ├── get_daily(ts_code, start, date)           # data/loader.py
        ├── determine_always_in(df)                   # state/market_state.py
        │     └── get_trend_filter(ai)                # state/market_state.py
        ├── detect_key_levels(df)                     # patterns/key_levels.py
        │     └── key_levels_summary(levels, price)   # patterns/key_levels.py
        ├── detect_pinbar(df, key_levels=levels)      # patterns/pinbar.py
        ├── _build_signals(df, trend_filter, conf)    # pipeline.py internal
        └── → pipeline_result
```

### 7.3 验收标准

| 标准 | 条件 |
|------|------|
| 运行 | `run_single_stock("000001.SZ", "20240115")` 返回完整 pipeline_result |
| 降级 | 去掉 Pinbar 模块, pipeline 仍返回 Always-In + Key Levels 部分 |
| 跳过 | `run_single_stock("000001.SZ", "20240115", lookback_days=5)` → skip=True |
| 输出断言 | `run_single_stock` 返回结果中 signals[] 每个元素含全部 9 个字段 |

---

> 文档版本: v1.0 | 2026-06-11
> 关联文档: `design_pinbar.md`, `design_key_levels.md`, `design_always_in.md`, `pat_mvp.md`
