# Factor Framework

本文件承接 `SKILL.md` 中较长的因子和评分细节，供 Agent 在需要实现或审查策略公式时读取。

## 通用因子

推荐从四类因子构建基础策略：

- 趋势动量：`momentum_1m = close / close.shift(20) - 1`、`momentum_3m = close / close.shift(60) - 1`、`momentum_6m = close / close.shift(120) - 1`。
- 技术状态：RSI、MACD、布林带、量比、波动率。
- 短线异动：成交量放大、换手率放大、MACD 转强、价格位置、短期收益。
- 风险控制：最大波动率、最大回撤、跌破均线、RSI 过热、流动性不足、价格异常、财务和事件风险。

技术指标必须说明窗口长度、缺失值处理和裁剪规则。风险控制建议先做硬过滤，再把剩余风险作为总分扣分项。

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
