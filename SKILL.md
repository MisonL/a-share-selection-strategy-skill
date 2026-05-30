---
name: stock-selection-strategy
description: 当用户要求 AI Agent 设计、解释、实现、审查或运行股票选股策略时使用本 Skill。适用于 A 股、港股、美股等股票数据集的规则化选股、多因子评分、技术指标筛选、短线异动识别、候选股排序和策略结果解释。即使用户只说“帮我选股”“写一个选股 Agent”“提炼选股逻辑”“做股票评分”“找短线爆发股”“审查选股策略”，也应使用本 Skill。
---

# 通用选股策略 Skill

本 Skill 面向 AI Agent，目标是把股票选股任务拆成可解释、可验证、可复用的流程。它不是投资建议模板，不承诺收益，不生成交易指令。

核心原则：先定义数据契约，再计算因子，之后评分、过滤、排序和解释。任何结论都必须能追溯到输入数据、公式、脚本输出或真实门禁记录；不得伪造行情、候选股、LightGBM prediction、回测收益或联网结果。

## 适用场景

在这些任务中使用本 Skill：

- 设计股票选股 Agent 或选股工作流。
- 从已有代码中提炼通用选股策略。
- 基于行情、财务、资金流、板块、新闻或技术指标生成候选股。
- 解释某个选股结果为什么入选或被剔除。
- 审查选股策略是否存在数据泄漏、过拟合、静默降级或不可验证结论。
- 将选股逻辑写成代码、文档、配置、测试用例或 Agent prompt。

若用户没有提供可验证行情文件或明确联网授权，不要输出候选表。使用 `docs/output-templates.md` 中的“无法直接选股”模板。

## 资源索引

本 Skill 入口只保留稳定规则。需要细节时按场景读取：

- `docs/factor-framework.md`：通用因子、评分、过滤和输出字段。
- `docs/qsss-derived-profile.md`：QSSS-derived A 股默认剖面、ML 口径和工程边界。
- `docs/output-templates.md`：无法选股、0 候选和候选结果输出模板。
- `docs/reviews/REAL-SCENARIO-GATES-2026-05-30.md`：真实任务场景门禁记录、下一步门禁优先级和仍未证明的边界。
- `docs/reviews/P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30.md`：baostock 涨跌停字段探测报告。

## 可选第三方库

通用 Skill 不绑定任何真实数据源。优先处理用户已经提供的本地 CSV 或 Parquet 数据；只有用户明确要求联网取数时，才按市场选择数据源库。

| 场景 | 推荐库 | 用途 | 说明 |
|------|--------|------|------|
| 基础计算 | `pandas`, `numpy` | 表格读取、滚动窗口、因子计算、排序输出 | 预设脚本需要这两个库。 |
| 配置和字段校验 | `pydantic` | 配置对象、输入字段、阈值校验 | 可选；脚本内使用标准库校验。 |
| 技术指标 | `ta`, `pandas-ta` | RSI、MACD、布林带等指标 | 可选；简单指标可直接用 pandas 实现。 |
| 机器学习 | `scikit-learn` | 标准化、基线模型、时间序列验证 | 需要 ML 打分时再引入。 |
| 梯度提升模型 | `lightgbm`, `xgboost` | 上涨概率或排序模型 | 可选；缺失时报告真实环境问题，不要静默替换。 |
| 回测 | `vectorbt`, `backtesting.py` | 策略回放、交易成本和滑点模拟 | 可选；没有真实回测时不要声称收益已验证。 |
| A 股数据 | `akshare`, `baostock`, `tushare` | 行情、财务、板块和资金流 | 可选；注意 token、额度、字段口径和复权规则。 |
| 海外数据 | `yfinance`, `pandas-datareader` | 美股、ETF、指数历史数据 | 可选；注意延迟、复权和交易日历差异。 |

当用户明确要求联网取数时，Agent 必须把联网结果转换成可复现的本地行情文件后再评分：

1. 选择数据源并说明 token、额度、限流和字段口径风险。
2. 明确市场、周期、复权口径、时间范围和交易日历。
3. 将数据映射为 `symbol`、`date`、`open`、`high`、`low`、`close`、`volume`，可选 `name`、`market`、`turn` 或 `turnover`。
4. 保存为本地 CSV 或 Parquet，并先运行 `validate_ohlcv.py`。
5. 只有校验通过后，才运行 `score_candidates.py`；不得把在线 API 响应直接解释成已验证候选。

常见字段映射：

