# 运行手册

本手册收纳可复制命令和门禁解释。根 [README.md](../../../README.md) 只保留入口、数据契约和常用路径；文档地图见 [../references/index.md](../references/index.md)。需要执行完整 demo、联网取数、回测或真实门禁复验时读本文件。

如果任务目标是“今日 A 股选股 / 真实 A 股选股 / 全 A / 全市场 / 扩大股票池 / 真实广度扫描”，且用户没有限定 symbol、板块、本地股票池或本地行情文件，先读 [full-a-strict-workflow.md](full-a-strict-workflow.md)。当前全 A 口径是沪深 A 股股票池（前缀过滤，不含北交所）；本文件中的 demo、小样本和单轮命令不能直接等价为全市场主路径。

## 场景快速路由

| 目标 | 读取章节 |
| --- | --- |
| 本地 demo 或低价超短离线诊断 | [本地 Demo](#本地-demo)、[低价超短离线诊断](#低价超短离线诊断) |
| 本地行情今日总控 | [今日 A 股总控 CLI](#今日-a-股总控-cli) |
| 联网取数后评分 | [真实行情入口](#真实行情入口) |
| prediction 生成 demo | [Prediction 生成 Demo](#prediction-生成-demo) |
| Parquet 输入验证 | [Parquet 输入](#parquet-输入) |
| 涨跌停字段或外部源稳定性 | [涨跌停字段探针](#涨跌停字段探针)、[外部源稳定性观察](#外部源稳定性观察) |
| P1/P2/P3 门禁、walk-forward 或组合容量 | [P1 组合容量门禁](#p1-组合容量门禁)、[单信号日定位链路](#单信号日定位链路) |
| 修改 skill 或代码后的验证 | [验证命令](#验证命令) |

## 目录

- [使用边界](#使用边界)
- [环境准备](#环境准备)
- [本地 Demo](#本地-demo)
- [低价超短离线诊断](#低价超短离线诊断)
- [Parquet 输入](#parquet-输入)
- [Prediction 生成 Demo](#prediction-生成-demo)
- [今日 A 股总控 CLI](#今日-a-股总控-cli)
- [真实行情入口](#真实行情入口)
- [涨跌停字段探针](#涨跌停字段探针)
- [外部源稳定性观察](#外部源稳定性观察)
- [P1 组合容量门禁](#p1-组合容量门禁)
- [单信号日定位链路](#单信号日定位链路)
- [验证命令](#验证命令)

## 使用边界

- 所有脚本以本地文件为稳定入口。
- 联网取数必须先落地 CSV/Parquet 和 metadata，再进入校验、评分和汇报。
- 本地 demo 只证明脚本链路可执行，不证明真实行情、真实 prediction、真实回测或收益。
- 任何 `output_written=true` 只表示对应产物或诊断报告已落盘；退出码、`quality_errors`、`errors` 和门禁字段仍是最终事实。

## 环境准备

主路径使用 `uv`：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --help
```

无 `uv` 时创建临时虚拟环境：

```bash
python3 -m venv /tmp/a-share-selection-skill-venv
/tmp/a-share-selection-skill-venv/bin/python -m pip install -r skills/a-share-selection-strategy/requirements.txt
```

后续命令可把 `uv run --with pandas --with numpy python` 等价替换为 `/tmp/a-share-selection-skill-venv/bin/python`。例如：

```bash
/tmp/a-share-selection-skill-venv/bin/python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --help
/tmp/a-share-selection-skill-venv/bin/python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py --help
```

需要联网取数或 ML 场景时，在同一 venv 里显式安装对应附加依赖，再运行原脚本命令；依赖缺失必须暴露为环境错误，不能改用 mock 数据或跳过门禁。

附加依赖：

下表路径默认相对本 Skill 目录；从仓库根目录执行时使用 `skills/a-share-selection-strategy/<文件名>`。

| 场景 | 依赖 |
| --- | --- |
| Parquet 输入 | `requirements-parquet.txt` 或 `pyarrow` / `fastparquet` |
| LightGBM prediction 生成器 | `requirements-ml.txt` |
| A 股 baostock 取数 | `baostock` |
| A 股 akshare 取数 | `akshare` |
| A 股 pytdx 取数 | `pytdx` |
| A 股 zzshare 取数 | `zzshare` |
| 海外 OHLCV 取数 | `yfinance` |

常用场景按需安装：

| 场景 | 命令骨架 |
| --- | --- |
| 本地校验、评分、clean pool、增量计划 | `uv run --with pandas --with numpy python ...` |
| 全 A 股票池 universe | `uv run --with baostock python skills/a-share-selection-strategy/scripts/fetch_baostock_a_share_universe.py --lookback-days 7 --retries 1 --retry-interval-seconds 1 ...` |
| 全 A 实时展示增强 | `python skills/a-share-selection-strategy/scripts/fetch_eastmoney_a_share_spot.py ...` |
| 全 A zzshare 历史 breadth | `uv run --with pandas --with numpy --with zzshare python ...` |
| baostock 小范围核验 | `uv run --with pandas --with numpy --with baostock python ...` |
| akshare A 股或港股补充 | `uv run --with pandas --with numpy --with akshare python ...` |
| pytdx A 股补充 | `uv run --with pandas --with numpy --with pytdx python ...` |
| yfinance 海外 ticker 补充 | `uv run --with pandas --with numpy --with yfinance python ...` |

`fetch_baostock_a_share_universe.py` 与 `run_today_a_share_selection.py --fetch-spot baostock_universe` 默认都不做日期回看；`--lookback-days 7` 或 runner 的 `--spot-fallback-lookback-days 7` 是显式选择。若 `date_fallback_used=true`，必须同时披露 `resolved_snapshot_date`，不能写成当日股票池。

依赖按场景显式安装，不默认全装。`baostock_universe` 是当前全 A 股票池主入口；`eastmoney` spot 无第三方包依赖，只用于实时展示增强或对照快照；`zzshare` 是当前全 A 历史主路径；`baostock`、`akshare`、`pytdx` 和 `yfinance` 只作为补充或核验源，不作为静默 fallback。

完全离线环境必须提前准备解释器、wheelhouse 或包缓存。依赖失败时应显式报告，不能改用 mock 数据或跳过依赖。
若只做离线只读测试且本机已有依赖缓存，可把下面的 `uv run --with ...` 改成 `uv run --offline --with ...`；缓存缺依赖时应报告环境问题，而不是联网或改用模拟成功。

## 本地 Demo

### 生成数据

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-demo
```

### 基础校验

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.csv
```

### 通用评分

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices.csv \
  --config skills/a-share-selection-strategy/configs/example_config.json \
  --output /tmp/a-share-selection-demo/candidates.csv \
  --profile-output /tmp/a-share-selection-demo/score_profile.json
```

`--profile-output` 是显式性能观测开关，记录输入规模、候选/诊断行数和评分阶段耗时，不改变候选、诊断、排序或失败语义。默认不传时不创建 profile；评分失败时也会清理同路径的陈旧 profile，避免旧结果被误认为本轮产物。使用今日总控时，对应开关是 `run_today_a_share_selection.py --score-profile`。

### prediction-derived 消费层评分

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices_with_prediction.csv \
  --config skills/a-share-selection-strategy/configs/prediction_profile_config.json
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices_with_prediction.csv \
  --config skills/a-share-selection-strategy/configs/prediction_profile_config.json \
  --output /tmp/a-share-selection-demo/prediction_candidates.csv
```

`prices_with_prediction.csv` 中的 `prediction_score` 是合成输入。该路径只证明评分脚本能消费预测列，不证明真实模型质量。

## 低价超短离线诊断

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py \
  --output /tmp/a-share-selection-low-price-demo \
  --days 160 \
  --scenario low-price-ultra-short
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /tmp/a-share-selection-low-price-demo/prices.csv \
  --spot-input /tmp/a-share-selection-low-price-demo/spot.csv \
  --output-dir /tmp/a-share-selection-low-price-demo/today \
  --mode auto \
  --html-report-language zh
```

检查：

- `summary.json`: `requested_mode`、`mode`、`mode_decision`、`mode_decision_reason`、`missing_prediction_column_groups`、`missing_prediction_requirement`、`consumes_prediction_columns`、`prediction_input_source`、`requested_prediction_input_source`、`prediction_model_executed_by_runner`、`source`、`source_scope`、`runner_source_scope`、`candidate_rows`、`candidate_field_coverage`、`selection_failed_reason`、`selection_failed_next_action`、`plan_only_reason`、`plan_only_next_action`、`planned_parameters`、`step_summary`、`diagnostic_rows`、`spot_matched_symbols`、`input_metadata`、`input_csv_provenance`、`source_provenance`、`history_metadata_file_exists`、`html_report_language`、`html_report_initial_language`、`html_report_error_type`、`summary_output_written`、`manifest_output_written`、`candidates_output_written`、`diagnostics_output_written`。
- `input_csv_provenance`: 若 `real_market_data`、`source_scope` 或 `source_claim_boundary` 为 `mixed`、`unknown` 或空值，只能说明本地 CSV 内嵌来源信息混合或未完整声明，不能写成真实全量行情、今日全市场覆盖或交易日历门禁通过。
- `source_provenance`: 汇总 `input_metadata` 和 CSV 内嵌来源字段，便于机器消费；旧字段仍保留，冲突时以本次 `summary.json`、`run_manifest.json` 和 CSV 机器字段为准。
- `run_manifest.json`: `html_report_enabled=false` 表示 `--no-html-report` 主动关闭 HTML；此时 `summary.html_report_written=false` 且 `html_report_error_type=""` 不是报告生成失败。
- `report.html`: 浏览器可读汇总，展示候选、字段覆盖率、诊断、步骤和证据路径；默认 `--html-report-language auto` 跟随运行环境，也可传 `zh` 或 `en` 并在浏览器内切换；只从已写出的 JSON/CSV 派生，不能替代退出码或机器字段。
- `candidates.csv`: 候选字段、spot 展示字段，以及 prediction 披露字段；低价超短 demo 显式传 `--spot-input spot.csv` 后，`spot_industry` 应展示 demo 行业。
- `diagnostics.csv`: `failed_thresholds`、`failed_thresholds_zh`、`selection_status`、`short_reason`，以及与候选一致的 prediction 披露字段。
- 价格、成交额、换手率、ST、停牌和一字板失败项只代表 demo 覆盖，不代表真实今日 A 股扫描。

## Parquet 输入

```bash
uv run --with pandas --with numpy --with pyarrow python - <<'PY'
from pathlib import Path
import pandas as pd
base = Path("/tmp/a-share-selection-demo")
pd.read_csv(base / "prices.csv", dtype={"symbol": str}).to_parquet(
    base / "prices.parquet",
    index=False,
)
PY
uv run --with pandas --with numpy --with pyarrow python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-demo/prices.parquet
uv run --with pandas --with numpy --with pyarrow python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-demo/prices.parquet \
  --config skills/a-share-selection-strategy/configs/example_config.json \
  --output /tmp/a-share-selection-demo/candidates_parquet.csv
```

当前候选输出和今日总控标准产物仍包含 CSV。`run_today_a_share_selection.py` 标准输出为 `run_manifest.json`、`summary.json`、`report.html`、`candidates.csv`、`diagnostics.csv`，并会使用 CSV 中间产物。若用户要求全链路中间完全不出现 CSV，必须先说明需要改造脚本输出、runner 固定路径、artifact validator 和测试。

## Prediction 生成 Demo

```bash
python3 skills/a-share-selection-strategy/scripts/create_demo_data.py --output /tmp/a-share-selection-ml-demo --days 220
uv run --with pandas --with numpy --with scikit-learn --with lightgbm \
  python skills/a-share-selection-strategy/scripts/generate_lightgbm_predictions.py \
  --input /tmp/a-share-selection-ml-demo/prices.csv \
  --output /tmp/a-share-selection-ml-demo/prices_generated_prediction.csv \
  --summary-output /tmp/a-share-selection-ml-demo/prediction_summary.json \
  --fail-on-skipped
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-ml-demo/prices_generated_prediction.csv \
  --config skills/a-share-selection-strategy/configs/prediction_profile_config.json
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-ml-demo/prices_generated_prediction.csv \
  --config skills/a-share-selection-strategy/configs/prediction_profile_config.json \
  --output /tmp/a-share-selection-ml-demo/prediction_candidates.csv \
  --fail-on-skipped \
  --fail-on-empty-result
```

核查 `prediction_summary.json`：

- `feature_columns`
- `split_method`
- `scaler_fit_scope`
- `label_definition`
- `prediction_scope`
- 每个 symbol 的训练窗口、标签分布、`skipped_reason`

`prediction_scope=latest_probability_repeated_for_scoring` 表示最新预测概率被重复写入该标的所有行，供评分脚本消费当前概率；不是逐日历史预测序列。

## 今日 A 股总控 CLI

### 本地行情输入

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /path/to/prices.csv \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fail-on-skipped
```

`--mode auto` 决策：

| 输入 | 实际 mode | 口径 |
| --- | --- | --- |
| 缺少 prediction-derived 必需列 | `generic` | 低价超短通用技术评分 |
| 同时已有 `market` + (`prediction` 或 `prediction_score`) + (`turn` 或 `turnover`) | `prediction` | 消费外部 prediction 输入 |

显式 `--mode prediction` 缺字段时必须失败并保留 manifest，不得自动改走通用评分；此时 `summary.selection_failed_reason=missing_prediction_columns`，`selection_failed_next_action=provide_prediction_or_prediction_score_or_use_generic_mode`。这些失败收口字段也会同步到 `run_manifest.json` 顶层，便于单文件审计。

### 合并东方财富实时快照展示字段

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --prices-input /path/to/prices.csv \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fetch-spot eastmoney \
  --spot-pages 5 \
  --fail-on-partial-spot
```

`spot_price`、`spot_pct_chg`、`spot_amount`、`spot_industry` 只进入候选和诊断展示，不参与核心评分。若 metadata 写出 `partial_result=true`，不能写成全市场实时扫描完成；优先同时看 `source_type`、`real_market_data`、`data_source_note`、`coverage_claim`、`source_claim_boundary`、`output_written`、`metadata_output_written`、`errors`、`started_at`、`finished_at` 和 `duration_seconds`，partial 场景应收束为 `partial_spot_snapshot_not_full_market_completion`。

### 总控 CLI 抓历史

低价超短剖面需要 `tradestatus/isST` 等可交易字段，优先用 baostock：

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

`--symbols` 接受 `000001`、`600000`、`sh.600000`、`sz.000001`，manifest 和 `selected_symbols.json` 会记录归一化后的六位代码。

### 从快照筛选小样本历史抓取标的

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/run_today_a_share_selection.py \
  --output-dir /tmp/a-share-selection-today \
  --mode auto \
  --fetch-spot eastmoney \
  --spot-pages 5 \
  --derive-symbols-from-spot \
  --max-history-symbols 50 \
  --history-source baostock \
  --start-date 2025-01-01 \
  --end-date 2026-05-29 \
  --fail-on-partial-spot \
  --fail-on-skipped
```

`--max-history-symbols 50` 在这里是“小样本演示上限”，不是全 A 推荐值。
如果目标是全市场 breadth 或扩大股票池，不要复用这条命令；改读 [full-a-strict-workflow.md](full-a-strict-workflow.md)，并显式设置 `--derive-all-spot-symbols`、适合该轮任务的 `--max-history-symbols`、批次策略和中间 artifact 检查。

`selected_symbols.json` 只证明按 spot 字段筛出了历史抓取列表，不证明实时全市场扫描完整，也不证明这些标的最终通过历史评分。未传 `--derive-all-spot-symbols` 时，spot 派生会先应用当前配置的价格、成交额和 ST 预筛；这适合候选池缩小，不适合全 A 历史 breadth。

本地或抓取的 spot 输入在历史筛选和 `score_candidates.py --spot-input` 中使用同一套 symbol 归一化规则：symbol 列支持 `symbol/code/code_id/stock_code/ticker/Ticker`，`sh.600000`、`600000.SH`、`sz.000001`、`000001.SZ` 会归一化为六位代码后匹配。`summary.json.spot_matched_symbols` 是排查 spot 展示字段是否实际合并的首选字段。

generic 技术评分不消费输入中的 `prediction` 或 `prediction_score` 列。需要使用外部预测列时，必须走 prediction-derived 配置或今日入口的 `mode=prediction`/`auto -> prediction`。

## 真实行情入口

### Baostock A 股历史日线

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/fetch_baostock_a_share.py \
  --symbols 000001,600000 \
  --names-input /tmp/a-share-selection-a-share/universe.csv \
  --missing-name-policy query \
  --non-trading-policy reject \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-a-share/prices.csv \
  --metadata-output /tmp/a-share-selection-a-share/metadata.json \
  --fail-on-fetch-error
```

门禁不能只看退出码，还要检查 metadata：

- `rows > 0`
- `symbol_count == len(requested_symbols)`
- `failed_symbols == []`
- `empty_symbols == []`
- `invalid_rows == 0`
- `non_trading_rows == 0`

`--names-input` 接受带 `symbol/name` 的 CSV 或 Parquet；完整覆盖时不会调用逐 symbol 的 `query_stock_basic`，缺失项按 `--missing-name-policy=query/fail/blank` 显式处理。`run_today_a_share_selection.py` 同时抓取 `baostock_universe` spot 和 baostock history 时，会自动复用本次 `spot.csv`；其他输入必须显式传 `--history-names-input`。

非交易行默认 `--non-trading-policy reject`；`drop` 会写入 `raw_non_trading_rows/dropped_non_trading_rows`，`keep` 会保留并披露。若使用 `--drop-invalid-rows`，必须披露 `dropped_invalid_rows` 和示例。

### Akshare A 股日线

```bash
uv run --with pandas --with numpy --with akshare python skills/a-share-selection-strategy/scripts/fetch_akshare_a_share.py \
  --symbols 000001 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-akshare/prices.csv \
  --metadata-output /tmp/a-share-selection-akshare/metadata.json \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-akshare/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-akshare/prices.csv \
  --config skills/a-share-selection-strategy/configs/example_config.json \
  --output /tmp/a-share-selection-akshare/candidates.csv \
  --diagnostics-output /tmp/a-share-selection-akshare/score_diagnostics.csv
```

akshare A 股入口会先尝试中文列接口，失败或空结果时记录 `fallback_errors` 并转用 `stock_zh_a_daily`。fallback 成功不等于主接口稳定可用。akshare 输出不生成真实 `prediction/prediction_score`。

### pytdx A 股日线

```bash
uv run --with pandas --with numpy --with pytdx python skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001,600000 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-pytdx/prices.csv \
  --metadata-output /tmp/a-share-selection-pytdx/metadata.json \
  --timeout-seconds 10 \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-pytdx/prices.csv
```

pytdx 入口通过 TDX 兼容行情服务器抓取日线 OHLCV，不需要 token；但 PyPI license metadata 为 UNKNOWN，包内 README 明确是个人协议研究/习作边界，机构或商业使用权、长期稳定性和官方数据授权都不能由本仓库证明。近期窗口的首请求会按起始日距当前日自适应缩小，未触达起始边界时后续恢复整页并按实际返回行数累计 offset；达到 `max-pages` 仍未触达时写入 `possibly_truncated_symbols`。优先检查 `requested_raw_rows/raw_rows/output_rows/overfetch_rows/api_request_count`。

pytdx 输出缺 `turn/tradestatus/isST/name`，provider 不返回名称时 `name` 保持空值并记录 `name_value_policy=blank_missing_provider_name`，不得把 symbol 写成名称。`selection_ready=false`，只能作为 no-token OHLCV/amount 补充或对照，不能替代 zzshare 全 A 历史 breadth、baostock 严格可交易字段核验或 prediction-derived 口径。补充字段的 join key 只能是同一 `symbol+date`；不得按 symbol 使用最近一条 strict 字段、前向填充或把旧交易日 strict 字段拼到新交易日。当前没有同日 strict companion 的 Pytdx 增量 verified merge 会显式失败。

### zzshare A 股日线

```bash
uv run --with pandas --with numpy --with zzshare python skills/a-share-selection-strategy/scripts/fetch_zzshare_a_share.py \
  --symbols 000001,600000 \
  --start-date 2025-09-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-zzshare/prices.csv \
  --metadata-output /tmp/a-share-selection-zzshare/metadata.json \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-zzshare/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-zzshare/prices.csv \
  --config skills/a-share-selection-strategy/configs/example_config.json \
  --output /tmp/a-share-selection-zzshare/candidates.csv \
  --diagnostics-output /tmp/a-share-selection-zzshare/score_diagnostics.csv
```

zzshare 入口默认使用 `daily(fields=all)`，并把 `source_scope=zzshare_history_fetch`、`real_market_data=true`、`partial_result`、`token_configured`、`request_interval_seconds`、`limit`、`max_pages`、`possibly_truncated_symbols`、`unprocessed_symbols`、`rate_limit_budget_exhausted`、`rate_limit_exhaustion_reason`、`source_claim_boundary` 写入 metadata。无 token 可用不等于无限频率或长期稳定；直接调用 `fetch_zzshare_a_share.py` 时可用 `--symbols` 或 `--symbols-file`，两者互斥。`--non-trading-policy` 默认是 `fail`，基础门禁会强制检查 `invalid_rows == dropped_invalid_rows`、`non_trading_rows == 0`、`tradestatus_missing_rows == 0` 和限流预算未耗尽；加 `--fail-on-fetch-error` 后还会检查 `failed_symbols == []`、`empty_symbols == []`、`possibly_truncated_symbols == []`、`symbol_count == requested_symbols` 和实际 `date_min/date_max`。任何 `unprocessed_symbols` 都会导致请求数对账失败，不能当成空结果或成功抓取。

`run_today_a_share_selection.py --history-source zzshare` 会透传 `--history-http-url`、`--history-timeout-seconds`、`--history-request-interval-seconds`、`--history-max-concurrent-symbol-requests`、`--history-max-rate-limit-sleep-seconds`、`--history-max-429-events`、`--history-max-runtime-seconds`、`--history-limit`、`--history-max-pages`、`--history-non-trading-policy`、`--history-checkpoint-batch-size`、`--history-resume-from-checkpoint` 和 `--history-progress-interval` 到 zzshare fetcher，并固定使用 `fields=all`。runner 未显式传值时，zzshare 默认使用 `history_non_trading_policy=drop`、`history_max_concurrent_symbol_requests=1`、`history_checkpoint_batch_size=100`、`history_progress_interval=100`；三项限流预算未传时沿用 fetcher 的 120 秒累计 429 sleep、3 次 429 和 900 秒总运行时间默认值。显式值会进入 `run_manifest.json`、`summary.json`、`history_metadata.json` 和候选/诊断 CSV provenance。runner 会实时透出 zzshare fetcher 的 `PROGRESS:` stderr 行，同时完整捕获 stdout/stderr 写入 `run_manifest.json`。zzshare token 只能通过 `ZZSHARE_TOKEN` 环境变量提供；不要把 token 放进 runner CLI 参数，因为 runner 会把 step command 写入 `run_manifest.json`。对 zzshare 长列表，runner 会传 `--symbols-file`；显式文件沿用用户路径，内部生成列表写入 `history_symbols.txt`。

`history_non_trading_policy=drop` 只表示把 `tradestatus != 1` 的行过滤出评分输入；必须同时披露 `raw_non_trading_rows`、`history_dropped_non_trading_rows`、`history_retained_non_trading_rows`、`history_checkpoint_enabled`、`history_checkpoint_symbols_skipped` 和 `history_checkpoint_requests_executed`。这不是全 A 完成证明，也不能替代 `failed_symbols`、`empty_symbols`、`possibly_truncated_symbols`、`unprocessed_symbols`、`rate_limit_budget_exhausted`、`invalid_rows` 和 `tradestatus_missing_rows` 的门禁检查。

长 symbol 列表、预演和恢复：

- `--symbols-file /path/to/symbols.txt` 支持逗号或换行分隔；`run_manifest.json.execution_path_reason=explicit_symbols_file`，仍是显式股票池。
- `--plan-only` 只写计划和审计所需输入快照，stdout 以 `PLAN_ONLY:` 开头，`run_manifest.json.commands_executed=false`、`steps[].executed=false`；它不能证明取数、校验或评分成功。若没有真实历史 artifact，`summary.history_output_written=false`、`history_metadata_output_written=false`、`history_artifact_status=not_written`，不要只看计划中的路径字段。`summary.plan_only_reason=plan_only_no_commands_executed`、`plan_only_next_action=execute_planned_workflow_to_collect_artifacts` 只表示计划未执行，不代表运行失败；`summary.planned_parameters` 是本轮计划会使用的非空抓取/日期参数，`summary.steps` 是步骤数量，完整命令仍看 `run_manifest.json.steps[]`，轻量状态可看 `summary.step_summary[]`。
- `--resume-from /path/to/run_manifest.json` 从上一轮 `selected_symbols.json` 和 `history_metadata.json` 生成 `resume_retry_symbols`；只覆盖失败、空结果、截断或因预算耗尽未处理 symbol 的恢复，不等于全市场完成。
- `--history-resume-from-checkpoint` 只复用当前输出目录 `history_checkpoints/` 中执行契约一致、文件大小和 SHA-256 匹配、symbol 行数对账通过的 completed checkpoint 分片；缺少指纹或内容篡改会记录完整性问题并重抓。它和 `--resume-from` 不是同一层恢复。前者恢复同一轮抓取进度，后者基于上一轮 metadata 生成失败、空、截断和未处理 symbol 重试清单。
- `--resume-from` 会继承上一轮 `history_source/start_date/end_date` 中本轮未显式设置的值；`history_adjust/history_timeout_seconds/history_request_interval_seconds/history_max_concurrent_symbol_requests`、三项限流预算、`history_limit/history_max_pages/history_non_trading_policy` 只在本轮历史源与上一轮一致时继承，并写入 `resume_inherited_options`。`history_http_url` 可能包含 signed query 或内部地址，不从上一轮 manifest 自动继承；需要复用时必须本轮显式传 `--history-http-url`，manifest 会用 `resume_sensitive_options_requiring_explicit_input` 提醒。若上一轮 manifest 里的 `output_dir` 是相对路径，会先判断该路径是否已经指向 manifest 所在目录，否则按该 `run_manifest.json` 所在目录解析。
- 如果上一轮没有失败、空结果、截断或未处理 symbol，`--resume-from` 应失败并提示没有可重试 symbol；不要用它替代显式 `--symbols-file` 全量复跑。

clean pool 和增量计划：

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/prepare_clean_history_pool.py \
  --prices-input "$RUN/pass1/prices.csv" \
  --history-metadata "$RUN/pass1/history_metadata.json" \
  --short-history "$RUN/pass1/short_history_symbols.json" \
  --output "$RUN/clean/prices.csv" \
  --metadata-output "$RUN/clean/history_metadata.json" \
  --metadata-alias-output "$RUN/clean/metadata.json" \
  --report-output "$RUN/clean/clean_history_report.json"
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/prepare_incremental_history_plan.py \
  --spot-input "$RUN/spot.csv" \
  --prices-input "$RUN/clean/prices.parquet" \
  --history-metadata "$RUN/clean/history_metadata.json" \
  --min-history-rows 120 \
  --target-end-date "$END_DATE" \
  --output "$RUN/incremental/incremental_history_plan.json" \
  --symbols-output "$RUN/incremental/incremental_history_symbols.txt"
```

`full_market_closure_eligible=true` 还要求至少 4,000 个 symbol、完整 baostock metadata 对账、每个 history symbol 达到共同 `as_of_date`，并且 clean 与 history 去除 removed symbols 后全行全列等价；该下限只用于拒绝局部样本，不能独立证明全市场。下文“上游零排除”同时包含 breadth、逐标 freshness、lineage 和 metadata 门禁通过，不是只检查 clean 删除数。

`prepare_clean_history_pool.py` 只从已有 artifacts 剔除 `empty/failed/possibly_truncated/unprocessed/short_history` symbol；需要 `metadata.json` 兼容副本供最终 `prices-input` 复跑读取时，必须显式传 `--metadata-alias-output`。它不是重新取数成功证明。需要检查 universe 到 clean pool 的完整 lineage 时，成组传入 `--universe-input --universe-metadata --provenance-output`；输出会绑定 universe、raw history、clean outputs 和可选 short-history 清单的集合、计数、路径和 SHA-256，并在复核时重算语义。universe 的 resolved snapshot、history metadata 的 `end_date` 和实际最大交易日必须一致，最终 `--min-symbol-latest-date` 也必须等于 provenance 的 `history.as_of_date`，不能通过传入更早日期放宽 freshness。该文件的 `full_market_closure_eligible=false` 不得提升 runner 的 `full_market_claim_allowed`，有 clean 剔除时尤其如此；当前 provenance 模式不接受 `--incremental-*`，避免内存 merged frame 被伪装为可复核 raw artifact。最终评分可显式传 `run_today_a_share_selection.py --full-a-provenance`，但它要求 `--prices-input`/`--spot-input` 精确匹配证明中的 clean/universe 路径，并同时要求 `--filter-prices-to-spot-universe --min-symbol-latest-date`；`--plan-only`、`--fetch-spot`、证明篡改、最终集合错配或 diagnostics 未覆盖全部最终 prices 都显式失败。评分后对账失败会清理本轮 candidates/diagnostics；`full_a_provenance_output_cleanup_errors` 非空时必须披露残余输出路径。只有上游零排除、最终过滤零剔除且评分后集合对账通过时，runner 才把 breadth 的 `full_market_claim_allowed` 设为 true；该字段不证明实时行情、模型、成交或收益。`prepare_incremental_history_plan.py` 强制读取 clean prices 的 `symbol/date` 与 metadata 的 `rows/date_min/date_max` 对账；不一致时显式失败。不存在、零行、缺少最新日期、metadata 失败/空/截断/未处理或少于 `--min-history-rows` 的历史进入 full bucket，有效但过期的历史进入 delta bucket；只有 `source_scope=clean_history_pool` 且带正数剔除原因的审计子集可以保留原始 partial/限流耗尽事实并继续规划。`fetch_buckets[]` 必须与 `fetch_symbols` 一一对账，full bucket 的历史起始日由执行命令显式提供。后续仍需逐 bucket 抓取、validate 和评分。增量抓取完成后，可把 `--incremental-plan --incremental-prices --incremental-metadata` 一起传回 `prepare_clean_history_pool.py`，在清洗前合并 delta；该合并会拒绝 failed/empty/truncated/unprocessed 或 `rate_limit_budget_exhausted=true` 的 delta、缺失计划 symbol、未达到 `target_end_date` 或超过目标日期的增量数据。

标准执行入口是 `execute_incremental_history_plan.py`。必须显式选择 `zzshare`、`baostock` 或 `pytdx`，full bucket 必须传 `--full-start-date`；入口不会隐式切换 provider。zzshare bucket 默认 `--zzshare-non-trading-policy fail`，需要剔除历史停牌行时必须显式传 `drop`，需要保留停牌事实供最终评分排除时显式传 `keep`。执行器还可显式透传 `--zzshare-request-interval-seconds`、`--zzshare-max-concurrent-symbol-requests`、`--zzshare-max-rate-limit-sleep-seconds`、`--zzshare-max-429-events`、`--zzshare-max-runtime-seconds` 和 `--zzshare-progress-interval`；未传时保持 fetcher 默认，传入值会进入 execution manifest，且这些选项不能用于其他 provider。每个 bucket 独立落盘；完成前会从 CSV 重算 symbol/date/rows，与计划和 metadata 的每证券统计对账，并拒绝空文件、重复行、缺失证券、越界日期、partial/rate-limit/unprocessed 状态。失败后以 `--resume` 重试时只复用文件 SHA-256、artifact 校验和 execution contract digest 都一致的 complete bucket；digest 绑定 provider、计划的 source/claim/目标日/min rows/symbols/buckets、full start、checkpoint 与 provider 参数，`generated_at`、耗时和吞吐等非语义观测字段变化不会让同路径计划失效。语义字段、provider 参数或桶文件内容变化会重新执行或拒绝复用。manifest 用 `executed_bucket_count/reused_bucket_count` 区分本轮实际抓取与复用；复用记录的 `current_run_duration_seconds=0`，原始成本保留在 `artifact_fetch_duration_seconds`。聚合 CSV 和 metadata 会先分别写入同目录暂存文件再成对发布；任一步失败都记录 `partial/failed_stage=aggregate_outputs` 并保留既有两份最终产物。零 fetch bucket 会记录 `no_op=true` 并移除陈旧聚合产物，不能继续执行 verified merge。聚合成功不等于 strict 字段、全 A 完整性或评分门禁通过；Pytdx bucket 可独立落盘和聚合，但没有同日 strict companion 时不能执行 verified selection merge。

zzshare 429 控制默认参数为 `--max-429-events 3 --max-rate-limit-sleep-seconds 120 --max-runtime-seconds 900`。若 metadata 中 `rate_limit_budget_exhausted=true`，必须保留 checkpoint 和 `unprocessed_symbols`，待冷却后显式 `--resume`；该状态不可报告为抓取成功，也不可将未处理 symbol 混入真实空结果清单。

最终基于 clean prices 复跑时，如同时有当前 `spot.csv` 和目标交易日，应显式加 `--filter-prices-to-spot-universe --min-symbol-latest-date "$END_DATE"`，让 runner 剔除当前 universe 外或最新日期过期的 symbol，并把 `prices_filter_*.json`、summary、stdout 和候选/诊断 CSV provenance 作为审计证据。大 clean prices 可显式加 `--prices-filter-output-format parquet`，让过滤后的运行内 prices 以 Parquet 进入 validate/score，减少 CSV 重写和读取成本。过滤证据会记录 input、spot、kept、removed 四个 symbol-set SHA-256；接入 full-A provenance 时，评分前读取 clean/final 的 `symbol` 列重算集合，评分后用已验证 final 集合的数量和哈希对账 diagnostics。过滤 Parquet 会同时写 `<prices>.metadata.json`，其中包含 artifact SHA-256/size/mtime、row/symbol/date 范围、symbol-set SHA-256、过滤契约和原始 input metadata；后续复用以路径、size 和 SHA-256 判定内容身份并重算表统计，mtime 仅作审计，单独触碰文件时间不会让内容相同的 artifact 失效。sidecar 缺失、摘要不匹配、内容篡改或统计漂移都会显式失败。symbol-set SHA-256 只证明 breadth 身份；该过滤只处理既有文件，不证明价格值或缺失历史已补齐。

### yfinance 通用 OHLCV

```bash
uv run --with pandas --with numpy --with yfinance python skills/a-share-selection-strategy/scripts/fetch_yfinance_ohlcv.py \
  --symbols AAPL,MSFT \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --output /tmp/a-share-selection-us/prices.csv \
  --metadata-output /tmp/a-share-selection-us/metadata.json \
  --timeout-seconds 30 \
  --fail-on-fetch-error
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py \
  --input /tmp/a-share-selection-us/prices.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py \
  --input /tmp/a-share-selection-us/prices.csv \
  --config skills/a-share-selection-strategy/configs/example_config.json \
  --output /tmp/a-share-selection-us/candidates.csv \
  --diagnostics-output /tmp/a-share-selection-us/score_diagnostics.csv \
  --fail-on-skipped \
  --fail-on-empty-result
```

yfinance 裸 OHLCV 不含 `turn` 或 `turnover`，通用评分会输出 `turnover_assumption=neutral_series_missing_turnover`。`end-date` 可能落在非交易日，实际数据范围以 metadata 中每个 symbol 的 `date_min/date_max` 为准。

## 涨跌停字段探针

真实涨跌停规则门禁当前仍是 `not_modeled`。`preclose/pctChg/tradestatus/isST` 只是行情控制和诊断字段，不是直接涨跌停字段。

完整控制字段严格探针：

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST,turn,volume,amount \
  --output /tmp/a-share-selection-p2a-limit-field-refresh/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

核心控制字段探针：

```bash
uv run --with pandas --with numpy --with baostock python skills/a-share-selection-strategy/scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST \
  --output /tmp/a-share-selection-p2a-limit-field-core/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

读取结果必须看 `provider_error_fields`、`unsupported_candidate_fields`、`supported_direct_limit_fields`、`supported_trading_state_fields`、`control_rows`、`rule_inference_performed=false` 和 `limit_rules_model=not_modeled`。

## 外部源稳定性观察

```bash
RUN_DIR=/tmp/a-share-selection-p3-external-$(date -u +%Y%m%dT%H%M%SZ)
uv run --with pandas --with numpy --with akshare --with yfinance --with baostock --with zzshare --with pytdx \
  python skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
    --output-dir "$RUN_DIR/runs" \
    --summary-output "$RUN_DIR/summary.json" \
    --iterations 3 \
    --eastmoney-pages 1 \
    --eastmoney-retries 5 \
    --eastmoney-retry-interval-seconds 1 \
    --baostock-universe-lookback-days 7 \
    --akshare-symbols 000001,600000 \
    --pytdx-symbols 000001 \
    --yfinance-symbols AAPL,MSFT \
    --baostock-symbols 000001,600000 \
    --zzshare-symbols 000001,600000
```

读取 `summary.json` 时必须检查 `summary.sources.*.all_passed`、逐次 `metadata`、`checks` 和 `long_term_stability_claim=not_proven`。连续复验通过只说明当前窗口、参数和网络环境下通过，不能写成公网数据源长期稳定。

探针的 `--baostock-universe-lookback-days` 默认值是 7，只用于提高外部源短窗口观察的非空概率；这不改变 `fetch_baostock_a_share_universe.py` 和 runner 的生产默认值 0。

最小单轮探针的解释规则：

- `passed=true` 只说明该 symbol、该窗口、当前网络和当前参数可用。
- `eastmoney_spot` 失败时不能声称当前可自动切到其他 spot 源；未显式传 `--fetch-spot-fallback` 时不得声称自动切换，传了该参数时必须披露 `fetch_spot_fallback_used` 与 `fetch_spot_primary_failure`。
- `akshare` 出现 `fallback_errors` 时，即使 rows 大于 0，也不能写成 `stock_zh_a_hist` 主接口稳定。
- `pytdx` 成功时也只说明 no-token 小样本日线可用；该入口缺 `turn/tradestatus/isST/name`，不能作为全 A 主历史源。
- `zzshare.token_configured=false` 且成功时，只能说明无 token 小样本可用，不能证明大批量额度或长期稳定。
- `yfinance.market_label_only=true` 时，`market` 只是输出标签，不能当作交易所、日历或真实市场归属证明。
- `baostock` 通过小样本门禁时，仍不代表适合全 A 首轮历史抓取；全 A clean pool 复核才优先考虑它。若用 `query_all_stock` 准备对照股票池，必须先按沪深 A 股股票前缀过滤，排除指数、基金、ETF、B 股和北交所代码。
- 任何源的 `long_term_stability_claim` 都必须保持 `not_proven`，除非有独立长期监控和明确验收窗口。

## P1 组合容量门禁

真实回测必须先按信号日截断评分输入，避免用未来行情生成候选；回测价格文件可以保留信号日之后的真实行用于出场。默认使用 `portfolio_cash_lot_floor`，不把预期失败当作通过条件。

```bash
set -euo pipefail
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
RUN_DIR="/tmp/a-share-selection-p1-portfolio-capacity-$RUN_ID"
SYMBOLS=000009,000021,000039,000060,000069,000100,000157,000301,000338,000400,000423,000568,000625,000661,000708,000768,000786,000895,000963,001979,002001,002007,002024,002129,002179,002230,002236,002241,002252,002271,002304,002311,002352,002410,002459,002460,002466,002493,002508,002555
SIGNAL_DATES=(2025-03-20 2025-06-20 2025-09-19 2025-12-19 2026-04-17 2026-05-20)
uv run --with pandas --with numpy --with baostock --with-requirements skills/a-share-selection-strategy/requirements-ml.txt python skills/a-share-selection-strategy/scripts/run_baostock_walk_forward.py \
  --symbols "$SYMBOLS" \
  --start-date 2024-01-01 \
  --end-date 2026-05-29 \
  --signal-dates "${SIGNAL_DATES[@]}" \
  --output-dir "$RUN_DIR" \
  --allocation-model portfolio_cash_lot_floor \
  --cash-budget 3000000 \
  --max-open-positions 10 \
  --max-gross-weight 1.0 \
  --max-gross-notional 3000000 \
  --max-cash-reserved 3000000 \
  --fail-on-symbol-overlap \
  --drop-invalid-rows
python3 skills/a-share-selection-strategy/scripts/validate_walk_forward_manifest.py \
  --manifest "$RUN_DIR/run_manifest.json" \
  --output "$RUN_DIR/run_manifest_validation.json" \
  --signal-dates "${SIGNAL_DATES[@]}" \
  --expected-symbol-count 40 \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled
```

artifact validator 的期望值必须从刚生成的 artifact 提取：

```bash
eval "$(
RUN_DIR="$RUN_DIR" python3 - <<'PY'
import json
import os
import shlex
from pathlib import Path

def bash_array(name, values):
    words = " ".join(shlex.quote(str(value)) for value in values)
    print(f"{name}=({words})")

run = Path(os.environ["RUN_DIR"])
manifest = json.loads((run / "run_manifest.json").read_text())
summary = json.loads((run / "prediction_run_summary.json").read_text())
bash_array("VALIDATION_SIGNAL_DATES", manifest["signal_dates"])
bash_array("VALIDATION_SYMBOLS", manifest["symbols"])
bash_array("VALIDATION_CANDIDATES", [item["candidates"] for item in summary["signals"]])
print("FINAL_EQUITY=" + shlex.quote(str(summary["equity"]["final_equity"])))
print("PORTFOLIO_VIOLATIONS=" + shlex.quote(str(len(summary["portfolio"]["violations"]))))
PY
)"
python3 skills/a-share-selection-strategy/scripts/validate_walk_forward_artifacts.py \
  --run-dir "$RUN_DIR" \
  --output "$RUN_DIR/run_artifact_validation.json" \
  --signal-dates "${VALIDATION_SIGNAL_DATES[@]}" \
  --expected-symbols "${VALIDATION_SYMBOLS[@]}" \
  --expected-candidates "${VALIDATION_CANDIDATES[@]}" \
  --expected-final-equity "$FINAL_EQUITY" \
  --expected-portfolio-violations "$PORTFOLIO_VIOLATIONS" \
  --required-allocation-model portfolio_cash_lot_floor \
  --required-tradability-model tradestatus_entry_exit_only \
  --required-limit-rules-model not_modeled \
  --manifest-validation "$RUN_DIR/run_manifest_validation.json" \
  --cash-budget 3000000 \
  --allow-dropped-invalid-rows
```

口径：

- `portfolio_violations>0` 不是组合容量门禁通过。
- `--expect-portfolio-violations` 只用于复现已知违规，不用于证明门禁通过。
- artifact validator 未传 `--manifest-validation` 但 run 目录存在 `run_manifest_validation.json` 时会自动校验该报告；`manifest_checked=false` 时不能说 manifest 门禁已纳入 artifact 复验。
- `calendar_model=business_day_closed_interval` 不是交易所日历。
- `tradestatus_holding_period_bars` 只覆盖价格表内已观测 bar，不补足缺失交易日、节假日或涨跌停规则。

## 单信号日定位链路

该链路只用于定位步骤，不替代 P1 组合容量门禁。

```bash
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/slice_prices_as_of.py --input prices.csv --output prices_signal_window.csv --as-of-date YYYY-MM-DD
uv run --with-requirements skills/a-share-selection-strategy/requirements-ml.txt python skills/a-share-selection-strategy/scripts/generate_lightgbm_predictions.py --input prices_signal_window.csv --output predictions_signal_window.csv --summary-output prediction_summary.json --fail-on-skipped
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/validate_ohlcv.py --input predictions_signal_window.csv --config skills/a-share-selection-strategy/configs/prediction_profile_config.json
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/score_candidates.py --input predictions_signal_window.csv --config skills/a-share-selection-strategy/configs/prediction_profile_config.json --output prediction_candidates.csv --fail-on-skipped --fail-on-empty-result
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/allocate_candidate_capital.py --prices prices.csv --candidates prediction_candidates.csv --output prediction_sized_candidates.csv --cash-budget 1000000 --lot-size 100 --fail-on-unallocated
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/backtest_buy_hold.py --prices prices.csv --candidates prediction_sized_candidates.csv --output prediction_backtest.csv --hold-days 5 --fail-on-incomplete
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/portfolio_equity_curve.py --backtests prediction_backtest.csv --output prediction_equity_curve.csv
uv run --with pandas --with numpy python skills/a-share-selection-strategy/scripts/portfolio_overlap_report.py --backtests prediction_backtest.csv --daily-output prediction_daily_positions.csv --overlap-output prediction_overlap.csv --summary-output prediction_overlap_summary.json --max-gross-weight 1.0 --max-gross-notional 1000000 --max-cash-reserved 1000000 --require-capital-fields
uv run --with pandas python skills/a-share-selection-strategy/scripts/summarize_walk_forward_run.py --run-dir RUN_DIR --output RUN_DIR/prediction_run_summary.json --expected-symbol-count N --required-tradability-model tradestatus_entry_exit_only --required-limit-rules-model not_modeled
```

`slice_prices_as_of.py` 的输出 CSV 会保留 `requested_as_of_date`、`actual_data_date` 和 `as_of_date_observed`。如果请求日不是实际交易行，后续候选、诊断和 HTML 报告必须按 `actual_data_date` 或候选 `date` 解释真实信号日。

`allocate_candidate_capital.py` 的 stdout 必须披露 `cash_budget`、`lot_size`、`capital_model` 和 `claim_boundary=local_sizing_not_broker_order`。这些字段只证明本地 sizing 计算可追溯，不能解释为真实成交、券商订单或真实现金容量证明。严格回测汇总应对 `portfolio_equity_curve.py` 显式使用 `--fail-on-incomplete`，否则默认只基于 complete trades 生成权益曲线。

## 验证命令

推荐先使用统一本地验证入口:

```bash
python3 validate_skill_changes.py
```

该入口只覆盖本地仓库门禁，不证明真实行情、真实 prediction、券商订单或真实回测门禁通过。若需要拆开执行，对应命令如下:

以下拆分命令是 `validate_skill_changes.py` 的人工展开视图；新增或调整本地门禁时，先更新仓库根验证脚本，再同步本节。

```bash
for file in skills/a-share-selection-strategy/evals/*.json skills/a-share-selection-strategy/configs/*.json; do
  python3 -m json.tool "$file" >/tmp/"$(basename "$file")"
done
uv run --with pyyaml python - <<'PY'
import yaml
from pathlib import Path
manifests = sorted(Path("skills/a-share-selection-strategy/agents").glob("*.yaml"))
if not manifests:
    raise RuntimeError("no YAML agent manifest files found")
for manifest in manifests:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{manifest}: expected mapping root")
    interface = data.get("interface")
    if not isinstance(interface, dict):
        raise RuntimeError(f"{manifest}: missing interface mapping")
    for key in ["display_name", "short_description", "default_prompt"]:
        value = interface.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"{manifest}: missing interface.{key}")
PY
PYTHONPYCACHEPREFIX=/tmp/a-share-selection-pycache python3 -m compileall -q skills/a-share-selection-strategy/scripts
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pyarrow python -m unittest discover -s tests -v
```

Skill 结构校验器来自本机 skill-creator，不随本仓库发布：

```bash
QUICK_VALIDATE=/path/to/skill-creator/scripts/quick_validate.py
uv run --with pyyaml python "$QUICK_VALIDATE" skills/a-share-selection-strategy
```
