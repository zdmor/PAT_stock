# P2 评审提示词 — 待转发 workbuddy/qclaw

> 保存于 2026-06-12。评审后结果写入 review_chain.md。

---

## 任务

审查 PAT 系统 P2 两个模块的代码实现，验证功能正确性、设计一致性和边界处理。

## 输入文件

1. `D:\ClaudeWorkspace\price_action_trading\state\market_state.py` — 5维加权 Always-In
2. `D:\ClaudeWorkspace\price_action_trading\tests\test_market_state.py` — 测试文件 (10个合成测试)
3. `D:\ClaudeWorkspace\price_action_trading\state\spike_channel.py` — Spike+Channel 检测
4. `D:\ClaudeWorkspace\price_action_trading\tests\test_spike_channel.py` — 测试文件 (12个测试)
5. `D:\ClaudeWorkspace\price_action_trading\docs\concept_map.md` — 设计文档

## 审查 checklist

### 模块 A: Always-In 5 维加权

- [ ] A1: 运行两个测试文件，确认全部通过（market_state 10/10, spike_channel 12/12）
- [ ] A2: 权重是否与 concept_map.md T-B01 一致 (0.30/0.25/0.20/0.15/0.10)
- [ ] A3: _dim_ema_slope 的 bearish 分支是否返回负分数（修复了符号 bug）
- [ ] A4: bearish 阈值 -0.30 是否与 bullish 阈值 0.30 对称
- [ ] A5: 边界条件：空 DataFrame 返回 oscillating + confidence=0
- [ ] A6: 边界条件：数据不足 30 根返回 oscillating + confidence=0
- [ ] A7: 每个维度函数的 weight 与 concept_map 一致(d1=0.30/d2=0.25/d3=0.20/d4=0.15/d5=0.10)
- [ ] A8: 权重总和 = 1.0 （测试 test_weights_sum_to_one 验证）

### 模块 B: Spike+Channel

- [ ] B1: 牛市 spike 检测：方向=bullish, bar_count >=2
- [ ] B2: 熊市 spike 检测：方向=bearish
- [ ] B3: 震荡数据不应检出 spike（调高 body_pct 和 min_bodies 后）
- [ ] B4: detect_channel 在无 spike 时返回 None
- [ ] B5: channel_overshoot_check 在无 channel 时返回 None
- [ ] B6: 边界条件：空 DataFrame 不崩溃
- [ ] B7: 参数覆盖：min_bodies=5 过滤长度为 3 的 spike

### 设计一致性

- [ ] C1: concept_map.md T-A04 指明 detect_spike 参数为 min_bodies=2, body_pct=0.70 — 实现是否匹配
- [ ] C2: concept_map.md T-B01 指明 5 维权重 0.30/0.25/0.20/0.15/0.10 — 实现是否匹配
- [ ] C3: concept_map.md T-A06 和 T-A03 的函数名分别位于 trend_strength.py 目录下，但当前实现在 market_state.py — 这是设计偏离还是合理内部化

## 输出断言

- 断言1: 测试文件 count = market_state 10个测试 + spike_channel 12个测试 = 22个，确认全部 PASS（逐条列出 pass/fail）
- 断言2: 5 维权重求和应等于 1.0，列出每个维度的 weight 值 + 总和

## 输出格式

```
## 审查结论

**测试结果:** X/22 PASS, X/22 FAIL

**发现的 issues:**
- [高/中/低] issue描述

**设计偏离:**
- [有/无]

**结论:** PASS / CONDITIONAL / FAIL
**条件（若 CONDITIONAL）:**
```
