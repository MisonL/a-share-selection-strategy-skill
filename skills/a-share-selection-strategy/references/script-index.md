# 脚本索引

本文件收纳 CLI 入口、配置文件、依赖、数据源字段映射、输入契约和脚本边界。`SKILL.md` 只保留路由和硬约束；需要执行命令或判断脚本职责时读本文件。只想区分“哪些文件是真 CLI、哪些是 helper”时，优先读 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)。

## 目录

- [配置文件](#配置文件)
- [常规 CLI 入口](#常规-cli-入口)
- [真实取数入口](#真实取数入口)
- [预测、回测和门禁入口](#预测回测和门禁入口)
- [helper 边界](#helper-边界)
- [依赖和离线环境](#依赖和离线环境)
- [输入数据契约](#输入数据契约)
- [数据源字段映射](#数据源字段映射)
- [常用命令](#常用命令)

## 配置文件

| 文件 | 用途 | 边界 |
| --- | --- | --- |
| `example_config.json` | 通用权重、窗口和阈值示例 | 不代表真实市场验证 |
| `ultra_short_low_price_config.json` | 低价超短通用技术评分 | 不使用也不伪造 prediction-derived/LightGBM |
| `prediction_profile_config.json` | prediction-derived A 股默认剖面 | 需要真实 `prediction` 或 `prediction_score` 输入 |
| `hong_kong_generic_config.json` | 港股本地 OHLCV 通用技术评分 | 不证明港交所日历、真实成交或收益 |

## 常规 CLI 入口

| 脚本 | 用途 | 关键产物或边界 |
| --- | --- | --- |
| `create_demo_data.py` | 生成可复制运行的本地 demo CSV | demo 不是真实行情 |
| `validate_ohlcv.py` | 校验本地 CSV/Parquet 行情文件 | 缺字段、重复日期、无效价格应失败 |
| `score_candidates.py` | 本地行情评分并输出候选 CSV | 只支持 CSV 输出；`spot_industry` 等 spot 字段只作展示 |
| `run_today_a_share_selection.py` | 总控 CLI，串联取数、校验、评分、诊断和 HTML | 产物为 `run_manifest.json`、`summary.json`、`report.html`、`candidates.csv`、`diagnostics.csv` |
| `slice_prices_as_of.py` | 按信号日截断本地行情 | 退出 0 只说明切片非空，不证明可评分 |

`run_today_a_share_selection.py --mode auto` 只选择评分口径，不自动完成全 A 工作流。全 A / 全市场 / 扩大股票池任务必须先读 `full-a-strict-workflow.md`。

## 真实取数入口

| 脚本 | 数据源 | 必看字段 |
| --- | --- | --- |
| `fetch_eastmoney_a_share_spot.py` | 东方财富 A 股实时快照 | `partial_result`、`failed_pages`、`snapshot_time`、`filtered_items` |
| `fetch_baostock_a_share.py` | baostock A 股日线 | `tradestatus`、`preclose`、`pctChg`、`isST` |
| `fetch_akshare_a_share.py` | akshare A 股日线 | fallback 记录、字段口径 |
| `fetch_akshare_hk_daily.py` | akshare 港股日线 | `real_market_data=unknown`、港交所日历未证明 |
| `fetch_zzshare_a_share.py` | zzshare A 股日线 | `token_configured`、`possibly_truncated_symbols`、`source_claim_boundary` |
| `fetch_yfinance_ohlcv.py` | yfinance 通用 OHLCV | `market_label_only=true`、`date_max`、失败和空 symbol |

联网取数必须先落地本地文件和 metadata，再进入 `validate_ohlcv.py`、评分和汇报。不得把在线 API 响应直接解释成已验证候选。

## 预测、回测和门禁入口

| 脚本 | 用途 | 不能外推 |
| --- | --- | --- |
| `generate_lightgbm_predictions.py` | 可选 LightGBM 预测生成器 | 下游评分成功不能反推被跳过标的也通过 |
| `lightgbm_prediction_summary.py` | prediction summary 辅助 | 不是常规用户 CLI |
| `allocate_candidate_capital.py` | 本地 sizing 字段生成 | 不是真实成交、券商订单或现金容量证明 |
| `backtest_buy_hold.py` | close-to-close buy-hold 基线回测 | 默认零成本，不是真实净收益 |
| `portfolio_equity_curve.py` | 等权组合资金曲线 | 默认只按 complete trades 等权计算 |
| `portfolio_overlap_report.py` | 并发持仓、重叠和容量门禁 | 工作日日历不是交易所日历 |
| `run_baostock_walk_forward.py` | baostock walk-forward 总控 | `--offline-plan` 只写计划，不执行真实门禁 |
| `summarize_walk_forward_run.py` | 汇总 walk-forward artifact 和门禁 | 未传 required model 参数时不能声称模型口径已验证 |
| `validate_walk_forward_manifest.py` | 校验 runner manifest | 不替代真实行情、prediction 或回测 |
| `validate_walk_forward_artifacts.py` | 校验 walk-forward artifact 内容 | `capacity_gate_pass=false` 仍表示容量门禁失败 |
| `probe_baostock_limit_fields.py` | baostock 涨跌停字段探测 | 字段可取不等于涨跌停规则已建模 |
| `probe_external_source_stability.py` | P3 外部源稳定性观察 | 短窗口通过不证明长期稳定 |

P1 `portfolio_cash_lot_floor`、单信号日定位链路、manifest/artifact validator 参数以 `runbook.md` 为准。

## helper 边界

`a_share_selection_*.py` 是配置、数据读取、指标、输出、profile、股票池、可交易性元数据和诊断辅助模块。它们不是用户 CLI 入口。

`run_today_a_share_selection_*.py`、`walk_forward_*.py`、`zzshare_a_share_data.py`、`zzshare_a_share_quality.py` 和 `lightgbm_prediction_summary.py` 也主要是内部模块或辅助模块。完整入口分层见 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)。

`python3 -S <helper>.py --help` 的顶层 pandas/numpy import 失败不属于 `--help` 入口缺口。`python3 -S --help` 轻量依赖门禁只适用于带 `argparse`、`main()` 或 `__main__` 的脚本入口。

Python 代码复用这些脚本时，需要将 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。不要把 `from scripts.<name> import ...` 当成稳定 API。

## 依赖和离线环境

| 场景 | 依赖 |
| --- | --- |
| 基础计算 | `pandas`, `numpy` |
| Parquet 输入 | `requirements-parquet.txt` 或 `pyarrow` / `fastparquet` |
| LightGBM prediction 生成器 | `requirements-ml.txt` |
| A 股 baostock 取数 | `baostock` |
| A 股 akshare 取数 | `akshare` |
| A 股 zzshare 取数 | `zzshare` |
| 海外 OHLCV 取数 | `yfinance` |

完全离线运行时，必须使用已经安装好依赖的解释器、虚拟环境、wheelhouse 或已有包缓存。若 `uv run --with ...` 因无法解析依赖失败，应显式报告环境问题；不得用 mock 数据、跳过依赖或把未运行的脚本说成验证通过。

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
| zzshare `daily(fields=all)` | `ts_code -> symbol`，去掉 `.SZ`、`.SH` 或 `.BJ`；`trade_date -> date`、`volume/vol -> volume`、`turnover/amount -> amount`、`turnover_rate -> turn`、`is_paused -> tradestatus`、`is_st -> isST` |
| tushare | `ts_code -> symbol`，去掉 `.SZ` 或 `.SH`；`trade_date -> date`、`vol -> volume`、`turnover_rate -> turn` |
| yfinance | `Date/Symbol/Open/High/Low/Close/Volume` 映射为小写标准字段 |

`成交额` 只能映射为可选字段 `amount`，不得映射为 `volume`。不要把 `Adj Close` 静默替换为 `close`；如使用复权价，必须记录复权口径。

## 常用命令

本地 demo：

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-demo
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --input /tmp/a-share-selection-demo/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py --input /tmp/a-share-selection-demo/prices.csv --config skills/a-share-selection-strategy/scripts/example_config.json --output /tmp/a-share-selection-demo/candidates.csv
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
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --history-source baostock \
  --symbols 000001,600000 \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-skipped
```
