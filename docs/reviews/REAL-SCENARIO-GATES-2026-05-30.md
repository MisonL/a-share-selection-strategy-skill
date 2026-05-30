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

状态: 外部源可用性不稳定；中文列 `stock_zh_a_hist` 曾通过，本轮复验失败；`stock_zh_a_daily` fallback 当前可用。

证据:

- `uv run --with akshare --with pandas --with numpy` 可安装并导入 akshare `1.18.64`。
- 历史门禁中 `ak.stock_zh_a_hist(symbol="000001", ...)` 成功返回 338 行，样本取 160 行。
- 本轮严格中文列路径在 `/tmp/stock-selection-akshare-current-retry-20260530T092022/` 三次失败，错误为 `RemoteDisconnected`。
- `stock_zh_a_daily(symbol="sz000001", ...)` 当前可用；产物在 `/tmp/stock-selection-akshare-alt-20260530T092125/`，映射后 177 行，日期范围 `2025-09-01` 到 `2026-05-29`。
- `stock_zh_a_daily` 映射使用 `volume -> volume`、`amount -> amount`、`turnover -> turn`，`validate_ohlcv.py` 返回 0，通用 `score_candidates.py` 返回 0 且候选数为 0。
- 新增 `fetch_akshare_a_share.py`，正式入口优先尝试 `stock_zh_a_hist`，失败或空结果时记录 `fallback_errors` 并转用 `stock_zh_a_daily`。
- 正式入口复验产物在 `/tmp/stock-selection-akshare-cli-real-20260530T093800/`；取数返回 0，metadata 记录 `rows=177`、`provider=stock_zh_a_daily`、`fallback_errors=1`，随后通用校验和评分均返回 0。
- QSSS-derived 校验按预期拒绝 `market=A股`、`000001.SZ`、缺 `prediction_score`、缺 `turn`。
- 补齐外部 `prediction_score` 后，`score_candidates.py` 返回 0，并输出 `prediction_source=external_unverified lightgbm_not_executed_by_this_script=true`。

边界:

