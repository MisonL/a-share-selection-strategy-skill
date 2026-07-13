# 全 A 严格工作流

本文件只服务一个目标：让 AI Agent 在“全 A / 全市场 / 扩大股票池 / 真实扫描”任务里，优先走可复现、少歧义、少误判的路径，而不是把 demo、小样本命令或一次 runner 成功误当成全市场闭环。当前全 A 实现口径是沪深 A 股股票池（前缀过滤，不含北交所），不是所有交易场所和所有证券类型。

## 目录

- [何时使用](#何时使用)
- [核心判断](#核心判断)
- [当前推荐拓扑](#当前推荐拓扑)
- [数据源策略](#数据源策略)
- [强制规则](#强制规则)
- [推荐执行顺序](#推荐执行顺序)
- [当前版本的推荐收口方式](#当前版本的推荐收口方式)
- [最终报告前的必查清单](#最终报告前的必查清单)
- [失败恢复路由](#失败恢复路由)
- [现在不要让 Agent 做的事](#现在不要让-agent-做的事)

## 何时使用

出现以下任一意图时，先读本文件，再决定命令：

- 用户只说“选 A 股”“今日 A 股选股”“真实选股”，且没有限定 symbol、板块、本地股票池或本地行情文件
- “全 A”“全市场”“扩大股票池”“尽量覆盖更多股票”
- “真实扫描”“真实任务”“不要 demo 数据”
- “先抓实时快照再筛历史”
- “看看今天全市场有哪些候选”
- “把固定样本池扩大”

不要把本文件用于以下场景：

- 用户已经给出本地 `prices.csv` 或 `prices.parquet`，只想评分或生成 HTML 报告。
- 用户只想验证 1 到 20 个明确代码的真实链路。
- 用户坚持 prediction-derived 且已经给出预测列。

## 核心判断

全 A 严格工作流和 `mode=generic/prediction` 是两套概念：

- 工作流路径回答“怎么取数、怎么清洗、怎么复跑、怎么收口”
- `mode` 只回答“最后评分时用 generic 还是 prediction-derived”

不要把 `run_today_a_share_selection.py --mode auto` 理解成“已经选好了全 A 工作流”。

## 当前推荐拓扑

| 层 | 目的 | 推荐入口 | 关键产物 |
| --- | --- | --- | --- |
| 1 | 全 A 股票池快照 | `fetch_baostock_a_share_universe.py` | `spot.csv`、`spot_metadata.json` |
| 2 | 可选实时展示增强 | `fetch_eastmoney_a_share_spot.py` | `eastmoney_spot.csv`、`eastmoney_spot_metadata.json` |
| 3 | 第一轮历史抓取 | `run_today_a_share_selection.py` 或 `fetch_zzshare_a_share.py` | `selected_symbols.json`、`history_metadata.json`、`summary.json` |
| 4 | 清洗与复跑 | 同上，基于清洗后的 symbol 集 | `prices.csv`、`history_metadata.json` |
| 5 | 最终评分与展示 | `run_today_a_share_selection.py --prices-input ...` | `run_manifest.json`、`summary.json`、`diagnostics.csv`、`candidates.csv`、`report.html` |

## 数据源策略

| 需求 | 优先源 | 原因 | 主要风险 | 不适合 |
| --- | --- | --- | --- | --- |
| 全 A 股票池快照 | `baostock_universe` | `query_all_stock` 可直接形成沪深 A 股 symbol/name 池 | 不是实时 quote，不含价格、成交额或行业 | 不能写成实时全市场行情 |
| 实时展示增强 | `eastmoney` spot | 有价格、涨跌幅、成交额和行业展示字段 | 分页失败、`partial_result=true`、公开网页接口不稳定 | 不能作为唯一全 A 股票池前置或历史事实源 |
| 小范围严格可交易字段 | `baostock` history | 有 `tradestatus/isST` | 大范围易卡顿，慢 | 不适合直接跑全 A 广度 |
| 大范围历史 breadth | `zzshare` history | 适合更大 symbol 池 | 422 参数上限、429 限流、截断风险 | 不适合无批次控制地盲跑 |
| 预测列生成 | 本地 `generate_lightgbm_predictions.py` | 可审计 | 不证明模型质量 | 不替代全市场取数 |

## 数据源能力矩阵

| 数据源 | 当前角色 | 主要字段 | 免费或 token 边界 | 全 A 适用性 |
| --- | --- | --- | --- | --- |
| `baostock_universe` | 全 A 股票池主入口 | `symbol/name` | 免费登录接口；`query_all_stock` 只证明本次返回的代码列表；当日为空时可显式 `--lookback-days` 回看最近非空日期；登录或查询失败可显式重试并记录 `fetch_errors/fetch_attempts/max_attempts` | 适合作为历史 breadth 的 symbol 池；不能当实时行情、价格、成交额或行业证明 |
| `eastmoney` spot | 实时展示增强和对照快照 | `symbol/name/spot_price/spot_pct_chg/spot_amount/spot_industry` | 无 token，但公开网页接口分页可能断连 | 成功时可补展示字段；`partial_result=true` 时不能写成实时全市场扫描完成 |
| `zzshare` history | 大范围历史 breadth | OHLCV、`preclose/pctChg/turn/tradestatus/isST/name` | token 只从 `ZZSHARE_TOKEN` 读取；无 token 成功不证明额度或长期稳定 | 首选历史 breadth；必须批次控制并检查截断、失败和空 symbol |
| `baostock` history | 小范围严格核验 | OHLCV、`preclose/pctChg/turn/tradestatus/isST`、`query_stock_basic` 名称 | 免费登录接口，但逐 symbol 名称和历史请求较多 | 不作为全 A 首轮历史源；适合 clean pool 复核 |
| `akshare` A 股 | 备选历史源 | OHLCV、`amount/turn` | 开源接口聚合；`stock_zh_a_hist` 失败会 fallback 到 `stock_zh_a_daily` | 只作补充；fallback 成功不能写成主接口稳定 |
| `pytdx` A 股 | no-token 历史补充 | OHLCV、`amount` | 可 pip 安装且无 token；但 PyPI license 为 UNKNOWN；近期窗口自适应请求，截断写入 metadata | 只作显式补充和对照；`selection_ready=false`，缺 `turn/tradestatus/isST/name`，不替代全 A 主路径 |
| `akshare_hk_daily` | 港股补充 | 港股 OHLCV、`amount/name` | 开源接口聚合 | 不参与 A 股全市场路径 |
| `yfinance` | 海外 ticker 补充 | OHLCV | 无 key；market 只是输出标签 | 不适合 A 股全 A；缺 A 股换手率和可交易字段 |

对全 A 场景，默认策略是：

1. `baostock_universe` 负责沪深 A 股股票池快照：`--fetch-spot baostock_universe --derive-all-spot-symbols` 或先单独落地 `fetch_baostock_a_share_universe.py` 产物。它按前缀过滤排除北交所和非股票证券，不提供实时价格、成交额或行业字段。
2. `eastmoney` 只作为实时展示增强或对照快照；如果它失败或 `partial_result=true`，不能声称实时全市场完成，但不应阻断基于 `baostock_universe` 和 `zzshare` 的历史 breadth。
3. `zzshare` 负责大范围历史抓取。
4. `baostock` history 只用于小范围严格核验、字段探针或对照，不作为全市场默认历史源。
5. `akshare`、`pytdx`、`akshare_hk_daily` 和 `yfinance` 只能作为补充源或跨市场扩展，不替代全 A 主路径。

Pytdx 的允许补充字段只有 `open/high/low/close/volume/amount`，合并键固定为同一 `symbol+date`。provider 不返回股票名称时，`name` 保持空值并以 `name_value_policy=blank_missing_provider_name` 披露，禁止把 symbol 伪装成名称。缺少同日 `turn/tradestatus/isST/name` 时必须停止 strict merge；禁止用上一交易日、最近一条或前向填充生成新交易日 strict 字段。当前 verified merge 会拒绝 `selection_ready=false` 的 Pytdx 增量 artifact。

`baostock` 历史抓取可通过 `--names-input` 复用 `query_all_stock` 形成的 `symbol/name` CSV 或 Parquet；完整覆盖时不再逐 symbol 调用 `query_stock_basic`。缺失名称必须由 `--missing-name-policy=query/fail/blank` 显式处理，非交易行必须由 `--non-trading-policy=reject/drop/keep` 显式处理；默认仍是查询缺名和拒绝非交易行。runner 同时使用 `baostock_universe` spot 与 baostock history 时自动复用本次 `spot.csv`。这能减少名称请求，但全市场 5000+ 标的会显著增加远端请求数，不改变 baostock 不适合全 A 首轮历史 breadth 的边界。如果用 `query_all_stock` 准备对照股票池，必须按沪深 A 股股票前缀过滤，只保留 `sz.000/001/002/003/300/301` 和 `sh.600/601/603/605/688/689`，排除指数、基金、ETF、B 股和北交所代码。

全 A 失败恢复优先级：

1. `baostock_universe` strict 失败或 `partial_result=true`：先按 metadata 中的 `fetch_errors/fetch_attempts/max_attempts` 定位登录、日期或过滤问题；必要时显式增加 `--lookback-days`、`--retries` 和 `--retry-interval-seconds` 后重跑。不得改用旧缓存伪造当前股票池。
2. `eastmoney` spot strict 失败或 `partial_result=true`：只影响实时展示增强和实时全市场声称；若任务不要求实时 quote 字段，可以继续使用已落地的 `baostock_universe` 股票池，但报告必须披露 Eastmoney 失败和缺少实时展示字段。
3. `zzshare` history 出现 `failed_symbols`、`empty_symbols`、`possibly_truncated_symbols`、`unprocessed_symbols` 或 `rate_limit_budget_exhausted=true`：先降批次、加间隔、缩短窗口或按恢复清单复跑；未处理 symbol 不能混入真实空结果。
4. `baostock` 大批量变慢或名称查询失败：缩回为 clean pool 复核，不把它提升为全 A 首轮历史源。
5. `akshare` fallback、`pytdx` 缺换手率/可交易字段或 yfinance 空结果：只记录为外部源观察，不提升为主路径成功证据。

数据源能力的机器可读注册表是 `configs/data_sources.json`，业务场景源路由的机器可读注册表是 `configs/source_routing.json`。二者只用于审计和文档一致性检查，不代表 runner 会自动选源、自动 fallback 或证明长期稳定。未显式传 `--fetch-spot-fallback` 时不得声称自动切换；传了该参数时，必须披露 `fetch_spot_fallback_used` 和 `fetch_spot_primary_failure`。

## 全 A 长跑控制点

全 A 历史抓取的主要风险不是评分，而是外部 I/O、provider 限流、尾部批处理和可交易状态门禁。当前 runner 在 `--history-source zzshare` 且用户未显式覆盖时，会使用以下默认控制项：

- `--history-non-trading-policy drop`：把 `tradestatus != 1` 的历史行过滤出评分输入，同时在 metadata、summary 和 CSV provenance 中保留 `raw_non_trading_rows`、`history_dropped_non_trading_rows`、`history_retained_non_trading_rows` 和 `history_non_trading_policy`。这不是静默降级；直接调用 `fetch_zzshare_a_share.py` 的默认仍是 `--non-trading-policy fail`。
- `--history-max-concurrent-symbol-requests 1`：runner 默认保持顺序抓取。2026-07-08 的真实 benchmark 中，把该值显式提高到 `2` 或 `6` 都会在当前 zzshare provider 条件下立刻触发 `429` 和额外 timeout，因此并发只保留为人工实验开关，不作为默认优化路径。
- `--history-max-rate-limit-sleep-seconds`、`--history-max-429-events`、`--history-max-runtime-seconds`：显式覆盖累计 429 等待、429 次数和单轮总运行预算；未传时沿用 fetcher 的 `120/3/900` 默认值。预算耗尽必须非零退出并保留 `unprocessed_symbols`，不得配置成无限等待。
- `--history-checkpoint-batch-size 100`：把 zzshare 历史抓取按 symbol 批次写入 `history_checkpoints/`，并在 `history_metadata.json` 里记录 `checkpoint_enabled`、`checkpoint_manifest`、`checkpoint_parts_available`、`checkpoint_symbols_skipped` 和 `checkpoint_requests_executed`。
- `--history-progress-interval 100`：每处理 100 个 symbol 向 stderr 输出一次 `PROGRESS:`；runner 会实时透出进度，失败摘要会跳过这些进度行，避免把进度日志误当错误。

如需在同一输出目录复用已完成 checkpoint，显式加 `--history-resume-from-checkpoint`。checkpoint v2 会校验 provider、日期、字段、复权、分页、timeout、并发、限流预算和质量策略；旧版或契约不同的 manifest 会明确失败。只有分片文件大小和 SHA-256 与 manifest 一致，且非空分片中的 symbol 行数一致时，`completed` symbol 才会跳过；缺少旧指纹、内容被改写、empty、failed、truncated 或分片损坏都会记录 `checkpoint_integrity_issues` 并重抓。checkpoint 是原始抓取和恢复证据，不等于全 A 完成证明；最终仍要检查 `history_metadata.json`、`summary.json`、`prices.csv`、`diagnostics.csv` 和候选输出。

## 强制规则

1. 一定显式传 `--max-history-symbols`。
   当前默认值是 50，只适合小样本，不适合全 A。

2. 中间轮次默认关闭 HTML。
   第一轮和清洗轮次以 `summary.json`、`history_metadata.json`、`selected_symbols.json` 为准；只在最终收口轮次生成 `report.html`。

3. `zzshare` 的 `--history-limit` 不得大于 1000。
   当前 provider 上限是 1000；更大值会在远端统一失败。

4. 不把一次 runner 成功写成全市场完成。
   必须检查 `selected_symbols.json`、`history_metadata.json`、`summary.json`、`diagnostics.csv` 的覆盖和清洗结果。

5. 当前版本下，`prices-input` 复跑会优先读取同目录的 `metadata.json`，若缺失则回退读取 `history_metadata.json`。
   Agent 不需要再手工复制 `history_metadata.json -> metadata.json`；只需确认同目录至少存在其中一个 provenance 文件。

## 推荐执行顺序

### 0. 预设运行目录

```bash
RUN=/tmp/a-share-full-market-$(date +%Y%m%dT%H%M%S)
mkdir -p "$RUN"
```

建议把每一轮都放在独立子目录中，避免旧产物污染新结论。

### 1. 先拿全 A 股票池快照

```bash
uv run --with baostock python skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py \
  --output "$RUN/spot.csv" \
  --metadata-output "$RUN/spot_metadata.json" \
  --retries 5 \
  --retry-interval-seconds 1 \
  --lookback-days 7 \
  --fail-on-partial
```

先看这些字段：

- `partial_result`
- `raw_items`
- `filtered_items`
- `symbol_count`
- `requested_snapshot_date`
- `resolved_snapshot_date`
- `lookback_days`
- `date_fallback_used`
- `excluded_count`
- `coverage_claim`
- `source_claim_boundary`
- `source_type`
- `real_market_data`
- `data_source_note`
- `output_written`
- `metadata_output_written`
- `errors`
- `started_at`
- `finished_at`
- `duration_seconds`

独立 `fetch_baostock_a_share_universe.py` 和 runner 默认都不做日期回看；示例中的 `--lookback-days 7` 或 runner 的 `--spot-fallback-lookback-days 7` 是显式选择。只要 `date_fallback_used=true`，报告必须写清 `resolved_snapshot_date`，不能写成当日股票池。

只要 `partial_result=true`，就不能把后续任何结果写成全 A 股票池完成。`baostock_universe` 产物是 spot-compatible CSV，目的是给后续 `--derive-all-spot-symbols` 提供稳定 symbol 池；它不是实时 quote、价格、成交额或行业证明。

如任务需要实时展示字段，可另跑 Eastmoney spot 作为增强产物：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/fetch_eastmoney_a_share_spot.py \
  --output "$RUN/eastmoney_spot.csv" \
  --metadata-output "$RUN/eastmoney_spot_metadata.json" \
  --pages 60 \
  --timeout-seconds 20 \
  --retries 5 \
  --retry-interval-seconds 1 \
  --request-interval-seconds 0.5 \
  --fail-on-partial
```

Eastmoney spot 分页必须优先保证稳定和去重：`fetch_eastmoney_a_share_spot.py` 当前按 symbol code 排序分页，长跑建议显式设置 `--retry-interval-seconds` 和 `--request-interval-seconds`。不要用实时涨跌幅排序的多页结果拼全 A universe；行情排序会在请求过程中漂移，导致页间重复或漏 symbol。若 `partial_result=true` 或 output 未写出，只能披露实时展示增强失败，不能把它写成全市场实时扫描完成。

### 2. 第一轮历史 breadth 抓取

推荐直接让 runner 串联抓历史、校验和评分，但先关闭 HTML：

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/pass1" \
  --mode auto \
  --spot-input "$RUN/spot.csv" \
  --derive-symbols-from-spot \
  --derive-all-spot-symbols \
  --max-history-symbols 6000 \
  --history-source zzshare \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --history-request-interval-seconds 0.5 \
  --history-max-rate-limit-sleep-seconds 120 \
  --history-max-429-events 3 \
  --history-max-runtime-seconds 7200 \
  --history-limit 1000 \
  --history-max-pages 2 \
  --history-non-trading-policy drop \
  --history-checkpoint-batch-size 100 \
  --history-progress-interval 100 \
  --fail-on-skipped \
  --no-html-report
```

注意：

- `6000` 不是固定推荐值，只表示“显式给一个足够覆盖过滤后 spot 池的上限”。
- 不要依赖默认 `--max-history-symbols 50`。
- 全 A 历史 breadth 必须加 `--derive-all-spot-symbols`。否则 runner 会按当前评分配置先套 spot 价格、成交额或 ST 预筛，适合“小样本候选池”，不适合“全 A 范围历史抓取”。
- 对全 A 第一轮，目标是摸清覆盖和失败类型，不是立刻出最终报告。

### 3. 第一轮后先读 artifact，不急着看候选

优先检查：

- `pass1/selected_symbols.json`
- `pass1/history_metadata.json`
- `pass1/summary.json`
- `pass1/run_manifest.json`

最重要的问题不是“选出了几只”，而是：

- 初始历史池有多少只
- 哪些 symbol 失败、为空、被截断
- 是否有 `invalid_rows`
- 是否有 `non_trading_rows`
- `history_non_trading_policy` 是 `drop`、`keep` 还是 `fail`
- `history_dropped_non_trading_rows` 和 `history_retained_non_trading_rows`
- checkpoint 是否启用、跳过了多少已完成 symbol
- 是否有 `st_rows`
- 是否触发 422 / 429 / timeout

### 4. 清洗分类

第一轮后，把问题分成四类：

1. 参数类：例如 `history-limit` 超上限。
   这种应直接修命令，再重跑，不要继续分析结果。

2. provider 稳定性类：例如 429、timeout、`possibly_truncated_symbols`、`unprocessed_symbols` 或限流预算耗尽。
   这种应降低批次、增加 `request_interval_seconds`、或拆轮次重跑。

3. 数据质量类：例如 `invalid_rows`、`non_trading_rows`、`st_rows`。
   这种应形成剔除清单，再重跑历史。

4. 历史长度类：例如 validate 阶段提示若干 symbol 少于最小历史行数。
   这种应形成最终移除清单，再进入最终评分轮。

全 A 冷启动时，spot 中存在退市、暂停、无 zzshare 日线或上市时间太短的 symbol 是正常现象。第一轮 `history_metadata.empty_symbols` 和 validate 生成的 `short_history_symbols.txt/json` 应作为 clean pool 剔除依据；不要把这类 strict failure 写成 0 候选，也不要无差别重抓全部 symbol。使用 checkpoint 后，确认 `checkpoint_symbols_skipped` 能跳过已完成 symbol，并检查 `checkpoint_integrity_issue_count`；该值非 0 时要确认本轮已重新抓取缺失分片 symbol，再基于 clean `prices.csv` 做最终评分。

## 当前版本的推荐收口方式

当前 runner 支持 `--symbols-file`、`--plan-only` 和 `--resume-from`，但它们是显式控制项，不是“全 A 一键自动闭环”。因此 Agent 应预期至少两轮：

1. 第一轮：拿覆盖、失败分类、清洗依据。
2. 第二轮：基于 `--symbols-file` 或 `--resume-from` 重抓需要恢复的 symbol 集。
3. 最终轮：基于 clean `prices.csv` 做 `prices-input` 评分和 HTML。

### 5. 清洗后复跑历史

如果第一轮已经明确哪些 symbol 需要剔除或重试，建议基于清洗后的 symbol 集重新跑一轮历史抓取。长列表优先使用 `--symbols-file`，不要把几千个 symbol 直接塞进 shell 命令行。runner 对 zzshare 会把内部生成的长列表写入 `history_symbols.txt` 后传给 fetcher；validate 因短历史失败时，会写出 `short_history_symbols.txt` 和 `short_history_symbols.json` 作为剔除或延长窗口复跑的恢复依据。

推荐用 `prepare_history_retry_symbols.py` 从 `selected_symbols.json` 和 `history_metadata.json` 生成 retry plan，收集失败、空结果、截断和因预算耗尽未处理的 symbol 作为 retry list；默认排除 invalid/non-trading/ST 等数据质量不合格的 symbol。只有显式传 `--include-clean-selected` 时，才追加本轮干净的 selected symbol。不要手工重敲大列表；必须保留清洗规则和剔除数量，方便复核。

```bash
python3 skills/a-share-selection-strategy/scripts/prepare_history_retry_symbols.py \
  --selected-symbols "$RUN/selected_symbols.json" \
  --history-metadata "$RUN/history_metadata.json" \
  --output "$RUN/retry_plan.json" \
  --symbols-output "$RUN/retry_symbols.txt"
```

`retry_plan.json.claim_boundary` 必须保持 `retry_plan_only_not_full_market_completion_or_history_fetch_success`；它只是恢复计划，不是历史抓取成功证明。
`retry_plan.json.unexpected_metadata_symbols` 非空时，说明 `history_metadata.json` 含有不在 `selected_symbols.json` 里的 symbol，默认不会纳入恢复清单；必须先排查是否混入旧 artifact。

若第一轮已经抓完，但存在 `empty_symbols` 或 validate 生成的短历史清单，优先用 clean pool 自动生成最终评分输入，而不是手工复制和删行：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/prepare_clean_history_pool.py \
  --prices-input "$RUN/pass1/prices.csv" \
  --history-metadata "$RUN/pass1/history_metadata.json" \
  --short-history "$RUN/pass1/short_history_symbols.json" \
  --output "$RUN/clean/prices.csv" \
  --metadata-output "$RUN/clean/history_metadata.json" \
  --metadata-alias-output "$RUN/clean/metadata.json" \
  --report-output "$RUN/clean/clean_history_report.json"
```

`clean_history_report.json.claim_boundary` 必须保持 `clean_history_pool_from_existing_artifacts_not_full_market_proof`。`skip_records[]` 记录 `symbol/source/reason/observed_at/ttl_days`，适合作为后续显式 skip 或到期复核清单；它不是静默成功，也不是退市或不可交易的最终证明。`metadata.json` 兼容副本必须通过 `--metadata-alias-output` 显式请求，脚本不会隐式覆盖同目录文件。

日常增量任务不要默认重新冷启动全量历史。先基于最新 spot 和 clean metadata 生成增量计划：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/prepare_incremental_history_plan.py \
  --spot-input "$RUN/spot.csv" \
  --prices-input "$RUN/clean/prices.parquet" \
  --history-metadata "$RUN/clean/history_metadata.json" \
  --min-history-rows 120 \
  --target-end-date "$END_DATE" \
  --output "$RUN/incremental/incremental_history_plan.json" \
  --symbols-output "$RUN/incremental/incremental_history_symbols.txt"
```

`incremental_history_plan.json.claim_boundary` 必须保持 `incremental_history_plan_only_not_history_fetch_success`。planner 会读取 clean prices 的 `symbol/date` 两列并与 metadata 的行数和日期范围对账；不一致时显式失败。metadata 不存在、`rows <= 0`、`date_max` 为空、失败/空/截断/未处理或少于 `--min-history-rows` 时必须进入 `fetch_mode=full`；有效但过期的历史进入 `fetch_mode=delta`。未经审计的 `partial_result` 或限流耗尽状态必须失败，只有 `source_scope=clean_history_pool` 且带正数剔除原因的 clean 子集可继续。`fetch_buckets[]` 是按模式、原因和日期窗口稳定分组的执行契约，所有 symbol 必须与 `fetch_symbols` 无重漏对账。full bucket 不推断历史起始日，执行时必须显式提供。只有逐 bucket 抓取、重新生成 metadata 并通过 validate 后，才能说增量历史完成。

可使用 `execute_incremental_history_plan.py --plan ... --provider <zzshare|baostock|pytdx> --full-start-date "$START_DATE" --output-dir ...` 逐 bucket 执行。一次运行只能选择一个 provider，失败时保留 partial manifest 和已完成 bucket，不自动切源；`--resume` 仅复用重新校验通过且 execution contract digest 完全一致的 complete bucket。digest 绑定 provider、计划的 source/claim/目标日/min rows/symbols/buckets、full start、checkpoint 和 provider 参数；重新生成计划时 `generated_at`、耗时或吞吐等观测字段变化不会使同路径、语义相同的计划失效。语义字段、provider 参数或 bucket artifact 内容变化会拒绝复用或重新执行。全部 bucket 通过后，聚合 CSV 和 metadata 先分别写入同目录暂存文件，再成对发布；聚合失败会把 manifest 标记为 `partial/failed_stage=aggregate_outputs` 并保留既有两份最终产物。零 fetch bucket 的计划会写 `no_op=true`、移除陈旧聚合产物，且不允许继续请求 verified merge。zzshare 历史停牌行默认导致失败；剔除停牌历史用 `--zzshare-non-trading-policy drop`，保留停牌事实供最终评分按最新状态排除用 `keep`。全 A 长 bucket 调整 request interval、429 sleep/event 或 runtime 预算前必须先跑小样本实测，并通过 `--zzshare-*` 显式传入有界值；不得改成无限等待。需要在同一命令完成 verified merge 时，必须成组提供 base prices、base metadata 和三个 merge 输出参数。

zzshare 默认将累计 429 sleep 限制为 120 秒、429 事件限制为 3 次、单次 fetch 总运行时间限制为 900 秒。预算耗尽是强制失败：已经得到可审计结果的当前 symbol 按失败语义写入 checkpoint，尚未得到结果的当前或剩余 symbol 只写入 `unprocessed_symbols`，CLI 非零退出。`failed_symbols`、`empty_symbols` 和 `unprocessed_symbols` 必须互斥表达，不得重复计数；不得提高并发或隐式切源来绕过限流。

增量抓取完成后，用同一个 clean pool 入口显式合并 delta：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/prepare_clean_history_pool.py \
  --prices-input "$RUN/clean/prices.csv" \
  --history-metadata "$RUN/clean/history_metadata.json" \
  --incremental-plan "$RUN/incremental/incremental_history_plan.json" \
  --incremental-prices "$RUN/incremental/prices_delta.csv" \
  --incremental-metadata "$RUN/incremental/history_metadata_delta.json" \
  --output "$RUN/clean_merged/prices.csv" \
  --metadata-output "$RUN/clean_merged/history_metadata.json" \
  --metadata-alias-output "$RUN/clean_merged/metadata.json" \
  --report-output "$RUN/clean_merged/clean_history_report.json"
```

增量合并会强制检查 delta metadata 无 `failed/empty/possibly_truncated/unprocessed` 且 `rate_limit_budget_exhausted=false`，计划内 symbol 都在增量 prices 中出现，且每个 symbol 的最新日期达到 `target_end_date`；重复的 `symbol/date` 行由增量结果覆盖并记录 `overlap_rows_replaced`。该步骤只合并已落地 artifact，不联网、不证明未来稳定性。

过滤输出为 Parquet 时，runner 必须同时写 `<prices>.metadata.json` sidecar。sidecar 记录 artifact 路径、SHA-256、size、mtime、rows、symbols、日期范围、过滤契约与原始 input metadata；内容身份由路径、size 和 SHA-256 锁定，mtime 仅供审计。复用时必须先验证 sidecar 并重算表统计；摘要不匹配、sidecar 缺失、内容篡改、统计漂移或 input metadata 结构损坏时不得继续评分，单独触碰 mtime 不应让内容相同的 artifact 失效。

可先用计划模式审计第二轮命令，不触发实际取数：

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/pass2-plan" \
  --mode auto \
  --symbols-file "$RUN/retry_symbols.txt" \
  --history-source zzshare \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --history-request-interval-seconds 0.5 \
  --history-limit 1000 \
  --history-max-pages 2 \
  --plan-only \
  --no-html-report
```

如果只是重跑上一轮失败、空结果、截断或未处理 symbol，也可以直接从上一轮 manifest 恢复：

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/pass2-retry" \
  --resume-from "$RUN/pass1/run_manifest.json" \
  --history-request-interval-seconds 0.5 \
  --history-limit 1000 \
  --history-max-pages 2 \
  --no-html-report
```

`--plan-only` 会写入 `run_manifest.json`、`summary.json`、配置副本和审计所需输入快照，stdout 以 `PLAN_ONLY:` 开头，但不会执行 fetch、validate 或 score，也不会产出本轮 `candidates.csv`、`diagnostics.csv` 或真实 `history_metadata.json`。此时 `summary.history_output_written=false`、`history_metadata_output_written=false`、`history_artifact_status=not_written` 才是未取数的机器判据；不要把计划里的输出路径当成已落地 artifact。`summary.plan_only_reason=plan_only_no_commands_executed`、`plan_only_next_action=execute_planned_workflow_to_collect_artifacts` 表示计划未执行，`summary.planned_parameters` 记录本轮计划会使用的非空抓取/日期参数，`summary.step_summary[]` 只提供轻量步骤状态，完整命令仍以 `run_manifest.json.steps[]` 为准。

`--resume-from` 写入的 `selected_symbols.json.source=resume_retry_symbols` 只表示本轮来自恢复清单；仍需重新检查 `history_metadata.json` 和 `summary.json`，不能跳过门禁。它会继承上一轮未被本轮显式覆盖的历史源和日期；`history_adjust`、超时、间隔、并发、三项限流预算、limit、max-pages 和 zzshare non-trading policy 只在本轮历史源与上一轮一致时继承，并在 manifest 中记录 `resume_inherited_options`。zzshare 自定义 URL 可能包含 signed query 或内部地址，runner 不会从上一轮 manifest 自动继承 `history_http_url`；需要复用时必须在本轮显式传 `--history-http-url`，manifest 会用 `resume_sensitive_options_requiring_explicit_input` 提醒。如果上一轮 manifest 的 `output_dir` 是相对路径，会先判断该路径是否已经指向 manifest 所在目录，否则按该 manifest 所在目录解析。

如果上一轮 `history_metadata.json` 中没有 `failed_symbols`、`empty_symbols`、`possibly_truncated_symbols` 或 `unprocessed_symbols`，`--resume-from` 不会构造恢复清单，而应失败并提示没有可重试 symbol；不要把它当成“从上一轮全量继续跑”的通用 resume。

这一步的目标是拿到：

- `invalid_rows == 0`
- `non_trading_rows == 0`
- `st_rows == 0`
- `failed_symbols == []`
- `empty_symbols == []`
- `possibly_truncated_symbols == []`
- `unprocessed_symbols == []`
- `rate_limit_budget_exhausted == false`

### 6. 最终评分与 HTML 报告

当 clean `prices.csv` 已经准备好后，再进入最终轮次：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input "$RUN/clean/prices.csv" \
  --spot-input "$RUN/spot.csv" \
  --filter-prices-to-spot-universe \
  --min-symbol-latest-date "$END_DATE" \
  --prices-filter-output-format parquet \
  --score-profile \
  --output-dir "$RUN/final" \
  --mode auto \
  --html-report-language zh \
  --fail-on-skipped
```

`--filter-prices-to-spot-universe` 和 `--min-symbol-latest-date` 只过滤已落地的 clean `prices.csv`，用于防止旧历史池混入当前 universe 外或过期 symbol；它们不会联网、不补齐缺失历史，也不能替代增量历史抓取和 metadata 复验。`--prices-filter-output-format parquet` 只改变过滤后运行内 prices 的落盘格式，减少大 CSV 重写和后续读取成本；它不改变评分口径，默认不传时仍沿用输入格式。

`--score-profile` 是最终轮性能排查开关，会让 runner 传递 `score_candidates.py --profile-output` 并写出 `score_profile.json`，记录 score step 的阶段耗时、输入行数、候选行数、诊断行数、input rows/s 和 scored symbols/s。该文件只用于定位本地评分瓶颈，不改变候选、诊断、排序或失败路径；默认不传时不会生成。

`summary.json` 同时保留 runner 总耗时、symbol 派生、prices filter、HTML、history fetch step 和 score profile 核心吞吐；外部源实际提供时还透传 `history_requested_raw_rows/history_raw_rows/history_output_rows/history_api_request_count/history_overfetch_rows` 以及 429、network retry 和 sleep。字段不存在表示 provider 未测量，不能按 0 推断没有请求或重试。

如果最终轮失败并提示 `local prices filters removed all price symbols`，先看 `prices_filter.json`、`summary.json.prices_filter_failure_reason` 和 `prices_filter_removed_stale_symbol_count`。这通常表示 clean 历史的最新日期早于传入的 `--min-symbol-latest-date`，或者当前 spot/universe 与 clean prices 没有交集；不得静默放宽日期或去掉 universe 过滤，必须先刷新增量历史或缩短本轮 claim。

2026-07-09 的一次真实全 A 观察口径：eastmoney spot 得到 5536 个 symbol；zzshare 冷启动历史抓取耗时约 5133 秒，返回 5242 个有日线 symbol，empty 294；validate 后又识别 56 个短历史 symbol；clean 后保留 5186 个 symbol、约 187 万行；最终评分约 185 秒，候选 49。该证据说明主要瓶颈是外部逐 symbol 历史 I/O，不是本地评分；它不证明未来每次耗时、真实 prediction、真实回测收益或券商成交。

## 最终报告前的必查清单

只有以下问题都答清楚后，才适合把 `report.html` 给用户：

1. `summary.json` 的 `execution_path`、`coverage_class`、`full_market_claim_allowed`、`full_market_claim_boundary` 是什么。
1. 初始 spot 样本多少只。
2. 第一轮历史抓取多少只。
3. 清洗掉多少只，按什么原因清洗。
4. 最终 validate 后保留多少只。
5. `candidate_rows` 和 `diagnostic_rows` 各是多少。
6. `candidate_field_coverage` 是否已经在 HTML 和 stdout 里清楚展示。
7. `source_scope`、`spot source_scope`、实际 `date_max` 是什么。
8. 哪些边界仍未证明：实时全市场完成、长期稳定性、真实成交、真实收益。

如果最终 `report.html` 没直接展示以下过程，Agent 在对用户汇报时必须手动补齐：

- 初始 spot 快照规模
- 初始历史抓取样本规模
- 每轮清洗剔除数量
- 最终 validate 通过股票池数量

不要只给页面链接或只报最终候选数。

## 失败恢复路由

| 信号 | 先看 | 下一步 |
| --- | --- | --- |
| 422 / 参数错误 | `run_manifest.json`、stderr | 修正 provider 参数后重跑整轮 |
| 429 / timeout | `history_metadata.json`、stderr | 降低批次、增加 `request_interval_seconds`、拆轮次重跑 |
| `invalid_rows > 0` | `history_metadata.json` | 剔除或显式 `--drop-invalid-rows`，再重跑历史 |
| `non_trading_rows > 0` 或 `st_rows > 0` | `history_metadata.json` | 形成剔除清单，重跑 clean history |
| `output_written=false` / validate 失败 | `summary.json`、validate stderr | 修输入或缩短 claim，不要写成 0 候选成功 |
| `source_scope=unknown` 的 `prices-input` 复跑 | `summary.json`、同目录 metadata 文件 | 确认同目录至少存在 `metadata.json` 或 `history_metadata.json`；缺失时补齐 provenance 后再重跑 |

## 现在不要让 Agent 做的事

- 不要在全 A 第一轮就急着生成 HTML 报告。
- 不要把默认 `max-history-symbols=50` 当成全市场命令。
- 不要把一轮 partial 或 strict gate failed 的产物写成“真实扫描完成”。
- 不要把 `mode=auto` 当成“工作流已经自动选对”。
- 不要把 `report.html` 当成比 `summary.json`、`history_metadata.json`、`run_manifest.json` 更高的事实源。
