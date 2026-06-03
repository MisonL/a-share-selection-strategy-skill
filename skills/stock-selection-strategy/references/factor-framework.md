# 因子框架

本文件承接 `SKILL.md` 中较长的因子和评分细节，供 Agent 在需要实现或审查策略公式时读取。

## 读取指南

| 任务 | 读取章节 |
| --- | --- |
| 实现或审查通用技术评分 | 通用因子、通用评分 |
| 调整低价超短权重 | 通用评分、过滤和排序 |
| 解释候选输出字段 | 输出字段 |
| 查 prediction-derived 专属口径 | [prediction-derived-profile.md](prediction-derived-profile.md) |

## 核心原则

| 原则 | 要求 |
| --- | --- |
| 先过滤再评分 | 硬门禁失败不能靠总分补回来 |
| 公式可追溯 | 每个分数都要能回到输入字段、窗口和裁剪规则 |
| 输出不外推 | 候选表只证明当前配置下入选，不证明收益或交易指令 |
| 缺字段显式失败 | 不用 mock、默认值或静默近似补齐关键输入 |

## 通用因子

推荐从四类因子构建基础策略：

- 趋势动量：`momentum_1m = close / close.shift(20) - 1`、`momentum_3m = close / close.shift(60) - 1`、`momentum_6m = close / close.shift(120) - 1`。
- 技术状态：RSI、MACD、布林带、量比、波动率。
- 短线异动：成交量放大、换手率放大、MACD 转强、价格位置、短期收益。
- 风险控制：最大波动率、最大回撤、跌破均线、RSI 过热、流动性不足、价格异常、财务和事件风险。

技术指标必须说明窗口长度、缺失值处理和裁剪规则。风险控制建议先做硬过滤，再把剩余风险作为总分扣分项。

| 因子组 | 常用输入 | 输出示例 | 注意事项 |
| --- | --- | --- | --- |
| 趋势动量 | `close` | `momentum_1m`、`momentum_3m` | 必须说明窗口和信号日 |
| 技术状态 | `close`、`volume` | RSI、MACD、布林带、量比 | 缺失值和裁剪规则要固定 |
| 短线异动 | `volume`、`turn`、`close` | `explosion_score` | 成交额和成交量不能混用 |
| 风险控制 | `close`、可交易字段 | `risk_score`、硬过滤原因 | 真实停牌、涨跌停需外部字段证明 |

## 通用评分

默认权重可作为起点：

```text
total_score =
  trend_score * 0.30
  + momentum_score * 0.20
  + explosion_score * 0.35
  + risk_score * 0.15
```

短线爆发分示例：

```text
explosion_score =
  volume_ratio * 0.30
  + turnover_ratio * 0.20
  + macd_cross_score * 0.20
  + price_position_score * 0.15
  + short_momentum_score * 0.15
```

建议对 `volume_ratio` 和 `turnover_ratio` 设置上限，例如裁剪到 0 到 5，避免异常成交量支配总分。

## 过滤和排序

评分后先硬过滤，再排序。示例阈值：

- `trend_score >= 0.60`
- `momentum_score >= -0.10`
- `30 <= rsi <= 75`
- `volatility <= 0.60`
- `volume >= 最低成交量阈值`
- `close >= 最低价格阈值`

排序默认按 `total_score` 降序。若任务偏短线，可提高 `explosion_score` 权重；若任务偏稳健，可提高 `risk_score` 和基本面权重。

## 输出字段

候选表建议包含：

- `rank`、`symbol`、`name`、`market`
- `total_score`、`trend_score`、`prediction_score`
- `momentum_score`、`explosion_score`、`risk_score`
- `ma15`、`signal_tier`、`recommendation`
- `key_reasons`、`risk_notes`、`data_window`

输出解释必须包含使用的数据、因子和权重、主要过滤原因，并明确结果是策略候选，不是收益承诺。

## 汇报边界

| 事实 | 可以说 | 不能说 |
| --- | --- | --- |
| 技术因子评分通过 | 当前配置下候选满足阈值 | 策略收益已验证 |
| `explosion_score` 较高 | 短线异动因子较强 | 必然短线爆发 |
| `risk_score` 较低 | 当前风险因子扣分较多 | 标的一定不可交易 |
| 输出候选表 | 生成了策略候选 | 已生成交易指令 |
