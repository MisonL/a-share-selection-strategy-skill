# 脚本参考

本文件收纳配置文件、依赖、数据源能力边界、数据源字段映射、输入契约和常用命令细节。`SKILL.md` 只保留路由和硬约束；判断脚本职责、稳定入口或 helper 边界时，先读 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)，不要用 `scripts/` 根目录文件数量或 `__main__` 保护猜入口。

## 目录

- [配置文件](#配置文件)
- [入口分层](#入口分层)
- [依赖和离线环境](#依赖和离线环境)
- [输入数据契约](#输入数据契约)
- [数据源字段映射](#数据源字段映射)
- [常用命令](#常用命令)

## 配置文件

| 文件 | 用途 | 边界 |
| --- | --- | --- |
| `../configs/example_config.json` | 通用权重、窗口和阈值示例 | 不代表真实市场验证 |
| `../configs/ultra_short_low_price_config.json` | 低价超短通用技术评分 | 不使用也不伪造 prediction-derived/LightGBM |
| `../configs/prediction_profile_config.json` | prediction-derived A 股默认剖面 | 需要真实 `prediction` 或 `prediction_score` 输入 |
| `../configs/hong_kong_generic_config.json` | 港股本地 OHLCV 通用技术评分 | 不证明港交所日历、真实成交或收益 |
| `../configs/data_sources.json` | 数据源能力机器注册表 | 只用于审计和一致性检查，不做运行时自动选源或稳定性证明 |
| `../configs/source_routing.json` | 业务场景到数据源的机器路由表 | 只用于审计和 Agent 决策辅助，不做运行时自动选源、自动 fallback 或稳定性证明 |
| `../configs/script_entrypoints.json` | 脚本入口机器注册表 | 只用于审计根层 `.py` 分类，不做运行时 dispatch 或 CLI 合约替代 |

旧命令里的 `../scripts/*.json` 路径仍由 CLI 解析到 `../configs/*.json`，但新文档和默认 runner 都应使用 `../configs/*.json`。

## 入口分层

稳定 CLI、取数入口、门禁回测入口和内部 helper 的完整边界见 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)。本文件只在已经确定入口后提供配置、依赖、字段和命令细节。

`../configs/script_entrypoints.json` 必须覆盖 `scripts/` 根层每个 `.py`，并把它们归入 `stable_cli`、`fetch_cli`、`gate_backtest_cli` 或 `internal_helper`。注册表 v2 用 `visibility`、`kind`、`stability`、`domain` 和 `skill_route` 拆开描述入口可见性、脚本类型、稳定性、领域和 Agent 路由资格；新增、删除或移动根层脚本时，先更新注册表，再更新 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md) 的解释层。

新增内部 helper 默认不得放到 `scripts/` 根层；放入 `scripts/lib/` 或后续内部子目录。根层 internal helper 是兼容预算，只允许迁出、删减或保留，不允许无审计地扩张。

依赖方向默认是 public CLI 调用 internal helper，internal helper 默认不得 import public CLI。共享 OHLCV frame 校验逻辑位于 `scripts/lib/a_share_selection_validation.py`，公开 CLI 和内部 helper 都从内部模块复用。

`compatibility_wrapper` 条目必须在 `../configs/script_entrypoints.json` 记录 `migration_target` 和 `deletion_blocker`，用于说明真实内部实现位置和根层 wrapper 的外部兼容保留原因。内部运行路径应优先导入 `lib.*`。

联网取数必须先落地本地表格 artifact 和 metadata，再进入 `validate_ohlcv.py`、评分和汇报。表格 artifact 默认是 CSV；明确支持 Parquet 的入口可按文档显式选择 `.parquet` / `.pq`。不得把在线 API 响应直接解释成已验证候选。

`run_today_a_share_selection.py --mode auto` 只选择评分口径，不自动完成全 A 工作流。全 A / 全市场 / 扩大股票池任务必须先读 `full-a-strict-workflow.md`。

P1 `portfolio_cash_lot_floor`、单信号日定位链路、manifest/artifact validator 参数以 `runbook.md` 为准。

`python3 -S <helper>.py --help` 的顶层 pandas/numpy import 失败不属于 `--help` 入口缺口。`python3 -S --help` 轻量依赖门禁只适用于带 `argparse`、`main()` 或 `__main__` 的脚本入口。

Python 代码复用这些脚本时，需要将 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。不要把 `from scripts.<name> import ...` 当成稳定 API。

部分内部 helper 的实现位于 `scripts/lib/`，根层同名 `.py` 文件保留为兼容 wrapper。外部调用和旧测试仍应通过根层路径导入；`lib/` 不是用户 CLI 入口。

公开 CLI 路径默认冻结；不要为了目录整洁移动 `stable_cli`、`fetch_cli` 或 `gate_backtest_cli`。若确需移动公开入口，必须先设计兼容 wrapper、更新 runbook/README/测试，并证明旧命令仍可用。

## 依赖和离线环境

| 场景 | 依赖 |
| --- | --- |
| 基础计算 | `pandas`, `numpy` |
| Parquet 输入 | `requirements-parquet.txt` 或 `pyarrow` / `fastparquet` |
| LightGBM prediction 生成器 | `requirements-ml.txt` |
| A 股 baostock 取数 | `baostock` |
| A 股 akshare 取数 | `akshare` |
| A 股 pytdx 取数 | `pytdx` |
| A 股 zzshare 取数 | `zzshare` |
| 海外 OHLCV 取数 | `yfinance` |

常用场景按需安装命令：

| 场景 | 命令骨架 |
| --- | --- |
| 本地校验、评分、clean pool、增量计划 | `uv run --with pandas --with numpy python ...` |
| 全 A 股票池 universe | `uv run --with baostock python skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py --lookback-days 7 --retries 1 --retry-interval-seconds 1 ...` |
| 全 A 实时展示增强 | `python skills/a-share-selection-strategy/scripts/fetch_eastmoney_a_share_spot.py ...` |
| 全 A zzshare 历史 breadth | `uv run --with pandas --with numpy --with zzshare python ...` |
| baostock 小范围核验 | `uv run --with pandas --with numpy --with baostock python ...` |
| akshare A 股或港股补充 | `uv run --with pandas --with numpy --with akshare python ...` |
| pytdx A 股补充 | `uv run --with pandas --with numpy --with pytdx python ...` |
| yfinance 海外 ticker 补充 | `uv run --with pandas --with numpy --with yfinance python ...` |

这些依赖按场景显式安装，不要求用户默认全装。`baostock_universe` 是当前全 A 股票池主入口；`eastmoney` spot 入口只依赖标准库，适合补实时展示字段但不作为唯一全 A 股票池前置；`zzshare` 是当前全 A 历史主路径；`baostock`、`akshare`、`pytdx` 和 `yfinance` 是补充或核验源，不是静默 fallback。

上表里的 `--lookback-days 7` 是非交易日或收盘后人工复验时的显式示例；`fetch_baostock_a_share_universe.py`、runner `--fetch-spot baostock_universe` 和 runner 显式 fallback 的日期回看默认值都是 0。

完全离线运行时，必须使用已经安装好依赖的解释器、虚拟环境、wheelhouse 或已有包缓存。若 `uv run --with ...` 因无法解析依赖失败，应显式报告环境问题；不得用 mock 数据、跳过依赖或把未运行的脚本说成验证通过。

## 数据源能力边界

| 入口 | 服务 | 数据范围 | 适合用途 | 不能证明 |
| --- | --- | --- | --- | --- |
| `fetch_baostock_a_share_universe.py` | baostock `query_all_stock` | A 股 symbol/name universe 兼容快照 | 全 A 股票池主入口；可用 `--lookback-days` 解析最近非空交易日；`--retries` 失败重试会写入 `fetch_errors/fetch_attempts/max_attempts`；配合 `--derive-all-spot-symbols` 使用 | 实时行情、价格、成交额、行业、交易所日历或实时全市场行情证明 |
| `fetch_eastmoney_a_share_spot.py` | 东方财富公开 spot 接口 | A 股实时快照展示字段 | 全 A 当日展示增强；长分页应使用稳定 symbol 排序和显式 retry/page interval | 历史 OHLCV、长期稳定性、唯一股票池前置 |
| `fetch_zzshare_a_share.py` | zzshare `daily(fields=all)` | A 股日线、换手、停牌/ST 相关字段 | 大范围历史 breadth、spot 派生 symbol 池历史抓取 | 无 token 长期额度、无截断、券商订单或成交能力 |
| `fetch_baostock_a_share.py` | baostock | A 股日线、`tradestatus/isST`；prices 可按 `.csv/.parquet/.pq` 后缀落盘，可复用 `symbol/name` 输入并仅查询缺名项 | 小范围严格字段核验、walk-forward 门禁；大文件本地复跑优先显式 Parquet | 全 A 首轮高吞吐抓取、直接涨跌停字段 |
| `fetch_akshare_a_share.py` | akshare | A 股日线、成交额、换手 | A 股历史补充或交叉观察 | `stock_zh_a_hist` 主接口稳定；fallback 不能当主源成功 |
| `fetch_pytdx_a_share.py` | pytdx | A 股日线 OHLCV、成交额；近期窗口自适应首请求并记录 raw/output/request 指标 | no-token 历史补充和对照；仅可按同一 `symbol+date` 补字段 | 换手率、停牌/ST、股票名称、独立 strict merge、官方授权、机构或商业使用权、长期稳定性 |
| `fetch_akshare_hk_daily.py` | akshare 港股日线 | 港股 OHLCV、成交额、名称 | 港股已落地数据集审查 | A 股全市场覆盖、港交所完整日历或可交易性 |
| `fetch_yfinance_ohlcv.py` | yfinance/Yahoo | 通用 ticker OHLCV | 美股/海外 ticker 补充 | A 股换手率、A 股可交易字段、exchange/calendar proof |

`ZZSHARE_TOKEN` 是唯一允许的 zzshare token 输入位置。不要把 token 放进 CLI 参数、config 或文档示例；runner 会记录 step command，命令行 token 会泄漏到 `run_manifest.json`。

`../configs/data_sources.json` 应与本节表格和 [../instructions/full-a-strict-workflow.md](../instructions/full-a-strict-workflow.md) 的数据源能力矩阵保持一致；它不是调度器，不会绕过显式 CLI 参数或全 A 严格工作流。

## 业务场景到数据源路由

`../configs/source_routing.json` 是场景级路由事实源，用来回答“本地评分、定向 A 股、全 A、prediction-derived、港股、海外 ticker 或外部源探针应考虑哪些源”。它不是运行时自动选源器；`automatic_source_selection=false`、`automatic_fallback=false` 且 `runtime_cli_explicit_fallback_requires_parameter=true` 是硬边界。联网源必须同时落地可复核的表格 artifact 和 metadata，不把格式限定为 CSV；只有入口明确声明支持时才可写 Parquet。表内 `explicit_fallback_sources=[]` 表示该场景不推荐自动或预设备用源，不会禁用 CLI 层面的显式 fallback 参数；CLI 层面的 `--fetch-spot-fallback` 必须由用户显式传入，并披露 `fetch_spot_fallback_used` 和 `fetch_spot_primary_failure`。全 A 增量路径必须先由 `prepare_incremental_history_plan.py` 生成计划，再由 `execute_incremental_history_plan.py` 使用一个显式 provider 执行；路由表列出二者不表示自动编排或自动切源。

| 业务场景 | 主源 | 显式备用 | 补充或对照 | 边界 |
| --- | --- | --- | --- | --- |
| 本地评分 | 本地 `prices.csv` / Parquet | 无 | 无 | 只证明本地 artifact 评分，不证明真实取数 |
| 定向 A 股真实任务 | `baostock_history` | 无 | `zzshare_history`、`akshare_a_share`、`pytdx_history` | 只覆盖显式 symbol 池，不外推全 A |
| 全 A 严格扫描 | `baostock_universe` + `zzshare_history` | 无 | `eastmoney_spot`、`baostock_history`、`akshare_a_share`、`pytdx_history` | 当前口径是沪深 A 股股票池（前缀过滤，不含北交所）；Eastmoney 只补实时展示字段；失败不能阻断 universe + history 主路径，也不能声称实时全市场完成 |
| prediction-derived A 股 | 外部或本地生成的 prediction 输入 | 无 | `zzshare_history`、`baostock_history` 只能补行情字段 | 行情源不能伪造 prediction |
| 港股数据集审查 | `akshare_hk_daily` | 无 | 无 | 不参与 A 股全市场路径 |
| 海外 ticker 审查 | `yfinance` | 无 | 无 | market 只是标签，不证明交易所日历 |
| 外部源短窗口探针 | `probe_external_source_stability.py` 覆盖注册外部源 | 无 | 无 | 只证明当前窗口、参数和网络，不证明长期稳定 |

## 输入数据契约

开始前先确认输入数据是否满足任务所需字段。字段缺失时不得静默生成“看似成功”的结果。

最小行情字段：

- `symbol`：股票代码，必须按文本保存，避免 `000002` 变成 `2`。
- `date`：交易日期，支持 `YYYY-MM-DD` 或 `YYYYMMDD`；两种格式会归一化为同一日，同一 `symbol/date` 重复必须先修复，不能当成两天数据。
- `open`、`high`、`low`、`close`：价格字段，必须为正数。
- `volume`：成交量，不得为负数，单位必须在同一文件内一致。
- `name`、`market`、`amount`、`turn` 或 `turnover`：可选字段，按策略需要提供。

校验规则：

- `validate_ohlcv.py` 会拒绝 1 到 5 位纯数字 `symbol`，用于捕获前导零损坏。
- 同一股票同一日期不能重复。
- 每只股票必须有足够历史窗口；prediction-derived 默认至少 120 条日线。
- prediction-derived 的 `market` 必须使用精确值 `A-share`。
- prediction-derived 必须包含 `prediction` 或 `prediction_score`，且取值在 0 到 1 之间。
- prediction-derived 必须包含 `turn` 或 `turnover`。
- 无 config 的基础 OHLCV 校验或切片成功不会检查或补齐 prediction-derived 必需字段；切片后要用 prediction-derived config 重新校验和评分，缺字段的 `bad_input output_written=false` 不是成功 0 候选。
- 如果使用未来收益做训练标签，必须避免在预测时泄漏未来数据。

## 数据源字段映射

| 数据源 | 关键映射 |
| --- | --- |
| akshare A 股中文列 | `日期 -> date`、`股票代码 -> symbol`、`开盘/最高/最低/收盘 -> open/high/low/close`、`成交量 -> volume`、`成交额 -> amount`、`换手率 -> turn` |
| akshare `stock_zh_a_daily` | `date -> date`、`open/high/low/close` 同名映射、`volume -> volume`、`amount -> amount`、`turnover -> turn` |
| baostock | `code -> symbol`，去掉 `sz.` 或 `sh.`；补 `market=A-share`；其余 OHLCV 字段同名映射 |
| pytdx | `datetime/year/month/day -> date`、`vol -> volume`、`amount -> amount`、`open/high/low/close` 同名映射；provider 不返回名称时 `name` 保持空值并记录 `name_value_policy=blank_missing_provider_name`，metadata 必须披露缺 `turn/tradestatus/isST/name` |
| zzshare `daily(fields=all)` | `ts_code -> symbol`，去掉 `.SZ`、`.SH` 或 `.BJ`；`trade_date -> date`、`volume/vol -> volume`、`turnover/amount -> amount`、`turnover_rate -> turn`、`is_paused -> tradestatus`、`is_st -> isST` |
| yfinance | `Date/Symbol/Open/High/Low/Close/Volume` 映射为小写标准字段 |

`成交额` 只能映射为可选字段 `amount`，不得映射为 `volume`。不要把 `Adj Close` 静默替换为 `close`；如使用复权价，必须记录复权口径。

本节只列已落地入口和通用输入别名。未出现在 `../configs/script_entrypoints.json` 或 `../configs/data_sources.json` 的数据源，不代表本 Skill 提供内置 fetch 能力。

## 常用命令

本地 demo：

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-demo
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --input /tmp/a-share-selection-demo/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py --input /tmp/a-share-selection-demo/prices.csv --config skills/a-share-selection-strategy/configs/example_config.json --output /tmp/a-share-selection-demo/candidates.csv
```

今日入口：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /path/to/prices.csv \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fail-on-skipped
```

带 baostock 历史源的小样本真实任务：

```bash
uv run --with pandas --with numpy --with pyarrow --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --history-source baostock \
  --history-output-format parquet \
  --history-names-input /path/to/universe.csv \
  --history-missing-name-policy query \
  --history-baostock-non-trading-policy reject \
  --symbols 000001,600000 \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-skipped
```

长 symbol 列表和恢复任务：

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-plan \
  --mode auto \
  --history-source baostock \
  --symbols-file /path/to/symbols.txt \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --plan-only \
  --no-html-report
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-retry \
  --resume-from /tmp/a-share-selection-pass1/run_manifest.json \
  --no-html-report
```

`--symbols-file` 会在 manifest 中形成 `execution_path_reason=explicit_symbols_file`；`--plan-only` 只写计划 step 和审计输入快照，`commands_executed=false`；`--resume-from` 只生成 `resume_retry_symbols`，并在 `resume_inherited_options` 记录从上一轮继承的非敏感历史抓取参数，仍需重新检查新一轮 `history_metadata.json`。Baostock 的 `--history-output-format parquet|pq` 需要 `pyarrow` 或 `fastparquet`，会把 fetch、validate、score、summary 和 HTML 候选 K 线绑定到同一 Parquet artifact；缺引擎在 step 和联网前失败。默认仍为 CSV，其他 provider 或本地 `--prices-input` 不接受该参数。`history_http_url` 不从上一轮 manifest 自动继承；需要复用自定义 URL 时本轮显式传 `--history-http-url`，manifest 会用 `resume_sensitive_options_requiring_explicit_input` 提醒。

全 A clean pool：

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

`prepare_clean_history_pool.py` 不联网、不重新取数，只基于既有 `history_metadata.json` 和短历史清单生成 clean `prices.csv`、clean metadata 和剔除报告。`metadata.json` 兼容副本必须通过 `--metadata-alias-output` 显式请求；脚本不会隐式覆盖同目录文件。`clean_history_report.json.skip_records[]` 必须保留 `symbol/source/reason/observed_at/ttl_days`，用于后续显式复核或过期重试。

只有需要 clean-pool provenance 审计时，才在命令中追加以下三项；前两个文件必须来自同一次 `baostock_universe` 抓取，不能使用 Eastmoney spot metadata：

```bash
  --universe-input "$RUN/universe.csv" \
  --universe-metadata "$RUN/universe_metadata.json" \
  --provenance-output "$RUN/clean/full_a_clean_pool_provenance.json"
```

可选的 `--universe-input --universe-metadata --provenance-output` 必须同时出现；它会在同一次原子发布中绑定 universe、raw history、clean outputs 和可选 short-history 清单，并逐原因对账 history metadata、short-history 与 clean report。`full_a_clean_pool_provenance.json.full_market_closure_eligible=true` 要求至少 4,000 个 symbol、完整 baostock metadata 合同、所有 history symbol 达到共同 as-of、clean 与 history 去除明确 removed symbols 后全行全列等价，且无 clean-pool 排除；4,000 只是拒绝局部样本的保守下限，不是独立完整性证明，也不等于最终 runner 已完成全市场筛选、实时行情、prediction、券商订单或收益证明。有 short-history 或 stale symbol 时该字段必须为 `false`。该 provenance 模式暂不接受 `--incremental-*` 参数，避免把未持久化的内存 merge 伪装成可复核 raw artifact。

增量抓取完成后，同一入口可加 `--incremental-plan --incremental-prices --incremental-metadata`，先把验证过的 delta history 合并进 clean pool，再执行原有清洗。合并会拒绝 delta metadata 中的 failed/truncated/unprocessed symbol、未经审计的 empty、`rate_limit_budget_exhausted=true`、缺失计划 symbol、未达到 target date 或超过 target date 的增量行；普通 empty 仍然失败。唯一例外是严格审计的 Baostock no-trading empty：三个集合必须满足 `empty_symbols == no_trading_update_symbols == non_trading_only_empty_symbols`，`partial_result_semantics` 必须为固定值，且必须同时满足 `provider=baostock`、`raw_symbols.rows > 0`、`date_max=target_end_date`。只有这类 symbol 可以不出现在 delta prices，merge 保留 base，最终 freshness 仍不通过；其余计划 symbol 仍必须出现在 delta prices 并达到目标日。合并会记录 `incremental_merge_*` 字段；它仍然只处理已落地 artifact，不联网、不证明完整全 A 完成。

全 A 增量计划。完整抓取后仍少于阈值的次新股应通过 `prepare_clean_history_pool.py --short-history-output <path> --min-history-rows <rows>` 从已落地 effective history 生成审计清单并显式排除，不能反复抓取或降低 validate 阈值。短历史派生不接受同轮 `--incremental-*` 内存合并，必须先持久化 merge 结果：

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

`prepare_incremental_history_plan.py` 会读取 clean prices 的 `symbol/date` 两列并与 metadata 的 `rows/date_min/date_max` 对账；漂移或重复 symbol metadata 时显式失败。metadata 不存在、`rows <= 0`、`date_max` 为空、失败/空/截断/unprocessed 或少于 `--min-history-rows` 的 symbol 归入 full fetch，有效但 `date_max < target_end_date` 的 symbol 归入 delta fetch；无法解释原因的 `partial_result` 或限流耗尽状态、未清除 invalid rows、缺失 tradestatus 或 `output_written=false` 会直接失败。只有 `source_scope=clean_history_pool` 且带正数剔除原因的审计子集可以保留原始 partial/限流事实并继续。历史池中不属于当前 universe 的旧证券允许保留，但会以 `prices_extra_symbols` 审计。`fetch_buckets[]` 按 `fetch_mode/reason/start_date/end_date` 稳定分组，且必须与 `fetch_symbols` 一一对账；`--max-bucket-symbols` 默认 200，用于限制单次故障和重跑范围。full bucket 的 `start_date` 为空，后续执行器必须显式提供完整历史起始日。`claim_boundary=incremental_history_plan_only_not_history_fetch_success`，因此该文件不能证明抓取成功；后续仍需逐 bucket 抓取并重新验证 metadata。

按 bucket 执行计划：

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/execute_incremental_history_plan.py \
  --plan "$RUN/incremental/incremental_history_plan.json" \
  --provider zzshare \
  --full-start-date "$START_DATE" \
  --output-dir "$RUN/incremental/execution" \
  --resume
```

一次执行只使用一个显式 provider，不自动切源。每个 bucket 分别保存 symbols、prices、metadata、SHA-256 和执行状态；任一命令非零、artifact 缺失、CSV 内容与计划/metadata 不一致或质量门禁失败都会停止并将 manifest 标记为 `partial`。`--resume` 只跳过状态为 complete、execution contract digest 一致且文件摘要和 artifact 校验仍通过的 bucket；计划的生成时间、耗时和吞吐等观测字段不参与 digest。全部 bucket 成功后，聚合 CSV 和 metadata 先写暂存文件再成对发布，失败会保留既有两份最终产物并标记 `failed_stage=aggregate_outputs`。零 bucket 计划显式记录 `no_op=true`、移除陈旧聚合产物，也不允许继续 verified merge。如同时提供 `--base-prices --base-metadata --merged-output --merged-metadata-output --merge-report-output`，入口会调用现有 verified incremental merge；这些参数必须成组提供。

聚合 metadata 的 `requested_symbol_count` 表示本轮计划 symbol 数，`symbol_count` 表示实际产生至少一行可合并历史的 symbol 数；聚合层不得用后者冒充请求数。`partial_result=false` 只表示没有未审计缺口，机器字段 `partial_result_semantics=false_means_no_unaudited_gaps_audited_no_trading_updates_disclosed_separately` 固定该含义。经审计的停牌空更新仍必须读取 `no_trading_update_symbols`，不能把 false 解释为全部 symbol 已产生目标日价格；存在该列表而缺失语义字段时，metadata 必须判为不完整；verified merge 会继续保存该语义字段。

使用 Baostock 执行同一计划时，将依赖改为 `--with baostock`、provider 改为 `baostock`。若同轮 universe artifact 含完整 `symbol/name`，应显式追加 `--baostock-names-input "$RUN/spot.csv" --baostock-missing-name-policy fail`，并按任务边界选择 `--baostock-non-trading-policy reject|drop|keep`。需要让当日全非交易 symbol 保留 base 历史时，必须显式传完整三项组合：`--baostock-non-trading-policy drop`、`--baostock-drop-invalid-rows`、`--baostock-allow-non-trading-empty`；缺少任一项不得放行 empty。该状态单独写入 `no_trading_update_symbols`，不能解释为达到目标日的价格更新。名称输入与 name policy 是独立契约，提供名称输入时 bucket 门禁仍按显式策略处理名称查询失败或缺失。这些输入和策略会进入 execution contract，不会被其他 provider 接受。

zzshare fetch 默认启用有界 429 控制：`--max-429-events 3`、`--max-rate-limit-sleep-seconds 120`、`--max-runtime-seconds 900`。控制器替代 SDK 内部不可控重试，按 `Retry-After` 维护全局 cooldown；预算耗尽时先 flush 当前 checkpoint，再停止调度并以非零退出。metadata 会记录 `rate_limit_429_events`、`rate_limit_sleep_seconds`、`rate_limit_retry_after_seconds`、`rate_limit_budget_exhausted`、`rate_limit_exhaustion_reason` 和 `unprocessed_symbols`。未调度 symbol 不得计为真实空结果，也不得自动切换数据源。

本地 clean prices 最终评分时，`run_today_a_share_selection.py --prices-input ... --spot-input ... --filter-prices-to-spot-universe --min-symbol-latest-date "$END_DATE"` 会在 validate/score 前过滤当前 universe 外和最新日期过期的 symbol，并写出 `prices_filter.json`、summary/stdout 字段和 CSV provenance。过滤证据还记录 input、spot、kept 和 removed 四个规范化 symbol 集合的 SHA-256。需要把 clean-pool lineage 接入最终 breadth 门禁时，再显式加 `--full-a-provenance <full_a_clean_pool_provenance.json>`；证明中的 `clean_prices`/`universe_input` 必须与本轮两个输入路径完全一致，`--min-symbol-latest-date` 必须等于证明的 `history.as_of_date`，且不允许 `--plan-only` 或 `--fetch-spot`。runner 评分前只读取 clean/final prices 的 `symbol` 列并重算集合，评分后用已验证 final 集合的数量和哈希要求 diagnostics 精确覆盖、candidates 为其子集；只有上游和最终过滤都零剔除时才允许 `full_market_claim_allowed=true`，该 true 仍不证明价格值、实时行情、模型、成交或收益。评分后对账失败会清理本轮 candidates/diagnostics，删除失败路径记录在 `full_a_provenance_output_cleanup_errors`，不得忽略。大文件场景可显式加 `--prices-filter-output-format parquet`，让过滤后的运行内 prices 直接以 Parquet 进入 validate/score；同时写出 `<prices>.metadata.json` sidecar，记录 SHA-256、size、mtime、row/symbol/date 范围、symbol-set SHA-256、过滤契约和原始 input metadata。后续复用以路径、size 和 SHA-256 校验内容身份，再读取 `symbol/date` 重算表统计并核对 symbol 集合和过滤契约，最后恢复 provenance；mtime 仅作审计，单独触碰时间不会使内容相同的 artifact 失效。sidecar 缺失、摘要不匹配、篡改或统计漂移都显式失败。默认不传时保持输入格式。该步骤不联网、不补数据，只是对既有 artifact 做显式收口。

需要定位评分阶段耗时时，可显式传 `score_candidates.py --profile-output <path>.json`；runner 对应参数为 `run_today_a_share_selection.py --score-profile`，产物固定为运行目录下的 `score_profile.json`。profile 只记录阶段耗时和行数，不参与评分，也不能作为候选、行情完整性或性能提升证明。默认关闭时不写该文件，失败路径会移除陈旧 profile。
