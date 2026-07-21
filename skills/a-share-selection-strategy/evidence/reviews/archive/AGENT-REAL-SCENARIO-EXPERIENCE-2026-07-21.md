# Multi-Agent Real Scenario Experience Validation 2026-07-21

本报告记录 2026-07-21 由两轮隔离 Agent 按 `SKILL.md` 路由完成的真实使用场景体验复验。它只记录当前机器、当前网络、指定日期窗口和指定 provider 的实际行为，不构成投资建议，也不证明全 A 长跑、实时行情、真实 LightGBM prediction、回测收益、券商订单、真实成交、长期稳定性、免费额度或授权持续有效。

## 执行边界

- 每个 Agent 只向独占的 `/tmp/a-share-opt040-*`、`/tmp/a-share-opt040-rerun-*` 或 `/private/tmp/a-share-scenario-pytdx-*` 目录写 artifact，没有修改仓库代码、配置或 Git 状态。
- 两轮场景前后复核的仓库 Git 变更都只包含父任务预先锁定 `OPT-040` 所需的文档和任务改动；场景运行产生的可再生 `__pycache__` 会在本地门禁前清理，没有发现由场景 Agent 新增的业务改动、暂存项或未跟踪文件。
- 所有联网命令显式选择 provider。没有自动 source fallback、自动 host 轮换、mock、伪造行情、prediction、候选、回测或成功路径。
- `/tmp` artifact 是易失性原始证据。本报告不复制价格 CSV、HTML、完整 stdout 或第三方缓存；复核时应先核对下方 SHA-256，再读取对应 JSON、stdout 和 stderr。
- 本轮新增的体验观察不会升级 `CURRENT-REAL-SCENARIO-GATES.md` 中任何真实门禁状态。

## 命令和退出码证据口径

- 只有独立保存的外层退出码文件、外层执行记录，或原始 Agent 会话的最终进程结果，才可写作对应顶层 CLI 的 exit code。
- `run_manifest.json.steps[].returncode` 只描述 runner 已执行子步骤；不可将它当作外层命令退出码。
- 每个场景的完整命令优先保存在同目录 `command.txt`。第一轮 7-source probe、第一轮 Pytdx provider merge contract、第二轮全 A plan-only 和第二轮 probe 的顶层命令从原始 Agent 会话恢复并在本报告完整列出；第一轮 merge 的持久化 `command.txt` 只是明确占位摘要，不能替代该会话记录。恢复的会话结果只补命令或外层码证据，不改变 `/tmp` artifact 的内容。
- 外层记录未保留时，本报告只陈述持久化的子步骤结果和缺失原因，不从脚本源码或严格门禁分支推断历史外层退出码。

## Artifact Index

