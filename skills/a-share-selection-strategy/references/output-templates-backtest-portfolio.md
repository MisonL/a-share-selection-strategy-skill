# Output Templates - 回测和组合

本文件是 `output-templates.md` 的按需展开模板库。只有快速路由指向本类问题时才读取本文件；模板占位项不能当作事实。

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
