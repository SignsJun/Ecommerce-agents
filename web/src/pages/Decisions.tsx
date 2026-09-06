import { Link } from "react-router-dom";
import type { Ctx } from "../App";
import { Card, Empty, SeverityChip } from "../components/ui";
import { money } from "../fmt";
import { t } from "../i18n";

export function DecisionsPage({ ctx }: { ctx: Ctx }) {
  const run = ctx.run;

  if (!run) {
    return (
      <Card>
        <Empty text="请先运行一次今日分析" />
      </Card>
    );
  }

  const archived = run.issues.filter((i) => i.decision_id);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">决策档案</h1>
        <p className="mt-1.5 text-sm text-ink-500">
          本次运行已归档 {archived.length} / {run.issues.length} 个决策
        </p>
      </div>

      {archived.length === 0 ? (
        <Card>
          <Empty text="尚未产生决策档案" />
        </Card>
      ) : (
        <Card className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline bg-canvas/60 text-left text-xs text-ink-500">
                  <th className="px-6 py-3 font-medium">问题类型</th>
                  <th className="px-6 py-3 font-medium">商品</th>
                  <th className="px-6 py-3 font-medium">严重度</th>
                  <th className="px-6 py-3 text-right font-medium">预计影响</th>
                  <th className="px-6 py-3 font-medium">决策编号</th>
                  <th className="px-6 py-3 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {archived.map((issue) => (
                  <tr key={issue.issue_id} className="border-b border-hairline last:border-0 hover:bg-canvas/60">
                    <td className="px-6 py-4 font-medium">{t.issueType(issue.issue_type)}</td>
                    <td className="num px-6 py-4 text-ink-500">{issue.entity_id}</td>
                    <td className="px-6 py-4">
                      <SeverityChip value={issue.severity} />
                    </td>
                    <td className="num px-6 py-4 text-right">{money(issue.estimated_impact)}</td>
                    <td className="num px-6 py-4 text-xs text-ink-400">{issue.decision_id}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-3">
                        <Link to={`/issues/${issue.issue_id}/decision`} className="text-brand-600 hover:text-brand-700">
                          策略
                        </Link>
                        <Link to={`/issues/${issue.issue_id}/trace`} className="text-brand-600 hover:text-brand-700">
                          链路
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
