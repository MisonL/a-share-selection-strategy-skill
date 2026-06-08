# P1-PORTFOLIO-CAPACITY-2026-06-08

## 范围

本报告记录一次 2026-06-08 对独立 40-symbol 池的 P1 `portfolio_cash_lot_floor` 组合容量复验。目标是复核同一固定池和信号窗口在当前产物中的 runner、manifest validator 和 artifact validator 证据，而不是新增全市场结论。

## 摘要

| 项目 | 结论 |
| --- | --- |
| 复验对象 | 独立 40-symbol 池 |
| 组合模型 | `portfolio_cash_lot_floor` |
| 主要结论 | 固定池和窗口的 artifact 内容一致，组合容量门禁 `portfolio_violations=0` |
| 不能外推 | 全市场样本外收益、真实订单成交、券商容量、真实涨跌停规则或长期稳定性 |

## 池和窗口

固定池:

```text
000009,000021,000039,000060,000069,000100,000157,000301,000338,000400,000423,000568,000625,000661,000708,000768,000786,000895,000963,001979,002001,002007,002024,002129,002179,002230,002236,002241,002252,002271,002304,002311,002352,002410,002459,002460,002466,002493,002508,002555
```

窗口和约束:

- `start_date=2024-01-01`
- `end_date=2026-05-29`
- `signal_dates=2025-03-20,2025-06-20,2025-09-19,2025-12-19,2026-04-17,2026-05-20`
- `cash_budget=3000000`
- `lot_size=100`
- `hold_days=5`
- `cost_bps=10`
- `slippage_bps=5`
- `max_open_positions=10`
- `max_gross_weight=1.0`
- `max_gross_notional=3000000`
- `max_cash_reserved=3000000`
- `allocation_model=portfolio_cash_lot_floor`
- `tradability_model=tradestatus_entry_exit_only`
- `limit_rules_model=not_modeled`
- `adjustflag=3`
- 显式使用 `--drop-invalid-rows`
- 未使用 `--expect-portfolio-violations`

## 命令

runner:

```bash
uv run --with pandas --with numpy --with baostock --with-requirements skills/a-share-selection-strategy/requirements-ml.txt python skills/a-share-selection-strategy/scripts/run_baostock_walk_forward.py \
  --symbols "$SYMBOLS" \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --signal-dates 2025-03-20 2025-06-20 2025-09-19 2025-12-19 2026-04-17 2026-05-20 \
  --output-dir /tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z \
  --allocation-model portfolio_cash_lot_floor \
  --cash-budget 3000000 \
  --lot-size 100 \
  --hold-days 5 \
  --cost-bps 10 \
  --slippage-bps 5 \
  --max-open-positions 10 \
  --max-gross-weight 1.0 \
  --max-gross-notional 3000000 \
  --max-cash-reserved 3000000 \
  --fail-on-symbol-overlap \
  --drop-invalid-rows
```

manifest validator:

```bash
python3 skills/a-share-selection-strategy/scripts/validate_walk_forward_manifest.py \
  --manifest /tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest.json \
  --output /tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest_validation.json \
  --signal-dates 2025-03-20 2025-06-20 2025-09-19 2025-12-19 2026-04-17 2026-05-20 \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 首次用裸 `python3` 运行时返回 2:

```text
ERROR: code=bad_input output_written=false message=No module named 'pandas'
```

这是执行环境缺少 `pandas`，不是 artifact 内容失败。随后使用包含 `pandas` 和 `numpy` 的 `uv` 环境运行同一校验口径通过:

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_walk_forward_artifacts.py \
  --run-dir /tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z \
  --output /tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_artifact_validation.json \
  --signal-dates 2025-03-20 2025-06-20 2025-09-19 2025-12-19 2026-04-17 2026-05-20 \
  --expected-symbols 000009 000021 000039 000060 000069 000100 000157 000301 000338 000400 000423 000568 000625 000661 000708 000768 000786 000895 000963 001979 002001 002007 002024 002129 002179 002230 002236 002241 002252 002271 002304 002311 002352 002410 002459 002460 002466 002493 002508 002555 \
  --expected-candidates 2 10 7 9 10 10 \
  --expected-final-equity 0.9614512632665976 \
  --expected-portfolio-violations 0 \
  --required-allocation-model portfolio_cash_lot_floor \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled \
  --manifest-validation /tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest_validation.json \
  --cash-budget 3000000 \
  --allow-dropped-invalid-rows
```

## 结果

产物目录:

- `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z`
- manifest: `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest.json`
- manifest validation: `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest_validation.json`
- artifact validation: `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_artifact_validation.json`

runner:

