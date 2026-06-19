# A股适配规则

> 项目: PAT (Price Action Trading)
> 基于: Al Brooks 三部曲蒸馏笔记 §A股落地实操 + 实际交易规则
> M0 产出: ashare_adaptation.md — Brooks 体系 → A股特化规则

---

## 规则一览

| 编号 | 规则名 | 类别 | 优先级 |
|------|--------|------|:---:|
| ASH-01 | T+1 入场成功率门槛 | 制度适配 | P0 |
| ASH-02 | T+1 尾盘禁开新仓 | 制度适配 | P0 |
| ASH-03 | T+1 隔夜仓位上限 | 制度适配 | P0 |
| ASH-04 | T+1 止损放宽 | 制度适配 | P0 |
| ASH-05 | 涨停板突破确认 | 涨跌停 | P0 |
| ASH-06 | 炸板=假突破检测 | 涨跌停 | P0 |
| ASH-07 | 涨停封死≠Always-In Long 可执行 | 涨跌停 | P1 |
| ASH-08 | 跌停板锁死熔断 | 涨跌停 | P0 |
| ASH-09 | 连续涨停的Always-In降权 | 涨跌停 | P1 |
| ASH-10 | 连板股特殊行为模式 | 涨跌停 | P1 |
| ASH-11 | 春节/国庆休市持仓限制 | 日历适配 | P1 |
| ASH-12 | 月末/季末调仓效应 | 日历适配 | P2 |
| ASH-13 | 最小价格变动单位处理 | 执行适配 | P2 |
| ASH-14 | 印花税/佣金计入 | 成本适配 | P1 |
| ASH-15 | 涨跌停板作为天然区间边界 | 方法论适配 | P1 |
| ASH-16 | A股散户情绪放大效应 | 方法论适配 | P1 |
| ASH-17 | 无做空机制下的熊市策略退避 | 方法论适配 | P0 |
| ASH-18 | 新股/次新股排除 | 选股适配 | P1 |
| ASH-19 | ST/退市股排除 | 选股适配 | P0 |
| ASH-20 | 全市场扫描分层策略 | 性能适配 | P1 |

---

## 一、T+1 制度适配 (P0)

### ASH-01: T+1 入场成功率门槛

**问题：** Brooks 原体系允许入场后数分钟内止损。A股当日买入后无法当日卖出，错误入场的代价远高于美股。

**规则：**
```
def t_plus_1_entry_filter(signal: dict) -> bool:
    """T+1 入场过滤
    
    入场条件（必须同时满足）:
      1. 信号置信度 >= 70%（高于原始的 60%）
      2. 信号K线质量 = A级 或 B级（C级直接拒绝）
      3. Always-In 方向 = 信号方向（方向一致）
      4. 多时间框架共振通过（日周不冲突）
      5. 趋势强度 >= "AA"（中等趋势以上）
    
    返回值: True=允许入场, False=禁止
    """
```

### ASH-02: T+1 尾盘禁开新仓

**问题：** 14:30 后开仓意味着到次日开盘至少有 15.5 小时的隔夜风险。T+1 下无法在尾盘调整持仓。

**规则：**
```
def t_plus_1_late_entry_ban(current_time: str) -> bool:
    """尾盘禁开新仓
    
    逻辑:
      - 若 current_time >= "14:30:00" → 禁止所有新开仓
      - 若 current_time >= "14:00:00" AND signal_confidence < 85% → 禁止
      - 盘中已有持仓的止损调整不受限制
    
    返回值: True=禁止, False=允许
    """
```

### ASH-03: T+1 隔夜仓位上限

**问题：** Brooks 原体系没有隔夜仓位限制。A股隔夜风险包括：次日大幅低开、利空消息、外盘大跌。

