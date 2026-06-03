# 通用选股策略 Skill

一套给 AI Agent 使用的通用选股策略 Skill。它把股票候选筛选拆成可解释、可验证、可复用的流程：先定义数据契约，再计算因子，之后评分、过滤、排序和解释结果。

本 Skill 不绑定任何行情源、券商接口或项目仓库。默认优先处理本地 CSV 或 Parquet 数据，适合用于 A 股、港股、美股等股票数据集的规则化选股、多因子评分、短线异动识别和策略审查。

## 亮点

| 能力 | 说明 |
|------|------|
| 通用选股流程 | 覆盖输入数据契约、股票池过滤、技术因子、短线异动、风险控制和输出解释。 |
| prediction-derived 剖面 | 保留从 prediction-derived 原实现提炼出的 A 股默认口径，但不依赖 prediction-derived 仓库或运行环境。 |
| 本地可复现脚本 | 提供 OHLCV 校验、候选股评分、通用配置和 prediction-derived 配置。 |
| 显式失败边界 | 字段缺失、预测缺失、配置错误、脚本环境问题都会显式暴露，不伪造成功结果。 |
| Agent 友好 | `SKILL.md` 可直接作为 Skill 入口，`evals/` 可用于验证 Agent 是否正确触发和使用。 |

## 快速开始

以下命令假设 `uv` 已安装并在 `PATH` 中。若当前环境没有 `uv`，可先创建临时虚拟环境：

```bash
python3 -m venv /tmp/stock-selection-skill-venv
/tmp/stock-selection-skill-venv/bin/python -m pip install -r requirements.txt
```

使用备用虚拟环境时，将下文 `uv run --with ... python` 替换为 `/tmp/stock-selection-skill-venv/bin/python`。
读取 Parquet 输入还需要安装 `pyarrow` 或 `fastparquet`；只处理 CSV 时不需要额外 Parquet 引擎。无 `uv` 且需要 Parquet 时，使用 `/tmp/stock-selection-skill-venv/bin/python -m pip install -r requirements-parquet.txt`。运行真实 LightGBM 预测生成器时，还需要安装 `requirements-ml.txt`。
完全离线环境还必须提前准备好依赖：`uv run --with pandas --with numpy` 可能需要访问网络或已有 uv 缓存；如果本机没有可用缓存或已安装解释器，应显式报告依赖缺失，不能改用 mock 数据、跳过 pandas/numpy，或把依赖失败写成脚本验证通过。

本仓库以 CLI 脚本为稳定入口。若在 Python 代码中复用脚本，请将 `scripts/` 加入 `PYTHONPATH` 或 `sys.path`；仓库当前不提供可安装 Python package。不要把 `from scripts.score_candidates import ...` 这类 package-style import 当成稳定 API；它可能在 import 阶段看似成功，但调用时因脚本内部顶层依赖未在路径中而失败。`python3 -S scripts/<name>.py --help` 的依赖轻量化门禁只覆盖带 `argparse`/`main()`/`__main__` 的 CLI 入口；`stock_selection_*.py`、`lightgbm_prediction_summary.py` 等 helper/import 模块没有帮助界面承诺，其顶层 pandas/numpy import 失败不应写成用户入口缺口。

### 1. 生成可运行 demo 数据

```bash
python3 scripts/create_demo_data.py --output /tmp/stock-selection-demo
```

生成文件：

- `/tmp/stock-selection-demo/prices.csv`
- `/tmp/stock-selection-demo/prices_with_prediction.csv`

### 2. 校验行情文件

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-demo/prices.csv
```

如需按某个评分配置同步检查 profile 专属字段，可传入 `--config`。例如 prediction-derived 会额外检查 `market`、`prediction` 或 `prediction_score`、`turn` 或 `turnover`：

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-demo/prices_with_prediction.csv \
  --config scripts/prediction_profile_config.json
```

`--min-history-rows 0` 或显式调低历史门槛只适合 debug 级字段校验。若评分配置仍要求默认 120 行历史，`score_candidates.py` 会按配置重新检查并跳过短历史标的；不能把低门槛 `OK: validated ...` 写成真实评分可用。

### 3. 使用通用配置评分

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-demo/candidates.csv
```

### 4. 使用 prediction-derived 配置评分

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices_with_prediction.csv \
  --config scripts/prediction_profile_config.json \
  --output /tmp/stock-selection-demo/prediction_candidates.csv
```

该 demo 中的 `prediction_score` 是 `create_demo_data.py` 生成的合成输入。`score_candidates.py` 只消费该列，不训练、不生成、也不验证真实 LightGBM prediction；输出中的 `prediction_source=external_unverified lightgbm_not_executed_by_this_script=true` 是预期提示。不要把该 smoke test 的退出码 0 或候选数写成真实 LightGBM 链路、真实 prediction-derived 策略或真实回测已经通过。

