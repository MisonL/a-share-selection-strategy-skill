# Multi-Agent Real Scenario Validation 2026-07-21

本报告记录 2026-07-21 由四个隔离 Agent 按 `SKILL.md` 路由完成的真实任务场景验收。它只记录当前机器、当前网络、指定日期窗口和指定 provider 的行为，不构成投资建议，也不证明全 A 长跑、实时行情、真实 LightGBM prediction、回测收益、券商订单、真实成交、长期稳定性、免费额度或授权持续有效。

## 执行边界

- 每个 Agent 只使用独占的 `/tmp/a-share-agent-*` 目录写运行产物，没有修改仓库代码、配置或 Git 状态。
- 场景开始和结束时工作树都只有预先存在的 `M tasks.csv`，没有新增业务改动、暂存项或未跟踪文件。
- 所有联网命令显式选择 provider。没有自动 source fallback、自动 host 轮换、伪造行情、prediction、候选、回测或成功路径。
- 本报告不复制价格 CSV、HTML 或原始缓存。`/tmp` 是易失性原始证据，复核时应先核对下方 SHA-256，再读取对应 JSON、stdout 和 stderr。

## 产物索引

| 场景 | 关键 artifact | SHA-256 |
| --- | --- | --- |
| 定向 Baostock 失败关闭 | `/tmp/a-share-agent-targeted-MWCn7lww/run/history_metadata.json` | `d0885d1112938fe132344ac9da8483b8c14f22f7a83c72bbd1dfd84e750f8187` |
| 定向 Baostock 恢复计划 | `/tmp/a-share-agent-targeted-MWCn7lww/retry_plan_from_failure.json` | `218326c197f09acca0705219e740d28262b7e5b79e955fade58901192fc212e2` |
| 全 A 股票池预检 | `/tmp/a-share-agent-fulla-preflight-aCj9jq/spot_metadata.json` | `7bfa9a0ac7cc2114337a4b5a071dad5427365322a6516090501caf2265cf5467` |
| 全 A plan-only manifest | `/tmp/a-share-agent-fulla-preflight-aCj9jq/plan-only/run_manifest.json` | `12bf034010eb4752ad9a975528949520bb33a4942b531beb62400acc63ca243c` |
| 完整 Baostock 定向恢复 | `/tmp/a-share-agent-recovery-ktdYDy/run/history_metadata.json` | `204aa295923778a3f7fdcf7b70b224486d19080abb36ac0be58993235736871c` |
| 完整 Baostock 空重试计划 | `/tmp/a-share-agent-recovery-ktdYDy/retry_plan.json` | `5ae55442b126171d6f72729a43fe817946ad3153f303c0a83e70721040a12551` |
| Pytdx 补充源边界 | `/tmp/a-share-agent-pytdx-dmYQoM/metadata.json` | `0bebc7fd4c1346ee0aa725b1e8c2808c005b38fc632f4a22c59b025aec3ef04d` |

## 场景一：定向 Baostock 失败关闭和失败恢复

实际命令中的临时路径以 `$RUN` 表示：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$RUN/pycache" \
  UV_CACHE_DIR="$RUN/uv-cache" XDG_CACHE_HOME="$RUN/xdg-cache" \
  uv run --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/run" --mode generic --history-source baostock \
  --symbols 000001,600000,300750 \
  --start-date 2025-12-01 --end-date 2026-07-21 \
  --fail-on-skipped --html-report-language zh
