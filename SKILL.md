---
name: stock-selection-strategy
description: 当用户要求 AI Agent 设计、解释、实现、审查或运行股票选股策略时使用本 Skill。适用于 A 股、港股、美股等股票数据集的规则化选股、多因子评分、技术指标筛选、短线异动识别、候选股排序和策略结果解释。即使用户只说“帮我选股”“写一个选股 Agent”“提炼选股逻辑”“做股票评分”“找短线爆发股”“审查选股策略”，也应使用本 Skill。
---

# 通用选股策略 Skill

本 Skill 面向 AI Agent，目标是把股票选股任务拆成可解释、可验证、可复用的流程。它不是某个项目的操作手册，也不依赖特定仓库、框架或数据源。

核心原则：先定义数据契约，再计算因子，之后评分、过滤、排序和解释。任何结论都必须能追溯到输入数据和公式，不得伪造行情、回测或推荐结果。

## 适用场景

在这些任务中使用本 Skill：

- 设计一个股票选股 Agent 或选股工作流。
- 从已有代码中提炼通用选股策略。
- 基于行情、财务、资金流、板块、新闻或技术指标生成候选股。
- 解释某个选股结果为什么入选或被剔除。
- 审查选股策略是否存在数据泄漏、过拟合、静默降级或不可验证结论。
- 将选股逻辑写成代码、文档、配置、测试用例或 Agent prompt。

不要把本 Skill 用作投资建议模板。输出应描述策略信号和候选排序，不应承诺收益或直接替用户做买卖决策。

## 可选第三方库

通用 Skill 不绑定任何真实数据源。优先处理用户已经提供的本地 CSV 或 Parquet 数据；只有用户明确要求联网取数时，才按市场选择数据源库。

| 场景 | 推荐库 | 用途 | 说明 |
|------|--------|------|------|
| 基础计算 | `pandas`, `numpy` | 表格读取、滚动窗口、因子计算、排序输出 | 预设脚本需要这两个库。 |
| 配置和字段校验 | `pydantic` | 配置对象、输入字段、阈值校验 | 可选；脚本内使用标准库校验，避免额外强依赖。 |
| 技术指标 | `ta`, `pandas-ta` | RSI、MACD、布林带等指标 | 可选；简单指标可直接用 pandas 实现。 |
| 机器学习 | `scikit-learn` | 标准化、基线模型、时间序列验证 | 需要 ML 打分时再引入。 |
| 梯度提升模型 | `lightgbm`, `xgboost` | 上涨概率或排序模型 | 可选；缺失时报告真实环境问题，不要静默替换。 |
| 回测 | `vectorbt`, `backtesting.py` | 策略回放、交易成本和滑点模拟 | 可选；没有真实回测时不要声称已验证收益。 |
| A 股数据 | `akshare`, `baostock`, `tushare` | 行情、财务、板块和资金流 | 可选；注意 token、额度、字段口径和复权规则。 |
| 海外数据 | `yfinance`, `pandas-datareader` | 美股、ETF、指数等历史数据 | 可选；注意延迟、复权和交易日历差异。 |

当任务只是“基于已有数据选股”时，不要主动加入数据源库。先用本地文件完成可复现分析。

当用户明确要求联网取数时，Agent 必须把联网结果转换成可复现的本地行情文件后再评分：

1. 选择数据源并说明 token、额度、限流和字段口径风险。
2. 明确市场、周期、复权口径、时间范围和交易日历。
3. 将数据映射为本 Skill 的字段：`symbol`、`date`、`open`、`high`、`low`、`close`、`volume`，可选 `name`、`market`、`turn` 或 `turnover`。
4. 保存为本地 CSV 或 Parquet，并先运行 `validate_ohlcv.py`。
5. 只有校验通过后，才运行 `score_candidates.py`；不得把在线 API 响应直接解释成已验证候选。

常见数据源字段映射：

