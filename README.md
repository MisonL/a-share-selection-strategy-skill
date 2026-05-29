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
|   |-- test_stock_selection_config.py
|   `-- test_stock_selection_scripts.py
`-- scripts/
    |-- example_config.json
    |-- qsss_profile_config.json
    |-- score_candidates.py
    |-- stock_selection_config.py
    |-- stock_selection_diagnostics.py
    |-- stock_selection_metrics.py
    |-- stock_selection_output.py
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

### 1. 校验 Skill 结构

```bash
uv run --with pyyaml python /Users/mison/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Volumes/Work/code/stock-selection-strategy-skill
```

期望输出：

```text
Skill is valid!
```

### 2. 校验行情文件

```bash
uv run --with pandas --with numpy python scripts/validate_ohlcv.py --input prices.csv
```

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

### 3. 使用通用配置评分

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input prices.csv \
  --config scripts/example_config.json \
  --output candidates.csv
```

### 4. 使用 QSSS-derived 配置评分

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input prices_with_prediction.csv \
  --config scripts/qsss_profile_config.json \
  --output qsss_candidates.csv
```

QSSS-derived 配置要求输入包含 `market` 列，且 A 股记录使用 `A-share`；同时必须包含 `prediction` 或 `prediction_score` 列，取值范围为 0 到 1。该列表示上游模型已经生成的上涨概率；评分脚本不会训练 LightGBM，也不会用动量分伪造机器学习预测。

`score_candidates.py` 的 CLI 摘要会报告输入文件名、股票池过滤、历史不足、输入异常、单股失败、阈值过滤、`turnover_assumption`、`effective_empty_result` 和最终候选数量。QSSS-derived 路径还会标记 `prediction_source=external_unverified`，表示脚本只消费上游预测，不验证该列是否由真实 LightGBM 链路生成。直接调用 Python API 时，`input` 字段由调用方自行记录或注入。

自动化流水线应把 `failed_symbols=0` 作为成功门槛之一；`failed_symbols>0` 表示存在单股运行期异常，即使脚本仍输出了其他候选，也应进入人工复核或失败处理。

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
| `recommendation` | 展示分层，非交易建议 |
| `key_reasons` | 主要入选原因 |
| `risk_notes` | 风险提示 |
| `data_window` | 使用的数据区间 |

## 验证清单

修改 Skill 或脚本后建议执行：

```bash
uv run --with pyyaml python /Users/mison/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Volumes/Work/code/stock-selection-strategy-skill
python3 -m json.tool evals/evals.json >/tmp/stock-selection-evals.json
python3 -m json.tool scripts/example_config.json >/tmp/stock-selection-example-config.json
python3 -m json.tool scripts/qsss_profile_config.json >/tmp/stock-selection-qsss-config.json
PYTHONPYCACHEPREFIX=/tmp/stock-selection-pycache python3 -m py_compile scripts/validate_ohlcv.py scripts/score_candidates.py scripts/stock_selection_config.py scripts/stock_selection_metrics.py scripts/stock_selection_output.py scripts/stock_selection_diagnostics.py
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy python -m unittest discover -s tests -v
```

如需 smoke test，可准备本地行情 CSV 后运行：

该 smoke 只验证本地文件读取、评分和输出流程，不代表真实行情接入、真实 LightGBM prediction 生成链路或真实回测已经通过。

```bash
uv run --with pandas --with numpy python scripts/score_candidates.py \
  --input prices.csv \
  --config scripts/example_config.json \
  --output candidates.csv
```

## 重要边界

- 本 Skill 不是投资建议，不承诺收益，不生成交易指令。
- 脚本只处理本地文件，不联网取数，不调用券商接口。
- 没有真实回测时，不得声称策略收益已经验证。
- 使用机器学习预测时，必须明确训练窗口、预测窗口、标签定义和未来数据泄漏风险。
- QSSS-derived 配置只复刻评分消费层；真实 LightGBM prediction 生成需要在上游单独实现和验证。

## 适合的使用方式

- 让 AI Agent 设计一套可解释的选股流程。
- 审查选股策略是否存在数据泄漏、静默降级或不可验证结论。
- 基于已有本地行情文件生成候选股 CSV。
- 将已有项目中的选股逻辑提炼为通用 Agent 能力。
