# 电商经营决策 Agent 技术规格与 AI 编码指南

**版本：v0.2（技术架构评审稿）**  
**用途：后续由 AI/开发者直接据此拆任务、生成代码、编写测试与迭代实现**  
**项目暂定名：E-commerce Operations Decision Agent / 电商经营决策 WorkBuddy**

---

## 0. 文档目的与当前结论

这份文档将前期业务设计进一步收敛为可编码的技术规格。目标不是给出某个框架的示例代码，而是定义整个系统的**领域模型、Agent 职责边界、状态生命周期、工具接口、模拟器接口、文档溯源机制、持久化、评测与开发约束**，使后续无论由人还是 AI 编码，都尽量沿着同一架构演进。

### 0.1 已基本确定的核心设计

1. 产品不是聊天机器人，而是**经营决策 Agent**：主动识别经营异常或机会，完成诊断、策略生成、策略核算/推演、推荐与后续跟踪。
2. 第一版核心经营对象：`Store -> SKU -> Campaign`；暂不做复杂多店铺、多仓、多供应商网络。
3. 第一版顶层经营问题：`Profit Erosion`、`Ad Inefficiency`、`Stockout Risk`、`Excess Inventory`。转化率、退款、评论、价格等首先作为根因和证据进入诊断。
4. Agent 采用三层职责：
   - **Main Decision Agent**：决定“应该怎么办”。
   - **Diagnosis Agent**：以受约束 ReAct / Graph-guided ReAct 方式调查“为什么”。
   - **Simulation Agent**：规划实验、选择 stress case，回答“这么做以后可能怎样”。
5. 真正的数值计算、异常检测、利润核算、库存演化、预测与世界状态变化均由确定性/预测服务完成，**LLM 不直接制造业务数值**。
6. `Simulator` 是工具化的 Business World / Decision Sandbox；`Simulation Agent` 是实验规划者，两者必须分离。
7. 系统必须显式区分：**真实观测、派生指标、Agent 判断、模拟未来**。
8. 每次经营决策既要有结构化 `DecisionState`，又要形成可阅读、可版本化、可溯源的 Decision Documents。
9. 每个结论必须尽可能绑定 `Evidence`；每个模拟结果必须绑定 `BusinessStateSnapshot`、模型/参数版本与 `Assumption`。
10. 第一版技术实现推荐：`Python + FastAPI + Pydantic v2 + LangGraph（或等价状态图 Runtime）+ PostgreSQL + 后台任务 Worker`。框架可替换，领域层不得绑定 LangGraph。

### 0.2 本文档新增的工程约束

除前期讨论外，本文档额外纳入以下容易被遗漏但必须提前设计的内容：

- Snapshot / Version / 并发与过期决策检测。
- 幂等写工具、失败恢复与异步 Simulation Job。
- Agent Context Builder，禁止直接把整库数据灌给模型。
- Prompt / Model / Tool / Simulator 版本记录。
- Data Quality / Data Freshness 状态。
- Event 模型与 Decision Lifecycle。
- 执行动作的风险等级与 Human Approval。
- Simulator 校准、Expected-vs-Actual 与长期 Decision Memory。
- Eval、Scenario Benchmark、回归测试与成本/延迟约束。
- 面向 AI 编码的 MUST / SHOULD / MUST NOT 规则。

---

# 1. 产品边界

## 1.1 目标用户

第一版面向中小型电商团队中的：

- 店铺运营负责人；
- 商品运营；
- 投放运营；
- 小型品牌负责人。

系统不试图替代完整 ERP、广告平台或供应链系统，而是作为其上层的**经营分析与决策协调层**。

## 1.2 核心价值

系统每天回答四个问题：

1. **现在经营正常吗？**
2. **如果不正常，为什么？**
3. **有哪些可行的解决方案？**
4. **这些方案未来 7/14/30 天可能怎样，哪个值得执行？**

核心目标不是最大化 GMV，而是优化综合经营质量：

```text
Business Value
= Profit
- Stockout Risk
- Excess Inventory / Cash Occupation
- Downside Risk
- Execution Cost
- Strategy Volatility
```

具体权重后续允许按经营模式配置。

## 1.3 v1 非目标（必须控制范围）

v1 不做：

- 通用电商客服；
- Listing 自动生成器；
- 全自动广告投放平台；
- 完整多仓、多店、多供应商供应链优化；
- 复杂采购合同和物流路由；
- 无边界 Multi-Agent 社会；
- 让 LLM 自己预测销量/利润数字；
- 直接宣称模拟器是真实数字孪生或 learned world model。

---

# 2. 总体系统架构

```text
                      ┌───────────────────────┐
                      │ User / Dashboard / Job│
                      └───────────┬───────────┘
                                  │
                                  ▼
                       ┌──────────────────────┐
                       │ Main Decision Agent  │
                       │   Operations Manager │
                       └───────┬───────┬──────┘
                               │       │
                    Why?       │       │ What if?
                               ▼       ▼
                     ┌────────────┐  ┌────────────────┐
                     │ Diagnosis  │  │ Simulation     │
                     │ Agent      │  │ Agent          │
                     └─────┬──────┘  └───────┬────────┘
                           │                 │
                           ▼                 ▼
                 ┌────────────────┐  ┌────────────────┐
                 │ Business Tools │  │ Business World │
                 │ / Causal Graph │  │ Simulator      │
                 └───────┬────────┘  └───────┬────────┘
                         │                   │
                         └─────────┬─────────┘
                                   ▼
                     ┌──────────────────────────┐
                     │ Deterministic Services   │
                     │ Metrics / Anomaly        │
                     │ Profit / Forecast        │
                     │ Validator / Simulation   │
                     └────────────┬─────────────┘
                                  ▼
                     ┌──────────────────────────┐
                     │ Data / State / Artifact  │
                     │ PostgreSQL + Document    │
                     │ Store + Decision Memory  │
                     └──────────────────────────┘
```

## 2.1 关键架构原则

### Principle A：Agent 负责认知，不负责基础计算

LLM 适合：

- 选择调查路径；
- 根据证据更新假设；
- 生成策略方向；
- 解释多目标权衡；
- 选择下一轮模拟实验；
- 形成最终建议。

LLM 不负责：

- 汇总 GMV；
- 计算利润；
- 计算 ROAS；
- 更新库存；
- 产生 Monte Carlo 随机数；
- 判断数据库是否写入成功。

### Principle B：State 是机器真相，Document 是可读档案

- `Structured State`：控制系统当前阶段、业务事实和机器可消费对象。
- `Decision Documents`：说明“为什么形成当前结论”，用于人类查看、历史检索和审计。
- 文档不是数据库 Source of Truth。

### Principle C：所有关键对象结构化

Agent 之间不得依赖长篇自由文本传递核心状态。主要交互对象必须是 Pydantic Schema，例如：

- `Issue`
- `DiagnosisReport`
- `Strategy`
- `SimulationReport`
- `DecisionRecord`

