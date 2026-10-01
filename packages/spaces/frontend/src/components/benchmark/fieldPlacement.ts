/**
 * Which phase block each settings field belongs to.
 *
 * The keys are this console's blocks — the verbs on its buttons — not the
 * benchmark's group codes, which are the strings quoted below.
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
  generate: {
    probe: [
      'dataset_mode',
      'document_window_days',
      'dataset_max_pairs',
      'chunks_per_run',
      'pairs_per_chunk',
      'min_chunk_chars',
      'generate_in_cycle',
    ],
    instrument: [
      'generator_model',
      'extractive_mode',
      // Screening is part of building: this is the gate a fresh pair has to
      // pass to become one worth measuring with.
      'answer_coverage_threshold',
    ],
  },
  filter: {
    probe: [],
    instrument: [],
  },
  execute: {
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
      // Two ceilings on what the measurement contains: how much of a found
      // chunk the model is shown, and whether a long answer is graded whole
      // or graded cut off.
      'fragment_max_chars',
      'answer_max_tokens',
      'subject_models',
      'methodology_profile',
      'max_consecutive_failures',
      'reuse_answers',
      'audit_log',
      // Read by the report, decided here: it is the floor the repeats
      // above have to clear to count as one answer rather than several.
      'consistency_floor',
    ],
  },
  judge: {
    probe: [],
    instrument: [
      'judge_model',
      'judge_models',
      'judge_policy',
      'key_facts_threshold',
      'text_metrics',
    ],
  },
} as const

export type PhaseBlockKey = keyof typeof FIELD_PLACEMENT
