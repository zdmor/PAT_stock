# 价格行为学 — 概念↔函数映射表

> **冻结状态：** CRD-01 | M1.5 校准完成, 2026-06-14 已冻结。后续变更须经审查流程。
>
> 项目: PAT (Price Action Trading)
> 基于: Al Brooks 三部曲蒸馏笔记 (6272行) + philosophy_deep_dive.md
> M0 产出: concept_map.md — 概念提取 + 可量化等级 + 函数签名映射

---

## 统计摘要

| 域 | A级(可直接量化) | B级(需简化量化) | C级(暂不量化) | 小计 |
|----|:---:|:---:|:---:|:---:|
| 趋势域 | 18 | 14 | 12 | **44** |
| 区间域 | 10 | 9 | 4 | **23** |
| 反转域 | 15 | 13 | 7 | **35** |
| **合计** | **43** | **36** | **23** | **102** |

---

## 一、趋势域 (Trend Domain)

### A级 — 可直接量化

| # | 概念名 | 英文 | 量化条件 | 文件名 | 函数名 | 参数 | 备注 |
|---|--------|------|---------|--------|--------|------|------|
| T-A01 | 趋势性高低点结构 | Trending Highs/Lows | HH+HL=牛, LL+LH=熊 | `state/always_in.py` | `compute_hhlh_structure()` | df, n=20 | 返回 +1/0/-1 |
| T-A02 | 趋势惯性定律(80%失败) | Trend Inertia | 80%反转/突破尝试失败 | `state/market_cycle.py` | `inertia_estimate()` | reversal_type | 概率常量 |
| T-A03 | 20缺口棒 | 20 Gap Bars | 连续20+根K线不触EMA | `state/trend_strength.py` | `detect_20_gap_bars()` | df, ma_col='EMA20' | Brooks 极强趋势标志 |
| T-A04 | Spike+Channel 检测 | Spike and Channel | 连续2-5根实体>70%,重叠<20% | `state/spike_channel.py` | `detect_spike()` | df, min_bodies=2, body_pct=0.70 | 后接通道确认 |
| T-A05 | 趋势强度五级分类 | Trend Strength Spectrum | 回调<33%=强, 33-50%=中, >50%=弱 | `state/trend_strength.py` | `classify_trend_strength()` | df | 五级:AAA/AA/A/B/C |
| T-A06 | 回调深度测量 | Retracement Depth | 回调幅度/前波幅度 | `state/trend_strength.py` | `measure_retracement_depth()` | peak, trough, current | Brooks 单一最佳指标 |
| T-A07 | 测量移动 | Measured Move | 腿1高度≈腿2预期高度 | `state/spike_channel.py` | `project_measured_move()` | leg1_height, direction | 程序交易基础 |
| T-A08 | 趋势日首小时判定 | First Hour Extreme | 50%日子极端在首5棒, 90%在开盘区间 | `state/trend_day_classifier.py` | `first_hour_extreme()` | df, bar_count=5 | 趋势日分类前置 |
| T-A09 | 小回调趋势日 | Small Pullback Trend Day | 回调<日均范围20%, 最后回调=前最大150-200% | `state/trend_day_classifier.py` | `match_small_pullback()` | df, daily_range | 月1-2次 |
| T-A10 | 尖刺+通道趋势日 | Spike+Channel Trend Day | Spike(连续大实体)+通道(斜向回调) | `state/trend_day_classifier.py` | `match_spike_channel_day()` | df | 最常见趋势日 |
| T-A11 | 趋势性区间日 | Trending Trading Range Day | 开盘区间≈日均1/3-1/2, 突破后第二区间 | `state/trend_day_classifier.py` | `match_trending_range_day()` | df, avg_range | 周2-3次 |
| T-A12 | 开盘趋势日 | Trend from the Open | 开盘区间<日均25%, 全天不回头 | `state/trend_day_classifier.py` | `match_open_trend_day()` | df, avg_range | 周1-2次 |
| T-A13 | High/Low 计数 | High/Low Count | 回调中反弹高/低点顺序编号 | `patterns/high_low.py` | `count_highs()` / `count_lows()` | df, trend:str | 牛用High/熊用Low |
| T-A14 | 突破入场(Stop Entry) | Stop Entry | 突破信号棒高/低点1 tick | `strategies/trend_following.py` | `stop_entry_signal()` | signal_bar, direction, tick=0.01 | 最保守顺势入场 |
| T-A15 | 限价入场(Limit Entry) | Limit Entry | 牛前棒低点/熊前棒高点挂限价 | `strategies/trend_following.py` | `limit_entry_signal()` | df, idx, direction | 更激进 |
| T-A16 | 分批获利策略 | Scaling Out | 2倍初始风险取1/4, 3倍1/4, 剩余跟踪 | `risk/position_sizing.py` | `scale_out_plan()` | entry, stop, current | Brooks标准版 |
| T-A17 | 交易者方程式 | Trader's Equation | P(win)×Reward > P(loss)×Risk | `risk/trader_equation.py` | `trader_equation_evaluate()` | signal_quality, stop_pct, target_pct, market_mul | 核心风控门禁 |
| T-A18 | 趋势两腿法则 | Two Legs Rule | 任何攻击/投降=至少两腿 | `state/trend_strength.py` | `two_legs_rule()` | df, move_type | 通用结构规律 |

