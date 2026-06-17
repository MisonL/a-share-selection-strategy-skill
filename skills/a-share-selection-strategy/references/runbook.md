# 运行手册

本手册收纳可复制命令和门禁解释。根 [README.md](../../../README.md) 只保留入口、数据契约和常用路径；文档地图见 [index.md](index.md)。需要执行完整 demo、联网取数、回测或真实门禁复验时读本文件。

## 使用边界

- 所有脚本以本地文件为稳定入口。
- 联网取数必须先落地 CSV/Parquet 和 metadata，再进入校验、评分和汇报。
- 本地 demo 只证明脚本链路可执行，不证明真实行情、真实 prediction、真实回测或收益。
- 任何 `output_written=true` 只表示对应产物或诊断报告已落盘；退出码、`quality_errors`、`errors` 和门禁字段仍是最终事实。

## 环境准备

主路径使用 `uv`：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --help
```

无 `uv` 时创建临时虚拟环境：

```bash
python3 -m venv /tmp/a-share-selection-skill-venv
/tmp/a-share-selection-skill-venv/bin/python -m pip install -r skills/a-share-selection-strategy/requirements.txt
```

附加依赖：

下表路径默认相对本 Skill 目录；从仓库根目录执行时使用 `skills/a-share-selection-strategy/<文件名>`。

| 场景 | 依赖 |
| --- | --- |
| Parquet 输入 | `requirements-parquet.txt` 或 `pyarrow` / `fastparquet` |
| LightGBM prediction 生成器 | `requirements-ml.txt` |
| A 股 baostock 取数 | `baostock` |
| A 股 akshare 取数 | `akshare` |
| A 股 zzshare 取数 | `zzshare` |
| 海外 OHLCV 取数 | `yfinance` |

完全离线环境必须提前准备解释器、wheelhouse 或包缓存。依赖失败时应显式报告，不能改用 mock 数据或跳过依赖。
若只做离线只读测试且本机已有依赖缓存，可把下面的 `uv run --with ...` 改成 `uv run --offline --with ...`；缓存缺依赖时应报告环境问题，而不是联网或改用模拟成功。

## 本地 Demo

### 生成数据

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-demo
```

### 基础校验

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.csv
```

### 通用评分

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices.csv \
  --config skills/a-share-selection-strategy/scripts/example_config.json \
  --output /tmp/a-share-selection-demo/candidates.csv
```

### prediction-derived 消费层评分

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices_with_prediction.csv \
  --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices_with_prediction.csv \
  --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json \
  --output /tmp/a-share-selection-demo/prediction_candidates.csv
```

`prices_with_prediction.csv` 中的 `prediction_score` 是合成输入。该路径只证明评分脚本能消费预测列，不证明真实模型质量。

## 低价超短离线诊断

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py \
  --output /tmp/a-share-selection-low-price-demo \
  --days 160 \
  --scenario low-price-ultra-short
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /tmp/a-share-selection-low-price-demo/prices.csv \
  --spot-input /tmp/a-share-selection-low-price-demo/spot.csv \
  --output-dir /tmp/a-share-selection-low-price-demo/today \
  --mode auto \
  --html-report-language zh
```

检查：

