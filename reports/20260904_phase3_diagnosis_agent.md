# Phase 3 Diagnosis Agent

日期：2026-09-04

## 做了什么

Graph-guided ReAct 诊断 Agent：显式 while 循环（observe → reason → tool → update → stop）。邻域外工具不执行，记 `unavailable`。数值只来自 Tool。证据 ID 不在 State 里则从根因剔除；覆盖工具未跑通则禁止 confirmed。

## 关键接口

- `agents/diagnosis/agent.py`：`diagnose(issue, ctx, llm) -> DiagnoseOutcome`
- `agents/llm/client.py`：`LLMClient`；CLI 默认 DeepSeek（`.env` 的 `ECOM_LLM_*`）；pytest/evals 用 FakeLLM
- Prompt：`prompts/diagnosis/system_v1.md`（`prompt_version=diagnosis/system_v1`）
- 停止：max rounds 6、max tool 8、连续 2 轮无新 evidence、或高信心且覆盖工具已成功

```text
python -m app.cli diagnose --data-dir <olist目录>
python -m app.cli diagnose --data-dir <olist目录> --fake-llm
```

缺 `ECOM_LLM_API_KEY` 退出码 1，不改 FakeLLM。

## 测试

`pytest tests`：34 passed。含四类 Issue FakeLLM、邻域拒绝、停滞/轮次上限、伪造 evidence 不能 confirmed、无日指标 escalation、evals grounding=1.0。单测不打真实 LLM。

## 真实跑通

mini olist 利润侵蚀 Issue：`status=partial`，tools=4，irrelevant=0，`model=deepseek-chat`，产出带 evidence 的 `DiagnosisReport`。密钥未入库、未写入本报告。

## 相对 Phase 4

未做 Main Agent、Simulator、LangGraph、FastAPI、S05–S08。