### B级 — 需简化量化

| # | 概念名 | 英文 | 简化方案 | 文件名 | 函数名 | 备注 |
|---|--------|------|---------|--------|--------|------|
| T-B01 | Always-In 方向判定 | Always-In | 5维加权评分(0.30/0.25/0.20/0.15/0.10) | `state/always_in.py` | `determine_always_in()` | >0.60=LONG, <-0.60=SHORT |
| T-B02 | 趋势棒 vs 十字星 | Trend Bar vs Doji | 实体>70%=趋势棒, <10%=Doji | `patterns/signal_bar.py` | `classify_bar()` | |
| T-B03 | 反转棒 | Reversal Bar | 尾巴>实体2倍+方向与趋势相反 | `patterns/signal_bar.py` | `detect_signal_bar()` | 99%不完美 |
| T-B04 | 两棒反转 | Two-Bar Reversal | 趋势棒+反向趋势棒,实体相当 | `patterns/signal_bar.py` | `detect_two_bar_reversal()` | 核心反转形态 |
| T-B05 | 三棒反转 | Three-Bar Reversal | 两棒趋势+中间无意义K线 | `patterns/signal_bar.py` | `detect_three_bar_reversal()` | |
| T-B06 | 趋势日七分法 | Trend Day Seven Types | 7类特征向量→模板匹配 | `state/trend_day_classifier.py` | `classify_trend_day()` | M2.5降级 |
| T-B07 | 反转日 | Reversal Day | 先一方向→反转收反向 | `state/trend_day_classifier.py` | `match_reversal_day()` | |
| T-B08 | 趋势恢复日 | Trend Resumption Day | 早盘趋势→横盘→尾盘恢复, 第二腿≈第一腿 | `state/trend_day_classifier.py` | `match_resumption_day()` | 月2-3次 |
| T-B09 | 宽通道/楼梯趋势日 | Stairs/Broad Channel | 至少三个区间+趋势性高低点 | `state/trend_day_classifier.py` | `match_stairs_day()` | |
| T-B10 | ABC 回调结构 | ABC Pullback | A逆势/B小顺势/C第二逆势 | `patterns/high_low.py` | `detect_abc_pullback()` | B不超过趋势极值 |
| T-B11 | 消耗棒/衰竭棒 | Exhaustion Bar | 异常大实体(>近期均值2倍) | `patterns/trap.py` | `detect_exhaustion_bar()` | 趋势末端信号 |
| T-B12 | 通道中反向剥头皮规则 | Channel Counter-Scalp | 宽通道可双向, 紧通道只顺势 | `strategies/range_trading.py` | `channel_scalp_rules()` | |
| T-B13 | 追踪止损 | Trailing Stop | 新高→止损移至更高低点下1 tick | `risk/stop_loss.py` | `trailing_stop()` | |
| T-B14 | 强趋势棒收盘入场 | Strong Bar Close Entry | 强尖刺阶段每棒收盘入场 | `strategies/trend_following.py` | `bar_close_entry()` | 止损远→仓位小 |

