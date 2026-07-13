# Full A Workflow Bottleneck Evidence 2026-07-09

本报告记录 2026-07-09 本地一次全 A 工作流观察证据。它用于工程复盘和门禁说明，不构成投资建议，不证明真实 prediction、真实回测收益或券商成交。

## 运行范围

- Run dir: `/tmp/a-share-full-market-20260709T094044`
- Universe source: eastmoney spot
- History source: zzshare `daily(fields=all)`
- Scoring mode: generic technical scoring
- Boundary: 本轮只证明这些 artifact 的执行事实和瓶颈位置，不证明未来稳定性、真实收益或成交能力。

## 关键结果

| 阶段 | 证据 |
| --- | --- |
| Spot universe | 5536 symbols, duplicates=0 |
| zzshare 冷启动历史 | 5133.25s, requested=5536, rows=1873891, symbol_count=5242 |
| zzshare 异常分类 | failed=0, empty=294, possibly_truncated=0, partial_result=true |
| checkpoint resume | checkpoint skipped=5536，恢复轮可复用已完成分片 |
| validate 短历史 | short_history_symbols=56 |
| clean pool | 5186 symbols, rows=1870133 |
| 最终评分 | 184.63s, candidates=49, diagnostics=5186 |
| HTML report | `/tmp/a-share-full-market-20260709T094044/final/report.html` |

## 瓶颈判断

主要瓶颈是外部逐 symbol 历史 I/O，而不是本地评分：

- zzshare 冷启动约 85.6 分钟。
- clean 后最终评分约 3.1 分钟。
- spot universe 获取和本地 clean/validate 相比历史 I/O 更轻。

## 当前优化方向

1. 保持 zzshare 作为当前全 A 历史主路径，但不默认提高并发；既有 2/6 并发测试出现 429 或 timeout 风险。
2. 用 checkpoint resume 降低中断重跑成本，并校验 completed 记录对应的 part 文件和 symbol 是否真实存在。
3. 用 `prepare_clean_history_pool.py` 将 `empty_symbols` 和短历史清单转为 clean `prices.csv`、metadata 和剔除报告，避免手工删行。
4. 用 `prepare_incremental_history_plan.py` 识别缺失或过期 symbol，日常任务优先跑增量计划，不默认全量冷启动。
5. 保持数据源按需安装：baostock universe 主股票池，eastmoney spot 只补实时展示字段，zzshare 主历史，baostock 小范围核验，akshare A 股或港股补充，pytdx no-token 日线补充，yfinance 海外 ticker 补充。

## 同日短窗口数据源探针补充

- Run dir: `/tmp/a-share-source-probe-20260709T235606`
- Probe command: `probe_external_source_stability.py --iterations 1`
- Result: total_runs=7, passed_runs=6, long_term_stability_claim=not_proven
- Failed required source gate: `eastmoney_spot` returned `RemoteDisconnected` for page 1, raw_items=0, output_written=false, metadata_output_written=true, partial_result=true.
- Passed current-window gates: `baostock_universe`, `baostock` history, `pytdx`, `yfinance`, and `zzshare`.
- Observation-only warning: `akshare` fell back from `stock_zh_a_hist` to `stock_zh_a_daily`; this remains usable as a supplement but not as main-interface stability proof.
- zzshare note: even the one-symbol probe logged a 429 retry before succeeding, so default full-A history concurrency remains conservative.

Decision impact:

- `baostock_universe` stays the full-A symbol pool source; this probe returned 5202 filtered沪深 A 股 symbols on 2026-07-09.
- `eastmoney` remains realtime display enrichment only. Current failure must be disclosed and must not block the `baostock_universe + zzshare_history` main path.
- `pytdx` is a usable no-token history supplement in this environment, but it lacks `turn/tradestatus/isST/name` and carries the package/license boundary already recorded in metadata.
- Short-window success for any provider does not prove future stability, free quota, broker execution, prediction quality, or backtest收益.

## 最终 prices 过滤失败复跑

- Run dir: `/tmp/a-share-full-market-20260709T094044/final_refilter_metadata_fix`
- Command scope: clean `prices.csv` + `baostock_universe` spot，显式 `--filter-prices-to-spot-universe --min-symbol-latest-date 2026-07-09`
- Result: exit_code=2, elapsed=13.79s, `run_error_type=PricesFilterError`
- Root signal: clean prices latest date was older than `2026-07-09`; stale-date filter removed all 5186 clean symbols.
- Observability fix verified: `prices_filter.json`, `summary.json`, and `run_manifest.json` were written; all three disclose `prices_filter_output_written=false`, `prices_filter_failure_reason=all_price_symbols_removed`, `prices_filter_input_symbol_count=5186`, `prices_filter_kept_symbol_count=0`, `prices_filter_removed_symbol_count=5186`, and `prices_filter_removed_stale_symbol_count=5186`.

