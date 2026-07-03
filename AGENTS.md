# AGENTS.md

## 沟通和边界

- 全程使用中文沟通。
- 不得伪造行情、候选股、LightGBM prediction、回测收益或联网结果。
- 本仓库脚本以 CLI 为稳定入口；Python API 复用时需自行将 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。
- 真实行情接入、真实 LightGBM prediction 生成、真实策略回测是外部门禁，不能用本地 smoke test 代替；当前真实门禁优先级以 `skills/a-share-selection-strategy/evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md` 为准。
- 当前仓库声明 MIT License，详见 `LICENSE`；不要替用户添加或推断额外授权条款。

## 文档入口

| 场景 | 入口 |
| --- | --- |
| 文档地图和历史报告索引 | `skills/a-share-selection-strategy/references/index.md` |
| Agent 调用规则和任务路由 | `skills/a-share-selection-strategy/SKILL.md` |
| 输出汇报模板 | `skills/a-share-selection-strategy/templates/output-templates.md` |
| 历史真实门禁 | `skills/a-share-selection-strategy/evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md` |

## 输入数据要求

- `symbol` 必须按文本保存，避免前导零丢失。
- `date` 支持 `YYYY-MM-DD` 或 `YYYYMMDD`。
- `volume` 单位必须在同一文件内一致；脚本无法从纯数值可靠识别股、手、张或成交额混用。
- prediction-derived 输入必须包含 `market=A-share`、`prediction` 或 `prediction_score`，以及 `turn` 或 `turnover`。
- `weight/notional/quantity/cash_reserved` 必须来自可追溯资金分配、组合或订单模型；测试用等权或固定金额字段只能验证门禁行为，不能替代真实现金容量证明。
- `allocate_candidate_capital.py` 生成的字段属于本仓库内可追溯 sizing 产物，必须保留 `cash_budget/lot_size/capital_model`，不得解释为真实成交或券商订单证明。

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

如需校验 Skill 结构，将 `QUICK_VALIDATE` 替换成本机 skill-creator 的 `quick_validate.py` 路径：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" skills/a-share-selection-strategy
```