### C级 — 暂不量化

| # | 概念名 | 英文 | 备注 |
|---|--------|------|------|
| T-C01 | 趋势频谱 | Trend Spectrum | 连续谱, 依赖主观判断 |
| T-C02 | 趋势成熟的8步渐变 | Trend Aging 8 Steps | 定性渐变过程 |
| T-C03 | 买卖压力累积性 | Cumulative Pressure | 小K线累积等效大K线 |
| T-C04 | 真空效应 | Vacuum Effect | 买方/卖方暂停交易 |
| T-C05 | 迟到入场规则 | Late Entry | 心理判断 |
| T-C06 | 弱信号=强趋势悖论 | Weak Signal=Strong Trend | 定性心理悖论 |
| T-C07 | 通道=斜向区间 | Channel=Slanted Range | 多时间框架嵌套 |
| T-C08 | 嵌套通道 | Nested Channels | |
| T-C09 | 缺口测试 | Gap Test | |
| T-C10 | 回调入场 | Pullback Entry | 主观时机选择 |
| T-C11 | 立即至少小仓位入场 | Small Position Now | |
| T-C12 | 安静市场酝酿大趋势 | Quiet Market→Big Trend | 主观情绪判断 |

---

## 二、区间域 (Range Domain)

### A级 — 可直接量化

| # | 概念名 | 英文 | 量化条件 | 文件名 | 函数名 | 参数 | 备注 |
|---|--------|------|---------|--------|--------|------|------|
| R-A01 | 内包K线 / ii / iii | Inside Bar / ii / iii | 实体完全在前根范围, ii=2连, iii=3连 | `patterns/range.py` | `detect_inside_bar()` | df, idx | |
| R-A02 | 外包棒 | Outside Bar | 高>前高 且 低<前低 | `patterns/range.py` | `detect_outside_bar()` | df, idx | 单K线区间 |
| R-A03 | 铁丝网(Barbwire) | Barbwire | N根K线范围<ATR 30%, 连续多根外包 | `patterns/range.py` | `detect_barbwire()` | df, atr_factor=0.3 | |
| R-A04 | 区间边界识别 | Range Boundary | Swing High中位数=阻力, Swing Low中位数=支撑 | `patterns/range.py` | `identify_range_boundary()` | df, n=20 | 边界的清晰度评分 |
| R-A05 | 80%突破失败 | 80% Breakout Failure | 区间内突破→80%概率失败 | `patterns/range.py` | `detect_fake_breakout()` | df, key_levels | 反向交易信号 |
| R-A06 | 突破回调买入 | Breakout Pullback | 突破后第一次回到突破点, 胜率~60% | `strategies/range_trading.py` | `breakout_pullback_signal()` | df, breakout | 最佳回调入场 |
| R-A07 | 区间交易核心规则 | Trading Range Core Rules | 利润=区间宽度50-80%, 区间收窄不交易 | `strategies/range_trading.py` | `range_trade_evaluate()` | boundary, signal | |
| R-A08 | 微双顶/微双底 | Micro Double Top/Bottom | 连续2根同价位高/低点 | `patterns/reversal.py` | `detect_micro_double()` | df, idx | |
| R-A09 | 突破缺口 | Breakout Gap | 突破缺口幅度≈趋势后续幅度 | `data/loader.py` | — | — | M1数据层标记 |
| R-A10 | 衰竭缺口 | Exhaustion Gap | 趋势末端缺口, 2-3根K线内回补 | `patterns/trap.py` | `detect_exhaustion_gap()` | df | 反转前兆 |

### B级 — 需简化量化

