# P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01

## 范围

本报告记录一次新增深市主板 40-symbol 池的 P1 `portfolio_cash_lot_floor` 组合容量复验。目标是扩大真实 A 股池覆盖，并确认该池与当前已展开的既有 20/40/40-symbol 池无交集。

## 池和窗口

新池:

```text
000012,000027,000028,000031,000050,000089,000099,000166,000401,000402,000425,000429,000488,000538,000539,000541,000547,000559,000581,000596,000617,000630,000686,000703,000709,000725,000728,000729,000738,000758,000776,000778,000783,000800,000807,000825,000830,000858,000876,000878
```

本地集合检查结果:

- `new_count=40`
- `unique=40`
- 与 `docs/reviews/REAL-SCENARIO-GATES-2026-05-30.md` 中已展开池集合、已记录交集符号和 `600438` 的交集为 `[]`

窗口和约束:

- `start_date=2024-01-01`
- `end_date=2026-05-29`
- `signal_dates=2025-02-28,2025-03-31,2025-04-30,2025-05-30,2025-06-30,2025-07-31`
- `cash_budget=3000000`
- `max_open_positions=10`
- `max_gross_weight=1.0`
- `max_gross_notional=3000000`
- `max_cash_reserved=3000000`
- `allocation_model=portfolio_cash_lot_floor`

## 命令

runner:

```bash
uv run --with pandas --with numpy --with baostock --with-requirements requirements-ml.txt python scripts/run_baostock_walk_forward.py \
  --symbols "$SYMBOLS" \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --signal-dates 2025-02-28 2025-03-31 2025-04-30 2025-05-30 2025-06-30 2025-07-31 \
  --output-dir /tmp/stock-selection-p1-portfolio-capacity-sz-mainboard-20260601T055752Z \
  --allocation-model portfolio_cash_lot_floor \
  --cash-budget 3000000 \
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
  --manifest /tmp/stock-selection-p1-portfolio-capacity-sz-mainboard-20260601T055752Z/run_manifest.json \
  --output /tmp/stock-selection-p1-portfolio-capacity-sz-mainboard-20260601T055752Z/run_manifest_validation.json \
  --signal-dates 2025-02-28 2025-03-31 2025-04-30 2025-05-30 2025-06-30 2025-07-31 \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 使用 README 的动态提取方式读取 `run_manifest.json` 和 `qsss_run_summary.json`，避免手填候选数和最终权益。

## 结果

产物目录:

- `/tmp/stock-selection-p1-portfolio-capacity-sz-mainboard-20260601T055752Z`

runner:

- 退出码 `0`
- `steps=35`
- `allocation_model=portfolio_cash_lot_floor`
- `limit_rules_model=not_modeled`

manifest validator:

- 退出码 `0`
- `steps_checked=35`
- `errors=[]`

artifact validator:

- 退出码 `0`
- `signals_checked=6`
- `total_candidates=52`
- `total_completed_trades=52`
- `portfolio_violations=0`
- `errors=[]`
- `manifest_checked=true`

metadata:

- `rows=23180`
- `raw_rows=23200`
- `symbol_count=40`
- `failed_symbols=[]`
- `empty_symbols=[]`
- `invalid_rows=20`
- `dropped_invalid_rows=20`
- `raw_non_trading_rows=20`
- `non_trading_rows=0`
- `raw_tradestatus_missing_rows=0`
- `tradestatus_missing_rows=0`
- `adjustflag=3`

run summary:

- 每期候选和完成交易数: `6/6/0`, `9/9/0`, `10/10/0`, `9/9/0`, `10/10/0`, `8/8/0`
- `quality_errors=[]`
- `final_equity=1.0072173506529436`
- `total_return=0.007217350652943599`
- `max_drawdown=-0.0796634005967671`
- `incomplete_trades=0`

allocation summary:

- `raw_candidates=61`
- `allocated_candidates=52`
- `skipped_candidates=9`
- `skip_reason_counts={"max_open_positions": 9}`
- `max_open_positions=10`
- `max_gross_weight=0.9990416666666667`
- `max_gross_notional=2997125.0`
- `max_cash_reserved=2997125.0`

overlap summary:

- `max_open_positions=10`
- `max_gross_weight=0.9990416666666663`
- `max_gross_notional=2997125.0`
- `max_cash_reserved=2997125.0`
- `same_symbol_overlap_rows=0`
- `same_symbol_overlap_symbols=[]`
- `capital_fields_missing=[]`
- `cash_capacity_verifiable=true`
- `weight_capacity_verifiable=true`
- `calendar_model=business_day_closed_interval`

## 边界

本次复验只证明该深市主板 40-symbol 池、6 个 2025 月末信号日、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点、`tradestatus` 入场/退出门禁和本地 `portfolio_cash_lot_floor` 模型下，现有 runner 和 artifact validator 能完整通过。

它不证明全市场策略质量、样本外收益、真实订单成交、券商容量或真实涨跌停规则。`invalid_rows=20` 和 `dropped_invalid_rows=20` 必须在报告中披露；`skip_reason_counts={"max_open_positions": 9}` 表示有 9 个 raw candidates 未进入回测，不能写成全部候选成交。

`final_equity` 和 `total_return` 是本地 close-to-close、完成交易等权资金曲线，不是按 `portfolio_cash_lot_floor` sizing 权重、真实成交或券商容量计算的收益。

价格来自本次 baostock `adjustflag=3` 落地文件；本报告不额外证明公司行为处理、复权口径适配真实交易或券商成交口径。

`calendar_model=business_day_closed_interval` 只表示 `portfolio_overlap_report.py` 用 pandas 工作日闭区间展开持仓日期；它不是 A 股交易所日历、节假日、停复牌或全持有期真实可交易性门禁。
