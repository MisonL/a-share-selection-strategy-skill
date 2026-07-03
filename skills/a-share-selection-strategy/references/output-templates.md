# Output Templates

本文件只保留汇报路由、高频模板和最终候选骨架。先按机器字段选择模板；若命中低频场景，再读取下方同级 reference。不要把模板中的占位项当作事实。

## 目录

- [场景直跳表](#场景直跳表)
- [快速路由](#快速路由)
- [恢复动作快速路由](#恢复动作快速路由)
- [模板分组](#模板分组)
- [使用规则](#使用规则)
- [高频模板](#高频模板)
- [详细模板索引](#详细模板索引)

## 场景直跳表

优先用本表直接跳到目标模板或子文件；不要先通读所有模板。

| 场景或机器信号 | 读取位置 |
| --- | --- |
| 缺本地行情或联网授权 | 本文件 [无法直接选股](#无法直接选股) |
| 用户要求隐藏边界或直接给名单 | 本文件 [用户要求直接给名单但缺数据源](#用户要求直接给名单但缺数据源)、[用户要求直接给结论但要求隐藏边界](#用户要求直接给结论但要求隐藏边界) |
| `partial_result=true`、分页失败、请求截止日无交易行、前导零损坏、离线依赖缺失 | [output-templates-source-and-input.md](./output-templates-source-and-input.md) |
| `output_written=false`、manifest/artifact 门禁、清洗、sizing 字段、涨跌停探针 | [output-templates-artifact-gates.md](./output-templates-artifact-gates.md) |
| prediction 缺字段、预测列冲突、LightGBM prediction 部分成功、历史窗口不足 | [output-templates-prediction.md](./output-templates-prediction.md) |
| buy-hold、资金曲线、overlap、可交易性和交易成本边界 | [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md) |
| 全 A / 全市场真实任务 | 本文件 [全 A 严格任务汇报骨架](#全-a-严格任务汇报骨架) |
| `effective_empty_result=true` 且 `candidate_rows=0` | 本文件 [0 候选解释](#0-候选解释) |
| 已有候选，需要最终汇报 | 本文件 [候选结果](#候选结果) |

## 快速路由

| 看到的字段或场景 | 使用模板 | 必须保留的边界 |
|------------------|----------|----------------|
| 缺本地行情或联网授权 | 无法直接选股 / 用户要求直接给名单但缺数据源 | 不输出候选代码、名称或模拟理由 |
| `partial_result=true` 或分页失败 | 东方财富实时快照部分成功 / 联网取数尚未完成校验 | 不能写成全市场实时扫描完成 |
| `output_written=false` 或 strict gate 非 0 | 对应失败模板，如历史窗口不足、prediction-derived 缺 prediction | 不能写成 0 候选成功 |
| `effective_empty_result=true` | 0 候选结果 | 说明成功空结果原因，不证明策略有效 |
| `prediction_source=external_unverified` | prediction-derived prediction 仅为外部输入 | 不能说预测源真实、训练质量或无泄漏已证明 |
| `prediction_model_executed_by_score_script=false` | 评分脚本只消费预测列 | 不能说 score_candidates 训练或执行了预测模型 |
| `volume_unit_verification=not_verified_by_cli` | CLI 未从纯数值验证成交量单位 | 不能写成已确认股、手、张或成交额未混用 |
| `prediction_input_source=not_used` 或 `mode=generic` | 今日入口 generic 技术评分 | 不能写成 prediction-derived/LightGBM 结果 |
| `prediction_model_executed_by_runner=false` | 今日入口或外部 prediction 评分 | 不能说 runner 训练或执行了预测模型 |
| `requested_prediction_input_source=external_input` 且 `consumes_prediction_columns=false` | 请求了 prediction 口径但本次未实际消费预测列 | 不能说已经使用 prediction 列完成评分 |
| `spot_matched_symbols` | spot 展示字段实际匹配到评分股票数 | 不能证明实时全市场扫描完整 |
| `coverage_class=local_input` | 本轮是本地价格文件评分 | 不能写成真实全市场扫描 |
| `coverage_class=spot_derived_sample` | 本轮使用默认小样本上限 | 不能写成扩大股票池或全 A |
| `coverage_class=spot_derived_limited_pool` | 本轮使用显式 spot 派生历史池上限 | 必须继续核对 `selected_symbols.json`、`history_metadata.json`、`summary.json` 后才可描述覆盖范围 |
| `candidate_field_coverage` | 候选表中可选字段的实际写出覆盖率 | 不能写成市场覆盖或数据完整性证明 |
| `full_market_claim_allowed=false` | runner 不允许自动宣称全市场闭环 | 必须按 `full_market_claim_boundary` 缩短结论 |
| 全 A / 全市场真实任务 | 全 A 严格任务汇报骨架 | 不能只报候选数，必须报股票池收口过程 |
| `lightgbm_*` 字段 | 旧产物兼容字段 | 新报告优先引用中性的 prediction 字段 |
| `html_report_written=true` | 人类可读 HTML 报告已写出 | 不能替代 JSON/CSV、退出码或门禁字段 |
| `html_report_enabled=false` 或 stdout `html_report=disabled` | HTML 展示层被主动关闭 | 不能写成报告生成失败，也不能替代 JSON/CSV 和退出码 |
| `html_report_written=false` 且 `html_report_error_type` 非空 | HTML 展示层写出失败 | 不能改写候选、诊断、退出码或 strict gate 事实 |
| `selection_failed_reason` / `selection_failed_next_action` | 预检失败时的可读原因与下一步 | 不能写成路径通过或数据已恢复 |
| `html_report_language=auto` | HTML 初始语言跟随运行环境，且浏览器内可切换 | 不能改变机器字段或事实口径 |
| `input_metadata.source_type=synthetic_demo` | 输入来自 `create_demo_data.py` 合成 demo | 不能写成真实行情、真实预测或真实选股结论 |
| `input_metadata={}` 或未声明 `real_market_data=true` | 本地行情文件来源未证明 | 不能写成真实行情源、今日全市场扫描或数据覆盖已验证 |
| `input_csv_provenance.real_market_data=mixed/unknown` 或 `input_csv_provenance.source_scope=mixed/unknown` | 本地行情文件来源未证明 | 不能把部分行来源声明写成全量真实行情证明 |

## 今日入口 mode 和输出检查

`mode=generic/prediction/auto` 只是评分口径选择，不是全 A 工作流选择。只要用户目标是全 A、全市场或扩大股票池，先按 [full-a-strict-workflow.md](full-a-strict-workflow.md) 走完数据路径，再决定最终评分 `mode`。

| mode | 触发条件 | 必须披露 |
| --- | --- | --- |
| `auto -> generic` | 缺少 prediction-derived 必需列 | `mode_decision_reason`、`prediction_input_source=not_used` |
| `auto -> prediction` | 输入同时包含 `market` + (`prediction` 或 `prediction_score`) + (`turn` 或 `turnover`) | `prediction_input_source=external_input`、`prediction_model_executed_by_runner=false` |
| `prediction` | 用户坚持 prediction-derived 口径 | 缺字段时必须失败，不能自动改 generic |
| `generic` | 用户明确接受通用技术评分 | 不得写成 prediction-derived 或模型预测结果 |

generic 技术评分不消费输入中的 `prediction` 或 `prediction_score` 列；即使原始文件带有这些列，候选和诊断输出也应披露 `prediction_input_source=not_used`，并以技术因子计算 `trend_score`。

输出检查重点：

| 文件 | 检查字段 |
| --- | --- |
| `run_manifest.json` | 每一步命令、退出码、stdout/stderr、允许退出码 |
| `summary.json` | `requested_mode`、`mode`、`mode_decision`、`prediction_input_source`、`prediction_model_executed_by_runner`、`source_scope`、`source_provenance`、`coverage_class`、`candidate_field_coverage`、`summary_output_written`、`manifest_output_written`、`full_market_claim_allowed`、`selection_failed_reason`、失败步骤 |
| `candidates.csv` | 候选字段、spot 展示字段、prediction 披露字段；prediction-derived 时检查 `prediction_source`、`prediction_input_source`、`prediction_model_executed_by_score_script` |
| `diagnostics.csv` | 机器字段 `failed_thresholds`，展示字段 `failed_thresholds_zh`、`selection_status`、`short_reason`，以及与候选一致的 prediction 披露字段 |
| `report.html` | 候选、诊断、步骤和证据路径的人类可读汇总；支持中英文切换，只读已有 JSON/CSV |
| `spot_metadata` | `partial_result`、`failed_pages`、`retry_attempts_per_page`、`allowed_failure_actions` |

`lightgbm_not_used`、`lightgbm_output_source`、`lightgbm_executed_by_runner` 是旧产物兼容字段；报告时优先引用中性的 prediction 字段。

## CLI 摘要和门禁字段

`score_candidates.py` 的 CLI 摘要会输出 `input`、`input_symbols`、股票池过滤、历史不足、单股失败、阈值过滤、`turnover_assumption`、`effective_empty_result`、`empty_result_reason` 和 `candidates`。直接调用 Python API 时，`input` 字段由调用方记录或注入。

| 字段 | 含义 | 不能外推 |
| --- | --- | --- |
| `effective_empty_result=true` | 成功运行但没有候选 | 策略有效或候选生成通过 |
| `output_written=false` | 严格门禁失败或输入失败 | 成功 0 候选 |
| `prediction_source=external_unverified` | 预测列为外部输入 | 上游模型真实或无泄漏 |
| `prediction_model_executed_by_score_script=false` | 评分脚本未执行预测模型 | 上游生成器已通过 |
| `threshold_failures` | 各阈值独立失败次数 | 与 `threshold_failed_symbols` 相加对账 |

解释规则：

- `effective_empty_result=true` 表示脚本成功运行但阈值或股票池过滤后没有候选。
- `empty_result_reason` 会区分 `universe_filtered_all`、`threshold_filtered_all` 等成功空结果原因。
- 所有股票都因历史不足或输入异常无法评分时，脚本应显式失败。
- `validate_ohlcv.py --min-history-rows 0` 或低于评分配置的历史门槛，只能证明基础字段和 profile 字段校验通过，不能证明可评分。
- `slice_prices_as_of.py` 退出 0 只说明切片文件写出且非空；仍要检查实际信号日并对切片后的文件重新校验。
- `threshold_failures` 是各阈值独立失败计数，不是互斥分类。
- `failed_symbols>0` 表示存在单股运行期异常，即使输出其他候选，也应进入复核或失败处理。

## 恢复动作快速路由

先判定失败类型，再决定下一步，不要一看到 `output_written=true` 或 HTML 存在就继续向用户展示结果。

| 机器信号 | 先读哪个产物 | 推荐下一步 | 不能误判 |
| --- | --- | --- | --- |
| `partial_result=true` | `spot_metadata.json`、`summary.json` | 先决定是否补抓分页；必要时重跑 spot，再继续历史抓取 | 不能写成实时全市场扫描完成 |
| `failed_symbols`、`empty_symbols`、`possibly_truncated_symbols` 非空 | `history_metadata.json`、`run_manifest.json` | 调整 provider 参数、降低批次或拆轮次重跑 | 不能把部分写出当成全量历史抓取成功 |
| `invalid_rows>0`、`non_trading_rows>0`、`st_rows>0` | `history_metadata.json` | 先形成清洗清单，再重跑 clean history | 不能把 strict gate failed 说成 0 候选成功 |
| `output_written=false` 或 validate 非 0 | `summary.json`、validate stderr | 回到 `validate_ohlcv.py` 或输入数据修复 | 不能直接进入评分或 HTML 汇报 |
| `candidate_rows=0` 且 `effective_empty_result=true` | `summary.json`、`diagnostics.csv` | 使用“0 候选结果”模板，解释真实过滤原因 | 不能写成策略一定无效或数据一定失败 |
| `source_scope=unknown` 且本轮使用 `--prices-input` | `summary.json`、输入目录中的 provenance 文件 | 确认同目录至少存在 `metadata.json` 或 `history_metadata.json`，必要时补齐 provenance 后再复跑 | 不能把 provenance 丢失的结果写成真实来源已证明 |

## 模板分组

| 分组 | 文件 | 什么时候读取 |
| --- | --- | --- |
| 高频模板 | 本文件 | 缺数据源、隐藏边界、全 A 汇报、0 候选、最终候选 |
| 数据源和输入质量 | [output-templates-source-and-input.md](./output-templates-source-and-input.md) | external source、日期、前导零、partial fetch、环境依赖 |
| artifact 和门禁 | [output-templates-artifact-gates.md](./output-templates-artifact-gates.md) | manifest、summary、sizing、价格一致性、清洗和字段探针 |
| 回测和组合 | [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md) | buy-hold、资金曲线、overlap、可交易性和交易成本边界 |
| prediction-derived | [output-templates-prediction.md](./output-templates-prediction.md) | prediction 字段、LightGBM 产物、历史窗口和预测口径门禁 |

## 使用规则

- 只引用本次 run 中实际存在的字段。
- `output_written=false`、strict gate 非 0、输入门禁失败时，不得改写成成功空结果。
- 历史报告中的旧 stdout 必须按历史原文引用；当前新报告优先引用中性 prediction 字段。
- 中文诊断字段只能从机器字段派生，不能覆盖 `failed_thresholds` 等机器事实。
- `report.html` 只作为展示层引用；语言切换只改变展示文本，发现冲突时以 `summary.json`、`run_manifest.json`、CSV 和退出码为准。
- 用户直接要求给候选名单但缺少可验证数据源时，优先使用“用户要求直接给名单但缺数据源”模板。

## 高频模板

### 无法直接选股

```markdown
## 无法直接选股
- 缺少本地行情文件或明确数据源，不能生成候选股。
- 不能提供示例候选名单，也不能用常识、记忆行情或热门股补全名单和理由。
- 已提供的市场、周期或目标风格可以保留；仍缺少 CSV/Parquet 路径或明确联网取数授权时不能继续。
- 如市场、周期、时间范围或目标风格也未提供，需要一并补充。
- 本地行情最小字段：`symbol`、`date`、`open`、`high`、`low`、`close`、`volume`。
- 可验证后再执行：先校验数据，再评分和解释结果。
```

### 用户要求直接给名单但缺数据源

```markdown
我现在不能直接给出股票名单。

你已经给了市场或风格，但缺少可验证行情文件或明确联网取数授权；我不能用热门股、记忆行情、常识或模拟数据补候选和理由。可执行路径是先落地真实 CSV/Parquet 或授权联网取数，再运行校验和评分脚本。没有这些输入前，候选名单、入选理由和收益判断都不能生成。
```

### 用户要求直接给结论但要求隐藏边界

```markdown
我现在不能只给结论而省略边界。

你要求直接给结论，但本任务必须保留数据源、门禁和非投资建议边界。不能省略数据源、门禁和非投资建议边界。
- 非投资建议
- 非交易指令
- 非真实成交
- 非收益证明
```

### 联网取数尚未完成校验

```markdown
## 暂不能给出候选名单
- 可以联网取数，但在线响应必须先分别落地为本地 CSV/Parquet，并记录数据源、时间范围、复权口径、交易日历和 metadata。
- A 股、港股和美股的交易日历、成交量单位、换手率字段、复权口径和交易币种不同，不能无说明地混合排序。
- 缺少真实 `turn` 或 `turnover` 时，不能自行估算并当作真实换手率；yfinance 通用链路只能披露 `turnover_assumption=neutral_series_missing_turnover`。
- 数据窗口必须覆盖评分配置的最小历史行数；最近一个月通常不足默认 120 行历史，可能导致历史不足或候选不足。
- 只有 `validate_ohlcv.py` 和 `score_candidates.py` 完成后，才能按真实输出解释候选、0 候选或不足 5 只的原因。
```

### 全 A 严格任务汇报骨架

```markdown
## 全 A 严格任务结果
- 本轮目标: 全 A / 全市场真实广度扫描，不是 demo，也不是固定小样本复验。
- 执行路径: `execution_path`、`execution_path_reason`、`coverage_class`。
- 字段覆盖率: `candidate_field_coverage`。
- 全市场声明边界: `full_market_claim_allowed`、`full_market_claim_boundary`。
- 快照范围: `spot_metadata.json` 的 `raw_items/filtered_items/requested_pages/successful_pages/partial_result`。
- 历史抓取范围: `selected_symbols.json` 或 `history_metadata.json` 中的初始历史样本数。
- 清洗过程: 说明剔除了多少只、按什么原因剔除，例如 `invalid_rows/non_trading_rows/st_rows/history_rows不足`。
- 最终有效股票池: `validate` 通过后的 `symbol_count` 或 `prices_rows` 对应的去重股票数。
- 诊断结果: `diagnostic_rows`。
- 最终候选: `candidate_rows`。
- 字段覆盖率卡片: `candidate_field_coverage`。
- 数据来源: 历史源 `source/source_scope`，实时快照源 `spot source/source_scope`。
- 必须保留边界:
  - 非实时全市场成交证明
  - 非真实收益证明
  - 非券商订单或真实成交容量证明
  - 外部源长期稳定性未证明

如果 `report.html` 没有直接展示“初始历史样本数 -> 清洗剔除数 -> 最终有效股票池”的链路，必须在文字汇报中手动补齐，不能只贴页面或只报候选数量。
```

### 本地行情来源未证明

```markdown
## 本地输入文件来源未证明
- 本次只验证了本地行情文件的字段、格式和评分流程，不能证明它是真实行情源、今日全市场覆盖或完整交易日历数据。
- 必须披露 `source_scope`、`runner_source_scope`、`input_metadata`、`input_csv_provenance`、价格文件路径、信号日期或文件内 `date_min/date_max`。
- 当 `input_metadata={}` 或未声明 `real_market_data=true` 时，只能称为“本地输入文件评分结果”，不能写成“今日真实 A 股候选”。
- 当 `input_csv_provenance.real_market_data`、`input_csv_provenance.source_scope` 或 `input_csv_provenance.source_claim_boundary` 为 `mixed`、`unknown` 或空值时，只能说明 CSV 内嵌来源信息不完整或混合，不能把部分行的真实来源声明外推为全文件真实行情证明。
- 若需要真实行情口径，必须补齐数据源、抓取时间、复权口径、交易日历、覆盖范围和 metadata，再重新校验和评分。
```

### 0 候选解释

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
- 如果同时使用 `--fail-on-empty-result`，`ERROR_SUMMARY` 只是失败摘要；`output_not_written=true` 且退出码非 0 时，不能说候选生成通过。
```

### 候选结果

```markdown
## 策略口径
- 市场和周期：
- 数据窗口：
- 股票池过滤：
- 因子和权重：
- `requested_mode/mode/mode_decision`：
- `prediction_mode/consumes_prediction_columns/prediction_input_source/requested_prediction_input_source/prediction_model_executed_by_runner`：
- 兼容字段 `lightgbm_not_used/lightgbm_output_source/lightgbm_executed_by_runner`：
- `source_scope`：
- `input_metadata`：

## 候选结果
| rank | symbol | name | market | listing_board | spot_industry/industry | date | close | spot_price | spot_pct_chg | total_score | key_reasons | risk_notes |
|------|--------|------|--------|---------------|---------------|------|-------|------------|--------------|-------------|-------------|------------|

## 过滤摘要
- 输入股票数：
- `prices_rows/candidate_rows/diagnostic_rows`：
- `spot_rows/spot_matched_symbols`：
- 剔除数量和原因：
- 最终候选数：

## 验证与限制
- 已验证：
- 未验证：
- 数据限制：
- 证据路径：
- HTML 报告：
- 输入 metadata：
- `volume_unit_verification`：
- `prediction_source`：
- `prediction_model_executed_by_score_script`：
- `raw_symbols/predicted_symbols/skipped_symbols`：
- `tradability_model`：
- `limit_rules_model`：
- `portfolio_violations`：
- `manifest_validation`：
- `artifact_validation`：
- 非投资建议：
- 非交易指令：
- 非真实成交：
- 非收益证明：
```

## 详细模板索引

以下条目只作为路由索引；需要正文时读取对应同级文件。

### output-templates-source-and-input.md

- 联网取数截止日不是实际最后交易日: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- 东方财富实时快照部分成功: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- 中文诊断只作展示层: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- Akshare fallback 成功: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- Yfinance 复权口径: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- Yfinance market 标签不是市场证明: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- Yfinance 部分取数成功: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- P3 外部源复验不是长期稳定证明: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- 前导零损坏: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- 日期格式归一化重复: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- 全 Parquet 链路未支持: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- 离线依赖缺失: [output-templates-source-and-input.md](./output-templates-source-and-input.md)
- Python API 复用边界: [output-templates-source-and-input.md](./output-templates-source-and-input.md)

### output-templates-artifact-gates.md

- P1 门禁证据不足: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- Artifact 未校验 manifest 报告: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- 组合 allocation 裁剪: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- 组合容量字段不完整: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- 信号日价格不一致: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- As-of 日期不等于候选信号日: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- Summary 诊断报告未通过: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- Summary 模型口径门禁未启用: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- Baostock 涨跌停字段探针: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- Drop-invalid 数据口径: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- Sizing/资金字段覆盖: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)
- 配置和摘要口径: [output-templates-artifact-gates.md](./output-templates-artifact-gates.md)

### output-templates-backtest-portfolio.md

- 严格回测 incomplete: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)
- Entry/exit-only 可交易性: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)
- 全持有期 observed bar 可交易性: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)
- 零成本 Buy-hold 基线: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)
- 资金曲线含 incomplete trades: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)
- 资金曲线等权口径: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)
- Overlap 日历口径不是交易所日历: [output-templates-backtest-portfolio.md](./output-templates-backtest-portfolio.md)

### output-templates-prediction.md

- prediction-derived 缺少 prediction: [output-templates-prediction.md](./output-templates-prediction.md)
- prediction-derived 预测列冲突: [output-templates-prediction.md](./output-templates-prediction.md)
- 基础 OHLCV 不是 prediction-derived 输入: [output-templates-prediction.md](./output-templates-prediction.md)
- LightGBM prediction 部分成功: [output-templates-prediction.md](./output-templates-prediction.md)
- 历史窗口不足: [output-templates-prediction.md](./output-templates-prediction.md)
- 切片后历史窗口不足: [output-templates-prediction.md](./output-templates-prediction.md)