| # | 概念名 | 英文 | 简化方案 | 文件名 | 函数名 | 备注 |
|---|--------|------|---------|--------|--------|------|
| R-B01 | 假突破陷阱 | Fake Breakout Trap | 突破后N根内回到边界+反向K线确认 | `patterns/trap.py` | `detect_fake_breakout_trap()` | |
| R-B02 | 扫止损陷阱 | Stop Run Trap | 穿越Swing Point后立即反转 | `patterns/trap.py` | `detect_stop_run_trap()` | |
| R-B03 | 高潮反转陷阱 | Climax Reversal Trap | 异常实体>2倍ATR+量>20日均量2倍+反向吞噬 | `patterns/trap.py` | `detect_climax_trap()` | M3.6核心 |
| R-B04 | 窄区间陷阱 | Barbwire Trap | 铁丝网结束突破无动能(阳接阴) | `patterns/trap.py` | `detect_barbwire_trap()` | |
| R-B05 | 双底牛旗 | Double Bottom Bull Flag | 回调中W底, 第二底不破第一底 | `patterns/reversal.py` | `detect_double_bottom_flag()` | |
| R-B06 | 双重确认原则 | Two Reasons Rule | 至少两个独立信号才入场 | `strategies/fusion.py` | `check_two_reasons()` | |
| R-B07 | 第一次回调 | First Pullback | 首次回调胜率≥60%, 1-2根浅回调 | `strategies/trend_following.py` | `first_pullback_signal()` | |
| R-B08 | 对决线 | Dueling Lines | 趋势线+通道线同时指向同一位置 | `patterns/range.py` | `detect_dueling_lines()` | 共振信号 |
| R-B09 | 三角形(4亚型) | Triangles | 上升/下降/收敛/扩张, 目标=高度 | `patterns/reversal.py` | `detect_triangle()` | |

### C级 — 暂不量化

| # | 概念名 | 英文 | 备注 |
|---|--------|------|------|
| R-C01 | 拐点区域 | Inflection Area | |
| R-C02 | 磁吸效应 | Magnet Effect | |
| R-C03 | 迟到的牛市陷阱 | Late Bull Trap | 主观"趋势老了" |
| R-C04 | 倾斜窄区间 | Sloping Tight Trading Range | |

---

## 三、反转域 (Reversal Domain)

### A级 — 可直接量化

| # | 概念名 | 英文 | 量化条件 | 文件名 | 函数名 | 参数 | 备注 |
|---|--------|------|---------|--------|--------|------|------|
| V-A01 | 楔形三推动能衰减 | Wedge Three-Push | 3推动能递减(实体缩小), 趋势线被突破 | `patterns/reversal.py` | `detect_wedge()` | df | |
| V-A02 | 双顶/双底 | Double Top/Bottom | 两顶高度差<ATR 30%, 中间回调>ATR 50% | `patterns/reversal.py` | `detect_double_top()` / `detect_double_bottom()` | df | |
| V-A03 | 更高低点(Higher Low) | Higher Low | 熊→牛确认: 回调低点高于前低 | `patterns/reversal.py` | `detect_higher_low()` | df | |
| V-A04 | 更低高点(Lower High) | Lower High | 牛→熊确认: 反弹高点低于前高 | `patterns/reversal.py` | `detect_lower_high()` | df | |
| V-A05 | 二次信号反转 | Second Signal Reversal | 第二次反转尝试比第一次可靠得多 | `patterns/reversal.py` | `second_signal_bonus()` | df | 80%首次失败 |
| V-A06 | MTR四必要条件 | Major Trend Reversal | 趋势→突破趋势线→测试极值→二次反转 | `state/market_cycle.py` | `check_mtr_conditions()` | df | 4步序列 |
| V-A07 | 连续Climax与三推修正 | Consecutive Climaxes | 3次Climax→至少两腿10+棒修正 | `patterns/trap.py` | `consecutive_climax_check()` | df | |
| V-A08 | Spike Pullback vs Reversal | Spike分类 | 顺势Spike被测试, 反转Spike几乎总被测试 | `state/spike_channel.py` | `classify_spike_type()` | df, spike | |
| V-A09 | 最终旗形反转 | Final Flag Reversal | 高潮→旗形(1-3棒)→再高潮→反转 | `patterns/reversal.py` | `detect_final_flag()` | df | |
| V-A10 | 1跳失败(One-Tick Failure) | 1-Tick Trap | 突破前棒仅1跳后立即反转 | `patterns/trap.py` | `detect_one_tick_failure()` | df, idx | 微观假突破 |
| V-A11 | 首小时极端形成规律 | Opening Hour Extremes | 50%/5棒, 90%/1-2小时, 首棒仅20% | `state/trend_day_classifier.py` | `opening_range_stats()` | df | |
| V-A12 | 跳空大小与趋势概率 | Gap Size Probability | 大跳空=5天最大或>日均波幅50% | `state/trend_day_classifier.py` | `gap_size_classify()` | df, avg_range | 参考15 |
| V-A13 | 跳空开盘三路径 | Gap Opening Paths | (1)开盘即趋势 (2)先逆后顺 (3)区间日 | `state/trend_day_classifier.py` | `gap_opening_path()` | df | |
| V-A14 | 趋势通道线超射反转 | Channel Overshoot | 通道线突破≈5根内失败 | `state/spike_channel.py` | `channel_overshoot_check()` | df | |
| V-A15 | 极度回归均值交易 | Extreme Mean-Reversion | >20根K线无回调→回归均值 | `state/trend_strength.py` | `extreme_mean_reversion()` | df, bar_threshold=20 | |

