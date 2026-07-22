# Multi-Agent Real Scenario Experience Validation 2026-07-22

本报告记录 2026-07-22 由五个隔离 Agent 按 `SKILL.md` 路由完成的真实使用场景验收，以及为补齐 probe 顶层退出码收据而进行的一次同参数后续复跑。它只描述当前机器、当前网络、指定日期窗口、指定 provider 和指定超时预算的行为，不构成投资建议，也不证明全 A 历史长跑、全 A 评分、prediction、回测、券商订单、真实成交、长期稳定性、免费额度或授权持续有效。

## 执行边界

- 每个 Agent 的业务 artifact 都只写入独占的 `/tmp/a-share-opt044-*` 目录，没有修改仓库代码、配置、Git index 或任务台账。运行过程产生的可再生 `__pycache__` 已在本地验证前清理。
- 所有联网命令显式选择 provider。没有自动 source fallback、自动 host rotation、mock、演示数据、伪造行情、prediction、候选、回测或成功路径。
- 五个 Agent 均已在收集反馈后关闭。复核时未发现本轮 `run_today_a_share_selection.py`、Baostock、Pytdx 或 probe 子进程残留。
- `/tmp` artifact 是易失性原始证据。本报告不复制价格 CSV、Parquet 内容、HTML、完整 stdout/stderr 或第三方缓存；下列 SHA-256 仅用于复核当前可见文件。
- 本报告是调用体验、性能观察和失败边界补充 evidence，不升级 `CURRENT-REAL-SCENARIO-GATES.md` 的任何真实门禁状态。

## 命令和退出码证据口径

- 只有独立保存的外层退出码文件才可写作对应顶层 CLI 的 exit code。`run_manifest.json.steps[].returncode` 只描述 runner 子步骤，不能替代外层命令退出码。
- 第一轮七源 probe 的 shell 在写入 `$?` 前没有完成后置收据，因此本报告只将其 `summary.json` 和 stderr 记为严格失败证据，不把后写的推导值当作该轮顶层 exit code。
- 为补齐这一缺口，主流程在新的独占目录以相同 source 集、相同参数和相同 8 秒子命令上限复跑。该后续窗口保留了直接 shell 收据，但其网络结果与第一轮不同，必须分开解释。

## Artifact Index

| 场景 | 关键 artifact | SHA-256 |
| --- | --- | --- |
| 定向 Baostock manifest | `/tmp/a-share-opt044-directed-baostock/run/run_manifest.json` | `5cd356f413f096c6ae809392f897c3b9a36c2d4421f5ce5ff6d830ccb70f8500` |
| 定向 Baostock summary | `/tmp/a-share-opt044-directed-baostock/run/summary.json` | `1dcfde8da46e4083cd0219613b0a23c1a1f6a74421a1178644c061ae5dc4efe9` |
| 全 A universe metadata | `/tmp/a-share-opt044-full-a-plan/spot_metadata.json` | `001eba0b6d98a08447171e7e071dc2d862e4a419255b5f432d8d7ea21a54bf99` |
| 全 A plan-only manifest | `/tmp/a-share-opt044-full-a-plan/spot-plan-run/run_manifest.json` | `b14fa74d325f8883789d5beb87e246085485d857d2a0ee8939cf2444a2f4c31c` |
| 全 A plan-only summary | `/tmp/a-share-opt044-full-a-plan/spot-plan-run/summary.json` | `f170a55ca61349ee7edcbfbe34015dec808fc95058f37e452ebc76956c23c02a` |
| Baostock Parquet manifest | `/tmp/a-share-opt044-baostock-parquet/run/run_manifest.json` | `96a250fbd084f6e2125e33d6fbf0712754e0c7686c4cfdb8bc13fb3c388944d9` |
| Baostock Parquet summary | `/tmp/a-share-opt044-baostock-parquet/run/summary.json` | `a6f3a298b9e9f3e20fbb4590c608130c2c040c5c5cabc09924f1a5da34ec4cd3` |
| Baostock Parquet metadata | `/tmp/a-share-opt044-baostock-parquet/run/history_metadata.json` | `d5c63dee07aea045c398b6960e72042c60d6e7658d5e47ae2ca590f50b590f34` |
| Pytdx runner manifest | `/tmp/a-share-opt044-pytdx-boundary/run/run_manifest.json` | `3e2851658610509b336b33d9795f5e9a50515c1e2f03a4766b1f8ddec8c557c3` |
| Pytdx runner summary | `/tmp/a-share-opt044-pytdx-boundary/run/summary.json` | `a2b3693632a48a435d5457d41b787210a505e38bd58ffb59e0cb1cbd1503bf69` |
| Pytdx metadata | `/tmp/a-share-opt044-pytdx-boundary/run/history_metadata.json` | `efd60fcb32ab5bb59609db5610e75075a7d1dc1ef7d84f3a5de5c628106f142c` |
| 首轮七源 probe summary | `/tmp/a-share-opt044-external-probe/summary.json` | `475fe8c0156ffe53ff8be00ead42de8ad7ffbc505ece454cf6fd14d1cd16a9b2` |
| 首轮七源 probe archive manifest | `/tmp/a-share-opt044-external-probe/archive/archive_manifest.json` | `374a152ef969f544b5f96508c31fd3a4546ea9d83545fbb5482c4db716685fe8` |
| 后续七源 probe summary | `/tmp/a-share-opt044-external-probe-direct-20260722/summary.json` | `7abbfe67dcce7599428d9c6e8540506fc26605611c258f1ad753d4ce1f8b3f46` |
| 后续七源 probe archive manifest | `/tmp/a-share-opt044-external-probe-direct-20260722/archive/archive_manifest.json` | `22a97f8d7e3a46ea4993645e3dda70bd132d2030a4768e980f692a519bd14c29` |
| 后续七源 probe exit receipt | `/tmp/a-share-opt044-external-probe-direct-20260722/exit_code.txt` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |

