import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { createRun, getRun, listRuns } from "./api";
import { Layout } from "./components/Layout";
import { DecisionPage } from "./pages/Decision";
import { DecisionsPage } from "./pages/Decisions";
import { IssueDetailPage } from "./pages/IssueDetail";
import { IssuesPage } from "./pages/Issues";
import { OverviewPage } from "./pages/Overview";
import { TracePage } from "./pages/Trace";
import type { RunDetail } from "./types";

export type RunMode = "fast" | "deep";

export type Ctx = {
  run: RunDetail | null;
  runs: RunDetail[];
  error: string | null;
  busy: boolean;
  mode: RunMode;
  setMode: (mode: RunMode) => void;
  setRunId: (id: string) => void;
  runDaily: () => void;
};

export function App() {
  const [runs, setRuns] = useState<RunDetail[]>([]);
  const [runId, setRunId] = useState<string>(() => localStorage.getItem("run_id") || "");
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<RunMode>("fast");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    listRuns()
      .then((rows) => {
        setRuns(rows);
        setRunId((prev) => prev || (rows.length ? rows[0].run_id : ""));
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    localStorage.setItem("run_id", runId);
    getRun(runId)
      .then(setRun)
      .catch((e) => setError(String(e)));
  }, [runId]);

  const status = run?.status;
  const activeRunId = run?.run_id;

  useEffect(() => {
    if (!activeRunId || (status !== "running" && status !== "pending")) return;
    const timer = setInterval(() => {
      getRun(activeRunId)
        .then((next) => {
          setRun(next);
          setRuns((prev) => [next, ...prev.filter((r) => r.run_id !== next.run_id)]);
        })
        .catch((e) => setError(String(e)));
    }, 2000);
    return () => clearInterval(timer);
  }, [activeRunId, status]);

  const runDaily = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await createRun({ fakeLlm: mode === "fast" });
      setRuns((prev) => [created, ...prev.filter((r) => r.run_id !== created.run_id)]);
      setRunId(created.run_id);
      setRun(created);
      nav("/");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [mode, nav]);

  const ctx = useMemo<Ctx>(
    () => ({ run, runs, error, busy, mode, setMode, setRunId, runDaily }),
    [run, runs, error, busy, mode, runDaily],
  );

  return (
    <Routes>
      <Route
        path="/"
        element={
          <Layout ctx={ctx}>
            <OverviewPage ctx={ctx} />
          </Layout>
        }
      />
      <Route
        path="/issues"
        element={
          <Layout ctx={ctx}>
            <IssuesPage ctx={ctx} />
          </Layout>
        }
      />
      <Route
        path="/issues/:issueId"
        element={
          <Layout ctx={ctx}>
            <IssueDetailPage ctx={ctx} />
          </Layout>
        }
      />
      <Route
        path="/issues/:issueId/decision"
        element={
          <Layout ctx={ctx}>
            <DecisionPage ctx={ctx} />
          </Layout>
        }
      />
      <Route
        path="/issues/:issueId/trace"
        element={
          <Layout ctx={ctx}>
            <TracePage ctx={ctx} />
          </Layout>
        }
      />
      <Route
        path="/decisions"
        element={
          <Layout ctx={ctx}>
            <DecisionsPage ctx={ctx} />
          </Layout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