### 5. 可选：低价超短离线诊断 demo

该场景用于验证 `ultra_short_low_price_config.json` 和今日总控 CLI 的诊断是否清楚。它会生成更多本地样本，覆盖通过、价格超限、成交额不足、换手率不足、ST、停牌和一字板等典型情况。它仍是合成数据，不是今日真实 A 股扫描。

```bash
python3 scripts/create_demo_data.py \
  --output /tmp/stock-selection-low-price-demo \
  --days 160 \
  --scenario low-price-ultra-short
uv run --with pandas --with numpy python scripts/run_today_a_share_selection.py \
  --prices-input /tmp/stock-selection-low-price-demo/prices.csv \
  --output-dir /tmp/stock-selection-low-price-demo/today \
  --mode auto
```

检查重点：

- `summary.json` 中 `requested_mode=auto`、`mode=generic`、`mode_decision=auto_generic`、`consumes_prediction_columns=false`、`lightgbm_not_used=true`、`lightgbm_output_source=not_used`、`lightgbm_executed_by_runner=false`、`prices_rows=1120`、`candidate_rows=1`、`diagnostic_rows=7`。
- `diagnostics.csv` 中的 `failed_thresholds`、`failed_thresholds_zh`、`selection_status`、`short_reason`。
- 价格、成交额、换手率、ST、停牌和一字板失败项只能解释为本地 demo 诊断覆盖，不能写成真实可交易性或全市场结论。

### 6. 可选：读取 Parquet 输入

```bash
uv run --with pandas --with numpy --with pyarrow python - <<'PY'
from pathlib import Path
import pandas as pd
base = Path("/tmp/stock-selection-demo")
pd.read_csv(base / "prices.csv", dtype={"symbol": str}).to_parquet(
    base / "prices.parquet",
    index=False,
)
PY
uv run --with pandas --with numpy --with pyarrow python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-demo/prices.parquet
uv run --with pandas --with numpy --with pyarrow python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices.parquet \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-demo/candidates_parquet.csv
```

这只验证 Parquet 输入读取；候选输出仍是 CSV。当前标准 CLI 链路不支持严格无 CSV 中间产物。如果用户要求全链路中间完全不出现 CSV，必须先停止并说明需要改造脚本输出、runner 固定路径、artifact validator 和测试；不得先写 CSV 再转换为 Parquet 后声称满足无 CSV。

### 7. 可选：本地 demo 的 sizing、回测和组合报告

快速开始第 4 步会使用 demo 数据末尾作为候选信号日；如果直接对该最新信号日运行 `--fail-on-incomplete` 回测，会因为缺少未来 5 个交易行而显式失败。这是正确门禁，不是脚本故障。

下面的本地 smoke 先把评分窗口截到较早的 `2025-06-25`，该日期同时满足 prediction-derived 默认 120 行历史和未来 5 日回测所需价格行；再用完整 demo 行情做 sizing、5 日 close-to-close 基线回测、等权资金曲线和组合容量报告：

```bash
uv run --with pandas --with numpy python scripts/slice_prices_as_of.py \
  --input /tmp/stock-selection-demo/prices_with_prediction.csv \
  --output /tmp/stock-selection-demo/prices_signal_window_2025-06-25.csv \
  --as-of-date 2025-06-25
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-demo/prices_signal_window_2025-06-25.csv \
  --config scripts/prediction_profile_config.json
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices_signal_window_2025-06-25.csv \
  --config scripts/prediction_profile_config.json \
  --output /tmp/stock-selection-demo/prediction_candidates_2025-06-25.csv \
  --fail-on-skipped \
  --fail-on-empty-result
uv run --with pandas --with numpy python scripts/allocate_candidate_capital.py \
  --prices /tmp/stock-selection-demo/prices.csv \
  --candidates /tmp/stock-selection-demo/prediction_candidates_2025-06-25.csv \
  --output /tmp/stock-selection-demo/prediction_sized_candidates_2025-06-25.csv \
  --cash-budget 1000000 \
  --lot-size 100 \
  --fail-on-unallocated
uv run --with pandas --with numpy python scripts/backtest_buy_hold.py \
  --prices /tmp/stock-selection-demo/prices.csv \
  --candidates /tmp/stock-selection-demo/prediction_sized_candidates_2025-06-25.csv \
  --output /tmp/stock-selection-demo/prediction_backtest_2025-06-25.csv \
  --hold-days 5 \
  --cost-bps 10 \
  --slippage-bps 5 \
  --expected-signal-date 2025-06-25 \
  --fail-on-incomplete
uv run --with pandas --with numpy python scripts/portfolio_equity_curve.py \
  --backtests /tmp/stock-selection-demo/prediction_backtest_2025-06-25.csv \
  --output /tmp/stock-selection-demo/prediction_equity_curve_2025-06-25.csv \
  --fail-on-incomplete
uv run --with pandas --with numpy python scripts/portfolio_overlap_report.py \
  --backtests /tmp/stock-selection-demo/prediction_backtest_2025-06-25.csv \
  --daily-output /tmp/stock-selection-demo/prediction_daily_positions_2025-06-25.csv \
  --overlap-output /tmp/stock-selection-demo/prediction_overlap_2025-06-25.csv \
  --summary-output /tmp/stock-selection-demo/prediction_overlap_summary_2025-06-25.json \
  --max-open-positions 10 \
  --max-gross-weight 1.0 \
  --max-gross-notional 1000000 \
  --max-cash-reserved 1000000 \
  --fail-on-symbol-overlap \
  --require-capital-fields
```

