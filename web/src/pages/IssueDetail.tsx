import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Ctx } from "../App";
import { getIssue } from "../api";
import { SkuTrend } from "../charts/Charts";
import { Card, CardHead, Delta, Empty, ErrorBox, Loading, SeverityChip } from "../components/ui";
import { count, money, num, ratio, signedPct } from "../fmt";
import { MONEY_DRIVERS, t } from "../i18n";
import type { Driver, IssueDetail } from "../types";

const INVERT = new Set(["ad_spend", "refund_loss", "refund_rate_7d", "days_of_cover"]);

function driverValue(driver: Driver) {
  if (MONEY_DRIVERS.has(driver.name)) return money(driver.current);
  if (driver.name === "refund_rate_7d") return ratio(driver.current, 1);
  if (driver.name === "days_of_cover") return `${count(driver.current)} 天`;
  if (driver.name === "units_sold") return count(driver.current);
  return num(driver.current, 2);
}

export function IssueDetailPage({ ctx }: { ctx: Ctx }) {
  const { issueId } = useParams();
  const runId = ctx.run?.run_id;
  const [data, setData] = useState<IssueDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !issueId) return;
    setData(null);
    setError(null);
    getIssue(runId, issueId)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [runId, issueId]);

  if (error) return <ErrorBox text={error} />;
  if (!data) return <Loading text="正在加载问题详情" />;

  const { issue, diagnosis } = data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <nav className="mb-2 flex items-center gap-2 text-sm text-ink-500">
            <Link to="/issues" className="hover:text-brand-700">
              问题清单
            </Link>
            <span>/</span>
            <span className="num">{issue.entity_id}</span>
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{t.issueType(issue.issue_type)}</h1>
            <SeverityChip value={issue.severity} />
          </div>
          <p className="mt-1.5 text-sm text-ink-500">
            预计影响 <span className="num font-medium text-ink-700">{money(issue.estimated_impact)}</span> · 检测置信度{" "}
            {ratio(issue.confidence)}
          </p>
        </div>
        {data.decision_id ? (
          <Link to={`/issues/${issue.issue_id}/decision`} className="btn-primary">
            查看策略对比 →
          </Link>
        ) : (
          <span className="btn-ghost cursor-not-allowed opacity-60">策略生成中</span>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {data.drivers.map((driver) => (
          <article key={driver.name} className="card flex flex-col gap-2 p-5">
            <p className="text-sm text-ink-500">{t.driver(driver.name)}</p>
            <p className="num text-xl font-semibold">{driverValue(driver)}</p>
            <Delta
              value={INVERT.has(driver.name) && driver.delta != null ? -driver.delta : driver.delta}
              text={driver.delta == null ? "无对比" : `${signedPct(driver.delta)} 环比`}
            />
          </article>
        ))}
      </div>

      <Card>
        <CardHead title="30 日走势" desc="收入、利润、广告花费与每日期末库存" />
        {data.trend.length > 1 ? <SkuTrend rows={data.trend} /> : <Empty text="暂无日序列数据" />}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHead
            title="根因诊断"
            desc={
              diagnosis
                ? `${t.diagnosisStatus(diagnosis.status)} · 整体置信度 ${ratio(diagnosis.overall_confidence)}`
                : undefined
            }
          />
          {!diagnosis ? (
            <Empty text="诊断尚未完成" />
          ) : (
            <div className="flex flex-col gap-3">
              {diagnosis.root_causes.map((cause) => (
                <div key={cause.cause_type} className="rounded-xl border border-hairline p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">{t.cause(cause.cause_type)}</p>
                    <span className="chip bg-brand-50 text-brand-700">置信度 {ratio(cause.confidence)}</span>
                  </div>
                  <p className="mt-1.5 text-sm text-ink-500">{cause.description}</p>
                  <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-canvas">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{ width: `${Math.min(100, cause.confidence * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
              {diagnosis.uncertainties.length > 0 && (
                <div className="rounded-xl bg-warn-soft p-4 text-sm text-warn">
                  <p className="font-medium">仍存在不确定性</p>
                  <ul className="mt-1.5 list-disc space-y-1 pl-4 opacity-90">
                    {diagnosis.uncertainties.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </Card>

        <Card>
          <CardHead title="支撑证据" desc={`共 ${data.evidence.length} 条，来自指标监测与诊断工具`} />
          {data.evidence.length === 0 ? (
            <Empty text="暂无证据" />
          ) : (
            <ul className="scroll-slim flex max-h-[420px] flex-col gap-3 overflow-y-auto pr-1">
              {data.evidence.map((item) => (
                <li key={item.evidence_id} className="rounded-xl border border-hairline p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="chip bg-canvas text-ink-700">
                      {item.metric ? t.metric(item.metric) : t.evidenceSource(item.source_type)}
                    </span>
                    <span className="text-xs text-ink-400">可信度 {ratio(item.reliability)}</span>
                  </div>
                  <p className="mt-2 text-sm text-ink-700">{t.description(item.description)}</p>
                  {item.value != null && (
                    <p className="num mt-1.5 text-xs text-ink-400">观测值：{String(item.value)}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
