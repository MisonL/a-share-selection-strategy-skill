# REAL-SCENARIO-GATES-2026-05-30

## 范围

本报告记录 2026-05-30 的真实任务场景复验结果。目标是区分已由本地脚本证明的能力和仍受外部环境约束的门禁，避免把 smoke test 误报为真实行情、真实 LightGBM 或真实回测通过。

说明: 文中若出现未带全参数的反引号命令，均为命令摘要，不是可直接复制执行的完整命令；完整命令以本仓库 README、脚本本身或产物目录中的运行记录为准。

## 场景 E: Parquet 输入

状态: 通过。

证据:

- `/tmp/stock-selection-parquet-scenario-e/prices.csv` 与 `/tmp/stock-selection-parquet-scenario-e/prices.parquet` 均可校验和评分。
- 无 `pyarrow` 或 `fastparquet` 时，Parquet 输入显式失败，`validate_ohlcv.py` 和 `score_candidates.py` 均返回非 0。
- 加 `pyarrow` 后，CSV 与 Parquet 输出候选行数一致，关键字段一致。
- 本轮新增 `tests/test_stock_selection_parquet_cli.py`，覆盖 Parquet validate 和 score CLI 路径。
- 当前脚本支持 CSV/Parquet 读取，但输出仍默认是 CSV；如果要让中间产物全程保留 Parquet，必须在每一步输出后显式转换。
- 真实 baostock Parquet 复验产物在 `/tmp/stock-selection-parquet-real-20260530-082339`：6 个代码、3480 行行情从 CSV 转 Parquet 后与原始 CSV 语义一致。
- 同一产物目录中，Parquet 输入完成 validate、slice、LightGBM prediction、QSSS validate 和 score；最终 `candidates.csv` 为 4 行。
- 对最新信号日 `2026-05-29` 执行严格 5 日 buy-hold 回测返回 3，原因是缺少未来 5 个交易行，`incomplete_trades=4`。这是信号日选择导致的未来数据不足门禁，不是 Parquet 读取差异。

边界:

- 该场景只证明本地 Parquet 读取、校验和评分链路，不证明真实行情源可用。

## 场景 G: akshare A 股映射

状态: 外部源可用性不稳定；中文列 `stock_zh_a_hist` 曾通过，本轮复验失败；`stock_zh_a_daily` fallback 在指定复验窗口可用。

证据:

- `uv run --with akshare --with pandas --with numpy` 可安装并导入 akshare `1.18.64`。
- 历史门禁中 `ak.stock_zh_a_hist(symbol="000001", ...)` 成功返回 338 行，样本取 160 行。
- 本轮严格中文列路径在 `/tmp/stock-selection-akshare-current-retry-20260530T092022/` 三次失败，错误为 `RemoteDisconnected`。
- `stock_zh_a_daily(symbol="sz000001", ...)` 在 `/tmp/stock-selection-akshare-alt-20260530T092125/` 复验窗口可用，映射后 177 行，日期范围 `2025-09-01` 到 `2026-05-29`。
- `stock_zh_a_daily` 映射使用 `volume -> volume`、`amount -> amount`、`turnover -> turn`，`validate_ohlcv.py` 返回 0，通用 `score_candidates.py` 返回 0 且候选数为 0。
- 新增 `fetch_akshare_a_share.py`，正式入口优先尝试 `stock_zh_a_hist`，失败或空结果时记录 `fallback_errors` 并转用 `stock_zh_a_daily`。
- 正式入口复验产物在 `/tmp/stock-selection-akshare-cli-real-20260530T093800/`；取数返回 0，metadata 记录 `rows=177`、`symbols[0].provider=stock_zh_a_daily`、`len(fallback_errors)=1`，随后通用校验和评分均返回 0。
- 连续 3 次正式入口复验产物在 `/tmp/akshare-a-share-stability-20260530103633-49722`；三次 `stock_zh_a_hist` 均被远端断开并记录 1 条 `fallback_errors`，三次均 fallback 到 `stock_zh_a_daily`，`rows=177`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`，通用 `validate_ohlcv.py` 均返回 0。
- 当前外部源复验产物在 `/tmp/stock-selection-external-sources-current-20260530T125716/akshare/`；正式入口返回 0，metadata 记录 `rows=177`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`、`symbols[0].provider=stock_zh_a_daily`、`len(fallback_errors)=1`，后续 `validate_ohlcv.py` 和通用 `score_candidates.py` 均返回 0。
- P3 固定总控脚本复验产物在 `/tmp/stock-selection-p3-external-source-stability-20260601T063044Z/`；3 轮 akshare run 均返回 0，`rows=177`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`、`date_max=2026-05-29`，但每轮仍有 1 条 `fallback_errors`，summary 记录 `observation_failed_checks.hist_provider_clean=3`。
- P3 固定总控脚本追加复验产物在 `/tmp/stock-selection-p3-external-20260601T080703Z/`；3 轮 akshare run 均返回 0，`rows=177`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`、`date_max=2026-05-29`，但每轮仍有 1 条 `fallback_errors`，summary 继续记录 `observation_failed_checks.hist_provider_clean=3`。
- P3 固定总控脚本追加复验产物在 `/tmp/stock-selection-p3-external-20260601T094216Z/`；3 轮 akshare run 均返回 0，metadata 均记录 `rows=177`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`、`symbols[0].provider=stock_zh_a_daily`、`symbols[0].date_max=2026-05-29`，但每轮仍有 1 条 `fallback_errors`，summary 继续记录 `observation_failed_checks.hist_provider_clean=3`。
- P3 固定总控脚本 2026-06-01 11:22 UTC 追加复验产物在 `/tmp/stock-selection-p3-external-20260601T112254Z/`；3 轮 akshare run 均返回 0，metadata 均记录 `rows=354`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`，但每轮仍有 2 条 `fallback_errors`，逐 symbol provider 均为 `stock_zh_a_daily` 且 `date_max=2026-05-29`，summary 继续记录 `observation_failed_checks.hist_provider_clean=3`。
- QSSS-derived 校验按预期拒绝 `market=A股`、`000001.SZ`、缺 `prediction_score`、缺 `turn`。
- 补齐外部 `prediction_score` 后，`score_candidates.py` 返回 0，并输出 `prediction_source=external_unverified lightgbm_not_executed_by_this_script=true`。

边界:

- `prediction_score` 是外部补齐值，本仓库仍未验证真实 LightGBM prediction 生成链路。
- `stock_zh_a_daily` 当前成功只证明替代日线接口可进入通用校验和评分，不证明 `stock_zh_a_hist` 稳定可用。
- 连续 3 次 fallback 成功只证明当前窗口内可用，不证明 akshare 长期稳定。
- `成交额` 或 `amount` 只能作为可选 `amount` 字段，不得映射为 `volume`。

## 场景 I: yfinance 美股映射

状态: 外部源可用性不稳定；同日既复现 Yahoo/TLS 失败，也有一次干净 README 路径成功拉取。

证据:

- yfinance 拉取 AAPL/MSFT 的首次尝试被超时终止，退出码 143。
- 受控重试退出码 20。
- 关键错误包括 `curl: (28) Connection timed out`、`curl: (35) TLS connect error`、`MSFT: possibly delisted; no price data found`。
- 最终只生成 `/tmp/stock-selection-yfinance-scenario-i/yfinance_error.json`，未生成 `generic_ohlcv_aapl_msft.csv` 或 `scored_candidates.csv`。
- 对缺失 CSV 运行 `validate_ohlcv.py` 和 `score_candidates.py` 均返回 2，错误明确为 input file not found。
- 新一轮 yfinance 真实网络测试产物在 `/tmp/stock-selection-yfinance-current/`；`uv run --with yfinance --with pandas --with numpy python /tmp/stock-selection-yfinance-fetch.py` 返回 1。
- yfinance stderr 包含 `curl: (28) Connection timed out after 30002 milliseconds`，AAPL/MSFT 均失败，metadata 记录 raw shape 为 `0 x 12`，未生成可验证 CSV。
- 直连 Yahoo chart API 探针也返回 1，AAPL/MSFT 均在 HTTPS handshake 阶段 30 秒超时，错误为 `_ssl.c:1063: The handshake operation timed out`。
- 本轮复验产物在 `/tmp/stock-selection-yfinance-current-20260530T084650/`；yfinance AAPL/MSFT 取数返回 1，错误包括 `curl: (28) Connection timed out after 30002 milliseconds`、`curl: (35) TLS connect error`、`yfinance returned empty dataframe for symbols=['AAPL', 'MSFT']`，未生成 `aapl_msft_ohlcv.csv`。
- 同一目录的 Yahoo chart API 直连探针返回 1；AAPL 为 `UNEXPECTED_EOF_WHILE_READING`，MSFT 为 handshake timeout。
- 新增正式入口后，`fetch_yfinance_ohlcv.py --symbols AAPL,MSFT --start-date 2024-01-01 --end-date 2026-05-29 --fail-on-fetch-error` 在 `/tmp/stock-selection-yfinance-cli-real-20260530T091000/` 返回 3，耗时 59.47 秒，写出空 CSV 和 metadata。
- 该 metadata 记录 `rows=0`、`symbol_count=0`、`len(failed_symbols)=2`、`empty_symbols=['AAPL','MSFT']`，错误为 Yahoo TLS connect error；对空 CSV 运行 `validate_ohlcv.py` 返回 1，运行 `score_candidates.py` 返回 2。
- README 干净路径复验产物在 `/tmp/stock-selection-readme-clean-20260530T091810/us/`；yfinance 命令用 60 秒外部超时包裹后成功，metadata 记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`。
- 新增脚本内 `--timeout-seconds` 后，受控复验产物在 `/tmp/stock-selection-yfinance-current-20260530T095106/`；`--timeout-seconds 10` 取数返回 0，耗时 2.592 秒，metadata 记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`。
- 同一产物的 `validate_ohlcv.py` 返回 0，`score_candidates.py` 返回 0，候选数为 0，stderr 提示缺少 `turn/turnover` 时通用模式使用 neutral turnover 序列。
- 连续 3 次受控复验产物在 `/tmp/stock-selection-yfinance-repeat-20260530T100324/`；三次 fetch 均返回 0，耗时分别为 2.644 秒、2.006 秒、1.738 秒，metadata 均记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`，后续校验和评分均返回 0。
- 再次连续 3 次受控复验产物在 `/tmp/stock-selection-yfinance-stability-20260530T111830-76636/`；三次 `fetch_yfinance_ohlcv.py`、通用 `validate_ohlcv.py` 和通用 `score_candidates.py` 均返回 0，metadata 均记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`。
- 当前外部源复验产物在 `/tmp/stock-selection-external-sources-current-20260530T125716/yfinance/`；`fetch_yfinance_ohlcv.py --timeout-seconds 10` 返回 0，metadata 记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`，后续 `validate_ohlcv.py` 和通用 `score_candidates.py` 均返回 0。
- P3 固定总控脚本复验产物在 `/tmp/stock-selection-p3-external-source-stability-20260601T063044Z/`；3 轮 yfinance run 均返回 0，metadata 均记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max` 均为 `2026-05-28`。
- P3 固定总控脚本追加复验产物在 `/tmp/stock-selection-p3-external-20260601T080703Z/`；3 轮 yfinance run 均返回 0，metadata 均记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max` 均为 `2026-05-28`。
- P3 固定总控脚本追加复验产物在 `/tmp/stock-selection-p3-external-20260601T094216Z/`；3 轮 yfinance run 均返回 0，metadata 均记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max` 均为 `2026-05-28`。
- P3 固定总控脚本 2026-06-01 11:22 UTC 追加复验产物在 `/tmp/stock-selection-p3-external-20260601T112254Z/`；3 轮 yfinance run 均返回 0，metadata 均记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max` 均为 `2026-05-28`。

边界:

- 本场景证明 yfinance 当前环境存在波动，不应把单次成功或失败推广为稳定可用性结论。
- 多轮连续 3 次成功只证明当前窗口内指定参数可用，不证明 Yahoo 源长期稳定可用。
- `--timeout-seconds` 只限制每票 yfinance history 拉取等待时间，不能证明 Yahoo 源稳定可用。
- yfinance 只满足通用 OHLCV；若用于 QSSS-derived，仍需外部补齐 `market=A-share`、真实上游 `prediction_score` 和 `turn` 或 `turnover`。
- 本轮新增 `fetch_yfinance_ohlcv.py` 作为正式联网入口；单元测试只覆盖字段映射、`Close` 口径、metadata 和空结果严格失败，不替代真实 Yahoo 网络门禁。

## 场景 L: LightGBM prediction 生成

状态: 合成 demo 真模型链路通过；baostock 真实行情生成链路已有 2-symbol 最新日和 12-symbol/3 信号日证据；仍不代表全市场训练质量。

证据:

- 本轮新增 `scripts/generate_lightgbm_predictions.py`，独立生成 `prediction_score`，并在缺少 `lightgbm` 或 `scikit-learn` 时非 0 退出。
- 生成器使用时间序列切分，不使用随机 `train_test_split`。
- `StandardScaler` 只在训练切分上 `fit`。
- 标签口径为 `close.shift(-horizon) / close - 1`，训练标签阈值只来自训练切分。
- 本轮新增 `tests/test_lightgbm_prediction_cli.py`，覆盖训练切分、输出概率范围、依赖缺失失败，以及生成结果可继续进入 QSSS-derived 评分消费层。
- 本地真实依赖复验已通过: `uv run --with-requirements requirements-ml.txt python scripts/generate_lightgbm_predictions.py --input /tmp/stock-selection-ml-local/prices.csv --output /tmp/stock-selection-ml-local/prices_generated_prediction.csv` 返回 0。
- 生成结果继续通过 `validate_ohlcv.py --config scripts/qsss_profile_config.json`，再进入 `score_candidates.py --config scripts/qsss_profile_config.json`，最终 `scored_symbols=2`、`candidates=1`。
- 本次合成 demo 的 `prediction_score` 范围为 `0.0107376151670856` 到 `0.9479974705646024`，生成器 stderr 为空。
- 2026-06-01 真实 SSE603 late-window 复验产物在 `/tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z/`；6 个信号日的 `prediction_summary.json` 均记录 `raw_symbols=40`、`predicted_symbols=40`、`skipped_symbols=0`，并包含 `feature_columns`、`split_method=time_series_train_prefix`、`scaler_fit_scope=train_split_only`、`label_definition=target_return = close.shift(-horizon) / close - 1; class = target_return > train_mean`、`prediction_scope=latest_probability_repeated_for_scoring`、训练日期窗口和正负训练标签计数。
- 同一 SSE603 真实产物的 summary 字段只证明 40-symbol/6 信号日生成链路可审计；当前代码生成的 `prediction_summary.json` 不包含已计算的 holdout AUC/IC、概率校准、分层收益、跨窗口稳定性、跨年份或分市场样本外统计，新增 `model_quality_metrics` 只会把这些边界标记为 `not_computed`、`not_evaluated` 或 `not_proven`，也不证明逐信号日独立预测质量或全市场泛化。

边界:

- 单元测试使用受控假模型验证契约；合成 demo 使用真实 LightGBM 依赖验证运行链路，但仍不等同于真实 A 股行情上的训练结果。
- 2-symbol、12-symbol 和 40-symbol baostock 证据只证明当前生成器能在有限真实行情样本上运行，并接入 `validate_ohlcv.py --config scripts/qsss_profile_config.json` 与 `score_candidates.py`；`model_quality_scope=generation_audit_only` 不证明概率校准、holdout AUC/IC、分层收益、跨窗口稳定性、逐信号日独立预测质量或全市场样本外泛化能力。

## 场景 M: buy-hold 基线回测

状态: 本地契约门禁已建立；baostock 真实候选和真实 OHLCV 已进入 12-symbol/3 信号日 close-to-close 基线回测；新增 round-trip bps 成本/滑点扣减和等权资金曲线，但仍不代表完整策略回测。

证据:

- 本轮新增 `scripts/backtest_buy_hold.py`。
- 脚本只做信号日收盘价到未来第 N 个可用交易行收盘价的 close-to-close buy-hold 基线。
- 候选日期必须精确匹配 OHLCV 日期，不自动滚动到下一交易日。
- 输出显式标记 `cost_model=round_trip_bps`、`slippage_model=round_trip_bps`；未启用回测级可交易门禁时 `tradability_model=not_modeled`，启用 `--require-tradable-bars` 时为 `tradestatus_entry_exit_only`，启用 `--require-tradable-holding-period` 时为 `tradestatus_holding_period_bars`；`limit_rules_model` 始终为 `not_modeled`。
- `--cost-bps` 和 `--slippage-bps` 只按 round-trip bps 从 `gross_return` 中扣减，并额外输出 `cost_bps`、`slippage_bps` 和扣减后的 `return`。
- 本轮新增 `tests/test_buy_hold_backtest_cli.py`，覆盖正常收益、缺入场日不回退、严格模式遇到缺数据非 0 且不写输出。
- 本轮测试补充覆盖 `cost_bps=12.5`、`slippage_bps=7.5` 时 `return = gross_return - 0.002`，以及负成本或负滑点显式失败。
- 本地合成 demo 完成路径已通过: 先用 180 日行情切出截至 `2025-07-31` 的信号窗口生成候选，再用完整行情运行 `backtest_buy_hold.py --hold-days 5`，输出 `completed_trades=2`、`incomplete_trades=0`。
- 本次合成 demo 的回测收益范围为 `0.0059836162887334` 到 `0.0071089378908271`。
- 真实 `/tmp/stock-selection-ashare-scan-20260530-032723/` 中的旧回测 CSV 只是 historical/no-cost baseline，字段值为 `cost_model=excluded`、`slippage_model=excluded`；成本/滑点证据以 `/tmp/stock-selection-backtest-costs-20260530T101000/` 和后续 sizing 复跑产物为准。
- 使用同一 12-symbol/3 信号日产物复跑 round-trip bps 回测，产物在 `/tmp/stock-selection-backtest-costs-20260530T101000/`；三次命令均返回 0，`cost_bps=10.0`、`slippage_bps=5.0`、`incomplete_trades=0`。
- 成本/滑点复跑结果显示每笔 `return = gross_return - 0.0015`；`2026-05-12` 净收益范围为 `-0.084328` 到 `-0.023832`，`2026-05-15` 为 `-0.034293` 到 `-0.013157`，`2026-05-20` 为 `-0.019537` 到 `-0.001379`。
- 新增 `portfolio_equity_curve.py`，读取一个或多个回测 CSV，只使用 `status=complete` 且 `missing_data=false` 的交易，按信号日等权平均 `return` 并复利生成 `equity`、`running_peak`、`drawdown`。
- 使用真实 12-symbol/3 信号日成本/滑点回测产物生成资金曲线，产物在 `/tmp/stock-selection-equity-curve-20260530T102617/`；命令返回 0，`periods=3`、`positions=15`、`incomplete_trades=0`、`final_equity=0.9191547145201625`、`total_return=-0.08084528547983749`、`max_drawdown=-0.08084528547983749`。
- 真实资金曲线的等权平均净收益为 `2026-05-12=-0.043135064458`、`2026-05-15=-0.027106257927`、`2026-05-20=-0.012646729332`；最大回撤区间为 `START -> 2026-05-20`。
- `portfolio_equity_curve.py` 新增 `--min-final-equity` 和 `--max-drawdown-floor`。真实成本/滑点回测产物复验在 `/tmp/stock-selection-equity-threshold-gate-20260530T104740/`；设置 `min-final-equity=0.95` 和 `max-drawdown-floor=-0.05` 返回 3 且不写失败输出，设置 `0.90/-0.10` 返回 0 并写出资金曲线。
- `backtest_buy_hold.py` 新增 `--require-tradable-bars`，打开后要求入场和退出 bar 都有 `tradestatus=1`；缺列、入场不可交易或退出不可交易会转为 incomplete，并可被 `--fail-on-incomplete` 拦截。
- `backtest_buy_hold.py` 新增 `--require-tradable-holding-period`，打开后会同时要求价格表内入场到退出的已观测 bar 都有 `tradestatus=1`；中间持有期已存在价格行不可交易时返回 `missing_reason=non_tradable_holding_period`，模型口径为 `tradestatus_holding_period_bars`。
- 回测级 `tradestatus` 门禁复验产物在 `/tmp/stock-selection-backtest-tradability-gate-20260530T111018/`；含 `tradestatus` 的 000001/600000 真实价格返回 0 且 `completed_trades=2`，旧 12-symbol 真实价格因缺 `tradestatus` 返回 3 且不写输出，`missing_reason_counts=missing_tradestatus:7`。
- 当前代码复跑产物在 `/tmp/stock-selection-backtest-tradability-current-20260530T124812/`；baostock 000001/600000 短窗口取数 36 行，`non_trading_rows=0`、`tradestatus_missing_rows=0`，启用 `--require-tradable-bars --fail-on-incomplete` 返回 0，回测 CSV 记录 `tradability_model=tradestatus_entry_exit_only` 且 `limit_rules_model=not_modeled`。
- 2026-06-01 本地契约测试补充覆盖新旧口径差异：旧 `--require-tradable-bars` 遇到中间持有期 `tradestatus=0` 仍保持 complete；新 `--require-tradable-holding-period` 遇到同一场景转为 incomplete，stdout 披露 `tradability_model=tradestatus_holding_period_bars` 和 `missing_reason_counts=non_tradable_holding_period:1`。focused 命令 `PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy python -m unittest tests.test_buy_hold_backtest_cli tests.test_baostock_walk_forward_runner tests.test_cli_help_without_dependencies -v` 返回 0，`Ran 23 tests ... OK`。
- 历史只读字段审查确认 `/tmp/stock-selection-ashare-scan-20260530-032723/prices.csv` 有 OHLCV 和 `turn`，但没有 `tradestatus`、`suspended`、`is_trading`、`limit_status`、`up_limit`、`down_limit`、`pre_close` 等字段；候选和回测产物也没有可交易/停牌/涨跌停字段。
- 只读并发持仓审查确认 `/tmp/stock-selection-backtest-costs-20260530T101000/` 的 15 笔真实 complete 交易最大同时打开 12 笔，发生在 `2026-05-15`、`2026-05-18`、`2026-05-19`；同一 symbol 跨信号日重复持仓冲突共有 21 个 `date-symbol` 组合，涉及 `002594`、`300059`、`300750`、`601318`、`000333`。
- 新增 `portfolio_overlap_report.py`，读取多个回测 CSV，按 business-day 闭区间统计 `daily_open_positions`、`max_open_positions`、同标的重叠和资金字段可验证性。该 business-day 闭区间不是 A 股交易所日历、节假日、停复牌或全持有期真实可交易性门禁。
- 真实并发门禁复验产物在 `/tmp/stock-selection-overlap-gate-20260530T112415/`；对三份真实成本/滑点回测设置 `--max-open-positions 10 --fail-on-symbol-overlap --require-capital-fields` 返回 3，并写出 `daily.csv`、`overlap.csv` 和 `summary.json`。summary 记录 `trades=15`、`complete_trades=15`、`max_open_positions=12`、`same_symbol_overlap_rows=21`、`cash_capacity_verifiable=false`、`capital_fields_missing=weight,notional,quantity,cash_reserved`。
- 新增候选资金字段透传和 `--max-gross-weight` 权重容量门禁。复验产物在 `/tmp/stock-selection-capacity-gate-20260530T114644/`；基于同一真实 12-symbol/3 信号日候选和价格，额外写入测试用等权 `weight/notional/quantity/cash_reserved` 后复跑回测。
- 同一复验中，`--max-gross-weight 1.0 --require-capital-fields` 返回 3，并写出 `summary_fail.json`；`--max-gross-weight 3.0 --require-capital-fields` 返回 0。summary 记录 `capital_fields_present=weight,notional,quantity,cash_reserved`、`capital_fields_missing=[]`、`cash_capacity_verifiable=true`、`weight_capacity_verifiable=true`、`max_gross_weight=2.0`、`max_gross_weight_dates=2026-05-20,2026-05-21,2026-05-22`。
- 新增 `--max-gross-notional` 和 `--max-cash-reserved` 金额容量门禁。复验产物在 `/tmp/stock-selection-cash-capacity-gate-20260530T120429/`；使用同一测试用资金字段回测产物，`--max-gross-notional 1000000 --max-cash-reserved 1000000` 返回 3，`--max-gross-notional 3000000 --max-cash-reserved 3000000` 返回 0。
- 金额容量复验的失败 summary 记录 `max_gross_notional=2000000.0`、`max_cash_reserved=2000000.0`，二者最大日期均为 `2026-05-15,2026-05-18,2026-05-19,2026-05-20,2026-05-21,2026-05-22`；stderr 包含 `max_gross_notional=2000000.0 limit=1000000.0` 和 `max_cash_reserved=2000000.0 limit=1000000.0`。
- 新增 `allocate_candidate_capital.py`，按 `symbol+date` 精确连接候选和价格，用信号日 close、`cash_budget` 和 `lot_size` 生成 `quantity/notional/cash_reserved/weight`，模型标记为 `equal_cash_budget_lot_floor`。
- sizing 真实复验产物在 `/tmp/stock-selection-sizing-gate-verify-20260530T122929/`；同一 12-symbol/3 信号日候选分别用 `cash_budget=1000000`、`lot_size=100` 生成 sized candidates，三日 `allocated_candidates` 分别为 7、5、3，`unallocated_candidates=0`，`total_cash_reserved` 分别为 `961321.0`、`959281.0`、`987871.0`。
- sizing 产物继续进入回测和容量门禁；严格阈值 `--max-gross-weight 1.0 --max-gross-notional 1000000 --max-cash-reserved 1000000` 返回 3，宽松阈值 `3.0/3000000/3000000` 返回 0。失败 summary 记录 `max_gross_weight=1.9471519999999998`、`max_gross_notional=1947152.0`、`max_cash_reserved=1947152.0`。

边界:

- 成本和滑点只是简单 round-trip bps 扣减；资金曲线只是按信号日等权复利已完成交易。sizing 脚本让仓位字段来源可追溯，但它仍只是本地 equal-cash/lot-floor 模型，不代表真实订单成交、券商容量、涨跌停可买入或全市场策略质量。
- 新 baostock 取数入口和 `--require-tradable-bars` 可拒绝 entry/exit 的 `tradestatus != 1`，`--require-tradable-holding-period` 可拒绝价格表内已观测持有期 bar 的 `tradestatus != 1`，但回测仍不补全真实交易所日历或判断涨跌停状态；因此 `limit_rules_model=not_modeled` 仍必须保留。
- 已有 12-symbol/3 信号日真实候选 CSV 与真实 OHLCV 运行记录；仍需要更大股票池、更多时间段和真实交易约束复验后，才能评价策略质量。

## 场景 U: baostock A 股全链路

状态: 2-symbol 最新日 smoke 已通过；12-symbol/3 信号日 baostock close-to-close 基线链路通过；baostock 无效 OHLCV 与 `tradestatus` 不可交易行门禁已补强。

证据:

- `fetch_baostock_a_share.py --symbols 000001,600000 --start-date 2024-01-01 --end-date 2026-05-29 --adjust 3` 返回 0。
- 输出 `/tmp/stock-selection-baostock-script-local/prices.csv` 共 1160 行、2 个 symbol；每只股票 580 行，日期范围为 `2024-01-02` 到 `2026-05-29`。
- 原始行情直接跑 `validate_ohlcv.py --config scripts/qsss_profile_config.json` 返回 1，错误为缺少 `prediction` 或 `prediction_score`，符合 QSSS-derived 门禁预期。
- `generate_lightgbm_predictions.py --summary-output /tmp/stock-selection-baostock-script-local/prediction_summary.json` 返回 0，`predicted_symbols=2`、`skipped_symbols=0`，stderr 为空。
- 真实 baostock 行情生成的 `prediction_score` 范围为 `0.3380476516805921` 到 `0.7682771131802957`；summary 记录 `000001` 和 `600000` 的 `train_rows=364`。
- 生成结果通过 `validate_ohlcv.py --config scripts/qsss_profile_config.json`，再进入 QSSS-derived 评分，输出 `scored_symbols=2`、`candidates=1`、`threshold_failures=min_prediction_score:1`。
- 使用 `slice_prices_as_of.py --as-of-date 2026-05-20` 截断信号窗口后重新生成 prediction 和评分，strict QSSS 评分返回 3，`effective_empty_result=true`，原因是 `threshold_filtered_all`。这说明信号日防泄漏协议生效，且当前真实两票在该信号日没有可进入回测的 QSSS 候选。
- 为单独验证回测脚本与真实 OHLCV 的兼容性，人工构造 `2026-05-20` 候选后运行 `backtest_buy_hold.py --hold-days 5 --fail-on-incomplete` 返回 0，`completed_trades=2`、`incomplete_trades=0`，收益范围为 `-0.0009285051067781` 到 `0.0548098434004473`。
- 新一轮 12-symbol 真实扫描产物在 `/tmp/stock-selection-ashare-scan-20260530-032723`，代码覆盖 `00/002/300/600/601/603/688` 前缀: `000001,000333,000651,002594,300059,300750,600000,600036,600519,601318,603288,688111`。
- 12-symbol baostock 抓取返回 0，输出 6960 行，`failed_symbols=0`。
- 信号日 `2026-05-12` 执行 fetch、slice、predict、validate、score、backtest 全部返回 0，真实 QSSS 候选 7 个，`incomplete_trades=0`，5 日收益范围为 `-0.082828` 到 `-0.022332`。
- 信号日 `2026-05-15` 执行 fetch、slice、predict、validate、score、backtest 全部返回 0，真实 QSSS 候选 5 个，`incomplete_trades=0`，5 日收益范围为 `-0.032793` 到 `-0.011657`。
- 信号日 `2026-05-20` 执行 fetch、slice、predict、validate、score、backtest 全部返回 0，真实 QSSS 候选 3 个，`incomplete_trades=0`，5 日收益范围为 `-0.018037` 到 `0.000121`。
- 本轮真实 `688981` 复验产物在 `/tmp/stock-selection-baostock-invalid-real-20260530-688981/`；`fetch_baostock_a_share.py --symbols 688981 --start-date 2020-07-16 --end-date 2026-05-29 --adjust 3 --fail-on-fetch-error` 返回 3。
- 该 fetch 输出 `ERROR: strict gate failed; invalid_rows=6 output_written=true`；metadata 路径为 `metadata_688981_20200716_20260529.json`，关键字段为 `raw_rows=1422`、`rows=1422`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=6`、`dropped_invalid_rows=0`。
- 6 行无效行均来自真实 baostock 返回，日期为 `2025-09-01`、`2025-09-02`、`2025-09-03`、`2025-09-04`、`2025-09-05`、`2025-09-08`，字段 `volume/amount/turn` 为空。
- 同一 fetch CSV 运行 `validate_ohlcv.py` 返回 1，错误包含 `column volume has 6 missing values` 和 `column volume has 6 non-numeric values`；运行 `slice_prices_as_of.py --as-of-date 2025-09-08` 返回 2 且不写 sliced 输出。
- 该反馈已转化为 `fetch_baostock_a_share.py` metadata 质量门禁: 默认报告 `invalid_rows` 并非 0 退出，只有显式 `--drop-invalid-rows` 才允许丢弃并记录 `dropped_invalid_rows`。
- 受控复验产物在 `/tmp/stock-selection-ashare-current-20260530T095205/`；默认严格 fetch 仍返回 3，`invalid_rows=6`、`dropped_invalid_rows=0`，显式 `--drop-invalid-rows` 后返回 0，`raw_rows=1422`、`rows=1416`、`dropped_invalid_rows=6`，清洗后 validate 返回 0。
- 只读字段探测产物在 `/tmp/stock-selection-baostock-field-probe-20260530/`；baostock 日 K 对 `preclose`、`pctChg`、`tradestatus`、`isST`、`turn`、`volume`、`amount` 返回成功，对 `up_limit`、`down_limit`、`limit_status`、`is_trading`、`suspended` 返回 `10004012` 参数错误。
- 新增 `stock_selection_tradability.py`，并让 `fetch_baostock_a_share.py` 输出 `preclose/pctChg/tradestatus/isST`。metadata 同时记录 raw 与输出侧的 `non_trading_rows`、`tradestatus_missing_rows`、`st_rows` 和示例。
- 新门禁复验产物在 `/tmp/stock-selection-baostock-tradability-gate-20260530T104739/`；688981 短窗口严格 fetch 返回 3，metadata 为 `raw_rows=15`、`invalid_rows=6`、`raw_non_trading_rows=6`、`non_trading_rows=6`、`tradestatus_missing_rows=0`，错误包含 `invalid_rows=6; non_trading_rows=6`。
- 同一短窗口显式 `--drop-invalid-rows` 后返回 0，metadata 为 `rows=9`、`dropped_invalid_rows=6`、`raw_non_trading_rows=6`、`non_trading_rows=0`；用 `validate_ohlcv.py --min-history-rows 1` 校验返回 0。默认校验返回 1 是因为短窗口只有 9 行，低于 120 行历史门槛。
- 正常长窗口复验产物在 `/tmp/stock-selection-baostock-tradability-normal-20260530T104829/`；000001/600000 取数返回 0，metadata 记录 `rows=354`、`symbol_count=2`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`，默认 `validate_ohlcv.py` 返回 0。
- P3 固定总控脚本复验产物在 `/tmp/stock-selection-p3-external-source-stability-20260601T063044Z/`；3 轮 baostock run 均返回 0，metadata 均记录 `rows=1160`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`，000001/600000 的 `date_max` 均为 `2026-05-29`。
- P3 固定总控脚本追加复验产物在 `/tmp/stock-selection-p3-external-20260601T080703Z/`；3 轮 baostock run 均返回 0，metadata 均记录 `rows=1160`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`，000001/600000 的 `date_max` 均为 `2026-05-29`。
- P3 固定总控脚本追加复验产物在 `/tmp/stock-selection-p3-external-20260601T094216Z/`；3 轮 baostock run 均返回 0，metadata 均记录 `rows=1160`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`，000001/600000 的 `date_max` 均为 `2026-05-29`。
- P3 固定总控脚本 2026-06-01 11:22 UTC 追加复验产物在 `/tmp/stock-selection-p3-external-20260601T112254Z/`；命令使用 `probe_external_source_stability.py --iterations 3 --akshare-symbols 000001,600000 --yfinance-symbols AAPL,MSFT --baostock-symbols 000001,600000`，返回 0。summary 记录 `total_runs=9`、`passed_runs=9`、`all_sources_all_iterations_passed=true`、`long_term_stability_claim=not_proven`。
- 同一 P3 追加复验中，akshare 3 轮均返回 0，metadata 每轮为 `rows=354`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`，但每轮 `fallback_errors=2` 且 summary 记录 `observation_failed_checks.hist_provider_clean=3`；逐 symbol provider 均为 `stock_zh_a_daily`，`date_max=2026-05-29`。这只能说明 fallback provider 在本次窗口可用，不能写成 `stock_zh_a_hist` 主接口稳定。
- 同一 P3 追加复验中，yfinance 3 轮均返回 0，metadata 每轮为 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max=2026-05-28`。baostock 3 轮均返回 0，metadata 每轮为 `rows=1160`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`，000001/600000 的 `date_max=2026-05-29`。
- P3 固定总控脚本 2026-06-01 12:37 UTC 追加复验产物在 `/tmp/stock-selection-p3-external-20260601T123704Z/`；命令使用 `probe_external_source_stability.py --iterations 3 --akshare-symbols 000001,600000 --yfinance-symbols AAPL,MSFT --baostock-symbols 000001,600000`，返回 0。summary 记录 `total_runs=9`、`passed_runs=9`、`all_sources_all_iterations_passed=true`、`long_term_stability_claim=not_proven`、`sources.akshare.observation_failed_checks.hist_provider_clean=3`。
- 同一 12:37 UTC P3 复验中，akshare 3 轮均返回 0，metadata 每轮为 `rows=354`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`、`fallback_errors=2`；逐 symbol provider 均为 `stock_zh_a_daily`，`date_max=2026-05-29`。yfinance 3 轮均返回 0，metadata 每轮为 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max=2026-05-28`，不能写成已覆盖请求 `end_date=2026-05-29`。baostock 3 轮均返回 0，metadata 每轮为 `rows=1160`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`，000001/600000 的 `date_max=2026-05-29`。
- P3 固定总控脚本 2026-06-01 13:33 UTC 追加复验产物在 `/tmp/stock-selection-p3-external-20260601T133324Z/`；命令使用 `probe_external_source_stability.py --iterations 3 --akshare-symbols 000001,600000 --yfinance-symbols AAPL,MSFT --baostock-symbols 000001,600000`，返回 0。summary 记录 `total_runs=9`、`passed_runs=9`、`all_sources_all_iterations_passed=true`、`long_term_stability_claim=not_proven`、`sources.akshare.observation_failed_checks.hist_provider_clean=3`。
- 同一 13:33 UTC P3 复验中，akshare 3 轮均返回 0，metadata 每轮为 `rows=354`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`、`fallback_errors=2`；逐 symbol provider 均为 `stock_zh_a_daily`，`date_max=2026-05-29`。yfinance 3 轮均返回 0，metadata 每轮为 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`、`adjustment=auto_adjust_false_close`，AAPL/MSFT 的 `date_max=2026-05-28`，仍不能写成已覆盖请求 `end_date=2026-05-29`。baostock 3 轮均返回 0，metadata 每轮为 `rows=1160`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`，000001/600000 的 `date_max=2026-05-29`。
- 涨跌停只读探测产物在 `/tmp/stock-selection-limit-rule-probe-20260530T105951/`；000001、600000、300750、688981 窗口样例显示可用 `preclose/pctChg/isST` 做理论候选研究，但没有直接 `up_limit/down_limit/limit_status` 字段，也未发现可证明规则实现的精确涨跌停样例。
- current-code walk-forward 复验产物在 `/tmp/stock-selection-oos-20260530T130952/`；重新用当前 baostock 入口拉取同一 12-symbol 固定池，metadata 为 `rows=6960`、`symbol_count=12`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。
- 同一复验固定信号日 `2026-05-12/2026-05-15/2026-05-20`、`hold_days=5`、`cost_bps=10`、`slippage_bps=5`，逐日信号窗口截断、LightGBM 生成、QSSS 评分、sizing 和 `--require-tradable-bars --fail-on-incomplete` 回测均返回 0。
- 三个信号日 `raw_symbols=12`、`predicted_symbols=12`、`skipped_symbols=0`；候选数分别为 7、5、3，completed trades 分别为 7、5、3，`incomplete_trades=0`，回测输出 `tradability_model=tradestatus_entry_exit_only` 且 `limit_rules_model=not_modeled`。
- 资金曲线返回 0，`final_equity=0.9191547145201625`、`total_return=-0.08084528547983749`、`max_drawdown=-0.08084528547983749`；该小样本未证明正收益。
- 组合严格门禁返回 3 并写出报告，原因是 `max_open_positions=12 > 10`、`max_gross_weight=1.9471519999999998 > 1.0`、`max_gross_notional=1947152.0 > 1000000.0`、`max_cash_reserved=1947152.0 > 1000000.0`、`same_symbol_overlap_rows=21`。该失败是有效风险暴露，不应通过放宽阈值改写为成功。
- 新增 `summarize_walk_forward_run.py`，用于把真实 walk-forward 运行目录汇总为 JSON，并自动检查 metadata、prediction skipped、候选数、incomplete trades、资金曲线和组合门禁；已对 `/tmp/stock-selection-oos-20260530T130952/` 生成 `qsss_run_summary.json`，返回 0，`quality_errors=0` 且记录 5 个组合门禁 violation。后续 P1 扩大复验必须优先生成该摘要，减少人工抄写误差。
- P1 四信号日扩展复验产物在 `/tmp/stock-selection-p1-qsss-12sym-4d-20260530T133043/`；固定 12-symbol 池身份已核对为 `000001,000333,000651,002594,300059,300750,600000,600036,600519,601318,603288,688111`，metadata 为 `rows=6960`、`symbol_count=12`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。
- 同一复验显式传入信号日 `2026-04-24/2026-05-12/2026-05-15/2026-05-20`；fetch、slice、predict、validate、score、size、backtest、equity、summary 均返回 0，overlap 严格门禁返回 3 并写出 summary。`qsss_run_summary.json` 记录 `signals=4`、`candidates=20`、`completed_trades=20`、`incomplete_trades=0`、`quality_errors=0`、`portfolio_violations=5`。
- 四信号日候选数分别为 `2026-04-24=5`、`2026-05-12=7`、`2026-05-15=5`、`2026-05-20=3`；四日均为 `raw_symbols=12`、`predicted_symbols=12`、`skipped_symbols=0`、`tradability_model=tradestatus_entry_exit_only`、`limit_rules_model=not_modeled`。
- 四信号日资金曲线为 `periods=4`、`positions=20`、`final_equity=0.9349716121129314`、`total_return=-0.06502838788706855`、`max_drawdown=-0.0808452854798374`；组合 violation 仍为 `max_open_positions=12 > 10`、`max_gross_weight=1.9471519999999998 > 1.0`、`max_gross_notional=1947152.0 > 1000000.0`、`max_cash_reserved=1947152.0 > 1000000.0`、`same_symbol_overlap_rows=21`。
- P2a baostock 涨跌停字段探测已脚本化，报告见 `docs/reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md`；产物在 `/tmp/stock-selection-p2a-limit-field-probe-20260530T135328/`，`supported_candidate_fields=[]`、`unsupported_candidate_fields=up_limit,down_limit,limit_status,is_trading,suspended`、错误码均为 `10004012`，`available_control_fields=preclose,pctChg,tradestatus,isST,turn,volume,amount`。2026-06-01 11:12 UTC 严格复验产物在 `/tmp/stock-selection-p2a-limit-field-refresh-20260601T111205Z/`，`supported_direct_limit_fields=[]`、`direct_limit_field_available=false`、`supported_trading_state_fields=[]`、`provider_error_fields=[]`、`control_rows=364`、`rule_inference_performed=false`、`limit_rules_model=not_modeled`。2026-06-01 12:45 UTC 完整控制字段严格复验产物在 `/tmp/stock-selection-p2a-limit-field-refresh-20260601T124503Z/`，返回 3，`provider_error_fields=turn,volume,amount`，不能写成严格通过；2026-06-01 12:46 UTC 核心控制字段严格复验产物在 `/tmp/stock-selection-p2a-limit-field-core-20260601T124601Z/`，返回 0，`supported_direct_limit_fields=[]`、`direct_limit_field_available=false`、`provider_error_fields=[]`、`control_rows=208`、`rule_inference_performed=false`、`limit_rules_model=not_modeled`。
- 新增 `run_baostock_walk_forward.py` 一键 runner 后，P1 固定 12-symbol/4 信号日复验产物在 `/tmp/stock-selection-p1-runner-20260530T140916/`；runner 从 fetch 到 summary 共记录 28 个步骤到 `run_manifest.json`，其中只有 `portfolio_overlap` 返回 `3` 且允许返回码为 `[0,3]`，最终 `summary` 返回 0。
- 同一 runner 复验的 metadata 为 `rows=6960`、`raw_rows=6960`、`symbol_count=12`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`non_trading_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`；`qsss_run_summary.json` 记录 `quality_errors=[]`、`signals=4`、`candidates=20`、`completed_trades=20`、`incomplete_trades=0`，资金曲线和组合 violation 与上一条 P1 四信号日复验一致。
- 新增 `validate_walk_forward_manifest.py` 后，对同一 runner 产物执行 manifest 契约校验返回 0，报告在 `/tmp/stock-selection-p1-runner-20260530T140916/run_manifest_validation.json`；校验结果为 `steps_checked=28`、`errors=[]`，只证明命令级步骤、退出码和门禁参数记录完整。
- 新增 `validate_walk_forward_artifacts.py` 后，对同一 runner 产物执行 artifact 内容校验返回 0，报告在 `/tmp/stock-selection-p1-runner-20260530T140916/run_artifact_validation.json`；校验结果为 `signals_checked=4`、`total_candidates=20`、`total_completed_trades=20`、`final_equity=0.9349716121129314`、`portfolio_violations=5`、`manifest_checked=true`、`errors=[]`，覆盖真实 `metadata.json`、信号窗口 CSV、候选 CSV、sizing CSV、回测 CSV、资金曲线 CSV、组合 summary JSON 和 manifest 校验报告。
- P1 20-symbol/6 信号日扩容复验先在 `/tmp/stock-selection-p1-expanded-20260530T151500/` 暴露 `cash_budget=1000000` 与 100 股 lot floor 不兼容：`2026-04-24` 7 个候选中 `600519` 一手名义额高于平均现金槽，`allocate_candidate_capital.py --fail-on-unallocated` 返回 3，未写 sizing 输出。这是真实资金约束失败，不应改写为成功。
- 同一 20-symbol/6 信号日复验改用 `cash_budget=3000000` 后又在 `/tmp/stock-selection-p1-expanded-20sym-6d-20260530T145418/` 暴露候选输出价差问题：`2026-05-12` 的 `002475` 在 `predictions_signal_window.csv` 和原始价格中 `close=77.19`，但 `qsss_candidates.csv` 曾输出清洗裁剪后的 `close=72.315824`，导致 sizing 拒绝 `candidate close differs from price signal close`。已修复为指标计算使用清洗数据，但候选输出保留原始信号日 `date/close/volume/turn`。
- 修复后 P1 20-symbol/6 信号日扩容复验产物在 `/tmp/stock-selection-p1-expanded-20sym-6d-fixed-20260530T145904/`；固定池为 `000001,000002,000063,000333,000651,002415,002475,002594,300014,300059,300750,600000,600036,600276,600309,600519,601166,601318,603288,688111`，信号日为 `2026-04-17/2026-04-24/2026-05-07/2026-05-12/2026-05-15/2026-05-20`。runner 共 40 步，除 `portfolio_overlap` 按预期返回 3 并被允许外，其余步骤返回 0。
- 同一扩容复验 metadata 为 `rows=11600`、`raw_rows=11600`、`symbol_count=20`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=0`、`dropped_invalid_rows=0`、`raw_non_trading_rows=0`、`non_trading_rows=0`、`raw_tradestatus_missing_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。
- 同一扩容复验 `qsss_run_summary.json` 记录 `quality_errors=[]`、`signals=6`、候选数分别为 `7/7/5/11/9/6`、`completed_trades=45`、`incomplete_trades=0`、资金曲线 `final_equity=0.8880888922355726`、`total_return=-0.11191110776442736`、`max_drawdown=-0.1266837841224236`。
- 同一扩容复验组合 violation 仍为 5 个：`max_open_positions=20 > 10`、`max_gross_weight=1.9770939999999997 > 1.0`、`max_gross_notional=5931282.0 > 1000000.0`、`max_cash_reserved=5931282.0 > 1000000.0`、`same_symbol_overlap_rows=49`。这说明扩容后风险暴露更大，不应通过放宽阈值改写为成功。
- 对同一扩容复验执行 `validate_walk_forward_manifest.py` 返回 0，报告在 `/tmp/stock-selection-p1-expanded-20sym-6d-fixed-20260530T145904/run_manifest_validation.json`，结果为 `steps_checked=40`、`errors=[]`；执行 `validate_walk_forward_artifacts.py` 返回 0，报告在 `/tmp/stock-selection-p1-expanded-20sym-6d-fixed-20260530T145904/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=45`、`total_completed_trades=45`、`final_equity=0.8880888922355726`、`portfolio_violations=5`、`errors=[]`。
- P1 40-symbol/6 信号日扩容首次严格复验在 `/tmp/stock-selection-p1-expanded-40sym-6d-20260530T150755/` 暴露 baostock 原始不可交易行：`600438` 在 `2026-02-25` 到 `2026-03-10` 共 10 行 `tradestatus=0` 且 `volume/amount/turn` 为空，fetch 返回 3，metadata 记录 `raw_rows=23200`、`invalid_rows=10`、`raw_non_trading_rows=10`。这是源数据质量边界，不应静默吞掉。
- 同一 40-symbol/6 信号日扩容在显式 `--drop-invalid-rows` 后的端到端复验产物为 `/tmp/stock-selection-p1-expanded-40sym-6d-dropinvalid-fixed-20260530T153132/`；runner 共 40 步，除 `portfolio_overlap` 按预期返回 3 并被允许外，其余步骤返回 0，summary 命令显式包含 `--allow-dropped-invalid-rows`。
- 同一 40-symbol/6 信号日显式 drop-invalid 复验 metadata 为 `rows=23190`、`raw_rows=23200`、`symbol_count=40`、`invalid_rows=10`、`dropped_invalid_rows=10`、`raw_non_trading_rows=10`、`non_trading_rows=0`、`raw_tradestatus_missing_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。这证明坏行被显式记录并丢弃，不证明源数据无异常。
- 同一 40-symbol/6 信号日显式 drop-invalid 复验 `qsss_run_summary.json` 记录 `quality_errors=[]`、候选数分别为 `16/13/10/20/14/12`、`completed_trades=85`、`incomplete_trades=0`、资金曲线 `final_equity=0.8851723337824899`、`total_return=-0.11482766621751006`、`max_drawdown=-0.1239265099532115`。
- 同一 40-symbol/6 信号日显式 drop-invalid 复验组合 violation 仍为 5 个：`max_open_positions=34 > 10`、`max_gross_weight=1.9791856666666663 > 1.0`、`max_gross_notional=5937557.0 > 1000000.0`、`max_cash_reserved=5937557.0 > 1000000.0`、`same_symbol_overlap_rows=97`。扩容后组合风险继续放大，不应通过放宽阈值改写为成功。
- 对同一 40-symbol/6 信号日显式 drop-invalid 复验执行 `validate_walk_forward_manifest.py` 返回 0，报告在 `/tmp/stock-selection-p1-expanded-40sym-6d-dropinvalid-fixed-20260530T153132/run_manifest_validation.json`，结果为 `steps_checked=40`、`errors=[]`；执行 `validate_walk_forward_artifacts.py --allow-dropped-invalid-rows` 返回 0，报告在 `/tmp/stock-selection-p1-expanded-40sym-6d-dropinvalid-fixed-20260530T153132/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=85`、`total_completed_trades=85`、`final_equity=0.8851723337824899`、`portfolio_violations=5`、`errors=[]`，并额外校验候选和 sizing 的信号日价格与 `prices_signal_window.csv` 原始 close 一致。
- P1 40-symbol/6 更早信号日复验产物为 `/tmp/stock-selection-p1-40sym-early6-20260530T154330/`；固定池仍为上一条 40 支股票，信号日扩展为 `2025-03-20/2025-06-20/2025-09-19/2025-12-19/2026-04-17/2026-05-20`。runner 共 40 步，除 `portfolio_overlap` 按预期返回 3 并被允许外，其余步骤返回 0。
- 同一 40-symbol/6 更早信号日复验 metadata 与上一条相同：`rows=23190`、`raw_rows=23200`、`symbol_count=40`、`invalid_rows=10`、`dropped_invalid_rows=10`、`raw_non_trading_rows=10`、`non_trading_rows=0`、`raw_tradestatus_missing_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。这说明源数据异常集中在相同原始区间，仍需显式 drop-invalid 解释。
- 同一 40-symbol/6 更早信号日复验 `qsss_run_summary.json` 记录 `quality_errors=[]`、候选数分别为 `9/12/13/14/16/12`、`completed_trades=76`、`incomplete_trades=0`、资金曲线 `final_equity=0.9994234423069976`、`total_return=-0.0005765576930023553`、`max_drawdown=-0.0385543978736397`。
- 同一 40-symbol/6 更早信号日复验组合 violation 为 3 个：`max_open_positions=16 > 10`、`max_gross_notional=2982665.0 > 1000000.0`、`max_cash_reserved=2982665.0 > 1000000.0`。该窗口未触发 gross weight 和 same-symbol overlap violation，但仍未满足组合容量门禁。
- 对同一 40-symbol/6 更早信号日复验执行 `validate_walk_forward_manifest.py` 返回 0，报告在 `/tmp/stock-selection-p1-40sym-early6-20260530T154330/run_manifest_validation.json`，结果为 `steps_checked=40`、`errors=[]`；执行 `validate_walk_forward_artifacts.py --allow-dropped-invalid-rows` 返回 0，报告在 `/tmp/stock-selection-p1-40sym-early6-20260530T154330/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=76`、`total_completed_trades=76`、`final_equity=0.9994234423069976`、`portfolio_violations=3`、`errors=[]`。
- P1 独立 40-symbol/6 信号日复验产物为 `/tmp/stock-selection-p1-40sym-independent-6d-20260530T155523/`；独立池为 `000009,000021,000039,000060,000069,000100,000157,000301,000338,000400,000423,000568,000625,000661,000708,000768,000786,000895,000963,001979,002001,002007,002024,002129,002179,002230,002236,002241,002252,002271,002304,002311,002352,002410,002459,002460,002466,002493,002508,002555`，与上一组 40-symbol 池交集为 `[]`。信号日仍为 `2025-03-20/2025-06-20/2025-09-19/2025-12-19/2026-04-17/2026-05-20`。
- 同一独立池复验 runner 共 40 步，除 `portfolio_overlap` 按预期返回 3 并被允许外，其余步骤返回 0；metadata 为 `rows=23190`、`raw_rows=23200`、`symbol_count=40`、`invalid_rows=10`、`dropped_invalid_rows=10`、`raw_non_trading_rows=10`、`non_trading_rows=0`、`raw_tradestatus_missing_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。
- 同一独立池复验 `qsss_run_summary.json` 记录 `quality_errors=[]`、候选数分别为 `2/13/7/9/15/13`、`completed_trades=59`、`incomplete_trades=0`、资金曲线 `final_equity=0.9604703366149994`、`total_return=-0.039529663385000635`、`max_drawdown=-0.0472927083305888`。
- 同一独立池复验组合 violation 为 3 个：`max_open_positions=15 > 10`、`max_gross_notional=2998116.0 > 1000000.0`、`max_cash_reserved=2998116.0 > 1000000.0`。独立池仍未满足组合容量门禁。
- 对同一独立池复验执行 `validate_walk_forward_manifest.py` 返回 0，报告在 `/tmp/stock-selection-p1-40sym-independent-6d-20260530T155523/run_manifest_validation.json`，结果为 `steps_checked=40`、`errors=[]`；执行 `validate_walk_forward_artifacts.py --allow-dropped-invalid-rows` 返回 0，报告在 `/tmp/stock-selection-p1-40sym-independent-6d-20260530T155523/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=59`、`total_completed_trades=59`、`final_equity=0.9604703366149994`、`portfolio_violations=3`、`errors=[]`。
- 新增 `run_baostock_walk_forward.py --max-candidates` 后，同一独立 40-symbol/6 信号日池完成 top-N=2 复验，产物在 `/tmp/stock-selection-p1-40sym-independent-topn2-20260530T161120/`。runner 使用 run-scoped `qsss_profile_config.json`，manifest 记录 `max_candidates=2` 和该配置路径；全链路未传入 `--expect-portfolio-violations`，40 个步骤均返回 0。
- 同一 top-N=2 复验 metadata 仍显式记录源数据异常：`rows=23190`、`raw_rows=23200`、`symbol_count=40`、`invalid_rows=10`、`dropped_invalid_rows=10`、`raw_non_trading_rows=10`、`non_trading_rows=0`、`raw_tradestatus_missing_rows=0`、`tradestatus_missing_rows=0`、`adjustflag=3`。
- 同一 top-N=2 复验每个信号日候选数均为 `2`，`qsss_run_summary.json` 记录 `quality_errors=[]`、`completed_trades=12`、`incomplete_trades=0`、资金曲线 `final_equity=0.8990438382018885`、`total_return=-0.10095616179811151`、`max_drawdown=-0.1009561617981115`。
- 同一 top-N=2 复验组合 summary 记录 `max_open_positions=2`、`max_gross_weight=0.9997069999999999`、`max_gross_notional=999707.0`、`max_cash_reserved=999707.0`、`same_symbol_overlap_rows=0`，组合 `violations=[]`。这只证明显式 top-N 截断下现有 equal-cash/lot-floor sizing 能通过固定组合门禁，不等同于已实现组合感知容量模型。
- 对同一 top-N=2 复验执行 `validate_walk_forward_manifest.py --expected-max-candidates 2` 返回 0，报告在 `/tmp/stock-selection-p1-40sym-independent-topn2-20260530T161120/run_manifest_validation.json`，结果为 `steps_checked=40`、`errors=[]`；执行 `validate_walk_forward_artifacts.py --allow-dropped-invalid-rows` 返回 0，报告在 `/tmp/stock-selection-p1-40sym-independent-topn2-20260530T161120/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=12`、`total_completed_trades=12`、`final_equity=0.8990438382018885`、`portfolio_violations=0`、`errors=[]`。
- 新增 `portfolio_cash_lot_floor` 组合级 sizing/cut 后，同一独立 40-symbol/6 信号日池完成真实组合容量复验，产物在 `/tmp/stock-selection-p1-portfolio-capacity-20260530T165104/`。runner 未传入 `--expect-portfolio-violations`，manifest 记录 `allocation_model=portfolio_cash_lot_floor`，步骤序列为每期 slice/predict/validate/score、统一 `portfolio_allocate`、逐期 backtest、equity、portfolio_overlap、summary，共 35 步且全部返回 0。
- 同一组合容量复验生成每信号日 `qsss_raw_candidates.csv`、cut 后 `qsss_candidates.csv`、`qsss_sized_candidates.csv`，以及全局 `qsss_skipped_candidates.csv` 和 `qsss_allocation_summary.json`。allocation summary 记录 `raw_candidates=59`、`allocated_candidates=48`、`skipped_candidates=11`、`skip_reason_counts={'max_open_positions': 11}`，各信号日 raw/allocated/skipped 为 `2/2/0`、`13/10/3`、`7/7/0`、`9/9/0`、`15/10/5`、`13/10/3`。
- 同一组合容量复验 allocation summary 同时记录约束与实际最大值：`cash_budget=3000000`、`lot_size=100`、`hold_days=5`、`max_open_positions=10` 且 limit 为 `10`、`max_gross_weight=0.99571` 且 limit 为 `1.0`、`max_gross_notional=2987130.0` 且 limit 为 `3000000.0`、`max_cash_reserved=2987130.0` 且 limit 为 `3000000.0`、`fail_on_symbol_overlap=true`。
- 同一组合容量复验 `qsss_run_summary.json` 记录 `quality_errors=[]`、`completed_trades=48`、`incomplete_trades=0`、资金曲线 `final_equity=0.9614512632665976`、`total_return=-0.03854873673340242`、`max_drawdown=-0.0494320515108941`；portfolio summary 记录 `max_open_positions=10`、`max_gross_weight=0.9957099999999997`、`max_gross_notional=2987130.0`、`max_cash_reserved=2987130.0`、`same_symbol_overlap_rows=0`、`violations=[]`。
- 对同一组合容量复验执行 `validate_walk_forward_manifest.py` 返回 0，报告在 `/tmp/stock-selection-p1-portfolio-capacity-20260530T165104/run_manifest_validation.json`，结果为 `steps_checked=35`、`errors=[]`；执行 `validate_walk_forward_artifacts.py --required-allocation-model portfolio_cash_lot_floor --allow-dropped-invalid-rows` 返回 0，报告在 `/tmp/stock-selection-p1-portfolio-capacity-20260530T165104/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=48`、`total_completed_trades=48`、`final_equity=0.9614512632665976`、`portfolio_violations=0`、`errors=[]`。
- P1 沪市 40-symbol/6 信号日组合容量复验首次尝试在 `/tmp/stock-selection-p1-portfolio-capacity-sse-20260601T020224Z/` 暴露 signal date 与实际 artifact 日期错位：runner 本身返回 0，manifest validator 返回 0 且 `steps_checked=35`、`errors=[]`，但 artifact validator 返回 3，报告在 `/tmp/stock-selection-p1-portfolio-capacity-sse-20260601T020224Z/run_artifact_validation.json`，核心错误包括 `2026-02-20_candidates_date_mismatch=2026-02-13`、`2026-02-20_sized_date_mismatch=2026-02-13`、多条 `2026-02-20_*_missing_raw_close=...` 和 `equity_signal_dates_mismatch`。该 run 只能作为 validator 捕捉日期错位的反例，不能记录为 P1 通过证据。
- P1 同一沪市 40-symbol 池的更早交易日窗口尝试在 `/tmp/stock-selection-p1-portfolio-capacity-sse-tradingdays-20260601T021130Z/` 于第一期 `2024-08-23:predict` 失败，`generate_lightgbm_predictions.py` 返回 2，stderr 记录 `no symbols predicted` 且 `skipped_reasons=fewer than 50 trainable rows after feature cleanup:40`。该失败说明过早信号日可能没有足够可训练历史，不能通过放宽预测失败门禁包装为成功。
- P1 同一沪市 40-symbol 池改用 6 个已确认 40/40 当日行且有训练历史的月末窗口后完成组合容量复验，产物在 `/tmp/stock-selection-p1-portfolio-capacity-sse-monthends-20260601T021449Z/`。固定池为 `600009,600010,600011,600015,600016,600018,600019,600028,600030,600031,600050,600104,600150,600196,600340,600436,600489,600690,600703,600887,600900,601012,601088,601111,601138,601211,601225,601288,601398,601601,601668,601688,601766,601788,601857,601899,601988,601989,603259,603501`，信号日为 `2025-02-28/2025-03-31/2025-04-30/2025-05-30/2025-06-30/2025-07-31`。该池与既有第一组 40-symbol 池交集为 `600030,600031,600050,600104,600196,600690,601012`，与既有独立 40-symbol 池交集为 `[]`，因此只能记录为新增沪市 40-symbol 月末窗口复验，不能写成与全部既有 40-symbol 池零交集的第三独立池。
- 同一沪市月末组合容量复验 runner 未传入 `--expect-portfolio-violations`，manifest 记录 `allocation_model=portfolio_cash_lot_floor`、`symbol_count=40`、`tradability_model=tradestatus_entry_exit_only`、`limit_rules_model=not_modeled`、`steps_count=35` 且失败步骤为 `[]`。metadata 记录 `rows=22956`、`raw_rows=23027`、`symbol_count=40`、`invalid_rows=71`、`dropped_invalid_rows=71`、`raw_non_trading_rows=71`、`non_trading_rows=0`、`raw_tradestatus_missing_rows=0`、`tradestatus_missing_rows=0`、`failed_symbols=[]`、`empty_symbols=[]`、`adjustflag=3`。
- 同一沪市月末组合容量复验 `qsss_allocation_summary.json` 记录 `raw_candidates=69`、`allocated_candidates=56`、`skipped_candidates=13`、`skip_reason_counts={'max_open_positions': 13}`，各信号日 raw/allocated/skipped 为 `9/9/0`、`11/10/1`、`13/10/3`、`14/10/4`、`15/10/5`、`7/7/0`。allocation 与 overlap summary 的最大容量一致：`max_open_positions=10`、`max_gross_weight=0.9971263333333333`、`max_gross_notional=2991379.0`、`max_cash_reserved=2991379.0`，limit 分别为 `10`、`1.0`、`3000000.0`、`3000000.0`。
- 同一沪市月末组合容量复验 `qsss_run_summary.json` 记录 `quality_errors=[]`、`completed_trades=56`、`incomplete_trades=0`、资金曲线 `final_equity=0.9972785699903136`、`total_return=-0.0027214300096863875`、`max_drawdown=-0.0654355170559202`；portfolio summary 记录 `same_symbol_overlap_rows=0`、`same_symbol_overlap_symbols=[]`、`capital_fields_present=weight,notional,quantity,cash_reserved`、`capital_fields_missing=[]`、`cash_capacity_verifiable=true`、`weight_capacity_verifiable=true`、`violations=[]`。
- 对同一沪市月末组合容量复验执行 `validate_walk_forward_manifest.py` 返回 0，报告在 `/tmp/stock-selection-p1-portfolio-capacity-sse-monthends-20260601T021449Z/run_manifest_validation.json`，结果为 `steps_checked=35`、`errors=[]`；执行 `validate_walk_forward_artifacts.py --required-allocation-model portfolio_cash_lot_floor --allow-dropped-invalid-rows` 返回 0，报告在 `/tmp/stock-selection-p1-portfolio-capacity-sse-monthends-20260601T021449Z/run_artifact_validation.json`，结果为 `signals_checked=6`、`total_candidates=56`、`total_completed_trades=56`、`final_equity=0.9972785699903136`、`portfolio_violations=0`、`manifest_checked=true`、`errors=[]`。
- P1 新增深市主板 40-symbol 零交集池组合容量复验，详见 `docs/reviews/P1-PORTFOLIO-CAPACITY-SZ-MAINBOARD-2026-06-01.md`。产物在 `/tmp/stock-selection-p1-portfolio-capacity-sz-mainboard-20260601T055752Z/`，runner、manifest validator 和 artifact validator 均返回 0；artifact validator 记录 `signals_checked=6`、`total_candidates=52`、`total_completed_trades=52`、`final_equity=1.0072173506529436`、`portfolio_violations=0`、`errors=[]`。
- P1 新增创业板 40-symbol 零交集池组合容量复验，详见 `docs/reviews/P1-PORTFOLIO-CAPACITY-CYB-2026-06-01.md`。产物在 `/tmp/stock-selection-p1-portfolio-capacity-cyb-20260601T065750Z/`，runner、manifest validator 和 artifact validator 均返回 0；artifact validator 记录 `signals_checked=6`、`total_candidates=49`、`total_completed_trades=49`、`final_equity=1.0057629234541754`、`portfolio_violations=0`、`errors=[]`。
- P1 新增科创板 40-symbol 零交集池组合容量复验，详见 `docs/reviews/P1-PORTFOLIO-CAPACITY-STAR-MARKET-2026-06-01.md`。初始池含 `688086` 的严格 fetch 在 `/tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100438Z/` 因 `empty_symbols=["688086"]` 返回 3，不能作为通过证据；最终池使用实探可取数的 `688102` 替换后，产物在 `/tmp/stock-selection-p1-portfolio-capacity-star-market-20260601T100924Z/`，runner、manifest validator 和 artifact validator 均返回 0；artifact validator 记录 `signals_checked=6`、`total_candidates=46`、`total_completed_trades=46`、`final_equity=0.9711787769119758`、`portfolio_violations=0`、`manifest_checked=true`、`errors=[]`。
- P1 新增沪市 603 号段 40-symbol、2025 下半年到 2026 年初窗口组合容量复验，详见 `docs/reviews/P1-PORTFOLIO-CAPACITY-SSE603-LATEWINDOW-2026-06-01.md`。取数探针在 `/tmp/stock-selection-p1-sse603-probe-20260601T105709Z/` 返回 0 且 `failed_symbols=[]`、`empty_symbols=[]`；最终产物在 `/tmp/stock-selection-p1-portfolio-capacity-sse603-latewindow-20260601T105911Z/`，runner、manifest validator 和 artifact validator 均返回 0；artifact validator 记录 `signals_checked=6`、`total_candidates=52`、`total_completed_trades=52`、`final_equity=0.9885268093529102`、`portfolio_violations=0`、`manifest_checked=true`、`errors=[]`。
- P1 沪市 601 号段 40-symbol、2025 下半年到 2026 年初窗口组合容量复验尝试在 `/tmp/stock-selection-p1-portfolio-capacity-sse601-latewindow-20260601T134251Z/` 暴露候选实际日期混杂。runner 返回 3；`run_manifest.json` 记录 `allocation_model=portfolio_cash_lot_floor`、`tradability_model=tradestatus_entry_exit_only`、`limit_rules_model=not_modeled`、请求信号日为 `2025-08-29/2025-09-30/2025-10-31/2025-11-28/2025-12-31/2026-01-30`，第 33 步 `equity` 返回 2，stderr 为 `ERROR: code=bad_input output_written=false message=each backtest file must contain exactly one signal_date`。metadata 已落地且记录 `rows=23166`、`raw_rows=23200`、`symbol_count=40`、`failed_symbols=[]`、`empty_symbols=[]`、`invalid_rows=34`、`dropped_invalid_rows=34`、`raw_non_trading_rows=34`、`raw_non_trading_symbols=601198,601298,601555,601718`、`raw_st_symbols=601718`、`adjustflag=3`。`qsss_allocation_summary.json` 已生成，记录 `raw_candidates=68`、`allocated_candidates=55`、`skipped_candidates=13`、`skip_reason_counts={"max_open_positions": 13}`、`max_open_positions=10`、`max_gross_weight=0.9984773333333333`、`max_gross_notional=2995432.0`、`max_cash_reserved=2995432.0`。人工复核该 run 的 `signals/2025-11-28/` 目录确认 `qsss_raw_candidates.csv`、`qsss_candidates.csv`、`qsss_sized_candidates.csv` 和 `qsss_backtest.csv` 均混有 `2025-11-19` 与 `2025-11-28` 两个实际日期；该 run 只能作为 drop-invalid 或缺精确信号日时实际候选日期不一致的失败边界，不能记录为 P1 通过证据。
- 2026-06-01 针对同一 SSE601 失败边界新增候选日期一致性早期门禁：`allocate_portfolio_candidate_capital.py` 可接收 `--expected-signal-dates` 并逐 raw candidate 文件校验日期集合，`run_baostock_walk_forward.py` 在 `portfolio_cash_lot_floor` 路径自动传入各 requested signal date，`backtest_buy_hold.py` 增加 `--expected-signal-date`，`validate_walk_forward_manifest.py` 要求 portfolio allocation 和 backtest 命令携带对应日期门禁，`validate_walk_forward_artifacts.py` 额外校验 `qsss_backtest.csv` 的 `signal_date`。对 `/tmp/stock-selection-p1-portfolio-capacity-sse601-latewindow-20260601T134251Z/` 的 raw candidate 重跑 portfolio allocation probe 返回 2，错误为 `candidate file 3 dates must match expected-signal-date=2025-11-28; found=2025-11-19,2025-11-28` 且未写出输出文件；对同一目录的 `2025-11-28/qsss_sized_candidates.csv` 重跑 backtest probe 返回 2，错误为 `candidate dates must match expected-signal-date=2025-11-28; found=2025-11-19,2025-11-28` 且未写出输出文件。该修复只把日期错位失败前移并固化为显式门禁，不把 SSE601 run 改写为通过证据。

