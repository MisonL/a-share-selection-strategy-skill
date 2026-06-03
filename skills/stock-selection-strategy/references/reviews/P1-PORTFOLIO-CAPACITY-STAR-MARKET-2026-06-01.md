# P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01

## 范围

本报告记录一次新增科创板 40-symbol 池的 P1 `portfolio_cash_lot_floor` 组合容量复验。目标是继续扩大真实 A 股池覆盖，并确认该池与当前已展开 P1 池和已记录问题符号零交集。

## 摘要

| 项目 | 结论 |
| --- | --- |
| 复验对象 | 科创板 40-symbol 池 |
| 组合模型 | `portfolio_cash_lot_floor` |
| 主要结论 | 最终固定池和窗口可跑通组合容量门禁 |
| 不能外推 | 全市场策略质量、真实成交容量、涨跌停规则或券商订单 |

## 池和窗口

新池:

```text
688001,688002,688003,688005,688006,688007,688008,688009,688012,688016,688019,688020,688023,688025,688026,688029,688030,688033,688036,688037,688039,688050,688055,688056,688063,688065,688066,688072,688075,688080,688081,688083,688085,688088,688089,688090,688099,688100,688101,688102
```

本地集合检查结果:

- `new_count=40`
- `unique=40`
- 与 `skills/stock-selection-strategy/references/reviews/REAL-SCENARIO-GATES-2026-05-30.md`、`skills/stock-selection-strategy/references/reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md`、`skills/stock-selection-strategy/references/reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md` 中 6 位 symbol，以及已记录问题符号 `600438`、`688981` 的交集为 `[]`

取数边界:

- 初始池包含 `688086`，严格 fetch 在 `/tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100438Z/` 返回 `3`，stderr 记录 `empty_symbols=1`，metadata 记录 `empty_symbols=["688086"]`
- 替换候选探测在 `/tmp/stock-selection-star-replacement-probe-20260601T100723Z/` 对 `688102,688103,688105,688106,688108,688109,688110,688112` 返回 `0`，且 `empty_symbols=[]`
- 最终通过池使用 `688102` 替换 `688086`；初始失败 run 不作为 P1 通过证据

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
uv run --with pandas --with numpy --with baostock --with-requirements skills/stock-selection-strategy/requirements-ml.txt python skills/stock-selection-strategy/scripts/run_baostock_walk_forward.py \
  --symbols "$SYMBOLS" \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --signal-dates 2025-02-28 2025-03-31 2025-04-30 2025-05-30 2025-06-30 2025-07-31 \
  --output-dir /tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z \
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
python3 skills/stock-selection-strategy/scripts/validate_walk_forward_manifest.py \
  --manifest /tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z/run_manifest.json \
  --output /tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z/run_manifest_validation.json \
  --signal-dates 2025-02-28 2025-03-31 2025-04-30 2025-05-30 2025-06-30 2025-07-31 \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 使用 README 的动态提取方式读取 `run_manifest.json` 和 `prediction_run_summary.json`，避免手填候选数和最终权益。命令额外固定:

```bash
python3 skills/stock-selection-strategy/scripts/validate_walk_forward_artifacts.py \
  --run-dir /tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z \
  --output /tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z/run_artifact_validation.json \
  --expected-portfolio-violations 0 \
  --required-allocation-model portfolio_cash_lot_floor \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled \
  --manifest-validation /tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z/run_manifest_validation.json \
  --cash-budget 3000000 \
  --lot-size 100 \
  --hold-days 5 \
  --cost-bps 10 \
  --slippage-bps 5 \
  --allow-dropped-invalid-rows
```

## 结果

产物目录:

- `/tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z`

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
- `total_candidates=46`
- `total_completed_trades=46`
- `final_equity=0.9711787769119758`
- `portfolio_violations=0`
- `manifest_checked=true`
- `errors=[]`

metadata:

- `rows=23169`
- `raw_rows=23200`
- `symbol_count=40`
- `failed_symbols=[]`
- `empty_symbols=[]`
- `invalid_rows=31`
- `dropped_invalid_rows=31`
- `raw_non_trading_rows=31`
- `non_trading_rows=0`
- `raw_tradestatus_missing_rows=0`
- `tradestatus_missing_rows=0`
- `adjustflag=3`
- `invalid_symbols=["688005","688012","688033","688037","688066","688085","688089"]`

run summary:

- 每期候选和完成交易数: `5/5/0`, `4/4/0`, `7/7/0`, `10/10/0`, `10/10/0`, `10/10/0`
- `quality_errors=[]`
- `final_equity=0.9711787769119758`
- `total_return=-0.02882122308802415`
- `max_drawdown=-0.1412684907172485`
- `incomplete_trades=0`

allocation summary:

- `raw_candidates=50`
- `allocated_candidates=46`
- `skipped_candidates=4`
- `skip_reason_counts={"max_open_positions": 4}`
- 每期 raw/allocated/skipped 为 `5/5/0`, `4/4/0`, `7/7/0`, `12/10/2`, `12/10/2`, `10/10/0`
- `max_open_positions=10`
- `max_gross_weight=0.994875`
- `max_gross_notional=2984625.0`
- `max_cash_reserved=2984625.0`

overlap summary:

- `max_open_positions=10`
- `max_gross_weight=0.9948749999999997`
- `max_gross_notional=2984625.0`
- `max_cash_reserved=2984625.0`
- `same_symbol_overlap_rows=0`
- `same_symbol_overlap_symbols=[]`
- `capital_fields_missing=[]`
- `cash_capacity_verifiable=true`
- `weight_capacity_verifiable=true`
- `calendar_model=business_day_closed_interval`

## 边界

本次复验只证明该科创板 40-symbol 池、6 个 2025 月末信号日、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点、`tradestatus` 入场/退出门禁和本地 `portfolio_cash_lot_floor` 模型下，现有 runner、manifest validator 和 artifact validator 能完整通过。

它不证明全市场策略质量、样本外收益、真实订单成交、券商容量或真实涨跌停规则。`invalid_rows=31` 和 `dropped_invalid_rows=31` 必须在报告中披露；`skip_reason_counts={"max_open_positions": 4}` 表示有 4 个 raw candidates 未进入回测，不能写成全部候选成交。

`final_equity` 和 `total_return` 是本地 close-to-close、完成交易等权资金曲线，不是按 `portfolio_cash_lot_floor` sizing 权重、真实成交或券商容量计算的收益。

价格来自本次 baostock `adjustflag=3` 落地文件；本报告不额外证明公司行为处理、复权口径适配真实交易或券商成交口径。

`calendar_model=business_day_closed_interval` 只表示 `portfolio_overlap_report.py` 用 pandas 工作日闭区间展开持仓日期；它不是 A 股交易所日历、节假日、停复牌或全持有期真实可交易性门禁。
