# AGENTS.md

## 任务跟踪

- 根目录 `tasks.csv` 是本仓库唯一任务驱动源；临时计划和审查报告不得替代其状态。
- 状态仅使用 `未开始`、`进行中`、`已完成`。每次只允许一个任务处于 `进行中`。
- 修改任务前先锁定对应行，完成验收和审查要求后再标记 `已完成`。

## 沟通和边界

- 全程使用中文沟通。
- 不得伪造行情、候选股、LightGBM prediction、回测收益或联网结果。
- 本仓库脚本以 CLI 为稳定入口；Python API 复用时需自行将 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。
- 真实行情接入、真实 LightGBM prediction 生成、真实策略回测是外部门禁，不能用本地 smoke test 代替；当前状态统一从 `skills/a-share-selection-strategy/evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md` 进入，再回到其引用的 dated evidence。
- 当前仓库声明 MIT License，详见 `LICENSE`；不要替用户添加或推断额外授权条款。

## 文档入口

| 场景 | 入口 |
| --- | --- |
| 文档地图和历史报告索引 | `skills/a-share-selection-strategy/references/index.md` |
| Agent 调用规则和任务路由 | `skills/a-share-selection-strategy/SKILL.md` |
| 输出汇报模板 | `skills/a-share-selection-strategy/templates/output-templates.md` |
| 当前真实门禁状态 | `skills/a-share-selection-strategy/evidence/reviews/CURRENT-REAL-SCENARIO-GATES.md` |
| 历史真实门禁证据 | `skills/a-share-selection-strategy/evidence/reviews/REAL-SCENARIO-GATES-2026-05-30.md` |

## 输入数据要求

- `symbol` 必须按文本保存，避免前导零丢失。
- `date` 支持 `YYYY-MM-DD` 或 `YYYYMMDD`。
- `volume` 单位必须在同一文件内一致；脚本无法从纯数值可靠识别股、手、张或成交额混用。
- prediction-derived 输入必须包含 `market=A-share`、`prediction` 或 `prediction_score`，以及 `turn` 或 `turnover`。
- `weight/notional/quantity/cash_reserved` 必须来自可追溯资金分配、组合或订单模型；测试用等权或固定金额字段只能验证门禁行为，不能替代真实现金容量证明。
- `allocate_candidate_capital.py` 生成的字段属于本仓库内可追溯 sizing 产物，必须保留 `cash_budget/lot_size/capital_model`，不得解释为真实成交或券商订单证明。

## 验证命令

推荐先使用统一本地验证入口:

```bash
python3 validate_skill_changes.py
```

常规验证子进程默认超时 900 秒，可用 `--command-timeout-seconds N` 显式覆盖；Python 模块可用性探针使用 `min(N, 10)` 秒，自定义更小值仍生效。任何超时都必须使门禁失败，并以 `SIGTERM` 后 `SIGKILL` 清理验证器创建的新会话进程组；即使主进程先退出也不得留下同组后台测试子进程。GitHub Actions 每个分片 job 的总超时为 15 分钟，该上限不是性能 SLA。

默认 `--dependency-profile latest` 用于最新兼容依赖探测；提交前需要精确复现 GitHub CI 的 Python 3.11 直接依赖组合时运行 `python3 validate_skill_changes.py --dependency-profile ci`。`ci` profile 必须读取 `constraints-ci.txt`，不得把外层虚拟环境中的依赖当作精确 CI 证据。

统一入口始终执行仓库自有的 `SKILL.md` frontmatter 合同，覆盖 YAML mapping、允许字段、必需 `name/description`、名称格式和 description 边界。`--skip-skill-validate` 只跳过本机 `quick_validate.py` 附加兼容检查，不得解释为跳过仓库 frontmatter 门禁。

该入口只覆盖本地仓库门禁，不证明真实行情、真实 prediction、券商订单或真实回测门禁通过。若需要拆开执行，对应命令如下:

以下拆分命令是 `validate_skill_changes.py` 的人工展开视图；新增或调整本地门禁时，先更新仓库根验证脚本，再同步本节和 runbook。

```bash
for file in skills/a-share-selection-strategy/evals/*.json skills/a-share-selection-strategy/configs/*.json; do
  python3 -m json.tool "$file" >/tmp/"$(basename "$file")"
done
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import yaml
from validate_skill_changes import (
    extract_skill_frontmatter,
    validate_skill_frontmatter_data,
)
path = Path("skills/a-share-selection-strategy/SKILL.md")
frontmatter = extract_skill_frontmatter(
    path.read_text(encoding="utf-8"),
    source=str(path),
)
validate_skill_frontmatter_data(yaml.safe_load(frontmatter), source=str(path))
PY
uv run --with pyyaml python - <<'PY'
import yaml
from pathlib import Path
manifests = sorted(Path("skills/a-share-selection-strategy/agents").glob("*.yaml"))
if not manifests:
    raise RuntimeError("no YAML agent manifest files found")
for manifest in manifests:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{manifest}: expected mapping root")
    interface = data.get("interface")
    if not isinstance(interface, dict):
        raise RuntimeError(f"{manifest}: missing interface mapping")
    for key in ["display_name", "short_description", "default_prompt"]:
        value = interface.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"{manifest}: missing interface.{key}")
PY
PYTHONPYCACHEPREFIX=/tmp/a-share-selection-pycache python3 -m compileall -q skills/a-share-selection-strategy/scripts
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python -m unittest discover -s tests -v
```

CI 会用 `tests/run_unittest_shard.py` 按职责分配普通测试文件，并将 `test_today_a_share_selection_runner.py` 按方法互斥分片；该脚本会校验全集覆盖和无重复。本地交付前仍需运行上面的完整 unittest，不能只依赖单个分片。

CI 直接依赖约束位于 `skills/a-share-selection-strategy/constraints-ci.txt`，仅用于固定仓库测试的已验证组合；面向使用者的 `requirements*.txt` 继续保留最低版本范围，两者不能混作发布兼容性声明。

如需校验 Skill 结构，将 `QUICK_VALIDATE` 替换成本机 skill-creator 的 `quick_validate.py` 路径：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" skills/a-share-selection-strategy
```
