# Output Templates - 数据源和输入质量

本文件是 `output-templates.md` 的按需展开模板库。只有快速路由指向本类问题时才读取本文件；模板占位项不能当作事实。

## 目录

- [联网取数截止日不是实际最后交易日](#联网取数截止日不是实际最后交易日)
- [东方财富实时快照部分成功](#东方财富实时快照部分成功)
- [中文诊断不替代机器字段](#中文诊断不替代机器字段)
- [Akshare 取数使用了 fallback](#akshare-取数使用了-fallback)
- [Yfinance 当前使用原始 Close](#yfinance-当前使用原始-close)
- [Yfinance market 只是输出标签](#yfinance-market-只是输出标签)
- [Yfinance 只写出了部分行情](#yfinance-只写出了部分行情)
- [外部源稳定性仍未证明](#外部源稳定性仍未证明)
- [输入数据需要先修复](#输入数据需要先修复)
- [输入日期存在重复](#输入日期存在重复)
- [当前不支持严格全 Parquet 中间产物](#当前不支持严格全-parquet-中间产物)
- [当前环境不能完成脚本验证](#当前环境不能完成脚本验证)
- [Python 复用需要显式脚本路径](#python-复用需要显式脚本路径)

### 联网取数截止日不是实际最后交易日

```markdown
## 请求截止日未必有交易行
- fetch metadata 中的 `end_date` 是请求截止日，不保证该日存在交易数据。
- 当 `end_date` 落在周末、节假日或非交易日时，必须以 metadata 中每个 symbol 的 `date_max` 作为实际最后数据日。
- fetch 命令退出 0、CSV 写出和 `validate_ohlcv.py` 通过，只说明取数和基础 OHLCV 校验通过，不证明请求截止日当天有行情行。
- 报告时必须同时披露 `history_selection.requested_end_date`、`history_metadata_actual_date_max`、`history_metadata_end_date_has_rows`、逐 symbol `date_min/date_max`、`failed_symbols` 和 `empty_symbols`。
- 不能把非交易日 `end_date` 写成实际信号日、覆盖日或可回测入场日。
```

### 东方财富实时快照部分成功

```markdown
## 实时快照只覆盖部分分页
- 东方财富或其他实时快照源发生分页断连、超时或部分页失败时，不能写成全市场实时扫描完成。
- 必须披露 `source`、`source_scope`、`requested_pages`、`successful_pages`、`failed_pages`、`raw_items`、`filtered_items`、`snapshot_time` 和 `partial_result`。
- 如果后续评分只使用已成功落地的快照或前 N 个标的，只能称为固定实时样本池，不是全市场 universe。
- 使用已落地快照继续历史日线、校验和评分时，应同时披露快照时间、样本池来源、落地标的数、历史日线 `symbol_count`、`failed_symbols`、`empty_symbols` 和实际 `date_max`。
- 不能把分页失败后的 partial result、缓存快照或已落地旧快照翻译成实时全市场成功。
```

### 中文诊断只作展示层

```markdown
## 中文诊断不替代机器字段
- `failed_thresholds_zh`、`selection_status`、`short_reason` 等中文字段只能从原始机器字段派生。
- 必须保留 `failed_thresholds`、`threshold_failures`、`effective_empty_result`、`empty_result_reason`、`failed_symbols`、`empty_symbols`、`fallback_errors`、`partial_result`、`output_written` 等可审计字段。
- 中文摘要不能改变退出码、strict gate、fallback、partial fetch、0 候选或 output_not_written 的真实含义。
- 如果英文机器字段显示 `strict gate failed`、`partial_result=true`、`output_written=false` 或 `fallback_errors` 非空，中文摘要必须同步写成失败、部分结果或 fallback，而不是写成成功。
```

### Akshare fallback 成功

```markdown
## Akshare 取数使用了 fallback
- 命令退出码为 0 但 `fallback_errors` 非空时，不能写成主接口稳定成功。
- 必须披露主接口错误、`fallback_errors` 数量，以及 metadata 中逐标的 `provider`。
- `failed_symbols=[]` 只说明最终没有标的完全失败，不代表主接口无异常。
- 合规表述是“主接口失败后 fallback provider 取数成功”；不能外推为真实公网数据源长期稳定。
```

### Yfinance 复权口径

```markdown
## Yfinance 当前使用原始 Close
- `fetch_yfinance_ohlcv.py` 当前使用 `auto_adjust=False`，输出 CSV 的 `close` 来自原始 `Close`。
- metadata 中 `adjustment=auto_adjust_false_close` 不等于已使用复权价。
- 不能把 yfinance 返回中存在 `Adj Close` 写成脚本已经用于评分。
- 若用户要求复权价，需要显式改造脚本和 metadata 口径，再重新落地、校验和评分。
```

### Yfinance market 标签不是市场证明

```markdown
## Yfinance market 只是输出标签
- `fetch_yfinance_ohlcv.py --market` 只把标签写入 CSV 和 metadata，不校验 symbol 所属市场、交易所或交易日历。
- metadata 会写出 `market_label_only=true` 和 `source_claim_boundary=market_label_not_source_exchange_or_calendar_proof`；这些字段是边界披露，不是市场证明。
- metadata 中 `source=yfinance`、`market=A-share` 和基础 `validate_ohlcv.py` 通过，不能写成 A 股数据源或 A 股交易日历门禁通过。
- 如果 symbol 仍是 `AAPL` 这类非六位代码，prediction-derived A 股 profile 应按 symbol 格式门禁显式失败。
- 常见错误文本是 `prediction-derived A-share symbols must be six digits` 和 `market labels do not prove A-share source or calendar`。
- 报告时必须披露真实数据源、requested symbols、market 标签来源，以及 prediction-derived profile 校验结果。
```

### Yfinance 部分取数成功

```markdown
## Yfinance 只写出了部分行情
- 命令退出码为 0 但 `failed_symbols` 或 `empty_symbols` 非空时，不能写成所有 requested symbols 都成功落地。
- 必须披露 `requested_symbols`、`symbol_count`、`failed_symbols`、`empty_symbols` 和每个 symbol 的行数。
- `rows>0`、CSV 存在或 `output_written=true` 只说明至少有部分行情写出，不等于全量取数成功。
- 若 partial fetch 应作为门禁失败，必须使用 `--fail-on-fetch-error` 并按非 0 退出处理。
```

### P3 外部源复验不是长期稳定证明

```markdown
## 外部源稳定性仍未证明
- `probe_external_source_stability.py` 的 `all_sources_all_iterations_passed=true` 只说明 akshare、Yahoo/yfinance、baostock 和 zzshare 在当前窗口、当前参数和当前网络环境下连续复验通过。
- 必须披露 `long_term_stability_claim=not_proven`，不能写成 akshare、Yahoo/yfinance、baostock 或 zzshare 长期稳定。
- akshare 的 `hist_provider_clean=false` 是主接口异常观察项；即使总控脚本退出 0，也只能写“fallback provider 成功”，不能写 `stock_zh_a_hist` 稳定。
- 报告时必须列出各源 metadata 的逐标的 `date_max`；yfinance 的实际最后交易日仍以每个 symbol 的 `date_max` 为准，可能早于请求 `end_date`。
- `timeout_seconds` 只记录本次等待上限，不证明公网稳定。
- baostock fetch 通过仍只覆盖本次 symbols、日期范围、`adjustflag` 和 metadata 门禁；不证明涨跌停规则、券商成交或长期服务稳定。
- zzshare fetch 通过仍只覆盖本次 symbols、日期范围、`fields`、`limit/max_pages`、token/限流配置和 metadata 门禁；无 token 成功不证明无限免费额度或长期服务稳定。
- 通过 runner 使用 zzshare 时，报告必须披露 `history_request_interval_seconds`、`history_limit`、`history_max_pages` 和 `history_token_configured`；token 只能来自 `ZZSHARE_TOKEN` 环境变量，不能写入 runner 命令或报告正文。
```

### 前导零损坏

```markdown
## 输入数据需要先修复
- `symbol` 看起来已被表格软件或上游处理损坏，例如 `000002` 变成 `2`。
- 不能静默左侧补零后继续评分；这会掩盖源数据质量问题。
- 可接受路径：生成可审计的修复副本，明确修复规则和影响行数，再重新运行 `validate_ohlcv.py`。
- 校验通过前不能输出候选股、回测收益或策略结论。
```

### 日期格式归一化重复

```markdown
## 输入日期存在重复
- `YYYY-MM-DD` 和 `YYYYMMDD` 都是支持格式，但会解析为同一个真实交易日。
- 同一 `symbol` 下 `2026-05-29` 和 `20260529` 这类重复不能当成两天数据。
- `validate_ohlcv.py` 或 `score_candidates.py` 返回 duplicate symbol/date 时，应先修复源文件并重新校验。
- `output_written=false` 不是 0 候选成功，校验通过前不能输出候选或回测结论。
```

### 全 Parquet 链路未支持

```markdown
## 当前不支持严格全 Parquet 中间产物
- 当前脚本支持读取 CSV/Parquet，但标准 CLI 链路的中间产物默认写 CSV。
- 如果要求执行过程中完全不出现 CSV，必须先停止并说明需要改造脚本输出、runner 固定路径、artifact validator 和测试。
- 不能先写 CSV 再转换为 Parquet 后声称满足无 CSV。
- 只有用户明确允许临时 CSV 时，才可把每一步 CSV 输出显式转换为 Parquet 后继续。
```

### 离线依赖缺失

```markdown
## 当前环境不能完成脚本验证
- 目标命令需要 `pandas`、`numpy` 或其他声明依赖，但完全离线环境没有可用解释器、虚拟环境、wheelhouse 或包缓存。
- 不能改用 mock 数据、跳过依赖，或把未运行脚本写成验证通过。
- 可接受路径：使用已安装依赖的解释器，或先准备离线 wheelhouse/缓存，再重新运行原命令。
- 依赖失败是环境门禁失败，不是策略结果、候选结果或回测结论。
```

### Python API 复用边界

```markdown
## Python 复用需要显式脚本路径
- 本仓库 CLI 是稳定入口，当前不是可安装 Python package。
- 复用脚本函数前，必须把仓库的 `skills/a-share-selection-strategy/scripts/` 加入 `PYTHONPATH` 或 `sys.path`。
- 不要把 `from skills/a-share-selection-strategy/scripts/score_candidates import ...` 当成稳定 API；它可能在 import 阶段成功，但调用时因内部顶层模块路径缺失而失败。
- `python3 -S skills/a-share-selection-strategy/scripts/<name>.py --help` 依赖轻量化门禁只覆盖带 `argparse`、`main()` 或 `__main__` 的 CLI 入口；`scripts/lib/*` 下的 helper/import 模块没有帮助界面承诺，顶层 pandas/numpy import 失败不应写成用户入口缺口。
- 使用 `skills/a-share-selection-strategy/scripts/*.py` 全量扫描时，必须先把真实 CLI 入口和 helper/import 模块分开；不能用 glob 扫描里的 helper 失败覆盖真实 CLI 入口的逐项验证结果。
- 直接调用 Python API 时，`input` 字段由调用方记录或注入，不能把 API 调用摘要说成完整 CLI 门禁。
```
