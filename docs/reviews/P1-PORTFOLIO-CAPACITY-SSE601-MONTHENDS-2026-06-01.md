# P1-PORTFOLIO-CAPACITY-SSE601-MONTHENDS-2026-06-01

## 范围

本报告记录一次沪市 601 号段 40-symbol 池、2025 上半年月末窗口的 P1 `portfolio_cash_lot_floor` 组合容量复验。目标是复用已暴露 late-window 日期混杂失败的同一 601 池，改用此前多组池已通过的 2025 月末窗口，验证该失败边界不是整个 601 池不可跑。

## 池和窗口

固定池:

```text
601006,601009,601018,601021,601058,601066,601077,601098,601100,601108,601117,601118,601128,601155,601162,601169,601186,601198,601216,601229,601238,601298,601319,601328,601336,601360,601377,601390,601555,601577,601607,601618,601628,601633,601658,601669,601696,601698,601699,601718
```

窗口和约束:

- `start_date=2024-01-01`
- `end_date=2026-05-29`
- `signal_dates=2025-02-28,2025-03-31,2025-04-30,2025-05-30,2025-06-30,2025-07-31`
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
- `adjustflag=3`

## 命令

runner:

```bash
uv run --with pandas --with numpy --with baostock --with-requirements requirements-ml.txt python scripts/run_baostock_walk_forward.py \
  --symbols "$SYMBOLS" \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --signal-dates 2025-02-28 2025-03-31 2025-04-30 2025-05-30 2025-06-30 2025-07-31 \
  --output-dir /tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z \
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
python3 scripts/validate_walk_forward_manifest.py \
  --manifest /tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z/run_manifest.json \
  --output /tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z/run_manifest_validation.json \
  --signal-dates 2025-02-28 2025-03-31 2025-04-30 2025-05-30 2025-06-30 2025-07-31 \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 使用 README 的动态提取方式读取 `run_manifest.json` 和 `prediction_run_summary.json`，避免手填候选数和最终权益。命令额外固定:

```bash
python3 scripts/validate_walk_forward_artifacts.py \
  --run-dir /tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z \
  --output /tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z/run_artifact_validation.json \
  --expected-portfolio-violations 0 \
  --required-allocation-model portfolio_cash_lot_floor \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled \
  --manifest-validation /tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z/run_manifest_validation.json \
  --cash-budget 3000000 \
  --lot-size 100 \
  --hold-days 5 \
  --cost-bps 10 \
  --slippage-bps 5 \
  --allow-dropped-invalid-rows
```

## 结果

产物目录:

- `/tmp/stock-selection-p1-portfolio-capacity-sse601-monthends-20260601T153554Z`

runner:

- 退出码 `0`
- `steps=35`
- 失败步骤为 `[]`
- `allocation_model=portfolio_cash_lot_floor`
- `tradability_model=tradestatus_entry_exit_only`
- `limit_rules_model=not_modeled`
- 未使用 `--expect-portfolio-violations`

manifest validator:

- 退出码 `0`
- `steps_checked=35`
- `errors=[]`

artifact validator:

- 退出码 `0`
- `signals_checked=6`
- `total_candidates=59`
- `total_completed_trades=59`
- `final_equity=0.9896602509081568`
- `portfolio_violations=0`
- `manifest_checked=true`
- `errors=[]`

metadata:

- `rows=23166`
- `raw_rows=23200`
- `symbol_count=40`
- `failed_symbols=[]`
- `empty_symbols=[]`
- `invalid_rows=34`
- `dropped_invalid_rows=34`
- `raw_non_trading_rows=34`
- `non_trading_rows=0`
- `raw_tradestatus_missing_rows=0`
- `tradestatus_missing_rows=0`
- `raw_non_trading_symbols=601198,601298,601555,601718`
- `raw_st_symbols=601718`
- `adjustflag=3`

run summary:

- 每期候选和完成交易数: `10/10/0`, `9/9/0`, `10/10/0`, `10/10/0`, `10/10/0`, `10/10/0`
- `quality_errors=[]`
- `final_equity=0.9896602509081568`
- `total_return=-0.010339749091843209`
- `max_drawdown=-0.0575652040324627`
- `incomplete_trades=0`

allocation summary:

- `raw_candidates=79`
- `allocated_candidates=59`
- `skipped_candidates=20`
- `skip_reason_counts={"max_open_positions": 20}`
- 每期 raw/allocated/skipped: `10/10/0`, `9/9/0`, `12/10/2`, `17/10/7`, `18/10/8`, `13/10/3`
- `max_open_positions=10`
- `max_gross_weight=0.999197`
- `max_gross_notional=2997591.0`
- `max_cash_reserved=2997591.0`

overlap summary:

- `max_open_positions=10`
- `max_gross_weight=0.9991969999999998`
- `max_gross_notional=2997591.0`
- `max_cash_reserved=2997591.0`
- `same_symbol_overlap_rows=0`
- `same_symbol_overlap_symbols=[]`
- `capital_fields_present=weight,notional,quantity,cash_reserved`
- `capital_fields_missing=[]`
- `weight_capacity_verifiable=true`
- `cash_capacity_verifiable=true`
- `calendar_model=business_day_closed_interval`

## 结论边界

本次复验只证明该沪市 601 号段 40-symbol 池、6 个 2025-02 到 2025-07 月末信号日、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点、`tradestatus` 入场/退出门禁和本地 `portfolio_cash_lot_floor` 模型下，现有 runner、manifest validator 和 artifact validator 能完整通过。

本次通过不改写同一池 late-window 失败边界；`2025-11-28` 附近的实际候选日期混杂仍只能作为失败证据，不能作为 P1 通过证据。

`invalid_rows=34` 和 `dropped_invalid_rows=34` 必须披露；显式 `--drop-invalid-rows` 成功不等于源数据无异常。

`skipped_candidates=20` 且原因均为 `max_open_positions`，因此不能说全部 raw candidates 都进入回测或成交。

`final_equity` 和 `total_return` 是本地 close-to-close、完成交易等权资金曲线，不是按 `portfolio_cash_lot_floor` sizing 权重、真实成交或券商容量计算的收益。

价格来自本次 baostock `adjustflag=3` 落地文件；本报告不额外证明公司行为处理、复权口径适配真实交易或券商成交口径。

`calendar_model=business_day_closed_interval` 只表示 `portfolio_overlap_report.py` 用 pandas 工作日闭区间展开持仓日期；它不是 A 股交易所日历、节假日、停复牌或全持有期真实可交易性门禁。

`limit_rules_model=not_modeled` 表示真实涨跌停规则仍未建模；本次复验也不证明真实成交容量、券商订单、全市场策略质量或样本外泛化。
