# Output Templates - Artifact 和门禁

本文件是 `output-templates.md` 的按需展开模板库。只有快速路由指向本类问题时才读取本文件；模板占位项不能当作事实。

## 目录

- [P1 门禁证据不足](#p1-门禁证据不足)
- [Artifact 未校验 manifest 报告](#artifact-未校验-manifest-报告)
- [组合 allocation 已裁剪候选](#组合-allocation-已裁剪候选)
- [组合容量只完成部分字段门禁](#组合容量只完成部分字段门禁)
- [Artifact 价格一致性门禁未通过](#artifact-价格一致性门禁未通过)
- [切片截止日不是实际信号日](#切片截止日不是实际信号日)
- [Summary/组合门禁未通过](#summary组合门禁未通过)
- [Summary 未验证模型口径](#summary-未验证模型口径)
- [Baostock 字段探针结果](#baostock-字段探针结果)
- [清洗后通过，不等于源数据无异常](#清洗后通过不等于源数据无异常)
- [不能静默覆盖候选 sizing/资金字段](#不能静默覆盖候选-sizing资金字段)
- [配置和摘要口径](#配置和摘要口径)

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

### 配置和摘要口径

```markdown
## 配置和摘要口径
- `output.max_candidates=0` 表示不截断候选，不是输出 0 个候选。
- `max_candidates` 是排序后的 top-N 截断，不是阈值过滤；截断不增加 `threshold_failed_symbols`。
- `threshold_failed_symbols` 是被任意阈值过滤的唯一标的数。
- `threshold_failures` 是逐阈值失败次数，同一标的可能同时计入多个阈值，不能和 `threshold_failed_symbols` 相加对账。
```
