# Pytdx Default Endpoint Evidence 2026-07-17

本报告记录 `fetch_pytdx_a_share.py` 默认 endpoint 从 `218.6.170.47:7709` 调整到 `180.153.18.170:7709` 后的本机真实短窗口复验。它只证明当前代码、当前参数、当前网络和所请求 symbol 的行为，不构成投资建议，也不证明 Pytdx 长期稳定、免费额度、官方授权、商业使用权、全 A 覆盖、候选质量、prediction、回测收益、券商订单或真实成交。

## 变更边界

- 调整依据: [EXTERNAL-SOURCE-STABILITY-2026-07-17.md](EXTERNAL-SOURCE-STABILITY-2026-07-17.md) 中旧默认 `218.6.170.47:7709` 的 3/3 严格失败，以及显式 `180.153.18.170:7709` 的 3/3 单 symbol 成功和两 symbol 成功。
- 代码默认值: `scripts/lib/fetch/pytdx_a_share.py` 的 `DEFAULT_HOST=180.153.18.170`、`DEFAULT_PORT=7709`。
- 显式覆盖: fetch CLI 继续使用 `--host/--port`；外部 source probe 新增 `--pytdx-host/--pytdx-port` 并原样转发到 fetch CLI。
- 禁止行为: 不实现 host 自动轮换、自动探测备用 host、自动 source selection 或自动 source fallback。指定其他 endpoint 必须由调用者显式传参，metadata 必须保留实际 `host/port`。

## 原始产物和命令

- 原始 artifact 根目录: `/tmp/a-share-selection-pytdx-default-20260717`。
- 单 symbol artifact: `iteration-1`、`iteration-2`、`iteration-3`。
- 两 symbol artifact: `two-symbols`。
- 补充审计重放 artifact: `audit-default-command`，其中保留 `prices.csv`、`metadata.json`、`stdout.txt` 和 `stderr.txt`；该请求不传 endpoint 覆盖，exit `0`。
- 依赖版本: `pytdx=1.72`。

三次单 symbol 调用均未传 `--host` 或 `--port`，因此验证的是更新后的代码默认值。每次使用以下有效参数，输出目录按 `iteration-1` 至 `iteration-3` 递增：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pytdx \
  python skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --output /tmp/a-share-selection-pytdx-default-20260717/iteration-N/prices.csv \
  --metadata-output /tmp/a-share-selection-pytdx-default-20260717/iteration-N/metadata.json \
  --timeout-seconds 10 \
  --max-pages 1 \
  --fail-on-fetch-error
```

两 symbol 复验同样不传 endpoint 覆盖参数：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pandas --with numpy --with pytdx \
  python skills/a-share-selection-strategy/scripts/fetch_pytdx_a_share.py \
  --symbols 000001,600000 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --output /tmp/a-share-selection-pytdx-default-20260717/two-symbols/prices.csv \
  --metadata-output /tmp/a-share-selection-pytdx-default-20260717/two-symbols/metadata.json \
  --timeout-seconds 10 \
  --max-pages 1 \
  --fail-on-fetch-error
```

`/tmp` artifact 不随仓库提交。复核时应读取上述 metadata 和 CSV，并用下列 SHA-256 检查文件未变化：

| Artifact | SHA-256 |
| --- | --- |
| 单 symbol 三份 metadata | `c04c9512512a2a4672ab67507514b045c7f7f6baac0495151b103e5f32a8e220` |
| 单 symbol 三份 prices CSV | `be48f79d5b976781ad038bb8847058e76dd487205111d5c4d42a867cb8f987f7` |
| 两 symbol metadata | `1670cb0280178479c193ed3d86632044f36623b830e9da94b948e21b112ade46` |
| 两 symbol prices CSV | `753cff186d25d7ece485502dc112f6e33103b6cf4e97e5d92d2f1ce5ad4f2eb3` |
| 补充审计重放 metadata | `c04c9512512a2a4672ab67507514b045c7f7f6baac0495151b103e5f32a8e220` |
| 补充审计重放 prices CSV | `be48f79d5b976781ad038bb8847058e76dd487205111d5c4d42a867cb8f987f7` |
| 补充审计重放 stdout | `146042fe8a0ab41ceaa13dfbf70f9af569f52d6791f390732ee9b10312009bf8` |
| 补充审计重放 stderr | `7f8f78a1491996867a32edc1e305108f96856b2507aa6facb15ae85e770bc984` |

## 真实复验结果

| 请求 | 次数 | 结果 | 关键 metadata |
| --- | ---: | --- | --- |
| `000001`，未传 endpoint 覆盖 | 3 | `3/3` exit `0`；每次 13 行 | `host=180.153.18.170`、`port=7709`、`symbol_count=1`、`failed_symbols=[]`、`empty_symbols=[]`、`api_request_count=1`、`possibly_truncated_symbols=[]` |
| `000001,600000`，未传 endpoint 覆盖 | 1 | exit `0`；共 26 行，每个 symbol 13 行 | `symbol_count=2`、`api_request_count=2`、两个 symbol 均 `window_complete=true`，无 failed/empty/truncated symbol |
| `000001`，补充审计重放，未传 endpoint 覆盖 | 1 | exit `0`；13 行；完整 stdout/stderr 已保留 | 与三次单 symbol 请求相同的 `host/port`、失败关闭和字段边界 |

两 symbol 请求的每个 symbol 都以一页 335 raw rows 覆盖窗口，输出 13 行，`reached_start_boundary=true`、`provider_exhausted=false`。该请求的 `overfetch_rows=644` 是为覆盖历史窗口的正常观测，不是行缺失或全市场吞吐指标。

所有成功 metadata 仍为 `token_configured=false`、`selection_ready=false`，并明确缺少 `turn`、`tradestatus`、`isST`、`name`，保留 `license_claim_boundary=pypi_license_unknown_readme_personal_research_boundary`。因此新默认 endpoint 只改善当前小窗口 OHLCV/amount 拉取的可达性，不会把 Pytdx 提升为全 A 主历史源或 strict selection merge 来源。

## 依赖警告

最初三次单 symbol 和一次两 symbol 请求没有分别保留 stderr 文件。为使警告可复核，补充审计重放已把完整 stderr 写入 `audit-default-command/stderr.txt`，其中由第三方 `pytdx=1.72` 的 `reader/block_reader.py` 产生两条 `SyntaxWarning`，提示代码使用 `is not` 比较 literal。该命令仍 exit `0`，仓库代码没有吞没或降级该告警。本任务不通过过滤、忽略或 monkey patch 隐藏第三方告警；后续若升级依赖，必须重新执行本报告的真实复验和本地合同测试。

## 不可外推项

1. `3/3` 成功只说明本轮 host、端口、日期窗口、symbol 和网络可用，不证明 endpoint 长期稳定、未来可用或优于其他 host。
2. 当前 fetch/probe 都不会在失败时自动换 host。默认 endpoint 失败仍必须保留 metadata、非零退出并由调用者决定显式恢复动作。
3. Pytdx 仍缺严格选股所需的换手率、停牌、ST 和名称字段，`selection_ready=false` 不变。不能作为全 A 主路径、全 A breadth、prediction-derived 输入或可交易性证明。
4. 本报告没有运行候选评分、LightGBM、回测、券商或成交流程，不能从网络成功推导任何策略、收益或交易结论。