| 场景 | 关键 artifact | SHA-256 |
| --- | --- | --- |
| 定向 Baostock 失败关闭 | `/tmp/a-share-opt040-targeted-cn9cUM/run_manifest.json` | `b4c6bba48ef4cf9fdf17c355aaccd5820200e5de8d2d4cf7f79a583c1119b8fe` |
| 定向 Baostock 失败摘要 | `/tmp/a-share-opt040-targeted-cn9cUM/summary.json` | `4f6da59b62af6ce6937e5483580563fa8fba85de5bc9509e4b42f7de1e6018eb` |
| 全 A 股票池预检 | `/tmp/a-share-opt040-fulla-KFHGWS/spot_metadata.json` | `9d958f9d5a5aa7c72a306e1bcfd1c61aae83c7443eee80d1d4509eb74915f6af` |
| 全 A plan-only manifest | `/tmp/a-share-opt040-fulla-KFHGWS/pass1-plan/run_manifest.json` | `d5cade046bee0950353447a866d83d7491f7ebb0fa762b9e90a2c802ed3aca68` |
| 全 A plan-only 外层退出码 | `/tmp/a-share-opt040-fulla-KFHGWS/plan.exit_code` | `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa` |
| 全 A plan-only 外层墙钟 | `/tmp/a-share-opt040-fulla-KFHGWS/plan.wall_seconds` | `10159baf262b43a92d95db59dae1f72c645127301661e0a3ce4e38b295a97c58` |
| Pytdx 补充源 metadata | `/tmp/a-share-opt040-pytdx-Rs2gle/fetch_strict_window/metadata.json` | `c3f3c2726f3ed914d9ea0976ee71f9ed02d62c931f214eafd1c89042beace50f` |
| Pytdx 原始价格文件 | `/tmp/a-share-opt040-pytdx-Rs2gle/fetch_strict_window/prices.csv` | `72c054cefd099e0f312e9998468bba40eecf3a8dd791f5cc3b7dfb612b11b707` |
| Pytdx merge-contract 输入 metadata | `/tmp/a-share-opt040-pytdx-Rs2gle/fetch/metadata.json` | `efb4f846bc2b52642b7674aae1120fa5d5282c0b38e25fa25b81c815d1c615b5` |
| Pytdx merge-contract stderr | `/tmp/a-share-opt040-pytdx-Rs2gle/verified_merge/stderr.txt` | `4e09b661d3389e71d2822eef7fbd59672443c29ed7676b664f44eeeb20aae3ab` |
| 外部源探针摘要 | `/tmp/a-share-opt040-sources-BUmUTR/summary.json` | `9a033f7c07b5b048266ea5274c01fadf2ec42e623a1745896812d38c92d8b522` |
| 外部源探针归档清单 | `/tmp/a-share-opt040-sources-BUmUTR/archive/archive_manifest.json` | `21d02ef0ad4ee4d9711de27c76c2eaeae85a9cef5ce81156bcf99e48e3ce5f6b` |
| 第二轮定向 Baostock manifest | `/tmp/a-share-opt040-rerun-directed-RxTjwIQ2/run_manifest.json` | `e3f86fa70aaa5ca760318cc3da154f9ec26e0a7ce5e532fabf582942a97c1753` |
| 第二轮定向 Baostock 摘要 | `/tmp/a-share-opt040-rerun-directed-RxTjwIQ2/summary.json` | `6090184cd187ff50c0b09175b35f1380b3267f7fe8fb9410d9dbddaf8ef34b4a` |
| 第二轮全 A plan-only manifest | `/tmp/a-share-opt040-rerun-fulla-UC34M0/pass1/run_manifest.json` | `e2b71907dc508519d24ccee75f5a5754fd8fe5dc39559d325cdf20beb2732e8a` |
| 第二轮全 A plan-only 摘要 | `/tmp/a-share-opt040-rerun-fulla-UC34M0/pass1/summary.json` | `bac5643ee42baef12540db2666f4dcd40ff252a4e74a450cf7900987580ebc06` |
| 第二轮全 A plan-only 外层执行记录 | `/tmp/a-share-opt040-rerun-fulla-UC34M0/execution_record.json` | `cf3fe32fa43fcc9ef4d356c16bbf4c2101a366029e79e6bbed3d5ffe823adc8f` |
| 第二轮 Pytdx metadata | `/private/tmp/a-share-scenario-pytdx-brGIZr/metadata.json` | `c417cf1c11c2cff73da9f45365a69798b936cc47fcda698795b4b66d8840f2ff` |
| 第二轮 Pytdx runner manifest | `/private/tmp/a-share-scenario-pytdx-brGIZr/runner/run_manifest.json` | `0a19cc03167593ac26423855dcf02186c910d8369ec68ed90a72a4ef7ae0c55d` |
| 第二轮外部源探针摘要 | `/tmp/a-share-opt040-rerun-probe-F6eCL5/summary.json` | `1bc9beb146fd11f724bbab81e6ee7e91778b73f8c77df253b0f2c47a7a232470` |
| 第二轮外部源探针归档清单 | `/tmp/a-share-opt040-rerun-probe-F6eCL5/archive/archive_manifest.json` | `6204ac4a7eccdd24f7d9f4b9d519f73ed303fc0d9c6572440e91ef7b2f37a082` |

## 场景一：定向真实 A 股评分的失败关闭

Agent 使用显式 `baostock` provider 对 `000001,600000` 运行 generic 定向任务：