| 数据源 | 关键映射 |
|--------|----------|
| akshare A 股中文列 | `日期 -> date`、`股票代码 -> symbol`、`开盘/最高/最低/收盘 -> open/high/low/close`、`成交量 -> volume`、`成交额 -> amount`、`换手率 -> turn` |
| akshare `stock_zh_a_daily` | `date -> date`、`open/high/low/close` 同名映射、`volume -> volume`、`amount -> amount`、`turnover -> turn` |
| baostock | `code -> symbol`，去掉 `sz.` 或 `sh.`；补 `market=A-share`；其余 OHLCV 字段同名映射 |
| tushare | `ts_code -> symbol`，去掉 `.SZ` 或 `.SH`；`trade_date -> date`、`vol -> volume`、`turnover_rate -> turn` |
| yfinance | `Date/Symbol/Open/High/Low/Close/Volume` 映射为小写标准字段 |

`成交额` 只能映射为可选字段 `amount`，不得映射为 `volume`。yfinance 映射后只满足通用 OHLCV；若用于 QSSS-derived，还必须外部补齐 `market=A-share`、真实上游 `prediction_score`、以及 `turn` 或 `turnover`。不要把 `Adj Close` 静默替换为 `close`；如使用复权价，必须记录复权口径。

## 预设脚本

本 Skill 提供以下资源，位于 `scripts/` 下：

- `example_config.json`：通用权重、窗口和阈值示例。
- `qsss_profile_config.json`：QSSS-derived A 股默认剖面示例。
- `create_demo_data.py`：生成可复制运行的本地 demo CSV。
- `validate_ohlcv.py`：校验本地 CSV/Parquet 行情文件。
- `score_candidates.py`：读取本地行情文件并输出候选股 CSV。
- `generate_lightgbm_predictions.py`：可选 LightGBM 预测生成器，输出 `prediction_score`。
- `allocate_candidate_capital.py`：可选候选资金分配脚本，按信号日 close、现金预算和 lot size 生成可追溯 sizing 字段。
- `backtest_buy_hold.py`：可选 close-to-close buy-hold 基线回测，可透传候选表资金字段。
- `portfolio_equity_curve.py`：可选等权组合资金曲线生成器，读取一个或多个回测 CSV，并支持 final equity / max drawdown 失败门槛。
- `portfolio_overlap_report.py`：可选组合并发持仓、同标的重叠、资金字段完整性，以及权重、名义金额和预留现金容量门禁报告。
- `validate_walk_forward_manifest.py`：校验一键 runner manifest 的步骤顺序、退出码和门禁参数；不替代真实行情、prediction 或回测执行。
- `validate_walk_forward_artifacts.py`：校验 walk-forward 复验目录中的真实 CSV/JSON artifact 内容，包括信号窗口、候选、sizing、回测、资金曲线、组合 summary 和 manifest 校验报告。
- `slice_prices_as_of.py`：按信号日截断本地行情，防止用未来行情生成候选。
- `fetch_baostock_a_share.py`：可选 baostock A 股日线取数脚本，输出本地行情 CSV 和 metadata JSON，包含 `tradestatus/preclose/pctChg/isST` 门禁字段。
- `fetch_akshare_a_share.py`：可选 akshare A 股日线取数脚本，先尝试中文列接口，失败时记录 fallback 并转用 `stock_zh_a_daily`。
- `fetch_yfinance_ohlcv.py`：可选 yfinance 日线取数脚本，输出本地通用 OHLCV CSV 和 metadata JSON；用 `--timeout-seconds` 显式限制每票拉取超时。
- `stock_selection_*.py`、`lightgbm_prediction_summary.py`：评分脚本使用的配置、数据读取、指标、输出、profile、股票池、可交易性元数据和诊断辅助函数。

使用方式：

```bash
python3 scripts/create_demo_data.py --output /tmp/stock-selection-demo
uv run --with pandas --with numpy python scripts/validate_ohlcv.py --input /tmp/stock-selection-demo/prices.csv
uv run --with pandas --with numpy python scripts/validate_ohlcv.py --input /tmp/stock-selection-demo/prices_with_prediction.csv --config scripts/qsss_profile_config.json
uv run --with pandas --with numpy python scripts/score_candidates.py --input /tmp/stock-selection-demo/prices.csv --config scripts/example_config.json --output /tmp/stock-selection-demo/candidates.csv
uv run --with pandas --with numpy python scripts/score_candidates.py --input /tmp/stock-selection-demo/prices_with_prediction.csv --config scripts/qsss_profile_config.json --output /tmp/stock-selection-demo/qsss_candidates.csv
```

`create_demo_data.py` 只依赖标准库。`validate_ohlcv.py`、`score_candidates.py`、`backtest_buy_hold.py` 和测试需要 `pandas`、`numpy`。Parquet 输入需要 `pyarrow` 或 `fastparquet`。真实 LightGBM 预测生成器需要 `requirements-ml.txt`。

