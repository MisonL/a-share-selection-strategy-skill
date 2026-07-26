# Multi-Agent Real Scenario Validation 2026-07-26

本报告记录 2026-07-26 由四个隔离 Agent 按当前 `SKILL.md` 路由执行的真实任务场景复验。它只描述当前机器、当前网络、指定日期窗口、指定 provider 和指定超时预算下的行为，不构成投资建议，也不证明全 A 历史长跑、全 A 最终评分、prediction、回测、券商订单、真实成交、长期稳定性、免费额度或授权持续有效。

## 执行边界

- 四个 Agent 分别执行定向 Baostock 选股、全 A 股票池与 plan-only、Pytdx 补充源取数和七源有界探针，业务 artifact 只写入各自独占的 `/tmp` 目录。
- 所有联网命令显式选择 provider；没有 mock、演示数据、旧输出复用、自动 source fallback 或 host rotation。
- 场景执行前后工作树都只有主流程预先锁定的 `M tasks.csv`，未发现子代理新增的仓库文件、暂存项或业务改动。
- 四个 Agent 收集反馈后均已关闭；收口复核未发现本轮 runner、Baostock、Pytdx 或 probe 子进程残留。
- `/tmp` artifact 是易失性原始证据。本报告不复制价格 CSV、HTML、完整 stdout/stderr 或第三方依赖缓存；下列 SHA-256 只用于复核当前仍可见的本轮文件。
- 本报告只补充真实调用体验和失败边界，不升级 `CURRENT-REAL-SCENARIO-GATES.md` 的任何表格状态。

## Artifact Index

| 场景 | 关键 artifact | SHA-256 |
| --- | --- | --- |
| 定向 Baostock 顶层退出码 | `/tmp/stock-selection-real-A.Inm2lB/run/exit_code.txt` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| 定向 Baostock manifest | `/tmp/stock-selection-real-A.Inm2lB/run/output/run_manifest.json` | `d0bd35e4fb5376aa826691355bc3e05a767cad0dae6d431e63cc78e637cc11d0` |
| 定向 Baostock summary | `/tmp/stock-selection-real-A.Inm2lB/run/output/summary.json` | `e90435ee3b9449906a2844ecda42c8ad2fae9b81316d1763644dbc44dd4e7865` |
| 定向 Baostock history metadata | `/tmp/stock-selection-real-A.Inm2lB/run/output/history_metadata.json` | `bb6f27cac40eff3ad1a13b73946fae311d44338fb143b5979fd7c478c3dd3deb` |
| 全 A universe metadata | `/tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/universe_metadata.json` | `bb623afe1a227e5eb486e9c4bd309064eed54c2eb588e0139ceb3c374c390db7` |
| 全 A symbols 文件 | `/tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/symbols.txt` | `a3b8ad9e2b07b21aa03b1d3defbb1983ad261bf5e5ead9d4afe8a2b92c626f83` |
| 全 A plan-only manifest | `/tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/plan/run_manifest.json` | `d4cd6241a394e82fe1d5ef87370b6d70c3acc491acc524d6ae6b5262a7ab3ea6` |
| 全 A plan-only summary | `/tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/plan/summary.json` | `7218cb872c6228ae3984a6d09dee420823d5d970a8d51726e8b13056dccb1d15` |
| Pytdx metadata | `/tmp/stock-selection-pytdx-c.2c1BVN/fetch/metadata.json` | `feec6d51f59317e5ebb55a696ff0464fd619788294b64dfb0249f73979e76718` |
| Pytdx prices | `/tmp/stock-selection-pytdx-c.2c1BVN/fetch/prices.csv` | `538ae4569aa110e37cf729cf68fc1c1e788a7121142532ecafb017d2aab17e78` |
| 七源探针顶层退出码 | `/tmp/stock-selection-scenario-d.WH02s3/probe.exit-code.txt` | `1121cfccd5913f0a63fec40a6ffd44ea64f9dc135c66634ba001d10bcf4302a2` |
| 七源探针 summary | `/tmp/stock-selection-scenario-d.WH02s3/summary.json` | `e6f3e5a015f40b4f7b220e9075c501ca573765e597878ef0e7aad0428e180934` |
| 七源探针 archive manifest | `/tmp/stock-selection-scenario-d.WH02s3/archive/archive_manifest.json` | `212178051589ca812c06df3688202e66f2368e3ac504b60c666433265b472790` |

