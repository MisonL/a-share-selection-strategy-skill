# 脚本清单

本文件只解决一个问题：Agent 看到 `scripts/` 目录时，应立即区分稳定 CLI 入口和内部模块。命令细节、依赖和字段映射仍以 [../references/script-index.md](../references/script-index.md) 为准。

## 用户常用 CLI

| 脚本 | 用途 | 首先检查 |
| --- | --- | --- |
| `create_demo_data.py` | 生成本地 demo CSV | demo 不是真实行情 |
| `validate_ohlcv.py` | 校验 CSV/Parquet 行情输入 | 字段、日期、前导零、重复行、价格和历史窗口 |
| `score_candidates.py` | 本地行情评分并输出候选 CSV | `effective_empty_result`、`failed_symbols`、prediction 披露字段 |
| `run_today_a_share_selection.py` | 今日总控，串联取数、校验、评分、诊断和 HTML | `run_manifest.json`、`summary.json`、metadata |
| `slice_prices_as_of.py` | 按信号日切片行情 | `actual_data_date`，不能只看退出码 |

## 真实取数 CLI

| 脚本 | 数据源 | 边界 |
| --- | --- | --- |
| `fetch_eastmoney_a_share_spot.py` | 东方财富 A 股实时快照 | partial 分页不能写成全市场完成 |
| `fetch_baostock_a_share.py` | baostock A 股日线 | 检查失败、空 symbol、无效行和可交易字段 |
| `fetch_akshare_a_share.py` | akshare A 股日线 | fallback 成功不证明主接口稳定 |
| `fetch_akshare_hk_daily.py` | akshare 港股日线 | 不证明港交所日历或真实成交 |
| `fetch_zzshare_a_share.py` | zzshare A 股日线 | 检查 token、截断、频率和来源边界 |
| `fetch_yfinance_ohlcv.py` | yfinance 通用 OHLCV | market 只是标签，缺换手率时必须披露假设 |

## 预测、回测和门禁 CLI

| 脚本 | 用途 | 不能外推 |
| --- | --- | --- |
| `generate_lightgbm_predictions.py` | 可选 LightGBM prediction 生成器 | 下游评分通过不能反推被跳过标的也通过 |
| `allocate_candidate_capital.py` | 单候选本地 sizing | 不是真实成交、券商订单或现金容量证明 |
| `allocate_portfolio_candidate_capital.py` | 组合级 sizing 和容量裁剪 | 裁剪后候选不能等同原始候选全通过 |
| `backtest_buy_hold.py` | close-to-close buy-hold 基线 | 默认零成本，不是真实净收益 |
| `portfolio_equity_curve.py` | 等权或 sizing 资金曲线 | 默认只按 complete trades 计算 |
| `portfolio_overlap_report.py` | 并发持仓、重叠和容量门禁 | 工作日日历不是交易所日历 |
| `run_baostock_walk_forward.py` | baostock walk-forward 总控 | `--offline-plan` 不执行真实门禁 |
| `summarize_walk_forward_run.py` | 汇总 walk-forward artifact | 未传 required model 参数时不能声称模型口径已验证 |
| `validate_walk_forward_manifest.py` | 校验 runner manifest | 不替代 artifact 内容复验 |
| `validate_walk_forward_artifacts.py` | 校验 walk-forward artifact 内容 | `capacity_gate_pass=false` 仍是容量门禁失败 |
| `probe_baostock_limit_fields.py` | baostock 涨跌停字段探测 | 字段可取不等于涨跌停规则已建模 |
| `probe_external_source_stability.py` | 外部源稳定性观察 | 短窗口通过不证明长期稳定 |

## 内部 helper 模块

这些模块可能带 `__main__`，但直接执行只用于 fail-fast 提示“不是 CLI 入口”。不要把它们当作用户入口或 `--help` 合约：

- `a_share_selection_*.py`
- `run_today_a_share_selection_*.py`
- `walk_forward_*.py`
- `zzshare_a_share_data.py`
- `zzshare_a_share_quality.py`
- `lightgbm_prediction_summary.py`
- `portfolio_candidate_allocation.py`

直接复用 Python 代码时，需要将本目录加入 `PYTHONPATH` 或 `sys.path`。不要把内部 helper 的导入路径当成稳定 package API。

## 入口选择规则

1. 用户给本地行情文件：优先 `validate_ohlcv.py` 或 `run_today_a_share_selection.py --prices-input`。
2. 用户要求今日 A 股、小样本真实任务或低价超短：优先 `run_today_a_share_selection.py`。
3. 用户要求全 A、全市场或扩大股票池：先读 [../references/full-a-strict-workflow.md](../references/full-a-strict-workflow.md)，不要直接套默认小样本命令。
4. 用户坚持 prediction-derived：必须有真实 `prediction` 或 `prediction_score` 输入，再走 prediction-derived config。
5. 需要回测、容量或历史门禁：只在评分 artifact 已经闭环后进入预测、回测和门禁 CLI。
