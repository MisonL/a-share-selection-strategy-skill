# P2A-BAOSTOCK-LIMIT-FIELDS-2026-05-30

## 范围

本报告只记录 baostock 日 K 字段可用性探测。目标是确认是否存在可直接用于真实涨跌停规则门禁的字段，不建模涨跌停规则，不从 `preclose`、`pctChg`、股票前缀或 `isST` 推断规则。

## 命令

```bash
uv run --with pandas --with numpy --with baostock python scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST,turn,volume,amount \
  --output /tmp/stock-selection-p2a-limit-field-probe-20260601T064758Z/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

退出码: `0`。

标准输出摘要:

```text
OK: source=baostock probe_type=limit_field_availability symbols=4 supported_candidate_fields=0 unsupported_candidate_fields=5 supported_direct_limit_fields=0 supported_trading_state_fields=0 available_control_fields=7 provider_error_fields=0 control_rows=364 direct_limit_field_available=False trading_state_field_available=False limit_rules_model=not_modeled
```

产物:

- `/tmp/stock-selection-p2a-limit-field-probe-20260601T064758Z/baostock_limit_field_probe.json`

## JSON 契约

关键字段:

- `schema_version=2`
- `source=baostock`
- `probe_type=limit_field_availability`
- `requested_symbols=000001,600000,300750,688981`
- `start_date=2025-08-25`
- `end_date=2025-09-10`
- `frequency=d`
- `adjustflag=3`
- `limit_rules_model=not_modeled`
- `rule_inference_performed=false`

汇总:

- `supported_candidate_fields=[]`
- `unsupported_candidate_fields=up_limit,down_limit,limit_status,is_trading,suspended`
- `provider_error_fields=[]`
- `available_control_fields=preclose,pctChg,tradestatus,isST,turn,volume,amount`
- `control_rows=364`
- `supported_direct_limit_fields=[]`
- `supported_trading_state_fields=[]`
- `direct_limit_field_available=false`
- `trading_state_field_available=false`

## 字段结果

候选字段:

- `up_limit`: `unsupported`，错误码 `10004012`，行数 `0`。
- `down_limit`: `unsupported`，错误码 `10004012`，行数 `0`。
- `limit_status`: `unsupported`，错误码 `10004012`，行数 `0`。
- `is_trading`: `unsupported`，错误码 `10004012`，行数 `0`。
- `suspended`: `unsupported`，错误码 `10004012`，行数 `0`。

控制字段:

- `preclose`: `supported`，行数 `52`，缺失 `0`，范围 `11.7` 到 `325.37`。
- `pctChg`: `supported`，行数 `52`，缺失 `6`，范围 `-10.2562` 到 `17.4466`。
- `tradestatus`: `supported`，行数 `52`，缺失 `0`，计数 `0=6, 1=46`。
- `isST`: `supported`，行数 `52`，缺失 `0`，计数 `0=52`。
- `turn`: `supported`，行数 `52`，缺失 `6`，范围 `0.1961` 到 `12.1725`。
- `volume`: `supported`，行数 `52`，缺失 `6`，范围 `23024462.0` 到 `304508753.0`。
- `amount`: `supported`，行数 `52`，缺失 `6`，范围 `831883207.37` 到 `27118768322.0`。

## 2026-06-01 追加复验

命令:

```bash
uv run --with pandas --with numpy --with baostock python scripts/probe_baostock_limit_fields.py \
  --symbols 000001,600000,300750,688981 \
  --start-date 2025-08-25 \
  --end-date 2025-09-10 \
  --adjust 3 \
  --candidate-fields up_limit,down_limit,limit_status,is_trading,suspended \
  --control-fields preclose,pctChg,tradestatus,isST,turn,volume,amount \
  --output /tmp/stock-selection-p2a-limit-field-refresh-20260601T083800Z/baostock_limit_field_probe.json \
  --fail-on-provider-error \
  --require-control-rows
```

退出码: `0`。

标准输出摘要:

```text
OK: source=baostock probe_type=limit_field_availability symbols=4 supported_candidate_fields=0 unsupported_candidate_fields=5 supported_direct_limit_fields=0 supported_trading_state_fields=0 available_control_fields=7 provider_error_fields=0 control_rows=364 direct_limit_field_available=False trading_state_field_available=False limit_rules_model=not_modeled
```

产物:

- `/tmp/stock-selection-p2a-limit-field-refresh-20260601T083800Z/baostock_limit_field_probe.json`

关键 JSON 事实:

- `schema_version=2`
- `limit_rules_model=not_modeled`
- `rule_inference_performed=false`
- `summary.supported_candidate_fields=[]`
- `summary.unsupported_candidate_fields=up_limit,down_limit,limit_status,is_trading,suspended`
- `summary.provider_error_fields=[]`
- `summary.available_control_fields=preclose,pctChg,tradestatus,isST,turn,volume,amount`
- `summary.control_rows=364`
- `summary.supported_direct_limit_fields=[]`
- `summary.supported_trading_state_fields=[]`
- `summary.direct_limit_field_available=false`
- `summary.trading_state_field_available=false`

字段结果与上一轮一致: `up_limit/down_limit/limit_status/is_trading/suspended` 均为 `unsupported`，错误码均为 `10004012`，行数均为 `0`；`preclose/pctChg/tradestatus/isST/turn/volume/amount` 均可作为控制字段返回。控制字段中 `tradestatus` 计数为 `0=6, 1=46`，`isST` 计数为 `0=52`，`pctChg/turn/volume/amount` 各有 `6` 个缺失值。

## 结论

本次 P2a 只证明当前 baostock 日 K 接口在指定窗口内没有可直接消费的 `up_limit/down_limit/limit_status` 直接涨跌停字段，也没有可作为候选字段取到的 `is_trading/suspended` 交易状态字段。`preclose/pctChg/tradestatus/isST` 可作为行情诊断和停牌/交易状态控制字段，但不能被解释为真实涨跌停规则已建模。

P2 仍未通过。后续只有拿到可靠数据源的直接涨跌停字段，或另起明确建模任务并完成规则、复权、ST、科创板/创业板、上市初期和异常交易日契约验证后，才允许改变 `limit_rules_model=not_modeled`。