- 退出码 `0`
- `steps=35`
- 35 个步骤全部返回 `0`
- `allocation_model=portfolio_cash_lot_floor`
- `tradability_model=tradestatus_entry_exit_only`
- `limit_rules_model=not_modeled`
- 未使用 `--expect-portfolio-violations`

manifest validator:

- 退出码 `0`
- `steps_checked=35`
- `errors=[]`
- `verdict=manifest_only_artifacts_not_checked`

artifact validator:

- 裸 `python3` 首次返回 `2`，原因为 `No module named 'pandas'`
- `uv run --with pandas --with numpy` 返回 `0`
- `signals_checked=6`
- `total_candidates=48`
- `total_completed_trades=48`
- `final_equity=0.9614512632665976`
- `portfolio_violations=0`
- `expected_portfolio_violations=false`
- `capacity_gate_pass=true`
- `capacity_gate_status=pass`
- `manifest_checked=true`
- `errors=[]`
- `verdict=artifacts_pass_enabled_gates_not_external_proof`
- `claim_boundary=artifact_validation_not_external_gate`

metadata:

- `rows=23190`
- `raw_rows=23200`
- `symbol_count=40`
- `failed_symbols=[]`
- `empty_symbols=[]`
- `invalid_rows=10`
- `dropped_invalid_rows=10`
- `raw_non_trading_rows=10`
- `non_trading_rows=0`
- `tradestatus_missing_rows=0`
- `raw_non_trading_symbols=002252`
- `raw_st_symbols=002024`
- `adjustflag=3`

run summary:

- 每期候选和完成交易数: `2/2/0`, `10/10/0`, `7/7/0`, `9/9/0`, `10/10/0`, `10/10/0`
- `quality_errors=[]`
- `final_equity=0.9614512632665976`
- `total_return=-0.03854873673340242`
- `max_drawdown=-0.0494320515108941`
- `incomplete_trades=0`
- `capacity_gate_pass=true`
- `capacity_gate_status=pass`

allocation summary:

- `raw_candidates=59`
- `allocated_candidates=48`
- `skipped_candidates=11`
- `skip_reason_counts={"max_open_positions": 11}`
- 每期 raw/allocated/skipped: `2/2/0`, `13/10/3`, `7/7/0`, `9/9/0`, `15/10/5`, `13/10/3`
- `max_open_positions=10`
- `max_gross_weight=0.99571`
- `max_gross_notional=2987130.0`
- `max_cash_reserved=2987130.0`

overlap summary:

- `trades=48`
- `complete_trades=48`
- `incomplete_trades=0`
- `max_open_positions=10`
- `max_gross_weight=0.9957099999999997`
- `max_gross_notional=2987130.0`
- `max_cash_reserved=2987130.0`
- `same_symbol_overlap_rows=0`
- `same_symbol_overlap_symbols=[]`
- `capital_fields_missing=[]`
- `weight_capacity_verifiable=true`
- `cash_capacity_verifiable=true`
- `calendar_model=business_day_closed_interval`

## 结论边界

本次 P1 通过只证明固定 40-symbol 池、6 个信号日、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点、`tradestatus_entry_exit_only`、`limit_rules_model=not_modeled` 和本地 `portfolio_cash_lot_floor` 模型下，现有 runner 产物一致且组合容量门禁为 0 违规。

它不证明全市场样本外收益、真实订单成交、券商容量、真实涨跌停规则门禁或长期稳定性。

`final_equity` 和 `total_return` 是本地 close-to-close、完成交易等权资金曲线，不是收益承诺，也不是按真实成交或券商容量计算的收益。

`--drop-invalid-rows` 成功不等于源数据无异常；本次 metadata 已记录 `invalid_rows=10`、`dropped_invalid_rows=10`、`raw_non_trading_rows=10`、`raw_non_trading_symbols=002252` 和 `raw_st_symbols=002024`。

`skipped_candidates=11` 且原因均为 `max_open_positions`，因此不能写成全部 raw candidates 都进入回测或成交。

价格来自本次 baostock `adjustflag=3` 落地文件；本报告不额外证明公司行为处理、复权口径适配真实交易或券商成交口径。

`calendar_model=business_day_closed_interval` 只表示 `portfolio_overlap_report.py` 用 pandas 工作日闭区间展开持仓日期；它不是 A 股交易所日历、节假日、停复牌或全持有期真实可交易性门禁。

manifest validator 只校验 manifest 结构、步骤、退出码和门禁参数；artifact validator 只校验既有 run dir 内 artifact 内容一致性，不重新联网取数、不重新训练 LightGBM、不替代外部门禁。