**规则：**
```
def t_plus_1_overnight_limit(current_position_pct: float, 
                              market_state: str) -> float:
    """隔夜仓位上限
    
    逻辑:
      - 趋势向上日: 单票上限 20%, 总仓上限 60%
      - 区间日:     单票上限 15%, 总仓上限 40%
      - 趋势向下日: 单票上限 10%, 总仓上限 20%
      - 周五/节前:  在以上基础上再 × 0.7
    
    返回值: 允许的仓位上限(%)
    """
```

### ASH-04: T+1 止损放宽

**问题：** Brooks 原止损"信号K线外 1 tick"。A股 T+1 下无法当日止损 → 必须给次日低开留空间。

**规则：**
```
def t_plus_1_stop_adjustment(stop_price: float, entry_price: float) -> float:
    """T+1 止损放宽
    
    逻辑:
      - 日线信号K线外: 放宽到 2-3%（非原 1%）
      - 实际止损价 = max(技术止损价 × 1.5, entry_price × 0.95)
      - 单笔最大风险 = 账户的 2%（与原版一致）
    
    返回值: 调整后的止损价
    """
```

---

## 二、涨跌停板适配 (P0)

### ASH-05: 涨停板突破确认

**问题：** A股涨停板是一个强制性的"突破成功"信号，但次日的 follow-through 决定了真假。

**规则：**
```
def limit_up_breakout_confirmation(stock: str, today: str) -> str:
    """涨停板突破确认
    
    信号质量评级:
      "STRONG":  早盘封板(10:00前) + 封单量 > 前日成交量 20% + 未开板
      "MEDIUM":  午盘封板(10:00-14:00) + 封单量 > 前日成交量 10%
      "WEAK":    尾盘封板(14:00后) 或 封单量 < 前日成交量 5%
      "FAILED":  炸板(封板后被打开)
    
    入场规则:
      - STRONG: 次日开盘若高开 → Signal Bar 确认后可入场
      - MEDIUM: 等次日确认K线收盘后再决定
      - WEAK/FAILED: 不做多
    """
```

### ASH-06: 炸板=假突破检测

**问题：** 涨停板被打开（炸板）是 A股特有的假突破形态，等价于 Brooks 的 Bull Trap。

**规则：**
```
def detect_zha_ban(stock: str, df: pd.DataFrame) -> Optional[dict]:
    """炸板检测
    
    触发条件:
      1. 当日盘中触及涨停价 (price == limit_up_price)
      2. 收盘时打开涨停 (close < limit_up_price)
      3. 若 封板时段 > 30分钟 后打开 → "TRAP_STRONG"
      4. 若 封板时段 < 30分钟 → "TRAP_WEAK"
    
    输出: {trap_direction: "BEAR", strength: "STRONG"/"WEAK", 
           trap_bar: 封板K线/开板K线}
    
    策略信号: 炸板强陷阱 → 次日如果低开，为强熊信号
    """
```

### ASH-07: 涨停封死≠Always-In Long 可执行

**问题：** 涨停封死时，Always-In 给出"LONG"信号，但实际无法买入。这会导致 Always-In 统计偏差和策略信号失真。

**规则：**
```
def limit_up_always_in_adjust(always_in: str, is_limit_up_locked: bool) -> str:
    """涨停封死时 Always-In 调整
    
    逻辑:
      - 涨停封死 AND Always-In = LONG → Always-In = None（不可执行）
      - 跌停封死 AND Always-In = SHORT → 同理
      - 此调整仅影响策略信号生成，不影响 Always-In 统计（统计分离）
    """
```

### ASH-08: 跌停板锁死熔断

**问题：** 跌停封死时无法止损，违反 Brooks 第一层风控"任何时候都能止损"。

**规则：**
```
def limit_down_freeze_abort(holding: dict, df: pd.DataFrame) -> str:
    """跌停板锁死熔断
    
    逻辑:
      - 持仓股票连续 2 天跌停封死 → 标记 "CRITICAL"
      - 总持仓中 > 30% 出现跌停锁死 → 熔断，停止一切新开仓
      - 单个跌停锁死: 不计入正常止损统计，标记为 "不可控损失"
    
    返回值: "NORMAL" / "WARN" / "CRITICAL" / "MELTDOWN"
    """
```

