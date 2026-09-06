import type { ReactNode } from "react";
import { t } from "../i18n";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card p-6 ${className}`}>{children}</section>;
}

export function CardHead({ title, desc, extra }: { title: string; desc?: string; extra?: ReactNode }) {
  return (
    <header className="mb-5 flex items-end justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold text-ink-900">{title}</h2>
        {desc && <p className="mt-1 text-sm text-ink-500">{desc}</p>}
      </div>
      {extra}
    </header>
  );
}

const SEVERITY_TONE: Record<string, string> = {
  high: "bg-fall-soft text-fall",
  medium: "bg-warn-soft text-warn",
  low: "bg-brand-50 text-brand-700",
};

export function SeverityChip({ value }: { value: string }) {
  return (
    <span className={`chip ${SEVERITY_TONE[value] ?? "bg-canvas text-ink-500"}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {t.severity(value)}
    </span>
  );
}

const STATUS_TONE: Record<string, string> = {
  done: "bg-rise-soft text-rise",
  running: "bg-brand-50 text-brand-700",
  pending: "bg-canvas text-ink-500",
  failed: "bg-fall-soft text-fall",
};

export function StatusChip({ value }: { value: string }) {
  return (
    <span className={`chip ${STATUS_TONE[value] ?? "bg-canvas text-ink-500"}`}>
      {value === "running" && <span className="size-1.5 animate-pulse rounded-full bg-current" />}
      {t.runStatus(value)}
    </span>
  );
}

export function Delta({ value, text }: { value: number | null | undefined; text: string }) {
  const tone =
    value === null || value === undefined || Number.isNaN(value) || value === 0
      ? "text-ink-400"
      : value > 0
        ? "text-rise"
        : "text-fall";
  const arrow = value && value > 0 ? "↑" : value && value < 0 ? "↓" : "";
  return (
    <span className={`num text-sm font-medium ${tone}`}>
      {arrow} {text}
    </span>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 text-center">
      <div className="grid size-11 place-items-center rounded-full bg-canvas text-lg text-ink-400">∅</div>
      <p className="text-sm text-ink-500">{text}</p>
    </div>
  );
}

export function Loading({ text = "加载中" }: { text?: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center gap-3 text-sm text-ink-500">
      <span className="size-4 animate-spin rounded-full border-2 border-brand-200 border-t-brand-600" />
      {text}
    </div>
  );
}

export function ErrorBox({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-fall/20 bg-fall-soft p-4 text-sm text-fall">
      <p className="font-medium">请求失败</p>
      <p className="mt-1 break-all opacity-80">{text}</p>
    </div>
  );
}