Decision impact:

- The runner should continue to fail fast when all prices are filtered out; it must not silently relax `--min-symbol-latest-date`.
- Final full-A `prices-input` reruns should set `--min-symbol-latest-date` to the verified target end date of the clean history pool, or first run `prepare_incremental_history_plan.py` and refresh stale symbols.

## 最终 prices 匹配日期复跑

- Run dir: `/tmp/a-share-full-market-20260709T094044/final_refilter_20260708`
- Command scope: clean `prices.csv` + `baostock_universe` spot，显式 `--filter-prices-to-spot-universe --min-symbol-latest-date 2026-07-08 --no-html-report`
- Result: exit_code=0, elapsed=90.55s, `status=completed`
- Output scope: `prices_rows=1861259`, `diagnostic_rows=5157`, `candidate_rows=48`
- Filter signal: `prices_filter_input_symbol_count=5186`, `prices_filter_kept_symbol_count=5157`, `prices_filter_removed_symbol_count=29`, `prices_filter_removed_stale_symbol_count=28`
- Boundary: `coverage_class=local_input`, `full_market_claim_allowed=false`，这是基于既有 clean artifact 的复跑，不是新一轮联网全 A 历史抓取。
- Log hygiene fix verified from the same manifest: stdout `input_requested_symbols` now keeps a 20-symbol sample and appends `__truncated__=5516,__total__=5536`; full list remains in JSON metadata.

## 2026-07-10 再次全 A 复跑

- Run dir: `/tmp/a-share-full-market-rerun-20260710T005624`
- Baostock universe: requested_snapshot_date=2026-07-10, resolved_snapshot_date=2026-07-09, date_fallback_used=true, symbol_count=5202, duration_seconds=40.250868
- Incremental plan: target_end_date=2026-07-09, fetch_symbol_count=5202, up_to_date_symbol_count=0, stale_symbol_count=5202
- Final as-of run: `/tmp/a-share-full-market-rerun-20260710T005624/final_asof_20260708`
- Final as-of result: status=completed, prices_rows=1861259, diagnostic_rows=5157, candidate_rows=48, spot_matched_symbols=5157, elapsed=140.98s
- Final as-of boundary: full_market_claim_allowed=false, full_market_claim_boundary=local_prices_input_not_full_market_scan
- Output size: filtered prices.csv is about 520MB; report.html is about 718KB

Decision impact:

- The current strict fresh target cannot be reported as complete without refreshing 5202 stale history symbols to 2026-07-09.
- The 2026-07-08 clean-pool scoring result is useful as an auditable as-of run, but it must not be described as a 2026-07-09 or 2026-07-10 fresh full-A scan.
- The cheap incremental plan is now the best first gate before any daily full-A task. If it reports every symbol stale, the bottleneck is history refresh, not ranking or HTML.
- After the P1 plan enhancement, the same 5202-symbol case reports history_refresh_mode=delta_only, delta_fetch_symbol_count=5202, full_fetch_symbol_count=0, suggested_fetch_start_date=2026-06-26, suggested_fetch_end_date=2026-07-09. This is a plan hint only, not proof that delta fetch has completed.
- After the P1 merge enhancement, `prepare_clean_history_pool.py` can explicitly merge `--incremental-plan`, `--incremental-prices`, and `--incremental-metadata` before cleaning. It rejects incomplete incremental arguments, failed/empty/truncated/unprocessed or rate-limit-exhausted delta metadata, missing planned symbols, stale delta rows, and rows beyond target_end_date. This closes the artifact-level plan -> fetch -> merge loop without adding another public script.
- After the P2 local I/O enhancement, final clean-price reruns can explicitly add `--prices-filter-output-format parquet`. When local prices filters are enabled, the runner reads the original landed prices artifact, writes the filtered run-scoped prices to `prices.parquet`, and passes that file to validate/score. This reduces repeated filtered CSV rewrites but does not solve the external history refresh bottleneck.

## Claude 只读复核摘要

Claude Code 2.1.179 was run in safe-mode, read-only review mode for the current repository and the 2026-07-10 rerun evidence. Its recommendations were consistent with local measurements:

1. High priority: add a real daily incremental history path. The current stale-symbol plan identifies the work, but the data path still tends toward a large per-symbol history refresh. The desired direction is explicit incremental fetch and merge, with claim boundaries that say the plan itself is not a successful history fetch.
2. High priority: profile and optimize scoring. The 2026-07-10 final as-of run spent 124.87s user CPU inside the local final round, so score/validate/report timing needs first-class visibility before larger refactors.
3. Medium priority: evaluate Parquet and avoid unnecessary 520MB CSV rewrites. This is lower priority than history refresh but useful for repeated local final rounds.
4. Medium priority: improve optional spot enrichment field coverage. Baostock universe is correct for symbol pool, but it does not fill industry, market_cap, pe_ttm, or pb_lf.
5. Do not weaken claim boundaries. `full_market_claim_allowed=false` and `local_prices_input_not_full_market_scan` are correct for clean-pool scoring reruns.