## 收据完整性复核

在本次 2026-07-22 收口复核时，上表 16 个索引文件均仍存在，重新计算的 SHA-256 全部与表中值一致。以下补充保存的外层收据；复核只读取现有 `/tmp` 文件，没有重跑任何历史联网命令。收据证明指定命令窗口的退出码或耗时，不提升任何真实门禁。

| 场景 | 直接外层收据和值 | SHA-256 |
| --- | --- | --- |
| 定向 Baostock | `/tmp/a-share-opt044-directed-baostock/exit_code.txt`: `0`；`/tmp/a-share-opt044-directed-baostock/time-p.log`: `real 15.68` | `/tmp/a-share-opt044-directed-baostock/exit_code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-opt044-directed-baostock/time-p.log`: `68b4a02418fd1a17a2c1fb5636da943beaa42c11418bf7ad06d5e24f7ad8151e` |
| 全 A universe | `/tmp/a-share-opt044-full-a-plan/universe-exit-code.txt`: `0`；`/tmp/a-share-opt044-full-a-plan/universe-time.txt`: `real 43.16` | `/tmp/a-share-opt044-full-a-plan/universe-exit-code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-opt044-full-a-plan/universe-time.txt`: `7c8b4ad02618859f22c2795d9661467479eeeff2872c278685d41aa20e97b990` |
| 全 A plan-only | `/tmp/a-share-opt044-full-a-plan/spot-plan-exit-code.txt`: `0`；`/tmp/a-share-opt044-full-a-plan/spot-plan-time.txt`: `real 12.81` | `/tmp/a-share-opt044-full-a-plan/spot-plan-exit-code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-opt044-full-a-plan/spot-plan-time.txt`: `974d398411bbfd6d52211e0c5672161b225c516338cd2f9b2657bdb0157677ea` |
| Baostock Parquet | 最终 `/tmp/a-share-opt044-baostock-parquet/attempt-4/exit_code.txt`: `0`；`/tmp/a-share-opt044-baostock-parquet/attempt-4/time.txt`: `real 35.23` | `/tmp/a-share-opt044-baostock-parquet/attempt-4/exit_code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-opt044-baostock-parquet/attempt-4/time.txt`: `62c9ad4df32193e87494d6e7d090c554f3df59e93afe01e8197ac6be6a38bc12` |
| Pytdx 严格边界 | `/tmp/a-share-opt044-pytdx-boundary/exit_code-final.txt`: `3`；`/tmp/a-share-opt044-pytdx-boundary/time-p-final.txt`: `real 2.32` | `/tmp/a-share-opt044-pytdx-boundary/exit_code-final.txt`: `1121cfccd5913f0a63fec40a6ffd44ea64f9dc135c66634ba001d10bcf4302a2`；`/tmp/a-share-opt044-pytdx-boundary/time-p-final.txt`: `72dd96555605e19412131a7d283f402ead30b4fb5ae4d377e6a1d2ef2da49e26` |
| 首轮七源 probe | 只有 `/tmp/a-share-opt044-external-probe/time.txt`: `real 181.41`；`/tmp/a-share-opt044-external-probe/exit_code_provenance.txt` 明确该轮没有直接 shell-status capture，不能将其派生 `3` 写作顶层 exit | `/tmp/a-share-opt044-external-probe/time.txt`: `b472d72fc13a1de601a014a93fdd37ab60fde189b2087335a2cf05fd69a1dd61`；`/tmp/a-share-opt044-external-probe/exit_code_provenance.txt`: `059575781d51311cccb09496eb83871c1f98313f0078082de1043f8c1ca01eaf` |
| 后续七源 probe | `/tmp/a-share-opt044-external-probe-direct-20260722/exit_code.txt`: `0`；`/tmp/a-share-opt044-external-probe-direct-20260722/time.txt`: `real 42.91` | `/tmp/a-share-opt044-external-probe-direct-20260722/exit_code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-opt044-external-probe-direct-20260722/time.txt`: `20c307d25cd98ebb3c9a0deecc8b1e43b8231e2f84c7947887a90686d671f9b1` |

