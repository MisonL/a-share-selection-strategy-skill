# Skill Optimization Closeout 2026-07-15

本报告记录 Skill 体系优化的本地收口状态。它只证明仓库合同和本地测试，不证明真实行情、prediction、回测、券商订单或投资结果。

## 提交边界

- `6bfd8fa chore: close audited skill baseline`
- `81c566f docs: establish current real gate index`
- `a667ee6 ci: bound validation execution time`
- `8d672f5 test: add exact CI dependency profile`

当前真实外部门禁统一从 `CURRENT-REAL-SCENARIO-GATES.md` 进入；dated evidence 保留原始范围和结论。

## 本地验证

精确 CI 依赖模式：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 validate_skill_changes.py --dependency-profile ci
```

- Exit code: `0`。
- Python: `3.11.12`。
- Direct dependencies: pandas `3.0.3`、numpy `2.4.6`、pyarrow `25.0.0`、PyYAML `6.0.3`。
- Tests: `845/845` passed。
- Unittest duration: `327.255s`。
- Unified gate wall time: `369.27s`。

最新兼容依赖模式：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 validate_skill_changes.py --dependency-profile latest
```

- Exit code: `0`。
- Tests: `845/845` passed。
- Unittest duration: `234.231s`。
- Unified gate wall time: `238.60s`。

两次运行均通过 task tracking、JSON、YAML、compileall、生产复杂度、Skill quick validation、git diff、文本、密钥和缓存门禁。耗时差异受依赖环境、缓存和本机负载影响，不是性能 SLA。

## CI 分片合同

| Shard | Test IDs |
| --- | ---: |
| `core` | 236 |
| `providers` | 155 |
| `gates` | 235 |
| `report` | 70 |
| `runner-core` | 40 |
| `runner-providers` | 28 |
| `runner-artifacts` | 28 |
| `runner-plan-resume` | 28 |
| `runner-universe` | 25 |

总计 845 个唯一 test ID，与完整 discovery 全集相等且无重复。每个 GitHub Actions matrix job 的总超时为 15 分钟；validator 每个子进程默认上限为 600 秒，真实 0.01 秒超时探针已确认错误会包含命令和秒数并显式失败。

## 远端状态

本报告首次写入时本轮提交尚未推送，远端九分片状态为 `pending`。在对应 GitHub Actions 完成前不得写成远端已验证。

## 未执行的外部门禁

- 本轮没有重新联网执行真实全 A 行情抓取。
- 本轮没有重新生成真实 LightGBM prediction。
- 本轮没有重新执行样本外策略回测、券商订单、真实成交、滑点或券商容量门禁。
- 数据源长期稳定性、额度、免费边界和授权持续性仍未证明。
