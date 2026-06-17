# Output Templates

本文件是汇报模板库。先用“快速路由”按机器字段定位模板，再复制对应代码块并填入本次 run 的真实字段。不要把模板中的占位项当作事实。

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
| `lightgbm_*` 字段 | 旧产物兼容字段 | 新报告优先引用中性的 prediction 字段 |
| `html_report_written=true` | 人类可读 HTML 报告已写出 | 不能替代 JSON/CSV、退出码或门禁字段 |
| `html_report_enabled=false` 或 stdout `html_report=disabled` | HTML 展示层被主动关闭 | 不能写成报告生成失败，也不能替代 JSON/CSV 和退出码 |
| `html_report_written=false` 且 `html_report_error_type` 非空 | HTML 展示层写出失败 | 不能改写候选、诊断、退出码或 strict gate 事实 |
| `html_report_language=auto` | HTML 初始语言跟随运行环境，且浏览器内可切换 | 不能改变机器字段或事实口径 |
| `input_metadata.source_type=synthetic_demo` | 输入来自 `create_demo_data.py` 合成 demo | 不能写成真实行情、真实预测或真实选股结论 |
| `input_metadata={}` 或未声明 `real_market_data=true` | 本地行情文件来源未证明 | 不能写成真实行情源、今日全市场扫描或数据覆盖已验证 |
| `input_csv_provenance.real_market_data=mixed/unknown` 或 `input_csv_provenance.source_scope=mixed/unknown` | 本地行情文件来源未证明 | 不能把部分行来源声明写成全量真实行情证明 |

## 模板分组

| 分组 | 典型标题 | 用途 |
| --- | --- | --- |
| 数据源缺口 | 无法直接选股、联网取数尚未完成校验 | 阻止无数据输出候选 |
| 输入质量 | 前导零损坏、日期格式重复、基础 OHLCV 不是 prediction-derived 输入 | 解释输入为什么不可评分 |
| 实时和外部源 | 东方财富部分成功、Akshare fallback、Yfinance 口径 | 披露 source scope 和部分结果 |
| artifact 门禁 | P1、manifest、summary、价格一致性、组合容量 | 防止把局部 artifact 写成全链路通过 |
| 回测和组合 | buy-hold、资金曲线、overlap、tradability | 区分 baseline、sizing、真实可交易性 |
| prediction-derived | 缺 prediction、预测列冲突、LightGBM 部分成功、0 候选 | 保留预测来源和模型质量边界 |
| 候选输出 | 候选结果 | 规范最终结果汇报结构 |

## 使用规则

- 只引用本次 run 中实际存在的字段。
- `output_written=false`、strict gate 非 0、输入门禁失败时，不得改写成成功空结果。
- 历史报告中的旧 stdout 必须按历史原文引用；当前新报告优先引用中性 prediction 字段。
- 中文诊断字段只能从机器字段派生，不能覆盖 `failed_thresholds` 等机器事实。
- `report.html` 只作为展示层引用；语言切换只改变展示文本，发现冲突时以 `summary.json`、`run_manifest.json`、CSV 和退出码为准。
- 用户直接要求给候选名单但缺少可验证数据源时，优先使用“用户要求直接给名单但缺数据源”模板。

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

### 本地行情来源未证明

```markdown
## 本地输入文件来源未证明
- 本次只验证了本地行情文件的字段、格式和评分流程，不能证明它是真实行情源、今日全市场覆盖或完整交易日历数据。
- 必须披露 `source_scope`、`runner_source_scope`、`input_metadata`、`input_csv_provenance`、价格文件路径、信号日期或文件内 `date_min/date_max`。
- 当 `input_metadata={}` 或未声明 `real_market_data=true` 时，只能称为“本地输入文件评分结果”，不能写成“今日真实 A 股候选”。
- 当 `input_csv_provenance.real_market_data`、`input_csv_provenance.source_scope` 或 `input_csv_provenance.source_claim_boundary` 为 `mixed`、`unknown` 或空值时，只能说明 CSV 内嵌来源信息不完整或混合，不能把部分行的真实来源声明外推为全文件真实行情证明。
- 若需要真实行情口径，必须补齐数据源、抓取时间、复权口径、交易日历、覆盖范围和 metadata，再重新校验和评分。
```

### 联网取数截止日不是实际最后交易日