| 数据源 | 常见原字段 | 映射到本 Skill |
|--------|------------|----------------|
| akshare A 股中文列 | `日期`、`股票代码`、`开盘`、`最高`、`最低`、`收盘`、`成交量`、`换手率` | `date`、`symbol`、`open`、`high`、`low`、`close`、`volume`、`turn` |
| tushare | `ts_code`、`trade_date`、`open`、`high`、`low`、`close`、`vol`、`turnover_rate` | 去掉 `.SZ`/`.SH` 后写入 `symbol`，`trade_date` 写入 `date`，`vol` 写入 `volume`，`turnover_rate` 写入 `turn` |
| yfinance | `Date`、`Symbol`、`Open`、`High`、`Low`、`Close`、`Volume` | `date`、`symbol`、`open`、`high`、`low`、`close`、`volume` |

yfinance 映射后只满足通用 OHLCV；若用于 QSSS-derived，还必须外部补齐 `market=A-share`、真实上游 `prediction_score`、以及 `turn` 或 `turnover`，不能从 yfinance OHLCV 自动推断。不要把 `Adj Close` 静默替换为 `close`；如使用复权价，必须在数据说明或旁路元数据中记录复权口径。多源合并时只能保留一个预测列；若同时出现 `prediction` 和 `prediction_score`，先生成统一的 `prediction_score = coalesce(prediction_score, prediction)` 后再运行脚本。

## 预设脚本

本 Skill 提供以下可复用资源，位于 Skill 目录的 `scripts/` 下：

- `scripts/example_config.json`：通用权重、窗口和阈值示例。
- `scripts/create_demo_data.py`：生成可复制运行的本地 demo CSV，用于快速 smoke test。
- `scripts/qsss_profile_config.json`：从 QSSS 原策略提炼的 A 股默认剖面示例。
- `scripts/validate_ohlcv.py`：校验本地 CSV/Parquet 行情文件是否满足最小字段和数据质量要求。
- `scripts/score_candidates.py`：读取本地行情文件，按示例配置计算因子、过滤和排序，输出候选股 CSV。
- `scripts/stock_selection_config.py`、`scripts/stock_selection_data.py`、`scripts/stock_selection_metrics.py`、`scripts/stock_selection_output.py`、`scripts/stock_selection_profile.py`、`scripts/stock_selection_universe.py`、`scripts/stock_selection_diagnostics.py`：评分脚本使用的配置校验、数据读取和日期解析、指标、输出、profile 门禁、股票池过滤和诊断辅助函数。

使用方式：

```bash
python3 scripts/create_demo_data.py --output /tmp/stock-selection-demo
uv run --with pandas --with numpy python scripts/validate_ohlcv.py --input /tmp/stock-selection-demo/prices.csv
uv run --with pandas --with numpy python scripts/validate_ohlcv.py --input /tmp/stock-selection-demo/prices_with_prediction.csv --config scripts/qsss_profile_config.json
uv run --with pandas --with numpy python scripts/score_candidates.py --input /tmp/stock-selection-demo/prices.csv --config scripts/example_config.json --output /tmp/stock-selection-demo/candidates.csv
uv run --with pandas --with numpy python scripts/score_candidates.py --input /tmp/stock-selection-demo/prices_with_prediction.csv --config scripts/qsss_profile_config.json --output /tmp/stock-selection-demo/qsss_candidates.csv
```

脚本只处理本地文件，不联网取数，不调用券商接口，不生成交易指令。运行脚本需要当前 Python 环境已安装 `pandas` 和 `numpy`；没有 `uv` 时先创建虚拟环境并安装这两个依赖。若输入是 Parquet 文件，还需要可用的 Parquet 引擎，例如 `pyarrow` 或 `fastparquet`。`validate_ohlcv.py --config` 会在基础 OHLCV 校验之外检查 profile 专属字段。

使用 `qsss_profile_config.json` 时，输入必须包含 `market` 列，且 A 股记录使用 `A-share`；同时必须包含 `prediction` 或 `prediction_score` 列，且取值在 0 到 1 之间。该列表示上游模型已经算好的上涨概率；脚本不会用动量分伪造机器学习预测。脚本只复刻评分消费层；若要复刻 QSSS 的 ML prediction 生成器，需要在上游按本节 ML 口径处理 `0 -> NaN`、特征标准化和 LightGBM 训练。