## 优化实施方案

P0 observability:

- Record real step duration for runner subprocess steps and expose it through `run_manifest.json.steps[]` and `summary.json.step_summary[]`.
- Keep plan-only step summaries unchanged unless a real duration exists.
- Add focused tests for duration propagation.

P1 incremental history:

- Implemented `prepare_incremental_history_plan.py` delta-only window hints: `history_refresh_mode`, delta/full counts, start dates, target end date, and `next_action`.
- Implemented verified incremental merge as an explicit `prepare_clean_history_pool.py` option set. The public script count does not grow; internal helper modules stay under the file-length limit and fail fast when executed directly.
- Merge output records `incremental_merge_*` metadata and `clean_history_report.json.incremental_merge`, including target date, planned symbols, base/delta/merged rows, and replaced overlap rows.
- Preserved Debug-First behavior: plan generation is not fetch success; delta metadata must prove successful output before merge; stale, unexpected, failed, or incomplete delta artifacts fail the command.

P2 local I/O:

- Implemented an explicit `--prices-filter-output-format {input,csv,parquet,pq}` runner option for local prices filters.
- Default remains `input`, preserving the prior CSV/PQ suffix behavior.
- Explicit `parquet` skips the run-scoped source CSV copy, writes filtered prices to `prices.parquet`, records `prices_filter_output_format` and `prices_filter_output_prices` in manifest/summary/stdout/CSV provenance, and clears stale `prices.csv/.parquet/.pq` outputs between runs.
- Verified with focused runner tests covering Parquet filtered output, default CSV filtering, stale alternate price cleanup, and PQ input preservation.

P3 scoring:

- Implemented explicit `score_candidates.py --profile-output` and runner `--score-profile` observability. The profile records stage timings and row counts, remains disabled by default, and is removed with stale score outputs on failure.
- Added CLI and runner tests proving the default artifact surface is unchanged, explicit profiling writes `score_profile.json`, and strict failures cannot leave a stale profile behind.
- Re-ran the retained 2026-07-08 as-of full-A scoring input without network access: 1,861,259 rows, 5,157 scored symbols, 48 candidates, and 5,157 diagnostics. The measured score CLI duration was 58.94s: dependency loading 1.64s, prices input loading 6.32s, scoring 50.73s, candidate write 0.01s, and diagnostics write 0.21s.
- Repeated the same current-code run with profiling disabled. Candidate and diagnostic CSV files were byte-identical to the profiled run, with matching SHA-256 values. The older runner-produced CSVs contain additional runner provenance columns, but every shared scoring column also matched row by row.
- `cProfile` identified three avoidable Python-level loops: provenance aggregation scanned six mostly constant columns row by row, latest gate fields built one Series per symbol, and spot symbol preference scanned every repeated history row. Replaced them with duplicate reduction and vectorized latest-row extraction while preserving the existing normalization and last-row contracts.
- The isolated provenance benchmark on the same 1,861,259 rows reduced aggregation from 6.24s to 0.286s, about 21.8x, with equal output. After all three low-risk changes, the same end-to-end profiled score run completed in 34.63s, with 6.12s input loading and 26.88s scoring. Candidate and diagnostic SHA-256 values remained identical to the pre-optimization current-code baseline.
- The 58.94s and 34.63s values are individual local runs, not a multi-run statistical benchmark. They establish a large measured improvement and strict output parity for this retained artifact, but not a universal runtime guarantee.
- This remains an auditable 2026-07-08 as-of replay. It is not a fresh 2026-07-09, 2026-07-10, or 2026-07-11 full-A scan and does not prove external history refresh performance.
- Consider precomputed per-symbol indicators or explicit opt-in parallel workers only after parity tests prove candidates, diagnostics, ordering, and failure behavior are unchanged.
- Keep default behavior single-path and reproducible until measured speedup is proven.

P4 enrichment:

- Treat Eastmoney spot fields as optional display enrichment only.
- Do not let enrichment fields participate in core scoring unless a separate scored profile and tests are added.

P5 verification:

- Run focused tests after each phase, then `validate_skill_changes.py`.
- Keep diff check and pycache scan clean.
- Re-run a near-real full-A as-of final round and compare summary fields before claiming performance improvement.

## 不可外推项