```markdown
## 请求截止日未必有交易行
- fetch metadata 中的 `end_date` 是请求截止日，不保证该日存在交易数据。
- 当 `end_date` 落在周末、节假日或非交易日时，必须以 metadata 中每个 symbol 的 `date_max` 作为实际最后数据日。
- fetch 命令退出 0、CSV 写出和 `validate_ohlcv.py` 通过，只说明取数和基础 OHLCV 校验通过，不证明请求截止日当天有行情行。
- 报告时必须同时披露 `history_selection.requested_end_date`、`history_metadata_actual_date_max`、`history_metadata_end_date_has_rows`、逐 symbol `date_min/date_max`、`failed_symbols` 和 `empty_symbols`。
- 不能把非交易日 `end_date` 写成实际信号日、覆盖日或可回测入场日。
```

### 东方财富实时快照部分成功

```markdown
## 实时快照只覆盖部分分页
- 东方财富或其他实时快照源发生分页断连、超时或部分页失败时，不能写成全市场实时扫描完成。
- 必须披露 `source`、`source_scope`、`requested_pages`、`successful_pages`、`failed_pages`、`raw_items`、`filtered_items`、`snapshot_time` 和 `partial_result`。
- 如果后续评分只使用已成功落地的快照或前 N 个标的，只能称为固定实时样本池，不是全市场 universe。
- 使用已落地快照继续历史日线、校验和评分时，应同时披露快照时间、样本池来源、落地标的数、历史日线 `symbol_count`、`failed_symbols`、`empty_symbols` 和实际 `date_max`。
- 不能把分页失败后的 partial result、缓存快照或已落地旧快照翻译成实时全市场成功。
```

### 中文诊断只作展示层

```markdown
## 中文诊断不替代机器字段
- `failed_thresholds_zh`、`selection_status`、`short_reason` 等中文字段只能从原始机器字段派生。
- 必须保留 `failed_thresholds`、`threshold_failures`、`effective_empty_result`、`empty_result_reason`、`failed_symbols`、`empty_symbols`、`fallback_errors`、`partial_result`、`output_written` 等可审计字段。
- 中文摘要不能改变退出码、strict gate、fallback、partial fetch、0 候选或 output_not_written 的真实含义。
- 如果英文机器字段显示 `strict gate failed`、`partial_result=true`、`output_written=false` 或 `fallback_errors` 非空，中文摘要必须同步写成失败、部分结果或 fallback，而不是写成成功。
```

### Akshare fallback 成功

```markdown
## Akshare 取数使用了 fallback
- 命令退出码为 0 但 `fallback_errors` 非空时，不能写成主接口稳定成功。
- 必须披露主接口错误、`fallback_errors` 数量，以及 metadata 中逐标的 `provider`。
- `failed_symbols=[]` 只说明最终没有标的完全失败，不代表主接口无异常。
- 合规表述是“主接口失败后 fallback provider 取数成功”；不能外推为真实公网数据源长期稳定。
```

### Yfinance 复权口径

```markdown
## Yfinance 当前使用原始 Close
- `fetch_yfinance_ohlcv.py` 当前使用 `auto_adjust=False`，输出 CSV 的 `close` 来自原始 `Close`。
- metadata 中 `adjustment=auto_adjust_false_close` 不等于已使用复权价。
- 不能把 yfinance 返回中存在 `Adj Close` 写成脚本已经用于评分。
- 若用户要求复权价，需要显式改造脚本和 metadata 口径，再重新落地、校验和评分。
```

### Yfinance market 标签不是市场证明

```markdown
## Yfinance market 只是输出标签
- `fetch_yfinance_ohlcv.py --market` 只把标签写入 CSV 和 metadata，不校验 symbol 所属市场、交易所或交易日历。
- metadata 会写出 `market_label_only=true` 和 `source_claim_boundary=market_label_not_source_exchange_or_calendar_proof`；这些字段是边界披露，不是市场证明。
- metadata 中 `source=yfinance`、`market=A-share` 和基础 `validate_ohlcv.py` 通过，不能写成 A 股数据源或 A 股交易日历门禁通过。
- 如果 symbol 仍是 `AAPL` 这类非六位代码，prediction-derived A 股 profile 应按 symbol 格式门禁显式失败。
- 常见错误文本是 `prediction-derived A-share symbols must be six digits` 和 `market labels do not prove A-share source or calendar`。
- 报告时必须披露真实数据源、requested symbols、market 标签来源，以及 prediction-derived profile 校验结果。
```

### Yfinance 部分取数成功

