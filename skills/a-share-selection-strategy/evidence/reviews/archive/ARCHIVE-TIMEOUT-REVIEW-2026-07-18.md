# Archive and Timeout Review 2026-07-18

本报告记录对 `d41fb64..6d881e1` 外部源探针紧凑归档和统一验证器超时清理变更的只读审查。它只覆盖代码和本地合同，不证明真实行情、外部数据源长期稳定性、prediction、回测或券商门禁。

## 审查范围

- `scripts/lib/gates/external_source_evidence_archive.py` 的原子归档、路径和符号链接检查、清单与完整性验证。
- `probe_external_source_stability.py` 的归档调用、失败语义和持久化脱敏。
- `scripts/lib/selection_core/a_share_selection_command_safety.py` 的命令、文本、URL 和 mapping 脱敏。
- `validate_skill_changes.py` 的 900 秒默认超时和 POSIX 进程组回收。
- 对应 probe、validator、文档合同和 CLI help 测试。

## Reviewer 结果

### Claude CLI

- 使用本机 NVM 下的 Claude CLI，以 safe mode 和 plan permission 进行只读审查。
- 基线审查未报告可行动 P1/P2；Codex 独立复现 camelCase 缺口后，该旧结论不覆盖 `OPT-029`。
- 在 camelCase 修复后的较早精确 diff 上再次审查，退出码为 0，输出 `NO_ACTIONABLE_P1_P2`。该结论早于 OMP 后续指出的 compact flag 缺口，不能作为 `OPT-029` 的最终审查结论。
- 随后以完整 patch 嵌入提示词的 safe-mode 只读审查输出 `NO_ACTIONABLE_P1_P2`；它提出的 Cookie closing delimiter 空格现象无法用最小复现重现，`max_cookie_size`/`cookie_timeout` 等包含 `cookie` 的日志字段会 fail-closed 脱敏是当前安全优先合同，不构成 P1/P2。该次审查早于 compound command flag 补强，最终精确 diff 仍须复审。
- 收尾精确 diff 仍通过 safe-mode、plan permission、禁用工具和无预算/时间上限的完整 patch 审查，输出 `NO_ACTIONABLE_P1_P2`。残余项仍是 `session_timeout`/`cookie_timeout` 等保守脱敏和非标准 Cookie 日志分段的未来边界，不改变当前归档、路由或真实门禁结论。

### OMP CLI

- 使用 `/usr/local/bin/omp` `v17.0.2` 与 `newapi-chat-completions/grok-4.5`。
- 首次带工具会话没有形成可裁定文本，且停滞的进程组已终止，不能视为审查结论。
- 基线无工具审查只传入 `d41fb64..6d881e1` 精确 diff，退出码为 0，结论为“无可行动 P1/P2”；该结论同样不覆盖之后独立发现的 `OPT-029`。
- 修复后的当前精确未提交 diff 以无工具、无扩展、无 skills、无 rules 的 `newapi-chat-completions/grok-4.5` 再审查，退出码为 0，先发现两个 P2：本报告对 URL query 与 metadata mapping 键名保留规则的表述混淆，以及 RFC 折行 `Cookie`/`Set-Cookie` 续行可能泄漏。两项均由 Codex 最小复现确认并修复。其后对修复版再次审查又发现两个同边界 P2：`set_cookie`/`cookies` 等 snake_case 或复数无引号日志只脱敏首段，以及 runbook 未公开 query 与 metadata 的实际键名策略；两项同样进入本轮修复。随后 OMP 又发现一个 P1：`--clientsecret`、`--privatekey`、`--sessionid`、`--refreshtoken`、`--bearertoken`、`--setcookie` 等无分隔标准敏感 flag 会保留后续独立值。Codex 复现后在 `classify_sensitive_flag()` 增加 compact 标准名分支，补充 helper 与 `source_record -> archive` 端到端测试，并重跑 CI。
- 在下一次无工具最终复审中，OMP 输出 `NO_ACTIONABLE_P1_P2`，但提示 `--secret-key`、`--auth-token`、`--session-token` 及其 compact 写法的独立值仍可能泄漏。Codex 独立复现后只向显式 command flag 集合补入 `secret_key`、`auth_token`、`session_token`，并同时覆盖紧凑、kebab-case、等号、分离值、嵌入凭据的 flag 名以及 `source_record -> archive` 持久化路径；`--session-timeout` 保持非敏感。该次模型输出不作为最终结论，最终精确 diff 仍须复审。推理流中超出 diff 的泛化状态断言未采信。
- 最终精确 diff 复审中，OMP 报告 `AWSSecretAccessKey` 会归一化为 `aw_secret_access_key` 的 P2。Codex 直接执行 `normalize_query_key("AWSSecretAccessKey")` 得到 `aws_secret_access_key`，对应单元测试也通过；模型对正则位置的推导错误，因此该 finding 不采纳。收尾精确 diff 的 OMP 复审随后输出 `NO_ACTIONABLE_P1_P2`，仅保留 fail-closed 非敏感字段、非标准 Cookie 分段和真实外部门禁未证明这三类边界。除该已证伪 finding 外，没有新的可复现 P1/P2。