这仍然只是合成 demo 数据上的本地基线 smoke:

- `prediction_score` 仍是合成输入。
- 回测输出中的 `tradability_model=not_modeled` 和 `limit_rules_model=not_modeled` 表示真实可交易性和涨跌停规则仍未证明。
- 资金曲线的 `final_equity` 不能写成真实收益验证。
- `portfolio_equity_curve.py` 使用 `equal_weight_completed_trades`。即使回测 CSV 含 `weight` 字段，也不能把 `final_equity` 写成按 sizing 权重计算的组合收益。
- `portfolio_overlap_report.py` 的资本字段门禁通过不证明资金曲线使用了这些权重。
- `portfolio_overlap_report.py` 的 `calendar_model=business_day_closed_interval` 只说明用 pandas 工作日闭区间展开入场到退出日期；它不是 A 股、美股或任一交易所日历模型，也不覆盖节假日、停复牌或涨跌停可交易性。

`backtest_buy_hold.py` 默认 `cost_bps=0.0`、`slippage_bps=0.0`；即使 `--fail-on-incomplete` 通过且 `status=complete`，输出 `return` 也只是零成本 close-to-close 基线，不是含真实交易成本、滑点、涨跌停或券商成交约束的净收益。

### 8. 可选：校验 Skill 结构

`quick_validate.py` 来自本机安装的 skill-creator 工具，不随本仓库发布。维护者或 Skill 开发者可运行该检查；第三方环境没有校验器时可跳过。把下面的 `QUICK_VALIDATE` 替换为你机器上的校验器路径：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" "$(pwd)"
```

期望输出：

```text
Skill is valid!
```

该检查只验证 Skill 元数据和结构，不验证 Python 依赖、脚本 smoke、真实行情接入、真实 LightGBM prediction 生成链路、真实回测或收益表现。

最小字段要求：

| 字段 | 含义 |
|------|------|
| `symbol` | 股票代码 |
| `date` | 交易日期 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |

prediction-derived 配置要求输入包含 `market` 列，且 A 股记录使用 `A-share`；同时必须包含 `prediction` 或 `prediction_score` 列，取值范围为 0 到 1。该列表示上游模型已经生成的上涨概率；评分脚本不会训练 LightGBM，也不会用动量分伪造机器学习预测。若输入同时包含 `prediction_score` 和 `prediction`，当前评分优先使用 `prediction_score`；两列冲突时，不能因为 `prediction` 更高就认定应通过阈值，必须先统一或审计预测列。

如果 prediction-derived 输入缺少 `prediction` 或 `prediction_score`，不要运行评分产出候选股；使用 `docs/output-templates.md` 中的“prediction-derived 缺少 prediction”模板说明失败原因。

如果需要真实生成 `prediction_score`，可使用可选脚本 `generate_lightgbm_predictions.py`。该脚本使用时间序列切分，只在训练切分上拟合 `StandardScaler`，并在缺少 `lightgbm` 或 `scikit-learn` 时显式失败：

```bash
python3 scripts/create_demo_data.py --output /tmp/stock-selection-ml-demo --days 220
uv run --with pandas --with numpy --with scikit-learn --with lightgbm \
  python scripts/generate_lightgbm_predictions.py \
  --input /tmp/stock-selection-ml-demo/prices.csv \
  --output /tmp/stock-selection-ml-demo/prices_generated_prediction.csv \
  --summary-output /tmp/stock-selection-ml-demo/prediction_summary.json \
  --fail-on-skipped
```

生成后可用 prediction-derived 配置继续校验和评分，形成本地 demo 的 prediction 生成闭环：

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-ml-demo/prices_generated_prediction.csv \
  --config scripts/prediction_profile_config.json
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-ml-demo/prices_generated_prediction.csv \
  --config scripts/prediction_profile_config.json \
  --output /tmp/stock-selection-ml-demo/prediction_candidates.csv \
  --fail-on-skipped \
  --fail-on-empty-result
```

该闭环只证明合成 demo 数据上的本地脚本可执行。

`prediction_scope=latest_probability_repeated_for_scoring` 表示最新预测概率被重复写入该标的所有行，供评分脚本消费当前概率，不是逐日历史预测序列。评分摘要中的 `prediction_source=external_unverified lightgbm_not_executed_by_this_script=true` 表示评分脚本本身不验证上游训练过程。