- `summary.json`: `requested_mode`、`mode`、`mode_decision`、`mode_decision_reason`、`missing_prediction_column_groups`、`missing_prediction_requirement`、`consumes_prediction_columns`、`prediction_input_source`、`requested_prediction_input_source`、`prediction_model_executed_by_runner`、`source`、`source_scope`、`runner_source_scope`、`candidate_rows`、`diagnostic_rows`、`spot_matched_symbols`、`input_metadata`、`input_csv_provenance`、`html_report_language`、`html_report_initial_language`、`html_report_error_type`、`candidates_output_written`、`diagnostics_output_written`。
- `input_csv_provenance`: 若 `real_market_data`、`source_scope` 或 `source_claim_boundary` 为 `mixed`、`unknown` 或空值，只能说明本地 CSV 内嵌来源信息混合或未完整声明，不能写成真实全量行情、今日全市场覆盖或交易日历门禁通过。
- `source_provenance`: 汇总 `input_metadata` 和 CSV 内嵌来源字段，便于机器消费；旧字段仍保留，冲突时以本次 `summary.json`、`run_manifest.json` 和 CSV 机器字段为准。
- `run_manifest.json`: `html_report_enabled=false` 表示 `--no-html-report` 主动关闭 HTML；此时 `summary.html_report_written=false` 且 `html_report_error_type=""` 不是报告生成失败。
- `report.html`: 浏览器可读汇总，展示候选、诊断、步骤和证据路径；默认 `--html-report-language auto` 跟随运行环境，也可传 `zh` 或 `en` 并在浏览器内切换；只从已写出的 JSON/CSV 派生，不能替代退出码或机器字段。
- `candidates.csv`: 候选字段、spot 展示字段，以及 prediction 披露字段；低价超短 demo 显式传 `--spot-input spot.csv` 后，`spot_industry` 应展示 demo 行业。
- `diagnostics.csv`: `failed_thresholds`、`failed_thresholds_zh`、`selection_status`、`short_reason`，以及与候选一致的 prediction 披露字段。
- 价格、成交额、换手率、ST、停牌和一字板失败项只代表 demo 覆盖，不代表真实今日 A 股扫描。

## Parquet 输入

```bash
uv run --with pandas --with numpy --with pyarrow python - <<'PY'
from pathlib import Path
import pandas as pd
base = Path("/tmp/a-share-selection-demo")
pd.read_csv(base / "prices.csv", dtype={"symbol": str}).to_parquet(
    base / "prices.parquet",
    index=False,
)
PY
uv run --with pandas --with numpy --with pyarrow python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.parquet
uv run --with pandas --with numpy --with pyarrow python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices.parquet \
  --config skills/a-share-selection-strategy/scripts/example_config.json \
  --output /tmp/a-share-selection-demo/candidates_parquet.csv
```

当前候选输出和今日总控标准产物仍包含 CSV。`run_today_a_share_selection.py` 标准输出为 `run_manifest.json`、`summary.json`、`report.html`、`candidates.csv`、`diagnostics.csv`，并会使用 CSV 中间产物。若用户要求全链路中间完全不出现 CSV，必须先说明需要改造脚本输出、runner 固定路径、artifact validator 和测试。

## Prediction 生成 Demo

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-ml-demo --days 220
uv run --with pandas --with numpy --with scikit-learn --with lightgbm \
  python skills/a-share-selection-strategy/scripts/generate_lightgbm_predictions.py \
  --input /tmp/a-share-selection-ml-demo/prices.csv \
  --output /tmp/a-share-selection-ml-demo/prices_generated_prediction.csv \
  --summary-output /tmp/a-share-selection-ml-demo/prediction_summary.json \
  --fail-on-skipped
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-ml-demo/prices_generated_prediction.csv \
  --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-ml-demo/prices_generated_prediction.csv \
  --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json \
  --output /tmp/a-share-selection-ml-demo/prediction_candidates.csv \
  --fail-on-skipped \
  --fail-on-empty-result
```

核查 `prediction_summary.json`：

- `feature_columns`
- `split_method`
- `scaler_fit_scope`
- `label_definition`
- `prediction_scope`
- 每个 symbol 的训练窗口、标签分布、`skipped_reason`

`prediction_scope=latest_probability_repeated_for_scoring` 表示最新预测概率被重复写入该标的所有行，供评分脚本消费当前概率；不是逐日历史预测序列。

## 今日 A 股总控 CLI

### 本地行情输入

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /path/to/prices.csv \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fail-on-skipped
```

`--mode auto` 决策：

