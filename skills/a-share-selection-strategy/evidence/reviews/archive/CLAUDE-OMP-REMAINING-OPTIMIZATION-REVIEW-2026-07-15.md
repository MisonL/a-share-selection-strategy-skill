# Claude and OMP Remaining Optimization Review 2026-07-15

本报告记录对 `main@d07ba1c` 的只读 Skill 体系复核。审查聚焦渐进披露、脚本入口面、复杂度豁免、远端 CI、最近三个提交和真实外部门禁，不把文件数量或外部门禁未运行直接解释为代码缺陷。

## Reviewer 环境

### Claude

- Binary: `/Users/mison/.nvm/versions/node/v24.14.0/bin/claude`。
- Version: `2.1.207 (Claude Code)`。
- Mode: Opus、max effort、safe mode、non-interactive、no session persistence，只提供 Read、Grep 和 Glob。
- Exit code: `0`。
- Result: 没有 P0/P1 或 correctness bug；提出文档语义重叠、CI quick_validate gap 和 wrapper blocker 措辞三个线索。

### OMP

- Binary: `/usr/local/bin/omp`。
- Version: `omp/16.5.0`。
- Model: `newapi-chat-completions/grok-4.5`，500000 context、128000 max tokens、reasoning enabled、high thinking。
- 首轮 exit code: `0`，但工具列表缺少 bash，最终停在新的 `turn_start`，没有形成最终审查正文，因此不作为有效 reviewer 结论。
- 只读重试 exit code: `0`，提供 read、bash、grep、glob 和 lsp，并明确禁止修改仓库。
- Result: 没有 P0-P2；CI 缺少 Skill packaging 校验属于 P3 条件增强，其余为非缺陷或条件式演进。

## Findings

### P3: 远端 CI 跳过外部 Skill frontmatter 校验

- `.github/workflows/ci.yml:38` 在 core shard 执行 `python3 validate_skill_changes.py --skip-skill-validate --skip-tests`。
- `validate_skill_changes.py` 的外部 quick validator 默认来自本机 `~/.codex/skills/.system/skill-creator/scripts/quick_validate.py`，GitHub runner 没有该路径，因此 CI 必须显式跳过。
- 当前本机 quick validator 共 101 行，主要检查 `SKILL.md` frontmatter 是否存在并可解析、允许字段、必需的 `name/description`、名称格式和长度、description 类型和长度。
- 仓库测试会读取 `SKILL.md`、检查路由、链接和入口，但没有完整锁定上述 frontmatter schema。因此远端仍存在一个 packaging 校验缺口；它不影响选股运行时 correctness，也不是 P2。

最小修复方向是把稳定 frontmatter 合同实现为仓库自有 validator 检查并接入现有 core health checks，保留本机 quick_validate 作为附加兼容检查。不要直接复制本机脚本或在 CI checkout 外部 skill-creator；前者会产生来源和漂移问题，后者增加网络依赖。该工作已登记为 `OPT-014`。

## 交叉验证

### 文档读取成本

- `SKILL.md:12-24` 要求先完成任务路由，再按场景读取一个 reference。
- `SKILL.md:71-80` 和 `references/index.md:39-49` 继续限制首轮读取，历史 evidence 明确不在启动路径。
- `runbook.md`、`full-a-strict-workflow.md` 和 `script-reference.md` 确有 provider、增量和依赖语义重叠，但逐行精确比较只发现少量相同长行；它们服务于复制命令、全 A 工作流和字段参考三个受众。
- runbook 首段已经要求全 A 和真实广度任务先读 full-A workflow。当前没有证据支持把语义重叠升级为 P2，也不应把三份文档合并成一个更大的文件。

### 脚本入口和复杂度

- 当前共有 118 个 Python 文件，根层 33 个、内部 85 个；注册表含 29 个 public CLI 和 4 个 compatibility wrapper，默认主入口仍只有 3 个。
- 5 个超长文件和 6 个超长函数均与机器豁免清单精确匹配，并带 `reassess_when` 条件。
- `a_share_selection_html_sections.py` 虽有 2121 行，但 111 个函数中最长为 67 行；当前主要是同一展示和本地化合同，不适合按总行数机械拆分。
- Claude 认为 compatibility wrapper 的 blocker 措辞可能陈旧，但 `tests/test_a_share_selection_config.py`、`tests/test_cli_help_contract_classification.py` 等仍直接导入根层 wrapper。该线索不成立，不能删除 wrapper 或弱化 blocker。

### 最近提交和外部门禁

- `23b4954`、`9cd6d1f` 和 `d07ba1c` 没有引入新的 correctness、文档合同或 timeout 行为问题。
- 九个 CI job 最近均为 success，单 job 约 16 至 38 秒，没有性能优化必要。
- 真实数据源长期稳定和授权、真实 prediction 无泄漏、样本外回测、券商订单和真实成交仍是外部门禁，不是代码 bug，也不应放进 GitHub CI 的稳定回归路径。

## 明确不建议

- 不合并 29 个 public CLI 为大命令，也不因 118 个 Python 文件继续压缩内部模块。
- 不把 runbook、full-A workflow 和 script reference 合成一个 1400 行以上的文档。
- 不按文件行数机械拆分当前复杂度豁免；只在 `reassess_when` 条件和对应回归覆盖同时满足时处理。
- 不删除 4 个 compatibility wrapper，除非完成外部消费者审计和 major compatibility 迁移。
- 不把真实联网、预测、回测或券商门禁放进普通 CI。

## 结论

当前体系没有必须修复的 P0、P1 或 P2 问题。保留一个 P3 级远端 Skill frontmatter 校验增强项；其余 reviewer 线索经代码、测试和文档路由交叉验证后均不构成当前缺陷。