`score_candidates.py` 的 CLI 摘要会输出 `input`、`input_symbols`、`universe_filtered_symbols`、`market_filtered_symbols`、`prefix_allow_filtered_symbols`、`prefix_excluded_symbols`、`insufficient_history_symbols`、`failed_symbols`、`threshold_failed_symbols`、`turnover_assumption`、`effective_empty_result`、`empty_result_reason` 和 `candidates`。直接调用 Python API 时，`input` 字段由调用方自行记录或注入。脚本是 CLI-first 资源；若在 Python 代码中复用，需要将 `scripts/` 加入 `PYTHONPATH` 或 `sys.path`。`effective_empty_result=true` 表示脚本成功运行但阈值或股票池过滤后没有候选；`empty_result_reason` 会区分 `universe_filtered_all`、`threshold_filtered_all` 等成功空结果原因。如果所有股票都因历史不足或输入数据异常无法评分，脚本会显式失败而不是输出 OK 摘要；如果混合批次里仍有可评分标的，短历史或单股失败会进入摘要和 warning。自动化门禁可传入 `--fail-on-skipped` 和 `--fail-on-empty-result`，让跳过标的或 0 候选以非 0 退出。`threshold_failures` 是各阈值独立失败计数，不是互斥分类；不要把这些计数相加解释为失败股票总数。成功摘要还可能输出 `failed_symbol_examples` 和 `insufficient_history_symbol_examples`，用于定位需要复核的标的。通用配置缺少 `turn`/`turnover` 时会告警，并用中性换手率序列计算 `turnover_ratio`；QSSS-derived 模式仍强制要求 `turn` 或 `turnover`。

QSSS-derived 输出中的 `prediction_source=external_unverified` 表示当前脚本只消费外部 `prediction` 或 `prediction_score`，不验证 LightGBM 上游生成链路。解释该字段时，应要求单独核验训练窗口、标签定义、特征、标准化和未来数据泄漏风险。

配置中的 `output.max_candidates` 大于 0 时限制输出数量；设为 0 表示不截断候选结果。

## 输入数据契约

开始前先确认输入数据是否满足任务所需字段。不要在字段缺失时静默生成“看似成功”的结果。

### 最小行情字段

每只股票的日线或周期线数据建议包含：

- `symbol`：股票代码。
- `name`：股票名称，可选但建议提供。
- `date`：交易日期或周期时间；若源数据使用 `timestamp`，需先重命名为 `date`。
- `open`、`high`、`low`、`close`：价格字段。
- `volume`：成交量。
- `amount`：成交额，可选。
- `turnover` 或 `turn`：换手率，可选。

字段口径：

- `symbol` 必须按文本保存，避免 Excel 或 CSV 推断把 `000002` 变成 `2`。
- 校验脚本会拒绝 1 到 3 位纯数字 `symbol`，用于捕获常见前导零损坏；其他市场代码仍需按对应市场规则人工确认。
- `date` 支持 `YYYY-MM-DD` 或 `YYYYMMDD`，其他格式需要先标准化。
- `volume` 单位必须在同一文件内一致；不要混用股、手、张或成交额。脚本只能校验数值和非负，无法从纯数值可靠判断单位是否混用。
- QSSS-derived 的 `market` 必须使用精确值 `A-share`；不会自动归一化 `A股`、`China` 等别名。

### 可选增强字段

根据任务需要可加入：

- 市值、行业、板块、上市天数、是否 ST 或退市风险。
- 资金流入、主力净流入、北向资金、融资融券。
- 财务指标，例如营收增速、净利润增速、ROE、毛利率、负债率。
- 估值指标，例如 PE、PB、PS、股息率。
- 新闻、公告、情绪、研报、事件标签。

### 数据质量门槛

策略运行前先做这些检查：

- 价格必须为正数，成交量不得为负数。
- 每只股票至少有足够历史窗口，例如 120 个交易日用于中期动量和波动率。
- 日期必须可排序，且同一股票同一周期不能重复。
- 缺失字段要显式报错、跳过该因子或降低策略能力说明，不得填充成假信号。
- 如果使用未来收益做训练标签，必须避免在预测时泄漏未来数据。

## 股票池过滤

先确定股票池，再做评分。常见过滤规则：

