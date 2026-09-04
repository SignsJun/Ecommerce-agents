# Diagnosis Runtime Guard

日期：2026-09-04

Adaptive Causal ReAct：Preflight 只做宽而浅筛查，Runtime 动态激活 Cause，Agent 自主深挖，Active Resolution Gate 只约束未交代的 ACTIVE Cause。

## 行为

- 利润侵蚀 Preflight：`get_issue_context` + `decompose_profit`（近7天 vs 前7天）
- `contribution_ratio > 0.15` → ACTIVE；否则 NON_MATERIAL / POSSIBLE
- Agent 动作：`call_tool` / `activate_cause` / `reject_cause` / `request_stop` / `escalate`
- Gate：仍有 ACTIVE 且预算未尽则拒绝 stop
- `confirmed` / `partial` / `insufficient_evidence` 由 Runtime 裁定；根因 confidence 不再因覆盖不全钳到 0.4
- SKU 上下文含 `roas_7d` / `roas_prev_7d` / `roas_30d`

```text
python -m app.cli diagnose --data-dir <olist目录>
```

## 测试

`pytest tests`：40 passed。含 material 激活、Gate 拒绝提前 stop、伪造 evidence、无日指标 escalation、Unnecessary Investigation Rate、四场景 grounding=1.0。

## 真实跑通

mini olist 利润侵蚀：Preflight 激活 refunds（0.77）与 ads（0.30）；`status=partial`，tools=8，irrelevant=0，根因带 evidence。密钥未入库。
