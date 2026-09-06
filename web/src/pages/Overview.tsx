import { Link } from "react-router-dom";
import type { Ctx } from "../App";
import { Sparkline, StoreTrend } from "../charts/Charts";
import { Card, CardHead, Delta, Empty, SeverityChip } from "../components/ui";
import { money, moneyCompact, num, ratio, signedPct } from "../fmt";
import { t } from "../i18n";
import { PALETTE } from "../charts/useChart";

export function OverviewPage({ ctx }: { ctx: Ctx }) {
  const run = ctx.run;

  if (!run) {
    return (
      <Card>
        <Empty text="还没有运行记录，点击左下角「运行今日分析」开始" />
      </Card>
    );
  }

  const kpi = run.kpi;
  const delta = run.kpi_delta ?? {};
  const hasPrev = Boolean(run.previous_run_id);
  const cards = [
    {
      key: "gmv",
      label: "成交额 GMV",
      value: money(kpi?.gmv),
      delta: delta.gmv,
      spark: run.series.map((s) => s.revenue),
      tone: PALETTE[0],
    },
    {
      key: "profit",
      label: "利润",
      value: money(kpi?.profit),
      delta: delta.profit,
      spark: run.series.map((s) => s.profit),
      tone: PALETTE[1],
    },
    {
      key: "roas",
      label: "广告 ROAS",
      value: kpi?.roas == null ? "—" : num(kpi.roas, 2),
      delta: delta.roas,
      spark: run.series.map((s) => s.ad_spend),
      tone: PALETTE[2],
    },
    {
      key: "health",
      label: "库存健康度",
      value: kpi ? ratio(kpi.inventory_health) : "—",
      delta: delta.inventory_health,
      spark: [] as number[],
      tone: PALETTE[3],
    },
  ];

  const highCount = run.issues.filter((i) => i.severity === "high").length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">经营概览</h1>
          <p className="mt-1.5 text-sm text-ink-500">
            共发现 {run.issues.length} 个问题，其中高优先级 {highCount} 个 · 分析模型 {run.fake_llm ? "内置模型" : run.llm}
          </p>
        </div>
        <Link to="/issues" className="btn-ghost">
          查看全部问题 →
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <article key={card.key} className="card flex flex-col gap-3 p-5">
            <p className="text-sm text-ink-500">{card.label}</p>
            <p className="num text-[26px] font-semibold leading-none">{card.value}</p>
            <div className="flex items-center justify-between gap-2">
              <Delta value={hasPrev ? card.delta : null} text={hasPrev ? signedPct(card.delta) : "首次运行，无对比"} />
              {hasPrev && <span className="text-xs text-ink-400">较上次</span>}
            </div>
            {card.spark.length > 1 && <Sparkline values={card.spark} tone={card.tone} />}
          </article>
        ))}
      </div>

      <Card>
        <CardHead
          title="全店日趋势"
          desc="按日汇总所有 SKU 的收入、利润与广告花费"
          extra={<span className="num text-sm text-ink-500">广告花费 {moneyCompact(kpi?.ad_spend)}</span>}
        />
        {run.series.length > 1 ? <StoreTrend rows={run.series} /> : <Empty text="暂无日序列数据" />}
      </Card>

      <Card className="p-0">
        <div className="flex items-end justify-between gap-4 px-6 pb-5 pt-6">
          <div>
            <h2 className="text-base font-semibold">今日问题</h2>
            <p className="mt-1 text-sm text-ink-500">点击任意一行进入问题详情</p>
          </div>
        </div>
        {run.issues.length === 0 ? (
          <div className="px-6 pb-6">
            <Empty text="本次运行没有检测到异常" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-y border-hairline bg-canvas/60 text-left text-xs text-ink-500">
                  <th className="px-6 py-3 font-medium">问题类型</th>
                  <th className="px-6 py-3 font-medium">商品</th>
                  <th className="px-6 py-3 font-medium">严重度</th>
                  <th className="px-6 py-3 text-right font-medium">预计影响</th>
                  <th className="px-6 py-3 text-right font-medium">决策</th>
                </tr>
              </thead>
              <tbody>
                {run.issues.map((issue) => (
                  <tr key={issue.issue_id} className="border-b border-hairline last:border-0 hover:bg-canvas/60">
                    <td className="px-6 py-4">
                      <Link to={`/issues/${issue.issue_id}`} className="font-medium text-ink-900 hover:text-brand-700">
                        {t.issueType(issue.issue_type)}
                      </Link>
                    </td>
                    <td className="num px-6 py-4 text-ink-500">{issue.entity_id}</td>
                    <td className="px-6 py-4">
                      <SeverityChip value={issue.severity} />
                    </td>
                    <td className="num px-6 py-4 text-right font-medium">{money(issue.estimated_impact)}</td>
                    <td className="px-6 py-4 text-right">
                      {issue.decision_id ? (
                        <Link to={`/issues/${issue.issue_id}/decision`} className="text-sm text-brand-600 hover:text-brand-700">
                          查看策略
                        </Link>
                      ) : (
                        <span className="text-sm text-ink-400">生成中</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