- 排除停牌、退市、ST、上市时间过短、成交极低或流动性不足的标的。
- 按市场、交易所、行业、板块、指数成分或用户自选范围限制股票池。
- 设置最低价格、最低成交量、最低成交额或最低市值。
- 对不同市场使用各自规则，不要把 A 股、港股、美股的代码格式、交易制度和单位混用。

股票池过滤应输出被剔除数量和原因分类，方便 Agent 解释结果。

## 因子体系

推荐从四类因子构建基础策略：趋势动量、技术状态、短线异动、风险控制。可按任务增加基本面、资金流或事件因子。

### 趋势动量因子

常用计算：

- `momentum_1m = close / close.shift(20) - 1`
- `momentum_3m = close / close.shift(60) - 1`
- `momentum_6m = close / close.shift(120) - 1`

使用建议：

- 短周期动量适合捕捉近期强势。
- 中长周期动量用于确认趋势持续性。
- 对极端涨跌幅做裁剪，避免单点异常支配总分。

### 技术状态因子

常用指标：

- RSI：14 周期，通常用于识别过弱或过热区间。
- MACD：EMA12、EMA26、signal 9，用于识别金叉、死叉和多空状态。
- 布林带：20 周期均线加减 2 倍标准差，用于观察价格位置。
- 量比：当前成交量除以近期均量。
- 波动率：收益率滚动标准差，可年化后用于风险过滤。

技术指标要说明窗口长度、缺失值处理和裁剪规则。

### 短线异动因子

短线爆发潜力可由以下组件组成：

- 成交量放大：最新成交量相对近期均量。
- 换手率放大：最新换手率相对近期均换手率。
- MACD 转强：MACD diff 从负转正，或已经处于多头状态。
- 价格位置：当前价格在近期高低区间中的位置。
- 短期收益：最近 3 到 5 个周期收益率。

示例评分：

```text
explosion_score =
  volume_ratio * 0.30
  + turnover_ratio * 0.20
  + macd_cross_score * 0.20
  + price_position_score * 0.15
  + short_momentum_score * 0.15
```

建议对 `volume_ratio` 和 `turnover_ratio` 设置上限，例如裁剪到 0 到 5，避免异常成交量导致总分失真。

### 风险控制因子

常用过滤或扣分项：

- 最大波动率。
- 最大回撤。
- 跌破关键均线。
- RSI 过热。
- 成交量或成交额不足。
- 价格过低或过高。
- 财务风险、退市风险、重大负面事件。

风险控制建议先做硬过滤，再把剩余风险作为总分扣分项。

## 多因子评分模板

在没有用户指定权重时，可使用以下通用权重作为初始模板：

```text
total_score =
  trend_score * 0.30
  + momentum_score * 0.20
  + explosion_score * 0.35
  + risk_score * 0.15
```

字段建议：

- `trend_score`：趋势或模型预测得分，范围建议归一化到 0 到 1。
- `momentum_score`：动量得分，可由 1 月、3 月、6 月动量加权得到。
- `explosion_score`：短线异动得分。
- `risk_score`：风险得分，低风险更高，高风险更低。

若使用机器学习模型，`trend_score` 可替换为上涨概率。必须说明：

- 特征列表。
- 标签定义。
- 训练窗口和预测窗口。
- 是否使用时间序列切分。
- 是否存在未来数据泄漏。

## QSSS-derived 默认策略剖面

当用户要求“复刻 QSSS 原选股策略”“按原 QSSS 口径选股”或需要一个 A 股默认剖面时，使用本节。它是从 QSSS 项目原实现提炼出的通用策略配置，不依赖 QSSS 仓库、类名或运行环境。

### 股票池和运行边界

- 默认市场为 A 股日线。
- 输入必须带 `market` 列，A 股记录使用 `A-share`；缺少该列时预设脚本会失败，避免跨市场混合数据仅靠代码前缀误纳入港股或其他市场代码。
- 股票代码只保留 `60`、`68`、`00`、`30` 开头的标的，分别覆盖上交所主板、科创板、深交所主板和创业板常见代码段。
- 排除 `8`、`4` 开头的标的，用于避开北交所和新三板口径。
- 默认历史起点可使用 `20220101`，每只股票至少需要 120 条日线记录。
- 批量执行时可限制样本数量；并发不是策略本身的一部分，迁移到 Agent 时应把超时、失败数量和进度事件作为可观测信息，而不是隐藏失败。