### ASH-09: 连续涨停的Always-In降权

**问题：** 连续涨停时 5个 Always-In 维度全部给出强牛信号，但封板后无流动性无法交易。

**规则：**
```
def consecutive_limit_up_adjust(always_in_score: float, 
                                 consecutive_days: int) -> float:
    """连续涨停 Always-In 降权
    
    逻辑:
      - N板涨停后: Always-In 得分 × (1 / (N+1))
      - 原因: 封板天数越多，可交易性越低
      - 3板以上: Always-In 强制设为 None（无参与价值）
    """
```

### ASH-10: 连板股特殊行为模式

**问题：** A股涨停板生态中有"一字板/换手板/烂板"等独特模式，Brooks 原体系不覆盖。

**规则：**
```
def lianban_pattern_detect(df: pd.DataFrame) -> str:
    """连板股行为模式
    
    分类:
      "ONE_LINE":   一字板（开盘即涨停，全天不打开）
      "HUANSHOU":   换手板（封板后被打开再封，伴随巨量换手）
      "LAN":        烂板（多次开板，收盘勉强封住）
      "ZHA":        炸板（封板失败，收盘未封住）
    
    策略:
      - 一字板: 等第一个回调日（至少跌 3%+ 且不跌停）再入场
      - 换手板: 次日高开 2%+ 则跟随，低于 2% 则警惕
      - 烂板/炸板: 不追，等充分回调（>5%）后再评估
    """
```

---

## 三、日历与休市适配

### ASH-11: 春节/国庆休市持仓限制

**问题：** 沪深交易所每年休市约 115天，春节和国庆各有 7天休市。长休市前持仓面临巨大不可控风险。

**规则：**
```
def pre_holiday_position_check(date: str) -> dict:
    """节前持仓检查
    
    逻辑:
      - 休市 >= 5天: 提前 2 个交易日降低仓位至 30% 以下
      - 休市 >= 7天: 提前 2 个交易日降低仓位至 15% 以下
      - 休市前最后交易日: 停止一切新开仓
    
    休市日历: 硬编码 2025-2027 春节/国庆日期
    """
```

### ASH-12: 月末/季末调仓效应

**问题：** A股公募基金在月末/季末有调仓需求，可能导致 Brooks 的信号在月末失真。

**规则：**
```
def month_end_adjust(date: str) -> float:
    """月末调仓效应
    
    逻辑:
      - 每月最后 3 个交易日: 信号置信度 × 0.85
      - 每季最后 5 个交易日: 信号置信度 × 0.75
      - 原因: 机构调仓产生非技术性交易，Brooks 形态可靠性下降
    """
```

---

## 四、执行与成本适配

### ASH-13: 最小价格变动单位处理

**问题：** A股最小价格变动单位依赖价格区间（非固定 1 tick），止损/入场价计算需取整。

**规则：**
```
def tick_size(price: float) -> float:
    """A股最小变动单位
    
    逻辑:
      - 价格 <  1元: tick = 0.001
      - 价格 1-10元: tick = 0.01
      - 价格 >= 10元: tick = 0.01 (实际)
    """

def round_to_tick(price: float) -> float:
    """价格取整到最小变动单位 """
```

### ASH-14: 印花税/佣金计入

**问题：** Brooks 原书未考虑税费，但 A股卖出时征收 0.05% 印花税 + 佣金。

**规则：**
```
def commission_cost(buy_price: float, sell_price: float, 
                     shares: int) -> dict:
    """税费计算
    
    费用:
      - 买入: 佣金 0.025%（最低 5元）
      - 卖出: 佣金 0.025% + 印花税 0.05%
      - 合计: 约 0.1% 双向成本
    
    计算: cost = buy_price * shares * 0.00025 + sell_price * shares * 0.00075
    """
```

---