### B级 — 需简化量化

| # | 概念名 | 英文 | 简化方案 | 文件名 | 函数名 | 备注 |
|---|--------|------|---------|--------|--------|------|
| V-B01 | 趋势线突破必须有力 | Strong Trend Line Break | 突破必须穿透EMA+超出若干tick | `state/market_cycle.py` | `strong_tl_break()` | |
| V-B02 | 反转更可能形成区间(>50%) | Reversal→Range | 趋势线突破+测试极值→60%+概率区间 | `state/market_cycle.py` | `post_reversal_state()` | |
| V-B03 | 测试极值动量判断 | Extreme Test Momentum | 紧通道/无回调/无重叠=趋势可能恢复 | `state/trend_strength.py` | `extreme_test_momentum()` | |
| V-B04 | 反转交易 vs 逆趋势刮头皮 | Reversal vs Counter-Scalp | 有趋势线突破=反转交易, 无=禁逆势 | `strategies/reversal.py` | `is_reversal_trade()` | |
| V-B05 | 高潮扩展定义与结束标志 | Climax Definition | 结束=Pause Bar(小实体/Doji)或Reversal Bar | `patterns/trap.py` | `climax_end_bar()` | |
| V-B06 | 最大突破棒悖论 | Biggest Bar Paradox | 趋势>20棒后最大实体=反转>70%概率 | `patterns/trap.py` | `biggest_bar_check()` | |
| V-B07 | Channel争夺战 | Channel Battle | 大上Spike+大下Spike=区间 | `state/spike_channel.py` | `channel_battle_check()` | |
| V-B08 | 楔形回调 vs 楔形反转区分 | Wedge Pullback vs Reversal | <20棒=回调旗形, >=20棒=反转 | `patterns/reversal.py` | `wedge_pullback_or_reversal()` | |
| V-B09 | 失败形态=反向入场 | Failed Pattern Reversal | 任何信号被反向突破1 tick=反向入场 | `strategies/reversal.py` | `failed_pattern_entry()` | |
| V-B10 | 微双底/微双顶普适性 | Micro DBT/DBB Universal | 反转入场需2-3棒级微双底/顶确认 | `patterns/reversal.py` | `micro_double_confirmation()` | |
| V-B11 | 强反转K线量化 | Reversal Bar Strength | Close高于前N根High, N越大越强 | `patterns/signal_bar.py` | `reversal_bar_strength()` | |
| V-B12 | 多头急迫信号 | Bull Urgency | 回调低点高于前低>=2 tick | `state/always_in.py` | `bull_urgency_check()` | |
| V-B13 | 两次尝试失败=反向 | Two Failed Attempts | 同阻力/支撑测试2次未突破→反向 | `patterns/reversal.py` | `two_failed_attempts()` | |

### C级 — 暂不量化