即使上一条命令刚生成了 `prediction_score`，仍需单独核验训练窗口、标签、特征、时间序列切分、跳过标的和未来泄漏风险。LightGBM 质量边界以 `docs/prediction-derived-profile.md` 的“LightGBM 质量边界”为准；不能把候选数或退出码写成真实策略收益、真实可交易性、真实 A 股全市场有效性或模型质量已证明。

真实 A 股行情可先落地为本地文件，再进入同一链路。下面示例使用 baostock，输出行情 CSV 和元数据 JSON；真实环境失败时命令会非 0，不应改用 mock 数据。门禁不能只看命令退出码，还必须检查 metadata 中 `rows > 0`、`symbol_count == len(requested_symbols)`、`failed_symbols == []`、`empty_symbols == []`、`invalid_rows == 0`、`non_trading_rows == 0`。脚本会输出 `preclose/pctChg/tradestatus/isST`；若 baostock 返回停牌或异常行导致不可交易或 `volume/amount/turn` 为空，脚本默认失败；只有显式加 `--drop-invalid-rows` 时才会丢弃异常行，并在 metadata 记录 `dropped_invalid_rows` 和示例。

```bash
uv run --with pandas --with numpy --with baostock python scripts/fetch_baostock_a_share.py \
  --symbols 000001,600000 \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --output /tmp/stock-selection-a-share/prices.csv \
  --metadata-output /tmp/stock-selection-a-share/metadata.json \
  --fail-on-fetch-error
```

P2 真实涨跌停规则门禁当前仍是 `not_modeled`:

- `preclose/pctChg/tradestatus/isST` 只是行情控制和诊断字段，不是 `up_limit/down_limit/limit_status` 这类直接涨跌停字段；不得用 `preclose + pctChg`、股票前缀或 `isST` 粗推真实涨跌停规则。
- `probe_baostock_limit_fields.py` 只做字段可用性探针，不做规则推断；读取结果时必须看 `summary.supported_direct_limit_fields`、`summary.direct_limit_field_available` 和 `rule_inference_performed=false`，不能只看控制字段可用或候选字段列表。
- walk-forward 命令中的 `--required-limit-rules-model not_modeled` 只是在 runner、manifest validator 和 artifact validator 中锁定并校验“未建模”口径保持一致，不是 P2 通过。

可复制的 P2A 完整控制字段严格探针如下。若返回 `provider_error_fields`，例如 `turn/volume/amount`，即使 JSON 已写出，也只能记录为严格探针失败，不能写成 P2A 严格通过:

```bash
uv run --with pandas --with numpy --with baostock python scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST,turn,volume,amount \
  --output /tmp/stock-selection-p2a-limit-field-refresh/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

若要只复验核心控制字段可取，可收窄到 `preclose,pctChg,tradestatus,isST`。该命令返回 0 也只证明核心控制字段和直接候选字段可用性口径，不证明真实涨跌停规则已建模:

```bash
uv run --with pandas --with numpy --with baostock python scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST \
  --output /tmp/stock-selection-p2a-limit-field-core/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

akshare A 股入口会先尝试 `stock_zh_a_hist` 中文列；该接口失败或空结果时，会在 metadata 中记录 `fallback_errors` 并转用 `stock_zh_a_daily` 英文字段。真实环境失败时命令应非 0，不得改用 mock 或缓存样例冒充成功。取数窗口必须覆盖评分配置的最小历史行数；默认通用配置需要每个标的至少 `120` 行，`2024-01-01` 到 `2024-06-30` 这类半年窗口可能不足。

```bash
uv run --with pandas --with numpy --with akshare python scripts/fetch_akshare_a_share.py \
  --symbols 000001 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/stock-selection-akshare/prices.csv \
  --metadata-output /tmp/stock-selection-akshare/metadata.json \
  --fail-on-fetch-error
```

取数成功后继续使用通用配置校验和评分，并保留逐标的阈值诊断：

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-akshare/prices.csv
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-akshare/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-akshare/candidates.csv \
  --diagnostics-output /tmp/stock-selection-akshare/score_diagnostics.csv
