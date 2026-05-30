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

边界:

- 单元测试使用受控假模型验证契约；合成 demo 使用真实 LightGBM 依赖验证运行链路，但仍不等同于真实 A 股行情上的训练结果。
- 2-symbol 与 12-symbol baostock 证据只证明当前生成器能在有限真实行情样本上运行，并接入 `validate_ohlcv.py --config scripts/qsss_profile_config.json` 与 `score_candidates.py`；不证明全市场样本外泛化能力。

## 场景 M: buy-hold 基线回测

状态: 本地契约门禁已建立；baostock 真实候选和真实 OHLCV 已进入 12-symbol/3 信号日 close-to-close 基线回测；新增 round-trip bps 成本/滑点扣减和等权资金曲线，但仍不代表完整策略回测。

证据:

- 本轮新增 `scripts/backtest_buy_hold.py`。
- 脚本只做信号日收盘价到未来第 N 个可用交易行收盘价的 close-to-close buy-hold 基线。
- 候选日期必须精确匹配 OHLCV 日期，不自动滚动到下一交易日。
- 输出显式标记 `cost_model=round_trip_bps`、`slippage_model=round_trip_bps`；未启用回测级可交易门禁时 `tradability_model=not_modeled`，启用 `--require-tradable-bars` 时为 `tradestatus_entry_exit_only`；`limit_rules_model` 始终为 `not_modeled`。
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
- 回测级 `tradestatus` 门禁复验产物在 `/tmp/stock-selection-backtest-tradability-gate-20260530T111018/`；含 `tradestatus` 的 000001/600000 真实价格返回 0 且 `completed_trades=2`，旧 12-symbol 真实价格因缺 `tradestatus` 返回 3 且不写输出，`missing_reason_counts=missing_tradestatus:7`。
- 当前代码复跑产物在 `/tmp/stock-selection-backtest-tradability-current-20260530T124812/`；baostock 000001/600000 短窗口取数 36 行，`non_trading_rows=0`、`tradestatus_missing_rows=0`，启用 `--require-tradable-bars --fail-on-incomplete` 返回 0，回测 CSV 记录 `tradability_model=tradestatus_entry_exit_only` 且 `limit_rules_model=not_modeled`。
- 历史只读字段审查确认 `/tmp/stock-selection-ashare-scan-20260530-032723/prices.csv` 有 OHLCV 和 `turn`，但没有 `tradestatus`、`suspended`、`is_trading`、`limit_status`、`up_limit`、`down_limit`、`pre_close` 等字段；候选和回测产物也没有可交易/停牌/涨跌停字段。
- 只读并发持仓审查确认 `/tmp/stock-selection-backtest-costs-20260530T101000/` 的 15 笔真实 complete 交易最大同时打开 12 笔，发生在 `2026-05-15`、`2026-05-18`、`2026-05-19`；同一 symbol 跨信号日重复持仓冲突共有 21 个 `date-symbol` 组合，涉及 `002594`、`300059`、`300750`、`601318`、`000333`。
- 新增 `portfolio_overlap_report.py`，读取多个回测 CSV，按 business-day 闭区间统计 `daily_open_positions`、`max_open_positions`、同标的重叠和资金字段可验证性。
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
- 新 baostock 取数入口和 `--require-tradable-bars` 可拒绝 `tradestatus != 1` 的不可交易行，但回测仍不判断涨跌停状态；因此 `limit_rules_model=not_modeled` 仍必须保留。
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

边界:

- 2-symbol 最新日 smoke 不证明全市场策略质量，也不证明样本外收益。
- 12-symbol 三信号日回测证明了真实候选和真实 OHLCV 能进入 close-to-close 基线回测；当前代码支持 round-trip bps 扣减、等权资金曲线、取数阶段 `tradestatus` 门禁、回测级 `--require-tradable-bars` 门禁、组合并发持仓报告和测试资金字段权重容量门禁，但仍不覆盖真实现金容量、涨跌停或全市场泛化能力。
- current-code 复验只证明固定 12-symbol、三信号日、5 日持有、10 bps 成本、5 bps 滑点和 `tradestatus` 入场/退出门禁下的可复跑边界；不能外推为全市场样本外收益有效。
- P1 四信号日扩展复验只证明同一固定池新增 `2026-04-24` 后仍能按固定门禁复跑；不能外推为策略正期望、全市场泛化、真实成交容量或涨跌停规则已覆盖。
- `--drop-invalid-rows` 成功不等于源数据无异常；审查时必须同时检查 metadata 的 `invalid_rows`、`dropped_invalid_rows`、`raw_non_trading_rows` 和 `non_trading_rows`。
- baostock 日 K 未直接提供 `up_limit/down_limit/limit_status`；当前不得把 `preclose + pctChg`、prefix 或 `isST` 粗推解释为真实涨跌停规则已建模。
- `generate_lightgbm_predictions.py` 当前把最新预测概率重复写入该标的评分窗口，目的是让评分脚本消费当前概率；不要解释成逐日历史预测序列。
- baostock 复权口径为 `adjustflag=3`，后续报告必须继续记录复权口径。