```markdown
## Yfinance 只写出了部分行情
- 命令退出码为 0 但 `failed_symbols` 或 `empty_symbols` 非空时，不能写成所有 requested symbols 都成功落地。
- 必须披露 `requested_symbols`、`symbol_count`、`failed_symbols`、`empty_symbols` 和每个 symbol 的行数。
- `rows>0`、CSV 存在或 `output_written=true` 只说明至少有部分行情写出，不等于全量取数成功。
- 若 partial fetch 应作为门禁失败，必须使用 `--fail-on-fetch-error` 并按非 0 退出处理。
```

### P3 外部源复验不是长期稳定证明

```markdown
## 外部源稳定性仍未证明
- `probe_external_source_stability.py` 的 `all_sources_all_iterations_passed=true` 只说明 akshare、Yahoo/yfinance、baostock 和 zzshare 在当前窗口、当前参数和当前网络环境下连续复验通过。
- 必须披露 `long_term_stability_claim=not_proven`，不能写成 akshare、Yahoo/yfinance、baostock 或 zzshare 长期稳定。
- akshare 的 `hist_provider_clean=false` 是主接口异常观察项；即使总控脚本退出 0，也只能写“fallback provider 成功”，不能写 `stock_zh_a_hist` 稳定。
- 报告时必须列出各源 metadata 的逐标的 `date_max`；yfinance 的实际最后交易日仍以每个 symbol 的 `date_max` 为准，可能早于请求 `end_date`。
- `timeout_seconds` 只记录本次等待上限，不证明公网稳定。
- baostock fetch 通过仍只覆盖本次 symbols、日期范围、`adjustflag` 和 metadata 门禁；不证明涨跌停规则、券商成交或长期服务稳定。
- zzshare fetch 通过仍只覆盖本次 symbols、日期范围、`fields`、`limit/max_pages`、token/限流配置和 metadata 门禁；无 token 成功不证明无限免费额度或长期服务稳定。
- 通过 runner 使用 zzshare 时，报告必须披露 `history_request_interval_seconds`、`history_limit`、`history_max_pages` 和 `history_token_configured`；token 只能来自 `ZZSHARE_TOKEN` 环境变量，不能写入 runner 命令或报告正文。
```

### 前导零损坏

```markdown
## 输入数据需要先修复
- `symbol` 看起来已被表格软件或上游处理损坏，例如 `000002` 变成 `2`。
- 不能静默左侧补零后继续评分；这会掩盖源数据质量问题。
- 可接受路径：生成可审计的修复副本，明确修复规则和影响行数，再重新运行 `validate_ohlcv.py`。
- 校验通过前不能输出候选股、回测收益或策略结论。
```

### 日期格式归一化重复

```markdown
## 输入日期存在重复
- `YYYY-MM-DD` 和 `YYYYMMDD` 都是支持格式，但会解析为同一个真实交易日。
- 同一 `symbol` 下 `2026-05-29` 和 `20260529` 这类重复不能当成两天数据。
- `validate_ohlcv.py` 或 `score_candidates.py` 返回 duplicate symbol/date 时，应先修复源文件并重新校验。
- `output_written=false` 不是 0 候选成功，校验通过前不能输出候选或回测结论。
```

### 全 Parquet 链路未支持

```markdown
## 当前不支持严格全 Parquet 中间产物
- 当前脚本支持读取 CSV/Parquet，但标准 CLI 链路的中间产物默认写 CSV。
- 如果要求执行过程中完全不出现 CSV，必须先停止并说明需要改造脚本输出、runner 固定路径、artifact validator 和测试。
- 不能先写 CSV 再转换为 Parquet 后声称满足无 CSV。
- 只有用户明确允许临时 CSV 时，才可把每一步 CSV 输出显式转换为 Parquet 后继续。
```

### P1 门禁证据不足

```markdown
## 不能仅凭 manifest 宣称 P1 通过
- `run_manifest.json` 和 manifest validator 只证明命令步骤、退出码和门禁参数符合预期。
- P1 通过还必须检查 `run_manifest_validation.json`、`run_artifact_validation.json`、真实 metadata、prediction summary、回测、权益曲线、allocation summary 和 overlap summary。
- `portfolio_cash_lot_floor` 路径默认不应使用 `--expect-portfolio-violations`；`portfolio_violations` 必须为 0 才能说明当前组合容量门禁通过。
- `summarize_walk_forward_run.py --expect-portfolio-violations` 退出 0 且 `quality_errors=[]` 只表示已知组合违规被显式允许复现；`capacity_gate_pass=false` 或 `portfolio_violations>0` 仍不是组合容量门禁通过。
- `validate_walk_forward_artifacts.py` 退出 0 且 `errors=[]` 只表示 artifact 与传入期望一致；如果 `capacity_gate_pass=false` 或 `portfolio_violations>0`，说明复现的是已知组合违规，不是组合容量门禁通过。
- 即使 artifact validator 通过，也不能外推为真实成交容量、券商订单、涨跌停规则或全市场策略质量已验证。
```

