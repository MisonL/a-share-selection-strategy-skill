# Current Real Scenario Gates

本文件是当前真实门禁状态的唯一人工入口，状态更新时间为 2026-07-17。它只汇总最新可追溯证据，不替代原始 dated report，也不把本地测试、历史成功或单次联网结果外推为长期能力。

## 事实优先级

发生冲突时按以下顺序判断：

1. 当前代码、当前命令退出码和本轮 artifact。
2. 本文件引用的最新 dated evidence。
3. 更早的历史 evidence。
4. 模板、示例和占位文本。

本文件只负责导航和当前边界。每项事实必须回到引用报告中的命令、日期、计数和 claim boundary；没有新证据时不得仅修改状态文字。

## 当前状态

| 门禁 | 当前状态 | 最新证据 | 已证明范围 | 仍未证明 |
| --- | --- | --- | --- | --- |
| 全 A 股票池、增量历史和 generic 评分 | `verified_limited_scope` | [FULL-A-INCREMENTAL-BAOSTOCK-2026-07-15.md](FULL-A-INCREMENTAL-BAOSTOCK-2026-07-15.md) | Baostock 5,200-symbol 计划完成分桶增量；clean pool 5,166 symbols；最终评分覆盖 5,160 symbols 并输出 34 个技术候选 | `full_market_claim_allowed=false`；4 个 no-trading stale symbols、36 个短历史 symbols 和 2 个 base extra symbols被显式排除；不证明零缺口、实时行情、可交易性或收益 |
| 全 A provenance 和失败关闭对账 | `verified_limited_scope` | [FULL-A-PROVENANCE-RUN-2026-07-14.md](FULL-A-PROVENANCE-RUN-2026-07-14.md) | universe、history、clean pool、最终过滤和 diagnostics 集合完成双指纹及 symbol-set 对账 | clean pool 有排除时仍必须保持 `full_market_claim_allowed=false`；不证明券商、收益或实时行情 |
| 真实 LightGBM prediction-derived | `verified_small_scope_only` | [REAL-SCENARIO-GATES-2026-05-30.md](REAL-SCENARIO-GATES-2026-05-30.md) | Baostock 真实行情上已有 2-symbol 最新日和 12-symbol、3 个信号日的 prediction 生成与评分证据 | 未证明全市场 prediction 质量、训练窗口无泄漏、长期稳定性或样本外收益 |
| 本地样本外回测和组合容量 | `verified_fixed_scope_only` | [CURRENT-GATES-CLOSEOUT-2026-06-08.md](CURRENT-GATES-CLOSEOUT-2026-06-08.md) | 固定 40-symbol、6 个信号日、48 个完成交易的本地 artifact 和容量门禁通过 | 未证明全市场收益、真实成交、券商容量、真实涨跌停规则或长期稳定性 |
| 真实涨跌停和完整可交易规则 | `not_proven` | [CURRENT-GATES-CLOSEOUT-2026-06-08.md](CURRENT-GATES-CLOSEOUT-2026-06-08.md) | `preclose/pctChg/tradestatus/isST` 可作为控制和诊断字段 | 直接涨跌停字段不可用，`limit_rules_model=not_modeled`，不得推导为规则门禁通过 |
| 外部数据源长期稳定性、额度和授权 | `not_proven` | [EXTERNAL-SOURCE-STABILITY-2026-07-17.md](EXTERNAL-SOURCE-STABILITY-2026-07-17.md)、[PYTDX-DEFAULT-ENDPOINT-2026-07-17.md](PYTDX-DEFAULT-ENDPOINT-2026-07-17.md) | 仅证明当前网络和参数下的 3 次短窗口探测：21 次调用中 15 次通过，Eastmoney spot 与旧默认 Pytdx 均为 0/3，Akshare 的内部 provider fallback 被显式记录；后续独立复验的新 Pytdx 默认 endpoint 单 symbol 3/3 和两 symbol 请求通过，不属于上述 21 次统计 | 不证明任一源长期稳定、未来免费、授权持续有效、默认或替代 Pytdx host 长期可用，或可自动 fallback |
| 券商订单、真实成交、滑点和真实资金容量 | `not_run` | [REAL-SCENARIO-GATES-2026-05-30.md](REAL-SCENARIO-GATES-2026-05-30.md) | 无 | 未接入真实券商门禁；任何本地 sizing、订单字段或 backtest 都不能替代 |

## 状态更新规则

- `verified_limited_scope` 只表示引用报告中的真实范围通过，不等于全市场、长期或生产通过。
- `verified_small_scope_only` 和 `verified_fixed_scope_only` 必须保留样本、日期、模型和 artifact 边界。
- `not_proven` 不能因本地单测、mock、demo、一次成功请求或字段推导改成通过。
- `not_run` 只能由对应真实环境命令和 artifact 关闭。
- 新 evidence 产生后，先验证原始报告，再更新本文件；历史报告继续保留原始日期和结论。

## 本地验证边界

`validate_skill_changes.py`、Skill quick validation、完整 unittest 和 GitHub Actions 只证明仓库本地合同。它们不改变上表任何真实门禁状态。
