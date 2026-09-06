import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Ctx } from "../App";
import { getDecision, getTrace } from "../api";
import { ProvenanceGraph } from "../charts/Charts";
import { Card, CardHead, Empty, ErrorBox, Loading } from "../components/ui";
import { money, ratio } from "../fmt";
import { t } from "../i18n";
import type { Candidate, DecisionDetail, TraceDetail } from "../types";

const FLOW = ["snapshot", "evidence", "diagnosis", "strategy", "simulation", "recommendation"];

function strategyLabel(candidate?: Candidate) {
  if (!candidate) return null;
  const actions = candidate.strategy.actions.map((a) => t.action(a.action_type));
  return actions.length ? actions.join(" + ") : "维持现状";
}

export function TracePage({ ctx }: { ctx: Ctx }) {
  const { issueId } = useParams();
  const runId = ctx.run?.run_id;
  const [trace, setTrace] = useState<TraceDetail | null>(null);
  const [decision, setDecision] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !issueId) return;
    setTrace(null);
    setDecision(null);
    setError(null);
    setPicked(null);
    getDecision(runId, issueId)
      .then((d) => {
        setDecision(d);
        return getTrace(d.decision_id);
      })
      .then(setTrace)
      .catch((e) => setError(String(e)));
  }, [runId, issueId]);

  const stages = useMemo(() => {
    if (!trace) return [];
    return FLOW.map((stage) => trace.stages.find((s) => s.stage === stage)).filter(
      (s): s is NonNullable<typeof s> => Boolean(s),
    );
  }, [trace]);

  if (error) return <ErrorBox text={error} />;
  if (!trace || !decision) return <Loading text="正在加载决策链路" />;

  const pickedNode = picked ? trace.graph.nodes.find((n) => n.node_id === picked) : null;
  const shown = picked && trace.explains[picked] ? decision.recommendations.filter((r) => r.strategy_id === picked) : decision.recommendations;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <nav className="mb-2 flex items-center gap-2 text-sm text-ink-500">
            <Link to={`/issues/${trace.issue_id}/decision`} className="hover:text-brand-700">
              策略对比
            </Link>
            <span>/</span>
            <span>决策链路</span>
          </nav>
          <h1 className="text-2xl font-semibold tracking-tight">决策链路</h1>
          <p className="num mt-1.5 text-sm text-ink-500">
            决策编号 {trace.decision_id} · 共 {trace.graph.nodes.length} 个节点、{trace.graph.edges.length} 条关系
          </p>
        </div>
        <Link to={`/issues/${trace.issue_id}`} className="btn-ghost">
          ← 回到问题详情
        </Link>
      </div>

      <ol className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {stages.map((stage, index) => (
          <li key={stage.stage} className="card flex items-center gap-3 p-4">
            <span className="num grid size-8 shrink-0 place-items-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700">
              {index + 1}
            </span>
            <div className="leading-tight">
              <p className="text-sm font-medium">{t.nodeType(stage.stage)}</p>
              <p className="num text-xs text-ink-400">{stage.nodes.length} 个节点</p>
            </div>
          </li>
        ))}
      </ol>

      <Card>
        <CardHead
          title="证据溯源图"
          desc="从数据快照到最终决策的完整链路，可拖拽缩放，点击推荐节点可聚焦"
          extra={
            pickedNode ? (
              <button onClick={() => setPicked(null)} className="btn-ghost py-1.5 text-xs">
                已选 {t.nodeType(pickedNode.node_type)} · 清除
              </button>
            ) : undefined
          }
        />
        {trace.graph.nodes.length ? (
          <ProvenanceGraph nodes={trace.graph.nodes} edges={trace.graph.edges} onSelect={setPicked} />
        ) : (
          <Empty text="暂无溯源图" />
        )}
        <div className="mt-4 flex flex-wrap gap-3 border-t border-hairline pt-4 text-xs text-ink-500">
          {stages.map((stage) => (
            <span key={stage.stage} className="inline-flex items-center gap-1.5">
              <span
                className="size-2.5 rounded-full"
                style={{ background: STAGE_DOT[stage.stage] ?? "#94a3b8" }}
              />
              {t.nodeType(stage.stage)}
            </span>
          ))}
        </div>
      </Card>

      <Card>
        <CardHead title="推荐方案的证据链" desc="每条推荐依据的根因、证据与仿真结果" />
        {shown.length === 0 ? (
          <Empty text="暂无推荐说明" />
        ) : (
          <div className="flex flex-col gap-4">
            {shown.map((rec) => {
              const candidate = decision.candidates.find((c) => c.strategy.strategy_id === rec.strategy_id);
              return (
                <article key={rec.strategy_id} className="rounded-2xl border border-hairline p-5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="chip bg-brand-600 text-white">第 {rec.rank} 推荐</span>
                    <span className="chip bg-brand-50 text-brand-700">{t.recType(rec.recommendation_type)}</span>
                    <h3 className="ml-1 font-semibold">{strategyLabel(candidate) ?? rec.strategy_id}</h3>
                  </div>

                  <dl className="mt-4 grid gap-3 sm:grid-cols-4">
                    <div className="rounded-xl bg-canvas p-3">
                      <dt className="text-xs text-ink-500">期望利润</dt>
                      <dd className="num mt-1 font-semibold">{money(rec.expected_profit)}</dd>
                    </div>
                    <div className="rounded-xl bg-canvas p-3">
                      <dt className="text-xs text-ink-500">悲观 P10</dt>
                      <dd className="num mt-1 font-semibold">{money(rec.profit_p10)}</dd>
                    </div>
                    <div className="rounded-xl bg-canvas p-3">
                      <dt className="text-xs text-ink-500">较不作为</dt>
                      <dd className="num mt-1 font-semibold">{money(rec.vs_baseline)}</dd>
                    </div>
                    <div className="rounded-xl bg-canvas p-3">
                      <dt className="text-xs text-ink-500">结论置信度</dt>
                      <dd className="mt-1 font-semibold">{t.confidence(rec.confidence)}</dd>
                    </div>
                  </dl>

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div>
                      <p className="text-xs font-medium text-ink-500">仿真覆盖情景</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {rec.simulation_support.length ? (
                          rec.simulation_support.map((s) => (
                            <span key={s} className="chip bg-canvas text-ink-700">
                              {t.scenario(s)}
                            </span>
                          ))
                        ) : (
                          <span className="text-sm text-ink-400">仅基准情景</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs font-medium text-ink-500">优势与风险</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {rec.strengths.map((s) => (
                          <span key={s} className="chip bg-rise-soft text-rise">
                            {t.label(s)}
                          </span>
                        ))}
                        {rec.risks.map((r) => (
                          <span key={r} className="chip bg-fall-soft text-fall">
                            {t.label(r)}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {candidate && candidate.simulations.length > 0 && (
                    <div className="mt-4 overflow-x-auto rounded-xl border border-hairline">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-hairline bg-canvas/60 text-left text-xs text-ink-500">
                            <th className="px-4 py-2.5 font-medium">情景</th>
                            <th className="px-4 py-2.5 text-right font-medium">期望利润</th>
                            <th className="px-4 py-2.5 text-right font-medium">悲观 P10</th>
                            <th className="px-4 py-2.5 text-right font-medium">较不作为</th>
                            <th className="px-4 py-2.5 text-right font-medium">断货概率</th>
                          </tr>
                        </thead>
                        <tbody>
                          {candidate.simulations.map((sim, i) => (
                            <tr key={i} className="border-b border-hairline last:border-0">
                              <td className="px-4 py-2.5">
                                {t.scenario(sim.scenario_results[0]?.scenario_id ?? "base")}
                              </td>
                              <td className="num px-4 py-2.5 text-right">{money(sim.expected_profit)}</td>
                              <td className="num px-4 py-2.5 text-right">{money(sim.profit_p10)}</td>
                              <td className="num px-4 py-2.5 text-right">
                                {money(Number(sim.expected_profit) - Number(sim.baseline_profit))}
                              </td>
                              <td className="num px-4 py-2.5 text-right">{ratio(sim.stockout_probability)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {trace.explains[rec.strategy_id] && (
                    <details className="mt-4">
                      <summary className="cursor-pointer text-xs text-ink-500 hover:text-brand-700">
                        查看原始溯源记录
                      </summary>
                      <pre className="scroll-slim mt-2 overflow-x-auto whitespace-pre-wrap rounded-xl bg-canvas px-4 py-3 text-xs leading-relaxed text-ink-700">
                        {trace.explains[rec.strategy_id]}
                      </pre>
                    </details>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

const STAGE_DOT: Record<string, string> = {
  snapshot: "#64748b",
  issue: "#d97706",
  evidence: "#0ea5e9",
  diagnosis: "#4f46e5",
  strategy: "#6366f1",
  simulation: "#16a34a",
  recommendation: "#db2777",
  decision: "#131722",
};