## 场景一：定向 Baostock 真实评分

```bash
uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt044-directed-baostock/run \
  --mode auto --history-source baostock --symbols 000001,600000,300750 \
  --start-date 2025-07-01 --end-date 2026-07-17 \
  --fail-on-skipped --no-html-report
```

- 外层 exit 是 `0`，`/usr/bin/time -p` 为 `real 15.68` 秒；runner `run_duration_seconds=9.503842`。
- `fetch_history`、`validate`、`score` 三个子步骤均为 return code `0`，耗时依次为 `4.224194`、`2.444058`、`2.501203` 秒。
- `history_metadata.json` 记录 `rows=765`、`symbol_count=3`、`partial_result=false`、`failed_symbols=[]`、`empty_symbols=[]`。
- 最终是成功空结果：`effective_empty_result=true`、`empty_result_reason=threshold_filtered_all`、`candidate_rows=0`、`diagnostic_rows=3`。`selection_failed_reason` 和 `selection_failed_next_action` 均为空，`candidates.csv` 仅含表头，诊断保留全部三只标的的阈值失败原因。
- 路径是 `history_fetch_explicit_symbols_generic`，`coverage_class=explicit_symbol_pool`，`full_market_claim_allowed=false`，边界为 `explicit_symbols_not_full_market_scan`。没有消费 prediction 或执行 LightGBM。

体验观察：定向入口、必要参数和首轮 artifact 足够容易定位。进程在 15 秒外层运行期间没有阶段性流式提示，fetch、validate、score 的进度只能在结束后从 manifest 查看。成功空结果可审计，但零候选下 `candidate_field_coverage` 显示 `rows_evaluated=0` 和 `all_fields_present=false`，容易被误读为字段质量失败。

## 场景二：全 A 股票池与 plan-only

先用公开 universe CLI 获得真实股票池，再把已落地快照交给 runner 生成计划：

```bash
uv run --with baostock python \
  skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py \
  --output /tmp/a-share-opt044-full-a-plan/spot.csv \
  --metadata-output /tmp/a-share-opt044-full-a-plan/spot_metadata.json \
  --snapshot-date 2026-07-22 --lookback-days 7 --retries 0 \
  --retry-interval-seconds 0 --fail-on-partial

uv run --with pandas --with numpy python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt044-full-a-plan/spot-plan-run \
  --mode auto --spot-input /tmp/a-share-opt044-full-a-plan/spot.csv \
  --derive-symbols-from-spot --derive-all-spot-symbols \
  --max-history-symbols 6000 --history-source baostock \
  --start-date 2025-07-01 --end-date 2026-07-17 \
  --plan-only --no-html-report
```

- universe CLI 外层 exit 是 `0`，耗时 `real 43.16` 秒。metadata 记录 `symbol_count=5200`、`partial_result=false`、请求日 `2026-07-22`、解析日 `2026-07-21`、`date_fallback_used=true`。其边界仍是 `baostock_universe_snapshot_not_realtime_spot_or_full_market_proof`。
- plan-only CLI 外层 exit 是 `0`，耗时 `real 12.81` 秒。`selected_symbols.json` 记录 `source=spot_snapshot`、`selected_symbol_count=5200`、`raw_spot_rows=5200`、`filtered_spot_rows=5200`，且未应用价格、成交额或 ST 预筛。
- plan 记录 `status=planned`、`plan_only=true`、`commands_executed=false`、`history_artifact_status=not_written`、`plan_only_reason=plan_only_no_commands_executed` 和 `plan_only_next_action=execute_planned_workflow_to_collect_artifacts`。`fetch_history`、`validate`、`score` 均为 planned、未执行且没有 return code。
- `history_symbols` 含 5,200 个实际代码；planned `fetch_history` 仍将它们内联到单个 `--symbols` 参数，长度为 36,399 字符，没有使用 `--symbols-file`。本轮没有历史抓取、校验、评分、候选、诊断或 HTML 输出。
- `coverage_class=spot_derived_limited_pool`、`full_market_claim_allowed=false`，边界为 `spot_derived_explicit_limit_requires_artifact_review`。真实股票池和计划都不构成全 A 历史或选股完成。

