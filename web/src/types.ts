export type IssueRow = {
  issue_id: string;
  issue_type: string;
  entity_id: string;
  severity: string;
  estimated_impact: string | number | null;
  status: string;
  confidence: number;
  decision_id: string | null;
  title: string;
};

export type KPI = {
  gmv: string | number;
  profit: string | number;
  roas: number | null;
  inventory_health: number;
  ad_spend: string | number;
};

export type SeriesPoint = { date: string; revenue: number; profit: number; ad_spend: number };

export type RunDetail = {
  run_id: string;
  status: string;
  source: string;
  fake_llm: boolean;
  llm: string;
  as_of: string | null;
  snapshot_id: string | null;
  error: string | null;
  store_name: string;
  kpi: KPI | null;
  kpi_delta: Record<string, number | null> | null;
  previous_run_id: string | null;
  issues: IssueRow[];
  series: SeriesPoint[];
};

export type Driver = { name: string; current: number; previous: number | null; delta: number | null };

export type EvidenceRow = {
  evidence_id: string;
  metric: string | null;
  value: string | number | boolean | null;
  description: string;
  reliability: number;
  source_type: string;
};

export type IssueDetail = {
  run_id: string;
  decision_id: string | null;
  issue: IssueRow;
  sku: Record<string, unknown> | null;
  drivers: Driver[];
  trend: { date: string; revenue: number; profit: number; ad_spend: number; units_sold: number; inventory_eod: number }[];
  diagnosis: {
    status: string;
    overall_confidence: number;
    root_causes: { cause_type: string; description: string; confidence: number }[];
    uncertainties: string[];
  } | null;
  evidence: EvidenceRow[];
};

export type Rec = {
  strategy_id: string;
  rank: number;
  recommendation_type: string;
  confidence: string;
  expected_profit: string | number;
  profit_p10: string | number;
  vs_baseline: string | number;
  strengths: string[];
  risks: string[];
  suitable_when: string[];
  simulation_support: string[];
};

export type Action = {
  action_type: string;
  change_pct?: number;
  quantity?: number;
  campaign_id?: string;
  sku_id?: string;
  target_issue?: string;
};

export type Candidate = {
  strategy: {
    strategy_id: string;
    name: string;
    strategy_type: string;
    objective: string;
    actions: Action[];
  };
  recommended: boolean;
  rejected: boolean;
  recommendation: Rec | null;
  simulations: {
    expected_profit: string | number;
    profit_p10: string | number;
    baseline_profit: string | number;
    stockout_probability: number;
    scenario_results: { scenario_id: string }[];
  }[];
};

export type DecisionDetail = {
  decision_id: string;
  issue_id: string;
  issue_type: string;
  experiment_status: string | null;
  recommendations: Rec[];
  rejected_after_eval: string[];
  candidates: Candidate[];
};

export type TraceDetail = {
  decision_id: string;
  issue_id: string;
  graph: { nodes: { node_id: string; node_type: string; label: string }[]; edges: { source_id: string; target_id: string; relation: string }[] };
  stages: { stage: string; nodes: { node_id: string; node_type: string; label: string }[] }[];
  explains: Record<string, string>;
};