### Artifact 未校验 manifest 报告

```markdown
## Manifest 门禁未纳入 artifact 复验
- `validate_walk_forward_artifacts.py` 未传 `--manifest-validation` 且 run 目录不存在 `run_manifest_validation.json` 时，不会校验 manifest 报告。
- 未传 `--manifest-validation` 但 run 目录存在 `run_manifest_validation.json` 时，artifact validator 会自动读取并校验该报告。
- `artifact_validation.json` 中 `manifest_checked=false` 是明确证据，不能说 manifest 门禁也通过；`manifest_checked=true` 但 `errors` 含 `manifest_errors` 时也不能说通过。
- `exit 0` 和 `errors=[]` 只表示当前 artifact 内容与传入期望一致，不覆盖 manifest validator 的步骤顺序、退出码或门禁参数。
- 如果同一 run 的 manifest validation 报告放在非默认路径，必须用 `--manifest-validation` 显式传入后重跑 artifact validator。
- 合规路径是检查 `run_manifest_validation.json`、确认 artifact validator 输出的 `manifest_checked` 和 `errors`，必要时显式传 `--manifest-validation`。
```

### 组合 allocation 裁剪

```markdown
## 组合 allocation 已裁剪候选
- `raw_candidates` 是组合容量裁剪前候选池，不等于最终进入回测或成交的数量。
- 后续回测应基于 `prediction_candidates.csv` / `prediction_sized_candidates.csv` 和 `allocated_candidates`。
- 如果 `skipped_candidates>0`，必须披露 `prediction_skipped_candidates.csv`、`skip_reason_counts` 和逐信号日 raw/allocated/skipped。
- 如果 `allocated_candidates=0`，即使命令退出 0 且 selected/sized CSV 已写出，也没有候选进入后续回测；只有表头的 CSV 不是有效候选表。
- 本地 `portfolio_cash_lot_floor` 仍不是券商订单、真实成交或真实现金容量证明。
```

### 组合容量字段不完整

```markdown
## 组合容量只完成部分字段门禁
- `portfolio_overlap_report.py` 可只针对已传入的单项字段执行门禁；退出码 0 不代表所有资本字段齐全。
- 必须披露 `capital_fields_present`、`capital_fields_missing`、`weight_capacity_verifiable` 和 `cash_capacity_verifiable`。
- `max_gross_notional` / `max_cash_reserved` 低于阈值，只证明这两个字段的金额门禁通过；若 `weight` 缺失，不能说权重容量已验证。
- 若需要完整资本字段门禁，必须使用 `--require-capital-fields`；若需要权重门禁，必须提供 `weight` 并使用 `--max-gross-weight`。
```

### 信号日价格不一致

```markdown
## Artifact 价格一致性门禁未通过
- 候选 `close` 和 sized `signal_close` 必须等于 `prices_signal_window.csv` 的原始信号日 close。
- `validate_walk_forward_artifacts.py` 返回非 0 且出现 `*_close_raw_mismatch` 或 `*_signal_close_raw_mismatch` 时，应按真实门禁失败处理。
- `artifact_validation.json` 被写出不代表通过；必须看退出码、`errors=[]` 和 stdout 的 `errors=0`。
- 可接受路径是修复可审计产物并重跑 validator，不能把原失败 run 改写成已通过。
```

### As-of 日期不等于候选信号日

```markdown
## 切片截止日不是实际信号日
- `slice_prices_as_of.py --as-of-date` 是包含该日期及之前的截断，不要求该日期本身存在交易行。
- 必须披露 stdout 中的 `date_max` 和 `actual_data_date`，并检查切片、候选、诊断或 HTML 报告中的 `requested_as_of_date`、`actual_data_date`、`as_of_date_observed`。
- 后续候选的真实信号日以候选 CSV 的 `date`、切片后的 `date_max` 或 `actual_data_date` 为准。
- 当 `as_of_date` 是周末、节假日或非交易日时，不能把请求的 as-of 日期写成候选信号日。
- 若必须验证精确信号日存在，应检查价格表和候选表的实际 `date`，或用后续 artifact price validator 做一致性门禁。
```