边界:

- 2-symbol 最新日 smoke 不证明全市场策略质量，也不证明样本外收益。
- 12-symbol 三信号日回测证明了真实候选和真实 OHLCV 能进入 close-to-close 基线回测；当前代码支持 round-trip bps 扣减、等权资金曲线、取数阶段 `tradestatus` 门禁、回测级 entry/exit `--require-tradable-bars` 门禁、回测级 observed holding-period `--require-tradable-holding-period` 门禁、组合并发持仓报告和测试资金字段权重容量门禁，但仍不覆盖真实现金容量、涨跌停或全市场泛化能力。
- current-code 复验只证明固定 12-symbol、三信号日、5 日持有、10 bps 成本、5 bps 滑点和 `tradestatus` 入场/退出门禁下的可复跑边界；不能外推为全市场样本外收益有效。
- P1 四信号日扩展复验只证明同一固定池新增 `2026-04-24` 后仍能按固定门禁复跑；不能外推为策略正期望、全市场泛化、真实成交容量或涨跌停规则已覆盖。
- P1 40-symbol/6 信号日扩容复验只证明两个既有 40 支股票池、一组新增沪市 40-symbol 月末窗口、深市主板/创业板/科创板零交集月末窗口、一组沪市 603 号段 late-window 窗口、多个 6 信号日窗口、显式丢弃源数据异常、`cash_budget=3000000`、5 日持有、10 bps 成本、5 bps 滑点和 `tradestatus` 入场/退出门禁下的可复跑边界；不能外推为全市场样本外收益有效，也不能证明固定 300 万现金预算适合更大候选集。
- P1 独立 40-symbol/6 信号日 top-N=2 复验只证明 `--max-candidates` 能把每期候选显式截断并通过现有固定组合门禁；它不证明跨信号日滚动现金占用、同标的组合级去重或真实订单容量已建模。
- P1 `portfolio_cash_lot_floor` 复验证明了当前代码能按固定持有期滚动处理现金占用、并发仓位和同标的重叠，并输出 raw/selected/sized/skipped/allocation summary 证据；但仍只是本地 close-to-close + lot-floor 模型，不证明真实涨跌停、真实订单成交、券商容量或全市场策略质量。
- P1 各复验中的 `final_equity` 和 `total_return` 均为本地 close-to-close、完成交易等权资金曲线，不是按 `portfolio_cash_lot_floor` sizing 权重、真实成交或券商容量计算的收益。
- P1 沪市 601 号段 late-window 失败说明，在部分 symbol 因源数据异常被 `--drop-invalid-rows` 丢弃精确信号日行后，`slice_prices_as_of.py --as-of-date` 仍可能按 symbol 保留更早可用行，后续候选与回测 artifact 会混入不同实际日期；当前日期一致性门禁只能提前暴露并阻断这类 artifact 污染，不能把失败 run 外推为组合容量通过证据，后续若要复验 601 号段，应改用所有 symbol 均有精确信号日的窗口重跑。
- `run_baostock_walk_forward.py` 只编排既有 CLI 并记录命令级 manifest，不新增行情、prediction、sizing、回测或组合逻辑；它不能把固定 12-symbol/4 信号日小样本外推为全市场结论。
- `validate_walk_forward_manifest.py` 只校验 runner manifest 的结构、步骤顺序、退出码和门禁参数；不能替代真实行情、真实 LightGBM、真实回测或真实组合报告。
- `validate_walk_forward_artifacts.py` 只校验既有复验目录内的 artifact 内容一致性，不重新联网取数、不重新训练 LightGBM、不重新回测，也不能把固定小样本外推为全市场结论；当前会额外校验候选和 sizing 信号日价格与原始信号窗口 close 一致，并交叉校验 allocation/overlap 容量摘要一致性。
- `--required-limit-rules-model not_modeled` 只校验 runner、summary、manifest validator 和 artifact validator 中的未建模口径一致；即使这些命令全部退出 0，也不能写成 P2 真实涨跌停规则门禁通过。
- P2a 字段探测只证明 baostock 日 K 当前候选字段不可用；不等同于真实涨跌停规则门禁通过。
- `--drop-invalid-rows` 成功不等于源数据无异常；审查时必须同时检查 metadata 的 `invalid_rows`、`dropped_invalid_rows`、`raw_non_trading_rows` 和 `non_trading_rows`。
- baostock 日 K 未直接提供 `up_limit/down_limit/limit_status`；当前不得把 `preclose + pctChg`、股票前缀或 `isST` 粗推解释为真实涨跌停规则已建模。
- `generate_lightgbm_predictions.py` 当前把最新预测概率重复写入该标的评分窗口，目的是让评分脚本消费当前概率；不要解释成逐日历史预测序列。
- baostock 复权口径为 `adjustflag=3`，后续报告必须继续记录复权口径。

