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

## 当前结论

已证明:

- 本地 CSV 评分链路。
- 本地 Parquet 读取、校验和评分链路。
- QSSS-derived 对 A 股字段、market、symbol、prediction、turn 的门禁。
- akshare A 股真实源在本次环境可拉取并映射到本地文件后进入校验和评分。

仍未证明:

- yfinance/Yahoo 在当前环境可稳定取数。
- 真实 LightGBM prediction 生成链路。
- 真实策略回测。
- 完整 CI 远端运行结果。
