<!-- README_ZH_START -->
# PAT_stock｜A股价格行为研究系统

> 状态：`ACTIVE_RESEARCH_REFERENCE`  
> 默认分支：`master`  
> 角色：`PRICE_ACTION_RESEARCH`  
> README 角色：`HUMAN_ORIENTATION_ONLY / NOT_WTOS_AUTHORITY`

## 1. 仓库概述

本仓库是一套基于 **Al Brooks 价格行为学** 的 A 股研究系统，重点研究 K 线结构、市场状态、关键位、Trap、Signal Bar、Pinbar、Always-In、Spike/Channel 等价格行为要素，并通过评分、策略、风控和回测模块验证其在 A 股中的适用性。

它是独立研究参考，不是当前 WTOS Runtime、Live Authority 或自动交易执行层。

## 2. 当前状态

根据 `zdmor/Meta-System@main:REPOSITORY_REGISTRY.yaml`：

```text
class  = RESEARCH_REFERENCE
role   = PRICE_ACTION_RESEARCH
status = ACTIVE_RESEARCH_REFERENCE
```

`ACTIVE_RESEARCH_REFERENCE` 表示研究仓仍可继续用于研究，但不等于生产 Authority。

## 3. 核心研究架构

历史/当前代码结构可概括为：

```text
L1 Data
  ↓
L2 Market State
  ↓
L3 Patterns
  ↓
L4 Strategy
  ↓
L5 Risk
  ↓
L6 Output / Review / Backtest
```

README 旧记录显示 P1 已覆盖较多基础结构，P2 部分实现，后续完整策略/回测仍有未完成部分；真实实现状态以当前代码、tests 和结果为准。

## 4. 目录结构

| 路径 | 作用 |
|---|---|
| `pipeline.py` | 主研究 pipeline / 分析编排入口 |
| `run_daily.py` | 历史/研究型日运行入口 |
| `patterns/` | 价格行为形态识别 |
| `state/` | 市场状态相关逻辑 |
| `strategies/` | 策略研究 |
| `risk/` | 风险约束研究 |
| `scoring/` | 评分/置信度相关逻辑 |
| `backtest/` | 回测框架与实验 |
| `data/` | 数据访问/处理相关模块或研究数据 |
| `results/` | 研究输出/结果 |
| `reviews/` | 复核/研究评审资料 |
| `docs/` | 方法与设计文档 |
| `scripts/` | 辅助脚本 |
| `tests/` | 测试 |
| `requirements.txt` | Python 依赖 |

## 5. 关键文件

### `pipeline.py`

主分析编排入口，串联数据、状态、形态、评分、策略/风控等层。任何当前行为应以代码和 tests 验证，README 只提供导航。

### `run_daily.py`

研究型日运行入口。它的存在不表示 PAT_stock 已经是生产日任务，也不意味着其输出具有 WTOS Authority。

### `patterns/` / `state/`

是本仓最具有研究复用价值的两类区域：一个关注价格行为 pattern，一个关注市场/结构状态。若未来要迁移到其他系统，应先抽取候选方法并独立验证。

## 6. 数据与资料

本仓可能使用 Tushare 等市场数据接口。Token/真实 secret 不应提交 GitHub。数据目录、结果目录中的任何历史输出都不自动等于当前市场事实。

## 7. 使用方式

历史 README 提供过类似：

```bash
pip install tushare pandas numpy
python pipeline.py --watch 000001.SZ
python pipeline.py
```

这些是研究入口，不是生产运行保证。需要执行时应先检查 `requirements.txt`、数据源权限、代码状态和 tests。

推荐研究流程：

```text
研究问题
-> state/pattern exact module
-> pipeline / scoring / strategy
-> backtest/tests
-> review result
-> 如需晋级，迁移到真正 owner 并重新验证
```

## 8. Current / Canonical / Authority

- 跨库 role/status：`zdmor/Meta-System@main:REPOSITORY_REGISTRY.yaml`
- WTOS startup：`zdmor/WTOS@main:SYSTEM_MANIFEST.yaml`
- 当前用户侧 WTOS owner：当前 resolver 指向 `zdmor/Stock-Analysis`
- 本仓 Live Authority：`NONE`

## 9. 与其他仓库关系

PAT_stock 可以为 WTOS、A-Share Intelligence 等项目提供价格行为研究候选，但只能以 research/shadow/reference 身份进入。任何规则要变成正式业务逻辑，都必须由业务 owner 接收并完成独立验证。

## 10. 最近重要调整

### 2026-09-10｜跨库身份明确

Meta-System 将 PAT_stock 定位为 `PRICE_ACTION_RESEARCH / ACTIVE_RESEARCH_REFERENCE`。