| # | 概念名 | 英文 | 备注 |
|---|--------|------|------|
| V-C01 | 反转的两种速度 | Fast vs Gradual Reversal | |
| V-C02 | 强趋势紧迫感 | Urgency in Trends | |
| V-C03 | 尾盘吓人震荡 | Scary Close | 主观持仓判断 |
| V-C04 | 同价双向可盈利 | Both Sides Profitable | 资金管理哲学 |
| V-C05 | 形态演变 | Pattern Evolution | 40%可靠形态失败 |
| V-C06 | 通道=斜向区间(多TF) | Channel=Slanted Range | |
| V-C07 | 嵌套通道 | Nested Channels | |

---

## 函数签名速查

### state/always_in.py
```python
def determine_always_in(df: pd.DataFrame, weights: dict = None) -> str:
    """Always-In 5维加权判定: 返回 "LONG"/"SHORT"/"NONE" """

def compute_hhlh_structure(df: pd.DataFrame, n: int = 20) -> int:
    """计算高低点结构走势: +1(HH+HL) / -1(LL+LH) / 0(混合) """

def bull_urgency_check(df: pd.DataFrame) -> bool:
    """多头急迫信号: 回调低点高于前低 >= 2 tick """
```

### state/trend_strength.py
```python
def classify_trend_strength(df: pd.DataFrame) -> dict:
    """趋势强度五级分类: {strength, retrace_depth, above_ema} """

def measure_retracement_depth(peak: float, trough: float, current: float) -> float:
    """回调深度比 (0.0 ~ 1.0+) """

def detect_20_gap_bars(df: pd.DataFrame, ma_col: str = 'EMA20') -> bool:
    """检测连续20+根K线未触MA """

def two_legs_rule(df: pd.DataFrame, move_type: str) -> bool:
    """两腿法则校验 """

def extreme_mean_reversion(df: pd.DataFrame, bar_threshold: int = 20) -> bool:
    """极度回归均值检测 """
```

### state/spike_channel.py
```python
def detect_spike(df: pd.DataFrame, min_bodies: int = 2, body_pct: float = 0.70) -> Optional[dict]:
    """Spike检测: {start_idx, end_idx, direction, magnitude} """

def detect_channel(df: pd.DataFrame, spike: dict) -> Optional[dict]:
    """Channel检测: {type, upper_bound, lower_bound, slope} """

def project_measured_move(leg1_height: float, direction: str) -> float:
    """测量移动投影 """

def classify_spike_type(df: pd.DataFrame, spike: dict) -> str:
    """Spike分类: "顺势/逆势/反转" """

def channel_overshoot_check(df: pd.DataFrame) -> Optional[dict]:
    """通道线超射检测 """

def channel_battle_check(df: pd.DataFrame) -> bool:
    """Channel争夺战检测 """
```

### state/market_cycle.py
```python
def identify_market_cycle(df: pd.DataFrame) -> str:
    """市场周期定位: barbwire/breakout/spike_channel/wide_channel/trading_range """

def inertia_estimate(reversal_type: str) -> float:
    """趋势惯性估算(80%失败常量) """

def check_mtr_conditions(df: pd.DataFrame) -> dict:
    """MTR四必要条件检测 """

def strong_tl_break(df: pd.DataFrame) -> bool:
    """趋势线突破是否有力 """

def post_reversal_state(df: pd.DataFrame) -> str:
    """反转后的市场状态预测: trading_range/opposite_trend """
```

### state/trend_day_classifier.py
```python
def classify_trend_day(df: pd.DataFrame, always_in: str) -> dict:
    """趋势日七分法: {trend_day_type, confidence, features} """

def first_hour_extreme(df: pd.DataFrame, bar_count: int = 5) -> dict:
    """首小时极端形成统计 """

def match_small_pullback(df: pd.DataFrame, daily_range: float) -> dict:
def match_spike_channel_day(df: pd.DataFrame) -> dict:
def match_trending_range_day(df: pd.DataFrame, avg_range: float) -> dict:
def match_open_trend_day(df: pd.DataFrame, avg_range: float) -> dict:
def match_reversal_day(df: pd.DataFrame) -> dict:
def match_resumption_day(df: pd.DataFrame) -> dict:
def match_stairs_day(df: pd.DataFrame) -> dict:

def opening_range_stats(df: pd.DataFrame) -> dict:
    """开盘区间统计: 开盘区间大小/占日均比等 """

def gap_size_classify(df: pd.DataFrame, avg_range: float) -> str:
    """跳空大小分类: large/medium/small """

def gap_opening_path(df: pd.DataFrame) -> str:
    """跳空开盘三路径: trend/counter_range/range """
```

