# Claude and OMP System Review 2026-07-15

本报告记录对 `09efee4..2a7c321` 提交范围和当前 Skill 体系的只读复核。报告只反映 2026-07-15 的代码、文档、测试和 reviewer 输出，不替代真实行情、prediction、回测、券商或外部数据源长期稳定性门禁。

## 审查范围

- 审查范围包含 8 个提交、41 个文件和当前 Skill 的入口、脚本注册表、文档路由、验证入口、CI workflow、测试及 evidence。
- 审查启动时 `main`、`origin/main` 和 `origin/HEAD` 均指向 `2a7c321`，工作树只有用于锁定本次审查的 `tasks.csv` 行。
- 两套外部 CLI 只获得读取和只读 shell 能力，不允许编辑、提交或推送仓库文件。

## Reviewer 环境

### Claude

- Binary: `/Users/mison/.nvm/versions/node/v24.14.0/bin/claude`。
- Version: `2.1.207 (Claude Code)`。
- Model and mode: Opus、max effort、safe mode、non-interactive、no session persistence。
- 首轮审查 exit code: `0`。首轮报告没有发现 P0/P1，提出 2 个 P2 和 4 个 P3 线索。
- 定向纠偏审查 exit code: `0`。定向审查认为 no-trading 文档属于通用规则和例外规则的互补关系，并把 Parquet 示例和 timeout 说明降为 P3。
- safe mode 的 plan permission 首轮在仓库外写入了 Claude 自身 plan 文件；`git status --short` 确认仓库内没有因此产生额外改动。

### OMP

- Binary: `/usr/local/bin/omp`。
- Version: `omp/16.5.0`。
- Model: `newapi-chat-completions/grok-4.5`，high thinking。
- Mode: non-interactive、no session、no extensions、no skills、no rules，只提供 read、bash、grep、glob 和 lsp。
- Exit code: `0`。
- Result: 报告 1 个 P1 文档合同问题，没有 P0；其余内容列为条件式优化或未验证外部门禁。

## Finding

### P2: 增量 no-trading 例外没有写入 merge 的绝对拒绝句

相关文档同时给出了正确例外和未限定的绝对规则：

- `instructions/full-a-strict-workflow.md` 的 no-trading 章节说明，只有显式启用三项 Baostock policy 且通过 raw 目标日审计时，`no_trading_update_symbols` 可以保留 base；同文件后续检查表却要求 delta metadata 不含任何 `empty`、每个计划 symbol 都出现在 delta prices 且达到 `target_end_date`。
- `references/script-reference.md` 的 clean pool 说明写 merge 拒绝 delta 中所有 `empty`、缺失计划 symbol 和未达到 target 的情况；同文件后续执行器说明又定义了审计 no-trading empty 例外。

代码真实合同没有问题：

- `scripts/lib/gates/incremental_history_merge.py` 先严格验证 `empty_symbols == no_trading_update_symbols == non_trading_only_empty_symbols`、固定 semantics、`provider=baostock`、raw rows 和 raw target date。
- 只有通过上述审计的 symbol 才会从普通 empty 拒绝集合中移除，并作为 `allowed_missing` 和 `allowed_stale` 进入 coverage 检查；merge 保留 base 数据。
- `scripts/lib/gates/incremental_history_artifacts.py` 固定 `partial_result_semantics=false_means_no_unaudited_gaps_audited_no_trading_updates_disclosed_separately`。
- `tests/test_incremental_history_execution_safety.py::test_verified_merge_retains_base_for_audited_no_trading_update` 锁定了合法例外；普通 empty、failed、错误 policy、错误 provider 或错误 raw 日期仍然失败关闭。

Claude 将前述文档解释为通用规则和例外规则的互补关系，OMP 将未限定绝对句判定为双重事实。Codex 交叉验证后保留 finding，但降为 P2：实现与回归测试是安全的，不会错误合并数据；问题在于 Skill 文档是 Agent 的执行接口，绝对句没有写出例外，可能让 Agent 或操作者把合法 merge 误判为违规。修复应只收口两处文档措辞并增加精确一致性断言，不改变代码语义。

## 未采纳线索

- `CLI_HELP_ENTRIES` 漂移：不成立。`test_all_scripts_are_classified_as_cli_or_helper` 对 `scripts/*.py` 做全集等式检查，注册表和公开入口另有精确覆盖测试；新增根层脚本不会被静默跳过。
- `--command-timeout-seconds` 与 10 秒模块探针上限冲突：不成立。用户值仍是所有 validator 子进程的最大上限，模块可用性探针使用更小的 10 秒上限不违反 maximum 语义。
- `metadata_symbols()` 转换非字符串：当前调用链随后执行计划、provider、symbol 集合和 raw metadata 严格对账，异常值会失败关闭，没有证据表明它可绕过门禁。
- `.previous` 备份：进程内异常回滚已有测试；硬中断或断电的跨进程恢复没有被本轮实测证明，但也没有证据表明本提交引入了可复现的数据错误，本次不列缺陷。
- `prepare_clean_history_pool.py` 缺少完整 Parquet 输出示例：功能、注册表和后续 Parquet 输入路径均已记录，属于可选 P3 易用性优化，不影响当前合同正确性。
- 文件数量本身、外部门禁没有在本轮重跑、泛化重构建议均不构成当前变更缺陷。

## 验证结果

使用仓库依赖环境运行以下定向回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow \
  python -m unittest -v \
  tests.test_incremental_history_execution_safety \
  tests.test_cli_help_contract_classification \
  tests.test_document_consistency
```

- Exit code: `0`。
- Result: 59 tests passed，耗时 13.737 秒。
- 覆盖内容包括 no-trading empty 正反例、verified merge 保留 base、聚合发布回滚、CLI 根层全集分类、注册表入口、文档链接和现有增量文档合同。
- 现有文档一致性测试只锁定 semantics 字符串和三项 policy，没有锁定 merge 绝对句中的 no-trading 例外，因此当前 P2 不会被 CI 发现。

基线提交 `2a7c321` 对应的 GitHub Actions run `29409416438` 已有九个 job 全部成功的历史证据。本报告没有重跑真实联网全 A、真实 LightGBM、样本外回测、券商订单或真实成交门禁，也不把这些外部门禁标记为通过。

## 结论

本轮没有发现 P0、P1 或代码 correctness 缺陷。保留 1 个 P2 文档合同问题，并在 `tasks.csv` 中登记独立修复任务。Claude 首轮提出的其他线索经代码、测试和定向复核后均不构成必须修改的问题。
