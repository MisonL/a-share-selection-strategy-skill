# 通用选股策略 Skill

一套给 AI Agent 使用的通用选股策略 Skill。它把股票候选筛选拆成可解释、可验证、可复用的流程：先定义数据契约，再计算因子，之后评分、过滤、排序和解释结果。

本 Skill 不绑定任何行情源、券商接口或项目仓库。默认优先处理本地 CSV 或 Parquet 数据，适合用于 A 股、港股、美股等股票数据集的规则化选股、多因子评分、短线异动识别和策略审查。

## 亮点

| 能力 | 说明 |
|------|------|
| 通用选股流程 | 覆盖输入数据契约、股票池过滤、技术因子、短线异动、风险控制和输出解释。 |
| QSSS-derived 剖面 | 保留从 QSSS 原实现提炼出的 A 股默认口径，但不依赖 QSSS 仓库或运行环境。 |
| 本地可复现脚本 | 提供 OHLCV 校验、候选股评分、通用配置和 QSSS-derived 配置。 |
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

本仓库以 CLI 脚本为稳定入口。若在 Python 代码中复用脚本，请将 `scripts/` 加入 `PYTHONPATH` 或 `sys.path`；仓库当前不提供可安装 Python package。

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

如需按某个评分配置同步检查 profile 专属字段，可传入 `--config`。例如 QSSS-derived 会额外检查 `market`、`prediction` 或 `prediction_score`、`turn` 或 `turnover`：

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-demo/prices_with_prediction.csv \
  --config scripts/qsss_profile_config.json
```

### 3. 使用通用配置评分

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-demo/candidates.csv
```

### 4. 使用 QSSS-derived 配置评分

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices_with_prediction.csv \
  --config scripts/qsss_profile_config.json \
  --output /tmp/stock-selection-demo/qsss_candidates.csv
```

### 5. 可选：读取 Parquet 输入

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

### 6. 可选：校验 Skill 结构

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

QSSS-derived 配置要求输入包含 `market` 列，且 A 股记录使用 `A-share`；同时必须包含 `prediction` 或 `prediction_score` 列，取值范围为 0 到 1。该列表示上游模型已经生成的上涨概率；评分脚本不会训练 LightGBM，也不会用动量分伪造机器学习预测。

如果需要真实生成 `prediction_score`，可使用可选脚本 `generate_lightgbm_predictions.py`。该脚本使用时间序列切分，只在训练切分上拟合 `StandardScaler`，并在缺少 `lightgbm` 或 `scikit-learn` 时显式失败：

```bash
python3 scripts/create_demo_data.py --output /tmp/stock-selection-ml-demo --days 220
uv run --with pandas --with numpy --with scikit-learn --with lightgbm \
  python scripts/generate_lightgbm_predictions.py \
  --input /tmp/stock-selection-ml-demo/prices.csv \
  --output /tmp/stock-selection-ml-demo/prices_generated_prediction.csv
```

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

akshare A 股入口会先尝试 `stock_zh_a_hist` 中文列；该接口失败或空结果时，会在 metadata 中记录 `fallback_errors` 并转用 `stock_zh_a_daily` 英文字段。真实环境失败时命令应非 0，不得改用 mock 或缓存样例冒充成功。

```bash
uv run --with pandas --with numpy --with akshare python scripts/fetch_akshare_a_share.py \
  --symbols 000001 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/stock-selection-akshare/prices.csv \
  --metadata-output /tmp/stock-selection-akshare/metadata.json \
  --fail-on-fetch-error
```

美股等通用 OHLCV 可先通过 yfinance 落地，再走通用校验和评分。真实环境失败时命令会非 0，不得改用 mock 或缓存样例冒充成功；门禁还必须检查 metadata 中 `rows > 0`、`symbol_count == len(requested_symbols)`、`failed_symbols == []`、`empty_symbols == []`。该脚本写入原始 `Close`，不会用 `Adj Close` 静默替代 `close`；`--timeout-seconds` 用于限制每票拉取超时。

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

真实回测必须先按信号日截断评分输入，避免用未来行情生成候选；回测价格文件可以保留信号日之后的真实行用于出场：

```bash
uv run --with pandas --with numpy python scripts/slice_prices_as_of.py \
  --input /tmp/stock-selection-a-share/prices.csv \
  --output /tmp/stock-selection-a-share/prices_signal_window.csv \
  --as-of-date 2026-05-20
