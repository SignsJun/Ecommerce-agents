import { Link, useLocation, useParams } from "react-router-dom";

const STEPS = [
  { key: "overview", label: "概览", desc: "店铺日指标" },
  { key: "issue", label: "问题详情", desc: "驱动与根因" },
  { key: "strategy", label: "策略对比", desc: "候选与仿真" },
  { key: "trace", label: "决策链路", desc: "证据溯源" },
];

function currentStep(pathname: string) {
  if (pathname.endsWith("/trace")) return 3;
  if (pathname.endsWith("/decision")) return 2;
  if (pathname.startsWith("/issues/")) return 1;
  return 0;
}

export function StepNav({ hasDecision }: { hasDecision: boolean }) {
  const { pathname } = useLocation();
  const { issueId } = useParams();
  const active = currentStep(pathname);

  const href = (index: number) => {
    if (index === 0) return "/";
    if (!issueId) return null;
    if (index === 1) return `/issues/${issueId}`;
    if (!hasDecision) return null;
    return index === 2 ? `/issues/${issueId}/decision` : `/issues/${issueId}/trace`;
  };

  return (
    <ol className="flex flex-wrap items-center gap-1">
      {STEPS.map((step, index) => {
        const to = href(index);
        const isActive = index === active;
        const done = index < active;
        const body = (
          <>
            <span
              className={`num grid size-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${
                isActive
                  ? "bg-brand-600 text-white"
                  : done
                    ? "bg-brand-100 text-brand-700"
                    : "bg-canvas text-ink-400"
              }`}
            >
              {index + 1}
            </span>
            <span className="flex flex-col leading-tight">
              <span className={isActive ? "text-ink-900" : ""}>{step.label}</span>
              <span className="text-[11px] text-ink-400">{step.desc}</span>
            </span>
          </>
        );
        const base =
          "flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium transition";
        return (
          <li key={step.key} className="flex items-center gap-1">
            {to ? (
              <Link
                to={to}
                className={`${base} ${isActive ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-canvas"}`}
              >
                {body}
              </Link>
            ) : (
              <span className={`${base} cursor-not-allowed text-ink-400`} title="请先选择问题">
                {body}
              </span>
            )}
            {index < STEPS.length - 1 && <span className="text-ink-400">›</span>}
          </li>
        );
      })}
    </ol>
  );
}