脚本以 CLI 为稳定入口；若在 Python 代码中复用，需要将 `scripts/` 加入 `PYTHONPATH` 或 `sys.path`。脚本读取 CSV/Parquet，但写出的中间产物默认是 CSV；如果用户要求全链路中间产物保持 Parquet，必须显式把每一步 CSV 输出转换成 Parquet 后再传入下一步。

## 输入数据契约

开始前先确认输入数据是否满足任务所需字段。字段缺失时不得静默生成“看似成功”的结果。

最小行情字段：

- `symbol`：股票代码，必须按文本保存，避免 `000002` 变成 `2`。
- `date`：交易日期，支持 `YYYY-MM-DD` 或 `YYYYMMDD`。
- `open`、`high`、`low`、`close`：价格字段，必须为正数。
- `volume`：成交量，不得为负数，单位必须在同一文件内一致。
- `name`、`market`、`amount`、`turn` 或 `turnover`：可选字段，按策略需要提供。

校验规则：

- `validate_ohlcv.py` 会拒绝 1 到 3 位纯数字 `symbol`，用于捕获前导零损坏。
- 同一股票同一日期不能重复。
- 每只股票必须有足够历史窗口；QSSS-derived 默认至少 120 条日线。
- QSSS-derived 的 `market` 必须使用精确值 `A-share`。
- QSSS-derived 必须包含 `prediction` 或 `prediction_score`，且取值在 0 到 1 之间。
- QSSS-derived 必须包含 `turn` 或 `turnover`。
- 如果使用未来收益做训练标签，必须避免在预测时泄漏未来数据。

## QSSS-derived 默认剖面

当用户要求“复刻 QSSS 原选股策略”“按原 QSSS 口径选股”或需要 A 股默认剖面时，使用 `scripts/qsss_profile_config.json`，并读取 `docs/qsss-derived-profile.md`。

稳定边界：

- 默认市场为 A 股日线，只保留 `60`、`68`、`00`、`30` 开头的标的，并排除 `8`、`4` 开头的标的。
- 主趋势分是上游 LightGBM 输出的上涨概率 `prediction` 或 `prediction_score`，不是动量近似。
- `score_candidates.py` 只消费预测列，不训练 LightGBM，也不会用技术因子伪造机器学习预测。
- `prediction_source=external_unverified` 表示当前脚本只消费外部预测，不验证其训练窗口、标签定义、特征、标准化或未来泄漏风险。
- `generate_lightgbm_predictions.py` 是可选上游生成器；真实门禁必须启用 `--fail-on-skipped`，或检查 `raw_symbols == predicted_symbols` 且 `skipped_symbols == 0`。
- `backtest_buy_hold.py` 只做信号日收盘价到未来第 N 个可用交易行收盘价的基线；`--cost-bps` 和 `--slippage-bps` 只做 round-trip bps 扣减，`--require-tradable-bars` 只检查入场和退出日 `tradestatus=1`，不覆盖涨跌停；回测不生成 sizing，需先由 `allocate_candidate_capital.py` 生成可追溯资金字段。

QSSS-derived 总分：

```text
total_score =
  prediction * 0.30
  + momentum_score * 0.20
  + explosion_score * 0.35
  + (1 - volatility) * 0.15
```

硬过滤阈值：

- `prediction >= 0.60`
- `momentum_score >= -0.10`
- `30 <= rsi <= 75`
- `volatility <= 0.60`
- `volume >= 50000`
- `close >= 3.0`

## CLI 摘要和门禁

`score_candidates.py` 的 CLI 摘要会输出 `input`、`input_symbols`、股票池过滤、历史不足、单股失败、阈值过滤、`turnover_assumption`、`effective_empty_result`、`empty_result_reason` 和 `candidates`。直接调用 Python API 时，`input` 字段由调用方记录或注入。

解释规则：

- `effective_empty_result=true` 表示脚本成功运行但阈值或股票池过滤后没有候选。
- `empty_result_reason` 会区分 `universe_filtered_all`、`threshold_filtered_all` 等成功空结果原因。
- 所有股票都因历史不足或输入异常无法评分时，脚本应显式失败。
- `threshold_failures` 是各阈值独立失败计数，不是互斥分类。
- 自动化门禁可传入 `--fail-on-skipped` 和 `--fail-on-empty-result`，让跳过标的或 0 候选以非 0 退出。
- `failed_symbols>0` 表示存在单股运行期异常，即使输出其他候选，也应进入复核或失败处理。

真实链路建议顺序：

