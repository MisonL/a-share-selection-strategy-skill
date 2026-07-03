# 脚本参考

本文件收纳配置文件、依赖、数据源字段映射、输入契约和常用命令细节。`SKILL.md` 只保留路由和硬约束；判断脚本职责、稳定入口或 helper 边界时，先读 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)，不要用 `scripts/` 根目录文件数量或 `__main__` 保护猜入口。

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

旧命令里的 `../scripts/*.json` 路径仍由 CLI 解析到 `../configs/*.json`，但新文档和默认 runner 都应使用 `../configs/*.json`。

## 入口分层

稳定 CLI、取数入口、门禁回测入口和内部 helper 的完整边界见 [../scripts/SCRIPTS.md](../scripts/SCRIPTS.md)。本文件只在已经确定入口后提供配置、依赖、字段和命令细节。

联网取数必须先落地本地文件和 metadata，再进入 `validate_ohlcv.py`、评分和汇报。不得把在线 API 响应直接解释成已验证候选。

`run_today_a_share_selection.py --mode auto` 只选择评分口径，不自动完成全 A 工作流。全 A / 全市场 / 扩大股票池任务必须先读 `full-a-strict-workflow.md`。

P1 `portfolio_cash_lot_floor`、单信号日定位链路、manifest/artifact validator 参数以 `runbook.md` 为准。

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
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --history-source baostock \
  --symbols 000001,600000 \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-skipped
```