```bash
uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt040-targeted-cn9cUM \
  --mode generic --history-source baostock --symbols 000001,600000 \
  --start-date 2025-01-01 --end-date 2026-07-17 \
  --fail-on-skipped --score-profile
```

- 第一轮定向 Baostock 的外层退出码未保留。`run_manifest.json` 记录 `run_duration_seconds=109.192162`，其中 `fetch_history.duration_seconds=109.113039`、该子步骤 return code 为 `2`；它不是顶层 CLI exit code。
- Baostock 登录失败：`10002007 网络接收错误`；manifest 还保留了 `Connection reset by peer` 和 `Broken pipe` 的原始 stdout。
- `execution_path=history_fetch_explicit_symbols_generic`、`coverage_class=explicit_symbol_pool`、`full_market_claim_allowed=false`，边界为 `explicit_symbols_not_full_market_scan`。
- `selection_failed_reason=fetch_history_failed`，`selection_failed_next_action=inspect_failed_step_details_and_rerun`。
- `history_output_written=false`、`history_metadata_output_written=false`、`candidates_output_written=false`、`diagnostics_output_written=false`。没有将旧 CSV 或部分数据写成成功结果。

这只证明当前网络下两个固定标的的失败关闭和 artifact 收口，不证明 Baostock、全 A、prediction、收益或交易结果。

## 场景二：全 A 股票池预检与 plan-only

真实股票池预检使用显式重试和 `--lookback-days 7`：

```bash
uv run --with baostock python \
  skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py \
  --output /tmp/a-share-opt040-fulla-KFHGWS/spot.csv \
  --metadata-output /tmp/a-share-opt040-fulla-KFHGWS/spot_metadata.json \
  --retries 5 --retry-interval-seconds 1 --lookback-days 7 --fail-on-partial
```

- 第一轮 universe 预检的外层监督进程在写入自身退出码前被中断，因此本报告不声明本次 CLI 的外层 exit code。
- metadata 记录 6 次 login 失败、`error=baostock login failed: 10002007 网络接收错误。`、`duration_seconds=395.906567`、`symbol_count=0`、`partial_result=true`、`output_written=false`、`metadata_output_written=true`。
- `requested_snapshot_date` 与 `resolved_snapshot_date` 都是 `2026-07-21`，`date_fallback_used=false`。没有生成 `spot.csv` 或实际全 A symbol 集，也没有切换 source。

随后验证不执行网络抓取的安全 plan-only 路径：

```bash
uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt040-fulla-KFHGWS/pass1-plan \
  --mode auto --fetch-spot baostock_universe \
  --spot-fallback-lookback-days 7 --spot-fallback-retries 5 \
  --spot-fallback-retry-interval-seconds 1 --fail-on-partial-spot \
  --derive-symbols-from-spot --derive-all-spot-symbols \
  --max-history-symbols 6000 --history-source baostock \
  --start-date 2025-07-21 --end-date 2026-07-21 \
  --history-baostock-non-trading-policy reject --plan-only --no-html-report
```

- `/tmp/a-share-opt040-fulla-KFHGWS/plan.exit_code` 为 `0`，`/tmp/a-share-opt040-fulla-KFHGWS/plan.wall_seconds` 为 `7` 秒；`run_duration_seconds=0.059748`。
- `status=planned`、`commands_executed=false`、`history_artifact_status=not_written`、`candidates_output_written=false`、`diagnostics_output_written=false`。
- `execution_path=history_fetch_spot_derived_explicit_limit_with_fetched_spot_generic`、`coverage_class=spot_derived_limited_pool`、`full_market_claim_allowed=false`。
- 计划中的 `history_symbols=["<derived_from_spot_snapshot>"]` 只是未落地 spot artifact 的占位符，不是实际全 A symbol 集；不能生成真实增量 bucket，也没有执行全 A 历史、清洗、provenance、评分、prediction 或回测。

这证明全 A 路径不会因缺少股票池 artifact 伪造 symbol 集或历史抓取成功，但当前 Baostock 网络失败会让预检在重试完成前长时间无进度。

## 场景三：Pytdx 补充源和严格边界

