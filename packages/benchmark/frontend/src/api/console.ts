import { api, query } from "./client";
import type {
  FilterRequest,
  JobView,
  JudgeRequest,
  PairPage,
  PairResponse,
  PairStatus,
  ProbeLayer,
  ProbeSettings,
  ResultPage,
  ResultResponse,
  RunRequest,
  Verdict,
} from "./types";

// --- pairs (Generation / Filtering) -----------------------------------------

export function listPairs(filters: {
  status?: PairStatus;
  cohort?: string;
  generator?: string;
  limit?: number;
  offset?: number;
}): Promise<PairPage> {
  return api.get<PairPage>(`/console/pairs${query(filters)}`);
}

export function getPair(id: string): Promise<PairResponse> {
  return api.get<PairResponse>(`/console/pairs/${id}`);
}

export function updatePairStatus(
  id: string,
  status: PairStatus,
  note = "",
): Promise<PairResponse> {
  return api.patch<PairResponse>(`/console/pairs/${id}`, { status, note });
}

export function deletePair(id: string): Promise<void> {
  return api.delete(`/console/pairs/${id}`);
}

export function runFilter(request: FilterRequest = {}): Promise<JobView> {
  return api.post<JobView>("/console/filter", request);
}

// --- results (Judging) ------------------------------------------------------

export function listResults(filters: {
  verdict?: Verdict;
  qa_id?: string;
  limit?: number;
  offset?: number;
}): Promise<ResultPage> {
  return api.get<ResultPage>(`/console/results${query(filters)}`);
}

export function overrideVerdict(
  resultId: string,
  verdict: Verdict,
  reasoning = "",
): Promise<ResultResponse> {
  return api.post<ResultResponse>(`/console/results/${resultId}/verdict`, {
    verdict,
    reasoning,
  });
}

export function runJudge(request: JudgeRequest = {}): Promise<JobView> {
  return api.post<JobView>("/console/judge", request);
}

// --- runs (Generation alone, Execution alone, Preparation, Testing) --------

export function startRun(request: RunRequest): Promise<JobView> {
  return api.post<JobView>("/console/runs", request);
}

export function listJobs(): Promise<JobView[]> {
  return api.get<JobView[]>("/console/jobs");
}

// --- report ------------------------------------------------------------------

export function buildReport(): Promise<Record<string, unknown>> {
  return api.post("/console/report");
}

export function publishReport(): Promise<Record<string, unknown>> {
  return api.post("/console/publish");
}

export function retractReport(): Promise<void> {
  return api.post("/console/retract");
}

// --- this target's own probe layer ------------------------------------------

export function getProbe(): Promise<ProbeSettings> {
  return api.get<ProbeSettings>("/console/probe");
}

export function saveProbe(probe: ProbeLayer): Promise<ProbeSettings> {
  return api.put<ProbeSettings>("/console/probe", probe);
}