```

如果 `candidates=0` 且 `effective_empty_result=true`，这表示脚本成功运行但没有标的通过当前阈值；不要写成“产生候选股”。用 `score_diagnostics.csv` 查看每个已评分 symbol 的 `failed_thresholds`。如果 metadata 中 `fallback_errors` 非空，必须说明主接口失败且已使用 fallback provider；fallback 成功不等于主接口稳定可用。akshare 输出可满足通用 OHLCV 和 `turn` 口径，但仍不生成真实 `prediction/prediction_score`，不能直接解释成 prediction-derived 或 LightGBM 链路通过。

本地已落地行情可以使用今日选股总控 CLI 串联校验、评分和诊断。默认 `--mode auto` 会先检查输入是否包含 prediction-derived 必需列；缺少 `prediction` 或 `prediction_score` 时，会显式选择 generic 低价超短剖面，并在 `run_manifest.json` 记录 `requested_mode`、实际 `mode`、`mode_decision` 和 `mode_decision_reason`。若输入包含 prediction-derived 必需列，auto 会使用外部 prediction 评分，但 `consumes_prediction_columns=true`、`lightgbm_output_source=external_input`、`lightgbm_executed_by_runner=false` 仍表示总控 CLI 只消费输入预测列，没有训练或执行 LightGBM。它不是静默降级，也不生成 LightGBM prediction：

```bash
uv run --with pandas --with numpy python scripts/run_today_a_share_selection.py \
  --prices-input /tmp/stock-selection-akshare/prices.csv \
  --output-dir /tmp/stock-selection-today-low-price \
  --mode auto \
  --fail-on-skipped
```

如果显式使用 `--mode prediction`，输入必须已经包含 `market=A-share`、`prediction` 或 `prediction_score`，以及 `turn` 或 `turnover`；缺少 prediction 时会在 validate 阶段失败并保留 manifest，不会自动改走通用评分。低价超短剖面还要求 `amount`、`turn`、`tradestatus` 和 `isST` 等可交易字段；akshare 日线输出没有 `tradestatus/isST`，会按门禁失败，不能静默放宽成“可交易性已验证”。

如需合并东方财富实时快照展示字段，可让总控 CLI 先调用快照入口。`spot_price`、`spot_pct_chg`、`spot_amount`、`spot_industry` 只进入候选和诊断展示，不参与核心评分；如果分页失败，metadata 会写出 `partial_result=true`，不能写成全市场实时扫描完成：

```bash
uv run --with pandas --with numpy python scripts/run_today_a_share_selection.py \
  --prices-input /tmp/stock-selection-akshare/prices.csv \
  --output-dir /tmp/stock-selection-today-low-price \
  --mode auto \
  --fetch-spot eastmoney \
  --spot-pages 5 \
  --fail-on-partial-spot
```

实时快照失败时只允许走显式下一步：增加重试或稍后重跑、使用 `--fail-on-partial-spot` 让部分分页直接失败、换源并披露 `source_scope`，或在用户接受陈旧口径时复用已落地快照。`summary.json.spot_metadata.allowed_failure_actions` 会记录这些允许动作；不得把 partial result、空快照或换源结果写成完整实时全市场扫描。

如果没有本地历史行情文件，总控 CLI 也可以先调用仓库内显式取数脚本，再执行同一套校验和评分。下面示例使用 baostock，因为低价超短剖面需要 `tradestatus/isST` 门禁字段；`fetch_history` 非 0 时流水线会停止，不会继续评分：

```bash
uv run --with pandas --with numpy --with baostock python scripts/run_today_a_share_selection.py \
  --output-dir /tmp/stock-selection-today-low-price \
  --mode auto \
  --history-source baostock \
  --symbols 000001,600000 \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-skipped
```

`--symbols` 接受六位 A 股代码，也接受 `sh.600000`、`sz.000001` 这类前缀形式；manifest 和 `selected_symbols.json` 会记录归一化后的六位代码。

也可以用东方财富快照先筛一批低价高成交额标的，再抓历史日线。这个流程的 `selected_symbols.json` 只证明“按实时快照字段筛出了历史抓取列表”，不证明实时全市场扫描完整，也不证明这些标的最终通过历史评分。spot 输入至少需要可识别的 symbol 列和 price/amount 字段；symbol 列支持 `symbol/code/code_id/stock_code/ticker/Ticker`，`sh.600000` 和 `sz.000001` 会归一化为六位代码，价格字段支持 `spot_price/price/close`，成交额字段支持 `spot_amount/amount`：

```bash
uv run --with pandas --with numpy --with baostock python scripts/run_today_a_share_selection.py \
  --output-dir /tmp/stock-selection-today-low-price \
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

美股等通用 OHLCV 可先通过 yfinance 落地，再走通用校验和评分。真实环境失败时命令会非 0，不得改用 mock 或缓存样例冒充成功；门禁还必须检查 metadata 中 `rows > 0`、`symbol_count == len(requested_symbols)`、`failed_symbols == []`、`empty_symbols == []`。该脚本写入原始 `Close`，不会用 `Adj Close` 静默替代 `close`；`--timeout-seconds` 用于限制每票拉取超时。`--market` 只是写入 CSV 和 metadata 的标签，不校验 yfinance symbol 所属市场、交易所或交易日历。

```bash
uv run --with pandas --with numpy --with yfinance python scripts/fetch_yfinance_ohlcv.py \
  --symbols AAPL,MSFT \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --output /tmp/stock-selection-us/prices.csv \
  --metadata-output /tmp/stock-selection-us/metadata.json \
  --timeout-seconds 30 \
  --fail-on-fetch-error
```