### Summary 诊断报告未通过

```markdown
## Summary/组合门禁未通过
- `prediction_run_summary.json`、`prediction_overlap_summary.json` 或 overlap CSV 已写出，只说明诊断产物可供审计。
- 退出码非 0、stderr 含 `strict gate failed`、`quality_errors` 非空或 `portfolio_violations>0` 时，不能写成资金曲线、组合容量或 P1 门禁通过。
- `output_written=true` 表示失败报告已落盘，不代表成功。
- 必须披露 `final_equity`、`max_drawdown`、`quality_errors` 和组合容量/重叠违规；受控样本的 `final_equity` 不能写成真实收益验证。
```

### Summary 模型口径门禁未启用

```markdown
## Summary 未验证模型口径
- `summarize_walk_forward_run.py` 省略 `--required-tradability-model` 或 `--required-limit-rules-model` 时，不会对对应模型口径执行严格门禁。
- 此时 `exit 0` 和 `quality_errors=[]` 只说明已启用的门槛通过，不能证明真实可交易性或涨跌停规则模型符合预期。
- 必须披露 summary JSON 中实际的 `tradability_models`、`limit_rules_models` 和 `model_gates_checked`。
- 若同一产物补传 required 参数后返回非 0，stderr 中的 `*_models=...` 才是模型口径未通过的门禁证据。
- 合规路径是用 required 参数重跑 summary，并以该严格命令的退出码、`quality_errors` 和 stderr 作为模型口径结论。
```

### Baostock 涨跌停字段探针

```markdown
## Baostock 字段探针结果
- `probe_baostock_limit_fields.py` 是字段可用性探测，不会推断或建模涨跌停规则。
- `schema_version=2` 起，`direct_limit_field_available` 只由 `supported_direct_limit_fields` 决定，不再表示任意候选字段可用。
- 默认退出码为 0 时仍必须披露 `unsupported_candidate_fields`、`provider_error_fields`、`available_control_fields`、`control_rows` 和 `limit_rules_model`。
- `provider_error_fields` 不是字段不支持；应保留 provider 错误码和错误信息，必要时用 `--fail-on-provider-error --require-control-rows` 作为严格门禁。
- 控制字段有样本行不等于真实可交易性、涨跌停或券商成交约束已验证。
- `preclose/pctChg/tradestatus/isST` 只是控制或诊断字段，不得用 `preclose + pctChg`、股票前缀或 `isST` 粗推真实涨跌停规则。
- `supported_direct_limit_fields` 只统计 `up_limit/down_limit/limit_status`；`is_trading` 或 `suspended` 即使可用，也只能作为交易状态或停牌字段线索，不能让 `limit_rules_model=not_modeled` 变成已建模。
```

### Drop-invalid 数据口径

```markdown
## 清洗后通过，不等于源数据无异常
- `--drop-invalid-rows` 只能说明取数阶段显式丢弃了已记录的异常行。
- 报告时必须同时披露 `invalid_rows`、`dropped_invalid_rows`、`raw_non_trading_rows`、`non_trading_rows` 和 `tradestatus_missing_rows`。
- 只有在 `invalid_rows == dropped_invalid_rows`，且清洗后 `non_trading_rows=0`、`tradestatus_missing_rows=0` 时，后续 validator 才能在显式 `--allow-dropped-invalid-rows` 下通过。
- 不能把 `quality_errors=[]`、summary 通过或 artifact validator 通过写成“源数据没有异常”。
```

### Sizing/资金字段覆盖

```markdown
## 不能静默覆盖候选 sizing/资金字段
- 候选表已有 `cash_budget`、`lot_size`、`capital_model`、`signal_close`、`cash_slot`、`quantity`、`cash_reserved`、`notional`、`weight` 或 `unallocated` 时，默认不能直接覆盖。
- 默认失败里的 `output_written=false` 是有效门禁证据，不能说已经生成 sized candidates。
- 只有用户明确确认要用本仓库 sizing 模型重算时，才显式传 `--overwrite-capital-fields`。
- 重算后必须披露 `capital_model`、`cash_budget` 和 `lot_size`；这仍不是券商订单、真实成交或真实现金容量证明。
```

### 严格回测 incomplete