---

# 3. 两类入口与完整运行流程

## 3.1 主动经营模式

```text
Daily Data Refresh
       ↓
Metric Aggregation
       ↓
Anomaly Engine
       ↓
Issue Pool
       ↓
Prioritization
       ↓
Top Issues
       ↓
Main Decision Agent
       ↓
Diagnosis / Strategy / Simulation
       ↓
Morning Brief / Decision Cards
```

## 3.2 用户问题模式

用户可以直接问：

- “为什么最近利润下降？”
- “SKU A 现在值得继续加广告吗？”
- “如果把广告预算减 20%，两周后会怎样？”

系统根据问题直接进入对应阶段：

```text
User Question
     ↓
Intent / Target Resolution
     ↓
已有 Issue? ---- Yes ---> Reuse Current Context
     │
     No
     ↓
Build Temporary Issue / Query Context
     ↓
Diagnosis or Simulation
```

## 3.3 完整 Decision Lifecycle

```text
ISSUE_OPENED
   ↓
DIAGNOSING
   ↓
DIAGNOSED
   ↓
PLANNING
   ↓
VALIDATING
   ↓
SIMULATING
   ↓
EVALUATING
   ├── all plans weak ---> PLANNING
   │
   └── acceptable
         ↓
WAITING_APPROVAL
   ↓
EXECUTING
   ↓
MONITORING
   ├── expected deviation high ---> ISSUE_REOPENED / REPLAN
   └── success ------------------> RESOLVED
```

---

# 4. 数据语义：四种真相 + 一种决策记录

系统必须从类型和持久化层面区分以下五类信息。

## 4.1 Observed Truth

真实业务系统直接观测：

- 当前库存；
- 广告花费；
- 订单；
- 销售价格；
- 评论；
- 退款金额。

`DataProvenance = OBSERVED`

## 4.2 Analytical Truth

从真实数据确定性计算或统计：

- 利润率；
- 7 日趋势；
- 库存覆盖天数；
- ROAS；
- 历史基线。

`DataProvenance = DERIVED`

## 4.3 Model Estimated

预测模型输出：

- 未来 14 日需求分布；
- 广告 response curve；
- price elasticity；
- 退款概率。

`DataProvenance = MODEL_ESTIMATED`

## 4.4 Agent Belief

Agent 的业务推断：

- “广告效率下降是主要原因”；
- `confidence=0.88`；
- “仍缺乏退款根因证据”。

`DataProvenance = AGENT_INFERRED`

## 4.5 Simulated Future

Simulator Rollout：

- 14 日期望利润；
- P10/P50/P90；
- stockout probability；
- stability horizon。

`DataProvenance = SIMULATED`

## 4.6 Decision Record

记录在上述事实、推断和模拟基础上最终为什么选择某个方案。

---

# 5. 核心领域数据模型

以下 Schema 是项目最重要的公共语言。实际实现统一使用 Pydantic v2。

## 5.1 基础枚举

```python
class DataProvenance(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    MODEL_ESTIMATED = "model_estimated"
    AGENT_INFERRED = "agent_inferred"
    SIMULATED = "simulated"

class IssueType(str, Enum):
    PROFIT_EROSION = "profit_erosion"
    AD_INEFFICIENCY = "ad_inefficiency"
    STOCKOUT_RISK = "stockout_risk"
    EXCESS_INVENTORY = "excess_inventory"

class DecisionPhase(str, Enum):
    ISSUE_OPENED = "issue_opened"
    DIAGNOSING = "diagnosing"
    DIAGNOSED = "diagnosed"
    PLANNING = "planning"
    VALIDATING = "validating"
    SIMULATING = "simulating"
    EVALUATING = "evaluating"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    FAILED = "failed"
```

## 5.2 BusinessStateSnapshot

真实世界的只读快照，用于诊断和模拟基准。

```python
class BusinessStateSnapshot(BaseModel):
    snapshot_id: str
    version: int
    created_at: datetime
    data_freshness_at: datetime
    store: StoreState
    skus: dict[str, SKUState]
    campaigns: dict[str, CampaignState]
    data_quality: DataQualityReport
```

要求：

- Snapshot 创建后 immutable。
- 一次 Strategy Compare 中所有方案必须基于同一 Snapshot。
- Strategy 必须记录 `based_on_snapshot_id` 和 `based_on_state_version`。

## 5.3 SKUState

```python
class SKUState(BaseModel):
    sku_id: str
    category: str
    lifecycle_stage: str | None

    price: Decimal
    base_price: Decimal | None
    unit_cost: Decimal

    inventory_on_hand: int
    inventory_available: int
    incoming_inventory: int
    lead_time_days: int

    units_sold_7d: int
    units_sold_30d: int
    revenue_7d: Decimal
    profit_7d: Decimal
    profit_margin_7d: float

    conversion_rate_7d: float | None
    refund_rate_7d: float
    avg_rating_30d: float | None
```

## 5.4 CampaignState

```python
class CampaignState(BaseModel):
    campaign_id: str
    sku_id: str
    status: str
    daily_budget: Decimal
    spend_7d: Decimal
    attributed_revenue_7d: Decimal
    impressions_7d: int
    clicks_7d: int
    conversions_7d: int
    cpc_7d: Decimal | None
    cvr_7d: float | None
    roas_7d: float | None
    acos_7d: float | None
```

## 5.5 MetricState

用于把“一个数字”转换为有上下文的经营指标。

```python
class MetricState(BaseModel):
    metric_name: str
    entity_type: str
    entity_id: str

    current_value: float
    baseline_7d: float | None
    baseline_30d: float | None
    trend_7d: float | None
    trend_30d: float | None
    expected_low: float | None
    expected_high: float | None
    peer_median: float | None

    provenance: DataProvenance
    calculated_at: datetime
```

## 5.6 Evidence

Evidence 必须成为一等数据类型。

```python
class Evidence(BaseModel):
    evidence_id: str
    source_type: str
    source_ref: str | None

    entity_type: str | None
    entity_id: str | None
    metric: str | None
    value: Any
    comparison: str | None
    period: TimeRange | None

    description: str
    reliability: float
    provenance: DataProvenance

    tool_name: str | None
    tool_version: str | None
    snapshot_id: str | None
    created_at: datetime
```

任何 `RootCause` 的 supporting evidence 必须引用 `evidence_id`，不能只保留自然语言。

## 5.7 Issue

```python
class Issue(BaseModel):
    issue_id: str
    issue_type: IssueType
    entity_type: str
    entity_id: str

    detected_at: datetime
    severity: str
    confidence: float
    estimated_impact: Decimal | None
    impact_horizon_days: int | None

    evidence_ids: list[str]
    status: str
    based_on_snapshot_id: str
```

## 5.8 DiagnosisState

这是 Diagnosis Agent 内部认知状态，不等同真实业务状态。