取数成功后继续使用通用配置校验和评分：

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-us/prices.csv
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-us/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-us/candidates.csv \
  --diagnostics-output /tmp/stock-selection-us/score_diagnostics.csv \
  --fail-on-skipped \
  --fail-on-empty-result
```

yfinance 裸 OHLCV 不含 `turn` 或 `turnover`，通用评分会输出 `turnover_assumption=neutral_series_missing_turnover` 并在 stderr 说明使用 neutral turnover series；报告候选时必须保留这个假设。`score_diagnostics.csv` 会记录每个已评分 symbol 的阈值失败项和是否入选，用于解释未入选标的，但它仍不是回测或收益证明。`end-date` 可能落在非交易日，实际数据范围以 metadata 中每个 symbol 的 `date_min/date_max` 为准；fetch 退出 0 且 `validate_ohlcv.py` 通过，也不能把非交易日 `end-date` 写成实际最后交易日、信号日或可回测入场日。该链路不生成或验证 LightGBM prediction，不适用于 prediction-derived；若强行使用 prediction-derived 配置，仍会因为缺少 `prediction/prediction_score` 和 `turn/turnover` 显式失败。

`backtest_buy_hold.py --require-tradable-bars` 是 entry/exit-only 门禁，只检查入场和退出 bar 的 `tradestatus=1`，模型名为 `tradestatus_entry_exit_only`。如果需要更严格的本地可交易性检查，可额外传入 `--require-tradable-holding-period`；该模式会检查价格表内从入场到退出的已观测 bar 都是 `tradestatus=1`，模型名为 `tradestatus_holding_period_bars`。这仍只是已落地价格表内的 observed bars 门禁，不补全真实交易所日历、缺失交易日、节假日、临时休市、涨跌停、真实订单或券商成交容量。

P3 外部源稳定性观察使用固定总控脚本重复调用 akshare、yfinance 和 baostock 取数入口。该脚本只证明当前窗口、当前参数和当前网络环境下的连续复验结果；即使 `all_sources_all_iterations_passed=true`，也不能写成公网数据源长期稳定。

```bash
RUN_DIR=/tmp/stock-selection-p3-external-$(date -u +%Y%m%dT%H%M%SZ)
uv run --with pandas --with numpy --with akshare --with yfinance --with baostock \
  python scripts/probe_external_source_stability.py \
    --output-dir "$RUN_DIR/runs" \
    --summary-output "$RUN_DIR/summary.json" \
    --iterations 3 \
    --akshare-symbols 000001,600000 \
    --yfinance-symbols AAPL,MSFT \
    --baostock-symbols 000001,600000
```

读取 `summary.json` 时必须检查 `summary.sources.*.all_passed`、逐次 `metadata`、`checks` 和 `long_term_stability_claim=not_proven`。akshare 的 `hist_provider_clean` 是观察项：若该项为 false 而其他必需检查通过，只能说明主接口失败后 fallback provider 成功，不能写成 `stock_zh_a_hist` 稳定。yfinance 的实际最后交易日仍看每个 symbol 的 `date_max`；当 yfinance 三轮均返回 `rows=0`、`symbol_count=0`、`empty_symbols=["AAPL","MSFT"]` 时，必须写成外部源严格门禁失败，不能复用早期成功记录说当前 Yahoo/yfinance 可用。baostock 仍需检查 `non_trading_rows=0`、`tradestatus_missing_rows=0` 和 `adjustflag=3`。

真实回测必须先按信号日截断评分输入，避免用未来行情生成候选；回测价格文件可以保留信号日之后的真实行用于出场。P1 组合容量门禁默认使用一键 runner 的 `portfolio_cash_lot_floor` 路径，不把预期失败当作通过条件：

```bash
set -euo pipefail
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RUN_DIR="/tmp/stock-selection-p1-portfolio-capacity-$RUN_ID"
SYMBOLS=000009,000021,000039,000060,000069,000100,000157,000301,000338,000400,000423,000568,000625,000661,000708,000768,000786,000895,000963,001979,002001,002007,002024,002129,002179,002230,002236,002241,002252,002271,002304,002311,002352,002410,002459,002460,002466,002493,002508,002555
SIGNAL_DATES=(2025-03-20 2025-06-20 2025-09-19 2025-12-19 2026-04-17 2026-05-20)
uv run --with pandas --with numpy --with baostock --with-requirements requirements-ml.txt python scripts/run_baostock_walk_forward.py \
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
python3 scripts/validate_walk_forward_manifest.py \
  --manifest "$RUN_DIR/run_manifest.json" \
  --output "$RUN_DIR/run_manifest_validation.json" \
  --signal-dates "${SIGNAL_DATES[@]}" \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 的期望值从刚生成的 `run_manifest.json` 和 `prediction_run_summary.json` 提取，避免手填导致假绿或假失败：

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
python3 scripts/validate_walk_forward_artifacts.py \
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