| 输入 | 实际 mode | 口径 |
| --- | --- | --- |
| 缺少 prediction-derived 必需列 | `generic` | 低价超短通用技术评分 |
| 同时已有 `market` + (`prediction` 或 `prediction_score`) + (`turn` 或 `turnover`) | `prediction` | 消费外部 prediction 输入 |

显式 `--mode prediction` 缺字段时必须失败并保留 manifest，不得自动改走通用评分。

### 合并东方财富实时快照展示字段

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /path/to/prices.csv \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fetch-spot eastmoney \
  --spot-pages 5 \
  --fail-on-partial-spot
```

`spot_price`、`spot_pct_chg`、`spot_amount`、`spot_industry` 只进入候选和诊断展示，不参与核心评分。若 metadata 写出 `partial_result=true`，不能写成全市场实时扫描完成。

### 总控 CLI 抓历史

低价超短剖面需要 `tradestatus/isST` 等可交易字段，优先用 baostock：

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --history-source baostock \
  --symbols 000001,600000 \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-skipped
```

`--symbols` 接受 `000001`、`600000`、`sh.600000`、`sz.000001`，manifest 和 `selected_symbols.json` 会记录归一化后的六位代码。

### 从快照筛选历史抓取标的

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fetch-spot eastmoney \
  --spot-pages 5 \
  --derive-symbols-from-spot \
  --max-history-symbols 50 \
  --history-source baostock \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-partial-spot \
  --fail-on-skipped
```

`selected_symbols.json` 只证明按 spot 字段筛出了历史抓取列表，不证明实时全市场扫描完整，也不证明这些标的最终通过历史评分。

本地或抓取的 spot 输入在历史筛选和 `score_candidates.py --spot-input` 中使用同一套 symbol 归一化规则：symbol 列支持 `symbol/code/code_id/stock_code/ticker/Ticker`，`sh.600000`、`600000.SH`、`sz.000001`、`000001.SZ` 会归一化为六位代码后匹配。`summary.json.spot_matched_symbols` 是排查 spot 展示字段是否实际合并的首选字段。

generic 技术评分不消费输入中的 `prediction` 或 `prediction_score` 列。需要使用外部预测列时，必须走 prediction-derived 配置或今日入口的 `mode=prediction`/`auto -> prediction`。

## 真实行情入口

### Baostock A 股历史日线

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/fetch_baostock_a_share.py \
  --symbols 000001,600000 \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-a-share/prices.csv \
  --metadata-output /tmp/a-share-selection-a-share/metadata.json \
  --fail-on-fetch-error
```

门禁不能只看退出码，还要检查 metadata：

- `rows > 0`
- `symbol_count == len(requested_symbols)`
- `failed_symbols == []`
- `empty_symbols == []`
- `invalid_rows == 0`
- `non_trading_rows == 0`

若使用 `--drop-invalid-rows`，必须披露 `dropped_invalid_rows` 和示例。

### Akshare A 股日线

```bash
uv run --with pandas --with numpy --with akshare python skills/a-share-selection-strategy/scripts/fetch_akshare_a_share.py \
  --symbols 000001 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-akshare/prices.csv \
  --metadata-output /tmp/a-share-selection-akshare/metadata.json \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-akshare/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-akshare/prices.csv \
  --config skills/a-share-selection-strategy/scripts/example_config.json \
  --output /tmp/a-share-selection-akshare/candidates.csv \
  --diagnostics-output /tmp/a-share-selection-akshare/score_diagnostics.csv
```

akshare A 股入口会先尝试中文列接口，失败或空结果时记录 `fallback_errors` 并转用 `stock_zh_a_daily`。fallback 成功不等于主接口稳定可用。akshare 输出不生成真实 `prediction/prediction_score`。

### zzshare A 股日线

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/fetch_zzshare_a_share.py \
  --symbols 000001,600000 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-zzshare/prices.csv \
  --metadata-output /tmp/a-share-selection-zzshare/metadata.json \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-zzshare/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-zzshare/prices.csv \
  --config skills/a-share-selection-strategy/scripts/example_config.json \
  --output /tmp/a-share-selection-zzshare/candidates.csv \
  --diagnostics-output /tmp/a-share-selection-zzshare/score_diagnostics.csv