### state/context_feedback.py
```python
def feedback_adjust(always_in: str, confidence: float,
                    l3_results: list, trend_strength: str) -> dict:
    """L2↔L3反馈回路: 返回更新后的状态和置信度 """
```

### state/multi_tf.py
```python
def multi_tf_alignment(df_daily: pd.DataFrame, df_weekly: pd.DataFrame) -> dict:
    """多时间框架协同: {daily_ai, weekly_ai, alignment, position_multiplier} """
```

### patterns/high_low.py
```python
def count_highs(df: pd.DataFrame, trend: str) -> pd.Series:
    """牛市High计数: 每根K线返回当前High计数(0-4) """

def count_lows(df: pd.DataFrame, trend: str) -> pd.Series:
    """熊市Low计数: 每根K线返回当前Low计数(0-4) """

def high_low_signal(df: pd.DataFrame, always_in: str) -> dict:
    """High/Low综合信号: {high_count, low_count, signal_valid, entry_trigger} """

def detect_abc_pullback(df: pd.DataFrame) -> Optional[dict]:
    """ABC回调结构检测 """
```

### patterns/signal_bar.py
```python
def classify_bar(df: pd.DataFrame, idx: int) -> dict:
    """K线分类: {type, body_pct, tail_pct, is_inside, is_outside} """

def detect_signal_bar(df: pd.DataFrame, idx: int, always_in: str) -> dict:
    """信号K线: {is_signal, quality, direction, reason} """

def detect_two_bar_reversal(df: pd.DataFrame, idx: int) -> Optional[dict]:
def detect_three_bar_reversal(df: pd.DataFrame, idx: int) -> Optional[dict]:
def reversal_bar_strength(df: pd.DataFrame, idx: int) -> float:
    """强反转K线量化: Close高于前N根High, N越大越强 """
```

### patterns/reversal.py
```python
def detect_wedge(df: pd.DataFrame) -> Optional[dict]:
def detect_double_top(df: pd.DataFrame) -> Optional[dict]:
def detect_double_bottom(df: pd.DataFrame) -> Optional[dict]:
def detect_flag(df: pd.DataFrame, always_in: str) -> Optional[dict]:
def detect_higher_low(df: pd.DataFrame) -> Optional[int]:
def detect_lower_high(df: pd.DataFrame) -> Optional[int]:
def detect_all_patterns(df: pd.DataFrame, always_in: str) -> list:
def detect_micro_double(df: pd.DataFrame, idx: int) -> Optional[dict]:
def detect_double_bottom_flag(df: pd.DataFrame) -> Optional[dict]:
def detect_triangle(df: pd.DataFrame) -> Optional[dict]:
def detect_final_flag(df: pd.DataFrame) -> Optional[dict]:
def second_signal_bonus(df: pd.DataFrame) -> float:
def wedge_pullback_or_reversal(df: pd.DataFrame, wedge: dict) -> str:
def micro_double_confirmation(df: pd.DataFrame, idx: int) -> bool:
def two_failed_attempts(df: pd.DataFrame, level: float) -> bool:
```

### patterns/range.py
```python
def identify_range_boundary(df: pd.DataFrame) -> dict:
def detect_barbwire(df: pd.DataFrame) -> Optional[dict]:
def detect_fake_breakout(df: pd.DataFrame) -> Optional[dict]:
def detect_inside_bar(df: pd.DataFrame, idx: int) -> Optional[dict]:
def detect_outside_bar(df: pd.DataFrame, idx: int) -> Optional[dict]:
def detect_dueling_lines(df: pd.DataFrame) -> Optional[dict]:
```

