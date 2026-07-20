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
    configs/
    evals/
    instructions/
    references/
    templates/
    evidence/
    requirements*.txt
    scripts/
```

仓库根目录只保留项目说明、约束、CI 和测试。脚本稳定入口都在 `skills/a-share-selection-strategy/scripts/`。

## 从哪里开始

| 目标 | 入口 |
| --- | --- |
| AI Agent 接手任务 | [skills/a-share-selection-strategy/SKILL.md](skills/a-share-selection-strategy/SKILL.md) |
| 仓库执行约束 | [AGENTS.md](AGENTS.md) |
| 完整命令 cookbook | [skills/a-share-selection-strategy/instructions/runbook.md](skills/a-share-selection-strategy/instructions/runbook.md) |
| 文档索引和历史报告 | [skills/a-share-selection-strategy/references/index.md](skills/a-share-selection-strategy/references/index.md) |
| 因子、字段、输出口径 | [skills/a-share-selection-strategy/references/factor-framework.md](skills/a-share-selection-strategy/references/factor-framework.md) |
| 预测列消费边界 | [skills/a-share-selection-strategy/references/prediction-derived-profile.md](skills/a-share-selection-strategy/references/prediction-derived-profile.md) |
| 汇报模板 | [skills/a-share-selection-strategy/templates/output-templates.md](skills/a-share-selection-strategy/templates/output-templates.md) |

## 核心入口

| 能力 | CLI |
| --- | --- |
| 行情契约校验 | `skills/a-share-selection-strategy/scripts/validate_ohlcv.py` |
| 候选评分 | `skills/a-share-selection-strategy/scripts/score_candidates.py` |
| 今日 A 股总控 | `skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py` |
| 本地 demo 数据 | `skills/a-share-selection-strategy/scripts/create_demo_data.py` |
| 低价超短剖面 | `skills/a-share-selection-strategy/configs/ultra_short_low_price_config.json` |
| 预测列消费剖面 | `skills/a-share-selection-strategy/configs/prediction_profile_config.json` |

脚本以 CLI 为稳定入口。配置文件的权威路径在 `skills/a-share-selection-strategy/configs/`；CLI 仍兼容旧命令里传入的 `skills/a-share-selection-strategy/scripts/*.json`，会自动回退到 `configs/`。Python 复用时需自行将 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。

`skills/a-share-selection-strategy/configs/script_entrypoints.json` 是脚本入口机器注册表，只用于本地一致性校验和审计；其中 `default_entry=true` 仅标记常规任务拓扑的三个主入口，其他 public CLI 仍按路径命中使用。用户仍按上表和 `skills/a-share-selection-strategy/scripts/SCRIPTS.md` 调用 CLI。

仅说“帮我选今天 A 股”但未提供行情文件或明确联网授权时，不运行 CLI、不输出候选股，先使用“无法直接选股”模板。

## 快速 demo

以下命令使用合成 demo 数据，只验证本地链路，不证明真实行情、真实预测、真实回测或收益。

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-demo

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.csv

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices.csv \
  --config skills/a-share-selection-strategy/configs/example_config.json \
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
  --spot-input /tmp/a-share-selection-low-price-demo/spot.csv \
  --output-dir /tmp/a-share-selection-low-price-demo/today \
  --mode auto
```

`create_demo_data.py` 会同时写出 `spot.csv` 和 `metadata.json`。显式传入
`--spot-input` 后，候选和诊断输出会展示 `spot_industry`；该字段只用于展示，
不参与核心评分。

总控 CLI 默认同时写出 `report.html`，用于浏览器查看候选、诊断、步骤和证据路径；报告支持中英文切换，默认 `--html-report-language auto` 跟随运行环境。它只是 `summary.json`、`run_manifest.json`、`candidates.csv` 和 `diagnostics.csv` 的展示层，不替代机器字段或退出码。自动化场景可传 `--no-html-report` 关闭。

更多 Parquet、联网取数、历史回测和门禁命令见 [runbook](skills/a-share-selection-strategy/instructions/runbook.md)。

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
- `summary.json` 中有输出路径或旧文件存在不代表本次文件已生成；以 `prices_output_written`、`candidates_output_written`、`diagnostics_output_written`、`summary_output_written`、`manifest_output_written` 为准。
- `source_provenance` 汇总 `input_metadata` 和输入 CSV 内嵌来源字段，便于机器消费；旧字段仍保留，冲突时以本次 `summary.json`、`run_manifest.json` 和 CSV 机器字段为准。
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

本仓库验证命令的权威入口是:

```bash
python3 validate_skill_changes.py
```

常规验证子进程默认最多运行 900 秒；需要调整时显式传入 `--command-timeout-seconds N`。Python 模块可用性探针使用 `min(N, 10)` 秒，避免轻量导入检查长时间阻塞；自定义小于 10 秒的值仍会收紧探针。任何超时都会使门禁失败并输出对应命令和秒数；在 POSIX 上会以 `SIGTERM` 后 `SIGKILL` 清理验证器创建的新会话进程组，即使主进程先退出也不会静默跳过或遗留同组后台测试。

默认 `--dependency-profile latest` 使用当前可解析的最新兼容 `pandas/numpy/pyarrow` 运行完整测试，用于发现上游兼容性漂移。需要在本机精确复现 GitHub CI 的 Python 3.11 直接依赖组合时运行：

```bash
python3 validate_skill_changes.py --dependency-profile ci
```

`ci` profile 直接从 `constraints-ci.txt` 创建完整 unittest 子进程，不依赖调用者当前 Python 环境中的同名包。

统一入口始终执行仓库自有的 `SKILL.md` frontmatter 合同，校验 YAML mapping、允许字段、必需字段、名称格式和 description 边界。`--skip-skill-validate` 只跳过本机 `quick_validate.py` 附加兼容检查，不会跳过该仓库门禁；因此 GitHub CI 不依赖本机 skill-creator 脚本也能拒绝非法 frontmatter。

该入口只覆盖本地仓库门禁，不证明真实行情、真实 prediction、券商订单或真实回测门禁通过。需要拆开执行或替换本机 `quick_validate.py` 时，使用 [runbook 验证命令](skills/a-share-selection-strategy/instructions/runbook.md#验证命令)。

CI 使用 `tests/run_unittest_shard.py` 按职责分配普通测试文件，并对 `test_today_a_share_selection_runner.py` 做方法级互斥分片；本地统一门禁仍以完整 `python -m unittest discover -s tests -v` 为准。分片脚本会校验覆盖全集、无重复，并在测试文件或 runner 方法变化时拒绝静默漏测。

迭代单个职责分片时可运行以下命令缩短本地反馈；它只用于开发反馈，交付前仍必须运行完整 `python3 validate_skill_changes.py --dependency-profile ci`：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --python 3.11 \
  --with-requirements skills/a-share-selection-strategy/constraints-ci.txt \
  python tests/run_unittest_shard.py gates
```

GitHub Actions 每个分片 job 的总超时为 15 分钟，用于阻止依赖安装或测试异常无限等待；该上限不是性能 SLA。

CI 直接依赖约束保存在 `skills/a-share-selection-strategy/constraints-ci.txt`，用于复现当前 Python 3.11 测试组合。`requirements*.txt` 仍表达使用者最低版本范围，不因 CI pin 而缩窄公开安装边界。

## 授权

本仓库使用 MIT License，详见 [LICENSE](LICENSE)。
