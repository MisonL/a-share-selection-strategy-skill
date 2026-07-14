# 2026-07-14 full-A provenance 真实任务复验

## 复验范围

本报告记录 2026-07-14 对本地保留真实 A 股 artifact 的重新清洗、provenance 生成和最终 runner 复验。它证明当前代码能对 universe、history、clean pool、最终过滤和评分输出做 fail-closed 对账，不证明实时行情、prediction 模型质量、券商成交、收益或投资建议。

数据基准：

- universe snapshot: 2026-07-13，Baostock 沪深 A 股 5,202 个 symbol。
- history: 2025-01-02 至 2026-07-13，1,888,327 行，5,202 个 symbol。
- 原 history metadata SHA-256: `68be64010094c1b2ca66f2b9b1cd1e8c91f2cb3c17cb996e8010a0c78a848d4d`。
- 原 history metadata 早于 `raw_dimension_counts_not_additive` 合同。复验在新目录生成升级副本，只补充可由已有计数唯一推导的 `raw_quality_counter_semantics` 和 `raw_invalid_non_trading_overlap_rows=3607`，并记录原路径、原 SHA 和推导规则；未修改原文件或行情行。
- 升级 metadata SHA-256: `f4d62063496bfd6df3e88f95d7332818a3e88fa1fb62f154f318d2aad912886e`。

## clean-pool 与 provenance

当前 `prepare_clean_history_pool.py` 重建结果：

- history: 5,202 symbols / 1,888,327 rows。
- clean pool: 5,166 symbols / 1,886,135 rows。
- short-history 排除: 36 symbols。
- 逐标 `date_max` 早于共同 as-of: 6 symbols，分别为 `000008`、`002005`、`002677`、`300567`、`301234`、`603580`。
- `full_market_closure_eligible=false`。
- `full_market_closure_boundary=clean_pool_removed_symbols_not_full_market`。
- proof SHA-256: `4ae168d70f80804b6e56f5c0945586cab760b3a2954eb559fd44658afe945fb3`。

provenance schema v2 同时验证：

- universe 至少 4,000 symbols，且 Baostock source/type/count/date/path 合同完整。
- universe snapshot、history metadata end date、history 全局实际最大交易日一致。
- 每个 history symbol 的实际最大交易日都单独检查；stale symbol 使 closure eligibility 收缩。
- clean 与 history 去除明确 removed symbols 后的列名、列序、行序和每列值完全一致。
- 所有绑定 artifact 在语义复算前后分别计算 SHA-256；验证窗口内替换会失败。

## 最终 runner 结果

最终代码复验输出目录：`/tmp/a-share-full-run-v4-AI78vm`。

- 完整命令 wall time: 84.17 秒。
- score profile: 26.172144 秒。
- score 输入: 1,883,949 rows / 5,160 symbols。
- group scoring: 12.429548 秒。
- 最终 freshness 过滤: 再排除 6 个 stale symbols。
- diagnostics: 5,160 rows，精确覆盖最终评分 symbol 集合。
- candidates: 33 rows；这里只是 generic 技术筛选结果，不是买卖建议。
- `full_a_provenance_validation_status=valid`。
- `full_a_provenance_final_scoring_validated=true`。
- `full_market_claim_allowed=false`。
- `full_market_claim_boundary=clean_pool_removed_symbols_not_full_market`。
- `full_a_provenance_output_cleanup_errors=[]`。

最终 artifact SHA-256：

- `run_manifest.json`: `a02e4cf3d3eca58a4ccaceb95e3a4d4d0a804c720146bb0d115e0d5518eaefae`
- `summary.json`: `82636585f5243de93c95c933ed1f42d96fdf248b2dec0d48c2f79ebbfa64429d`
- `candidates.csv`: `3cc2c28a9d4b98a152015f235bc49658bff6e47427a9a6c052b8b30dd5b4dca8`
- `diagnostics.csv`: `900b762b6f4305b2b0f34e00046bdfbd5f023d66eae290e2e94779e0c7df2f9a`

## 性能判断

完整 runner 的主要额外成本来自 220MB history 和 53MB clean artifact 的语义复算及前后双 SHA-256，而不是 26.17 秒 score 子进程本身。曾验证单次指纹可缩短约 8 秒，但 OMP 复核复现了 fingerprint 与内容重读脱钩的替换窗口，因此最终实现保留双指纹。后续性能优化只能采用同一打开流上的 hash+parse、不可变文件句柄或等价原子快照，不能再次复用与实际解析内容脱钩的旧指纹。

## 验证与审查

- `PYTHONDONTWRITEBYTECODE=1 python3 validate_skill_changes.py`: 退出 0。
- full unittest suite: 785 tests passed。
- full-A provenance 定向测试: 35 tests passed，包含 content/row/column-order tamper、per-symbol stale、schema v1、双指纹 TOCTOU、runner pre/post-score 和清理失败。
- Claude 最终复核: 两个阻塞项已关闭，无新阻塞问题。
- OMP `newapi-responses/grok-4.5` 最终复核: 两个阻塞项已关闭，无新阻塞问题。
- CodeRabbit: 3 个 issues；采纳 Skill 首轮读取字段补全。未采纳 `< as_of` 建议，因为本合同要求严格等于共同 as-of，未来日期同样应 fail-closed；未采纳新 coverage class，因为有效但不满足全 A 的真实分类仍是 `local_input`。

## 结论边界

本次真实任务证明 `5,202 -> 5,166 -> 5,160 -> 33` 链路可重现、可审计，且排除存在时不会错误提升全市场声明。它不证明全 A 零缺口，不证明 33 个候选可交易或有收益，也不构成投资建议。
