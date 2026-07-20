# Full-A workflow bottleneck evidence (2026-07-12)

## Scope

- Snapshot date: `2026-07-10` (Baostock resolved the requested Sunday
  `2026-07-12` to the latest available trading date).
- Universe: 5,202 Shanghai/Shenzhen A-share symbols; Beijing Exchange symbols
  were excluded by the universe fetch contract.
- History provider: ZZShare, no token configured, explicit non-trading policy
  `keep`, concurrency `1`, checkpoint batch `100`.
- Selection profile: `ultra_short_low_price_config.json`, generic mode, strict
  validation, local spot-universe filtering, minimum latest date
  `2026-07-10`.
- Run artifacts: `/tmp/a-share-full-market-rerun-20260712T090131Z`.

## Observed result

- Universe fetch: `14.55s`, `5,202/5,202`, `partial_result=false`.
- Incremental plan: `0.60s`, `5,202` symbols, `5,201` delta and `1` full.
- Incremental history fetch: `3,355.30s` wall time, `54` HTTP 429 events,
  `1,671s` explicit rate-limit sleep, no failed or empty symbols.
- CSV clean-pool merge: `428.39s`, `1,880,576` rows. This is a local I/O
  bottleneck caused by rebuilding the full CSV.
- Strict Parquet clean-up after removing 37 short-history symbols: `64.53s`,
  `5,165` scoreable symbols and `1,874,534` rows.
- Final runner: completed in `629.40s`; validation passed, scoring produced
  `5,165` diagnostics and `50` candidates.
- Scoring profile: `412.33s` total; `388.75s` in the scored stage, about
  `12.53` symbols/second. Candidate and diagnostic files were written
  successfully.

## Findings and boundaries

1. The dominant cold/update-path bottleneck is upstream ZZShare rate limiting,
   not the local request interval. A bulk provider or a verified provider
   routing policy is required for a material reduction; increasing concurrency
   without provider evidence is unsafe.
2. The local merge path is still unnecessarily CSV-oriented. Keeping the clean
   pool in Parquet and avoiding repeated full CSV rewrites materially reduces
   local preparation time.
3. The generic scoring stage is the dominant warm-run bottleneck. Its current
   per-symbol Pandas work uses limited CPU and should be optimized only with
   output-equivalence benchmarks.
4. The first strict validation correctly rejected 37 symbols with only two
   rows. They were removed through the explicit short-history clean-pool path;
   no rows were fabricated and no strict gate was relaxed.
5. The final runner deliberately reports
   `full_market_claim_allowed=false` for local prices input. The upstream
   universe and history evidence are real, but an end-to-end full-market claim
   should only be enabled after a signed/linked provenance contract is added.
6. The current Baostock universe snapshot does not provide the optional
   `industry`, `market_cap`, `pe_ttm`, or `pb_lf` fields. The 50 candidates are
   therefore technical ranking signals, not fundamental-complete records.

## Recovery improvement

When validation fails for local CSV/Parquet input without a
`history_metadata.json`, the runner now infers per-symbol row counts from the
actual input and writes the standard `short_history_symbols.txt/json` recovery
artifacts. This preserves strict failure behavior while removing the need for
manual metadata reconstruction.

## Implemented optimization controls

- The incremental planner now reconciles the actual prices artifact with its
  metadata and requires an explicit `--prices-input`. It checks row count,
  earliest/latest date, duplicate symbol/date rows, metadata drift, and a
  configurable `--min-history-rows` (default `120`). The real artifact was
  replanned as `37` full short-history recoveries and `5,165` up-to-date
  symbols, avoiding the earlier unnecessary `5,201`-symbol delta plan.
- Incremental execution now persists a SHA-256 execution-contract digest that
  covers provider, full plan, date range, checkpoint size, non-trading policy,
  and ZZShare rate-limit controls. Resume rejects provider or policy drift and
  rejects bucket artifacts whose provider metadata does not match the current
  execution.