- 不证明 eastmoney 或 zzshare 长期稳定。
- 不证明所有 A 股交易日、停复牌、ST、退市和新股状态已由单一数据源完整覆盖。
- 不证明 LightGBM prediction、真实策略回测收益或未来表现。
- 不证明券商订单、真实成交、滑点或容量。
- 不证明本轮候选股适合直接交易。

## 2026-07-12 闭环优化和复核

本节记录基于前述真实瓶颈证据完成的实现闭环。它证明本地代码、契约和离线门禁通过，不代表在 2026-07-12 重新完成了一次当日全 A 历史刷新或真实选股。

已完成：

1. 增量计划把 `rows <= 0` 或 `date_max` 为空的 symbol 归入 `empty_or_missing_history/full`，有效过期历史归入 `delta`，并输出可守恒、可恢复的稳定 buckets。
2. `execute_incremental_history_plan.py` 按 bucket 使用单一显式 provider，分别落盘状态、metadata 和 checkpoint；verified merge 继续拒绝 failed、empty、truncated、缺 symbol、未达 target 或越界日期的数据。
3. zzshare 429 控制具备 `Retry-After`、全局 sleep/event/runtime 预算和耗尽原因；耗尽时先 flush checkpoint，再以 partial/nonzero 结果退出，不自动切源。
4. 过滤后 Parquet 写入带 SHA-256、大小、mtime、行数、symbol/date 范围、过滤契约和原始 provenance 的 sidecar；缺失、篡改或 stale 会显式失败。
5. Baostock history 可复用 universe 的 `symbol/name`，只查询缺失名称，并显式支持 `reject/drop/keep` 非交易行策略。
6. Pytdx 近期窗口首请求按日期跨度自适应缩小，后续按实际返回行数推进 offset，并记录 request/raw/output/overfetch。一次真实探针抓取 `000001` 的 `2026-07-09` 至 `2026-07-10`：请求 16 行、返回 16 行、输出 2 行、1 次 API 请求、约 7.5 秒、窗口完整。该结果只证明本次路径；Pytdx 仍缺 `turn/tradestatus/isST/name`，不能独立进入 strict 评分 merge。
7. runner、计划、bucket fetch、merge、filter、validate、score 和 report 已补充耗时、吞吐、retry、sleep、cache/reuse、raw/output 等观测字段。复用 bucket 的本轮耗时为 0，原始抓取成本另行保留。
8. 当前 `scripts/` 树共有 113 个 Python 文件；根层 33 个，其中 29 个 public CLI、4 个 compatibility wrapper，内部 80 个按领域分层。Agent 默认入口仍只有 `validate_ohlcv.py`、`score_candidates.py` 和 `run_today_a_share_selection.py`。超过 800 行的声明式 HTML、summary 投影和 runner 编排文件已由动态文档测试锁定并记录职责豁免，不按行数机械拆分。

本地验证：

- `python3 validate_skill_changes.py`: exit 0。
- JSON、YAML agent manifest、compileall、Skill quick_validate、tracked/staged diff check、文本冲突标记、secret、`__pycache__` 共 9 层门禁通过。
- 完整 `unittest discover`: 680 tests，全部通过；单次本机耗时会随缓存和系统负载变化，不作为稳定性能承诺。
- 聚焦回归还覆盖 Baostock/runner 146 项、zzshare/rate-limit 24 项、评分/runner 182 项和文档一致性 26 项。

独立 CLI 复核：

- Claude Code 2.1.179 以 `--safe-mode --permission-mode plan` 完成只读审查。逐项回到代码验证后，采纳并删除 2 个未引用 helper，补齐 runner 新增参数的无依赖 `--help` 契约；其 sidecar 条件反转、双管道死锁和 CSV 逗号问题与现有实现及测试不符，未采纳。
- OMP 16.3.12 使用 `google-antigravity/claude-opus-4-6` 完成只读 patch 复核。采纳 `SKILL.md` 的 28/29 public CLI 计数漂移，并把测试改为从注册表动态计算；其 `FetchResult` 未定义结论来自 patch 缺少未改上下文，实际别名已存在。
- Grok Build 0.2.93 使用用户本机自定义 Responses 网关重试，最终由 `http://127.0.0.1:3000/v1/responses` 返回 `503 No available channel for model grok-4.5`，未产出审查结论。该问题属于外部模型通道，不在本仓库伪修或写成复核通过。

残余真实门禁：

- 尚未在当前代码上重新完成 5000+ symbol 的当日 zzshare 历史增量刷新、全部 bucket 执行和 verified merge。
- 尚未证明 Eastmoney、zzshare、Baostock、Pytdx、Akshare 或 yfinance 的长期稳定、免费额度、授权或未来可用性。
- 尚未证明真实 LightGBM prediction、样本外回测收益、券商订单、真实成交、滑点或容量。