```markdown
## 严格回测未通过
- `--fail-on-incomplete` 返回非 0 且 `output_not_written=true` 时，不能报告回测成功。
- `missing_future_price` 表示信号日之后没有足够的未来交易行，不是可忽略 warning。
- `missing_entry_price` 表示候选信号日没有精确入场价格；脚本不会自动顺延到下一交易日。
- 合规路径是提供覆盖持有期的价格数据，或改用更早信号日重新生成候选和 sizing。
- 不能跳过 incomplete trades、手写空回测文件，或把候选结果解释成 5 日 buy-hold 收益。
```

### Entry/exit-only 可交易性

```markdown
## 可交易性门禁范围
- `tradability_model=tradestatus_entry_exit_only` 只说明入场日和退出日 `tradestatus=1`。
- `--require-tradable-bars` 不扫描中间持有期每一行；中间日期 `tradestatus=0` 时仍可能得到 `status=complete`。
- `completed_trades>0` 和收益字段只属于 close-to-close 基线，不证明全持有期每天可交易、涨跌停可成交或券商成交约束。
- 必须同时披露 `limit_rules_model=not_modeled`。
```

### 全持有期 observed bar 可交易性

```markdown
## 已观测持有期可交易性门禁范围
- `tradability_model=tradestatus_holding_period_bars` 只说明价格表内从入场到退出的已观测 bar 均满足 `tradestatus=1`。
- `--require-tradable-holding-period` 会把中间持有期已存在价格行的 `tradestatus=0` 标为 `non_tradable_holding_period`，并可被 `--fail-on-incomplete` 拦截。
- 该门禁不补全价格表缺失日期，不证明真实交易所日历、节假日、特殊交易日、临时休市或全市场停复牌覆盖。
- 该门禁不覆盖涨跌停、真实订单、券商成交容量或滑点成交约束；必须同时披露 `limit_rules_model=not_modeled`。
```

### 零成本 Buy-hold 基线

```markdown
## 回测收益仍是零成本基线
- 默认未传 `--cost-bps` 和 `--slippage-bps` 时，`cost_bps=0.0`、`slippage_bps=0.0`。
- 此时 `return` 只是 `gross_return` 扣减 0 后的 close-to-close 基线结果，不是含真实交易成本和滑点的净收益。
- `exit 0`、`status=complete`、`completed_trades>0` 或输出 CSV 存在，只证明入场/出场价格和严格 incomplete 门禁通过。
- 必须披露 `cost_model`、`slippage_model`、`tradability_model` 和 `limit_rules_model`；`limit_rules_model=not_modeled` 仍不证明涨跌停或券商成交约束。
- 若要声称净收益口径，需要传入可追溯成本/滑点假设，或接入真实成交与交易规则模型后重跑。
```

### 资金曲线含 incomplete trades

```markdown
## 资金曲线不是全量回测通过
- `portfolio_equity_curve.py` 默认只用 complete trades 计算 `mean_return` 和 `final_equity`。
- `incomplete_trades>0` 时，`OK:`、输出 CSV 存在或 `final_equity` 不代表全部 trade 都参与了资金曲线。
- CSV 中 `weighting=equal_weight_completed_trades` 表示按完成交易等权计算。
- 若 incomplete 应作为门禁失败，必须使用 `--fail-on-incomplete`，并按非 0 退出和 `output_not_written=true` 处理；`ERROR_SUMMARY` 中的 `final_equity` 只是失败诊断值，不是通过证据。
```

### 资金曲线等权口径

```markdown
## 资金曲线未按 sizing 权重计算
- `portfolio_equity_curve.py` 的 `portfolio_model` 或 CSV `weighting=equal_weight_completed_trades` 表示按完成交易等权计算。
- 即使输入回测 CSV 含 `weight`、`notional`、`quantity` 和 `cash_reserved`，`final_equity` 也不是按这些 sizing 字段加权后的组合收益。
- `portfolio_overlap_report.py` 退出 0 且 `capital_fields_missing=[]`，只说明 overlap 报告检查了资本字段和容量阈值，不能反向证明资金曲线使用了权重。
- 如果按输入 `weight` 重算得到不同收益，应披露差异，不能把等权 `final_equity` 写成真实加权组合收益。
- 本地资金曲线仍不是真实成交容量、券商订单或真实组合收益证明。
```

### Overlap 日历口径不是交易所日历

