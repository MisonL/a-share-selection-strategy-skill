# QSSS-Derived Profile

本文件保存 QSSS-derived A 股默认剖面的细节。`SKILL.md` 只保留入口约束；当用户要求“复刻 QSSS 原选股策略”或使用 `scripts/qsss_profile_config.json` 时再读取本文件。

## 股票池和运行边界

- 默认市场为 A 股日线。
- 输入必须带 `market` 列，A 股记录使用 `A-share`。
- 股票代码只保留 `60`、`68`、`00`、`30` 开头的标的。
- 排除 `8`、`4` 开头的标的，用于避开北交所和新三板口径。
- 每只股票至少需要 120 条日线记录。
- 批量任务必须让超时、失败数量和进度事件可观测，不得隐藏失败。

## 数据清洗和失败分类

预设脚本采用严格输入校验：字段缺失、无效价格、负成交量或重复日期会直接失败；历史不足和单股评分异常会被记录为可见计数。

- `close` 必须存在、非空且大于 0。
- 历史行数不足 120 时记录为 `insufficient_history_symbols`。
- 对 `close`、`volume`、`turn` 或 `turnover` 使用中位数加减 3 倍标准差裁剪异常值。
- 技术指标阶段不额外把 0 替换为缺失值；ML 特征阶段才将 `close`、`volume`、`turn` 中的 0 替换为缺失值，再前向和后向填充。
- 涉及除法的换手率、成交量和短线动量组件必须显式处理 0 或缺失分母。
- 单股分析异常应记录为 `failed_stocks` 或等价失败计数，不得把失败股票伪装成成功候选。

## 技术指标口径

- 动量：`momentum_1m = close.pct_change(20)`、`momentum_3m = close.pct_change(60)`、`momentum_6m = close.pct_change(120)`。
- 候选表中的 `momentum_score` 使用最新 `momentum_1m`。
- RSI：14 周期，缺失填充为 50，裁剪到 0 到 100。
- MACD：EMA12、EMA26、signal 9；状态包括 `golden_cross`、`dead_cross`、`bullish`、`bearish`、`neutral`、`unknown`。
- 布林带：20 周期均线，加减 2 倍标准差，滚动窗口最少 5 条。
- 波动率：日收益率 20 周期滚动标准差乘以 `sqrt(252)`，缺失填充为均值，裁剪到 0 到 2。
- 风险项直接使用 `1 - volatility`，当 `volatility > 1` 时允许产生负向扣分。
- 量比：`volume / volume_ma20`，滚动窗口最少 5 条，缺失填充为 1.0，裁剪到 0 到 10。

## ML Prediction 口径

QSSS 原策略的主趋势分是 LightGBM 输出的上涨概率 `prediction`。

- 特征：`momentum_1m`、`momentum_3m`、`momentum_6m`、`volatility`、`vol_ratio`、`rsi`、`macd`、`signal`。
- 输入少于 100 行时不训练；特征和目标清洗后少于 50 行时不训练。
- 标签：`target = close.shift(-5) / close - 1`，分类标签为 `target > target.mean()`。
- 未来收益标签只能用于训练标签构造，不得泄漏到预测期特征、筛选条件或同日验证结论里。
- 标准化：使用 `StandardScaler` 拟合训练特征。
- 模型：`LGBMClassifier`，`n_estimators=100`、`num_leaves=31`、`min_child_samples=5`、`max_depth=5`、`learning_rate=0.1`、`random_state=42`。
- 历史原实现使用随机 `train_test_split(test_size=0.2, random_state=42)`，新 Agent 应优先改为时间序列切分。
- LightGBM 不可用、训练失败或预测失败时，应显式报告环境或模型问题，不得用固定 0.5 或动量近似冒充有效预测。
- `generate_lightgbm_predictions.py` 会把最新预测概率重复写入该标的所有行，供评分脚本消费当前概率；不要解释成逐日历史预测序列。
- 真实门禁必须启用 `--fail-on-skipped`，或显式检查 `raw_symbols == predicted_symbols` 且 `skipped_symbols == 0`。

## 短线爆发分

```text
explosion_score =
  volume_ratio * 0.30
  + turnover_ratio * 0.20
  + macd_cross_score * 0.20
  + (1 - price_position) * 0.15
  + short_momentum_score * 0.15
```

- `volume_ratio = latest_volume / mean(volume[-20:])`，裁剪到 0 到 5。
- `turnover_ratio = latest_turn / mean(turn[-20:])`，裁剪到 0 到 5。
- `macd_cross_score = 1.0` 仅当最新 `macd - signal > 0` 且前一条 `macd - signal < 0`。
- `price_position` 为当前收盘价在近 20 日高低区间中的位置；分数使用 `1 - price_position`。
- `short_momentum_score` 使用 `close[-1] / close[-3] - 1`，放大 100 倍后裁剪到 -20 到 20，再映射到 0 到 1。

## 评分、过滤和派生视图

```text
total_score =
  prediction * 0.30
  + momentum_score * 0.20
  + explosion_score * 0.35
  + (1 - volatility) * 0.15
```

硬过滤阈值：

- `prediction >= 0.60`
- `momentum_score >= -0.10`
- `30 <= rsi <= 75`
- `volatility <= 0.60`
- `volume >= 50000`
- `close >= 3.0`

排序按 `total_score` 降序。CLI 派生视图可额外列出低价均线、超短线爆发潜力和低价爆发标的。

`signal_tier` 和 `recommendation` 是展示分层，不是买卖建议。原 Web 回测只支持真实日线收盘价上的 `buy_hold` 基线；`backtest_buy_hold.py` 只支持 round-trip bps 成本和滑点扣减，不覆盖涨跌停和不可交易状态。

## 工程派生边界

- `OptimizedQuantStrategy` 复用同一组技术指标、ML prediction、爆发分、过滤阈值和总分公式，但增加缓存、分布式任务、分析时间戳和批处理路径。
- 交互 CLI 复用 `run_analysis()` 的结果，只改变表格展示、保存和分组。
- 数据库辅助查询不是实时选股主链，只能作为历史展示或二次查询口径。
- 缓存、线程数、分布式调度、数据库批量插入、数据源健康状态是工程控制面，不是新的选股因子。