- `prediction_score` 是外部补齐值，本仓库仍未验证真实 LightGBM prediction 生成链路。
- `stock_zh_a_daily` 当前成功只证明替代日线接口可进入通用校验和评分，不证明 `stock_zh_a_hist` 稳定可用。
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
- 该 metadata 记录 `rows=0`、`symbol_count=0`、`failed_symbols=2`、`empty_symbols=['AAPL','MSFT']`，错误为 Yahoo TLS connect error；对空 CSV 运行 `validate_ohlcv.py` 返回 1，运行 `score_candidates.py` 返回 2。
- README 干净路径复验产物在 `/tmp/stock-selection-readme-clean-20260530T091810/us/`；yfinance 命令用 60 秒外部超时包裹后成功，metadata 记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`。
- 新增脚本内 `--timeout-seconds` 后，受控复验产物在 `/tmp/stock-selection-yfinance-current-20260530T095106/`；`--timeout-seconds 10` 取数返回 0，耗时 2.592 秒，metadata 记录 `rows=1206`、`symbol_count=2`、`failed_symbols=[]`、`empty_symbols=[]`、`timeout_seconds=10.0`。
- 同一产物的 `validate_ohlcv.py` 返回 0，`score_candidates.py` 返回 0，候选数为 0，stderr 提示缺少 `turn/turnover` 时通用模式使用 neutral turnover 序列。

边界:

- 本场景证明 yfinance 当前环境存在波动，不应把单次成功或失败推广为稳定可用性结论。
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

边界:

- 单元测试使用受控假模型验证契约；合成 demo 使用真实 LightGBM 依赖验证运行链路，但仍不等同于真实 A 股行情上的训练结果。
- 2-symbol 与 12-symbol baostock 证据只证明当前生成器能在有限真实行情样本上运行，并接入 `validate_ohlcv.py --config scripts/qsss_profile_config.json` 与 `score_candidates.py`；不证明全市场样本外泛化能力。

## 场景 M: buy-hold 基线回测

状态: 本地契约门禁已建立；baostock 真实候选和真实 OHLCV 已进入 12-symbol/3 信号日 close-to-close 基线回测；仍不代表完整策略回测。

证据:

- 本轮新增 `scripts/backtest_buy_hold.py`。
- 脚本只做信号日收盘价到未来第 N 个可用交易行收盘价的 close-to-close buy-hold 基线。
- 候选日期必须精确匹配 OHLCV 日期，不自动滚动到下一交易日。
- 输出显式标记 `cost_model=excluded`、`slippage_model=excluded`、`tradability_model=not_modeled`。
- 本轮新增 `tests/test_buy_hold_backtest_cli.py`，覆盖正常收益、缺入场日不回退、严格模式遇到缺数据非 0 且不写输出。
- 本地合成 demo 完成路径已通过: 先用 180 日行情切出截至 `2025-07-31` 的信号窗口生成候选，再用完整行情运行 `backtest_buy_hold.py --hold-days 5`，输出 `completed_trades=2`、`incomplete_trades=0`。
- 本次合成 demo 的回测收益范围为 `0.0059836162887334` 到 `0.0071089378908271`。

边界:

- 该脚本不覆盖交易成本、滑点、涨跌停、停牌可交易性或组合资金曲线。
- 已有 12-symbol/3 信号日真实候选 CSV 与真实 OHLCV 运行记录；仍需要更大股票池、更多时间段和真实交易约束复验后，才能评价策略质量。

## 场景 U: baostock A 股全链路

状态: 2-symbol 最新日 smoke 已通过；12-symbol/3 信号日 baostock close-to-close 基线链路通过；baostock 无效 OHLCV 行门禁已补强。

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

边界:

- 2-symbol 最新日 smoke 不证明全市场策略质量，也不证明样本外收益。
- 12-symbol 三信号日回测证明了真实候选和真实 OHLCV 能进入当前 close-to-close 基线回测；它仍不覆盖交易成本、滑点、涨跌停、停牌可交易性、组合资金曲线或全市场泛化能力。
- `--drop-invalid-rows` 成功不等于源数据无异常；审查时必须同时检查 metadata 的 `invalid_rows` 和 `dropped_invalid_rows`。
- `generate_lightgbm_predictions.py` 当前把最新预测概率重复写入该标的评分窗口，目的是让评分脚本消费当前概率；不要解释成逐日历史预测序列。
- baostock 复权口径为 `adjustflag=3`，后续报告必须继续记录复权口径。

## 当前结论

已证明:

- 本地 CSV 评分链路。
- 本地 Parquet 读取、校验和评分链路。
- QSSS-derived 对 A 股字段、market、symbol、prediction、turn 的门禁。
- akshare A 股 `stock_zh_a_daily` 真实源当前可拉取，并可映射到本地文件后进入通用校验和评分；`stock_zh_a_hist` 当前稳定性未证明。
- akshare 正式联网入口的 hist/daily fallback、metadata 和严格失败契约。
- yfinance 正式联网入口的 metadata、内置 timeout、空结果和严格失败契约；本轮带 `--timeout-seconds 10` 的 AAPL/MSFT 取数、校验和通用评分通过。
- LightGBM prediction 生成器的本地契约、失败边界和合成 demo 真模型运行链路。
- buy-hold 基线回测脚本的本地契约和失败边界。
- 2-symbol baostock 真实依赖 smoke 链路: 真实行情落地、真实 LightGBM prediction 生成、QSSS 最新日评分。
- 12-symbol baostock 多信号日真实链路: 严格信号日截断、真实 QSSS 候选生成、5 日 buy-hold 基线回测，且 `incomplete_trades=0`。
- 信号日截断防未来泄漏门禁。
- 上一轮远端基线提交 `242c637` 的 CI 通过，GitHub Actions run 为 `26670338754`。

仍未证明:

- akshare `stock_zh_a_hist` 中文列接口在当前环境可稳定取数。
- yfinance/Yahoo 在当前环境可稳定取数。
- 全市场级 QSSS 策略质量、样本外收益、交易成本、滑点、涨跌停和停牌可交易性。