```python
class DiagnosisState(BaseModel):
    diagnosis_id: str
    issue: Issue
    hypotheses: list[Hypothesis] = []
    evidence_ids: list[str] = []
    unresolved_questions: list[str] = []
    tool_history: list[ToolCallRecord] = []
    root_causes: list[RootCause] = []
    diagnosis_status: str = "in_progress"
    step_count: int = 0
```

## 5.9 Hypothesis / RootCause

```python
class Hypothesis(BaseModel):
    hypothesis_id: str
    cause_type: str
    description: str
    confidence: float
    supporting_evidence_ids: list[str] = []
    contradicting_evidence_ids: list[str] = []
    status: str

class RootCause(BaseModel):
    cause_type: str
    description: str
    confidence: float
    estimated_contribution: float | None
    supporting_evidence_ids: list[str]
```

> `confidence` 是 Agent 的判断信心，不宣称是严格统计概率。UI 和文档必须避免把它包装为精确概率。

## 5.10 DiagnosisReport

```python
class DiagnosisReport(BaseModel):
    diagnosis_id: str
    issue_id: str
    status: Literal["confirmed", "partial", "insufficient_evidence"]
    root_causes: list[RootCause]
    overall_confidence: float
    key_evidence_ids: list[str]
    uncertainties: list[str]
    generated_at: datetime
    agent_version: str
    model_version: str
```

## 5.11 BusinessAction

Business Action 使用 discriminated union。

```python
class AdjustAdBudget(BaseModel):
    action_type: Literal["adjust_ad_budget"]
    campaign_id: str
    change_pct: float = Field(ge=-0.30, le=0.30)

class PauseCampaign(BaseModel):
    action_type: Literal["pause_campaign"]
    campaign_id: str

class ReplenishInventory(BaseModel):
    action_type: Literal["replenish"]
    sku_id: str
    quantity: int = Field(gt=0)

class AdjustPrice(BaseModel):
    action_type: Literal["adjust_price"]
    sku_id: str
    change_pct: float = Field(ge=-0.15, le=0.10)

class UpdateListing(BaseModel):
    action_type: Literal["update_listing"]
    sku_id: str
    target_issue: str

BusinessAction = Annotated[
    AdjustAdBudget
    | PauseCampaign
    | ReplenishInventory
    | AdjustPrice
    | UpdateListing,
    Field(discriminator="action_type"),
]
```

具体上下限进入 `BusinessPolicyConfig`，上述数字仅作为 v1 默认值。

## 5.12 Strategy

```python
class Strategy(BaseModel):
    strategy_id: str
    issue_id: str
    name: str
    strategy_type: Literal["conservative", "balanced", "growth", "custom"]
    objective: str
    actions: list[BusinessAction]
    assumptions: list[Assumption]
    horizon_days: int

    based_on_snapshot_id: str
    based_on_state_version: int
    status: str
```

## 5.13 Assumption

```python
class Assumption(BaseModel):
    assumption_id: str
    description: str
    parameter: str | None
    assumed_value: float | None
    confidence: float
    source: str
    provenance: DataProvenance
```

## 5.14 SimulationRequest / SimulationReport

```python
class SimulationRequest(BaseModel):
    simulation_id: str
    base_snapshot_id: str
    strategy: Strategy
    horizon_days: int
    scenario: SimulationScenario
    rollout_count: int = 100
    random_seed: int | None = None

class SimulationReport(BaseModel):
    simulation_id: str
    strategy_id: str
    base_snapshot_id: str
    horizon_days: int

    expected_profit: Decimal
    baseline_profit: Decimal
    expected_revenue: Decimal
    profit_p10: Decimal
    profit_p50: Decimal
    profit_p90: Decimal

    stockout_probability: float
    expected_end_inventory: int | None
    cash_required: Decimal
    stability_horizon_days: int

    failure_triggers: list[FailureTrigger]
    scenario_results: list[ScenarioResult]
    sensitivity: list[SensitivityResult]

    simulator_version: str
    parameter_version: str
    created_at: datetime
```

## 5.15 SimulatedBusinessState

模拟状态禁止复用真实 `BusinessStateSnapshot` 类型。

```python
class SimulatedBusinessState(BaseModel):
    simulation_id: str
    simulated_day: int
    source_snapshot_id: str
    expected_sales: float
    expected_inventory: float
    expected_revenue: Decimal
    expected_profit: Decimal
    confidence_interval: ConfidenceInterval | None
```

## 5.16 DecisionState

```python
class DecisionState(BaseModel):
    decision_id: str
    phase: DecisionPhase
    issue: Issue

    diagnosis_report: DiagnosisReport | None = None
    candidate_strategies: list[Strategy] = []
    simulation_reports: list[SimulationReport] = []
    rejected_strategy_ids: list[str] = []
    selected_strategy_id: str | None = None

    approval: ApprovalState | None = None
    execution: ExecutionState | None = None
    monitoring: MonitoringState | None = None

    trace_id: str
    created_at: datetime
    updated_at: datetime
```

---

# 6. Snapshot、版本与并发控制

这是业务 Agent 容易被忽略但必须实现的机制。

## 6.1 Snapshot 原则

一次诊断和多方案比较必须基于同一业务快照。

```text
Business DB
    ↓
Snapshot #184
    ├── Diagnosis
    ├── Strategy A Simulation
    ├── Strategy B Simulation
    └── Strategy C Simulation
```

## 6.2 Stale Decision 检测

Strategy 创建时：

```text
based_on_state_version = 184
```

执行前若当前：

```text
current_state_version = 193
```

系统必须执行 `revalidate_strategy()`；变化超过阈值则重新诊断/模拟。

## 6.3 Data Freshness

BusinessStateSnapshot 必须记录数据最新时间。如果广告数据已 24 小时未更新、库存数据 5 分钟前更新，两者 freshness 不同，Diagnosis Report 要能表达数据时效性风险。

---

# 7. Anomaly Engine

Anomaly Engine 是确定性/统计服务，不是 LLM Agent。

## 7.1 目标

识别有业务价值的异常，而不是纯统计异常。

```text
Raw Metric
    ↓
Historical Baseline
    ↓
Trend / Peer / Expected Range
    ↓
Business Constraint
    ↓
Forecast Risk
    ↓
Impact Estimation
    ↓
Issue
```

## 7.2 Issue Priority

概念上：

```text
Priority = Anomaly Severity × Business Impact × Urgency × Confidence
```

具体公式配置化，不写死在 Agent Prompt。

## 7.3 v1 四类 Issue

### Profit Erosion

重点证据：利润率偏离、GMV/利润剪刀差、成本分解、退款/广告贡献。

### Ad Inefficiency

重点证据：ROAS/ACOS 相对基线、广告支出变化与订单/收入变化不匹配、campaign mix。

### Stockout Risk

重点证据：days of cover、lead time、未来需求、incoming inventory。

### Excess Inventory

重点证据：days of cover、销量趋势、库存资金占用、转化与价格。

