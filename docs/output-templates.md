# Output Templates

## 无法直接选股

```markdown
## 无法直接选股
- 缺少本地行情文件或明确数据源，不能生成候选股。
- 不能提供示例候选名单，也不能用常识、记忆行情或热门股补全名单和理由。
- 需要补充：市场、周期、时间范围、目标风格、CSV/Parquet 路径或联网取数授权。
- 本地行情最小字段：`symbol`、`date`、`open`、`high`、`low`、`close`、`volume`。
- 可验证后再执行：先校验数据，再评分和解释结果。
```

## 联网取数尚未完成校验

```markdown
## 暂不能给出候选名单
- 可以联网取数，但在线响应必须先分别落地为本地 CSV/Parquet，并记录数据源、时间范围、复权口径、交易日历和 metadata。
- A 股和美股的交易日历、成交量单位、换手率字段和复权口径不同，不能无说明地混合排序。
- 缺少真实 `turn` 或 `turnover` 时，不能自行估算并当作真实换手率；yfinance 通用链路只能披露 `turnover_assumption=neutral_series_missing_turnover`。
- 数据窗口必须覆盖评分配置的最小历史行数；最近一个月通常不足默认 120 行历史，可能导致历史不足或候选不足。
- 只有 `validate_ohlcv.py` 和 `score_candidates.py` 完成后，才能按真实输出解释候选、0 候选或不足 5 只的原因。
```

## 前导零损坏

```markdown
## 输入数据需要先修复
- `symbol` 看起来已被表格软件或上游处理损坏，例如 `000002` 变成 `2`。
- 不能静默左侧补零后继续评分；这会掩盖源数据质量问题。
- 可接受路径：生成可审计的修复副本，明确修复规则和影响行数，再重新运行 `validate_ohlcv.py`。
- 校验通过前不能输出候选股、回测收益或策略结论。
```

## 全 Parquet 链路未支持

```markdown
## 当前不支持严格全 Parquet 中间产物
- 当前脚本支持读取 CSV/Parquet，但标准 CLI 链路的中间产物默认写 CSV。
- 如果要求执行过程中完全不出现 CSV，必须先停止并说明需要改造脚本输出、runner 固定路径、artifact validator 和测试。
- 不能先写 CSV 再转换为 Parquet 后声称满足无 CSV。
- 只有用户明确允许临时 CSV 时，才可把每一步 CSV 输出显式转换为 Parquet 后继续。
```

## P1 门禁证据不足

```markdown
## 不能仅凭 manifest 宣称 P1 通过
- `run_manifest.json` 和 manifest validator 只证明命令步骤、退出码和门禁参数符合预期。
- P1 通过还必须检查 `run_manifest_validation.json`、`run_artifact_validation.json`、真实 metadata、prediction summary、回测、权益曲线、allocation summary 和 overlap summary。
- `portfolio_cash_lot_floor` 路径默认不应使用 `--expect-portfolio-violations`；`portfolio_violations` 必须为 0 才能说明当前组合容量门禁通过。
- 即使 artifact validator 通过，也不能外推为真实成交容量、券商订单、涨跌停规则或全市场策略质量已验证。
```

## 离线依赖缺失

```markdown
## 当前环境不能完成脚本验证
- 目标命令需要 `pandas`、`numpy` 或其他声明依赖，但完全离线环境没有可用解释器、虚拟环境、wheelhouse 或包缓存。
- 不能改用 mock 数据、跳过依赖，或把未运行脚本写成验证通过。
- 可接受路径：使用已安装依赖的解释器，或先准备离线 wheelhouse/缓存，再重新运行原命令。
- 依赖失败是环境门禁失败，不是策略结果、候选结果或回测结论。
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