## PR 合并闭环 / 2026-06-01

- `codex/portfolio-allocation-validator-crosscheck` 已通过 PR #1 `[codex] Harden stock selection real-scenario gates` 合并到 `main`；`gh pr view 1` 记录 `state=MERGED`、`mergedAt=2026-06-01T07:59:45Z`、merge commit `4d67a3ded29a13a3c9f65dec0adb05657a6c870c`、head `0269cec3892f3238f28a2a2ac49144f8f9af7b8e`。
- 2026-06-01 复验 `git merge-base --is-ancestor origin/codex/portfolio-allocation-validator-crosscheck origin/main` 和 `git merge-base --is-ancestor 4d67a3ded29a13a3c9f65dec0adb05657a6c870c origin/main` 均返回 0；`git rev-list --left-right --count origin/main...origin/codex/portfolio-allocation-validator-crosscheck` 为 `25 0`，说明该分支 head 已包含于 `origin/main`。
- GitHub 当前列出 PR #1 commits 数量为 74；不应再把早期 60 个提交未闭环作为当前未完成风险，当前无需再次 merge PR #1 或该分支。

## Current Next Gates / 下一步门禁

- P1: 继续扩大 A 股真实 QSSS 门禁。当前已有两个既有 40-symbol 池、一组沪市 40-symbol 月末窗口、一组深市主板 40-symbol 零交集月末窗口、一组创业板 40-symbol 零交集月末窗口、一组科创板 40-symbol 零交集月末窗口和一组沪市 603 号段 late-window 窗口复验，并已在六个 40-symbol 池/窗口上复验 `portfolio_cash_lot_floor` 组合级 sizing/cut；下一轮 P1 应优先推进更真实的订单容量/涨跌停规则门禁，或继续扩大到更多独立池和更长窗口。
- P2: 真实涨跌停规则门禁。P2a 已确认当前 baostock 日 K 无直接 `up_limit/down_limit/limit_status/is_trading/suspended` 字段；未取得可靠直接字段或另起明确规则建模任务前，不得把 `preclose/pctChg/isST` 粗推写成已建模。
- P3: 外部源稳定性观察。akshare `stock_zh_a_hist`、yfinance/Yahoo 和 baostock 长期稳定性只能按固定脚本持续复验，不优先于 P1 的 A 股真实策略门禁。