---

# 8. Diagnosis Agent 规格

## 8.1 角色

**经营调查员**。只负责“发生了什么、为什么、证据是什么、哪里还不确定”，不负责最终选择策略。

## 8.2 模式

采用 **Business-Causal-Graph-Guided ReAct**：

```text
Issue
  ↓
Observe Current Evidence
  ↓
Generate / Update Hypotheses
  ↓
Choose Next Investigation Tool
  ↓
Tool Result -> Evidence
  ↓
Update Hypotheses
  ↓
Enough Evidence?
  ├── No -> Continue
  └── Yes -> DiagnosisReport
```

## 8.3 Business Causal Graph（v1）

```text
Profit
│
├── Revenue
│   ├── Traffic
│   │   ├── Organic
│   │   └── Paid
│   ├── Conversion
│   │   ├── Price
│   │   ├── Listing
│   │   ├── Reviews
│   │   └── Promotion
│   └── Availability
│       └── Inventory
│
├── Product Cost
├── Ad Cost
│   ├── CPC
│   ├── CTR
│   ├── CVR
│   └── Campaign Mix
├── Refund
│   ├── Quality
│   ├── Size
│   ├── Description
│   ├── Logistics
│   └── Service
└── Promotion Cost
```

图的作用不是硬编码唯一诊断路径，而是：

- 帮助选择候选假设；
- 限制无关工具调用；
- 给 Context Builder 暴露更相关的工具；
- 形成可解释诊断路径。

## 8.4 Diagnosis Tools

v1 推荐：

```text
get_issue_context(issue_id)
get_sku_summary(sku_id)
get_metric_trend(entity, metric, window)
decompose_profit(sku_id, period_a, period_b)
get_conversion_funnel(sku_id)
get_campaign_breakdown(sku_id)
get_campaign_trend(campaign_id)
get_inventory_projection(sku_id)
get_refund_breakdown(sku_id)
analyze_reviews(sku_id, window)
compare_peer_skus(sku_id, metrics)
get_price_history(sku_id)
get_promotion_history(sku_id)
```

每个 Tool 必须返回结构化结果，并同时生成/引用 Evidence。

## 8.5 Stop Conditions

Diagnosis Agent 不能无限 ReAct。默认：

- max tool calls：8；
- max reasoning rounds：6；
- 无新信息连续 2 轮：停止；
- 根因信心达到阈值且主要负向贡献已覆盖：允许停止；
- 数据不足：输出 `INSUFFICIENT_EVIDENCE`，禁止幻觉补齐。

## 8.6 Diagnosis 输出要求

必须包含：

- primary / secondary root causes；
- supporting evidence；
- contradiction / uncertainty；
- remaining unknown；
- status：confirmed / partial / insufficient_evidence。

不要求强行找到唯一根因。

---

# 9. Main Decision Agent 规格

## 9.1 角色

Main Agent 是唯一面向用户的“运营经理”。它拥有最终回答权，但不拥有世界计算权。

核心职责：

1. 选择要处理的 Issue；
2. 调用 Diagnosis Agent；
3. 基于 DiagnosisReport 生成 2-4 个策略；
4. 决定哪些策略需要模拟；
5. 将策略交给 Validator；
6. 调用 Simulation Agent；
7. 比较收益、风险、稳定期、现金需求、可逆性；
8. 必要时 replan；
9. 生成最终 Decision Record；
10. 高风险动作请求 Human Approval。

## 9.2 Strategy Generation 原则

默认应包含：

- Conservative / 止损型；
- Balanced / 平衡型；
- Growth / 增长型；
- `Do Nothing` baseline 在适当情况下必须存在。

策略必须是结构化 `BusinessAction[]`，自然语言只能作为说明。

## 9.3 是否需要 Simulation 的判断

不要求所有建议都模拟。

```text
Simple + Low Impact
    -> Calculator / Rule

Multi-factor / Coupled Decision
    -> Simulator

High Uncertainty
    -> Simulator + Stress Test

High Impact / Irreversible
    -> Simulator + Human Approval
```

## 9.4 Main Agent 决策目标

比较至少包括：

- Expected Profit / Margin；
- Downside Risk；
- Stockout Probability；
- Cash Requirement；
- Stability Horizon；
- Execution Complexity；
- Reversibility；
- Dependency on uncertain assumptions。

不允许只按 expected profit 排序。

---

# 10. Strategy Validator

Validator 是确定性服务。

检查：

- Action 是否在业务允许范围；
- 预算是否足够；
- 是否超过价格变化限制；
- 库存/采购量是否合法；
- Action 之间是否冲突；
- 是否存在不允许自动执行的高风险动作；
- Snapshot 是否过期；
- 是否缺少必要参数。

输出：

```python
class StrategyValidationResult(BaseModel):
    strategy_id: str
    feasible: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    normalized_strategy: Strategy | None
```

Agent 不得绕过 Validator 直接把 Strategy 送入执行层。

---

# 11. Business Simulator / Business World

## 11.1 角色

Simulator 是一个**可计算的经营沙盘**，而不是 LLM。

建议接口：

```python
world = BusinessWorld(snapshot, parameter_set)
next_state = world.step(action)
report = world.rollout(strategy, horizon=14, scenario=scenario)
```

## 11.2 Hybrid World Model

```text
Business World
│
├── Deterministic Rules
│   ├── inventory accounting
│   ├── revenue / cost / profit
│   └── action constraints
│
├── Predictive Models
│   ├── demand forecast
│   ├── price elasticity
│   ├── ad response
│   └── refund response
│
└── Stochastic Components
    ├── demand noise
    ├── ad efficiency noise
    ├── supplier delay
    └── refund variability
```

v1 不要求训练端到端 learned world model。

## 11.3 基础状态转移

示意：

```text
PaidTraffic(t+1) = AdResponse(ad_budget_t, campaign_state_t)
Conversion(t+1) = BaseCVR × PriceEffect × ListingEffect × ReviewEffect
Demand(t+1) = Traffic(t+1) × Conversion(t+1) × stochastic_noise
Sales(t+1) = min(Demand(t+1), AvailableInventory(t))
Inventory(t+1) = Inventory(t) + Arrival(t) - Sales(t)
Profit(t+1) = Revenue - COGS - AdSpend - RefundLoss - PromotionCost - HoldingCost
```

公式中的 response function 必须由独立模型/参数集实现，禁止散落在 Agent 代码。

## 11.4 Monte Carlo Rollout

复杂策略不得只返回单点预测。

至少输出：

- Expected；
- P10 / P50 / P90；
- stockout probability；
- downside probability；
- stability horizon。

所有随机模拟必须支持固定 `random_seed`，保证测试可复现。

## 11.5 Simulation Modes

v1/v2 支持：

1. **Base Forecast**：正常未来；
2. **What-if**：不同动作参数；
3. **Stress Test**：需求突增、ROAS 下滑、补货延期等；
4. **Sensitivity Analysis**：识别结果对哪些参数最敏感。

