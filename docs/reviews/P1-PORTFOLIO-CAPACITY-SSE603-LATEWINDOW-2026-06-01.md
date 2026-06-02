# P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01

## 范围

本报告记录一次新增沪市 603 号段 40-symbol 池、2025 下半年到 2026 年初窗口的 P1 `portfolio_cash_lot_floor` 组合容量复验。目标是继续扩大真实 A 股池和窗口覆盖，并避免重复当前已记录的 2025-02 到 2025-07 月末窗口。

## 池和窗口

新池:

```text
603000,603019,603025,603027,603035,603043,603056,603058,603077,603087,603096,603108,603127,603129,603156,603160,603179,603195,603198,603218,603225,603228,603233,603236,603258,603260,603267,603268,603279,603283,603290,603298,603300,603305,603306,603308,603313,603317,603318,603319
```

取数探针:

- `/tmp/stock-selection-p1-sse603-probe-20260601T105709Z`
- 严格 baostock fetch 返回 `0`
- `symbol_count=40`
- `failed_symbols=[]`
- `empty_symbols=[]`
- `invalid_rows=104`
- `dropped_invalid_rows=104`
- `non_trading_rows=0`

窗口和约束:

- `start_date=2024-01-01`
- `end_date=2026-05-29`
- `signal_dates=2025-08-29,2025-09-30,2025-10-31,2025-11-28,2025-12-31,2026-01-30`
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
  --signal-dates 2025-08-29 2025-09-30 2025-10-31 2025-11-28 2025-12-31 2026-01-30 \
  --output-dir /tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z \
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
  --manifest /tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z/run_manifest.json \
  --output /tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z/run_manifest_validation.json \
  --signal-dates 2025-08-29 2025-09-30 2025-10-31 2025-11-28 2025-12-31 2026-01-30 \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 使用 README 的动态提取方式读取 `run_manifest.json` 和 `qsss_run_summary.json`，避免手填候选数和最终权益。命令额外固定:

```bash
python3 scripts/validate_walk_forward_artifacts.py \
  --run-dir /tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z \
  --output /tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z/run_artifact_validation.json \
  --expected-portfolio-violations 0 \
  --required-allocation-model portfolio_cash_lot_floor \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled \
  --manifest-validation /tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z/run_manifest_validation.json \
  --cash-budget 3000000 \
  --lot-size 100 \
  --hold-days 5 \
  --cost-bps 10 \
  --slippage-bps 5 \
  --allow-dropped-invalid-rows
```

## 结果

产物目录:

- `/tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z`

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
- `total_candidates=52`
- `total_completed_trades=52`
- `final_equity=0.9885268093529102`
- `portfolio_violations=0`
- `manifest_checked=true`
- `errors=[]`

metadata:

- `rows=23056`
- `raw_rows=23160`
- `symbol_count=40`
- `failed_symbols=[]`
- `empty_symbols=[]`
- `invalid_rows=104`
- `dropped_invalid_rows=104`
- `raw_non_trading_rows=104`
- `non_trading_rows=0`
- `raw_tradestatus_missing_rows=0`
- `tradestatus_missing_rows=0`
- `adjustflag=3`

run summary:

- 每期候选和完成交易数: `10/10/0`, `7/7/0`, `7/7/0`, `10/10/0`, `9/9/0`, `9/9/0`
- `quality_errors=[]`
- `final_equity=0.9885268093529102`
- `total_return=-0.011473190647089848`
- `max_drawdown=-0.0392929082401981`
- `incomplete_trades=0`

allocation summary:

- `raw_candidates=56`
- `allocated_candidates=52`
- `skipped_candidates=4`
- `skip_reason_counts={"max_open_positions": 4}`
- 每期 raw/allocated/skipped: `13/10/3`, `7/7/0`, `7/7/0`, `11/10/1`, `9/9/0`, `9/9/0`
- `max_open_positions=10`
- `max_gross_weight=0.9959`
- `max_gross_notional=2987700.0`
- `max_cash_reserved=2987700.0`

overlap summary:

- `max_open_positions=10`
- `max_gross_weight=0.9958999999999997`
- `max_gross_notional=2987700.0`
- `max_cash_reserved=2987700.0`
- `same_symbol_overlap_rows=0`
- `same_symbol_overlap_symbols=[]`
- `capital_fields_present=weight,notional,quantity,cash_reserved`
- `capital_fields_missing=[]`
- `weight_capacity_verifiable=true`
- `cash_capacity_verifiable=true`
- `calendar_model=business_day_closed_interval`

## 结论边界

本次复验只证明该沪市 603 号段 40-symbol 池、6 个 2025-08 到 2026-01 信号日、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点、`tradestatus` 入场/退出门禁和本地 `portfolio_cash_lot_floor` 模型下，现有 runner、manifest validator 和 artifact validator 能完整通过。

`invalid_rows=104` 和 `dropped_invalid_rows=104` 必须披露；显式 `--drop-invalid-rows` 成功不等于源数据无异常。

`skipped_candidates=4` 且原因均为 `max_open_positions`，因此不能说全部 raw candidates 都进入回测或成交。

`final_equity` 和 `total_return` 是本地 close-to-close、完成交易等权资金曲线，不是按 `portfolio_cash_lot_floor` sizing 权重、真实成交或券商容量计算的收益。

价格来自本次 baostock `adjustflag=3` 落地文件；本报告不额外证明公司行为处理、复权口径适配真实交易或券商成交口径。

`calendar_model=business_day_closed_interval` 只表示 `portfolio_overlap_report.py` 用 pandas 工作日闭区间展开持仓日期；它不是 A 股交易所日历、节假日、停复牌或全持有期真实可交易性门禁。

`limit_rules_model=not_modeled` 表示真实涨跌停规则仍未建模；本次复验也不证明真实成交容量、券商订单、全市场策略质量或样本外泛化。