## Current Next Gates / 下一步门禁

- P1: 扩大 A 股真实 QSSS 门禁。用更大股票池和更多历史信号日，按信号日截断、真实 LightGBM 生成、QSSS 评分、sizing、成本/滑点、`--require-tradable-bars` 回测、组合并发和容量报告完整复跑；通过条件必须绑定产物目录、metadata、summary、退出码和固定阈值。
- P2: 真实涨跌停规则门禁。先确认可靠数据源字段；未取得 `up_limit/down_limit/limit_status` 等直接字段前，不得把 `preclose/pctChg/isST` 粗推写成已建模。
- P3: 外部源稳定性观察。akshare `stock_zh_a_hist`、yfinance/Yahoo 和 baostock 长期稳定性只能按固定脚本持续复验，不优先于 P1 的 A 股真实策略门禁。

## 当前结论

已证明:

- 本地 CSV 评分链路。
- 本地 Parquet 读取、校验和评分链路。
- QSSS-derived 对 A 股字段、market、symbol、prediction、turn 的门禁。
- akshare A 股 `stock_zh_a_daily` 在 2026-05-30 指定窗口曾可拉取，并可映射到本地文件后进入通用校验和评分；`stock_zh_a_hist` 稳定性未证明。
- akshare 正式联网入口的 hist/daily fallback、metadata 和严格失败契约。
- yfinance 正式联网入口的 metadata、内置 timeout、空结果和严格失败契约；本轮带 `--timeout-seconds 10` 的 AAPL/MSFT 取数、校验和通用评分通过。
- LightGBM prediction 生成器的本地契约、失败边界和合成 demo 真模型运行链路。
- buy-hold 基线回测脚本的本地契约、失败边界、round-trip bps 成本/滑点扣减、可选 `tradestatus` 入场/退出门禁、等权资金曲线、组合阈值失败门槛、并发持仓门禁、候选资金字段透传、equal-cash/lot-floor sizing 产物，以及权重、名义金额、预留现金容量失败门禁。
- 2-symbol baostock 真实依赖 smoke 链路: 真实行情落地、真实 LightGBM prediction 生成、QSSS 最新日评分。
- 12-symbol baostock 多信号日真实链路: 严格信号日截断、真实 QSSS 候选生成、5 日 buy-hold 基线回测，3/4 信号日复验记录均为 `incomplete_trades=0`。
- baostock 日 K `tradestatus/preclose/pctChg/isST` 字段可取，取数阶段可拒绝 `tradestatus != 1` 的不可交易行。
- current-code 12-symbol/3 信号日 walk-forward 复验可完整跑到组合严格门禁，并以非 0 暴露并发、同标的重叠和资金阈值风险。
- P1 12-symbol/4 信号日扩展复验可完整跑到组合严格门禁，摘要质量错误为 0，并继续暴露同一组组合阈值风险。
- 真实 12-symbol/3 信号日样本已经暴露最大 12 笔并发持仓和同标的重复持仓冲突风险，并已可由 `portfolio_overlap_report.py` 自动化失败。
- 信号日截断防未来泄漏门禁。
- CI 证据必须绑定具体 `headSha` 和 GitHub Actions run；不得把旧提交的绿色 CI 外推为当前代码已验证。

仍未证明:

- akshare `stock_zh_a_hist` 中文列接口在当前环境可稳定取数。
- yfinance/Yahoo 在当前环境长期稳定取数。
- 全市场级 QSSS 策略质量、样本外收益、真实涨跌停规则、真实成交容量和券商订单证明。