```

zzshare 入口默认使用 `daily(fields=all)`，并把 `source_scope=zzshare_history_fetch`、`token_configured`、`request_interval_seconds`、`limit`、`max_pages`、`possibly_truncated_symbols`、`source_claim_boundary` 写入 metadata。无 token 可用不等于无限频率或长期稳定；基础门禁会强制检查 `invalid_rows == dropped_invalid_rows`、`non_trading_rows == 0`、`tradestatus_missing_rows == 0`；加 `--fail-on-fetch-error` 后还会检查 `failed_symbols == []`、`empty_symbols == []`、`possibly_truncated_symbols == []`、`symbol_count == requested_symbols` 和实际 `date_min/date_max`。

`run_today_a_share_selection.py --history-source zzshare` 会透传 `--history-http-url`、`--history-timeout-seconds`、`--history-request-interval-seconds`、`--history-limit` 和 `--history-max-pages` 到 zzshare fetcher，并固定使用 `fields=all`。zzshare token 只能通过 `ZZSHARE_TOKEN` 环境变量提供；不要把 token 放进 runner CLI 参数，因为 runner 会把 step command 写入 `run_manifest.json`。

### yfinance 通用 OHLCV

```bash
uv run --with pandas --with numpy --with yfinance python skills/a-share-selection-strategy/scripts/fetch_yfinance_ohlcv.py \
  --symbols AAPL,MSFT \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-us/prices.csv \
  --metadata-output /tmp/a-share-selection-us/metadata.json \
  --timeout-seconds 30 \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-us/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-us/prices.csv \
  --config skills/a-share-selection-strategy/scripts/example_config.json \
  --output /tmp/a-share-selection-us/candidates.csv \
  --diagnostics-output /tmp/a-share-selection-us/score_diagnostics.csv \
  --fail-on-skipped \
  --fail-on-empty-result
```

yfinance 裸 OHLCV 不含 `turn` 或 `turnover`，通用评分会输出 `turnover_assumption=neutral_series_missing_turnover`。`end-date` 可能落在非交易日，实际数据范围以 metadata 中每个 symbol 的 `date_min/date_max` 为准。

## 涨跌停字段探针

真实涨跌停规则门禁当前仍是 `not_modeled`。`preclose/pctChg/tradestatus/isST` 只是行情控制和诊断字段，不是直接涨跌停字段。

完整控制字段严格探针：

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST,turn,volume,amount \
  --output /tmp/a-share-selection-p2a-limit-field-refresh/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

核心控制字段探针：

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST \
  --output /tmp/a-share-selection-p2a-limit-field-core/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

读取结果必须看 `provider_error_fields`、`unsupported_candidate_fields`、`supported_direct_limit_fields`、`supported_trading_state_fields`、`control_rows`、`rule_inference_performed=false` 和 `limit_rules_model=not_modeled`。

## 外部源稳定性观察

```bash
RUN_DIR=/tmp/a-share-selection-p3-external-$(date -u +%Y%m%dT%H%M%SZ)
uv run --with pandas --with numpy --with akshare --with yfinance --with baostock --with zzshare \
  python skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
    --output-dir "$RUN_DIR/runs" \
    --summary-output "$RUN_DIR/summary.json" \
    --iterations 3 \
    --akshare-symbols 000001,600000 \
    --yfinance-symbols AAPL,MSFT \
    --baostock-symbols 000001,600000 \
    --zzshare-symbols 000001,600000