## 真实使用反馈验收锚点 / 2026-06-01

本节记录 2026-06-01 真实使用反馈对应的后续验收边界。本轮只沉淀文档和 eval 口径，不表示已经实现新的总控 CLI、实时全市场扫描或低价超短 profile。

- 今日真实选股如果按 QSSS-derived 口径执行，输入仍必须包含 `market=A-share`、`prediction` 或 `prediction_score`，以及 `turn` 或 `turnover`。缺少 `prediction_score` 时，标准决策树是先停止 QSSS-derived 评分并暴露缺口；若用户要保留 QSSS 口径，应先运行真实可审计的 `generate_lightgbm_predictions.py --fail-on-skipped` 或提供外部预测列；不得用动量分、爆发分、固定 0.5 或人工判断替代 LightGBM prediction。
- 如果用户明确接受非 QSSS 的通用技术评分，才可以在本地 OHLCV 已落地并通过 `validate_ohlcv.py` 后走 `scripts/example_config.json` 或后续明确命名的通用 profile。该输出必须写明 `prediction_score` 未参与、不是 QSSS-derived 复刻、缺 `turn/turnover` 时只能披露 neutral turnover 假设，并且不能把候选排序写成真实收益、真实 LightGBM 或全市场策略质量证明。
- 实时样本池或联网抓取的少量股票只证明该固定 `requested_symbols`、数据源、参数、网络窗口和实际 `date_max` 下的局部样本可复跑。即使 runner、manifest validator 和 artifact validator 均通过，也不能写成“全市场扫描完成”。要宣称全市场扫描，必须先定义全市场 universe 生成规则，披露请求标的数、实际落地标的数、`failed_symbols`、`empty_symbols`、股票池过滤数、历史不足数、预测跳过数和最终候选数。
- 如果后续引入东方财富或其他实时快照源，必须把分页完整性写入 metadata，包括 source、source_scope、requested_pages、successful_pages、failed_pages、raw_items、filtered_items、snapshot_time 和 partial_result。分页断连、部分页成功或只使用已落地快照时，只能称为局部实时样本池或历史快照复用，不能写成今日全市场实时扫描完成。
- 低价超短意图应作为后续脚本化 profile 或总控 CLI 任务处理，而不是在当前 QSSS 评分中临时手工筛选。验收锚点应包括可配置阈值、至少 `close`/`ma15`/`explosion_score`/`volume_ratio`/`turnover_ratio`/`signal_tier` 字段、诊断输出、0 候选原因、低价风险披露，以及 QSSS prediction 依赖与通用技术评分模式的明确分流。
- 中文诊断字段如果后续加入，只能作为展示层派生字段，例如 `failed_thresholds_zh`、`selection_status`、`short_reason`。这些字段必须从机器可读的 `failed_thresholds`、`threshold_failures`、summary 计数和取数 metadata 派生，不得替代原始字段，也不得把 fallback、partial result、strict gate failed 或 output_not_written 翻译成成功。
- 后续总控 CLI 的最小可审计路径应串联取数或本地输入、`validate_ohlcv.py`、可选 `generate_lightgbm_predictions.py`、`score_candidates.py`、可选 sizing/backtest/portfolio validators，并写出 run-scoped metadata、命令 manifest、summary 和失败原因。CLI 不得吞掉任一步非 0 退出，也不得在缺少真实预测、真实行情或严格回测时生成候选名单或收益结论。

