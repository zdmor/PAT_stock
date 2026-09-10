<!-- README_ZH_START -->
# PAT_stock｜价格行为研究系统

> 当前跨库定位：`PRICE_ACTION_RESEARCH / ACTIVE_RESEARCH_REFERENCE`

基于 **Al Brooks 价格行为学三部曲** 的 A 股研究系统。核心关注 K 线结构、市场状态、关键位、陷阱与信号 K 线。

## 系统架构

`L1 数据 → L2 状态 → L3 形态 → L4 策略 → L5 风控 → L6 输出`

### 当前历史实现概况

- P1：市场状态、关键位、Pinbar、Trap、Signal Bar、评分与主管线已实现；
- P2：Always-In + Spike/Channel 部分实现；
- P3/P4、完整回测仍有未实现部分；
- 数据/代码细节以仓库实际文件为准，不以 README 的旧进度表代替代码事实。

## 快速开始

```bash
pip install tushare pandas numpy
export TUSHARE_TOKEN=your_token_here
python pipeline.py --watch 000001.SZ
python pipeline.py
```

## 当前治理边界

本仓库是**独立研究参考**，不是当前 WTOS Runtime、Live Authority 或自动交易执行层。可用于未来价格行为/M5研究，但任何晋级必须经过独立验证和明确批准。

当前用户侧 WTOS 主线：`zdmor/Stock-Analysis`。所有 WTOS 任务仍先读 `zdmor/WTOS@main:SYSTEM_MANIFEST.yaml`。

README 只是人类导航；跨库角色以 `zdmor/Meta-System@main:REPOSITORY_REGISTRY.yaml` 为准。

<!-- README_EN_START -->
# PAT_stock | Price-Action Research System

> Current portfolio role: `PRICE_ACTION_RESEARCH / ACTIVE_RESEARCH_REFERENCE`

This repository is an A-share price-action research system inspired by Al Brooks, focusing on bar structure, market state, key levels, traps, and signal bars.

## Architecture

`L1 Data → L2 State → L3 Patterns → L4 Strategy → L5 Risk → L6 Output`

### Historical implementation snapshot

- P1 implements market state, key levels, Pinbar, traps, signal bars, scoring, and the main pipeline;
- P2 partially implements Always-In plus Spike/Channel logic;
- later strategy/backtest layers remain incomplete;
- actual code is authoritative for implementation state; this README is not a substitute for code evidence.

## Quick start

```bash
pip install tushare pandas numpy
export TUSHARE_TOKEN=your_token_here
python pipeline.py --watch 000001.SZ
python pipeline.py
```

## Current governance boundary

This repository is an **independent research reference**, not the current WTOS Runtime, Live Authority, or automated execution layer. Price-action ideas may support future research, but promotion requires independent validation and explicit approval.

The current user-facing WTOS mainline is `zdmor/Stock-Analysis`. Every WTOS task still starts from `zdmor/WTOS@main:SYSTEM_MANIFEST.yaml`.

README is human orientation only. Cross-repository role classification is owned by `zdmor/Meta-System@main:REPOSITORY_REGISTRY.yaml`.