Agent 使用固定 endpoint 进行少量真实请求：

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -p \
  uv run --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001,600000 --start-date 2025-09-01 --end-date 2026-03-31 \
  --output /tmp/a-share-opt040-pytdx-Rs2gle/fetch_strict_window/prices.csv \
  --metadata-output /tmp/a-share-opt040-pytdx-Rs2gle/fetch_strict_window/metadata.json \
  --host 180.153.18.170 --port 7709 --timeout-seconds 10 \
  --page-size 800 --max-pages 2 --fail-on-fetch-error
```

- fetch exit `0`；`rows=276`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`possibly_truncated_symbols=[]`、`partial_result=false`。
- metadata `duration_seconds=0.599824`；外层 `/usr/bin/time` 为 `23.65` 秒，包含依赖准备和进程开销，不等同于 metadata 的内部 fetch 观测。
- `raw_rows=664`、`overfetch_rows=388`、`api_request_count=2`。这只描述该 TDX 回溯 API 在本窗口的过取数，不是吞吐或长期性能证明。
- `selection_ready=false`，缺少 `turn/tradestatus/isST/name`，保持补充源边界。

较大的 strict-window CSV 继续经过两个严格 CLI 路径；其命令和退出码都保存在对应 `command.txt`、`exit_code.txt`：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy python \
  skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-opt040-pytdx-Rs2gle/fetch_strict_window/prices.csv \
  --config skills/a-share-selection-strategy/configs/ultra_short_low_price_config.json

PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /tmp/a-share-opt040-pytdx-Rs2gle/fetch_strict_window/prices.csv \
  --output-dir /tmp/a-share-opt040-pytdx-Rs2gle/runner_strict_sufficient \
  --mode generic \
  --config skills/a-share-selection-strategy/configs/ultra_short_low_price_config.json \
  --no-html-report

```

- `strict_validate_sufficient/exit_code.txt` 为 `1`，明确拒绝缺少 `turn/turnover`、`isST` 和 `tradestatus`。
- `runner_strict_sufficient/exit_code.txt` 为 `3`，`selection_failed_reason=validation_failed_before_scoring`，且没有 candidates 或 diagnostics。

另一个独立的短窗口 fetch（`2025-09-01` 至 `2025-09-12`，20 行）只用于 provider merge contract。它与上方 strict-window CSV 不属于同一次输入链路，完整调用来自原始 Agent 会话，退出码和 stderr 保存在 `verified_merge/`：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy python - <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, 'skills/a-share-selection-strategy/scripts')
from lib.gates.incremental_history_merge import validate_provider_merge_contract

metadata_path = Path('/tmp/a-share-opt040-pytdx-Rs2gle/fetch/metadata.json')
metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
validate_provider_merge_contract(metadata)
PY
```

- `verified_merge/exit_code.txt` 为 `1`，明确拒绝 Pytdx 进入 verified selection merge，要求同 `symbol+date` 的 strict companion fields。

Pytdx 的第三方包在本轮输出两条 `SyntaxWarning`，但真实请求与严格边界的退出码保持可区分。不得吞没该上游告警，也不得因此自动换 host 或 source。

## 场景四：外部数据源短窗口观察

Agent 使用 `probe_external_source_stability.py` 执行单轮、有界的 7-source 探针，设置每个子命令 `45` 秒上限，并启用 owner-only 紧凑归档。该顶层命令从原始 Agent 会话恢复；该 `/tmp` 目录没有独立的顶层 `command.txt` 或 exit-code artifact。

```bash
env UV_CACHE_DIR=/tmp/a-share-opt040-sources-BUmUTR/uv-cache /usr/bin/time -p \
  uv run --with pandas --with numpy --with akshare --with yfinance --with baostock \
  --with zzshare --with pytdx python \
  skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
  --output-dir /tmp/a-share-opt040-sources-BUmUTR/runs \
  --summary-output /tmp/a-share-opt040-sources-BUmUTR/summary.json \
  --archive-dir /tmp/a-share-opt040-sources-BUmUTR/archive \
  --iterations 1 \
  --eastmoney-pages 1 --eastmoney-page-size 20 --eastmoney-timeout-seconds 8 \
  --eastmoney-retries 0 --eastmoney-retry-interval-seconds 0 \
  --baostock-universe-lookback-days 7 --baostock-universe-retries 0 \
  --baostock-universe-retry-interval-seconds 0 \
  --akshare-symbols 000001 --akshare-start-date 2026-07-01 --akshare-end-date 2026-07-10 \
  --pytdx-symbols 000001 --pytdx-host 180.153.18.170 --pytdx-port 7709 \
  --pytdx-start-date 2026-07-01 --pytdx-end-date 2026-07-10 \
  --pytdx-timeout-seconds 8 --pytdx-max-pages 1 \
  --yfinance-symbols AAPL --yfinance-start-date 2026-07-01 --yfinance-end-date 2026-07-10 \
  --yfinance-timeout-seconds 8 --command-timeout-seconds 45 \
  --baostock-symbols 000001 --baostock-start-date 2026-07-01 --baostock-end-date 2026-07-10 \
  --baostock-adjust 3 \
  --zzshare-symbols 000001 --zzshare-start-date 2026-07-01 --zzshare-end-date 2026-07-10 \
  --zzshare-timeout-seconds 8 --zzshare-request-interval-seconds 0 \
  --zzshare-limit 100 --zzshare-max-pages 1