### 数据清洗和失败分类

运行因子前先做以下处理。预设 `score_candidates.py` 采用严格输入校验：字段缺失、无效价格、负成交量或重复日期会直接失败；历史不足和单股评分异常会被记录为可见计数，若没有任何股票可评分则脚本失败。若 Agent 自行实现批量服务，可以按股票跳过并记录失败分类，但必须让失败计数可见。

- `close` 必须存在、非空且大于 0；预设脚本会显式失败，批量服务可跳过该股票并记录为 `invalid_data`。
- 历史行数不足 120 时；混合批次中记录为 `insufficient_history_symbols`，若所有标的都历史不足则脚本失败。
- 技术指标和 ML 特征计算前，对 `close`、`volume`、`turn` 或 `turnover` 使用中位数加减 3 倍标准差裁剪异常值。
- 技术指标阶段不额外把 0 替换为缺失值；ML 特征阶段才将 `close`、`volume`、`turn` 中的 0 替换为缺失值，再前向和后向填充。
- 评分路径依赖输入校验保证价格为正、成交量非负；涉及除法的换手率、成交量和短线动量组件必须显式处理 0 或缺失分母，不得让 `inf` 或 `NaN` 进入总分。
- 单股分析异常应记录为 `failed_stocks` 或等价失败计数；批量任务可以跳过该股票继续处理其他股票，但必须输出可见告警，不得把失败股票伪装成成功候选。

### 技术指标口径

- 动量：`momentum_1m = close.pct_change(20)`、`momentum_3m = close.pct_change(60)`、`momentum_6m = close.pct_change(120)`。
- 候选表中的 `momentum_score` 使用最新 `momentum_1m`。
- RSI：14 周期，缺失填充为 50，裁剪到 0 到 100。
- MACD：EMA12、EMA26、signal 9；状态包括 `golden_cross`、`dead_cross`、`bullish`、`bearish`、`neutral`、`unknown`。
- 布林带：20 周期均线，加减 2 倍标准差，滚动窗口最少 5 条。
- 波动率：日收益率 20 周期滚动标准差乘以 `sqrt(252)`，缺失填充为均值，裁剪到 0 到 2。
- QSSS-derived 总分中的风险项直接使用 `1 - volatility`，因此当 `volatility > 1` 时允许产生负向扣分；不要把该风险项强行截断到 0 到 1。
- 量比：`volume / volume_ma20`，滚动窗口最少 5 条，缺失填充为 1.0，裁剪到 0 到 10。

### ML prediction 口径

QSSS 原策略的主趋势分不是动量近似，而是 LightGBM 输出的上涨概率 `prediction`：

- 特征：`momentum_1m`、`momentum_3m`、`momentum_6m`、`volatility`、`vol_ratio`、`rsi`、`macd`、`signal`。
- 输入少于 100 行时不训练；特征和目标清洗后少于 50 行时不训练。
- 标签：`target = close.shift(-5) / close - 1`，分类标签为 `target > target.mean()`。
- 未来收益标签只能用于训练标签构造，不得泄漏到预测期特征、筛选条件或同日验证结论里。
- 标准化：使用 `StandardScaler` 拟合训练特征。
- 模型：`LGBMClassifier`，`n_estimators=100`、`num_leaves=31`、`min_child_samples=5`、`max_depth=5`、`learning_rate=0.1`、`random_state=42`。
- 原实现使用随机 `train_test_split(test_size=0.2, random_state=42)`。Agent 迁移时应优先改为时间序列切分；若为了复刻原口径保留随机切分，必须在输出中记录未来泄漏风险。
- LightGBM 不可用、训练失败或预测失败时，应显式报告环境或模型问题，不得用固定 0.5 或动量近似冒充有效预测。
- 原 `predict()` 在预测阶段遇到空特征、最新特征缺失或异常时返回 0.5；Agent 复刻时应把 0.5 标记为“模型无把握或预测失败默认值”，不要解释成真实中性概率。
- 原实现先在全量特征上拟合 `StandardScaler`，再随机切分训练集和测试集；这会扩大时间序列泄漏风险。复刻原口径时要写明这是历史实现，不应作为新 Agent 的推荐训练方式。
- 本 Skill 的预设评分脚本不训练 LightGBM，也不会重建 `prediction`；它假定 `prediction` 已由上游模型生成。若输入数据还没有 `prediction`，应先实现上游 ML 生成器或显式报告缺失，不能在评分脚本里用技术因子替代。