### 2026-09-10｜README Governance 对齐

README 扩展为详细双语说明，加入目录职责、关键文件、数据/运行边界和 Current pointer。

## 11. 生命周期 / 已知限制

- 仓库允许继续研究；
- 旧进度表不作为 Current 实现证明；
- 历史结果不自动变成今天的市场事实；
- 不自动写交易；
- 方法晋级必须经过验证和 owner approval。

## 12. README 同步状态

```text
README_STANDARD = zdmor/Meta-System@main:standards/REPOSITORY_README_STANDARD.md
README_LANGUAGE_ORDER = CHINESE_THEN_ENGLISH
README_DETAIL_BASELINE = PASS
ROLE_STATUS_ALIGNED = PASS
README_SYNC = PASS_AT_THIS_COMMIT
```

<!-- README_EN_START -->
# PAT_stock | A-Share Price-Action Research System

> Status: `ACTIVE_RESEARCH_REFERENCE`  
> Default branch: `master`  
> Role: `PRICE_ACTION_RESEARCH`  
> README role: `HUMAN_ORIENTATION_ONLY / NOT_WTOS_AUTHORITY`

## 1. Repository overview

PAT_stock is an A-share research system inspired by Al Brooks price action. It studies bar structure, market state, key levels, traps, signal bars, Pinbars, Always-In, Spike/Channel behavior, scoring, strategy, risk, and backtesting.

It is an independent research reference, not current WTOS Runtime, Live Authority, or automated execution.

## 2. Current status

Meta-System classifies the repository as `RESEARCH_REFERENCE / PRICE_ACTION_RESEARCH / ACTIVE_RESEARCH_REFERENCE`. Active research status permits continued study but does not grant production authority.

## 3. Research architecture

```text
L1 Data -> L2 Market State -> L3 Patterns -> L4 Strategy -> L5 Risk -> L6 Output/Review/Backtest
```

Older README progress notes indicate substantial P1 implementation and partial P2 work, while later strategy/backtest layers remain incomplete. Actual implementation state must be verified from code, tests, and results.

## 4. Directory structure

- `pipeline.py` — main research orchestration.
- `run_daily.py` — historical/research daily runner.
- `patterns/` — price-action pattern logic.
- `state/` — market/state logic.
- `strategies/` — strategy research.
- `risk/` — risk research.
- `scoring/` — scoring/confidence logic.
- `backtest/` — backtesting experiments.
- `data/` — data access/processing or research data.
- `results/` — research outputs.
- `reviews/` — review material.
- `docs/` — design/method documentation.
- `scripts/` — support scripts.
- `tests/` — tests.
- `requirements.txt` — Python dependencies.

## 5. Key files

`pipeline.py` is the main analysis orchestrator. `run_daily.py` is a research runner, not proof of a production scheduled service. The `patterns/` and `state/` areas are especially relevant for selective research reuse, but any migration requires independent validation.

## 6. Data and assets

The repository may use market-data sources such as Tushare. Real credentials must never be committed. Historical data/results do not automatically represent current market facts.

## 7. Usage workflow

Historical commands using `pipeline.py` are research entry points only. Before execution, validate dependencies, data-source access, current code, and tests. The recommended flow is research question -> exact state/pattern module -> pipeline/scoring/strategy -> backtest/tests -> review -> explicit owner adoption if promoted.

## 8. Current / Canonical / Authority

- Cross-repository role/status: `zdmor/Meta-System@main:REPOSITORY_REGISTRY.yaml`
- WTOS startup: `zdmor/WTOS@main:SYSTEM_MANIFEST.yaml`
- Current user-facing WTOS owner: currently routed to `zdmor/Stock-Analysis`
- Live Authority here: `NONE`

## 9. Repository relationships

PAT_stock may contribute price-action research candidates to WTOS or A-Share Intelligence, but only as research/shadow/reference material. Formal business logic must be accepted and revalidated by the owning repository.

## 10. Major recent changes

On 2026-09-10 Meta-System explicitly classified PAT_stock as active price-action research reference. The README was expanded to the global detailed bilingual standard.

## 11. Lifecycle / limitations

Research may continue, but old progress tables are not implementation authority, historical results are not current facts, no broker write is implied, and promotion requires validation plus owner approval.

## 12. README sync status

```text
README_STANDARD = zdmor/Meta-System@main:standards/REPOSITORY_README_STANDARD.md
README_LANGUAGE_ORDER = CHINESE_THEN_ENGLISH
README_DETAIL_BASELINE = PASS
ROLE_STATUS_ALIGNED = PASS
README_SYNC = PASS_AT_THIS_COMMIT
```