## 五、方法论 A 股特化适配

### ASH-15: 涨跌停板作为天然区间边界

**问题：** Brooks 原体系区间边界需要从 Swing Point 中位数计算，A股涨跌停价本身就是强制边界。

**规则：**
```
def ashare_range_boundary(stock: str, df: pd.DataFrame) -> dict:
    """A股区间边界增强
    
    逻辑:
      - 合并自动识别的区间边界 + 涨停价/跌停价
      - 若区间上轨距离涨停价 < 3% → 上轨 = 涨停价
      - 若区间下轨距离跌停价 < 3% → 下轨 = 跌停价
      - 涨跌停价边界的突破判定比普通边界严格 50%
    
    原因: 停板价是强制性的, 穿越它的概率远低于技术性边界
    """
```

### ASH-16: A股散户情绪放大效应

**问题：** A股散户占比远高于美股，情绪化交易更严重。Brooks 的"陷阱"在 A股频率更高、振幅更大。

**规则：**
```
def retail_amplification_adjust(pattern_confidence: float, 
                                 pattern_type: str) -> float:
    """散户情绪放大调整
    
    逻辑:
      - 假突破/陷阱类形态: 置信度 × 1.2（频率更高，信号更可靠）
      - 反转形态: 间隔要求 + 20%（更多假反转）
      - 趋势跟随: 趋势确认所需 K 线数 + 20%（噪音更大）
    
    原因: A股散户驱动的假突破频率是美股的 1.3-1.5 倍
    """
```

### ASH-17: 无做空机制下的熊市策略退避

**问题：** Brooks 原书有完整的沽空策略（熊趋势中的 Low 1/2 做空）。A股无做空机制 → 熊市策略只能用于空仓避险，不能反向获利。

**规则：**
```
def bear_market_adapt(always_in: str, market_state: str) -> str:
    """熊市策略退避
    
    逻辑:
      - Always-In = SHORT AND 无融券资格 → "EMPTY"（空仓）
      - "EMPTY" = 不生成任何买入信号，全部现金等待
      - 若持有融券账户: 可启用 Low 1/2 做空策略（但仓位上限 10%）
    """
```

---

## 六、选股适配

### ASH-18: 新股/次新股排除

**问题：** Brooks 方法论依赖至少 20+ 根 K 线的历史结构。新股无历史 → 无法做 Always-In 判定。

**规则：**
```
def exclude_new_stocks(stock: str, date: str) -> bool:
    """新股排除
    
    逻辑:
      - list_date + 60天 < date → 可纳入
      - 否则: 无法计算 Always-In / EMA20 / Swing Point, 排除
    
    原因: M1 验收标准的需求，详见 project_charter.md
    """
```

### ASH-19: ST/退市股排除

**规则：**
```
def exclude_st_stocks(name: str) -> bool:
    """ST/退市股排除
    
    逻辑:
      - name 包含 "ST" 或 "退" → 排除
      - 原因: Brooks 价格行为学假设市场参与者是理性的，ST 股流动性差/信息不对称严重
    """
```

---

## 七、性能适配

### ASH-20: 全市场扫描分层策略

**问题：** 4000+ 只股票的全管线穿透在 5 分钟目标下需要分层策略。

**规则：**
```
def two_pass_scan_strategy():
    """两层扫描策略
    
    第一层 (粗筛, 覆盖率 100%):
      - 只执行 Always-In 判定 + 趋势强度（每只 < 0.05s）
      - 筛选条件: Always-In ≠ NONE AND trend_strength >= "AA"
      - 预期: 保留 10-15% 候选（400-600 只）
    
    第二层 (精筛, 覆盖率 候选池):
      - 执行完整 M2+M3+M4+M5 管线
      - 每只 < 0.3s × 600 = 180s
      - 总时间: 第一层 200s + 第二层 180s ≈ 6 分钟
    """
```

---

_规则数量: 20 条。全部可代码化，无不明确的规范用语。_