### patterns/trap.py
```python
def detect_fake_breakout_trap(df: pd.DataFrame, key_levels: dict) -> Optional[dict]:
def detect_stop_run_trap(df: pd.DataFrame, swing_points: dict) -> Optional[dict]:
def detect_climax_trap(df: pd.DataFrame) -> Optional[dict]:
def detect_barbwire_trap(df: pd.DataFrame) -> Optional[dict]:
def detect_all_traps(df: pd.DataFrame, key_levels: dict, swing_points: dict) -> list:
def detect_exhaustion_bar(df: pd.DataFrame, idx: int) -> Optional[dict]:
def detect_exhaustion_gap(df: pd.DataFrame) -> Optional[dict]:
def consecutive_climax_check(df: pd.DataFrame) -> dict:
def detect_one_tick_failure(df: pd.DataFrame, idx: int) -> Optional[dict]:
def climax_end_bar(df: pd.DataFrame, idx: int) -> bool:
def biggest_bar_check(df: pd.DataFrame) -> Optional[dict]:
```

### strategies/trend_following.py
```python
def high1_buy_signal(df: pd.DataFrame, state: dict, patterns: dict) -> Optional[dict]:
def channel_pullback_signal(df: pd.DataFrame, state: dict) -> Optional[dict]:
def breakout_pullback_signal(df: pd.DataFrame, patterns: dict) -> Optional[dict]:
def trend_following_signals(df: pd.DataFrame, state: dict, patterns: dict) -> list:
def stop_entry_signal(signal_bar: dict, direction: str, tick: float) -> dict:
def limit_entry_signal(df: pd.DataFrame, idx: int, direction: str) -> dict:
def bar_close_entry(df: pd.DataFrame, idx: int, direction: str) -> dict:
def first_pullback_signal(df: pd.DataFrame) -> Optional[dict]:
```

### strategies/range_trading.py
```python
def range_boundary_signal(df: pd.DataFrame, boundary: dict) -> Optional[dict]:
def fake_breakout_reversal(df: pd.DataFrame, breakout: dict) -> Optional[dict]:
def range_trading_signals(df: pd.DataFrame, boundary: dict, patterns: list) -> list:
def range_trade_evaluate(boundary: dict, signal: dict) -> dict:
def channel_scalp_rules(df: pd.DataFrame, channel: dict) -> str:
def breakout_pullback_signal(df: pd.DataFrame, breakout: dict) -> Optional[dict]:
```

### strategies/reversal.py
```python
def wedge_reversal_signal(df: pd.DataFrame, wedge: dict) -> Optional[dict]:
def double_top_bottom_signal(df: pd.DataFrame, pattern: dict) -> Optional[dict]:
def trendline_break_signal(df: pd.DataFrame) -> Optional[dict]:
def is_reversal_trade(df: pd.DataFrame) -> bool:
def failed_pattern_entry(df: pd.DataFrame, pattern: dict) -> Optional[dict]:
```

### strategies/fusion.py
```python
def confluence_score(signals: list, market_state: dict) -> float:
def rank_stocks(all_signals: dict, market_state: dict, top_n: int = 5) -> pd.Series:
def check_two_reasons(signals: list) -> bool:
```

### risk/trader_equation.py
```python
def trader_equation_evaluate(signal_quality: str, stop_pct: float,
                              target_pct: float, market_multiplier: float) -> dict:
def position_size_from_te(te_result: dict, account_risk_pct: float = 0.02) -> float:
```

### risk/position_sizing.py
```python
def kelly_variant(win_rate: float, win_loss_ratio: float) -> float:
def max_position_per_market_state(state: str, trend_strength: str) -> float:
def scale_out_plan(entry: float, stop: float, current: float) -> dict:
```

### risk/stop_loss.py
```python
def initial_stop(signal_bar: dict, direction: str, buffer_tick: float = 0.01) -> float:
def breakeven_stop(entry: float, current: float, risk_amount: float) -> Optional[float]:
def trailing_stop(current: float, highest: float, trail_pct: float = 0.05) -> float:
```

---

_与 requirements.md §M2-M5 函数签名一致。_
