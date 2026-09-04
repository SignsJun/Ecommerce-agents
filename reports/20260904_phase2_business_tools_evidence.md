# Phase 2 Business Tools + Evidence

日期：2026-09-04

## 做了什么

把 Phase 1 的 Snapshot / 日指标 / Issue 暴露为 13 个只读诊断 Tool。Tool 调 Service 算数，成功结果写入 Evidence；无 LLM、无 Diagnosis Agent。

ingest 增加 `ReviewRecord`（仅评分）。`DailyRunResult` 带回三个 InMemory repo，供 Tool 查询。

## 关键接口

`tools/diagnosis/`：`ToolContext`、`ToolResult`、`ToolError`、`invoke`、`investigate_issue`。

失败码：`not_found` / `empty_result` / `unavailable`。`get_promotion_history` 固定空列表，`produces_evidence=false`。

## 怎么跑

```text
python -m app.cli run-daily --data-dir <olist目录>
python -m app.cli investigate --data-dir <olist目录> [--issue-id ID]
```

## 测试

`pytest tests`：24 passed（含 `tests/contract/test_diagnosis_tools.py` 每 Tool 往返校验、缺实体错误形状、decompose/库存投影数值）。

## 相对 Phase 3

未做 Graph-guided ReAct、Context Builder、Prompt、LangGraph。Phase 3 直接挂 `registry.invoke`。
