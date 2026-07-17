# External Source Stability Evidence 2026-07-17

本报告记录 2026-07-17 在当前本机网络环境完成的三次短窗口外部数据源探测。它只用于复核稳定 CLI 的失败关闭、metadata 留存和当前短窗口行为，不构成投资建议，不证明全 A 覆盖、长期稳定性、免费额度、授权持续有效、prediction、回测收益、券商订单或真实成交。

## 运行边界和原始产物

- Harness: `scripts/probe_external_source_stability.py`。
- 迭代数: `3`；每次都依次调用 Eastmoney spot、Baostock universe、Akshare、Pytdx、yfinance、Baostock history 和 ZZShare history 的稳定 CLI。
- 历史窗口: `2025-08-25` 至 `2025-09-10`。Baostock universe 使用 probe-only `--lookback-days 7`，本轮解析快照日为 `2026-07-17`。
- 原始 artifact 根目录: `/tmp/a-share-selection-p3-external-20260717`。
- 汇总 manifest: `/tmp/a-share-selection-p3-external-20260717/summary.json`。
- 汇总 manifest SHA-256: `2b4c7c4f654ae9d72ee33bb1a8d901d3b8faaf1e2ed153e52a4b7eca1b071649`。
- Harness 退出码: `3`。这是预期的严格失败关闭，因为 Eastmoney spot 和默认 Pytdx 均未通过全部三次。

父级 Harness 命令本身不会写入 manifest；以下重放命令使用 manifest 中 `.results[].command` 记录的相同有效窗口、迭代数、输出路径和默认探针参数。21 条实际子命令、stdout、stderr、检查项和每次 metadata 都保存在上述 `summary.json` 中。

```bash
python3 skills/a-share-selection-strategy/scripts/probe_external_source_stability.py \
  --output-dir /tmp/a-share-selection-p3-external-20260717/runs \
  --summary-output /tmp/a-share-selection-p3-external-20260717/summary.json \
  --iterations 3 \
  --akshare-start-date 2025-08-25 \
  --akshare-end-date 2025-09-10 \
  --pytdx-start-date 2025-08-25 \
  --pytdx-end-date 2025-09-10 \
  --yfinance-start-date 2025-08-25 \
  --yfinance-end-date 2025-09-10 \
  --baostock-start-date 2025-08-25 \
  --baostock-end-date 2025-09-10 \
  --zzshare-start-date 2025-08-25 \
  --zzshare-end-date 2025-09-10
```

`/tmp` artifact 是本次审计的易失性原始证据，不随仓库提交。复核时先验证 SHA-256，再读取 manifest 的 `summary`、`.results[].command` 和对应 metadata 路径；不得仅根据本报告文字推导结果。

## 探测结果

| Source | 三次结果 | 本轮可证实的短窗口事实 | 失败或观察项 |
| --- | --- | --- | --- |
| Eastmoney spot | `0/3`，均 exit `3` | 每次都写入 metadata，严格 CLI 正确拒绝 partial snapshot | 1 page、100 page size、10 秒 timeout、5 retries 后仍为 `Remote end closed connection without response`；`raw_items=0`、`partial_result=true`、CSV 未写入 |
| Baostock universe | `3/3`，均 exit `0` | 每次解析 `5,199` raw/filtered items，`partial_result=false`，metadata 和 CSV 均已写入 | 只证明本轮 lookback 7 天内的 universe snapshot 调用，不证明全市场闭环或长期可用 |
| Akshare history | `3/3`，均 exit `0` | `000001,600000` 每次各 13 行，共 26 行，失败和空 symbol 均为空 | 三次 `hist_provider_clean` 均为非必需观察失败。`stock_zh_a_hist` 对两个 symbol 都报连接关闭，随后已披露地使用 `stock_zh_a_daily` 返回数据；不得把此结果写成单一内部 provider 稳定性证明 |
| Pytdx default | `0/3`，均 exit `3` | 每次 metadata 已写入，严格 CLI 保留失败和空 symbol 后不写 CSV | 默认 `218.6.170.47:7709` 对 `000001` 均报 `calling function error`，`api_request_count=0`、`rows=0`、`failed_symbols=1`、`empty_symbols=1` |
| yfinance | `3/3`，均 exit `0` | `AAPL,MSFT` 每次各 11 行，共 22 行；`auto_adjust_false_close` 已记录 | 仅为 US market label 的调用检查，不是 A-share 数据源、交易所或日历证明 |
| Baostock history | `3/3`，均 exit `0` | `000001,600000` 每次各 13 行，共 26 行；`adjustflag=3`，无 invalid/non-trading/tradestatus-missing rows | 只证明所请求 symbol 和窗口的历史调用，不证明全市场、实时行情或可交易性 |
| ZZShare history | `3/3`，均 exit `0` | `000001,600000` 每次各 13 行，共 26 行；无 failed/empty/possibly truncated symbol | metadata 保留 token、429、重试和额度字段；本轮不把成功调用外推为额度、免费性、授权或长期稳定性证明 |