## Codex 交叉验证

外部 reviewer 结论只作为线索。以下复核直接针对当前代码和最小复现：

1. 归档目标、输出目录和 summary 的重叠检查在归档前执行；归档写入使用同文件系统临时目录和 rename，归档内容不读取 `output` 价格路径。
2. 完整性验证同时检查 payload hash、字节数、source record 映射、额外文件、unsafe relative path 和符号链接。
3. 验证器在 POSIX 上用新会话启动，超时后即使 leader 已退出也会对进程组发送 SIGKILL；对应真实后代进程测试已存在。
4. 发现并复现一个 P1 安全问题：`normalize_query_key` 不会把 `clientSecret`、`privateKey`、`bearerToken`、`refreshToken` 或 `sessionId` 拆成敏感 key 组件。因此 `sanitize_persisted_mapping` 会把这些字段的原始值写入 summary 和 archive metadata。该问题不能由外部 reviewer 的无 finding 结论覆盖，已作为 `OPT-029` 单独锁定修复。
5. 修复复核继续发现并收口两个同一持久化边界：分号、逗号或 RFC 折行续段的 `Cookie`/`Set-Cookie` 日志不能只脱敏第一个值，且等价的 `set_cookie`、`Set_Cookie`、`cookies` 和包含 `cookie` 的无引号 key 也必须整段脱敏；敏感字段名与实际值无分隔拼接在 query 或 metadata 键中时，键名也不能保留。URL query 对标准语义键（含 `ToKeN`、`accessKeyId`、`X-Amz-Credential`）保留键名并隐藏值；metadata mapping 仅在字段名归一化后精确落入常见敏感字段集合时保留字段名，其余敏感或嵌入式键名统一写为 `[REDACTED] key`。`tokenConfigured` 仅在真实 bool 时保留能力状态。
6. 当前最小充分验证覆盖 snake/kebab/camel/Pascal/缩写敏感字段、递归 metadata、URL、Cookie 续段、`tokenConfigured` 类型例外、compact/compound command flag 和 `source_record -> archive`；定向测试、`git diff --check` 与 `compileall` 均通过。
7. 对 compact flag P1 的最小复现显示修复前 `sanitize_command(["tool", "--clientsecret", "secret"])` 会保留 `secret`，修复后标准 compact flag 保留名称但分离值和 `--flag=value` 值均为 `[REDACTED]`；同样的最小复现发现并收口 `--secret-key`、`--auth-token`、`--session-token`。当前端到端归档用例覆盖这些路径。收尾 CI 约束门禁通过 `911` 项测试，耗时 `242.088s`，验证器 12 个本地门禁全部通过。

## 结论和边界

当前精确 diff 已完成 Claude、OMP 无工具复审，且没有已采纳的 P1/P2；`OPT-029` 已标记完成，diff 与缓存卫生检查也通过。无论本地测试结果如何，外部数据源长期稳定性、授权和额度仍保持 `not_proven`。