## 收据完整性复核

收口时重新计算了上表所有文件的 SHA-256，均与表中值一致。全 A 场景的独立最终校验返回 `0`，记录 `receipts_ok=true`、`forbidden_plan_artifacts_absent=true` 和 `git_status_unchanged=true`。Pytdx 收据记录 fetch 与 validate 均返回 `0`、`repo_files_newer_than_run_start=0`、`matching_processes_after=0`。七源 compact archive 的 manifest 校验逐项通过 21 个 payload；archive 根目录权限为 `drwx------`，内部没有符号链接。

顶层直接耗时收据如下：

| 场景 | 退出码 | 外层耗时 | 业务内部耗时 |
| --- | ---: | ---: | ---: |
| 定向 Baostock runner | `0` | `32.82s` | runner `15.807249s` |
| 全 A Baostock universe | `0` | `56.29s` | provider `27.066801s` |
| 全 A plan-only | `0` | `5.98s` | runner `0.187388s` |
| Pytdx fetch | `0` | `150.06s` | provider `1.694191s` |
| Pytdx validate | `0` | `6.39s` | 未单独记录内部阶段 |
| 七源有界 probe | `3` | `210.61s` | 七个 provider 子命令合计 `90.215320s` |

外层耗时包含隔离 `uv` 环境解析、下载、构建和进程启动，不能直接当作 provider 延迟。七源 probe 的 stderr 明确记录 fresh isolated 环境安装 43 个包；Pytdx fetch 的 stderr 记录首次构建 `pytdx` 和 `cryptography`。这解释了主要差额，但不构成固定性能基准。

## 场景一：定向 Baostock 真实选股

实际命令使用三个明确标的，并执行历史抓取、校验、generic 评分和 HTML 展示：

```bash
uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/stock-selection-real-A.Inm2lB/run/output \
  --mode generic --history-source baostock \
  --symbols 000001,600519,300750 \
  --start-date 2025-01-01 --end-date 2026-07-26 \
  --fail-on-skipped
```

- 顶层 exit 为 `0`。`fetch_history`、`validate` 和 `score` 子步骤均返回 `0`，耗时依次为 `8.690388s`、`2.662147s` 和 `4.092354s`。
- Baostock 写出 1,131 行、3 个 symbol；每个 symbol 为 377 行，实际日期范围为 `2025-01-02` 至 `2026-07-24`。请求结束日 `2026-07-26` 没有交易行，metadata 已以 `history_end_date_has_rows=false` 显式披露。
- 最终为成功空结果：`effective_empty_result=true`、`empty_result_reason=threshold_filtered_all`、`candidate_rows=0`、`diagnostic_rows=3`，且候选、诊断、summary、manifest 和 HTML 均已写出。
- 三个标的都未通过 `max_close` 和 `min_turn`，其中 `300750` 还未通过 `min_trend_score`。这只能解释本轮 0 候选，不能证明策略有效或无效。
- `execution_path=history_fetch_explicit_symbols_generic`、`coverage_class=explicit_symbol_pool`、`full_market_claim_allowed=false`，边界为 `explicit_symbols_not_full_market_scan`。该结果不是全 A 扫描或投资建议。

## 场景二：全 A 股票池与 plan-only

先调用公开 Baostock universe CLI，再把已落地的 5,200-symbol 文本文件交给 runner 的 `--plan-only` 路径：

```bash
uv run --with baostock python \
  skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py \
  --output /tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/universe.csv \
  --metadata-output /tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/universe_metadata.json \
  --snapshot-date 2026-07-24 --lookback-days 0 --retries 0 \
  --retry-interval-seconds 1 --fail-on-partial

uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/plan \
  --mode auto --history-source baostock \
  --symbols-file /tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/symbols.txt \
  --history-names-input /tmp/a-share-scenario-b-20260726-V3NlBl/artifacts/universe.csv \
  --history-missing-name-policy fail \
  --history-baostock-non-trading-policy reject \
  --start-date 2025-01-01 --end-date 2026-07-24 \
  --plan-only --no-html-report
```

