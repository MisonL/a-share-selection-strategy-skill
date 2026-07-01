# 全 A 严格工作流

本文件只服务一个目标：让 AI Agent 在“全 A / 全市场 / 扩大股票池 / 真实扫描”任务里，优先走可复现、少歧义、少误判的路径，而不是把 demo、小样本命令或一次 runner 成功误当成全市场闭环。

## 何时使用

出现以下任一意图时，先读本文件，再决定命令：

- “全 A”“全市场”“扩大股票池”“尽量覆盖更多股票”
- “真实扫描”“真实任务”“不要 demo 数据”
- “先抓实时快照再筛历史”
- “看看今天全市场有哪些候选”
- “把固定样本池扩大”

不要把本文件用于以下场景：

- 用户已经给出本地 `prices.csv` 或 `prices.parquet`，只想评分或生成 HTML 报告。
- 用户只想验证 1 到 20 个明确代码的真实链路。
- 用户坚持 prediction-derived 且已经给出预测列。

## 核心判断

全 A 严格工作流和 `mode=generic/prediction` 是两套概念：

- 工作流路径回答“怎么取数、怎么清洗、怎么复跑、怎么收口”
- `mode` 只回答“最后评分时用 generic 还是 prediction-derived”

不要把 `run_today_a_share_selection.py --mode auto` 理解成“已经选好了全 A 工作流”。

## 当前推荐拓扑

| 层 | 目的 | 推荐入口 | 关键产物 |
| --- | --- | --- | --- |
| 1 | 广度快照 | `fetch_eastmoney_a_share_spot.py` | `spot.csv`、`spot_metadata.json` |
| 2 | 第一轮历史抓取 | `run_today_a_share_selection.py` 或 `fetch_zzshare_a_share.py` | `selected_symbols.json`、`history_metadata.json`、`summary.json` |
| 3 | 清洗与复跑 | 同上，基于清洗后的 symbol 集 | `prices.csv`、`history_metadata.json` |
| 4 | 最终评分与展示 | `run_today_a_share_selection.py --prices-input ...` | `run_manifest.json`、`summary.json`、`diagnostics.csv`、`candidates.csv`、`report.html` |

## 数据源策略

| 需求 | 优先源 | 原因 | 主要风险 | 不适合 |
| --- | --- | --- | --- | --- |
| 全市场广度快照 | `eastmoney` spot | 覆盖广，先形成候选历史抓取池 | 分页失败、`partial_result=true` | 不能直接当历史事实源 |
| 小范围严格可交易字段 | `baostock` history | 有 `tradestatus/isST` | 大范围易卡顿，慢 | 不适合直接跑全 A 广度 |
| 大范围历史 breadth | `zzshare` history | 适合更大 symbol 池 | 422 参数上限、429 限流、截断风险 | 不适合无批次控制地盲跑 |
| 预测列生成 | 本地 `generate_lightgbm_predictions.py` | 可审计 | 不证明模型质量 | 不替代全市场取数 |

对全 A 场景，默认策略是：

1. `eastmoney` 负责广度快照。
2. `zzshare` 负责大范围历史抓取。
3. `baostock` 只用于小范围严格核验、字段探针或对照，不作为全市场默认历史源。

`baostock` 历史抓取会为每个 symbol 额外调用一次 `query_stock_basic` 补股票名称，并在 strict 模式下把名称查询失败或缺失写入门禁错误。这个设计能避免报告把代码误当股票名称，但全市场 5000+ 标的会显著增加远端请求数；全 A 主路径不要直接用 baostock 做大范围首轮历史 breadth。

## 强制规则

1. 一定显式传 `--max-history-symbols`。  
   当前默认值是 50，只适合小样本，不适合全 A。

2. 中间轮次默认关闭 HTML。  
   第一轮和清洗轮次以 `summary.json`、`history_metadata.json`、`selected_symbols.json` 为准；只在最终收口轮次生成 `report.html`。

3. `zzshare` 的 `--history-limit` 不得大于 1000。  
   当前 provider 上限是 1000；更大值会在远端统一失败。

4. 不把一次 runner 成功写成全市场完成。  
   必须检查 `selected_symbols.json`、`history_metadata.json`、`summary.json`、`diagnostics.csv` 的覆盖和清洗结果。

5. 当前版本下，`prices-input` 复跑会优先读取同目录的 `metadata.json`，若缺失则回退读取 `history_metadata.json`。  
   Agent 不需要再手工复制 `history_metadata.json -> metadata.json`；只需确认同目录至少存在其中一个 provenance 文件。

## 推荐执行顺序

### 0. 预设运行目录

```bash
RUN=/tmp/a-share-full-market-$(date +%Y%m%dT%H%M%S)
mkdir -p "$RUN"
```

建议把每一轮都放在独立子目录中，避免旧产物污染新结论。

### 1. 先拿广度快照

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/fetch_eastmoney_a_share_spot.py \
  --output "$RUN/spot.csv" \
  --metadata-output "$RUN/spot_metadata.json" \
  --pages 300 \
  --fail-on-partial
```

先看这些字段：

- `partial_result`
- `requested_pages`
- `successful_pages`
- `failed_pages`
- `raw_items`
- `filtered_items`

只要 `partial_result=true`，就不能把后续任何结果写成“实时全市场扫描完成”。

### 2. 第一轮历史 breadth 抓取

推荐直接让 runner 串联抓历史、校验和评分，但先关闭 HTML：

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir "$RUN/pass1" \
  --mode auto \
  --spot-input "$RUN/spot.csv" \
  --derive-symbols-from-spot \
  --max-history-symbols 6000 \
  --history-source zzshare \
  --start-date "$START_DATE" \
  --end-date "$END_DATE" \
  --history-request-interval-seconds 0.5 \
  --history-limit 1000 \
  --history-max-pages 2 \
  --fail-on-skipped \
  --no-html-report
```

