import type {
  BenchmarkModelReport,
  BenchmarkQuestionDetail,
  BenchmarkQuestionRow,
  BenchmarkRunProgress,
  BenchmarkRunReport,
  BenchmarkRunSummary,
} from '@/api/types'

export const OPUS = 'anthropic/claude-opus-4.8'
export const QWEN = 'qwen/qwen3.8-27b'
export const GPT = 'openai/gpt-5.1'
export const GEMINI = 'google/gemini-3.1-pro-preview'

export function modelReport(
  model: string,
  extra: Partial<BenchmarkModelReport> = {},
): BenchmarkModelReport {
  return {
    model,
    asked: 100,
    graded_alone: 100,
    graded_with: 97,
    right_alone: 30,
    right_with: 80,
    rate_alone: 0.3,
    rate_with: 0.8,
    lift: 50,
    made_up_alone: 0.25,
    made_up_with: 0.08,
    pending: 3,
    technical: 0,
    tally: {
      alone: { correct: 30, abstain: 45, hallucinate: 25, pending: 0, technical: 0, graded: 100 },
      with: { correct: 80, abstain: 12, hallucinate: 8, pending: 3, technical: 0, graded: 100 },
    },
    kinds: [
      {
        generator: 'named_entity_masking',
        asked: 10,
        graded_alone: 10,
        graded_with: 10,
        right_alone: 1,
        right_with: 9,
        rate_alone: 0.1,
        rate_with: 0.9,
        lift: 80,
      },
      {
        generator: 'temporal_masking',
        asked: 20,
        graded_alone: 20,
        graded_with: 20,
        right_alone: 3,
        right_with: 17,
        rate_alone: 0.15,
        rate_with: 0.85,
        lift: 70,
      },
    ],
    groups: { fixed: 50, either: 30, still: 15, worse: 5 },
    checks: {
      challenged: 0,
      denial_limit: null,
      held_by_round: [],
      kept_right: null,
      repeated: 0,
      same_answer: null,
      by_temperature: [],
      trick_asked: 0,
      trick_answered: 0,
      trick_alone_asked: null,
      trick_alone_answered: null,
      searched: 0,
      search_found: null,
      missed: 0,
      answers: 0,
      judges_agreed: 0,
      agreement: null,
    },
    ...extra,
  }
}

export function runSummary(
  jobId: string,
  extra: Partial<BenchmarkRunSummary> = {},
): BenchmarkRunSummary {
  return {
    job_id: jobId,
    created_at: '2026-09-30T06:00:00Z',
    finished_at: '2026-09-30T06:50:00Z',
    trigger: 'schedule',
    window_days: 1,
    articles: 9,
    questions: 100,
    models: [modelReport(OPUS), modelReport(QWEN)],
    lift_lo: 47,
    lift_hi: 70,
    card_outdated: false,
    published: false,
    card_id: null,
    ...extra,
  }
}

export function progress(
  jobId: string,
  extra: Partial<BenchmarkRunProgress> = {},
): BenchmarkRunProgress {
  return {
    job_id: jobId,
    state: 'running',
    trigger: 'schedule',
    kind: 'pipeline',
    phase: 'evaluate',
    block: '',
    model: '',
    step_done: 3,
    step_total: 12,
    done: 0,
    total: 0,
    message: '',
    created_at: '2026-10-01T12:00:00Z',
    started_at: '2026-10-01T12:00:05Z',
    ...extra,
  }
}

export function runReport(extra: Partial<BenchmarkRunReport> = {}): BenchmarkRunReport {
  return {
    run: runSummary('j1'),
    funnel: { written: 120, removed: {}, removed_total: 20, asked: 100, trick: 5 },
    models: [
      modelReport(OPUS),
      modelReport(QWEN, {
        rate_with: 0.85,
        rate_alone: 0.38,
        lift: 47,
        made_up_alone: 0.22,
        made_up_with: 0.07,
      }),
    ],
    judges: [GPT, GEMINI],
    method: {
      articles_from: null,
      articles_to: null,
      generator_model: null,
      kinds: [],
      trick: 0,
      context_docs: null,
      judges: [],
      profile: null,
      next_run_at: null,
      denial_rounds: null,
      repeats: null,
    },
    ...extra,
  }
}

export function questionRow(
  qaId: string,
  extra: Partial<BenchmarkQuestionRow> = {},
): BenchmarkQuestionRow {
  return {
    n: 1,
    qa_id: qaId,
    generator: 'named_entity_masking',
    document_title: 'Article A',
    file_name: 'a.md',
    question: `Question ${qaId}`,
    gold_answer: `Gold ${qaId}`,
    status: 'retired',
    verdict_alone: 'abstain',
    verdict_with: 'correct',
    group: 'fixed',
    overridden: false,
    excluded: false,
    ...extra,
  }
}

export function questionDetail(
  qaId: string,
  extra: Partial<BenchmarkQuestionDetail> = {},
): BenchmarkQuestionDetail {
  return {
    question: questionRow(qaId),
    context: 'The source paragraph',
    arms: {
      alone: {
        answer: `Alone ${qaId}`,
        verdict: 'abstain',
        reasoning: '',
        result_id: `${qaId}-alone`,
        override: null,
        retrieval: null,
        denial: null,
        repeats: null,
      },
      with: {
        answer: `With ${qaId}`,
        verdict: 'correct',
        reasoning: '',
        result_id: `${qaId}-with`,
        override: null,
        retrieval: { hit: true, rank: 2, context_docs: 3 },
        denial: { rounds: 2, flipped: true, flip_round: 2, limit: 3 },
        repeats: { trials: 4, right: 3, consistency: 0.75, by_temperature: {} },
      },
    },
    judges: [
      { model: GPT, primary: true, alone: 'abstain', with: 'correct' },
      { model: GEMINI, primary: false, alone: 'abstain', with: 'correct' },
    ],
    judges_agreed: true,
    exclusion: null,
    ...extra,
  }
}