```markdown
## Overlap 日历口径
- `portfolio_overlap_report.py` 的 `calendar_model=business_day_closed_interval` 表示脚本用 `pandas.bdate_range` 的普通工作日闭区间从 `entry_date` 展开到 `exit_date`。
- 该模型不是 A 股、美股或任一交易所日历，不校验节假日、临时休市、停复牌、涨跌停或全持有期真实可交易性。
- 普通工作日近似可能包含交易所休市日，例如法定节假日或特殊休市日；这些日期出现在 `daily_positions.csv` 时只能说明 overlap/capacity 近似口径覆盖了该工作日，不能证明当天是交易所可交易日。
- `daily_positions.csv` 中的日期只能作为本地组合重叠和容量报告的工作日近似口径；真实交易日历或真实可交易性需要额外数据源和门禁。
- 报告 overlap 结果时必须披露 `calendar_model`，不能把 `OK:`、`daily_rows` 或 `max_open_positions` 写成交易所日历门禁通过。
```

### 离线依赖缺失

```markdown
## 当前环境不能完成脚本验证
- 目标命令需要 `pandas`、`numpy` 或其他声明依赖，但完全离线环境没有可用解释器、虚拟环境、wheelhouse 或包缓存。
- 不能改用 mock 数据、跳过依赖，或把未运行脚本写成验证通过。
- 可接受路径：使用已安装依赖的解释器，或先准备离线 wheelhouse/缓存，再重新运行原命令。
- 依赖失败是环境门禁失败，不是策略结果、候选结果或回测结论。
```

### Python API 复用边界