汇总为 `21` 次 source run 中 `15` 次通过。manifest 固定输出 `all_sources_all_iterations_passed=false`、`long_term_stability_claim=not_proven` 和 `short_window_claim_boundary=current_window_parameters_network_only`。

## Pytdx 显式 Host 诊断

默认 Pytdx 失败后，单独执行了显式 host 诊断，产物位于 `/tmp/a-share-selection-p3-external-20260717/pytdx-explicit/`。该诊断不属于上述 7-source Harness 的 21 次统计，也没有修改当前代码默认值。

- 显式 `--host 180.153.18.170 --port 7709`，对 `000001` 的三次单 symbol 请求均成功：每次 13 行、`failed_symbols=[]`、`empty_symbols=[]`。
- 同一 host 对 `000001,600000` 的两 symbol 请求成功：共 26 行，每个 symbol 13 行，`api_request_count=2`，窗口完整。
- 两 symbol metadata 仍明确 `token_configured=false`、`selection_ready=false`，且缺少 `turn`、`tradestatus`、`isST`、`name`。`license_claim_boundary=pypi_license_unknown_readme_personal_research_boundary` 仍然存在。

该结果只表明此 host 在本轮参数和网络下可响应，不能证明默认 host 的永久失效，也不能证明替代 host 的长期稳定性、授权、商业使用权或选股字段完备性。任何默认 host 或 Harness 参数调整必须作为新的原子任务，补充本地合同测试和新的真实探测证据；不得在运行中自动轮换 host 或改为自动 source fallback。

## 失败关闭和范围裁定

1. Harness 对每个 source 使用显式稳定 CLI。Eastmoney 和默认 Pytdx 失败时保留 metadata 并以非零退出，不会被另一个 source 的成功结果掩盖。
2. Harness 没有 source routing、自动选源或跨 source fallback。Akshare 的 `fallback_errors` 是其自身稳定 fetch CLI 的已披露内部 provider 观察，不是 Harness 的隐式成功路径。
3. 本轮不产生候选、不运行 LightGBM、不执行回测，也不接入券商。所有历史和 spot 产物只用于 source 行为观察。
4. 本轮成功与失败均受日期、参数、网络、远端服务和依赖版本影响。它们不能升级当前真实门禁中的 `not_proven` 状态。

## 复核结果

- `summary.json` 中 21 条记录均有 source、command、return code、stdout、stderr、metadata 路径、output 路径、检查项和 `passed` 结果。
- Eastmoney 和默认 Pytdx 的失败均保留 metadata，且没有输出被误作为成功 CSV。
- Akshare 的非必需 observation failure 在 summary 中计数为 `hist_provider_clean=3`，严格结果仍完整保留其 provider fallback 事实。
- 本报告只更新外部数据源证据入口，不改变全 A、prediction、回测、可交易性或券商门禁。
