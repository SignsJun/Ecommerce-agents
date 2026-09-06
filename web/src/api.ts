import type { DecisionDetail, IssueDetail, RunDetail, TraceDetail } from "./types";

async function read<T>(r: Response): Promise<T> {
  if (!r.ok) {
    throw new Error(await r.text());
  }
  return r.json() as Promise<T>;
}

export function listRuns() {
  return fetch("/api/v1/runs").then((r) => read<RunDetail[]>(r));
}

export function getRun(runId: string) {
  return fetch(`/api/v1/runs/${runId}`).then((r) => read<RunDetail>(r));
}

export function getIssue(runId: string, issueId: string) {
  return fetch(`/api/v1/runs/${runId}/issues/${issueId}`).then((r) => read<IssueDetail>(r));
}

export function getDecision(runId: string, issueId: string) {
  return fetch(`/api/v1/runs/${runId}/issues/${issueId}/decision`).then((r) => read<DecisionDetail>(r));
}

export function getTrace(decisionId: string) {
  return fetch(`/api/v1/decisions/${decisionId}/trace`).then((r) => read<TraceDetail>(r));
}

export function createRun(opts: { fakeLlm: boolean; n?: number }) {
  return fetch("/api/v1/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "bundled", fake_llm: opts.fakeLlm, n: opts.n ?? 2 }),
  }).then((r) => read<RunDetail>(r));
}