如要让一键 runner 的回测步骤使用全持有期已观测 bar 可交易性门禁，可在 runner 命令中加入 `--require-tradable-holding-period`，并把后续 manifest validator、artifact validator 或手工 summary 的 `--required-tradability-model` 改为 `tradestatus_holding_period_bars`。默认 P1 示例仍使用 `tradestatus_entry_exit_only`，因此不能把旧产物解释成全持有期 observed bar 门禁通过。

若目标是复现已知组合风险暴露，而不是证明当前门禁通过，才在 runner、summary 和 manifest validator 中同时使用 `--expect-portfolio-violations`。summary 在该模式下退出 0 且 `quality_errors=[]`，只表示已知违规被显式允许；报告中的 `portfolio_violations>0` 仍不是组合容量门禁通过。手工运行 summary 时，只有传入 `--required-tradability-model` 和 `--required-limit-rules-model`，`quality_errors=[]` 才能覆盖这些模型口径；省略 required 参数时必须披露 JSON 中实际 `tradability_models` 和 `limit_rules_models`。若 artifact validator 使用非 0 的 `--expected-portfolio-violations` 后退出 0 且 `errors=[]`，这只说明 artifact 与已知违规数量一致；报告中的 `portfolio_violations>0` 仍不是组合容量门禁通过。artifact validator 只有传入 `--manifest-validation "$RUN_DIR/run_manifest_validation.json"` 时才会校验 manifest 报告；若输出 `manifest_checked=false`，不能说 manifest 门禁已纳入本次 artifact 复验。若 runner 显式设置 `--max-candidates M`，manifest validator 才同步传 `--expected-max-candidates M`。`portfolio_cash_lot_floor` 生成 `prediction_raw_candidates.csv`、`prediction_candidates.csv`、`prediction_sized_candidates.csv`、`prediction_skipped_candidates.csv` 和 `prediction_allocation_summary.json`；artifact validator 会交叉校验 allocation 与 overlap 的容量摘要。overlap summary 中的 `calendar_model=business_day_closed_interval` 仍只是 pandas 工作日闭区间，不是交易所日历、节假日、特殊交易日或全持有期停复牌可交易性门禁。`tradestatus_holding_period_bars` 只覆盖价格表内已观测 bar 的 `tradestatus=1`，不能补足真实交易所日历、缺失交易日或涨跌停规则。当前脚本仍不证明真实成交容量、券商订单或涨跌停规则。当前真实门禁优先级以 `docs/reviews/REAL-SCENARIO-GATES-2026-05-30.md` 为准。
输入约定：`symbol` 必须按文本保存以保留前导零；校验脚本会拒绝 1 到 3 位纯数字代码，避免把 `000001` 这类 A 股代码被表格软件损坏后的值当作有效输入。`date` 支持 `YYYY-MM-DD` 或 `YYYYMMDD`；`volume` 单位必须在同一文件内保持一致，脚本只能校验数值和非负，无法从纯数值可靠判断“股/手/张/成交额”是否混用。prediction-derived 的 `market` 只接受精确值 `A-share`，不会自动归一化 `A股`、`China` 等别名。

常见字段映射：akshare 中文列需映射为 `股票代码 -> symbol`、`日期 -> date`、`成交量 -> volume`、`成交额 -> amount`、`换手率 -> turn`，`stock_zh_a_daily` 英文字段需映射 `volume -> volume`、`amount -> amount`、`turnover -> turn`，其中 `成交额` 或 `amount` 不得映射为 `volume`；tushare 需将 `ts_code` 去掉 `.SZ`/`.SH` 后写入 `symbol`，`trade_date -> date`，`vol -> volume`，`amount -> amount`，`turnover_rate -> turn`；yfinance 需将 `Date/Symbol/Open/High/Low/Close/Volume` 映射为小写标准字段。yfinance 映射后只满足通用 OHLCV；若用于 prediction-derived，还必须外部补齐 `market=A-share`、真实上游 `prediction_score`、以及 `turn` 或 `turnover`，不能从 yfinance OHLCV 自动推断。不要把 `Adj Close` 静默替换为 `close`；使用复权价时要记录复权口径。多源合并时统一保留一个预测列，推荐先生成 `prediction_score = coalesce(prediction_score, prediction)`。

`score_candidates.py` 的 CLI 摘要会报告输入文件名、`input_symbols`、股票池过滤、历史不足、输入异常、单股失败、阈值过滤、`turnover_assumption`、`effective_empty_result`、`empty_result_reason` 和最终候选数量。股票池过滤包含 `market_filtered_symbols`、`prefix_allow_filtered_symbols`、`prefix_excluded_symbols` 分项。`threshold_failures` 是各阈值独立失败计数，不是互斥分类，不能和 `threshold_failed_symbols` 相加对账。prediction-derived 路径还会标记 `prediction_source=external_unverified`，表示脚本只消费上游预测，不验证该列是否由真实 LightGBM 链路生成。直接调用 Python API 时，`input` 字段由调用方自行记录或注入。

