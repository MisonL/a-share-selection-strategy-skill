# CURRENT-GATES-CLOSEOUT-2026-06-08

## 范围

本报告记录 2026-06-08 对当前 `Current Next Gates` 的推进结果。目标是把可复验项推进到真实命令证据，把当前无法关闭的项标成阻断边界，而不是把外部源失败、缺少直接字段或短窗口观察包装成通过。

本轮覆盖:

- P1: 复用同日新增的独立 40-symbol `portfolio_cash_lot_floor` 组合容量复验证据。
- P2: 重跑 baostock 涨跌停字段探针，区分核心控制字段通过和完整控制字段失败。
- P3: 重跑 3 轮外部源稳定性观察。

## 摘要

| 门禁 | 本轮结果 | 结论 |
| --- | --- | --- |
| P1 组合容量 | 通过固定池和固定窗口 artifact validator | 当前固定样本可记录为通过证据 |
| P2 涨跌停规则 | 直接字段仍不可用，核心控制字段探针通过 | 真实涨跌停规则仍不能建模为通过 |
| P3 外部源稳定性 | akshare 和 yfinance 失败，baostock 通过 | 长期稳定性仍未证明，且本轮不是全源通过 |

## P1 组合容量

证据报告:

- `skills/a-share-selection-strategy/references/reviews/P1-PORTFOLIO-CAPACITY-2026-06-08.md`

产物:

- `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest.json`
- `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_manifest_validation.json`
- `/tmp/a-share-selection-p1-portfolio-capacity-20260608T092009Z/run_artifact_validation.json`

结果:

- runner 返回 `0`
- manifest validator 返回 `0`
- artifact validator 在 `uv run --with pandas --with numpy` 环境返回 `0`
- `signals_checked=6`
- `total_candidates=48`
- `total_completed_trades=48`
- `final_equity=0.9614512632665976`
- `portfolio_violations=0`
- `capacity_gate_pass=true`
- `capacity_gate_status=pass`
- `errors=[]`

边界:

- 该结果只证明固定 40-symbol 池、6 个信号日、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点、`tradestatus_entry_exit_only`、`limit_rules_model=not_modeled` 和本地 `portfolio_cash_lot_floor` 模型下 artifact 一致且组合容量门禁为 0 违规。
- 它不证明全市场样本外收益、真实成交、券商容量、真实涨跌停规则或长期稳定性。

## P2 涨跌停字段和规则

完整控制字段严格探针:

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST,turn,volume,amount \
  --output /tmp/a-share-selection-p2a-limit-field-full-20260608T180000Z/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

结果:

- 退出码 `3`
- `supported_candidate_fields=[]`
- `unsupported_candidate_fields=up_limit,down_limit,limit_status,is_trading,suspended`
- `supported_direct_limit_fields=[]`
- `supported_trading_state_fields=[]`
- `direct_limit_field_available=false`
- `trading_state_field_available=false`
- `available_control_fields=preclose,pctChg,tradestatus,isST,turn,volume`
- `provider_error_fields=volume,amount`
- `control_rows=286`
- `limit_rules_model=not_modeled`
- `rule_inference_performed=false`

核心控制字段严格探针:

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST \
  --output /tmp/a-share-selection-p2a-limit-field-core-20260608T180000Z/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

结果:

- 退出码 `0`
- `supported_candidate_fields=[]`
- `unsupported_candidate_fields=up_limit,down_limit,limit_status,is_trading,suspended`
- `supported_direct_limit_fields=[]`
- `supported_trading_state_fields=[]`
- `direct_limit_field_available=false`
- `trading_state_field_available=false`
- `available_control_fields=preclose,pctChg,tradestatus,isST`
- `provider_error_fields=[]`
- `control_rows=208`
- `limit_rules_model=not_modeled`
- `rule_inference_performed=false`

P2 结论:

- 本轮已经把 P2 推进到当前 baostock 日 K 字段能力的可审计边界。
- 直接涨跌停字段和交易状态候选字段仍不可用，因此不能把 P2 写成真实涨跌停规则门禁通过。
- `preclose/pctChg/tradestatus/isST` 只能作为控制字段和诊断字段；本轮没有、也不应从这些字段粗推真实涨跌停规则。
- 若要继续关闭 P2，需要引入可靠直接字段源、交易所级规则引擎和相应真实样例校验；当前仓库和本轮 baostock 产物不支持把该门禁标成通过。

## P3 外部源稳定性

命令:

```bash
uv run --with pandas --with numpy --with akshare --with yfinance --with baostock \
  python skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
    --output-dir /tmp/a-share-selection-p3-external-20260608T180000Z/runs \
    --summary-output /tmp/a-share-selection-p3-external-20260608T180000Z/summary.json \
    --iterations 3 \
    --akshare-symbols 000001,600000 \
    --yfinance-symbols AAPL,MSFT \
    --baostock-symbols 000001,600000
```

结果:

- 退出码 `3`
- `iterations=3`
- `total_runs=9`
- `passed_runs=3`
- `all_sources_all_iterations_passed=false`
- `long_term_stability_claim=not_proven`

逐源结果:

| source | runs | passed_runs | all_passed | 关键事实 |
| --- | --- | --- | --- | --- |
| akshare | 3 | 0 | false | 每轮 `fallback_errors=2`，`stock_zh_a_hist` 被远端断开，`hist_provider_clean=3` |
| yfinance | 3 | 0 | false | 每轮 `rows=0`、`symbol_count=0`、`empty_symbols=AAPL,MSFT` |
| baostock | 3 | 3 | true | 每轮 `rows=1160`、`symbol_count=2`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3` |

P3 结论:

- 本轮 P3 不是全源通过；akshare 和 yfinance 严格门禁失败。
- baostock 在本次固定 2-symbol、3 轮、固定窗口和本地网络环境下通过。
- 任何单日或三轮观察都不能证明长期稳定性；`long_term_stability_claim=not_proven` 必须保留。

## 处理边界

本轮已经把当前可执行的 P1/P2/P3 门禁推进到可审计证据:

- P1 有同日通过证据。
- P2 有同日阻断证据，不能伪装成通过。
- P3 有同日失败证据和 baostock 局部通过证据，不能伪装成长期稳定。

仍不能关闭为“已证明”的项:

- 真实涨跌停规则门禁。
- 真实券商订单、真实成交和券商容量。
- 全市场级 prediction-derived 策略质量和样本外收益。
- 外部源长期稳定性。
- 交易所日历、节假日、特殊交易日、临时休市和全持有期真实可交易性。
