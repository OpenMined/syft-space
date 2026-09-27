/**
 * Which phase block each settings field belongs to.
 *
 * The benchmark's own field groups (`arms`, `dataset`, `judging`, ...) are a
 * display hint, not a phase map, and some land oddly against what actually
 * reads a field: `answer_coverage_threshold` is grouped under "judging" on
 * that side but is read during filtering (`generation/validate.py`), and
 * `consistency_floor` only by the report (`report/metrics.py`,
 * `report/narrative.py`) — never by a judge. This placement follows where a
 * field is actually consumed, verified against the source rather than its
 * group code.
 */

export const FIELD_PLACEMENT = {
  generation: {
    probe: [
      'dataset_mode',
      'document_window_days',
      'dataset_max_pairs',
      'chunks_per_run',
      'pairs_per_chunk',
      'min_chunk_chars',
      'generate_in_cycle',
    ],
    instrument: ['generator_model', 'extractive_mode'],
  },
  filtering: {
    probe: [],
    instrument: ['answer_coverage_threshold'],
  },
  execution: {
    probe: [
      'retrieval_top_k',
      'similarity_threshold',
      'endpoint_max_tokens',
      'endpoint_temperature',
      'endpoint_concurrency',
    ],
    instrument: [
      'arms',
      'blocks',
      'denial_rounds',
      'monte_carlo_temperatures',
      'monte_carlo_trials',
      'context_source',
      'context_docs',
      'subject_models',
      'methodology_profile',
      'max_consecutive_failures',
      'reuse_answers',
      'audit_log',
    ],
  },
  judging: {
    probe: [],
    instrument: ['judge_model', 'judge_models', 'judge_policy', 'key_facts_threshold', 'text_metrics'],
  },
  report: {
    probe: [],
    instrument: ['consistency_floor'],
  },
} as const

export type PhaseBlockKey = keyof typeof FIELD_PLACEMENT