```

读取 `summary.json` 时必须检查 `summary.sources.*.all_passed`、逐次 `metadata`、`checks` 和 `long_term_stability_claim=not_proven`。连续复验通过只说明当前窗口、参数和网络环境下通过，不能写成公网数据源长期稳定。

## P1 组合容量门禁

真实回测必须先按信号日截断评分输入，避免用未来行情生成候选；回测价格文件可以保留信号日之后的真实行用于出场。默认使用 `portfolio_cash_lot_floor`，不把预期失败当作通过条件。

```bash
set -euo pipefail
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RUN_DIR="/tmp/a-share-selection-p1-portfolio-capacity-$RUN_ID"
SYMBOLS=000009,000021,000039,000060,000069,000100,000157,000301,000338,000400,000423,000568,000625,000661,000708,000768,000786,000895,000963,001979,002001,002007,002024,002129,002179,002230,002236,002241,002252,002271,002304,002311,002352,002410,002459,002460,002466,002493,002508,002555
SIGNAL_DATES=(2025-03-20 2025-06-20 2025-09-19 2025-12-19 2026-04-17 2026-05-20)
uv run --with pandas --with numpy --with baostock --with-requirements skills/a-share-selection-strategy/requirements-ml.txt python skills/a-share-selection-strategy/scripts/run_baostock_walk_forward.py \
  --symbols "$SYMBOLS" \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --signal-dates "${SIGNAL_DATES[@]}" \
  --output-dir "$RUN_DIR" \
  --allocation-model portfolio_cash_lot_floor \
  --cash-budget 3000000 \
  --max-open-positions 10 \
  --max-gross-weight 1.0 \
  --max-gross-notional 3000000 \
  --max-cash-reserved 3000000 \
  --fail-on-symbol-overlap \
  --drop-invalid-rows
python3 skills/a-share-selection-strategy/scripts/validate_walk_forward_manifest.py \
  --manifest "$RUN_DIR/run_manifest.json" \
  --output "$RUN_DIR/run_manifest_validation.json" \
  --signal-dates "${SIGNAL_DATES[@]}" \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 的期望值必须从刚生成的 artifact 提取：

```bash
eval "$(
RUN_DIR="$RUN_DIR" python3 - <<'PY'
import json
import os
import shlex
from pathlib import Path

def bash_array(name, values):
    words = " ".join(shlex.quote(str(value)) for value in values)
    print(f"{name}=({words})")

run = Path(os.environ["RUN_DIR"])
manifest = json.loads((run / "run_manifest.json").read_text())
summary = json.loads((run / "prediction_run_summary.json").read_text())
bash_array("VALIDATION_SIGNAL_DATES", manifest["signal_dates"])
bash_array("VALIDATION_SYMBOLS", manifest["symbols"])
bash_array("VALIDATION_CANDIDATES", [item["candidates"] for item in summary["signals"]])
print("FINAL_EQUITY=" + shlex.quote(str(summary["equity"]["final_equity"])))
print("PORTFOLIO_VIOLATIONS=" + shlex.quote(str(len(summary["portfolio"]["violations"]))))
PY
)"
python3 skills/a-share-selection-strategy/scripts/validate_walk_forward_artifacts.py \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/run_artifact_validation.json" \
  --signal-dates "${VALIDATION_SIGNAL_DATES[@]}" \
  --expected-symbols "${VALIDATION_SYMBOLS[@]}" \
  --expected-candidates "${VALIDATION_CANDIDATES[@]}" \
  --expected-final-equity "$FINAL_EQUITY" \
  --expected-portfolio-violations "$PORTFOLIO_VIOLATIONS" \
  --required-allocation-model portfolio_cash_lot_floor \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled \
  --manifest-validation "$RUN_DIR/run_manifest_validation.json" \
  --cash-budget 3000000 \
  --allow-dropped-invalid-rows
```

口径：

- `portfolio_violations>0` 不是组合容量门禁通过。
- `--expect-portfolio-violations` 只用于复现已知违规，不用于证明门禁通过。
- artifact validator 未传 `--manifest-validation` 但 run 目录存在 `run_manifest_validation.json` 时会自动校验该报告；`manifest_checked=false` 时不能说 manifest 门禁已纳入 artifact 复验。
- `calendar_model=business_day_closed_interval` 不是交易所日历。
- `tradestatus_holding_period_bars` 只覆盖价格表内已观测 bar，不补足缺失交易日、节假日或涨跌停规则。