- universe 顶层 exit 为 `0`。请求和解析日期均为 `2026-07-24`，`date_fallback_used=false`；原始 7,315 行中排除 2,115 行非沪深 A 股代码，得到 5,200 个 symbol，`partial_result=false`。
- `symbols.txt` 恰有 5,200 行、36,400 bytes，SHA-256 与 summary 记录的 `history_symbols_file_sha256` 一致。
- plan-only 顶层 exit 为 `0`，`status=planned`、`execution_mode=plan_only`、`commands_executed=false`、`history_artifact_status=not_written`。fetch、validate 和 score 三个步骤都为 `planned=true`、`executed=false`、`returncode=null`。
- `execution_path_reason=explicit_symbols_file`、`coverage_class=explicit_symbol_pool`、`full_market_claim_allowed=false`。因此该场景只证明股票池落地和计划可生成，没有执行全 A 历史抓取、校验、评分或 HTML。
- manifest 仍把 5,200 个代码完整复制到 `history_symbols`，文件为 82,072 bytes；同时已有可校验的 `history_symbols_file`、数量、大小和 SHA-256。该重复是已验证的 artifact 体积和审阅成本问题，不是数据正确性失败。

## 场景三：Pytdx 补充源边界

实际 fetch 使用项目默认 endpoint 和两个明确标的：

```bash
uv run --no-project --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001,600519 \
  --start-date 2026-01-01 --end-date 2026-07-24 \
  --output /tmp/stock-selection-pytdx-c.2c1BVN/fetch/prices.csv \
  --metadata-output /tmp/stock-selection-pytdx-c.2c1BVN/fetch/metadata.json \
  --timeout-seconds 10 --max-pages 1 --fail-on-fetch-error
```

- fetch 顶层 exit 为 `0`，默认 endpoint 为 `180.153.18.170:7709`。输出 268 行、2 个 symbol，每个 134 行，日期范围为 `2026-01-05` 至 `2026-07-24`。
- metadata 记录 `partial_result=false`、`failed_symbols=[]`、`empty_symbols=[]`、`possibly_truncated_symbols=[]`、`invalid_rows=0`，并保留 `pytdx_external_fetch_not_turnover_tradability_or_stability_proof` 边界。
- 后续 `validate_ohlcv.py` 返回 `0`，只证明基础 OHLCV 格式通过。metadata 同时明确 `selection_ready=false`，缺少 `turn/tradestatus/isST/name`，因此按严格选股边界停止，没有运行 score。
- metadata 没有复权声明字段，验证收据记录 `adjustment_declaration_present=false`；成交量单位也只能由 validate 披露为 `volume_unit_verification=not_verified_by_cli`。不能推断复权口径或成交量单位。
- fresh isolated 环境的第三方 `pytdx==1.72` 在 `block_reader.py` 输出两个 `SyntaxWarning`。它们没有改变本轮 exit，但属于依赖兼容告警，不能写成仓库源码告警已消除。

## 场景四：七源有界稳定性探针

实际 probe 使用单轮、每个 provider 40 秒上限和整体有界执行。它覆盖 Eastmoney spot、Baostock universe、Akshare、Pytdx、yfinance、Baostock history 和 ZZShare；没有自动 fallback 或 host rotation。

- 顶层 exit 为 `3`，summary 为 6/7 通过，`all_sources_all_iterations_passed=false`、`long_term_stability_claim=not_proven`、`short_window_claim_boundary=current_window_parameters_network_only`。
- Eastmoney spot、Baostock universe、Akshare、Pytdx、yfinance 和 ZZShare 分别耗时 `1.192180s`、`24.355397s`、`5.438586s`、`5.502659s`、`8.660357s` 和 `5.034453s`，均返回 `0`。
- Baostock history 在 `40.031688s` 触发外层有界执行器，返回 `124`、`command_timed_out=true`，没有写 metadata。probe 严格失败并将首个 required failure 记录为 `metadata_written`。
- Baostock history 缺 metadata 时，`failed_symbols_empty`、`empty_symbols_empty`、`invalid_rows_accounted`、`non_trading_rows_zero` 和 `tradestatus_missing_rows_zero` 仍因空默认值显示 `passed=true`。总门禁仍正确失败，但这些依赖 metadata 的检查状态具有误导性，是本轮确认的可观测性问题。
- compact archive 的 summary 与原 summary SHA-256 相同，manifest 中 21 个 payload 全部通过完整性校验。它只保存控制面证据，不保存价格数据，也不证明长期稳定性。

