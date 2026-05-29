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

## 目录结构

```text
stock-selection-strategy-skill/
|-- agents/
|   `-- openai.yaml
|-- SKILL.md
|-- README.md
|-- evals/
|   `-- evals.json
|-- tests/
|   |-- helpers.py
|   |-- test_stock_selection_config.py
|   |-- test_stock_selection_profile_gates.py
|   `-- test_stock_selection_scripts.py
`-- scripts/
    |-- example_config.json
    |-- create_demo_data.py
    |-- qsss_profile_config.json
    |-- score_candidates.py
    |-- stock_selection_config.py
    |-- stock_selection_data.py
    |-- stock_selection_diagnostics.py
    |-- stock_selection_metrics.py
    |-- stock_selection_output.py
    |-- stock_selection_profile.py
    |-- stock_selection_universe.py
    `-- validate_ohlcv.py
```

## 快速开始

以下命令假设 `uv` 已安装并在 `PATH` 中。若当前环境没有 `uv`，可先创建临时虚拟环境：

```bash
python3 -m venv /tmp/stock-selection-skill-venv
/tmp/stock-selection-skill-venv/bin/python -m pip install pandas numpy pyyaml
```

使用备用虚拟环境时，将下文 `uv run --with ... python` 替换为 `/tmp/stock-selection-skill-venv/bin/python`。
读取 Parquet 输入还需要安装 `pyarrow` 或 `fastparquet`；只处理 CSV 时不需要额外 Parquet 引擎。

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

### 5. 可选：校验 Skill 结构

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

输入约定：`symbol` 必须按文本保存以保留前导零；校验脚本会拒绝 1 到 3 位纯数字代码，避免把 `000001` 这类 A 股代码被表格软件损坏后的值当作有效输入。`date` 支持 `YYYY-MM-DD` 或 `YYYYMMDD`；`volume` 单位必须在同一文件内保持一致，脚本只能校验数值和非负，无法从纯数值可靠判断“股/手/张/成交额”是否混用。QSSS-derived 的 `market` 只接受精确值 `A-share`，不会自动归一化 `A股`、`China` 等别名。

常见字段映射：akshare 中文列需映射为 `股票代码 -> symbol`、`日期 -> date`、`成交量 -> volume`、`换手率 -> turn`；tushare 需将 `ts_code` 去掉 `.SZ`/`.SH` 后写入 `symbol`，`trade_date -> date`，`vol -> volume`，`turnover_rate -> turn`；yfinance 需将 `Date/Symbol/Open/High/Low/Close/Volume` 映射为小写标准字段。yfinance 映射后只满足通用 OHLCV；若用于 QSSS-derived，还必须外部补齐 `market=A-share`、真实上游 `prediction_score`、以及 `turn` 或 `turnover`，不能从 yfinance OHLCV 自动推断。不要把 `Adj Close` 静默替换为 `close`；使用复权价时要记录复权口径。多源合并时统一保留一个预测列，推荐先生成 `prediction_score = coalesce(prediction_score, prediction)`。

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

## 输出字段

`score_candidates.py` 默认输出 CSV，核心字段包括：

| 字段 | 含义 |
|------|------|
| `rank` | 候选排名 |
| `symbol` | 股票代码 |
| `name` | 股票名称 |
| `total_score` | 综合得分 |
| `prediction_score` | 模型上涨概率或输入预测分 |
| `momentum_score` | 动量得分 |
| `explosion_score` | 短线异动得分 |
| `risk_score` | 风险得分 |
| `recommendation` | 历史兼容字段，值为 `high_signal`、`medium_signal` 或 `low_signal` 的信号分层，非交易建议 |
| `key_reasons` | 主要入选原因 |
| `risk_notes` | 风险提示 |
| `data_window` | 使用的数据区间 |

## 验证清单

修改 Skill 或脚本后建议执行：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" "$(pwd)"
python3 -m json.tool evals/evals.json >/tmp/stock-selection-evals.json
python3 -m json.tool scripts/example_config.json >/tmp/stock-selection-example-config.json
python3 -m json.tool scripts/qsss_profile_config.json >/tmp/stock-selection-qsss-config.json
uv run --with pyyaml python - <<'PY'
import yaml
from pathlib import Path
assert yaml.safe_load(Path("agents/openai.yaml").read_text())["interface"]["display_name"]
PY
PYTHONPYCACHEPREFIX=/tmp/stock-selection-pycache python3 -m py_compile scripts/create_demo_data.py scripts/validate_ohlcv.py scripts/score_candidates.py scripts/stock_selection_config.py scripts/stock_selection_data.py scripts/stock_selection_metrics.py scripts/stock_selection_output.py scripts/stock_selection_profile.py scripts/stock_selection_universe.py scripts/stock_selection_diagnostics.py
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy python -m unittest discover -s tests -v
```

没有 `uv` 时，可使用前文的备用虚拟环境运行单测：

```bash
/tmp/stock-selection-skill-venv/bin/python -m unittest discover -s tests -v
```

如需 smoke test，可使用 demo 数据运行：

该 smoke 只验证本地文件读取、评分和输出流程，不代表真实行情接入、真实 LightGBM prediction 生成链路或真实回测已经通过。

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input /tmp/stock-selection-demo/prices.csv \
  --config scripts/example_config.json \
  --output /tmp/stock-selection-demo/candidates.csv
```

## 重要边界

- 本 Skill 不是投资建议，不承诺收益，不生成交易指令。
- 脚本只处理本地文件，不联网取数，不调用券商接口。
- 没有真实回测时，不得声称策略收益已经验证。
- 使用机器学习预测时，必须明确训练窗口、预测窗口、标签定义和未来数据泄漏风险。
- QSSS-derived 配置只复刻评分消费层；真实 LightGBM prediction 生成需要在上游单独实现和验证。

## 授权

当前仓库未声明开源许可证。除 GitHub 平台允许的浏览和 clone 能力外，本仓库暂未授予复制、修改、分发或商用授权。若需要公开复用，应先由维护者选择并添加明确的 `LICENSE` 文件。

## 适合的使用方式

- 让 AI Agent 设计一套可解释的选股流程。
- 审查选股策略是否存在数据泄漏、静默降级或不可验证结论。
- 基于已有本地行情文件生成候选股 CSV。
- 将已有项目中的选股逻辑提炼为通用 Agent 能力。
