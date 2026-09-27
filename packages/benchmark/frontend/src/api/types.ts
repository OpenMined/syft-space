// Mirrors syft_benchmark.control.schemas — kept in step by hand, the same
// way the rest of this codebase's two sides (Python/TypeScript) already are.

export type PairStatus = "pending" | "active" | "rejected" | "retired";
export type Verdict = "correct" | "abstain" | "hallucinate" | "pending";

export interface PairResponse {
  id: string;
  generator: string;
  task_type: string;
  cohort: string;
  status: PairStatus;
  status_note: string;
  question: string;
  answer: string;
  context: string;
  expected_behavior: string;
  document_title: string;
  file_name: string;
  meta: Record<string, unknown>;
  created_at: string;
  has_results: boolean;
}

export interface PairPage {
  items: PairResponse[];
  total: number;
}

export interface ResultResponse {
  id: string;
  qa_id: string;
  question: string;
  answer: string;
  verdict: Verdict;
  reasoning: string;
  judge_model: string;
  context_mode: string;
  block: string;
  model: string;
  created_at: string;
  is_latest: boolean;
}

export interface ResultPage {
  items: ResultResponse[];
  total: number;
}

export interface JobView {
  id: string;
  target: string;
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  phase: string;
  kind: "pipeline" | "filter" | "judge";
  done: number;
  total: number;
  arm: string;
  block: string;
  model: string;
  step_done: number;
  step_total: number;
  message: string;
  trigger: string;
  error: string;
  card: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface RunRequest {
  generate?: boolean | null;
  filter?: boolean | null;
  evaluate?: boolean | null;
  defer_judging?: boolean;
  publish?: boolean;
  limit?: number | null;
}

export interface FilterRequest {
  generator?: string | null;
  cohort?: string | null;
  limit?: number | null;
}

export interface JudgeRequest {
  limit?: number | null;
}

export type ProbeLayer = Record<string, unknown>;

export interface ProbeField {
  name: string;
  type: string;
  group: string;
  choices?: (string | number)[];
  item_type?: string;
  minimum?: number;
  maximum?: number;
}

export interface ProbeSettings {
  probe: ProbeLayer;
  inherited: ProbeLayer;
  fields: ProbeField[];
}