```

- summary 记录 7 次 source run 中 5 次通过，`all_sources_all_iterations_passed=false`。该目录没有独立 harness exit-code artifact；严格失败结论来自保存的 required check 失败和各 source result，而不是未落盘的外层退出码。
- Eastmoney spot、Akshare、Pytdx、yfinance 和 ZZShare exit `0`；Baostock universe 与 Baostock history 都因 `command timed out after 45.0 seconds` 得到 return code `124`，没有 metadata 或价格输出。
- Pytdx 仍显式使用 `180.153.18.170:7709`，`selection_ready=false` 且缺少 strict fields；其成功 stderr 有第三方 `SyntaxWarning`。
- summary 保持 `long_term_stability_claim=not_proven` 与 `short_window_claim_boundary=current_window_parameters_network_only`。
- `/tmp/a-share-opt040-sources-BUmUTR/archive` 权限为 `0700`；`archive_manifest.json` 中 20 个 payload 的 SHA-256 均复核一致，且归档不包含 CSV、Parquet 或价格输出。

单轮探针只描述当次参数、网络和远端响应，不证明任何 source 的长期稳定、免费、授权、全 A 完整性或交易可用性。

## 第二轮独立复验

为避免将第一轮的网络失败或 provider 成功泛化为稳定结论，随后重新派发四个隔离 Agent。以下结果来自不同的临时目录和网络窗口，须与前四个场景分开阅读。

### 定向 Baostock：真实取数后被策略阈值严格过滤

第二轮使用以下完整命令，日期范围为 `2025-01-01` 至 `2026-07-17`，并启用 `--fail-on-empty-result --fail-on-skipped`：

```bash
uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --history-source baostock --symbols 000001,600000 \
  --start-date 2025-01-01 --end-date 2026-07-17 \
  --output-dir /tmp/a-share-opt040-rerun-directed-RxTjwIQ2 \
  --history-missing-name-policy query \
  --history-baostock-non-trading-policy reject \
  --fail-on-empty-result --fail-on-skipped
