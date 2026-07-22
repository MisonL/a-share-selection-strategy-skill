# Multi-Agent Real Scenario Validation 2026-07-22

本报告记录 2026-07-22 由四个隔离 Agent 按 `SKILL.md` 路由完成的真实使用场景复验。它只描述当前机器、当前网络、指定日期窗口和指定 provider 的行为，不构成投资建议，也不证明全 A 历史长跑、全 A 评分、prediction、回测、券商订单、真实成交、长期稳定性、免费额度或授权持续有效。

## 执行边界

- 每个 Agent 仅向独占 `/tmp/a-share-agent-*` 目录写入 artifact，没有修改仓库代码、配置或 Git 状态。
- 所有联网命令显式选择 provider；没有自动 source fallback、自动 host rotation、mock、演示数据、伪造行情、prediction、候选、回测或成功路径。
- 子代理完成后已全部关闭。复核时未发现本轮 `run_today_a_share_selection.py`、Baostock、Pytdx 或 probe 子进程残留；未关闭其他项目的独立 OMP 进程。
- `/tmp` artifact 是易失性证据。本报告不复制价格 CSV、完整 stdout/stderr 或第三方缓存；下面的 SHA-256 只用于复核当前可见 artifact。
- 本报告是体验和失败边界补充 evidence，不升级 `CURRENT-REAL-SCENARIO-GATES.md` 的任何表格状态。

## Artifact Index

| 场景 | 关键 artifact | SHA-256 |
| --- | --- | --- |
| 定向 Baostock 顶层收据 | `/tmp/a-share-opt043-directed-receipt-7rjc7K/top_level_exit_code.txt` | `85bd8d991b3b9f2b96c8e084e55dd374340ae36a6adf19e49a138a27c427df3c` |
| 定向 Baostock manifest | `/tmp/a-share-opt043-directed-receipt-7rjc7K/run/run_manifest.json` | `8fef71a40ec24c5f05614ee56786811a5ca4382e21d6679d4df2fc88582c9e2f` |
| 定向 Baostock summary | `/tmp/a-share-opt043-directed-receipt-7rjc7K/run/summary.json` | `58cd811178919d9dc8806f49d3d60a040fe5fc2a2eeed40fff21162764a4108f` |
| 全 A 股票池 metadata | `/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/spot_metadata.json` | `59b3931e30634812d8b2fbe4d86bb6e423e3d01d7918cc10ff772b13b567511d` |
| 全 A plan-only manifest | `/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/plan-only/run_manifest.json` | `0f971434c3a6a9dc69623441fc950a704be1642df381194fc3afc4beb9868bc1` |
| Pytdx metadata | `/tmp/a-share-agent-pytdx-20260721T233928Z-rc/metadata.json` | `2382f2c40f15769fe3f1da8499856b3589f55fa0e0c91790fb81ed885d2c2f11` |
| 外部源探针 summary | `/tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-summary.json` | `3606935e2434134c1ccec077b458ccd7d0b986c579f2f9fc801c1f843c131217` |
| 外部源探针归档清单 | `/tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-archive/archive_manifest.json` | `29e97f5d738af3063f048783108e094a0ebe30383e54fa052a5f698075741132` |

## 收据完整性复核

在本次 2026-07-22 收口复核时，上表 8 个索引文件均仍存在，重新计算的 SHA-256 全部与表中值一致。以下补充保存的外层收据；复核只读取现有 `/tmp` 文件，没有重跑任何历史联网命令。收据证明指定命令窗口的退出码或耗时，不提升任何真实门禁。