### 短线爆发分

`explosion_score` 使用 20 日窗口，历史少于 20 行时返回 0：

```text
explosion_score =
  volume_ratio * 0.30
  + turnover_ratio * 0.20
  + macd_cross_score * 0.20
  + (1 - price_position) * 0.15
  + short_momentum_score * 0.15
```

组件口径：

- `volume_ratio = latest_volume / mean(volume[-20:])`，裁剪到 0 到 5。
- `turnover_ratio = latest_turn / mean(turn[-20:])`，裁剪到 0 到 5。
- `macd_cross_score = 1.0` 仅当最新 `macd - signal > 0` 且前一条 `macd - signal < 0`，否则为 0。
- `price_position` 为当前收盘价在近 20 日高低区间中的位置；分数使用 `1 - price_position`。
- `short_momentum_score` 使用 `close[-1] / close[-3] - 1`，放大 100 倍后裁剪到 -20 到 20，再映射到 0 到 1。
- 当历史少于 3 条时，短线动量分使用 0.5；但 QSSS-derived 主剖面要求至少 120 条日线，因此正常选股不会触发该 fallback。

短线信号可额外输出：

- `volume_surge`：最新成交量相对前 19 条均量大于 2。
- `turnover_surge`：最新换手率相对前 19 条均值大于 1.5。
- `price_breakout`：最新收盘价高于近 5 条均价的 1.02 倍。
- `momentum_acceleration`：`close[-1] / close[-5] - 1 > 0.05`。

### 评分、过滤和派生视图

QSSS-derived 总分使用 `prediction` 而不是 `trend_score`：

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

排序按 `total_score` 降序。若为了通用策略稳定排序增加二级排序键，必须说明这是工程扩展；QSSS-derived 复刻口径不应把二级排序键当作原策略规则。CLI 派生视图可额外列出：

- `ma15 <= 15` 的低价均线标的。
- `explosion_score > 1.5` 的超短线爆发潜力标的。
- 同时满足 `ma15 <= 15` 和 `explosion_score > 1.5` 的低价爆发标的。

Web 历史推荐字段只作为展示分层，不是买卖建议：

- `total_score >= 0.8`：`high_signal`
- `0.6 <= total_score < 0.8`：`medium_signal`
- `total_score < 0.6`：`low_signal`

CSV 中优先读取 `signal_tier`；`recommendation` 是历史兼容字段，与 `signal_tier` 同值。

回测边界：原 Web 回测只支持真实日线收盘价上的 `buy_hold` 基线。没有交易成本、滑点、涨跌停和不可交易状态时，不要把结果表述为完整策略回测。

### 工程派生路径边界

QSSS 还存在优化策略、交互界面和数据库辅助查询。这些属于运行和展示路径，不改变主选股公式：

- `OptimizedQuantStrategy` 复用同一组技术指标、ML prediction、爆发分、过滤阈值和总分公式，但增加缓存、分布式任务、分析时间戳和批处理路径。
- 交互 CLI 复用 `run_analysis()` 的结果，只改变表格展示、保存和 `ma15`、爆发潜力分组。
- 数据库辅助查询可按历史 `prediction_score` 与 `momentum_score` 均值排序，这不是实时选股主链，只能作为历史展示或二次查询口径。
- 缓存、线程数、分布式调度、数据库批量插入、数据源健康状态是工程控制面；提炼策略时只记录其可观测和失败边界，不把它们当作新的选股因子。

## 过滤与排序

评分后先硬过滤，再排序。示例阈值：

