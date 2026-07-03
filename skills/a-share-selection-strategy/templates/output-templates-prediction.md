# Output Templates - Prediction-derived

本文件是 `output-templates.md` 的按需展开模板库。只有快速路由指向本类问题时才读取本文件；模板占位项不能当作事实。

### prediction-derived 缺少 prediction

```markdown
## 无法按 prediction-derived 原口径评分
- 输入缺少 `prediction` 或 `prediction_score`，不能生成 prediction-derived 候选股。
- 常见错误文本是 `prediction-derived profile requires prediction or prediction_score column`。
- `prediction` 是上游 LightGBM 概率，不得用动量分、固定 `0.5`、mock 值或技术指标近似冒充。
- 当前可做：
  - 先提供或生成可追溯的上游 `prediction_score`，再运行 prediction-derived 评分。
  - 只做字段质量检查时，可先运行 prediction-derived profile 校验，让缺失字段显式失败。
- 即使使用 `generate_lightgbm_predictions.py`，也必须单独核验训练窗口、标签、特征、时间序列切分、跳过标的和未来泄漏风险。
```

### prediction-derived 预测列冲突

```markdown
## 预测列口径需要先统一
- 输入同时包含 `prediction_score` 和 `prediction` 且数值不一致时，prediction-derived profile 校验和评分都会失败。
- 常见错误文本是 `prediction and prediction_score both exist but differ` 和 `unify upstream prediction columns before prediction-derived scoring`。
- 不能用较高的一列解释 `min_prediction_score` 阈值应通过，也不能让评分脚本静默选择其中一列继续。
- `output_written=false` 或 `code=bad_input` 表示输入门禁失败，不是成功 0 候选。
- 合规路径是先统一预测列或审计上游字段映射，再重新运行 prediction-derived profile 校验和评分。
```

### 基础 OHLCV 不是 prediction-derived 输入

```markdown
## prediction-derived 门禁未通过
- 无 config 的 `validate_ohlcv.py` 通过，只证明基础 OHLCV 字段、日期和数值有效。
- `slice_prices_as_of.py` 退出 0 只说明切片非空并写出，不会补齐 prediction-derived 必需字段。
- prediction-derived 仍必须包含 `market=A-share`、可追溯的 `prediction` 或 `prediction_score`，以及真实 `turn` 或 `turnover`。
- `score_candidates.py --config skills/a-share-selection-strategy/scripts/prediction_profile_config.json` 报缺字段、`code=bad_input` 或 `output_written=false` 时，是输入门禁失败，不是成功 0 候选。
- 合规路径是补齐 prediction-derived 必需字段后，对切片文件重新运行 profile 校验和评分。
```

### LightGBM prediction 部分成功

```markdown
## LightGBM prediction 门禁未完整通过
- 非严格模式退出码为 0 但 `skipped_symbols>0` 时，只能说明部分标的写出了预测。
- 必须披露 `raw_symbols`、`predicted_symbols`、`skipped_symbols` 和 `skipped_symbol_examples`。
- 下游 `validate_ohlcv.py` 或 `score_candidates.py` 通过，只覆盖已写出的预测文件，不能反推上游全部标的通过。
- 完整门禁应使用 `--fail-on-skipped`，或显式确认 `raw_symbols == predicted_symbols` 且 `skipped_symbols == 0`。
- `prediction_summary.json` 中的 `feature_columns`、`split_method`、`scaler_fit_scope`、`label_definition`、训练/holdout 日期窗口和标签分布只是本次生成链路审计字段。
- `label_definition=target_return = close.shift(-horizon) / close - 1; class = target_return > train_mean` 只是相对训练集均值的二分类标签口径。
- `target_positive_labels` 和 `target_negative_labels` 非空只证明训练切分内两类标签都存在，不证明标签业务合理性、概率校准、holdout IC、跨窗口稳定性或样本外泛化。
- `holdout_auc` 只来自训练前缀之后、latest 之前的同一 symbol 时间后缀；`holdout_metric_status=not_computable` 时必须披露原因。它不是跨窗口、跨年份、分市场或全市场样本外泛化证明。
- `prediction_scope=latest_probability_repeated_for_scoring` 不是逐日历史预测序列；它表示最新预测概率被重复写入该标的评分窗口。
- `model_quality_scope=generation_audit_only` 和 `model_quality_metrics` 里的 `not_computed/not_evaluated/not_proven` 是机器可读边界声明，不是质量指标通过证明。
- 即使 summary 字段完整且 `holdout_auc` 可计算，也不能写成 LightGBM 模型质量、样本外泛化、IC、分层收益或全市场策略质量已证明。
```

### 历史窗口不足

```markdown
## 历史窗口不足，不能评分
- `validate_ohlcv.py --min-history-rows 0` 或低门槛校验通过，只说明基础字段、日期、数值和 profile 必需字段有效。
- 如果评分配置要求更长历史窗口，仍必须以 `score_candidates.py` 的 `insufficient_history_symbols` 和退出码为准。
- `code=bad_input output_written=false` 表示没有 symbol 可评分，不是成功的 0 候选结果。
- 合规表述是“debug 级字段校验通过，真实评分不可用，未产生候选”。
```

### 切片后历史窗口不足

```markdown
## 切片后仍不能评分
- 原始 prediction-derived 文件通过 `validate_ohlcv.py`，不代表 `slice_prices_as_of.py` 截断后的文件仍满足评分历史窗口。
- `slice_prices_as_of.py` 退出 0 只说明切片结果非空并已写出；必须披露切片 stdout 中的 `rows`、`date_min`、`date_max`、`actual_data_date` 和 `as_of_date_observed`。
- 对切片后的文件重新运行校验和评分；最终以 `score_candidates.py` 的退出码、`insufficient_history_symbols` 和 `output_written` 为准。
- `code=bad_input output_written=false` 或 `insufficient_history_symbols>0` 表示切片后不可评分，不是成功 0 候选。
- 合规表述是“原始文件校验通过、切片步骤成功，但切片后历史窗口未通过；需要选择更晚 as-of 日期或补足历史后重跑”。
```