```

- `/tmp/a-share-opt040-rerun-directed-RxTjwIQ2/outer_exit_code.txt` 为顶层 CLI exit `3`；manifest 的总耗时为 `16.633623` 秒。
- `run_manifest.json.steps[]` 的 `returncode` 分别为 `fetch_history=0`、`validate=0`、`score=3`，这些是 runner 子步骤 returncode，不是顶层 CLI exit code。`fetch_history.duration_seconds=8.926207`；`history_metadata.json` 记录 744 行、2 个 symbol、无 failed/empty/invalid/non-trading 行且 `partial_result=false`。
- `score.returncode=3` 对应 `effective_empty_result=true`、`empty_result_reason=threshold_filtered_all`；失败计数为 `max_close:1,min_momentum_score:1,min_trend_score:2,min_turn:2`。
- runner 以 `selection_failed_reason=scoring_failed`、`selection_failed_next_action=inspect_score_stderr_and_fix_input_or_config` 收口，`candidates_output_written=false`、`diagnostics_output_written=false`，并保持 `coverage_class=explicit_symbol_pool`、`full_market_claim_allowed=false`。

这次运行只证明两个明确标的在指定窗口可以取得历史数据且策略阈值会显式拒绝 0 候选；它不是全 A 扫描、候选推荐或策略有效性证明。

### 全 A：仅生成未执行的安全计划

第二轮使用 runner 的 `--plan-only`，显式规划 `baostock_universe` 股票池、`zzshare` 历史源、`--derive-all-spot-symbols` 和 `--max-history-symbols 6000`，未传入 fallback。以下顶层命令从原始 Agent 会话恢复；其外层结果写入 `/tmp/a-share-opt040-rerun-fulla-UC34M0/execution_record.json`，它位于 runner `--output-dir` 的父目录：

```bash
uv run --with pandas --with numpy --with zzshare python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt040-rerun-fulla-UC34M0/pass1 \
  --mode auto --plan-only --fetch-spot baostock_universe \
  --derive-symbols-from-spot --derive-all-spot-symbols \
  --max-history-symbols 6000 --history-source zzshare \
  --start-date 2025-07-21 --end-date 2026-07-20 \
  --history-request-interval-seconds 0.5 \
  --history-max-rate-limit-sleep-seconds 120 \
  --history-max-429-events 3 --history-max-runtime-seconds 7200 \
  --history-limit 1000 --history-max-pages 2 \
  --history-non-trading-policy drop --history-checkpoint-batch-size 100 \
  --history-progress-interval 100 --fail-on-skipped --no-html-report
```

- `/tmp/a-share-opt040-rerun-fulla-UC34M0/execution_record.json` 记录 `runner_exit_code=0`、`elapsed_seconds=23.696282`；manifest 内 `run_duration_seconds=0.639563`。stderr 只记录 `uv` 安装 10 个包耗时 377ms，现有 artifact 不足以把其余外层耗时精确归因给依赖、启动或 runner。
- `status=planned`、`execution_mode=plan_only`、`commands_executed=false`，四个 step 都是 `planned=true`、`executed=false`、`returncode=null`。
- 没有写出 spot、prices、history metadata、候选、诊断或 HTML；`history_artifact_status=not_written`、`full_market_claim_allowed=false`。
- `history_symbols=["<derived_from_spot_snapshot>"]` 是未取数计划的占位符，不是实际股票清单或数量；`coverage_class=spot_derived_limited_pool` 也明确拒绝全 A 声称。

这只验证 Agent 可以安全预览全 A 路径而不触发网络抓取、评分或候选输出，不证明全 A 股票池、增量计划或实际执行已经完成。

### Pytdx：补充 OHLCV 成功，严格闭环继续拒绝

第二轮对固定 `180.153.18.170:7709` 的 `000001` 执行 `2025-07-01` 至 `2026-07-17` 的有界抓取：

```bash
uv run --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001 --start-date 2025-07-01 --end-date 2026-07-17 \
  --output /tmp/a-share-scenario-pytdx-brGIZr/prices.csv \
  --metadata-output /tmp/a-share-scenario-pytdx-brGIZr/metadata.json \
  --host 180.153.18.170 --port 7709 --timeout-seconds 8 \
  --page-size 800 --max-pages 2 --fail-on-fetch-error
```

- `fetch_pytdx_a_share.py` exit `0`，`metadata.json` 记录 255 行、1 个 symbol、`duration_seconds=0.294525`、`partial_result=false`、`selection_ready=false` 和 `strict_fields_same_date_required=true`；外层 time 输出为 6.98 秒。

```bash
uv run --with pandas --with numpy python \
  skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-scenario-pytdx-brGIZr/prices.csv \
  --min-history-rows 120 \
  --config skills/a-share-selection-strategy/configs/prediction_profile_config.json

uv run --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-scenario-pytdx-brGIZr/runner \
  --history-source pytdx --symbols 000001 \
  --start-date 2025-07-01 --end-date 2026-07-17 \
  --history-timeout-seconds 8 --min-history-rows 120 \
  --mode generic --no-html-report

