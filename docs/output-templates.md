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

## Akshare fallback 成功

```markdown
## Akshare 取数使用了 fallback
- 命令退出码为 0 但 `fallback_errors` 非空时，不能写成主接口稳定成功。
- 必须披露主接口错误、`fallback_errors` 数量，以及 metadata 中逐标的 `provider`。
- `failed_symbols=[]` 只说明最终没有标的完全失败，不代表主接口无异常。
- 合规表述是“主接口失败后 fallback provider 取数成功”；不能外推为真实公网数据源长期稳定。
```

## 前导零损坏

```markdown
## 输入数据需要先修复
- `symbol` 看起来已被表格软件或上游处理损坏，例如 `000002` 变成 `2`。
- 不能静默左侧补零后继续评分；这会掩盖源数据质量问题。
- 可接受路径：生成可审计的修复副本，明确修复规则和影响行数，再重新运行 `validate_ohlcv.py`。
- 校验通过前不能输出候选股、回测收益或策略结论。
```

## 日期格式归一化重复

```markdown
## 输入日期存在重复
- `YYYY-MM-DD` 和 `YYYYMMDD` 都是支持格式，但会解析为同一个真实交易日。
- 同一 `symbol` 下 `2026-05-29` 和 `20260529` 这类重复不能当成两天数据。
- `validate_ohlcv.py` 或 `score_candidates.py` 返回 duplicate symbol/date 时，应先修复源文件并重新校验。
- `output_written=false` 不是 0 候选成功，校验通过前不能输出候选或回测结论。
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

## 组合 allocation 裁剪

```markdown
## 组合 allocation 已裁剪候选
- `raw_candidates` 是组合容量裁剪前候选池，不等于最终进入回测或成交的数量。
- 后续回测应基于 `qsss_candidates.csv` / `qsss_sized_candidates.csv` 和 `allocated_candidates`。
- 如果 `skipped_candidates>0`，必须披露 `qsss_skipped_candidates.csv`、`skip_reason_counts` 和逐信号日 raw/allocated/skipped。
- 本地 `portfolio_cash_lot_floor` 仍不是券商订单、真实成交或真实现金容量证明。
```

## Drop-invalid 数据口径

```markdown
## 清洗后通过，不等于源数据无异常
- `--drop-invalid-rows` 只能说明取数阶段显式丢弃了已记录的异常行。
- 报告时必须同时披露 `invalid_rows`、`dropped_invalid_rows`、`raw_non_trading_rows`、`non_trading_rows` 和 `tradestatus_missing_rows`。
- 只有在 `invalid_rows == dropped_invalid_rows`，且清洗后 `non_trading_rows=0`、`tradestatus_missing_rows=0` 时，后续 validator 才能在显式 `--allow-dropped-invalid-rows` 下通过。
- 不能把 `quality_errors=[]`、summary 通过或 artifact validator 通过写成“源数据没有异常”。
```

## 资金字段覆盖

```markdown
## 不能静默覆盖候选资金字段
- 候选表已有 `weight`、`notional`、`quantity` 或 `cash_reserved` 时，默认不能直接覆盖。
- 默认失败里的 `output_written=false` 是有效门禁证据，不能说已经生成 sized candidates。
- 只有用户明确确认要用本仓库 sizing 模型重算时，才显式传 `--overwrite-capital-fields`。
- 重算后必须披露 `capital_model`、`cash_budget` 和 `lot_size`；这仍不是券商订单、真实成交或真实现金容量证明。
```

## 严格回测缺少未来价格

```markdown
## 严格回测未通过
- `--fail-on-incomplete` 返回非 0 且 `output_not_written=true` 时，不能报告回测成功。
- `missing_future_price` 表示信号日之后没有足够的未来交易行，不是可忽略 warning。
- 合规路径是提供覆盖持有期的价格数据，或改用更早信号日重新生成候选和 sizing。
- 不能跳过 incomplete trades、手写空回测文件，或把候选结果解释成 5 日 buy-hold 收益。
```

## 离线依赖缺失

```markdown
## 当前环境不能完成脚本验证
- 目标命令需要 `pandas`、`numpy` 或其他声明依赖，但完全离线环境没有可用解释器、虚拟环境、wheelhouse 或包缓存。
- 不能改用 mock 数据、跳过依赖，或把未运行脚本写成验证通过。
- 可接受路径：使用已安装依赖的解释器，或先准备离线 wheelhouse/缓存，再重新运行原命令。
- 依赖失败是环境门禁失败，不是策略结果、候选结果或回测结论。
```

## Python API 复用边界

```markdown
## Python 复用需要显式脚本路径
- 本仓库 CLI 是稳定入口，当前不是可安装 Python package。
- 复用脚本函数前，必须把仓库的 `scripts/` 加入 `PYTHONPATH` 或 `sys.path`。
- 不要把 `from scripts.score_candidates import ...` 当成稳定 API；它可能在 import 阶段成功，但调用时因内部顶层模块路径缺失而失败。
- 直接调用 Python API 时，`input` 字段由调用方记录或注入，不能把 API 调用摘要说成完整 CLI 门禁。
```

## 配置和摘要口径

```markdown
## 配置和摘要口径
- `output.max_candidates=0` 表示不截断候选，不是输出 0 个候选。
- `max_candidates` 是排序后的 top-N 截断，不是阈值过滤；截断不增加 `threshold_failed_symbols`。
- `threshold_failed_symbols` 是被任意阈值过滤的唯一标的数。
- `threshold_failures` 是逐阈值失败次数，同一标的可能同时计入多个阈值，不能和 `threshold_failed_symbols` 相加对账。
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

## LightGBM prediction 部分成功

```markdown
## LightGBM prediction 门禁未完整通过
- 非严格模式退出码为 0 但 `skipped_symbols>0` 时，只能说明部分标的写出了预测。
- 必须披露 `raw_symbols`、`predicted_symbols`、`skipped_symbols` 和 `skipped_symbol_examples`。
- 下游 `validate_ohlcv.py` 或 `score_candidates.py` 通过，只覆盖已写出的预测文件，不能反推上游全部标的通过。
- 完整门禁应使用 `--fail-on-skipped`，或显式确认 `raw_symbols == predicted_symbols` 且 `skipped_symbols == 0`。
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