## 单信号日定位链路

该链路只用于定位步骤，不替代 P1 组合容量门禁。

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/slice_prices_as_of.py --input prices.csv --output prices_signal_window.csv --as-of-date YYYY-MM-DD
uv run --with-requirements skills/a-share-selection-strategy/requirements-ml.txt python skills/a-share-selection-strategy/scripts/generate_lightgbm_predictions.py --input prices_signal_window.csv --output predictions_signal_window.csv --summary-output prediction_summary.json --fail-on-skipped
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --input predictions_signal_window.csv --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py --input predictions_signal_window.csv --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json --output prediction_candidates.csv --fail-on-skipped --fail-on-empty-result
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/allocate_candidate_capital.py --prices prices.csv --candidates prediction_candidates.csv --output prediction_sized_candidates.csv --cash-budget 1000000 --lot-size 100 --fail-on-unallocated
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/backtest_buy_hold.py --prices prices.csv --candidates prediction_sized_candidates.csv --output prediction_backtest.csv --hold-days 5 --fail-on-incomplete
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/portfolio_equity_curve.py --backtests prediction_backtest.csv --output prediction_equity_curve.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/portfolio_overlap_report.py --backtests prediction_backtest.csv --daily-output prediction_daily_positions.csv --overlap-output prediction_overlap.csv --summary-output prediction_overlap_summary.json --max-gross-weight 1.0 --max-gross-notional 1000000 --max-cash-reserved 1000000 --require-capital-fields
uv run --with pandas python skills/a-share-selection-strategy/scripts/summarize_walk_forward_run.py --run-dir RUN_DIR --output RUN_DIR/prediction_run_summary.json --expected-symbol-count N --required-tradability-model tradestatus_entry_exit_only --required-limit-rules-model not_modeled
```

`slice_prices_as_of.py` 的输出 CSV 会保留 `requested_as_of_date`、`actual_data_date` 和 `as_of_date_observed`。如果请求日不是实际交易行，后续候选、诊断和 HTML 报告必须按 `actual_data_date` 或候选 `date` 解释真实信号日。

`allocate_candidate_capital.py` 的 stdout 必须披露 `cash_budget`、`lot_size`、`capital_model` 和 `claim_boundary=local_sizing_not_broker_order`。这些字段只证明本地 sizing 计算可追溯，不能解释为真实成交、券商订单或真实现金容量证明。严格回测汇总应对 `portfolio_equity_curve.py` 显式使用 `--fail-on-incomplete`，否则默认只基于 complete trades 生成权益曲线。

## 验证命令

```bash
python3 -m json.tool skills/a-share-selection-strategy/evals/evals.json >/tmp/a-share-selection-evals.json
python3 -m json.tool skills/a-share-selection-strategy/scripts/example_config.json >/tmp/a-share-selection-example-config.json
python3 -m json.tool skills/a-share-selection-strategy/scripts/prediction_profile_config.json >/tmp/a-share-selection-prediction-config.json
python3 -m json.tool skills/a-share-selection-strategy/scripts/ultra_short_low_price_config.json >/tmp/a-share-selection-ultra-short-config.json
uv run --with pyyaml python - <<'PY'
import yaml
from pathlib import Path
assert yaml.safe_load(Path("skills/a-share-selection-strategy/agents/openai.yaml").read_text())["interface"]["display_name"]
PY
PYTHONPYCACHEPREFIX=/tmp/a-share-selection-pycache python3 -m py_compile skills/a-share-selection-strategy/scripts/*.py
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python -m unittest discover -s tests -v
```

Skill 结构校验器来自本机 skill-creator，不随本仓库发布：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" skills/a-share-selection-strategy
```