PYTHONPATH=skills/a-share-selection-strategy/scripts \
  uv run --with pandas --with numpy python -c \
  "import json, pandas as pd; from pathlib import Path; from lib.gates.incremental_history_merge import merge_incremental_history; root=Path('/tmp/a-share-scenario-pytdx-brGIZr'); frame=pd.read_csv(root/'prices.csv', dtype={'symbol': str}); meta=json.loads((root/'metadata.json').read_text()); plan={'source':'incremental_history_plan','claim_boundary':'incremental_history_plan_only_not_history_fetch_success','fetch_symbols':['000001'], 'target_end_date':'2026-07-17'}; merge_incremental_history(frame, {}, plan, frame, meta)"
```

- prediction-derived 校验的完整命令和外层码分别保存在 `validate_prediction.command.txt`、`validate_prediction.exit_code.txt`，exit `1`，明确缺少 `prediction/prediction_score` 与 `turn/turnover`；runner 的对应文件为 `runner.command.txt`、`runner.exit_code.txt`，exit `3`，在 validate 阶段因缺少 `turn/turnover`、`isST` 和 `tradestatus` 收口，未写 candidates 或 diagnostics。
- 专门调用 `merge_incremental_history` 的完整命令和外层码分别保存在 `verified_merge_pytdx_contract.command.txt`、`verified_merge_pytdx_contract.exit_code.txt`，exit `1`；其内部 provider contract 校验提示同一 `symbol+date` 必须具有 strict companion fields。另一个以无效 incremental plan 为输入的 merge 调用也 exit `1`，但它只证明 plan 输入无效，不能作为 Pytdx provider 拒绝的证据。
- 上游 `pytdx 1.72` 导入时输出两条 `SyntaxWarning`；fetch 成功、严格字段拒绝和上游警告仍由各自的退出码与 stderr 清楚区分。

这再次证明 Pytdx 可作为显式、有限的 OHLCV 对照源，但不能绕过 prediction、换手和可交易字段门禁进入 verified selection merge。

### 外部源探针：当前窗口 6/7 source 通过

第二轮外部源探针执行一轮 7-source 观察。以下顶层命令从原始 Agent 会话恢复；其最终进程 exit `3` 也仅保留在该会话结果中，没有独立的 `/tmp` 外层 exit-code 文件。Agent 报告每个 child command 设置了 45 秒上限，但该 top-level 参数没有写入 summary；以下只以落盘 summary 和 archive 为准。

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with akshare \
  --with yfinance --with baostock --with zzshare --with pytdx python \
  skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
  --output-dir /tmp/a-share-opt040-rerun-probe-F6eCL5/runs \
  --summary-output /tmp/a-share-opt040-rerun-probe-F6eCL5/summary.json \
  --archive-dir /tmp/a-share-opt040-rerun-probe-F6eCL5/archive \
  --iterations 1 --command-timeout-seconds 45
```

- 顶层 exit `3` 是 Eastmoney strict failure 的收口，不是 7 个 source return code 的替代；`summary.summary` 记录 `total_runs=7`、`passed_runs=6`、`all_sources_all_iterations_passed=false`、`long_term_stability_claim=not_proven`。
- Eastmoney spot 的 source result return code 为 `3`，`partial_result=true`、`raw_items=0`、`output_written=false`；metadata 的原始错误为 `Remote end closed connection without response`，内部 `duration_seconds=6.298831`。
- Baostock universe、Akshare、固定 Pytdx endpoint、yfinance、Baostock history 和 ZZShare 的 source result 均为 return code `0`。Akshare 的 `hist_provider_clean` 是非 required observation failed；Pytdx 成功 stderr 仍含上游 `SyntaxWarning`。
- `/tmp/a-share-opt040-rerun-probe-F6eCL5/archive` 通过 `verify_archive_integrity`：schema `1`、7 条 source record、22 个 payload、目录权限 `0700`，且 archive 内没有 CSV、Parquet 或价格输出。

这只说明上述 provider 在该单次参数和网络窗口的 control-plane 结果，不证明长期可用性、免费额度、授权持续性、全 A 完整性或交易可用性。

