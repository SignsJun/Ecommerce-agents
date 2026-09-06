const ISSUE_TYPE: Record<string, string> = {
  profit_erosion: "利润侵蚀",
  ad_inefficiency: "广告低效",
  stockout_risk: "断货风险",
  excess_inventory: "库存积压",
};

const SEVERITY: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

const RUN_STATUS: Record<string, string> = {
  pending: "待运行",
  running: "运行中",
  done: "已完成",
  failed: "失败",
};

const REC_TYPE: Record<string, string> = {
  profit: "利润优先",
  robust: "稳健",
  balanced: "均衡",
  status_quo: "维持现状",
};

const CONFIDENCE: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

const ACTION: Record<string, string> = {
  adjust_ad_budget: "调整广告预算",
  pause_campaign: "暂停广告",
  replenish: "补货",
  adjust_price: "调整价格",
  update_listing: "优化商品页",
};

const CAUSE: Record<string, string> = {
  revenue: "收入下滑",
  cogs: "成本上升",
  ad_efficiency: "广告效率",
  refunds: "退款上升",
  price: "价格因素",
  conversion: "转化率",
  campaign_mix: "广告结构",
  inventory: "库存不足",
  excess_inventory: "库存过剩",
  demand_decline: "需求下降",
};

const SCENARIO: Record<string, string> = {
  base: "基准",
  roas_down: "ROAS 下滑",
  demand_down: "需求下滑",
  listing_worse: "商品页变差",
  supplier_delay: "供应商延迟",
  eta_ad_p20: "广告弹性 +20%",
  eta_ad_m20: "广告弹性 -20%",
};

const EXPERIMENT: Record<string, string> = {
  sufficient: "验证充分",
  budget_exhausted: "预算耗尽",
  uncertain: "结论不确定",
};

const DIAGNOSIS_STATUS: Record<string, string> = {
  confirmed: "已确认",
  partial: "部分确认",
  insufficient_evidence: "证据不足",
};

const STRATEGY_TYPE: Record<string, string> = {
  conservative: "保守型",
  balanced: "均衡型",
  growth: "进取型",
  custom: "定制型",
};

const NODE_TYPE: Record<string, string> = {
  snapshot: "数据快照",
  issue: "问题",
  evidence: "证据",
  diagnosis: "诊断",
  strategy: "策略",
  validation: "校验",
  simulation: "仿真",
  recommendation: "推荐",
  decision: "决策",
};

const LABEL: Record<string, string> = {
  vs_baseline_positive: "优于不作为",
  vs_baseline_negative: "劣于不作为",
  p10_non_negative: "悲观情形不亏损",
  p10_negative: "悲观情形亏损",
  low_stockout: "断货风险低",
  high_stockout: "断货风险高",
  no_cash_outlay: "无需现金投入",
  cash_required: "需要现金投入",
  stress_untested: "未做压力测试",
  fragile_under_stress: "压力下脆弱",
  stable_under_stress: "压力下稳定",
  prefer_profit: "追求利润时",
  prefer_stability: "追求稳健时",
  prefer_no_execution: "不想动作时",
  prefer_balance: "兼顾两者时",
};

const DRIVER: Record<string, string> = {
  revenue: "收入",
  profit: "利润",
  ad_spend: "广告花费",
  refund_loss: "退款损失",
  units_sold: "销量",
  refund_rate_7d: "7 日退款率",
  roas_7d: "7 日 ROAS",
  days_of_cover: "库存可售天数",
};

const EVIDENCE_SOURCE: Record<string, string> = {
  metric_state: "指标监测",
  diagnosis_tool: "诊断工具",
};

const METRIC: Record<string, string> = {
  profit_margin: "利润率",
  profit: "利润",
  revenue: "收入",
  roas: "广告 ROAS",
  ad_spend: "广告花费",
  refund_rate: "退款率",
  days_of_cover: "库存可售天数",
  inventory_available: "可用库存",
  units_sold: "销量",
  conversion_rate: "转化率",
};

const DESCRIPTION: Record<string, string> = {
  "7d profit margin below 30d baseline": "近 7 日利润率低于 30 日基线",
  "GMV vs profit scissors": "成交额上升但利润下降，出现剪刀差",
  "ROAS below threshold or spend/revenue mismatch": "ROAS 低于阈值，或花费与回报不匹配",
  "inventory coverage below lead time plus safety stock": "库存可售天数低于补货周期加安全库存",
  "excess inventory with declining sales": "销量下滑的同时库存明显积压",
};

function pick(map: Record<string, string>, key: string | null | undefined) {
  if (!key) return "—";
  return map[key] ?? key;
}

export const t = {
  issueType: (v?: string | null) => pick(ISSUE_TYPE, v),
  severity: (v?: string | null) => pick(SEVERITY, v),
  runStatus: (v?: string | null) => pick(RUN_STATUS, v),
  recType: (v?: string | null) => pick(REC_TYPE, v),
  confidence: (v?: string | null) => pick(CONFIDENCE, v),
  action: (v?: string | null) => pick(ACTION, v),
  cause: (v?: string | null) => pick(CAUSE, v),
  scenario: (v?: string | null) => pick(SCENARIO, v),
  experiment: (v?: string | null) => pick(EXPERIMENT, v),
  diagnosisStatus: (v?: string | null) => pick(DIAGNOSIS_STATUS, v),
  strategyType: (v?: string | null) => pick(STRATEGY_TYPE, v),
  nodeType: (v?: string | null) => pick(NODE_TYPE, v),
  label: (v?: string | null) => pick(LABEL, v),
  driver: (v?: string | null) => pick(DRIVER, v),
  evidenceSource: (v?: string | null) => pick(EVIDENCE_SOURCE, v),
  metric: (v?: string | null) => pick(METRIC, v),
  description: (v?: string | null) => pick(DESCRIPTION, v),
};

export const MONEY_DRIVERS = new Set(["revenue", "profit", "ad_spend", "refund_loss"]);

export function actionDetail(action: {
  action_type: string;
  change_pct?: number;
  quantity?: number;
}): string {
  const name = t.action(action.action_type);
  if (action.change_pct != null) {
    const pct = action.change_pct * 100;
    return `${name} ${pct > 0 ? "+" : ""}${pct.toFixed(0)}%`;
  }
  if (action.quantity != null) return `${name} ${action.quantity} 件`;
  return name;
}