- Clean-pool Parquet preparation removes duplicate full-table summaries and
  unnecessary normalization copies. The final verified single-file benchmark
  was `163.78s`, with merge work `70.95s`; output contained `1,880,503` rows and
  was Arrow-table equal to the preceding verified artifact. This did not meet
  the provisional `90s` target, so date partitioning remains an unimplemented
  design option rather than an implied completed optimization.
- Candidate scoring keeps the full-series indicator API for prediction feature
  generation, while generic candidate scoring uses equivalent latest-value
  RSI, MACD, and volatility calculations. On 500 real symbols, the isolated
  indicator benchmark fell from `10.56s` to `0.20s`. End-to-end candidate and
  diagnostic values stayed within `1e-12`, and candidate symbols/ranks were
  unchanged.
- The final full-A score rerun processed `5,165/5,165` symbols and produced `50`
  candidates with no stderr error. Its profile took `591.39s` under a noisy
  local runtime: input load `50.17s`, input preparation `72.52s`, universe
  filter `32.87s`, group scoring `228.93s`, provenance aggregation `69.59s`,
  and post-score/output work `137.32s`. The result demonstrates a material
  reduction from the original `388.75s` group-scoring hotspot but not a stable
  end-to-end speed target; process startup, Pandas copies, provenance scans,
  and CSV output remain measurable local bottlenecks.
- The runner's filtered-prices pass-through path now copies a same-format
  artifact byte-for-byte and writes a fresh SHA-256 sidecar. It does not skip
  content verification or raise `full_market_claim_allowed`.

## External review

- Claude CLI was invoked in safe plan mode with read-only tools. It identified
  serial per-symbol scoring, missing actual-row reconciliation, CSV merge cost,
  and prediction input diagnostics as the main actionable items. The first
  three were addressed or measured above. Its suggested fixed HTTP 429 budget
  was not adopted because the successful real run required `54` events and
  `1,671s` of explicit cooldown; a lower unverified default would reject a
  valid recoverable run.
- OMP was invoked through the configured qualified model route
  `newapi-responses/gpt-5.6-sol`. The unqualified `gpt-5.6-sol` name first
  resolved to `github-copilot` and failed before inference because that
  provider was not authenticated; that failed attempt is not counted as a
  review. The qualified review identified resume-contract drift, bucket content
  verification, planner reconciliation, duplicate table scans, score profiling,
  provenance linkage, and optional-fundamental boundaries. Resume and planner
  correctness, single-file Parquet work, score profiling, and local artifact
  SHA-256 sidecars are implemented. Month partitioning, end-to-end signed
  provenance, and as-of fundamental enrichment remain separate gated work.
- Both reviewers agreed that public CLI stability and domain-separated internal
  helpers are more important than reducing the Python file count. No mechanical
  script merge, automatic provider fallback, fabricated strict field, or
  unverified concurrency increase was adopted.

## Remaining gates

- ZZShare cold/update latency and 429 cooldown dominate the network path. No
  provider has enough repeated real evidence to replace it automatically.
- Pytdx remains a supplemental OHLCV source only. It cannot independently prove
  turnover, tradability, ST, suspension, or strict same-date quality fields.
- `industry`, `market_cap`, `pe_ttm`, and `pb_lf` remain unknown unless an
  explicit as-of source is supplied. No fallback values are generated.
- The local input chain has artifact SHA-256 evidence, but the complete universe
  snapshot to history provider to scoring chain is not signed as one contract;
  therefore `full_market_claim_allowed=false` remains mandatory.
- Monthly/date Parquet partitioning should only be implemented after a separate
  golden benchmark proves lower merge and read time without increasing partial
  artifact or recovery risk.

## Verification

- `python3 validate_skill_changes.py`: passed all 9 gates.
- Focused runner recovery tests: passed.
- Full unittest suite: passed.
- The run proves this concrete workflow and artifact set only. It does not
  prove long-term provider quota stability, broker execution, fundamental data
  completeness, or investment returns.