## 当前结论

已证明:

- 本地 CSV 评分链路。
- 本地 Parquet 读取、校验和评分链路。
- QSSS-derived 对 A 股字段、market、symbol、prediction、turn 的门禁。
- akshare A 股 `stock_zh_a_daily` 在 2026-05-30 指定窗口曾可拉取，并可映射到本地文件后进入通用校验和评分；`stock_zh_a_hist` 稳定性未证明。
- akshare 正式联网入口的 hist/daily fallback、metadata 和严格失败契约。
- yfinance 正式联网入口的 metadata、内置 timeout、空结果和严格失败契约；本轮带 `--timeout-seconds 10` 的 AAPL/MSFT 取数、校验和通用评分通过。
- P3 固定总控脚本在 2026-06-01 复验 akshare、yfinance 和 baostock 共 3 轮 9 次 source run，`passed_runs=9`、`all_sources_all_iterations_passed=true`，但 `long_term_stability_claim=not_proven`；akshare 仍记录 `hist_provider_clean=3` 的观察失败，只能说明 fallback provider 在本次窗口可用。
- P3 固定总控脚本在 `/tmp/stock-selection-p3-external-20260601T080703Z/` 追加复验 akshare、yfinance 和 baostock 共 3 轮 9 次 source run，`passed_runs=9`、`all_sources_all_iterations_passed=true`，但 `long_term_stability_claim=not_proven`；akshare 仍记录 `hist_provider_clean=3` 的观察失败，只能说明 fallback provider 在本次窗口可用。
- P3 固定总控脚本在 `/tmp/stock-selection-p3-external-20260601T094216Z/` 追加复验 akshare、yfinance 和 baostock 共 3 轮 9 次 source run，`passed_runs=9`、`all_sources_all_iterations_passed=true`，但 `long_term_stability_claim=not_proven`；akshare 仍记录 `hist_provider_clean=3` 的观察失败，只能说明 fallback provider 在本次窗口可用。
- P3 固定总控脚本在 `/tmp/stock-selection-p3-external-20260601T112254Z/` 追加复验 akshare、yfinance 和 baostock 共 3 轮 9 次 source run，`passed_runs=9`、`all_sources_all_iterations_passed=true`，但 `long_term_stability_claim=not_proven`；akshare 仍记录 `hist_provider_clean=3` 的观察失败且每轮使用 `stock_zh_a_daily` fallback，不能写成 `stock_zh_a_hist` 主接口稳定。
- P3 固定总控脚本在 `/tmp/stock-selection-p3-external-20260601T123704Z/` 追加复验 akshare、yfinance 和 baostock 共 3 轮 9 次 source run，`passed_runs=9`、`all_sources_all_iterations_passed=true`，但 `long_term_stability_claim=not_proven`；akshare 仍记录 `hist_provider_clean=3` 的观察失败且每轮使用 `stock_zh_a_daily` fallback，yfinance 的 AAPL/MSFT `date_max=2026-05-28` 早于请求 `end_date=2026-05-29`。
- P3 固定总控脚本在 `/tmp/stock-selection-p3-external-20260601T133324Z/` 追加复验 akshare、yfinance 和 baostock 共 3 轮 9 次 source run，`passed_runs=9`、`all_sources_all_iterations_passed=true`，但 `long_term_stability_claim=not_proven`；akshare 仍记录 `hist_provider_clean=3` 的观察失败且每轮使用 `stock_zh_a_daily` fallback，yfinance 的 AAPL/MSFT `date_max=2026-05-28` 早于请求 `end_date=2026-05-29`。
- LightGBM prediction 生成器的本地契约、失败边界和合成 demo 真模型运行链路。
- buy-hold 基线回测脚本的本地契约、失败边界、round-trip bps 成本/滑点扣减、可选 `tradestatus` 入场/退出门禁、等权资金曲线、组合阈值失败门槛、并发持仓门禁、候选资金字段透传、equal-cash/lot-floor sizing 产物，以及权重、名义金额、预留现金容量失败门禁。
- 2-symbol baostock 真实依赖 smoke 链路: 真实行情落地、真实 LightGBM prediction 生成、QSSS 最新日评分。
- 12-symbol baostock 多信号日真实链路: 严格信号日截断、真实 QSSS 候选生成、5 日 buy-hold 基线回测，3/4 信号日复验记录均为 `incomplete_trades=0`。
- baostock 日 K `tradestatus/preclose/pctChg/isST` 字段可取，取数阶段可拒绝 `tradestatus != 1` 的不可交易行。
- current-code 12-symbol/3 信号日 walk-forward 复验可完整跑到组合严格门禁，并以非 0 暴露并发、同标的重叠和资金阈值风险。
- P1 12-symbol/4 信号日扩展复验可完整跑到组合严格门禁，摘要质量错误为 0，并继续暴露同一组组合阈值风险。
- P1 20-symbol/6 信号日扩容复验可完整跑到组合严格门禁，摘要质量错误为 0，并进一步暴露 45 笔完成交易、最大 20 笔并发持仓、49 行同标的重叠、`final_equity=0.8880888922355726` 和更高资金阈值风险。
- P1 40-symbol 两个 6 信号日窗口复验可完整跑到组合严格门禁，摘要质量错误为 0；较近窗口完成 85 笔交易、`final_equity=0.8851723337824899` 并暴露 5 个组合 violation，较早窗口完成 76 笔交易、`final_equity=0.9994234423069976` 并暴露 3 个组合 violation。
- P1 独立 40-symbol/6 信号日复验与上一组 40-symbol 池交集为 0，可完整跑到组合严格门禁，摘要质量错误为 0，完成 59 笔交易、`final_equity=0.9604703366149994`，并暴露 3 个组合容量 violation。
- P1 独立 40-symbol/6 信号日 top-N=2 复验可在不使用 `--expect-portfolio-violations` 的情况下完整通过，摘要质量错误为 0，完成 12 笔交易、`final_equity=0.8990438382018885`，组合 `portfolio_violations=0`。
- P1 独立 40-symbol/6 信号日 `portfolio_cash_lot_floor` 复验可在不使用 `--expect-portfolio-violations` 的情况下完整通过，raw 候选 59 个、组合 cut 后 48 个、跳过 11 个且原因均为 `max_open_positions`，完成 48 笔交易、`final_equity=0.9614512632665976`，组合 `portfolio_violations=0`。
- P1 沪市 40-symbol/6 月末信号日 `portfolio_cash_lot_floor` 复验可在不使用 `--expect-portfolio-violations` 的情况下完整通过，raw 候选 69 个、组合 cut 后 56 个、跳过 13 个且原因均为 `max_open_positions`，完成 56 笔交易、`final_equity=0.9972785699903136`，组合 `portfolio_violations=0`；该池与既有第一组 40-symbol 池有 7 个交集，不能写成第三个全独立池。
- P1 深市主板 40-symbol/6 月末信号日 `portfolio_cash_lot_floor` 复验与已展开池集合交集为 `[]`，可在不使用 `--expect-portfolio-violations` 的情况下完整通过，raw 候选 61 个、组合 cut 后 52 个、跳过 9 个且原因均为 `max_open_positions`，完成 52 笔交易、`final_equity=1.0072173506529436`，组合 `portfolio_violations=0`。
- P1 创业板 40-symbol/6 月末信号日 `portfolio_cash_lot_floor` 复验与已展开池集合交集为 `[]`，可在不使用 `--expect-portfolio-violations` 的情况下完整通过，raw 候选 60 个、组合 cut 后 49 个、跳过 11 个且原因均为 `max_open_positions`，完成 49 笔交易、`final_equity=1.0057629234541754`，组合 `portfolio_violations=0`。
- P1 科创板 40-symbol/6 月末信号日 `portfolio_cash_lot_floor` 复验与已展开池集合交集为 `[]`，可在不使用 `--expect-portfolio-violations` 的情况下完整通过；初始 `688086` 空结果 run 已按失败边界排除，最终池 raw 候选 50 个、组合 cut 后 46 个、跳过 4 个且原因均为 `max_open_positions`，完成 46 笔交易、`final_equity=0.9711787769119758`，组合 `portfolio_violations=0`。
- P1 沪市 603 号段 40-symbol/6 late-window 信号日 `portfolio_cash_lot_floor` 复验可在不使用 `--expect-portfolio-violations` 的情况下完整通过；取数探针和最终 runner 均记录 `failed_symbols=[]`、`empty_symbols=[]`，raw 候选 56 个、组合 cut 后 52 个、跳过 4 个且原因均为 `max_open_positions`，完成 52 笔交易、`final_equity=0.9885268093529102`，组合 `portfolio_violations=0`。
- P1 `portfolio_cash_lot_floor` artifact validator 已交叉校验 `qsss_allocation_summary.json` 与 `qsss_overlap_summary.json` 的最大持仓、权重、名义金额和预留现金容量字段，真实复验目录 `run_artifact_validation_crosscheck.json` 通过且 `errors=0`。
- 真实 12-symbol/3 信号日样本已经暴露最大 12 笔并发持仓和同标的重复持仓冲突风险，并已可由 `portfolio_overlap_report.py` 自动化失败。
- 信号日截断防未来泄漏门禁。
- CI 证据必须绑定具体 `headSha` 和 GitHub Actions run；不得把旧提交的绿色 CI 外推为当前代码已验证。

仍未证明:

- akshare `stock_zh_a_hist` 中文列接口在当前环境可稳定取数。
- yfinance/Yahoo 在当前环境长期稳定取数。
- baostock、akshare 或 yfinance 任一外部源的长期服务稳定性。
- 真实交易所日历、节假日、特殊交易日、临时休市和全持有期停复牌可交易性。
- 价格表缺失日期、非交易所工作日差异、真实停复牌区间完整性和临时休市；`tradestatus_holding_period_bars` 只覆盖已观测 bar。
- 真实 LightGBM 质量指标，包括概率校准、holdout AUC/IC、分层收益、跨窗口稳定性、跨年份或分市场样本外统计、逐信号日独立预测质量。
- 全市场级 QSSS 策略质量、样本外收益、真实涨跌停规则、真实成交容量和券商订单证明。