uv run --with-requirements requirements-ml.txt python scripts/generate_lightgbm_predictions.py \
  --input /tmp/stock-selection-a-share/prices_signal_window.csv \
  --output /tmp/stock-selection-a-share/predictions_signal_window.csv \
  --summary-output /tmp/stock-selection-a-share/prediction_summary.json \
  --fail-on-skipped
uv run --with pandas --with numpy python scripts/validate_ohlcv.py \
  --input /tmp/stock-selection-a-share/predictions_signal_window.csv \
  --config scripts/qsss_profile_config.json
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-a-share/predictions_signal_window.csv \
  --config scripts/qsss_profile_config.json \
  --output /tmp/stock-selection-a-share/qsss_candidates.csv \
  --fail-on-skipped \
  --fail-on-empty-result
uv run --with pandas --with numpy python scripts/allocate_candidate_capital.py --prices /tmp/stock-selection-a-share/prices.csv --candidates /tmp/stock-selection-a-share/qsss_candidates.csv --output /tmp/stock-selection-a-share/qsss_sized_candidates.csv --cash-budget 1000000 --lot-size 100 --fail-on-unallocated
uv run --with pandas --with numpy python scripts/backtest_buy_hold.py \
  --prices /tmp/stock-selection-a-share/prices.csv \
  --candidates /tmp/stock-selection-a-share/qsss_sized_candidates.csv \
  --output /tmp/stock-selection-a-share/qsss_backtest.csv \
  --hold-days 5 \
  --cost-bps 10 --slippage-bps 5 \
  --fail-on-incomplete
