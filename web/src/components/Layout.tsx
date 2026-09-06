import type { ReactNode } from "react";
import { NavLink, useParams } from "react-router-dom";
import type { Ctx } from "../App";
import { t } from "../i18n";
import { StatusChip } from "./ui";
import { StepNav } from "./StepNav";

const NAV = [
  { to: "/", label: "概览", icon: "◎", end: true },
  { to: "/issues", label: "问题", icon: "◈", end: false },
  { to: "/decisions", label: "决策", icon: "◆", end: false },
];

export function Layout({ ctx, children }: { ctx: Ctx; children: ReactNode }) {
  const { issueId } = useParams();
  const { run, runs, busy, mode, setMode, setRunId, runDaily } = ctx;
  const hasDecision = Boolean(run?.issues.find((i) => i.issue_id === issueId)?.decision_id);
  const runningNotice = run?.status === "running" || run?.status === "pending";

  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col gap-6 border-r border-hairline bg-surface px-5 py-6">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl bg-brand-600 text-sm font-semibold text-white">
            决策
          </span>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-sm font-semibold" title={run?.store_name}>
              {run?.store_name || "电商决策智能体"}
            </p>
            <p className="text-xs text-ink-400">经营决策控制台</p>
          </div>
        </div>

        <nav className="flex flex-col gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                  isActive ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-canvas"
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-4">
          <label className="flex flex-col gap-2">
            <span className="text-xs font-medium text-ink-500">运行批次</span>
            <select
              value={run?.run_id ?? ""}
              onChange={(e) => setRunId(e.target.value)}
              className="w-full rounded-xl border border-hairline bg-surface px-3 py-2.5 text-sm text-ink-900 outline-none transition focus:border-brand-500"
            >
              {!runs.length && <option value="">暂无运行记录</option>}
              {runs.map((item) => (
                <option key={item.run_id} value={item.run_id}>
                  {item.as_of ?? item.run_id.slice(0, 12)} · {t.runStatus(item.status)}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-col gap-2">
            <span className="text-xs font-medium text-ink-500">分析模式</span>
            <div className="grid grid-cols-2 gap-1 rounded-xl bg-canvas p-1">
              <button
                onClick={() => setMode("fast")}
                className={`rounded-lg px-2 py-2 text-xs font-medium transition ${
                  mode === "fast" ? "bg-surface text-brand-700 shadow-card" : "text-ink-500"
                }`}
              >
                极速演示
              </button>
              <button
                onClick={() => setMode("deep")}
                className={`rounded-lg px-2 py-2 text-xs font-medium transition ${
                  mode === "deep" ? "bg-surface text-brand-700 shadow-card" : "text-ink-500"
                }`}
              >
                DeepSeek
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-ink-400">
              {mode === "fast" ? "内置模型，秒级出结果" : "真实大模型，后台运行需数分钟"}
            </p>
          </div>

          <button className="btn-primary w-full" disabled={busy} onClick={runDaily}>
            {busy ? "正在运行…" : "运行今日分析"}
          </button>
          <p className="text-[11px] text-ink-400">数据源：内置 Olist 数据集</p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-4 border-b border-hairline bg-surface/85 px-8 py-4 backdrop-blur">
          <StepNav hasDecision={hasDecision} />
          <div className="flex items-center gap-3">
            {run && <StatusChip value={run.status} />}
            {run?.as_of && <span className="num text-sm text-ink-500">经营日 {run.as_of}</span>}
          </div>
        </header>

        <main className="scroll-slim flex-1 px-8 py-7">
          {runningNotice && (
            <div className="mb-5 flex items-center gap-3 rounded-2xl border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-brand-700">
              <span className="size-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
              正在调用大模型分析全部问题，页面会自动刷新
            </div>
          )}
          {run?.status === "failed" && run.error && (
            <div className="mb-5 rounded-2xl border border-fall/20 bg-fall-soft px-4 py-3 text-sm text-fall">
              本次运行失败：{run.error}
            </div>
          )}
          {ctx.error && (
            <div className="mb-5 rounded-2xl border border-fall/20 bg-fall-soft px-4 py-3 text-sm text-fall">
              {ctx.error}
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
