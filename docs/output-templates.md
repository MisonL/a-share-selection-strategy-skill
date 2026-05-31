# Output Templates

## 无法直接选股

```markdown
## 无法直接选股
- 缺少本地行情文件或明确数据源，不能生成候选股。
- 需要补充：市场、周期、时间范围、目标风格、CSV/Parquet 路径或联网取数授权。
- 本地行情最小字段：`symbol`、`date`、`open`、`high`、`low`、`close`、`volume`。
- 可验证后再执行：先校验数据，再评分和解释结果。
```

## QSSS-derived 缺少 prediction

```markdown
## 无法按 QSSS-derived 原口径评分
- 输入缺少 `prediction` 或 `prediction_score`，不能生成 QSSS-derived 候选股。
- `prediction` 是上游 LightGBM 概率，不得用动量分、固定 `0.5`、mock 值或技术指标近似冒充。
- 当前可做：
  - 先提供或生成可追溯的上游 `prediction_score`，再运行 QSSS-derived 评分。
  - 只做字段质量检查时，可先运行 QSSS profile 校验，让缺失字段显式失败。
- 即使使用 `generate_lightgbm_predictions.py`，也必须单独核验训练窗口、标签、特征、时间序列切分、跳过标的和未来泄漏风险。
```

## 0 候选解释

```markdown
## 0 候选解释
- 脚本已成功运行，但没有股票通过当前股票池和阈值。
- 主要原因：
  - `input_symbols=0`：股票池配置和输入市场或代码不匹配。
  - `universe_filtered_symbols>0`：股票池过滤剔除了标的，可继续查看 `market_filtered_symbols`、`prefix_allow_filtered_symbols`、`prefix_excluded_symbols`。
  - `threshold_failed_symbols>0`：评分后被阈值过滤；`threshold_failures` 是非互斥独立计数。
  - `empty_result_reason`：区分 `universe_filtered_all`、`threshold_filtered_all` 等成功空结果原因；全失败或全短历史会显式失败。
  - `failed_symbols>0`：存在单股运行期异常，需要复核。
- 如果 `failed_symbols>0`，应进入复核或失败处理；`effective_empty_result=true` 只说明脚本完成并无候选。
- 0 候选不是错误退出，也不是收益或策略有效性验证。
```

## 候选结果

```markdown
## 策略口径
- 市场和周期：
- 数据窗口：
- 股票池过滤：
- 因子和权重：

## 候选结果
| rank | symbol | name | total_score | key_reasons | risk_notes |
|------|--------|------|-------------|-------------|------------|

## 过滤摘要
- 输入股票数：
- 剔除数量和原因：
- 最终候选数：

## 验证与限制
- 已验证：
- 未验证：
- 数据限制：
- 证据路径：
- `prediction_source`：
- `raw_symbols/predicted_symbols/skipped_symbols`：
- `tradability_model`：
- `limit_rules_model`：
- `portfolio_violations`：
- `manifest_validation`：
- `artifact_validation`：
```
