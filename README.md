# A-Share Selection Strategy

面向 AI Agent 的 A 股选股策略 Skill。流程覆盖数据契约校验、因子计算、硬过滤、排序、诊断和汇报。

默认处理已落地的 CSV 或 Parquet 输入。联网取数只能通过显式 CLI 写入本地数据和 metadata 后，再进入同一套校验、评分与汇报流程。

## 从哪里开始

| 目标 | 入口 |
| --- | --- |
| Agent 路由和调用规则 | [SKILL.md](skills/a-share-selection-strategy/SKILL.md) |
| 常规命令与输入要求 | [runbook](skills/a-share-selection-strategy/instructions/runbook.md) |
| 全 A 严格工作流 | [full-a-strict-workflow.md](skills/a-share-selection-strategy/instructions/full-a-strict-workflow.md) |
| 文档和历史证据索引 | [references/index.md](skills/a-share-selection-strategy/references/index.md) |
| 当前真实门禁状态 | [CURRENT-REAL-SCENARIO-GATES.md](skills/a-share-selection-strategy/evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md) |
| 汇报格式 | [output-templates.md](skills/a-share-selection-strategy/templates/output-templates.md) |

Skill 将流程说明放在 `instructions/`，输出格式放在 `templates/`，可追溯证据放在 `evidence/`；不要把 README 当成完整运行手册。

## 常用入口

| 能力 | CLI |
| --- | --- |
| 行情契约校验 | `skills/a-share-selection-strategy/scripts/validate_ohlcv.py` |
| 候选评分 | `skills/a-share-selection-strategy/scripts/score_candidates.py` |
| 今日 A 股总控 | `skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py` |

CLI 是稳定入口；完整入口清单、配置和专项 fetch 或门禁命令见 [SCRIPTS.md](skills/a-share-selection-strategy/scripts/SCRIPTS.md) 与 runbook。未提供行情文件或明确联网授权时，不运行选股 CLI，也不输出候选股。

## 最小 demo

以下命令只验证本地合成链路，不证明真实行情、真实 prediction、真实回测或收益。

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py \
  --output /tmp/a-share-selection-demo

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.csv

uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /tmp/a-share-selection-demo/prices.csv \
  --spot-input /tmp/a-share-selection-demo/spot.csv \
  --output-dir /tmp/a-share-selection-demo/today \
  --mode auto
```

`--spot-input` 使输出展示 `spot_industry`，但该字段不参与核心评分。以 `source_provenance`、退出码和机器产物为准；`summary_output_written` 与 `manifest_output_written` 仅说明对应文件本次是否写出。

## 事实边界

- `input_metadata` 缺失或未声明 `real_market_data=true` 时，只能称为本地输入，不能声称真实行情、今日全市场覆盖或数据源已验证。
- `report.html` 是 JSON 和 CSV 产物的展示层，不能替代机器字段、退出码或门禁结论。
- 候选、sizing、回测或资金曲线必须写明：非投资建议、非交易指令、非真实成交、非收益证明。
- 真实行情接入、真实 prediction 生成和真实策略回测均是外部门禁；本地 smoke test 不可替代。

## 验证

统一的本地仓库门禁入口：

```bash
python3 validate_skill_changes.py
python3 validate_skill_changes.py --dependency-profile ci
```

第二条命令使用 CI 直接依赖约束复现 GitHub CI 的 Python 3.11 组合。统一入口始终执行仓库自有的 `SKILL.md` frontmatter 合同；`--skip-skill-validate` 只跳过本机 `quick_validate.py` 附加兼容检查。

迭代单个分片时：

```bash
uv run --python 3.11 \
  --with-requirements skills/a-share-selection-strategy/constraints-ci.txt \
  python tests/run_unittest_shard.py gates
```

它只用于开发反馈；交付前仍须运行完整 CI profile 门禁。超时、分片拓扑和替代验证命令见 [runbook 验证命令](skills/a-share-selection-strategy/instructions/runbook.md#验证命令)。

## 授权

本仓库使用 MIT License，详见 [LICENSE](LICENSE)。
