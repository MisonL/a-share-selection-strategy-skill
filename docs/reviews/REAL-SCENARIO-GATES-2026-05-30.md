# REAL-SCENARIO-GATES-2026-05-30

## 范围

本报告记录 2026-05-30 的真实任务场景复验结果。目标是区分已由本地脚本证明的能力和仍受外部环境约束的门禁，避免把 smoke test 误报为真实行情、真实 LightGBM 或真实回测通过。

## 场景 E: Parquet 输入

状态: 通过。

证据:

- `/tmp/stock-selection-parquet-scenario-e/prices.csv` 与 `/tmp/stock-selection-parquet-scenario-e/prices.parquet` 均可校验和评分。
- 无 `pyarrow` 或 `fastparquet` 时，Parquet 输入显式失败，`validate_ohlcv.py` 和 `score_candidates.py` 均返回非 0。
- 加 `pyarrow` 后，CSV 与 Parquet 输出候选行数一致，关键字段一致。
- 本轮新增 `tests/test_stock_selection_parquet_cli.py`，覆盖 Parquet validate 和 score CLI 路径。

边界:

- 该场景只证明本地 Parquet 读取、校验和评分链路，不证明真实行情源可用。

## 场景 G: akshare A 股映射

状态: 通过但依赖外部源可用性。

证据:

- `uv run --with akshare --with pandas --with numpy` 可安装并导入 akshare `1.18.64`。
- `ak.stock_zh_a_hist(symbol="000001", ...)` 成功返回 338 行，样本取 160 行。
- 字段映射使用 `股票代码 -> symbol`、`日期 -> date`、`开盘 -> open`、`最高 -> high`、`最低 -> low`、`收盘 -> close`、`成交量 -> volume`、`换手率 -> turn`。
- QSSS-derived 校验按预期拒绝 `market=A股`、`000001.SZ`、缺 `prediction_score`、缺 `turn`。
- 补齐外部 `prediction_score` 后，`score_candidates.py` 返回 0，并输出 `prediction_source=external_unverified lightgbm_not_executed_by_this_script=true`。

边界:

- `prediction_score` 是外部补齐值，本仓库仍未验证真实 LightGBM prediction 生成链路。
- `成交额` 只能作为可选 `amount` 字段，不得映射为 `volume`。

## 场景 I: yfinance 美股映射

状态: 未通过，受外部网络或 Yahoo 源门禁阻断。

证据:

- yfinance 拉取 AAPL/MSFT 的首次尝试被超时终止，退出码 143。
- 受控重试退出码 20。
- 关键错误包括 `curl: (28) Connection timed out`、`curl: (35) TLS connect error`、`MSFT: possibly delisted; no price data found`。
- 最终只生成 `/tmp/stock-selection-yfinance-scenario-i/yfinance_error.json`，未生成 `generic_ohlcv_aapl_msft.csv` 或 `scored_candidates.csv`。
- 对缺失 CSV 运行 `validate_ohlcv.py` 和 `score_candidates.py` 均返回 2，错误明确为 input file not found。

边界:

- 本场景不能证明 yfinance 单票或多票 MultiIndex、Date reset、Adj Close 与 Close 口径、symbol 写入或缺 `turn`/`turnover` warning 的真实端到端表现。
- 网络可用后应保留同一复验路径: 先落地本地 CSV 或 Parquet，再运行 `validate_ohlcv.py` 和 `score_candidates.py`。

## 场景 L: LightGBM prediction 生成

状态: 合成 demo 真模型链路通过，真实行情训练门禁仍未完成。

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
- 真实通过仍需要安装 `requirements-ml.txt`，用真实行情文件运行生成器，并把输出接入 `validate_ohlcv.py --config scripts/qsss_profile_config.json` 和 `score_candidates.py`。

## 场景 M: buy-hold 基线回测

状态: 本地契约门禁已建立，真实候选和真实行情回测仍未完成。

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
- 真实通过仍需要用真实候选 CSV 和真实 OHLCV 文件运行，并记录退出码、输出和缺数据数量。

## 当前结论

已证明:

- 本地 CSV 评分链路。
- 本地 Parquet 读取、校验和评分链路。
- QSSS-derived 对 A 股字段、market、symbol、prediction、turn 的门禁。
- akshare A 股真实源在本次环境可拉取并映射到本地文件后进入校验和评分。
- LightGBM prediction 生成器的本地契约、失败边界和合成 demo 真模型运行链路。
- buy-hold 基线回测脚本的本地契约和失败边界。

仍未证明:

- yfinance/Yahoo 在当前环境可稳定取数。
- 真实 LightGBM 在真实行情上的 prediction 生成链路。
- 真实候选和真实行情上的 buy-hold 回测结果。
- 完整 CI 远端运行结果。