自动化流水线应把 `failed_symbols=0`、`insufficient_history_symbols=0`、`effective_empty_result=false` 作为成功门槛；也可在 CLI 中显式传入 `--fail-on-skipped` 和 `--fail-on-empty-result`，让跳过标的或 0 候选直接返回非 0。`failed_symbols>0` 表示存在单股运行期异常，即使脚本仍输出了其他候选，也应进入人工复核或失败处理。成功摘要会输出截断样例，例如 `failed_symbol_examples`、`insufficient_history_symbol_examples`，用于定位需要复核的标的。

`validate_ohlcv.py --min-history-rows 0` 的成功只覆盖基础字段、日期、数值和 profile 必需字段，不覆盖评分配置的历史窗口。默认 prediction-derived 评分仍要求 120 行历史；若 `score_candidates.py` 报 `code=bad_input output_written=false` 和 `insufficient_history_symbols>0`，这是输入不可评分，不是 0 候选成功。

配置中的 `output.max_candidates` 大于 0 时限制输出数量；设为 0 表示不截断候选结果。一键 runner 可用 `--max-candidates` 写出 run-scoped 配置，便于在 manifest 中追踪本次 top-N 门禁；也可用 `--allocation-model portfolio_cash_lot_floor` 启用组合级 sizing/cut，并生成 raw、selected、sized、skipped 和 allocation summary 证据。

## 策略框架

默认工作流分为六步：

1. 校验数据字段和质量。
2. 定义股票池，排除不符合市场、流动性或代码规则的标的。
3. 计算趋势动量、技术状态、短线异动和风险控制因子。
4. 使用配置权重计算 `total_score`。
5. 按阈值硬过滤，再按得分排序。
6. 输出候选股、入选原因、风险提示和数据窗口。

通用评分模板：

```text
total_score =
  trend_score * 0.30
  + momentum_score * 0.20
  + explosion_score * 0.35
  + risk_score * 0.15
```

prediction-derived 评分模板：

```text
total_score =
  prediction * 0.30
  + momentum_score * 0.20
  + explosion_score * 0.35
  + (1 - volatility) * 0.15
```

## 验证清单

修改 Skill 或脚本后建议执行：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" "$(pwd)"
# 或使用备用虚拟环境:
/tmp/stock-selection-skill-venv/bin/python "$QUICK_VALIDATE" "$(pwd)"
python3 -m json.tool evals/evals.json >/tmp/stock-selection-evals.json
python3 -m json.tool scripts/example_config.json >/tmp/stock-selection-example-config.json
python3 -m json.tool scripts/prediction_profile_config.json >/tmp/stock-selection-prediction-config.json
uv run --with pyyaml python - <<'PY'
import yaml
from pathlib import Path
assert yaml.safe_load(Path("agents/openai.yaml").read_text())["interface"]["display_name"]
PY
PYTHONPYCACHEPREFIX=/tmp/stock-selection-pycache python3 -m py_compile scripts/*.py
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python -m unittest discover -s tests -v
```

如需 smoke test，可使用 demo 数据运行；该 smoke 只验证本地文件读取、评分和输出流程，不代表真实行情接入、真实 LightGBM prediction 生成链路或真实回测已经通过。

```bash
python3 scripts/create_demo_data.py --output /tmp/stock-selection-demo
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-demo/candidates.csv
# 或使用备用虚拟环境:
/tmp/stock-selection-skill-venv/bin/python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-demo/candidates.csv
```

## 重要边界

- 本 Skill 不是投资建议，不承诺收益，不生成交易指令。
- 评分、校验、切片、预测和回测脚本以本地文件为入口；`fetch_baostock_a_share.py`、`fetch_akshare_a_share.py` 和 `fetch_yfinance_ohlcv.py` 是显式可选联网取数入口，只负责落地本地 gate 文件，不调用券商接口或交易接口。
- 没有真实回测时，不得声称策略收益已经验证。
- 使用机器学习预测时，必须明确训练窗口、预测窗口、标签定义和未来数据泄漏风险。
- prediction-derived 配置只复刻评分消费层；真实 LightGBM prediction 可由本仓库可选生成器或外部上游生成，但必须单独验证训练窗口、标签定义和未来泄漏风险。

## 授权

当前仓库未声明开源许可证。除 GitHub 平台允许的浏览和 clone 能力外，本仓库暂未授予复制、修改、分发或商用授权。若需要公开复用，应先由维护者选择并添加明确的 `LICENSE` 文件。

## 适合的使用方式

用于设计可解释选股流程、审查数据泄漏或不可验证结论，并基于本地行情文件生成候选股 CSV。