## 11.6 Stability Horizon

定义：关键经营约束仍成立的最长预计周期。

示例约束：

```text
InventoryCoverage >= 7 days
ROAS >= 2.2
ProfitMargin >= 20%
CashBalance >= 0
```

若 Day 19 第一个违反 ROAS，则：

```text
stability_horizon_days = 18
failure_trigger = "ROAS below 2.2"
```

---

# 12. Simulation Agent 规格

## 12.1 角色

Simulation Agent 是**实验规划者**，不直接计算未来。

回答：

- 哪些 Strategy 需要先跑 Base Case？
- 哪些方案结果接近，需要额外压力测试？
- 哪个假设对推荐结果最敏感？
- 是否需要修改参数后再模拟？
- 证据是否足够区分方案？

## 12.2 Agent Loop

```text
Receive Valid Strategies
       ↓
Base Rollouts
       ↓
Compare Results
       ↓
Identify Key Uncertainty
       ↓
Choose Stress / Sensitivity Scenario
       ↓
Run Simulator
       ↓
Evidence Sufficient?
  ├── No -> More Experiments
  └── Yes -> SimulationReport Set
```

## 12.3 Strategy Envelope

Simulation Agent 只能在 Main Agent 给定的 envelope 内微调策略参数，例如：

```text
Strategy family: Growth
Ad budget change: 0% ~ +20%
Replenishment: 200 ~ 500
Price: fixed
```

禁止“评估 Plan C 时改成完全不同的 Plan D”。

## 12.4 Budget

默认：

- max strategy families：4；
- max refinement rounds：3；
- max stress scenarios：4；
- max total simulator jobs：20（可配置）；
- 发现结果对模拟器边界高度敏感时，必须返回 `UNCERTAIN` 而非继续无限搜索。

---

# 13. Context Builder

Agent 不应直接访问整库，也不应把所有历史数据灌给模型。

每个 Agent 前必须有 `ContextBuilder`：

```text
Structured State
 + Relevant Evidence
 + Relevant Historical Decision Cases
 + Allowed Tools
 + Business Policy
 -> Bounded Agent Context
```

## 13.1 Diagnosis Context

包含：

- current Issue；
- relevant MetricState；
- current hypotheses；
- causal graph neighborhood；
- evidence summary；
- unresolved questions；
- available tools。

不默认包含完整评论和全量 campaign history。

## 13.2 Main Agent Context

包含：

- Issue；
- DiagnosisReport；
- available action space；
- strategy validation warnings；
- SimulationReports；
- high-level historical similar cases。

## 13.3 Simulation Agent Context

包含：

- Strategy set；
- baseline snapshot summary；
- simulator capabilities；
- uncertainty / assumptions；
- existing simulation results。

---

# 14. Agent 输出与 Prompt 管理

## 14.1 Structured Output First

所有关键 Agent 调用必须使用 Pydantic/JSON Schema structured output。

自然语言回复从结构化对象二次渲染，不反过来从自然语言解析核心状态。

## 14.2 Prompt Registry

Prompt 不散落在代码里：

```text
prompts/
  diagnosis/
    system_v1.md
  main_decision/
    system_v1.md
  simulation/
    system_v1.md
```

每次 Agent Run 记录：

- prompt_version；
- model_provider；
- model_name；
- model_parameters；
- tool_registry_version。

## 14.3 Model Adapter

Agent 层通过统一 `LLMClient` / provider adapter 调用模型，避免业务代码绑定某一厂商。

---

# 15. Decision Documents、Artifact 与 Provenance

## 15.1 一次决策的文档工作区

```text
DEC_20260903_001/
├── 01_issue_brief.md
├── 02_diagnosis_report.md
├── 03_strategy_proposals.md
├── 04_simulation_report.md
├── 05_decision_record.md
├── 06_execution_record.md
└── 07_outcome_review.md
```

## 15.2 DecisionArtifact

```python
class DecisionArtifact(BaseModel):
    artifact_id: str
    artifact_type: str
    decision_id: str
    issue_id: str | None
    version: int
    status: str

    created_at: datetime
    created_by: str
    model_version: str | None

    source_snapshot_ids: list[str]
    evidence_ids: list[str]
    related_artifact_ids: list[str]
    document_uri: str
```

## 15.3 Front Matter

每份 Markdown 文档头部：

```yaml
---
document_type: diagnosis_report
decision_id: DEC_018
issue_id: ISSUE_018
business_snapshot: SNAPSHOT_184
generated_at: 2026-09-03T10:32:00
agent: diagnosis-agent
agent_version: v0.3
model: model-x
evidence:
  - E101
  - E108
status: final
---
```

## 15.4 Provenance Graph

```text
Business Snapshot #184
       ↓
Evidence E101 / E108
       ↓
Diagnosis Report #18
       ↓
Strategy B #24
       ↓
Simulation Run #27
       ↓
Decision Record #18
       ↓
Execution #18
       ↓
Outcome Review #18
```

最终 UI 中一条建议应能追溯到：

- 原始/派生证据；
- 使用哪个 Snapshot；
- Diagnosis 版本；
- Simulator 版本与假设；
- 为什么拒绝其他方案。

---

# 16. 持久化设计

## 16.1 PostgreSQL（结构化 Source of Truth）

推荐表：

```text
stores
products
sku_daily_metrics
campaign_daily_metrics
inventory_daily
reviews

business_snapshots
metric_states
evidence
issues

diagnosis_runs
diagnosis_reports
strategies
simulation_jobs
simulation_reports

decisions
approvals
executions
monitoring_results
artifacts
agent_runs
tool_calls
```

## 16.2 Document Store

v1 可直接将 Markdown/JSON Artifact 存文件系统或对象存储；数据库仅存 URI、hash、版本、metadata。

## 16.3 Vector / Retrieval Store

不是 v1 强依赖。后续仅用于：

- 相似历史 Decision Case 检索；
- Decision Record / Outcome Review 语义检索；
- SOP / 运营规则 Knowledge Memory。

不得将当前业务事实只存向量库。

---

# 17. Event 模型与异步任务

## 17.1 核心事件

```text
DATA_REFRESHED
ISSUE_DETECTED
DIAGNOSIS_STARTED
DIAGNOSIS_COMPLETED
STRATEGIES_GENERATED
STRATEGY_VALIDATED
SIMULATION_SUBMITTED
SIMULATION_COMPLETED
DECISION_READY
APPROVAL_GRANTED
ACTION_EXECUTED
MONITORING_UPDATED
STRATEGY_INVALIDATED
OUTCOME_REVIEWED
```

## 17.2 Simulation Job

Simulation 可能是异步的：

```python
class SimulationJob(BaseModel):
    job_id: str
    simulation_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
```

Main Graph 可在 `SIMULATING` 状态等待 job 完成后恢复。

## 17.3 幂等

所有可能改变外部世界的操作必须携带 `idempotency_key`。