```bash
uv run --with pandas --with numpy --with baostock --with-requirements requirements-ml.txt python scripts/run_baostock_walk_forward.py --symbols SYMBOLS --start-date START --end-date END --signal-dates YYYY-MM-DD --output-dir RUN_DIR --cash-budget 1000000 --max-open-positions 10 --max-gross-weight 1.0 --max-gross-notional 1000000 --max-cash-reserved 1000000 --fail-on-symbol-overlap --expect-portfolio-violations
python scripts/validate_walk_forward_manifest.py --manifest RUN_DIR/run_manifest.json --signal-dates YYYY-MM-DD --expected-symbol-count N --required-tradability-model tradestatus_entry_exit_only --required-limit-rules-model not_modeled --expect-portfolio-violations
python scripts/validate_walk_forward_artifacts.py --run-dir RUN_DIR --output RUN_DIR/run_artifact_validation.json --signal-dates YYYY-MM-DD --expected-symbols SYMBOLS --expected-candidates CANDIDATE_COUNTS --expected-final-equity FINAL_EQUITY --expected-portfolio-violations N --required-tradability-model tradestatus_entry_exit_only --required-limit-rules-model not_modeled --manifest-validation RUN_DIR/run_manifest_validation.json
uv run --with pandas --with numpy python scripts/slice_prices_as_of.py --input prices.csv --output prices_signal_window.csv --as-of-date YYYY-MM-DD
uv run --with-requirements requirements-ml.txt python scripts/generate_lightgbm_predictions.py --input prices_signal_window.csv --output predictions_signal_window.csv --summary-output prediction_summary.json --fail-on-skipped
uv run --with pandas --with numpy python scripts/validate_ohlcv.py --input predictions_signal_window.csv --config scripts/qsss_profile_config.json
uv run --with pandas --with numpy python scripts/score_candidates.py --input predictions_signal_window.csv --config scripts/qsss_profile_config.json --output qsss_candidates.csv --fail-on-skipped --fail-on-empty-result
uv run --with pandas --with numpy python scripts/allocate_candidate_capital.py --prices prices.csv --candidates qsss_candidates.csv --output qsss_sized_candidates.csv --cash-budget 1000000 --lot-size 100 --fail-on-unallocated
uv run --with pandas --with numpy python scripts/backtest_buy_hold.py --prices prices.csv --candidates qsss_sized_candidates.csv --output qsss_backtest.csv --hold-days 5 --fail-on-incomplete
uv run --with pandas --with numpy python scripts/portfolio_equity_curve.py --backtests qsss_backtest.csv --output qsss_equity_curve.csv
uv run --with pandas --with numpy python scripts/portfolio_overlap_report.py --backtests qsss_backtest.csv --daily-output qsss_daily_positions.csv --overlap-output qsss_overlap.csv --summary-output qsss_overlap_summary.json --max-gross-weight 1.0 --max-gross-notional 1000000 --max-cash-reserved 1000000 --require-capital-fields
uv run --with pandas python scripts/summarize_walk_forward_run.py --run-dir RUN_DIR --output RUN_DIR/qsss_run_summary.json --expected-symbol-count N --required-tradability-model tradestatus_entry_exit_only --required-limit-rules-model not_modeled
```

涨跌停规则仍未建模；如需确认 baostock 字段能力，只能用 `probe_baostock_limit_fields.py` 做字段可用性探测并记录真实错误码。

## Agent 工作流

执行选股任务时按以下步骤：

1. 明确用户目标：短线、中线、稳健、成长、低波动、板块内筛选或全市场筛选。
2. 明确市场和周期：A 股、港股、美股；日线、分钟线、周线等。
3. 检查输入数据字段、时间范围、复权口径和成交量单位。
4. 定义股票池过滤规则。
5. 计算因子并记录公式；通用细节见 `docs/factor-framework.md`。
6. 归一化或裁剪因子。
7. 计算总分。
8. 应用硬过滤。
9. 排序输出候选股。
10. 解释每只候选股的入选原因和主要风险。
11. 记录无法验证或数据不足的部分。

## 审查清单

审查选股策略时重点检查：

- 是否使用未来数据训练或筛选。
- 是否把缺失数据当作有效信号。
- 是否隐藏上游失败或用 mock 数据冒充真实结果。
- 是否混用不同市场的数据单位、价格复权口径或成交量单位。
- 是否只在单一时间段过拟合。
- 是否缺少停牌、涨跌停等真实可交易性约束。
- 是否把候选排序说成确定收益。
- 是否没有记录被过滤股票的原因。

发现问题时，先指出会影响策略结论的高风险问题，再给改法。

## 验证要求

能运行代码时，至少验证：

- 因子公式对小样本数据的输出符合预期。
- 缺失字段、空数据、负价格、重复日期会显式失败或被记录。
- 评分公式权重与文档一致。
- 排序稳定，过滤条件逐项生效。
- 输出字段完整。

若有历史数据，进一步验证：

- 时间序列切分，避免随机切分造成未来泄漏。
- 样本外区间表现。
- 加入交易成本、滑点、组合资金曲线和不可交易状态。
- 对不同市场、行业、年份分别统计。

不能运行真实验证时，明确说明“未验证真实行情结果”，不要用理论推导冒充已通过。
