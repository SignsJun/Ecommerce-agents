import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Ctx } from "../App";
import { getDecision } from "../api";
import { ScenarioCompare, StrategyCompare } from "../charts/Charts";
import type { ScenarioMatrix, StrategyBar } from "../charts/Charts";
import { Card, CardHead, Empty, ErrorBox, Loading } from "../components/ui";
import { money, num, ratio } from "../fmt";
import { actionDetail, t } from "../i18n";
import type { Candidate, DecisionDetail } from "../types";

function strategyLabel(candidate: Candidate) {
  const actions = candidate.strategy.actions.map((a) => t.action(a.action_type));
  return actions.length ? actions.join(" + ") : "维持现状";
}

function baseSim(candidate: Candidate) {
  return (
    candidate.simulations.find((s) => (s.scenario_results[0]?.scenario_id ?? "base") === "base") ??
    candidate.simulations[0]
  );
}

const TAG = {
  recommended: { text: "推荐", cls: "bg-brand-50 text-brand-700" },
  rejected: { text: "已淘汰", cls: "bg-fall-soft text-fall" },
  candidate: { text: "候选", cls: "bg-canvas text-ink-500" },
};

export function DecisionPage({ ctx }: { ctx: Ctx }) {
  const { issueId } = useParams();
  const runId = ctx.run?.run_id;
  const [data, setData] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !issueId) return;
    setData(null);
    setError(null);
    getDecision(runId, issueId)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [runId, issueId]);

  const bars = useMemo<StrategyBar[]>(() => {
    if (!data) return [];
    return data.candidates
      .map((c) => {
        const sim = baseSim(c);
        return {
          name: strategyLabel(c),
          expected: Number(sim?.expected_profit ?? 0),
          p10: Number(sim?.profit_p10 ?? 0),
          recommended: c.recommended,
        };
      })
      .sort((a, b) => a.expected - b.expected);
  }, [data]);

  const matrix = useMemo<ScenarioMatrix>(() => {
    if (!data) return { scenarios: [], series: [] };
    const scenarios: string[] = [];
    data.candidates.forEach((c) =>
      c.simulations.forEach((s) => {
        const id = s.scenario_results[0]?.scenario_id ?? "base";
        if (!scenarios.includes(id)) scenarios.push(id);
      }),
    );
    scenarios.sort((a, b) => (a === "base" ? -1 : b === "base" ? 1 : a.localeCompare(b)));
    const series = data.candidates.map((c) => ({
      name: strategyLabel(c),
      recommended: c.recommended,
      values: scenarios.map((id) => {
        const hit = c.simulations.find((s) => (s.scenario_results[0]?.scenario_id ?? "base") === id);
        return hit ? Number(hit.expected_profit) : null;
      }),
    }));
    return { scenarios, series };
  }, [data]);

  if (error) return <ErrorBox text={error} />;
  if (!data) return <Loading text="正在加载策略方案" />;

  const ordered = [...data.candidates].sort(
    (a, b) => Number(b.recommended) - Number(a.recommended) || Number(a.rejected) - Number(b.rejected),
  );
  const multiScenario = matrix.scenarios.length > 1;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <nav className="mb-2 flex items-center gap-2 text-sm text-ink-500">
            <Link to={`/issues/${data.issue_id}`} className="hover:text-brand-700">
              {t.issueType(data.issue_type)}
            </Link>
            <span>/</span>
            <span>策略对比</span>
          </nav>
          <h1 className="text-2xl font-semibold tracking-tight">策略对比</h1>
          <p className="mt-1.5 text-sm text-ink-500">
            共 {data.candidates.length} 个候选方案，最终保留 {data.recommendations.length} 条推荐 · 实验结论{" "}
            {t.experiment(data.experiment_status)}
          </p>
        </div>
        <Link to={`/issues/${data.issue_id}/trace`} className="btn-primary">
          查看决策链路 →
        </Link>
      </div>

      <Card>
        <CardHead title="推荐方案" desc="按稳健性与利润排序，不同类型对应不同经营偏好" />
        {data.recommendations.length === 0 ? (
          <Empty text="没有产生推荐方案" />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.recommendations.map((rec) => {
              const candidate = data.candidates.find((c) => c.strategy.strategy_id === rec.strategy_id);
              return (
                <article key={rec.strategy_id} className="rounded-2xl border border-brand-100 bg-brand-50/50 p-5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="chip bg-brand-600 text-white">第 {rec.rank} 推荐</span>
                    <span className="chip bg-surface text-brand-700">{t.recType(rec.recommendation_type)}</span>
                  </div>
                  <h3 className="mt-3 text-base font-semibold">
                    {candidate ? strategyLabel(candidate) : rec.strategy_id}
                  </h3>
                  <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <dt className="text-xs text-ink-500">期望利润</dt>
                      <dd className="num mt-0.5 font-semibold">{money(rec.expected_profit)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-500">悲观 P10</dt>
                      <dd className="num mt-0.5 font-semibold">{money(rec.profit_p10)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-500">较不作为</dt>
                      <dd className="num mt-0.5 font-semibold">{money(rec.vs_baseline)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-500">结论置信度</dt>
                      <dd className="mt-0.5 font-semibold">{t.confidence(rec.confidence)}</dd>
                    </div>
                  </dl>
                  <div className="mt-4 flex flex-wrap gap-1.5">
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
                  {rec.suitable_when.length > 0 && (
                    <p className="mt-3 text-xs text-ink-500">
                      适用：{rec.suitable_when.map((s) => t.label(s)).join("、")}
                    </p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </Card>

      <div className={`grid gap-6 ${multiScenario ? "xl:grid-cols-2" : ""}`}>
        <Card>
          <CardHead title="基准情景利润对比" desc="深色为推荐方案，浅色为其余候选" />
          {bars.length ? <StrategyCompare rows={bars} /> : <Empty text="暂无仿真结果" />}
        </Card>
        {multiScenario && (
          <Card>
            <CardHead title="压力情景对比" desc="同一方案在不同外部冲击下的期望利润" />
            <ScenarioCompare data={matrix} />
          </Card>
        )}
      </div>

      <Card>
        <CardHead
          title="全部候选方案"
          desc="保留被淘汰的方案，便于复盘决策过程"
          extra={
            <span className="text-xs text-ink-400">
              推荐 {data.candidates.filter((c) => c.recommended).length} · 淘汰{" "}
              {data.candidates.filter((c) => c.rejected).length}
            </span>
          }
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {ordered.map((candidate) => {
            const sim = baseSim(candidate);
            const tag = candidate.recommended ? TAG.recommended : candidate.rejected ? TAG.rejected : TAG.candidate;
            return (
              <article
                key={candidate.strategy.strategy_id}
                className={`rounded-2xl border p-5 transition ${
                  candidate.recommended ? "border-brand-200 bg-surface" : "border-hairline bg-surface"
                } ${candidate.rejected ? "opacity-70" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`chip ${tag.cls}`}>{tag.text}</span>
                  <span className="text-xs text-ink-400">{t.strategyType(candidate.strategy.strategy_type)}</span>
                </div>
                <h3 className="mt-3 font-semibold">{strategyLabel(candidate)}</h3>
                <p className="mt-1 text-sm text-ink-500">
                  {candidate.strategy.actions.length
                    ? candidate.strategy.actions.map(actionDetail).join("，")
                    : "不做任何动作，作为对照基准"}
                </p>
                {sim && (
                  <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-hairline pt-4 text-sm">
                    <div>
                      <dt className="text-xs text-ink-500">期望利润</dt>
                      <dd className="num mt-0.5 font-medium">{money(sim.expected_profit)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-500">悲观 P10</dt>
                      <dd className="num mt-0.5 font-medium">{money(sim.profit_p10)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-500">较不作为</dt>
                      <dd className="num mt-0.5 font-medium">
                        {money(Number(sim.expected_profit) - Number(sim.baseline_profit))}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-ink-500">断货概率</dt>
                      <dd className="num mt-0.5 font-medium">{ratio(sim.stockout_probability)}</dd>
                    </div>
                  </dl>
                )}
                {candidate.recommendation && (
                  <p className="mt-3 text-xs text-ink-400">
                    仿真覆盖 {candidate.recommendation.simulation_support.map((s) => t.scenario(s)).join("、") || "仅基准"}
                  </p>
                )}
                {!sim && <p className="mt-4 text-sm text-ink-400">未参与仿真（校验未通过）</p>}
                {candidate.simulations.length > 1 && (
                  <p className="num mt-2 text-xs text-ink-400">
                    共 {candidate.simulations.length} 次仿真 · 最差{" "}
                    {money(Math.min(...candidate.simulations.map((s) => Number(s.expected_profit))))}
                  </p>
                )}
                {candidate.recommendation && (
                  <p className="num mt-2 text-xs text-ink-400">排名 {num(candidate.recommendation.rank, 0)}</p>
                )}
              </article>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