uv run --with pandas --with numpy python scripts/portfolio_equity_curve.py --backtests /tmp/stock-selection-a-share/qsss_backtest.csv --output /tmp/stock-selection-a-share/qsss_equity_curve.csv
uv run --with pandas --with numpy python scripts/portfolio_overlap_report.py --backtests /tmp/stock-selection-a-share/qsss_backtest.csv --daily-output /tmp/stock-selection-a-share/qsss_daily_positions.csv --overlap-output /tmp/stock-selection-a-share/qsss_overlap.csv --summary-output /tmp/stock-selection-a-share/qsss_overlap_summary.json --max-gross-weight 1.0 --max-gross-notional 1000000 --max-cash-reserved 1000000 --require-capital-fields
```
`allocate_candidate_capital.py` 用信号日 close、现金预算和 lot size 生成可追溯 sizing 字段，模型为 `equal_cash_budget_lot_floor`。上例回测是未启用 `--require-tradable-bars` 的 close-to-close 基线；如需回测级可交易门禁，价格文件必须含 `tradestatus`，并显式加该参数。回测只透传资金字段；组合报告检查并发、同标的重叠、权重、名义金额和预留现金门禁；这些脚本仍不证明真实成交容量或判断涨跌停规则。当前真实门禁优先级以 `docs/reviews/REAL-SCENARIO-GATES-2026-05-30.md` 为准；复验目录可用 `scripts/summarize_walk_forward_run.py` 生成机器可检摘要。
输入约定：`symbol` 必须按文本保存以保留前导零；校验脚本会拒绝 1 到 3 位纯数字代码，避免把 `000001` 这类 A 股代码被表格软件损坏后的值当作有效输入。`date` 支持 `YYYY-MM-DD` 或 `YYYYMMDD`；`volume` 单位必须在同一文件内保持一致，脚本只能校验数值和非负，无法从纯数值可靠判断“股/手/张/成交额”是否混用。QSSS-derived 的 `market` 只接受精确值 `A-share`，不会自动归一化 `A股`、`China` 等别名。

常见字段映射：akshare 中文列需映射为 `股票代码 -> symbol`、`日期 -> date`、`成交量 -> volume`、`成交额 -> amount`、`换手率 -> turn`，`stock_zh_a_daily` 英文字段需映射 `volume -> volume`、`amount -> amount`、`turnover -> turn`，其中 `成交额` 或 `amount` 不得映射为 `volume`；tushare 需将 `ts_code` 去掉 `.SZ`/`.SH` 后写入 `symbol`，`trade_date -> date`，`vol -> volume`，`amount -> amount`，`turnover_rate -> turn`；yfinance 需将 `Date/Symbol/Open/High/Low/Close/Volume` 映射为小写标准字段。yfinance 映射后只满足通用 OHLCV；若用于 QSSS-derived，还必须外部补齐 `market=A-share`、真实上游 `prediction_score`、以及 `turn` 或 `turnover`，不能从 yfinance OHLCV 自动推断。不要把 `Adj Close` 静默替换为 `close`；使用复权价时要记录复权口径。多源合并时统一保留一个预测列，推荐先生成 `prediction_score = coalesce(prediction_score, prediction)`。

`score_candidates.py` 的 CLI 摘要会报告输入文件名、`input_symbols`、股票池过滤、历史不足、输入异常、单股失败、阈值过滤、`turnover_assumption`、`effective_empty_result`、`empty_result_reason` 和最终候选数量。股票池过滤包含 `market_filtered_symbols`、`prefix_allow_filtered_symbols`、`prefix_excluded_symbols` 分项。`threshold_failures` 是各阈值独立失败计数，不是互斥分类，不能和 `threshold_failed_symbols` 相加对账。QSSS-derived 路径还会标记 `prediction_source=external_unverified`，表示脚本只消费上游预测，不验证该列是否由真实 LightGBM 链路生成。直接调用 Python API 时，`input` 字段由调用方自行记录或注入。

自动化流水线应把 `failed_symbols=0`、`insufficient_history_symbols=0`、`effective_empty_result=false` 作为成功门槛；也可在 CLI 中显式传入 `--fail-on-skipped` 和 `--fail-on-empty-result`，让跳过标的或 0 候选直接返回非 0。`failed_symbols>0` 表示存在单股运行期异常，即使脚本仍输出了其他候选，也应进入人工复核或失败处理。成功摘要会输出截断样例，例如 `failed_symbol_examples`、`insufficient_history_symbol_examples`，用于定位需要复核的标的。

配置中的 `output.max_candidates` 大于 0 时限制输出数量；设为 0 表示不截断候选结果。

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

QSSS-derived 评分模板：

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
python3 -m json.tool scripts/qsss_profile_config.json >/tmp/stock-selection-qsss-config.json
uv run --with pyyaml python - <<'PY'
import yaml
from pathlib import Path
assert yaml.safe_load(Path("agents/openai.yaml").read_text())["interface"]["display_name"]
PY
PYTHONPYCACHEPREFIX=/tmp/stock-selection-pycache python3 -m py_compile scripts/create_demo_data.py scripts/validate_ohlcv.py scripts/score_candidates.py scripts/generate_lightgbm_predictions.py scripts/allocate_candidate_capital.py scripts/backtest_buy_hold.py scripts/stock_selection_backtest_rows.py scripts/stock_selection_capital.py scripts/portfolio_equity_curve.py scripts/portfolio_overlap_report.py scripts/fetch_baostock_a_share.py scripts/fetch_akshare_a_share.py scripts/fetch_yfinance_ohlcv.py scripts/slice_prices_as_of.py scripts/stock_selection_config.py scripts/stock_selection_data.py scripts/stock_selection_metrics.py scripts/stock_selection_output.py scripts/stock_selection_profile.py scripts/stock_selection_universe.py scripts/stock_selection_tradability.py scripts/stock_selection_diagnostics.py scripts/lightgbm_prediction_summary.py
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
- QSSS-derived 配置只复刻评分消费层；真实 LightGBM prediction 可由本仓库可选生成器或外部上游生成，但必须单独验证训练窗口、标签定义和未来泄漏风险。

## 授权

当前仓库未声明开源许可证。除 GitHub 平台允许的浏览和 clone 能力外，本仓库暂未授予复制、修改、分发或商用授权。若需要公开复用，应先由维护者选择并添加明确的 `LICENSE` 文件。

## 适合的使用方式

用于设计可解释选股流程、审查数据泄漏或不可验证结论，并基于本地行情文件生成候选股 CSV。
