# A-Share Selection Strategy

面向 AI Agent 的 A 股选股策略 Skill。它把候选筛选拆成可验证流程：数据契约校验、因子计算、硬过滤、排序、诊断和汇报。

本仓库默认处理已经落地的本地 CSV 或 Parquet 数据，A 股是默认工作流。联网取数只作为显式入口，必须先写成本地文件和 metadata，再进入同一套校验、评分和汇报流程。

## 目录结构

Skill 按标准外层容器存放：

```text
skills/
  a-share-selection-strategy/
    SKILL.md
    agents/openai.yaml
    evals/evals.json
    references/
    requirements*.txt
    scripts/
```

仓库根目录只保留项目说明、约束、CI 和测试。脚本稳定入口都在 `skills/a-share-selection-strategy/scripts/`。

## 从哪里开始

| 目标 | 入口 |
| --- | --- |
| AI Agent 接手任务 | [skills/a-share-selection-strategy/SKILL.md](skills/a-share-selection-strategy/SKILL.md) |
| 仓库执行约束 | [AGENTS.md](AGENTS.md) |
| 完整命令 cookbook | [skills/a-share-selection-strategy/references/runbook.md](skills/a-share-selection-strategy/references/runbook.md) |
| 文档索引和历史报告 | [skills/a-share-selection-strategy/references/index.md](skills/a-share-selection-strategy/references/index.md) |
| 因子、字段、输出口径 | [skills/a-share-selection-strategy/references/factor-framework.md](skills/a-share-selection-strategy/references/factor-framework.md) |
| 预测列消费边界 | [skills/a-share-selection-strategy/references/prediction-derived-profile.md](skills/a-share-selection-strategy/references/prediction-derived-profile.md) |
| 汇报模板 | [skills/a-share-selection-strategy/references/output-templates.md](skills/a-share-selection-strategy/references/output-templates.md) |

## 核心入口

| 能力 | CLI |
| --- | --- |
| 行情契约校验 | `skills/a-share-selection-strategy/scripts/validate_ohlcv.py` |
| 候选评分 | `skills/a-share-selection-strategy/scripts/score_candidates.py` |
| 今日 A 股总控 | `skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py` |
| 本地 demo 数据 | `skills/a-share-selection-strategy/scripts/create_demo_data.py` |
| 低价超短剖面 | `skills/a-share-selection-strategy/scripts/ultra_short_low_price_config.json` |
| 预测列消费剖面 | `skills/a-share-selection-strategy/scripts/prediction_profile_config.json` |

脚本以 CLI 为稳定入口。Python 复用时需自行将 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。

仅说“帮我选今天 A 股”但未提供行情文件或明确联网授权时，不运行 CLI、不输出候选股，先使用“无法直接选股”模板。

## 快速 demo

以下命令使用合成 demo 数据，只验证本地链路，不证明真实行情、真实预测、真实回测或收益。

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-demo

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.csv

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices.csv \
  --config skills/a-share-selection-strategy/scripts/example_config.json \
  --output /tmp/a-share-selection-demo/candidates.csv
```

低价超短总控 demo：

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py \
  --output /tmp/a-share-selection-low-price-demo \
  --days 160 \
  --scenario low-price-ultra-short

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /tmp/a-share-selection-low-price-demo/prices.csv \
  --output-dir /tmp/a-share-selection-low-price-demo/today \
  --mode auto
```

总控 CLI 默认同时写出 `report.html`，用于浏览器查看候选、诊断、步骤和证据路径；报告支持中英文切换，默认 `--html-report-language auto` 跟随运行环境。它只是 `summary.json`、`run_manifest.json`、`candidates.csv` 和 `diagnostics.csv` 的展示层，不替代机器字段或退出码。自动化场景可传 `--no-html-report` 关闭。

更多 Parquet、联网取数、历史回测和门禁命令见 [runbook](skills/a-share-selection-strategy/references/runbook.md)。

## 数据契约

最小行情字段：

| 字段 | 要求 |
| --- | --- |
| `symbol` | 文本保存，避免前导零丢失。 |
| `date` | 支持 `YYYY-MM-DD` 或 `YYYYMMDD`。 |
| `open/high/low/close` | 正数。 |
| `volume` | 非负；同一文件内单位必须一致。 |

常用可选字段：`name`、`market`、`amount`、`turn`、`turnover`、`tradestatus`、`isST`、`prediction`、`prediction_score`。

prediction-derived 输入必须包含：

- `market=A-share`
- `prediction` 或 `prediction_score`
- `turn` 或 `turnover`

`score_candidates.py` 只消费外部提供的预测列，不训练、不生成、也不证明上游模型质量。
`score_candidates.py --output` 目前只接受 `.csv`；把输出写成 `.parquet` 或 `.pq` 会显式失败。

## 汇报边界

- 不得伪造行情、候选股、LightGBM prediction、回测收益或联网结果。
- `effective_empty_result=true` 表示成功运行但没有候选，不等于策略有效。
- `output_written=false` 表示输入失败或严格门禁失败，不能写成成功 0 候选。
- `summary.json` 中有输出路径或旧文件存在不代表本次文件已生成；以 `prices_output_written`、`candidates_output_written`、`diagnostics_output_written` 为准。
- `input_metadata` 缺失或未声明 `real_market_data=true` 时，只能称为本地输入文件，不能写成真实行情源、今日全市场覆盖或数据源已验证。
- `input_metadata.source_type=synthetic_demo` 表示输入来自合成 demo，不是真实行情或真实选股结论。
- `run_today_a_share_selection.py` 生成的 `candidates.csv` 和 `diagnostics.csv` 会附带 runner provenance 字段，例如 `source_type`、`real_market_data`、`mode_decision`、`consumes_prediction_columns`、`prediction_model_executed_by_runner`、`lightgbm_executed_by_runner`。
- `allocate_candidate_capital.py` 只生成本地可追溯 sizing 字段；必须保留 `cash_budget`、`lot_size`、`capital_model` 和 `claim_boundary=local_sizing_not_broker_order`，不得解释为真实成交、券商订单或真实现金容量证明。
- `allocate_candidate_capital.py` 输出会附带 `sizing_claim_boundary=local_sizing_not_broker_order`；默认成功但存在 `unallocated` 行时会在 stdout 给出 warning，必须同时检查 `unallocated` 列和 `--fail-on-unallocated`。
- `report.html` 只用于人类阅读；事实仍以 JSON/CSV、退出码和门禁字段为准。若报告被 `--no-html-report` 主动关闭，不能写成报告生成失败；若报告写出失败，`html_report_written=false` 并记录 `html_report_error_type/html_report_error`。
- 候选、sizing、回测或资金曲线必须写明非投资建议、非交易指令、非真实成交、非收益证明。
- `failed_symbols` 大于 0 时必须披露，即使其他候选已输出。
- 中文展示字段只能从机器字段派生，不能反向覆盖机器事实。
- 真实行情接入、真实 prediction 生成、真实策略回测是外部门禁，不能用本地 smoke test 代替。

## 验证

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

## 授权

本仓库使用 MIT License，详见 [LICENSE](LICENSE)。