```

- 外层命令 exit `3`，墙钟 `53` 秒；`summary.json.run_duration_seconds=25.905141`。
- `history_metadata.json` 为真实 Baostock 数据，`rows=306`、`symbol_count=2`、`partial_result=true`。
- `000001` 和 `600000` 各有 153 行，最新日期为 `2026-07-20`；`300750` 的 provider 错误为 `用户未登录`，同时进入 `failed_symbols` 和 `empty_symbols`。
- runner 以 `selection_failed_reason=fetch_history_failed` 失败关闭，`candidate_rows=0`、`diagnostic_rows=0`，没有把部分结果作为候选或评分结果继续使用。
- `coverage_class=explicit_symbol_pool` 且 `full_market_claim_allowed=false`，边界为 `explicit_symbols_not_full_market_scan`。

同一真实失败 artifact 随后由 recovery CLI 处理：

```bash
uv run --python 3.11 python \
  skills/a-share-selection-strategy/scripts/prepare_history_retry_symbols.py \
  --selected-symbols "$RUN/run/selected_symbols.json" \
  --history-metadata "$RUN/run/history_metadata.json" \
  --output "$RUN/retry_plan_from_failure.json" \
  --symbols-output "$RUN/retry_symbols_from_failure.txt"
```

该命令 exit `0`，只生成 `300750` 一个 retry symbol，保留两个干净已选 symbol。计划的 `claim_boundary=retry_plan_only_not_full_market_completion_or_history_fetch_success`，它只给出显式重跑对象，不把局部成功写成全 A 完成。

## 场景二：全 A 严格路径预检

先获取真实 Baostock 沪深 A 股股票池快照：

```bash
uv run --with baostock python \
  skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py \
  --output "$RUN/spot.csv" --metadata-output "$RUN/spot_metadata.json" \
  --retries 5 --retry-interval-seconds 1 --lookback-days 7 --fail-on-partial
```

- exit `0`，外层墙钟约 `13` 秒，metadata `duration_seconds=12.456305`。
- `symbol_count=5199`、`partial_result=false`、`fetch_error_count=0`。
- 请求日为 `2026-07-21`，解析为 `2026-07-20`，`date_fallback_used=true`。
- 边界仍为 `baostock_universe_snapshot_not_realtime_spot_or_full_market_proof`，它不是实时 spot 或全 A 选股完成证明。

在该真实 snapshot 上只运行安全的计划预检：

```bash
uv run --with pandas --with numpy python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/plan-only" --mode generic --spot-input "$RUN/spot.csv" \
  --derive-symbols-from-spot --derive-all-spot-symbols \
  --max-history-symbols 6000 --history-source baostock \
  --start-date 2025-07-01 --end-date 2026-07-20 \
  --history-names-input "$RUN/spot.csv" --history-missing-name-policy fail \
  --history-baostock-non-trading-policy reject --plan-only --no-html-report
```

- exit `0`，外层墙钟约 `5` 秒，`summary.json.run_duration_seconds=1.929499`。
- 计划中的 history symbol 为 `5199`，由调用者显式上限 `6000` 约束。
- `status=planned`、`commands_executed=false`；`fetch_history`、`validate` 和 `score` 都是 `planned=true`、`executed=false`。
- 没有生成 history metadata、候选或 diagnostics，`full_market_claim_allowed=false`，边界为 `spot_derived_explicit_limit_requires_artifact_review`。

因此该场景只证明全 A 股票池和安全计划构造可用。它没有执行 5,199 symbol 历史抓取、校验或评分，不能替代已有的全 A dated evidence，也不能形成全市场候选或收益声明。

## 场景三：完整定向抓取后的空重试路径

真实 runner 和 recovery CLI 都显式使用 Baostock：

```bash
uv run --python 3.11 --with pandas --with numpy --with baostock python \
  skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/run" --mode generic --history-source baostock \
  --symbols 000001,600000,300750 \
  --start-date 2025-01-01 --end-date 2025-12-31 --no-html-report
```

```bash
uv run --python 3.11 python \
  skills/a-share-selection-strategy/scripts/prepare_history_retry_symbols.py \
  --selected-symbols "$RUN/run/selected_symbols.json" \
  --history-metadata "$RUN/run/history_metadata.json" \
  --output "$RUN/retry_plan.json" --symbols-output "$RUN/retry_symbols.txt"
