# SKILL-SYSTEM-CLOSEOUT-2026-07-04

## 范围

本记录覆盖 2026-07-04 对 A 股选股 Skill 体系优化的收尾复核。目标是把本轮工程体系改动、外部 reviewer 结论和本地验证结果沉淀到仓库证据目录，避免只依赖聊天上下文。

本轮覆盖:

- Skill 入口、runbook、全 A 严格工作流、脚本索引和数据源能力边界文档。
- `run_today_a_share_selection.py` 的 `--plan-only`、`--resume-from`、retry symbol、source-specific option inheritance 和 stale cleanup 行为。
- 命令和日志脱敏 helper。
- `configs/data_sources.json` 数据源能力注册表。
- `validate_skill_changes.py` 统一本地验证入口。
- 相关单元测试、文档一致性测试和 runner 集成测试。

## 外部 review 摘要

Claude 结论:

- 未发现阻塞问题。
- 建议 close 前确认新增 untracked 文件归属。
- 建议补强 `data_sources.json` schema 断言。
- 建议抽掉 `option_configured` 重复实现。
- 脱敏边界测试和大测试文件拆分可以按风险取舍。

OMP 结论:

- 未发现明确功能性 blocking issue。
- 新增 untracked 文件若属于本轮功能闭环，必须纳入最终提交范围。
- 建议 close 前增加最终复核记录、补强脱敏边界测试、补强 `data_sources.json` schema 和文档一致性测试。
- 不建议在本轮收尾中做大规模测试重排、自动 fallback 或 runner 架构重排。

本轮采纳:

- 补强 `data_sources.json` schema 和文档一致性测试。
- 补强命令和日志脱敏边界测试。
- 补强 runner 通用异常路径的 `run_error`、`stale_cleanup_error` 和终端 `message` 脱敏。
- 抽出共享 `option_configured` helper，移除两处重复定义。
- 补强空 `--symbols-file` 显式错误和 yfinance resume timeout 继承测试。
- 将本收尾证据挂入 `references/index.md` 历史报告索引。
- 统一验证入口使用 home-relative quick_validate 默认路径，并标注 secret scan 自检片段。
- 补强 retry plan 输出路径碰撞保护，避免 recovery helper 覆盖输入文件。
- 补强 retry plan `--include-clean-selected` CLI 边界测试，锁定 clean symbols 追加和计数语义。
- 补强 symbols 文件 CRLF 归一化，避免 Windows 换行把 `\r` 混入 symbol。
- 将 CI 中的轻量验证 step 命名为 repo health checks，避免误读为重复完整测试。
- 补强 JSON 形式 `Authorization`/`Proxy-Authorization` 日志脱敏，避免 header dict 被写入 manifest、summary 或 HTML 证据。
- 补强 URL-encoded nested callback URL 脱敏，避免 `redirect_uri` 等 query value 中的 credential 漏进 artifact。
- 收紧 URL fragment 脱敏边界，仅在明确 `key=value` 形态下重写 fragment，避免破坏普通文档锚点或 SPA 路由。
- 补强 SPA/OAuth route fragment query 脱敏，避免 `#/callback?access_token=...` 这类回调泄露 credential。
- 将 `.github/` 纳入 `validate_skill_changes.py` 的 secret scan，避免 workflow 泄漏绕过 repo health check。
- 抽出重复的路径碰撞比较和 step 执行判定 helper，减少 runner、summary 和 HTML 分支漂移。
- 按末轮本地验证更新测试数量证据，避免 stale verification evidence。
- 添加本复核记录。

本轮不采纳:

- 不拆分 `tests/test_today_a_share_selection_runner.py`。这是后续维护项，不应混入当前已收敛的行为变更。
- 不新增真实行情、真实 LightGBM prediction 或真实回测的本地替代证明。真实门禁仍以专门证据文档和外部环境为准。
- 不引入自动选源、静默 fallback 或隐式降级。

最终复核:

- Claude 和 OMP 在本轮末次只读复核中均未发现新增 P1/P2。
- 剩余建议只适合后续独立任务: 拆分大测试文件、拆分 HTML 报告大模块、CI 分层提速、真实外部门禁复验和正式提交分组。
- 本轮不继续扩大 runner、parser、HTML 或真实数据链路改动面；优先保持已通过门禁的行为变更稳定。

## 本轮新增控制点

`data_sources.json` registry:

- 锁定顶层字段为 `schema_version`、`claim_boundary` 和 `sources`。
- 锁定 source key 命名规则。
- 锁定每个 source 的 metadata 字段集合。
- 校验 `entry` 指向 `scripts/` 下真实文件。
- 校验 token 环境变量出现在文档中。

命令和日志脱敏:

- 覆盖普通敏感 flag 和 key-value 模式。
- 覆盖 JSON、header 和 key-value 形式的敏感字段。
- 覆盖 Authorization header 和 assignment 形式，包含 Bearer、Basic、Token、ApiKey、Digest、AWS4-HMAC-SHA256 等单 token 或多段 scheme。
- 覆盖 JSON 和 Python dict 风格的 `Authorization`、`Proxy-Authorization` header 值。
- 覆盖 OpenAI style `sk-*` key。
- 覆盖 URL userinfo。
- 覆盖普通 query secret。
- 覆盖 percent-encoded query key、大小写混合 query key、重复 query 参数、空值敏感参数、signed URL query 以及普通 key-value 中的 signature/credential/access key 字段和多行 stdout/stderr。
- 覆盖 fragment credential 脱敏，同时保持普通锚点和非敏感 SPA route fragment 原样；SPA/OAuth route fragment query 中的 credential 仍会脱敏。
- 覆盖 runner 失败路径写入终端的 `step_stderr` 首行，避免外部脚本第一行 stderr 泄露敏感值。
- 覆盖 runner 通用失败路径写入 manifest、summary 和终端的异常文本。

Runner helper 收敛:

- `option_configured` 作为 runner helper 中的单一实现。
- `run_today_a_share_selection.py` 和 `run_today_a_share_selection_history.py` 不再各自维护重复定义。
- 未改变 CLI 参数语义或 runner 执行顺序。

History recovery and symbol input:

- 空 `--symbols-file` 会在读取阶段显式失败，错误指向具体文件。
- `--symbols-file` 支持 CRLF、CR 和 LF 换行输入，读取后统一按逗号分隔。
- yfinance resume 会继承上一轮 `history_timeout_seconds`，并由 plan-only manifest 测试锁定。
- zzshare resume 不从上一轮 manifest 自动继承 `history_http_url`；如上一轮包含该字段，manifest 记录 `resume_sensitive_options_requiring_explicit_input=["history_http_url"]`，需要本轮显式重传自定义 URL。
- `prepare_history_retry_symbols.py` 会拒绝输出路径覆盖 `selected_symbols.json` 或 `history_metadata.json`，也拒绝重复输出路径。
- `prepare_history_retry_symbols.py --include-clean-selected` 会把 clean selected symbols 追加到 retry list，并保持 retry count 和 text output 一致。
- `prepare_history_retry_symbols.py` 保持独立 CLI 自包含，JSON 写出 helper 与 runner helper 的重复是有意边界。

## 验证结果

统一验证入口:

```bash
python3 validate_skill_changes.py
```

该入口只串联本地仓库门禁，不运行真实行情、真实 prediction、券商订单或真实回测门禁。

结果:

- 退出码: 0
- `OK: local validation gates passed`
- 覆盖 JSON configs/evals、scripts compileall、Skill quick_validate、`git diff --check`、secret scan、`__pycache__` scan 和 full unittest suite。
- CI 通过 `python3 validate_skill_changes.py --skip-skill-validate --skip-tests` 复用该入口的本地快速门禁；CI 不运行本机 skill-creator quick_validate，也不代表真实外部门禁通过。

相关子集:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python -m unittest tests.test_today_a_share_runner_failure_evidence tests.test_today_a_share_selection_runner tests.test_today_a_share_html_report_modes tests.test_recovery_and_safety_helpers -v
```

结果:

- 退出码: 0
- `Ran 125 tests`
- `OK`

全量回归:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python -m unittest discover -s tests -v
```

结果:

- 退出码: 0
- `Ran 549 tests`
- `OK`

前置和卫生检查:

- JSON configs/evals: `python3 -m json.tool` 通过。
- scripts compileall: 通过。
- Skill quick_validate: 通过。
- `git diff --check`: 通过。
- secret scan: 无命中。
- `__pycache__` scan: 无残留。

## 交付边界

本轮本地验证证明:

- 本地 CLI 行为、runner resume/plan-only 语义、文档一致性、命令脱敏和 registry 契约在当前测试环境下通过。
- 新增的 `configs/data_sources.json`、`evidence/reviews/SKILL-SYSTEM-CLOSEOUT-2026-07-04.md`、`a_share_selection_command_safety.py`、`prepare_history_retry_symbols.py`、`tests/test_recovery_and_safety_helpers.py` 和 `validate_skill_changes.py` 是本轮功能闭环的一部分，最终提交时应纳入版本控制。

本轮不证明:

- 真实全 A 行情源长期稳定。
- 真实 LightGBM prediction 策略质量。
- 真实样本外收益。
- 真实券商订单、成交或资金容量。
- 真实涨跌停规则已完整建模。

这些仍属于外部门禁，不得用本地 smoke test 或本地 unittest 替代。