注意：

- `6000` 不是固定推荐值，只表示“显式给一个足够覆盖过滤后 spot 池的上限”。
- 不要依赖默认 `--max-history-symbols 50`。
- 对全 A 第一轮，目标是摸清覆盖和失败类型，不是立刻出最终报告。

### 3. 第一轮后先读 artifact，不急着看候选

优先检查：

- `pass1/selected_symbols.json`
- `pass1/history_metadata.json`
- `pass1/summary.json`
- `pass1/run_manifest.json`

最重要的问题不是“选出了几只”，而是：

- 初始历史池有多少只
- 哪些 symbol 失败、为空、被截断
- 是否有 `invalid_rows`
- 是否有 `non_trading_rows`
- 是否有 `st_rows`
- 是否触发 422 / 429 / timeout

### 4. 清洗分类

第一轮后，把问题分成四类：

1. 参数类：例如 `history-limit` 超上限。  
   这种应直接修命令，再重跑，不要继续分析结果。

2. provider 稳定性类：例如 429、timeout、`possibly_truncated_symbols`。  
   这种应降低批次、增加 `request_interval_seconds`、或拆轮次重跑。

3. 数据质量类：例如 `invalid_rows`、`non_trading_rows`、`st_rows`。  
   这种应形成剔除清单，再重跑历史。

4. 历史长度类：例如 validate 阶段提示若干 symbol 少于最小历史行数。  
   这种应形成最终移除清单，再进入最终评分轮。

## 当前版本的推荐收口方式

当前 runner 还没有“全 A 一键清洗续跑模式”。因此 Agent 应预期至少两轮：

1. 第一轮：拿覆盖、失败分类、清洗依据。
2. 第二轮：基于清洗后的 symbol 集重抓历史。
3. 最终轮：基于 clean `prices.csv` 做 `prices-input` 评分和 HTML。

### 5. 清洗后复跑历史

如果第一轮已经明确哪些 symbol 需要剔除，建议基于清洗后的 symbol 集重新跑一轮历史抓取。  
当前仓库没有稳定的“从文件读 symbol 列表”CLI 入口，因此可以：

- 用 shell 组装新的 `--symbols` 参数，或
- 复用上轮筛出的 symbol 清单，在外层生成新的 comma-separated 列表

这一步的目标是拿到：

- `invalid_rows == 0`
- `non_trading_rows == 0`
- `st_rows == 0`
- `failed_symbols == []`
- `empty_symbols == []`
- `possibly_truncated_symbols == []`

### 6. 最终评分与 HTML 报告

当 clean `prices.csv` 已经准备好后，再进入最终轮次：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input "$RUN/clean/prices.csv" \
  --spot-input "$RUN/spot.csv" \
  --output-dir "$RUN/final" \
  --mode auto \
  --html-report-language zh \
  --fail-on-skipped
```

## 最终报告前的必查清单

只有以下问题都答清楚后，才适合把 `report.html` 给用户：

1. `summary.json` 的 `execution_path`、`coverage_class`、`full_market_claim_allowed`、`full_market_claim_boundary` 是什么。
1. 初始 spot 样本多少只。
2. 第一轮历史抓取多少只。
3. 清洗掉多少只，按什么原因清洗。
4. 最终 validate 后保留多少只。
5. `candidate_rows` 和 `diagnostic_rows` 各是多少。
6. `candidate_field_coverage` 是否已经在 HTML 和 stdout 里清楚展示。
7. `source_scope`、`spot source_scope`、实际 `date_max` 是什么。
8. 哪些边界仍未证明：实时全市场完成、长期稳定性、真实成交、真实收益。

如果最终 `report.html` 没直接展示以下过程，Agent 在对用户汇报时必须手动补齐：

- 初始 spot 快照规模
- 初始历史抓取样本规模
- 每轮清洗剔除数量
- 最终 validate 通过股票池数量

不要只给页面链接或只报最终候选数。

## 失败恢复路由

| 信号 | 先看 | 下一步 |
| --- | --- | --- |
| 422 / 参数错误 | `run_manifest.json`、stderr | 修正 provider 参数后重跑整轮 |
| 429 / timeout | `history_metadata.json`、stderr | 降低批次、增加 `request_interval_seconds`、拆轮次重跑 |
| `invalid_rows > 0` | `history_metadata.json` | 剔除或显式 `--drop-invalid-rows`，再重跑历史 |
| `non_trading_rows > 0` 或 `st_rows > 0` | `history_metadata.json` | 形成剔除清单，重跑 clean history |
| `output_written=false` / validate 失败 | `summary.json`、validate stderr | 修输入或缩短 claim，不要写成 0 候选成功 |
| `source_scope=unknown` 的 `prices-input` 复跑 | `summary.json`、同目录 metadata 文件 | 确认同目录至少存在 `metadata.json` 或 `history_metadata.json`；缺失时补齐 provenance 后再重跑 |

## 现在不要让 Agent 做的事

- 不要在全 A 第一轮就急着生成 HTML 报告。
- 不要把默认 `max-history-symbols=50` 当成全市场命令。
- 不要把一轮 partial 或 strict gate failed 的产物写成“真实扫描完成”。
- 不要把 `mode=auto` 当成“工作流已经自动选对”。
- 不要把 `report.html` 当成比 `summary.json`、`history_metadata.json`、`run_manifest.json` 更高的事实源。