例如：

```text
create_replenishment_order(
    sku_id="SKU_A",
    quantity=200,
    idempotency_key="DEC18-ACT02"
)
```

避免 Agent retry 导致重复采购/重复调价。

---

# 18. Human-in-the-loop 与执行权限

建议按风险划分：

- **L0 - 读取指标、诊断**：自动执行。
- **L1 - 生成建议、模拟**：自动执行。
- **L2 - 小额、可逆广告调整**：允许按配置自动执行。
- **L3 - 调价、明显预算变化**：必须人工审批。
- **L4 - 补货采购、大额现金动作**：必须人工审批，并保留完整审计记录。

执行前必须：

1. 检查 Strategy 仍基于有效 Snapshot；
2. 重新运行关键业务约束；
3. 检查 approval；
4. 写入 execution record；
5. 使用 idempotency key。

---

# 19. Monitoring、Outcome Review 与 Simulator Calibration

执行后不得结束。

```text
Decision
  ↓
Execution
  ↓
Day 1 / 3 / 7 / 14 Monitor
  ↓
Expected vs Actual
  ↓
Deviation within tolerance?
  ├── Yes -> Continue / Resolve
  └── No  -> Invalidate Strategy / Re-diagnose
```

## 19.1 Expected-vs-Actual

保存：

- 预测利润 vs 实际利润；
- 预测退款率 vs 实际；
- 预测库存 vs 实际；
- 预测 ROAS vs 实际。

## 19.2 Calibration

若长期发现某类模型偏差，例如价格弹性总被高估，应生成 calibration candidate，而不是让 Agent 直接在线修改生产模型参数。

推荐流程：

```text
Outcome Reviews
      ↓
Calibration Dataset
      ↓
Offline Refit / Recalibration
      ↓
Validation
      ↓
New parameter_version
```

---

# 20. Memory 设计

## 20.1 Operational Memory

当前 DecisionState、当前 Issue、当前工具结果。生命周期短。

## 20.2 Decision Memory

历史：

- Diagnosis；
- Strategy；
- Simulation；
- Decision；
- Actual Outcome。

这是 Agent 后续“参考过去类似经营案例”的核心。

## 20.3 Knowledge Memory

相对稳定的：

- 指标定义；
- 运营 SOP；
- 业务规则；
- Action policy；
- 平台约束。

三种 Memory 不混用。

---

# 21. API 设计（v1）

## 21.1 Business

```text
GET  /api/v1/store/health
GET  /api/v1/skus/{sku_id}/health
GET  /api/v1/issues
GET  /api/v1/issues/{issue_id}
```

## 21.2 Decision

```text
POST /api/v1/decisions
GET  /api/v1/decisions/{decision_id}
POST /api/v1/decisions/{decision_id}/diagnose
POST /api/v1/decisions/{decision_id}/strategies
POST /api/v1/decisions/{decision_id}/simulate
POST /api/v1/decisions/{decision_id}/approve
POST /api/v1/decisions/{decision_id}/execute
```

## 21.3 Simulation

```text
POST /api/v1/simulations
GET  /api/v1/simulations/{simulation_id}
GET  /api/v1/simulation-jobs/{job_id}
```

## 21.4 Artifacts / Trace

```text
GET /api/v1/decisions/{decision_id}/artifacts
GET /api/v1/artifacts/{artifact_id}
GET /api/v1/decisions/{decision_id}/trace
```

---

# 22. Failure Handling

必须显式处理以下失败：

## 22.1 Tool Failure

- timeout；
- 数据源暂不可用；
- schema mismatch；
- 空结果。

Agent收到结构化错误，不把 traceback 原样塞给模型。

## 22.2 Diagnosis Failure

- tool budget exhausted；
- insufficient evidence；
- contradictory evidence。

输出 partial/insufficient，而不是伪造答案。

## 22.3 Simulation Failure

- model unavailable；
- non-convergent / invalid parameters；
- no feasible rollout；
- job timeout。

Strategy 不得因此被自动标成失败业务方案，只标记“无法可靠评估”。

## 22.4 Execution Failure

执行层必须支持：

- idempotent retry；
- partial action status；
- compensating action（仅可逆动作）；
- escalation。

---

# 23. Observability 与 Trace

每次 Decision 统一 `trace_id`。

需要记录：

```text
Decision #102
├── Main Agent Run #1
├── Diagnosis Agent
│   ├── tool call 1
│   ├── tool call 2
│   └── diagnosis report
├── Strategy Generation
├── Simulation Agent
│   ├── simulation job 1
│   ├── stress job 2
│   └── simulation report
└── Final Decision
```

AgentRun 建议字段：

- agent_name/version；
- model/provider；
- prompt_version；
- input tokens / output tokens；
- latency；
- tool calls；
- retry count；
- final structured output hash；
- success/failure。

---

# 24. Evaluation 与 Benchmark

项目必须从一开始建立 Scenario Dataset。

## 24.1 场景库

至少包含：

```text
S01 高 ROAS + 快断货
S02 低 ROAS + 高库存
S03 GMV 增长 + 利润下降
S04 库存积压 + 低转化
S05 供应延迟 + 正在放量
S06 退款突然增加
S07 有限现金 + 多 SKU 补货冲突
S08 多 Campaign 中单一 Campaign 失效
```

每个 Scenario 保存：

- initial snapshot；
- hidden ground truth root cause；
- allowed actions；
- hard constraints；
- baseline strategy；
- expected evaluation targets。

## 24.2 Diagnosis Eval

- Root Cause Accuracy；
- Evidence Grounding Accuracy；
- Tool Efficiency；
- Irrelevant Tool Rate；
- Hallucination Rate；
- Correct Escalation Rate。

## 24.3 Strategy Eval

- Feasibility Rate；
- Constraint Violation Rate；
- Strategy Diversity；
- Business Utility；
- Reversibility / Risk awareness。

## 24.4 Simulator Eval

- Forecast MAE / MAPE（适用时）；
- probabilistic calibration；
- stockout probability calibration；
- stability horizon error；
- scenario sensitivity correctness。

## 24.5 End-to-End Eval

比较 Baseline：

1. Fixed Rule；
2. LLM-only Recommendation；
3. Main Agent + Tools；
4. Agent + Diagnosis + Simulator（完整系统）。

指标：

- business reward；
- profit improvement；
- stockout reduction；
- inventory/cash efficiency；
- decision success rate；
- tokens / cost / latency；
- number of tool/simulation calls。

---

# 25. 测试策略

## 25.1 Unit Test

优先覆盖：

- 利润公式；
- MetricState；
- anomaly rules；
- inventory transitions；
- strategy validation；
- stability horizon；
- Pydantic validation。

## 25.2 Contract Test

每个 Tool / Service 的输入输出 Schema 必须 contract-test。

## 25.3 Scenario Test

给固定 Snapshot + fixed random seed，确保 Simulator 输出在容忍范围。