- `trend_score >= 0.60`
- `momentum_score >= -0.10`
- `30 <= rsi <= 75`
- `volatility <= 0.60`
- `volume >= 最低成交量阈值`
- `close >= 最低价格阈值`

这些阈值只是起点。Agent 应根据市场、周期、数据单位和用户目标调整，并在输出中说明调整依据。

排序默认按 `total_score` 降序。若任务偏短线，可提高 `explosion_score` 权重；若任务偏稳健，可提高 `risk_score` 和基本面权重。

## 输出格式

默认输出候选股表格。建议字段：

- `rank`：排名。
- `symbol`：股票代码。
- `name`：股票名称。
- `market`：交易所或市场板块，可选；QSSS 原输出包含该字段。
- `total_score`：综合得分。
- `trend_score`：趋势或模型得分。
- `prediction_score`：模型上涨概率，可选；QSSS-derived 剖面需要该字段。
- `momentum_score`：动量得分。
- `explosion_score`：短线异动得分。
- `risk_score`：风险得分。
- `ma15`：15 日均线，可选；用于低价均线派生视图。
- `signal_tier`：信号分层，非交易建议。
- `recommendation`：历史兼容字段，与 `signal_tier` 同值。
- `key_reasons`：入选原因，列出最重要的 2 到 4 条。
- `risk_notes`：主要风险或数据不足说明。
- `data_window`：使用的数据区间。

输出解释必须包含：

- 使用了哪些数据。
- 使用了哪些因子和权重。
- 过滤掉了哪些主要类型的股票。
- 结果是策略候选，不是收益承诺。

## Agent 工作流

执行选股任务时按以下步骤：

1. 明确用户目标：短线、中线、稳健、成长、低波动、板块内筛选或全市场筛选。
2. 明确市场和周期：A 股、港股、美股；日线、分钟线、周线等。
3. 检查输入数据字段和时间范围。
4. 定义股票池过滤规则。
5. 计算因子并记录公式。
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
- 是否没有交易成本、滑点、停牌、涨跌停等约束。
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
- 加入交易成本、滑点和不可交易状态。
- 对不同市场、行业、年份分别统计。

不能运行真实验证时，明确说明“未验证真实行情结果”，不要用理论推导冒充已通过。

## 简短输出模板

如果用户没有提供可验证行情数据，使用澄清模板，不要输出候选表：

```markdown
## 无法直接选股
- 缺少本地行情文件或明确数据源，不能生成候选股。
- 需要补充：市场、周期、时间范围、目标风格、CSV/Parquet 路径或联网取数授权。
- 可验证后再执行：先校验数据，再评分和解释结果。
```

如果脚本返回 `effective_empty_result=true`，使用 0 候选解释模板：

```markdown
## 0 候选解释
- 脚本已成功运行，但没有股票通过当前股票池和阈值。
- 主要原因：
  - `input_symbols=0`：股票池配置和输入市场或代码不匹配。
  - `universe_filtered_symbols>0`：股票池过滤剔除了标的，可继续查看 `market_filtered_symbols`、`prefix_allow_filtered_symbols`、`prefix_excluded_symbols`。
  - `threshold_failed_symbols>0`：评分后被阈值过滤；`threshold_failures` 是非互斥独立计数。
  - `empty_result_reason`：区分 `universe_filtered_all`、`threshold_filtered_all` 等成功空结果原因；全失败或全短历史会显式失败。
  - `failed_symbols>0`：存在单股运行期异常，需要复核。
- 如果 `failed_symbols>0`，应进入复核或失败处理；`effective_empty_result=true` 只说明脚本完成并无候选。
- 0 候选不是错误退出，也不是收益或策略有效性验证。
```

有可验证数据并成功评分时，使用结果模板：

```markdown
## 策略口径
- 市场和周期：
- 数据窗口：
- 股票池过滤：
- 因子和权重：

## 候选结果
| rank | symbol | name | total_score | key_reasons | risk_notes |
|------|--------|------|-------------|-------------|------------|

## 过滤摘要
- 输入股票数：
- 剔除数量和原因：
- 最终候选数：

## 验证与限制
- 已验证：
- 未验证：
- 数据限制：
```