额外验证：把 `--fetch-spot baostock_universe` 与 `--plan-only` 放在同一 runner 命令时，计划模式按合同不会执行 `fetch_spot`，只留下 `<derived_from_spot_snapshot>` 占位符。正确的真实使用方式是上述两步：先显式落地并审查股票池，再进行计划。

体验观察：两阶段路径能正确避免把未抓取股票池说成真实广度，但 36 KB 内联命令会增加人工审查、日志截断和复制错误风险。计划 summary 对本地 spot 输入的 provenance 投影有限，用户仍需打开 `selected_symbols.json` 和原始 metadata 才能完整理解 5,200 代码来源。

## 场景三：Baostock Parquet 定向路径

```bash
uv run --with pandas --with numpy --with pyarrow --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt044-baostock-parquet/run \
  --mode auto --history-source baostock --symbols 000001,600000,300750 \
  --start-date 2025-07-01 --end-date 2026-07-17 \
  --history-output-format parquet --fail-on-skipped --no-html-report
```

- 外层 exit 是 `0`，`/usr/bin/time -p` 为 `real 35.23` 秒；runner `run_duration_seconds=24.263816`。
- `fetch_history`、`validate`、`score` 均成功，并且三个 command 都引用同一 `prices.parquet`。
- `history_metadata.json` 记录 `output_format=parquet`、`output_written=true`、`rows=765`、`symbol_count=3`、`partial_result=false`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`non_trading_rows=0`。产物大小是 56,763 bytes。
- 最终仍是 `threshold_filtered_all` 的成功空结果，`candidate_rows=0`、`diagnostic_rows=3`；它是 `explicit_symbol_pool`，并保持 `full_market_claim_allowed=false`。

体验观察：Parquet 入口可发现，`--with pyarrow` 和 `--history-output-format parquet` 都是显式控制项，且没有 fallback。独立缓存下的 PyArrow 下载和安装成本应与 runner 的业务耗时分开看；本次小样本只证明格式链路，不证明全 A 本地 I/O 或远端吞吐改善。

## 场景四：Pytdx 补充源严格边界

```bash
uv run --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt044-pytdx-boundary/run \
  --mode auto --history-source pytdx --symbols 000001,600000 \
  --start-date 2025-07-01 --end-date 2026-07-17 \
  --history-timeout-seconds 10 --fail-on-skipped --no-html-report
```

- 外层 exit 是 `3`，`/usr/bin/time -p` 为 `real 2.32` 秒。使用默认 Pytdx endpoint `180.153.18.170:7709`，没有 host rotation。
- 抓取子步骤成功，metadata 记录 `rows=510`、`symbol_count=2`、`raw_rows=790`、`api_request_count=2`、`duration_seconds=0.277729`、`partial_result=false`、`failed_symbols=[]`、`empty_symbols=[]`。
- metadata 明确保持 `selection_ready=false`、`missing_provider_fields=["turn","tradestatus","isST","name"]` 和 `name_value_policy=blank_missing_provider_name`。随后 validate return code 是 `1`，runner 在评分前以 `selection_failed_reason=validation_failed_before_scoring` 失败关闭，未写 candidates 或 diagnostics。
- 本轮仍是 `explicit_symbol_pool`，`full_market_claim_allowed=false`，边界为 `explicit_symbols_not_full_market_scan`。这证明有限 OHLCV/amount 补充观察，不证明 strict selection、全 A 主历史、可交易性、长期稳定性或交易完成。

体验观察：失败语义和缺字段原因可从 stderr、metadata 与 summary 的嵌套 `input_metadata.history_missing_provider_fields` 找到，但 summary 顶层没有专门的严格缺字段摘要。界面或报告也应明确区分“补充 OHLCV 已获取”和“严格选股未就绪”。

## 场景五：有界七源 probe 的两个网络窗口

首轮 Agent 使用下列命令，保留 summary、stderr 和 owner-only archive，但没有留下直接外层 exit receipt：

```bash
uv run --with pandas --with numpy --with baostock --with akshare \
  --with pytdx --with yfinance --with zzshare python \
  skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
  --output-dir /tmp/a-share-opt044-external-probe/probe \
  --summary-output /tmp/a-share-opt044-external-probe/summary.json \
  --archive-dir /tmp/a-share-opt044-external-probe/archive \
  --iterations 1 --command-timeout-seconds 8 \
  --eastmoney-timeout-seconds 5 --pytdx-timeout-seconds 5 \
  --yfinance-timeout-seconds 5
```