| 场景 | 直接外层收据和值 | SHA-256 |
| --- | --- | --- |
| 定向 Baostock | 退出码已见上表；`/tmp/a-share-opt043-directed-receipt-7rjc7K/stderr.txt` 记录 `/usr/bin/time -p` 的 `real 36.58` | `/tmp/a-share-opt043-directed-receipt-7rjc7K/stderr.txt`: `67c4cafa1e6e8ccb51adcecfdb8d8c9c78ae69ca5f0eac1a6d0d1fec8d01cd82` |
| 全 A universe | `/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/universe.exit_code.txt`: `0`；`/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/universe.timing.txt`: `wall_elapsed_seconds=39.796061` | `/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/universe.exit_code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/universe.timing.txt`: `2476f9370a1069f07b8556c9fbca1a9fbe2760d82f97db912e86f708b047d8c9` |
| 全 A plan-only | `/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/plan_only.exit_code.txt`: `0`；`/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/plan_only.timing.txt`: `wall_elapsed_seconds=19.179164` | `/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/plan_only.exit_code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/plan_only.timing.txt`: `7d9ec0fd3e3f5bfb196dcee81fd74d3a57cc5fa83834dcae7d4ed1ced2dc5127` |
| Pytdx | `/tmp/a-share-agent-pytdx-20260721T233928Z-rc/top_level_exit_code.txt`: `0`；`/tmp/a-share-agent-pytdx-20260721T233928Z-rc/timing.txt`: `real 1.32` | `/tmp/a-share-agent-pytdx-20260721T233928Z-rc/top_level_exit_code.txt`: `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`；`/tmp/a-share-agent-pytdx-20260721T233928Z-rc/timing.txt`: `2e316a157af9adafb6f033116ed6912f51c5ae08f4f47f4839bd6f0420c8816a` |
| 有界七源 probe | `/tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-top_level.exit_code.txt`: `top_level_exit_code=3`；`/tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps.top_level.time.txt`: `real 86.87` | `/tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-top_level.exit_code.txt`: `796903036e1c5f5c195573fe7abc94be8ce073731b6a2c960b2b2040fe3f56b1`；`/tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps.top_level.time.txt`: `bc5b265b798c94232941190c2231397b82945d37b5147d0dfd4f9a94ad39270e` |

## 场景一：定向 Baostock 评分的成功空结果

实际顶层命令使用两个明确标的和有限历史窗口：

```bash
uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-opt043-directed-receipt-7rjc7K/run \
  --mode generic --history-source baostock --symbols 000001,600000 \
  --start-date 2025-01-01 --end-date 2026-07-21 --no-html-report
```

- 保存的顶层 exit code 是 `0`；外层 `time` 为 `36.58` 秒，包含临时依赖准备。runner `run_duration_seconds=12.705925`。
- `fetch_history`、`validate`、`score` 子步骤 return code 都是 `0`，耗时依次为 `6.708277`、`2.186468`、`3.560830` 秒。
- `history_metadata.json` 记录 `rows=748`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`partial_result=false`，并保留 `baostock_external_api_not_broker_order_or_full_market_proof` 边界。
- 最终是成功空结果：`effective_empty_result=true`、`empty_result_reason=threshold_filtered_all`、`candidate_rows=0`、`diagnostic_rows=2`。`candidates.csv` 和 `diagnostics.csv` 都已写出，`selection_failed_reason` 为空。
- 该任务是 `execution_path=history_fetch_explicit_symbols_generic`、`coverage_class=explicit_symbol_pool`，且 `full_market_claim_allowed=false`。它不是全 A 扫描、候选推荐或投资结论。

## 场景二：全 A 股票池与 plan-only 预检

先通过公开 Baostock universe CLI 获取股票池，再把已落地快照传给公开 runner 的 `--plan-only` 路径：

```bash
uv run --with baostock python \
  skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py \
  --output /tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/spot.csv \
  --metadata-output /tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/spot_metadata.json \
  --snapshot-date 2026-07-22 --lookback-days 3 --retries 0 \
  --retry-interval-seconds 0 --fail-on-partial

uv run --with pandas --with numpy python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/plan-only \
  --mode generic --spot-input /tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/spot.csv \
  --derive-symbols-from-spot --derive-all-spot-symbols --max-history-symbols 5200 \
  --history-source baostock --start-date 2025-07-01 --end-date 2026-07-21 \
  --history-names-input /tmp/a-share-agent-full-a-preflight-20260722T074754-hUUnoU/spot.csv \
  --history-missing-name-policy fail --history-baostock-non-trading-policy reject \
  --plan-only --no-html-report
```

- 两个顶层命令 exit 都是 `0`；外层单调耗时分别为 `39.796061` 和 `19.179164` 秒。对应的内部业务耗时为 `16.751347` 和 `11.244018` 秒；stderr 显示首次 `uv` 依赖准备参与了外层耗时。
- universe metadata 记录 `real_market_data=true`、`symbol_count=5200`、`partial_result=false`、`fetch_error_count=0`、`date_fallback_used=true`，请求日 `2026-07-22` 显式回看并解析到 `2026-07-21`。其边界仍是 `baostock_universe_snapshot_not_realtime_spot_or_full_market_proof`。
- plan-only manifest/summary 记录 `status=planned`、`execution_mode=plan_only`、`commands_executed=false`、`history_artifact_status=not_written`、`coverage_class=spot_derived_limited_pool`、`full_market_claim_allowed=false`，三个步骤均为 `planned=true`、`executed=false`、`returncode=null`。
- 没有执行历史抓取、校验、评分或 HTML 输出，不能作为全 A 历史、全 A 选股或实时行情证明。