## 25.4 Agent Regression

保存典型 Agent 任务，并验证：

- 必须/禁止调用哪些工具；
- Diagnosis 输出包含必要 evidence；
- 不出现不存在的业务字段；
- 遇到缺数据会 escalate。

## 25.5 Temporal Leakage Test

训练/校准预测模型与 Eval 必须防止未来数据泄漏。任何历史 Scenario 只能使用当时可见数据构造 Snapshot。

---

# 26. 数据质量

Agent 决策前必须知道数据是否可靠。

```python
class DataQualityReport(BaseModel):
    completeness_score: float
    freshness_score: float
    consistency_score: float
    missing_sources: list[str]
    warnings: list[str]
```

例如：

- 广告数据缺失 -> 不应高信心诊断广告；
- 库存过期 2 天 -> 禁止自动补货；
- 评论样本太少 -> 退款根因降置信度。

---

# 27. 安全、权限与业务治理

v1 即便只做 demo，也应保留以下抽象：

- Tool Permission；
- Read vs Write Tool 分离；
- action risk level；
- user role；
- audit log；
- monetary action threshold；
- PII 最小化。

LLM 不直接持有数据库写权限；所有写动作通过受控 Tool/Service。

---

# 28. 推荐代码目录

```text
ecommerce-decision-agent/
│
├── app/
│   ├── api/
│   ├── config/
│   └── dependencies/
│
├── domain/
│   ├── business/
│   │   ├── store.py
│   │   ├── sku.py
│   │   ├── campaign.py
│   │   ├── inventory.py
│   │   └── metrics.py
│   ├── issue/
│   │   ├── models.py
│   │   ├── evidence.py
│   │   └── enums.py
│   ├── diagnosis/
│   │   ├── state.py
│   │   ├── hypothesis.py
│   │   └── report.py
│   ├── strategy/
│   │   ├── models.py
│   │   ├── actions.py
│   │   └── validation.py
│   ├── simulation/
│   │   ├── models.py
│   │   ├── scenario.py
│   │   └── report.py
│   └── decision/
│       ├── state.py
│       ├── approval.py
│       └── monitoring.py
│
├── agents/
│   ├── main/
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   └── context.py
│   ├── diagnosis/
│   │   ├── graph.py
│   │   ├── causal_graph.py
│   │   ├── context.py
│   │   └── agent.py
│   └── simulation/
│       ├── graph.py
│       ├── context.py
│       └── agent.py
│
├── tools/
│   ├── business/
│   ├── diagnosis/
│   ├── simulation/
│   └── execution/
│
├── services/
│   ├── metrics/
│   ├── anomaly/
│   ├── profit/
│   ├── forecast/
│   ├── simulator/
│   ├── strategy_validator/
│   ├── monitoring/
│   └── artifact/
│
├── repositories/
│   ├── business.py
│   ├── issue.py
│   ├── decision.py
│   └── artifact.py
│
├── prompts/
│   ├── diagnosis/
│   ├── main_decision/
│   └── simulation/
│
├── workers/
│   └── simulation_worker.py
│
├── evals/
│   ├── scenarios/
│   ├── diagnosis/
│   ├── strategy/
│   ├── simulation/
│   └── e2e/
│
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── scenarios/
│   └── regression/
│
└── docs/
    ├── architecture/
    ├── decisions/
    └── schemas/
```

---

# 29. 依赖方向（非常重要）

必须保持单向依赖：

```text
API / Agents
     ↓
Application Services / Tools
     ↓
Domain
     ↓
Repositories / Infrastructure adapters
```

关键要求：

- `domain/` 不 import LangGraph；
- `services/simulator` 不 import LLM SDK；
- Agent 不直接 import SQLAlchemy model 做任意查询；
- Agent 只能通过 Tool/Service 接口获取业务能力；
- API 不直接实现利润/库存业务公式。

---

# 30. AI 编码必须遵守的规则

本节可直接提供给 Coding Agent 作为仓库级约束。

## 30.1 MUST

1. 所有公共输入输出使用 Pydantic v2 model。
2. 使用完整类型标注；关键函数禁止 `dict[str, Any]` 作为长期接口。
3. 所有 monetary value 优先使用 `Decimal`，避免浮点金额误差。
4. 所有业务时间使用 timezone-aware datetime。
5. 所有模拟随机过程可注入 random seed。
6. 所有 Agent 核心输出必须 structured output validation。
7. 所有 Tool result 必须可生成 Evidence 或明确声明不是 evidence-producing tool。
8. 所有写动作必须有 idempotency key。
9. 所有 Strategy 在 Simulation/Execution 前必须经过 Validator。
10. 所有执行前检查 Snapshot/version freshness。
11. 每个 Agent Run 必须有 trace_id、agent_version、prompt_version、model_version。
12. 新增 Domain Model 时必须补单元测试。
13. 新增 Tool 时必须补 contract test。
14. 新增 Simulator transition 时必须补 deterministic seed scenario test。

## 30.2 MUST NOT

1. 不允许在 Prompt 中硬编码核心业务公式作为唯一计算逻辑。
2. 不允许让 LLM 自己产生利润、库存、ROAS 等计算结果并直接写入 State。
3. 不允许把 simulated state 写回 observed business state。
4. 不允许从自由文本重新解析已经存在的结构化对象。
5. 不允许 Agent 直接执行 SQL 任意写操作。
6. 不允许 Agent 绕过 StrategyValidator。
7. 不允许 high-risk action 在无 Approval 情况下执行。
8. 不允许隐藏 Simulation Assumption。
9. 不允许在根因证据不足时强行输出 confirmed diagnosis。
10. 不允许为了“Multi-Agent”继续拆没有独立上下文/认知任务的 Agent。

## 30.3 SHOULD

- 函数优先纯函数；
- Domain 逻辑尽量 deterministic；
- Tool 小而语义明确；
- Agent context 有 token budget；
- 每轮 agentic loop 有 step/tool budget；
- Error 结构化；
- Artifact 可重新生成；
- 模型和参数版本化；
- feature flag 控制实验性 Agent 功能。

---

# 31. v1 开发顺序

## Phase 0：Domain Skeleton

实现：

- Pydantic schema；
- repository interfaces；
- config；
- test infrastructure。

验收：所有核心数据类可序列化/反序列化，类型与约束测试通过。

## Phase 1：Business Data + Metrics + Anomaly

实现：

- Olist/合成运营数据 loader；
- SKU daily metrics；
- Profit Engine；
- inventory coverage；
- 四类 Issue。

此时完全不需要 LLM。

## Phase 2：Business Tools + Evidence

实现诊断 Tool，确保所有数据调查能通过结构化接口完成。

## Phase 3：Diagnosis Agent

实现 Graph-guided ReAct，建立 Diagnosis Benchmark。

这是第一块真正 Agentic 的核心能力。

## Phase 4：Main Decision Agent + Strategy Validator

