import { Link } from "react-router-dom";
import type { Ctx } from "../App";
import { Card, Empty, SeverityChip } from "../components/ui";
import { money, ratio } from "../fmt";
import { t } from "../i18n";

const RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

export function IssuesPage({ ctx }: { ctx: Ctx }) {
  const run = ctx.run;

  if (!run) {
    return (
      <Card>
        <Empty text="请先运行一次今日分析" />
      </Card>
    );
  }

  const issues = [...run.issues].sort(
    (a, b) =>
      (RANK[a.severity] ?? 9) - (RANK[b.severity] ?? 9) ||
      Number(b.estimated_impact ?? 0) - Number(a.estimated_impact ?? 0),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">问题清单</h1>
        <p className="mt-1.5 text-sm text-ink-500">本次运行共 {issues.length} 个问题，按严重度与影响金额排序</p>
      </div>

      {issues.length === 0 ? (
        <Card>
          <Empty text="本次运行没有检测到异常" />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {issues.map((issue) => (
            <Link
              key={issue.issue_id}
              to={`/issues/${issue.issue_id}`}
              className="card group flex flex-col gap-4 p-5 transition hover:-translate-y-0.5 hover:shadow-lift"
            >
              <div className="flex items-start justify-between gap-3">
                <SeverityChip value={issue.severity} />
                <span className="text-xs text-ink-400">置信度 {ratio(issue.confidence)}</span>
              </div>
              <div>
                <h3 className="text-lg font-semibold group-hover:text-brand-700">{t.issueType(issue.issue_type)}</h3>
                <p className="num mt-1 text-sm text-ink-500">{issue.entity_id}</p>
              </div>
              <div className="mt-auto flex items-end justify-between border-t border-hairline pt-4">
                <div>
                  <p className="text-xs text-ink-400">预计影响</p>
                  <p className="num mt-0.5 text-lg font-semibold">{money(issue.estimated_impact)}</p>
                </div>
                <span className="text-sm text-brand-600 group-hover:text-brand-700">
                  {issue.decision_id ? "查看详情 →" : "生成中"}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