## 场景三：Pytdx 补充源严格边界

实际调用公开 Pytdx CLI，仅使用默认项目 endpoint 和两个固定标的：

```bash
uv run --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001,600000 --start-date 2026-07-13 --end-date 2026-07-17 \
  --output /tmp/a-share-agent-pytdx-20260721T233928Z-rc/prices.csv \
  --metadata-output /tmp/a-share-agent-pytdx-20260721T233928Z-rc/metadata.json \
  --timeout-seconds 10 --fail-on-fetch-error
```

- 顶层 exit 为 `0`，外层耗时 `1.32` 秒，metadata `duration_seconds=0.236282`。
- 产物有 10 行、2 个标的；`failed_symbols=[]`、`empty_symbols=[]`、`possibly_truncated_symbols=[]`、`partial_result=false`。
- metadata 明确记录 `selection_ready=false`、`missing_provider_fields=["turn","tradestatus","isST","name"]`、`strict_fields_same_date_required=true`、`name_value_policy=blank_missing_provider_name`，并限制可合并字段为 `open/high/low/close/volume/amount`。
- 因此这只证明当前默认 endpoint 的有限 OHLCV/amount 补充观察，不证明 strict selection、verified merge、全 A 主历史、可交易性、长期稳定性或投资结果。

## 场景四：有界外部源诊断

实际 probe 运行所有当前注册 source，但使用单轮和每子命令 5 秒上限：

```bash
uv run --with pandas --with numpy --with baostock --with pytdx python \
  skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
  --output-dir /tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-probe-output \
  --summary-output /tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-summary.json \
  --archive-dir /tmp/a-share-agent-probe-20260722T073620-qQlCXO/with-deps-archive \
  --iterations 1 --command-timeout-seconds 5 \
  --baostock-universe-lookback-days 7 --baostock-universe-retries 0 \
  --pytdx-symbols 000001 --pytdx-start-date 2026-07-20 \
  --pytdx-end-date 2026-07-21 --pytdx-timeout-seconds 4 --pytdx-max-pages 1
```

- 顶层 exit 是 `3`，外层耗时 `86.87` 秒，包含临时依赖解析和 7 个 source 串行探测；不能将它当作 Pytdx 单次或任何 provider 的实际吞吐。
- `pytdx` 子命令 return code 为 `0`，`latest_command_elapsed_seconds=4.428204`、`latest_command_timed_out=false`。成功 stderr 中仍有第三方 `SyntaxWarning`，但其未被当成严格门禁失败。
- Baostock universe、Baostock history 和 yfinance 均为 `returncode=124`、`latest_command_timed_out=true`，在 5 秒上限内未写 metadata；这只表示本次参数和超时预算下未完成。
- 所有 source 的 `observation_failed_checks={}`，required failure 与 optional observation 保持分离。summary 保持 `long_term_stability_claim=not_proven` 和 `short_window_claim_boundary=current_window_parameters_network_only`。
- `verify_archive_integrity` 成功复核 owner-only compact archive 的 17 个 payload；归档没有价格 CSV 或 Parquet。

## 体验反馈与可验证改进项

1. 全 A `plan-only` 的 fetch command 内联 5,200 个代码，长度约 37,030 字符，manifest 约 118 KB。当前实现仅为 ZZShare 的非 plan-only 路径生成 `history_symbols.txt`；可评估让 plan-only 也落地并引用 symbol 文件，降低人工审阅与日志截断风险。该项只影响计划 artifact 可读性，不应改变执行命令或声明边界。
2. `plan-only` summary 已保留 `spot_output` 和 `spot_rows`，但复制到 output directory 的 spot metadata 未写出，导致 `spot_metadata={}`、`real_market_data=unknown`。可评估投影输入 spot metadata 路径、哈希和有限 provenance 字段，让计划 artifact 解释真实输入来源；不得将该投影误写成全 A 历史或选股完成。
3. probe 当前固定运行 7 个 source，无法只诊断指定 source；这使临时依赖、无关 provider 与严格失败共同放大外层耗时。可评估显式、可重复的 source 过滤参数及选后依赖预检，同时维持默认无自动 fallback、无 host rotation 和长期稳定性边界。
4. source summary 已有 `latest_metadata_output`，但没有明确的 file/missing/symlink 状态。可评估加入脱敏状态字段，减少失败时用户必须下钻 `results[]` 的成本。

这些建议来自本轮 artifact 的可观测性和使用体验，不是已确认的正确性、数据安全或策略缺陷；实施前仍需建立独立原子任务和回归测试。