实现结构化 Strategy 生成、validation 与 no-simulation baseline。

## Phase 5：Business Simulator

先实现 deterministic + simple stochastic v1，不加入 Simulation Agent。

## Phase 6：Simulation Agent

实现 experiment planning、stress test、refinement budget。

## Phase 7：Decision Documents + Provenance

生成完整 Artifact 链与历史 Decision Memory。

## Phase 8：Execution / Monitoring

先用 mock business actions，完成 approval、idempotency、expected-vs-actual。

## Phase 9：Dashboard / Demo

展示：

- 今日 Issue；
- Diagnosis path/evidence；
- Strategy cards；
- Simulation comparison；
- trace/provenance；
- Outcome Review。

---

# 32. MVP 验收标准

一个可投简历的 MVP 至少应完成以下完整 Case：

```text
Synthetic / Historical Business Data
        ↓
Profit Erosion Issue detected
        ↓
Diagnosis Agent autonomously investigates
        ↓
DiagnosisReport with evidence
        ↓
Main Agent generates 3 valid strategies
        ↓
Simulator evaluates 7/14/30 day outcomes
        ↓
Simulation Agent adds at least one stress test
        ↓
Main Agent recommends one strategy
        ↓
Decision Record cites evidence + simulations
        ↓
Mock Human Approval
        ↓
Mock Execute
        ↓
Outcome Review compares expected vs actual
```

同时必须有：

- 至少 8 个 Scenario Eval；
- Fixed Rule baseline；
- LLM-only baseline；
- Agent + Simulation 完整结果；
- Tool/Token/Latency 指标；
- 一次 failure/insufficient evidence 案例。

---

# 33. 推荐的数据方案

## 33.1 主体真实数据

建议以 Olist 等真实电商订单数据构造：

- orders；
- products；
- seller/customer；
- price；
- review；
- delivery。

## 33.2 Synthetic Operational Layer

需要明确标记为 synthetic：

- product cost；
- inventory；
- lead time；
- ad spend；
- traffic；
- cash / budget。

Synthetic 字段不是随便随机：应根据历史销售、商品类别与 Scenario 目标生成，保证业务关系一致。

## 33.3 Simulator Calibration

后续可利用其他公开行为/预测数据集帮助校准：

- 流量到购买的转化规律；
- 广告点击到转化；
- 价格/节日对需求的影响。

不同来源的数据用于“校准规律/benchmark”，不伪装成同一家真实商店并强行 join。

---

# 34. 完整 Case 示例

## 34.1 初始 Issue

```text
SKU_A Profit Margin:
30d baseline = 31%
current 7d = 23%

GMV = +11%
Ad Spend = +52%
Refund Rate = 7% -> 13%
```

Anomaly Engine：

```text
Issue: PROFIT_EROSION
Impact: -18,200 / 14d
Severity: HIGH
```

## 34.2 Diagnosis Agent

调用：

```text
decompose_profit
 -> ads + refunds are main negative contributors

get_campaign_breakdown
 -> Campaign B caused 74% incremental spend

get_refund_breakdown
 -> size/description refunds increased

analyze_reviews
 -> recurring size mismatch complaints
```

输出：

```text
Root Cause 1: ad efficiency deterioration
confidence: 0.91

Root Cause 2: size-related refunds
confidence: 0.84
```

## 34.3 Main Agent Strategies

```text
A Conservative:
Campaign B budget -30%

B Balanced:
Campaign B budget -10%
Update size listing

C Growth:
Keep spend
Reallocate campaign mix
Update listing
```

## 34.4 Simulator

```text
             A          B          C
14d Profit   +8%        +16%       +18%
Worst Case   +3%        +6%        -5%
Stability    25d        18d         8d
Risk         Low        Low/Med     High
```

Simulation Agent 对 C 执行 `ROAS -20%` stress test，发现收益接近 0；对 B 执行 listing-effect sensitivity，最坏仍正收益。

## 34.5 Final Decision

推荐 B，理由：

- expected profit 高；
- downside 仍正；
- 可逆性高；
- 现金要求低；
- 稳定窗口足够；
- 对不确定参数不如 C 敏感。

最终 Decision Record 必须链接：Snapshot、Evidence、DiagnosisReport、Strategy、SimulationRun。

---

# 35. 仍需后续评审的问题

以下内容暂不应该让 Coding Agent自行决定，应由项目负责人后续确认：

1. v1 是否支持真实写操作，还是全部 mock execution；
2. profit 的最终业务口径，是否计入平台费、物流费、仓储费；
3. Scenario 中商品成本与广告 response 的 synthetic 生成规则；
4. Diagnosis confidence 的计算/更新方式；
5. Strategy 的参数边界；
6. Simulator v1 采用哪些预测模型；
7. Simulation Agent 是否允许自动 parameter search；
8. 何种金额阈值进入人工审批；
9. LangGraph checkpointer / background job 的最终选型；
10. UI 是否优先展示“今日三件事”还是对话入口。

这些应以 ADR/Decision Record 形式逐项确定。

---

# 36. 给后续 Coding AI 的启动提示模板

下面的文字可以作为每次让 Coding Agent 开始实现前的基础上下文，而不是让其重新设计架构。

> 你正在实现一个 E-commerce Operations Decision Agent。请严格遵守仓库中的 Technical Spec。该系统使用结构化 Domain Model 控制状态，Main Decision Agent、Diagnosis Agent、Simulation Agent 三者职责分离。Diagnosis 使用受约束的 Graph-guided ReAct 调业务 Tool 收集 Evidence；Main Agent 生成结构化 Strategy；Strategy 必须通过 deterministic Validator；Simulation Agent 只规划实验，Business Simulator 才负责数值世界演化。Observed/Derived/Agent-Inferred/Simulated 数据必须类型隔离。所有关键输出使用 Pydantic v2 Schema，所有金额使用 Decimal，所有写操作使用 idempotency key。禁止把业务公式写进 Prompt 作为计算实现，禁止让 LLM 产生业务数值后直接写入 State，禁止模拟状态污染真实业务状态。实现新模块时必须同步创建 unit/contract/scenario tests，并保持 domain 层不依赖 LangGraph/LLM SDK。

针对具体任务，再附：

- 要修改的模块；
- 目标 Schema；
- 输入/输出；
- acceptance criteria；
- 需要补的测试。

---

# 37. 最终推荐

目前架构已经足以进入实现阶段。此时最重要的不是继续增加 Agent 或功能，而是**冻结 v1 Domain Contract**：

1. 先实现核心 Pydantic Model；
2. 确定 Snapshot / Evidence / Provenance；
3. 实现纯业务 Service；
4. 再实现 Diagnosis Agent；
5. 最后叠加 Main Agent、Simulator 和 Simulation Agent。

只要严格保持“**事实可计算、推断有证据、模拟有假设、决策可追溯、执行有边界**”，这个项目就不会退化成一个套了 LangGraph 的电商聊天机器人。