- 首轮 summary 为 7 次运行中的 4 次通过。Eastmoney、Akshare、Pytdx、ZZShare 通过；Baostock universe、Baostock history、yfinance 均在 8 秒上限超时，三者的 `latest_source_returncode=124`、`latest_command_timed_out=true`、首个 required failure 为 `metadata_written`。
- 首轮 archive 通过 `verify_archive_integrity`，权限为 `0700`，有 7 条 source record、19 个 payload，且不含 CSV、Parquet 或 PQ 价格文件。
- 首轮 `/usr/bin/time -p` 为 `real 181.41` 秒。它包含临时依赖下载、构建、安装、7 个 source 的串行执行以及三个超时，不能当作任何单一 provider 吞吐指标。

为取得直接 shell 收据，主流程在新的目录中以相同 source 集和参数复跑：

```bash
uv run --with pandas --with numpy --with baostock --with akshare \
  --with pytdx --with yfinance --with zzshare python \
  skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
  --output-dir /tmp/a-share-opt044-external-probe-direct-20260722/probe \
  --summary-output /tmp/a-share-opt044-external-probe-direct-20260722/summary.json \
  --archive-dir /tmp/a-share-opt044-external-probe-direct-20260722/archive \
  --iterations 1 --command-timeout-seconds 8 \
  --eastmoney-timeout-seconds 5 --pytdx-timeout-seconds 5 \
  --yfinance-timeout-seconds 5
```

- 后续窗口的独立 exit receipt 是 `0`，`/usr/bin/time -p` 为 `real 42.91` 秒。七个 source 均通过，且 `all_sources_all_iterations_passed=true`。
- 后续 archive 也通过完整性复核，权限为 `0700`，有 7 条 source record、22 个 payload，仍没有价格文件。
- 两个窗口的 summary 都保持 `long_term_stability_claim=not_proven` 和 `short_window_claim_boundary=current_window_parameters_network_only`。首轮严格失败和后续全通过共同证明窗口性，不能被解释为长期稳定、免费额度、授权持续、自动 fallback 或全 A 完成。

体验观察：source summary 已能显示 return code、耗时、timeout、首个 required failure、metadata 路径和 stderr 非空状态，足以区分大多数严格失败。仍可增加 setup、source 执行和 archive 清理的单调计时，以及脱敏 `timeout_stage`/终止方式，帮助解释外层耗时与单 source 耗时差额，且不增加重试、fallback 或 host rotation。

## 汇总反馈和可验证优化候选

本轮没有发现需要放宽数据契约、修改 provider 路由或改变严格门禁的正确性缺陷。以下是由 artifact 与实际操作支持的体验优化候选，应各自建立原子任务并补回归测试后再实施：

1. 全 A plan-only 对大 symbol 集落地并引用 `history_symbols.txt`，而不是把 5,200 个代码内联到 36,399 字符的 command；同时保留 manifest 中可审计的数量、哈希和完整展开参数。
2. 为成功空结果增加结构化 `empty_result_next_action`，并将零候选 `candidate_field_coverage` 表达为不适用而非字段缺失，避免误判 strict failure。
3. 为长期真实任务增加默认关闭的阶段进度和性能观测：fetch、validate、score 的开始、结束、耗时、行数和吞吐都可写入独立 profile，而不改变候选、排序或失败语义。
4. 在 plan-only summary 中投影已落地 spot metadata 的有限 provenance，例如路径、内容哈希、source、resolved snapshot date 和 `partial_result`；该投影不得被解释为历史、评分或全市场完成。
5. 在 Pytdx 严格失败 summary 顶层投影缺失字段，并在展示层明确 `selection_ready=false`；任何 companion merge 仍必须要求同一 `symbol+date` 的真实字段，禁止最近值或前向填充。
6. 为外部 probe 增加 setup、source 执行和归档阶段计时，以及脱敏的超时阶段信息；默认全 source probe 的行为、严格失败、无自动 fallback 和长期稳定性边界保持不变。

## 当前门禁边界

本报告没有执行全 A 历史冷启动或新的全 A 最终评分、真实 prediction 生成、样本外回测、完整涨跌停规则、券商订单、真实成交、滑点或资金容量门禁。当前真实门禁总状态继续以 [CURRENT-REAL-SCENARIO-GATES.md](../CURRENT-REAL-SCENARIO-GATES.md) 和其中引用的 dated evidence 为准。