```markdown
## Python 复用需要显式脚本路径
- 本仓库 CLI 是稳定入口，当前不是可安装 Python package。
- 复用脚本函数前，必须把仓库的 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。
- 不要把 `from skills/a-share-selection-strategy/scripts/score_candidates import ...` 当成稳定 API；它可能在 import 阶段成功，但调用时因内部顶层模块路径缺失而失败。
- `python3 -S skills/a-share-selection-strategy/scripts/<name>.py --help` 依赖轻量化门禁只覆盖带 `argparse`、`main()` 或 `__main__` 的 CLI 入口；`a_share_selection_*.py`、`lightgbm_prediction_summary.py` 等 helper/import 模块没有帮助界面承诺，顶层 pandas/numpy import 失败不应写成用户入口缺口。
- 使用 `skills/a-share-selection-strategy/scripts/*.py` 全量扫描时，必须先把真实 CLI 入口和 helper/import 模块分开；不能用 glob 扫描里的 helper 失败覆盖真实 CLI 入口的逐项验证结果。
- 直接调用 Python API 时，`input` 字段由调用方记录或注入，不能把 API 调用摘要说成完整 CLI 门禁。
```

### 配置和摘要口径

```markdown
## 配置和摘要口径
- `output.max_candidates=0` 表示不截断候选，不是输出 0 个候选。
- `max_candidates` 是排序后的 top-N 截断，不是阈值过滤；截断不增加 `threshold_failed_symbols`。
- `threshold_failed_symbols` 是被任意阈值过滤的唯一标的数。
- `threshold_failures` 是逐阈值失败次数，同一标的可能同时计入多个阈值，不能和 `threshold_failed_symbols` 相加对账。
```

### prediction-derived 缺少 prediction

```markdown
## 无法按 prediction-derived 原口径评分
- 输入缺少 `prediction` 或 `prediction_score`，不能生成 prediction-derived 候选股。
- 常见错误文本是 `prediction-derived profile requires prediction or prediction_score column`。
- `prediction` 是上游 LightGBM 概率，不得用动量分、固定 `0.5`、mock 值或技术指标近似冒充。
- 当前可做：
  - 先提供或生成可追溯的上游 `prediction_score`，再运行 prediction-derived 评分。
  - 只做字段质量检查时，可先运行 prediction-derived profile 校验，让缺失字段显式失败。
- 即使使用 `generate_lightgbm_predictions.py`，也必须单独核验训练窗口、标签、特征、时间序列切分、跳过标的和未来泄漏风险。
```

### prediction-derived 预测列冲突

```markdown
## 预测列口径需要先统一
- 输入同时包含 `prediction_score` 和 `prediction` 且数值不一致时，prediction-derived profile 校验和评分都会失败。
- 常见错误文本是 `prediction and prediction_score both exist but differ` 和 `unify upstream prediction columns before prediction-derived scoring`。
- 不能用较高的一列解释 `min_prediction_score` 阈值应通过，也不能让评分脚本静默选择其中一列继续。
- `output_written=false` 或 `code=bad_input` 表示输入门禁失败，不是成功 0 候选。
- 合规路径是先统一预测列或审计上游字段映射，再重新运行 prediction-derived profile 校验和评分。
```

### 基础 OHLCV 不是 prediction-derived 输入

```markdown
## prediction-derived 门禁未通过
- 无 config 的 `validate_ohlcv.py` 通过，只证明基础 OHLCV 字段、日期和数值有效。
- `slice_prices_as_of.py` 退出 0 只说明切片非空并写出，不会补齐 prediction-derived 必需字段。
- prediction-derived 仍必须包含 `market=A-share`、可追溯的 `prediction` 或 `prediction_score`，以及真实 `turn` 或 `turnover`。
- `score_candidates.py --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json` 报缺字段、`code=bad_input` 或 `output_written=false` 时，是输入门禁失败，不是成功 0 候选。
- 合规路径是补齐 prediction-derived 必需字段后，对切片文件重新运行 profile 校验和评分。
```

### LightGBM prediction 部分成功

```markdown
## LightGBM prediction 门禁未完整通过
- 非严格模式退出码为 0 但 `skipped_symbols>0` 时，只能说明部分标的写出了预测。
- 必须披露 `raw_symbols`、`predicted_symbols`、`skipped_symbols` 和 `skipped_symbol_examples`。
- 下游 `validate_ohlcv.py` 或 `score_candidates.py` 通过，只覆盖已写出的预测文件，不能反推上游全部标的通过。
- 完整门禁应使用 `--fail-on-skipped`，或显式确认 `raw_symbols == predicted_symbols` 且 `skipped_symbols == 0`。
- `prediction_summary.json` 中的 `feature_columns`、`split_method`、`scaler_fit_scope`、`label_definition`、训练/holdout 日期窗口和标签分布只是本次生成链路审计字段。
- `label_definition=target_return = close.shift(-horizon) / close - 1; class = target_return > train_mean` 只是相对训练集均值的二分类标签口径。
- `target_positive_labels` 和 `target_negative_labels` 非空只证明训练切分内两类标签都存在，不证明标签业务合理性、概率校准、holdout IC、跨窗口稳定性或样本外泛化。
- `holdout_auc` 只来自训练前缀之后、latest 之前的同一 symbol 时间后缀；`holdout_metric_status=not_computable` 时必须披露原因。它不是跨窗口、跨年份、分市场或全市场样本外泛化证明。
- `prediction_scope=latest_probability_repeated_for_scoring` 不是逐日历史预测序列；它表示最新预测概率被重复写入该标的评分窗口。
- `model_quality_scope=generation_audit_only` 和 `model_quality_metrics` 里的 `not_computed/not_evaluated/not_proven` 是机器可读边界声明，不是质量指标通过证明。
- 即使 summary 字段完整且 `holdout_auc` 可计算，也不能写成 LightGBM 模型质量、样本外泛化、IC、分层收益或全市场策略质量已证明。
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

### 历史窗口不足

```markdown
## 历史窗口不足，不能评分
- `validate_ohlcv.py --min-history-rows 0` 或低门槛校验通过，只说明基础字段、日期、数值和 profile 必需字段有效。
- 如果评分配置要求更长历史窗口，仍必须以 `score_candidates.py` 的 `insufficient_history_symbols` 和退出码为准。
- `code=bad_input output_written=false` 表示没有 symbol 可评分，不是成功的 0 候选结果。
- 合规表述是“debug 级字段校验通过，真实评分不可用，未产生候选”。
```

### 切片后历史窗口不足

```markdown
## 切片后仍不能评分
- 原始 prediction-derived 文件通过 `validate_ohlcv.py`，不代表 `slice_prices_as_of.py` 截断后的文件仍满足评分历史窗口。
- `slice_prices_as_of.py` 退出 0 只说明切片结果非空并已写出；必须披露切片 stdout 中的 `rows`、`date_min`、`date_max`、`actual_data_date` 和 `as_of_date_observed`。
- 对切片后的文件重新运行校验和评分；最终以 `score_candidates.py` 的退出码、`insufficient_history_symbols` 和 `output_written` 为准。
- `code=bad_input output_written=false` 或 `insufficient_history_symbols>0` 表示切片后不可评分，不是成功 0 候选。
- 合规表述是“原始文件校验通过、切片步骤成功，但切片后历史窗口未通过；需要选择更晚 as-of 日期或补足历史后重跑”。
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