## 使用体验反馈

已验证的正向体验：

1. 四条路径都保留了可机读的失败关闭字段。定向 Baostock 和 Pytdx 严格输入失败均未生成候选或诊断，避免旧输出或局部结果被误读为成功。
2. 全 A plan-only 清楚标记 `commands_executed=false`，没有把 `<derived_from_spot_snapshot>` 占位符写成实际 universe。
3. Pytdx 可以落地有限 OHLCV/amount，但严格校验和 verified merge 都拒绝其越权进入选股主路径。
4. 外部源探针的紧凑归档可验证 payload 哈希且不保存价格文件，适合作为短窗口控制面证据。
5. 第二轮定向任务将“历史抓取和校验成功”与“策略阈值全过滤”分开收口，避免把 0 候选误判为行情抓取失败。
6. 第二轮全 A plan-only 保持所有 fetch/validate/score step 为未执行，且没有把计划占位符写成实际股票池。

已验证的体验摩擦：

1. Baostock login 在当前网络下可能长时间无 `PROGRESS:` 事件：定向任务等待约 109 秒，全 A universe 6 次重试等待约 396 秒后才得到完整失败 metadata。
2. probe 顶层 `summary.sources.<source>` 只汇总 `all_passed` 和可选观察项。Baostock 的 required failure 需要下钻 `results[]` 才能看到 return code `124` 和 45 秒超时原因。
3. metadata 内部耗时与外层命令耗时分别有明确语义，但 Agent 需要手工对照多个 artifact 才能区分依赖准备、远端调用和写盘成本。
4. Pytdx 上游 `SyntaxWarning` 会出现在成功请求的 stderr，当前 source 汇总没有直接标示成功但 stderr 非空的情况。
5. 第二轮定向 runner 只在最终失败时向外层 stderr 汇总 step 和 return code；Agent 若要观察 fetch/validate/score 的开始、结束和耗时，仍需等待结束后下钻 manifest。
6. 第二轮 plan-only 的单行 stdout 混合大量 `unknown` 字段。虽然完整字段有审计价值，但首轮判断仍要从很长的一行中提取四个未执行 step、manifest 路径和 placeholder 语义。
7. 第二轮 probe 的顶层 `summary.sources.<source>` 仍只有通过状态和可选观察失败；source return code、首个 required failure、stderr 和耗时需要继续下钻 `results[]` 与 metadata。

## 优化候选

以下是后续独立原子任务的候选，不在本次验收中实施：

1. 为 Baostock universe 增加显式、有界且可披露的总运行时或连接预算，并在每次 login/retry 写无敏感信息的 `PROGRESS:` stderr 事件和 timeout metadata。不得增加自动换源。
2. 让 runner 在 stderr 实时输出无敏感信息的 step start、finish、return code 和 monotonic elapsed，并在严格空结果的顶层错误中附带已存在的 `threshold_failures` 摘要；manifest 继续保留完整审计记录。
3. 为外部源 probe 的顶层 source 汇总增加最新 return code、elapsed、timeout、首个 required failure、metadata 路径和成功但 stderr 非空标记。保留 `observation_failed_checks` 仅表示可选观察失败的语义，避免混淆严格失败与 observation。
4. 在 plan-only 输出增加 `planned_symbol_count=null`、`spot_artifact_required_for_symbol_count=true` 与紧凑四步摘要；完整审计字段继续写入 JSON，避免把占位符误读为实际 symbol 集。
5. 在 Pytdx fetch stdout 和 runbook 中显式展示 `selection_ready=false`、缺失 strict fields 与第三方 `SyntaxWarning` 的边界。警告需保留原文且不能被当作 fetch 失败或联网成功证明。

## 当前门禁边界

本报告不执行全 A 历史长跑、全 A generic 评分、真实 prediction 生成、样本外回测、涨跌停完整规则、券商订单、真实成交、滑点或资金容量门禁。当前真实门禁总状态继续以 [CURRENT-REAL-SCENARIO-GATES.md](../CURRENT-REAL-SCENARIO-GATES.md) 和其引用的 dated evidence 为准。