```

- runner exit `0`，外层墙钟约 `17` 秒，`summary.json.run_duration_seconds=15.198227`。
- 历史产物为真实数据，`rows=729`、`symbol_count=3`、`failed_symbols=[]`、`empty_symbols=[]`、`partial_result=false`。
- runner 正确区分了成功空结果：`effective_empty_result=true`、`empty_result_reason=threshold_filtered_all`、`diagnostic_rows=3`、`candidate_rows=0`。
- recovery CLI exit `0`，耗时小于 1 秒，`retry_symbol_count=0`、`clean_selected_symbol_count=3`。

这证明阈值筛空候选没有被错误地加入历史抓取重试队列。它仍是 `explicit_symbol_pool`，`full_market_claim_allowed=false`，不能外推为全 A 完成。

## 场景四：Pytdx 补充源严格边界

真实 Pytdx 请求显式固定已验证 endpoint，没有 host 轮换或其他 provider：

```bash
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 \
  uv run --with pandas --with numpy --with pytdx python \
  skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001,600000 --start-date 2025-09-01 --end-date 2026-07-17 \
  --output "$RUN/prices.csv" --metadata-output "$RUN/metadata.json" \
  --host 180.153.18.170 --port 7709 --timeout-seconds 10 \
  --page-size 800 --max-pages 2 --fail-on-fetch-error
```

- fetch exit `0`，外层计时 `1.70` 秒。
- `rows=422`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`possibly_truncated_symbols=[]`、`partial_result=false`。
- `token_configured=false`、`selection_ready=false`，缺少 `turn`、`tradestatus`、`isST`、`name`。
- `source_claim_boundary=pytdx_external_fetch_not_turnover_tradability_or_stability_proof`。

随后对同一真实 CSV 运行三项严格检查：

| 检查 | exit | 结果 |
| --- | ---: | --- |
| `validate_ohlcv.py --config ultra_short_low_price_config.json` | `1` | 明确拒绝缺少 `turn` 或 `turnover`、`isST`、`tradestatus` |
| `validate_provider_merge_contract(metadata)` | `1` | 明确拒绝 Pytdx 进入 verified selection merge，要求同 symbol/date 的 strict companion fields |
| `run_today_a_share_selection.py --prices-input ... --config ultra_short_low_price_config.json` | `3` | 在 validate 步骤失败关闭，`selection_failed_reason=validation_failed_before_scoring` |

这证明 Pytdx 当前可作为小范围 OHLCV/amount 补充观察源，但不能用于 strict selection、verified merge、全 A 主历史路径、prediction-derived 输入或可交易性证明。

## 收集到的反馈

1. Baostock 的 provider 级故障可以只影响一个 symbol。runner 没有让局部历史数据继续进入评分，recovery plan 也只隔离失败 symbol，失败关闭和恢复边界均符合预期。
2. 成功的零候选与抓取失败被区分。`threshold_filtered_all` 会保留为有效空结果，而不是触发无意义的 history retry。
3. 全 A 股票池预检和 plan-only 明确展示了后续历史抓取计划，但没有伪造全 A history、评分、prediction、回测或交易已完成。
4. Pytdx 的字段门禁正确阻止其越权进入严格选股。当前成功 fetch 的 metadata 没有 `duration_seconds`，只能从外层 `/usr/bin/time` 得到 1.70 秒，这是可观测性缺口，不是数据正确性或严格门禁缺口。

## 未关闭的外部门禁

- 本轮没有重新执行全 A 历史长跑、全 A generic 评分、真实 prediction 生成、样本外回测、涨跌停完整规则、券商订单、真实成交或资金容量门禁。
- 一次成功或失败联网请求不证明任一 provider 的长期稳定性、免费性、授权、额度或未来可用性。
- 当前真实门禁总状态应继续以 `CURRENT-REAL-SCENARIO-GATES.md` 和其中引用的已验证范围为准。本报告仅为补充验收 evidence，不升级任何全局真实门禁状态。