## 体验反馈分类

### 已验证问题

1. 本轮隔离 harness 的冷启动是主要外层耗时。四个子代理为隔离任务状态分别使用独立 `UV_CACHE_DIR`，七源 probe 还显式使用 `uv run --isolated`；定向 runner、universe、Pytdx 和七源 probe 的外层耗时分别比内部业务计时多约 `17.01s`、`29.22s`、`148.37s` 和 `120.39s`，stderr 同时记录依赖下载、构建或安装。这是本轮测试方式的成本，不是项目 runner 默认每次创建 fresh isolated 环境；常规 runbook 已支持共享 uv 缓存和复用 venv。
2. probe 在 metadata 未写出时仍把若干 metadata 依赖检查显示为通过。虽然 required gate 最终失败，但下钻报告会让读者误以为这些字段已经评估。
3. 显式 `--symbols-file` 已提供路径、数量、大小和 SHA-256，plan-only manifest 仍复制完整 5,200-symbol 数组，增加 artifact 体积和 Agent 上下文读取成本。
4. 成功空结果的 stdout 只有一条很长的 `OK:` 行，`effective_empty_result`、原因和核心 artifact 路径埋在大量机器字段中；人工扫描成本高。
5. Pytdx fetch stdout 没有直接披露 `selection_ready=false` 和缺失字段；必须打开 metadata 才能知道它不能直接进入严格评分。

### 单窗口现象

1. 本轮 Baostock history 在 40 秒上限内超时，但同轮 Baostock universe 通过，定向 Baostock runner 也在另一独立窗口通过。该现象只能描述本轮参数和网络，不能判定 Baostock 长期不可用。
2. 七源 6/7 通过、Pytdx 默认 endpoint 成功和 Eastmoney 单页成功都不证明长期稳定、未来免费、授权持续或生产 SLA。
3. 所有耗时均包含当前机器和临时依赖状态，不能外推为其他机器或热环境性能。

### 可验证优化建议

1. 常规 Agent 和性能复验应优先使用 runbook 已有的共享 uv 缓存或复用 venv 路径，并保留依赖缺失的显式失败。验收应分别记录冷启动和热启动，不把缓存命中解释为 provider 提速；需要隔离依赖时必须在报告中标明独立 `UV_CACHE_DIR` 或 `--isolated`。
2. 让成功空结果额外输出独立 `EMPTY_RESULT:` 摘要，直接列出 `empty_result_reason`、`candidates`、`diagnostics`、`summary` 和 `manifest`；保留现有机器字段和退出码。
3. 为 universe 和 Baostock 长调用增加 login、query、filter、write 阶段的低频 stderr 进度，保持 stdout 机器摘要稳定。
4. probe 在 `metadata_written=false` 时应把所有依赖 metadata 的检查标记为 `not_evaluated`，并确保它们不能计为通过；补 metadata 缺失、超时和普通 provider failure 回归。
5. Pytdx stdout 应直接输出 `selection_ready` 和 `missing_provider_fields`；metadata 可增加显式 `price_adjustment=unknown`、`volume_unit=unknown`，避免由字段缺失推断口径。
6. 对显式 `--symbols-file` 的 plan-only manifest，可只保留 path、origin、count、size 和 SHA-256，将完整列表留在 `selected_symbols.json` 或原 symbols 文件；变更前需确认 resume、审计和兼容消费者不依赖内联数组。

## 结论边界

四个场景都保留了真实命令、直接退出码、耗时和可复核 artifact，没有发现子代理写入仓库、泄露凭据、使用 mock、自动 fallback 或 host rotation。定向 Baostock 得到的是 3-symbol 成功空结果；全 A 场景只完成 5,200-symbol 股票池和未执行的 plan-only；Pytdx 只证明有限 OHLCV 补充并明确不具备严格选股字段；七源 probe 严格失败且仍维持长期稳定性未证明。

本轮没有执行新的全 A 历史长跑、全 A 最终评分、真实 prediction 生成、样本外回测、完整涨跌停规则、券商订单、真实成交、滑点或资金容量门禁。当前真实门禁总状态继续以 [CURRENT-REAL-SCENARIO-GATES.md](../CURRENT-REAL-SCENARIO-GATES.md) 和其中引用的 dated evidence 为准。
