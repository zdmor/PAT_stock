# PAT_stock — 价格行为交易系统

基于 **Al Brooks 价格行为学三部曲** 的 A 股交易系统。纯 K 线结构与市场状态判定，不依赖技术指标。

## 系统架构

```
六层架构: L1 数据 → L2 状态 → L3 形态 → L4 策略 → L5 风控 → L6 输出
```

### P1 篇（已实现）
| 模块 | 功能 |
|------|------|
| `state/market_state` | Always-In 5 维加权方向判定（EMA斜率/高低点结构/K线倾向/回调深度/缺口棒） |
| `patterns/key_levels` | 水平关键位检测（Swing点聚类+极性转换+假突破记录） |
| `patterns/pinbar` | Pinbar 反转形态检测（向量化实现） |
| `patterns/trap` | 陷阱识别（假突破/扫止损/高潮反转/窄区间陷阱） |
| `patterns/signal_bar` | 信号 K 线分类与评级 |
| `scoring/score` | 信号综合评分与 Top-N 筛选 |
| `pipeline` | 主管线编排 |

### P2 篇（部分实现）
- Always-In + Spike+Channel 检测
- A 股均值回复适配（reverse_sign）

### P3 篇 — 震荡区间（未实现）
### P4 篇 — 交易战术（未实现）
### M6 回测系统（未实现）

## A 股适配

- T+1 入场成功率门槛 ≥ 70%
- 涨跌停板突破确认与炸板检测
- 无做空机制下的熊市策略退避
- 散户情绪放大效应（假突破频率 1.3-1.5x）

详见 `docs/ashare_adaptation.md`。

## 快速开始

```bash
# 安装依赖
pip install tushare pandas numpy

# 设置 Tushare Token
export TUSHARE_TOKEN=your_token_here

# 单股分析
python pipeline.py --watch 000001.SZ

# 盘后批量扫描（默认 watchlist）
python pipeline.py
```

## 项目状态

| 里程碑 | 状态 | 备注 |
|--------|------|------|
| M0 知识体系+需求 | ✅ | docs/requirements.md + concept_map.md |
| M1 数据基建 | ✅ | Tushare 接口 + 缓存 + 交易日历 |
| M1.5 数据校准 | ⚠️ | IC 检验完成，thresholds.json 未输出 |
| M2 状态分类 | ✅ | Always-In + Spike+Channel |
| M3 形态识别 | ⚠️ | Pinbar/KeyLevels/Trap/SignalBar 完成，部分形态未实现 |
| M4 策略层 | ❌ | |
| M5 风控层 | ⚠️ | 交易者方程+仓位管理完成 |
| M6 回测系统 | ❌ | |
| M7 集成验证 | ⚠️ | pipeline.py 可运行 |

## 设计原则

- **价格行为第一**：不依赖任何技术指标（除 EMA20 做趋势基准）
- **可证伪的组件接口**：每个模块能回答"什么条件下你是错的"
- **倾向派驱动**：市场状态分类（吸筹/拉升/派发/震荡）优先于参数优化
- **风险前置**：交易者方程过滤每笔信号，预期值 < 0 不交易

详见 `docs/project_charter.md`。
