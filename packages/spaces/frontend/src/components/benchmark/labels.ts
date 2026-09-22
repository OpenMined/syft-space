/**
 * Words for the settings the benchmark describes by code.
 *
 * The benchmark sends field names, types and ranges — never prose. That is
 * deliberate on both sides: the wording belongs to whoever renders it, in his
 * reader's language, the same rule by which a card carries `trust.flags` as
 * codes. This file is that wording for this Space.
 *
 * A field with no entry here is still shown, under its own name with its name
 * humanised. New settings therefore appear in the form the day the benchmark
 * grows them, plainly labelled but usable, instead of being invisible until
 * somebody remembers to add them.
 */

export interface Words {
  label: string
  help?: string
}

export const GROUPS: Record<string, Words> = {
  arms: {
    label: 'What is measured',
    help: 'Which comparisons the run makes. Each arm answers a different question, and they are never averaged together.',
  },
  models: {
    label: 'Who takes part',
    help: 'The models that answer and the models that grade. Named here, and named again in every card, because a figure is only comparable against the same line-up.',
  },
  judging: {
    label: 'How answers are graded',
    help: 'A benchmark figure is a verdict by a model. These decide how strict that verdict is.',
  },
  dataset: {
    label: 'The question set',
    help: 'How questions are built from the corpus and which of them stay in the measurement.',
  },
  endpoint: {
    label: 'How the endpoint is questioned',
    help: 'Search and answer limits. These belong to the node: its capacity and its corpus are its own.',
  },
  run: {
    label: 'The run itself',
    help: 'Bookkeeping: what to record, when to give up, what to reuse.',
  },
}

export const FIELDS: Record<string, Words> = {
  // --- what is measured
  arms: {
    label: 'Arms',
    help: 'closed_book — the model alone, no corpus. open_book — the endpoint answers as itself. model_with_context — the same model plus what the search returned. An endpoint in raw mode has no open_book: it never writes an answer.',
  },
  blocks: {
    label: 'Checks',
    help: 'direct asks once. denial_loop pushes back on a correct answer to see whether it caves. monte_carlo repeats at several temperatures. The last two cost several times more.',
  },
  denial_rounds: { label: 'Rounds of pushback', help: 'How many times denial_loop argues.' },
  monte_carlo_temperatures: {
    label: 'Temperatures',
    help: 'Each question is repeated at each of these.',
  },
  monte_carlo_trials: { label: 'Tries per temperature' },
  context_source: {
    label: 'What goes into the context arm',
    help: 'Fragments test whether the model can work with raw material. The endpoint’s finished answer tests something else: whether the model will repeat someone else’s invention.',
  },
  context_docs: { label: 'Fragments in the prompt' },

  // --- who takes part
  generator_model: {
    label: 'Question writer',
    help: 'Reads the corpus to build questions. Usually the one model that must stay inside the perimeter.',
  },
  subject_models: {
    label: 'Models under test',
    help: 'Picked from the benchmark own catalogue, so the spelling is never yours to get right. Never averaged: a mean would move whenever this list changed, while nothing had happened to the endpoint.',
  },
  judge_model: { label: 'Grader' },
  judge_models: {
    label: 'Panel',
    help: 'Several graders see the same answer. How far apart they land is what says whether the figures can be trusted at all. A grader from the same house as a model under test is a conflict of interest — see the policy below.',
  },

  // --- grading
  judge_policy: {
    label: 'Grader independence',
    help: 'A grader from the same vendor as the model under test tends to approve its own style. recuse stands that grader down and carries on with the rest.',
  },
  key_facts_threshold: {
    label: 'Facts an explanation must cover',
    help: 'Not all of them: a plain-language answer legitimately drops particulars.',
  },
  answer_coverage_threshold: { label: 'Reference words found in the fragment' },
  consistency_floor: {
    label: 'Agreement floor',
    help: 'Below this, the measured accuracy says which run reached the report, not how good the model is.',
  },
  text_metrics: {
    label: 'Mechanical similarity',
    help: 'BLEU, ROUGE, BERTScore. They know nothing about truth, never enter a published figure, and exist as a second opinion independent of the grader.',
  },

  // --- the question set
  dataset_mode: {
    label: 'How the set changes',
    help: 'incremental accumulates — for a corpus where the right answer does not go stale. rolling moves with time — for a live stream. rebuild asks the same material again as a new cohort, to test the questions rather than the model.',
  },
  document_window_days: {
    label: 'Freshness window, days',
    help: '0 — the whole corpus.',
  },
  dataset_max_pairs: { label: 'Cap on active questions', help: '0 — no cap.' },
  disabled_generators: {
    label: 'Generators to skip',
    help: 'Each generator is a separate skill. Switching one off removes that skill from every figure.',
  },
  chunks_per_run: { label: 'Fragments per generation pass' },
  pairs_per_chunk: { label: 'Questions per fragment' },
  min_chunk_chars: { label: 'Shortest usable fragment' },
  generate_in_cycle: {
    label: 'Rebuild the set before each run',
    help: 'Switched off when the corpus is closed to the generator, or the set is filled separately.',
  },
  extractive_mode: {
    label: 'How blanks are cut',
    help: 'auto uses spaCy where a model for the language exists and falls back to the LLM.',
  },

  // --- the endpoint
  retrieval_top_k: { label: 'Fragments to ask for' },
  similarity_threshold: {
    label: 'Similarity threshold',
    help: 'At zero the endpoint returns its top-k for any question at all, including ones with no answer in the corpus — it physically cannot stay silent.',
  },
  endpoint_max_tokens: { label: 'Answer length cap' },
  endpoint_temperature: { label: 'Answer temperature' },
  endpoint_concurrency: {
    label: 'Requests at once',
    help: 'This is one node with one model. A queue does not make it faster, it only collects timeouts.',
  },

  // --- the run
  methodology_profile: {
    label: 'Methodology profile',
    help: 'Written into every run and every card. Change the thresholds but not the name, and the report will quietly mix runs that cannot be compared.',
  },
  max_consecutive_failures: {
    label: 'Give up after failures in a row',
    help: 'A wrong key or a node that is down is not cured by retrying. 0 — never give up.',
  },
  reuse_answers: {
    label: 'Reuse identical calls',
    help: 'Switched off when the point is to measure the spread between repeated calls.',
  },
  audit_log: {
    label: 'Keep the audit trail',
    help: 'Prompts and the grader’s reasoning, stored beside each answer. Without it a verdict cannot be checked by anything but another verdict.',
  },
}

/** What to call a field nobody has written words for yet. */
export function humanise(name: string): string {
  const spaced = name.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export function wordsFor(name: string): Words {
  return FIELDS[name] ?? { label: humanise(name) }
}

export function groupWords(code: string): Words {
  return GROUPS[code] ?? { label: humanise(code) }
}

/**
 * Why an arm cannot be measured on this endpoint.
 *
 * The benchmark sends a code; these are the words. An arm being unmeasurable
 * is usually not a fault at all — an endpoint that only searches has no answer
 * to grade — so the wording says what the endpoint is, not what is broken.
 */
export const BLOCKED_ARMS: Record<string, string> = {
  raw_has_no_answer:
    'This endpoint only finds material — it never writes an answer, so there is nothing for this arm to grade. What it can be graded on is whether the search found the right material.',
  summary_hides_fragments:
    'In summary mode the endpoint strips the fragments it found out of its reply, so there is nothing to put in front of the model. Switch the endpoint to raw or both, or have this arm use the endpoint’s finished answer instead.',
  raw_has_no_answer_to_mix:
    'This arm was set to use the endpoint’s finished answer, and this endpoint does not write one. Switch the endpoint to summary or both, or have the arm use the fragments instead.',
}

export function blockedArmWords(code: string): string {
  return BLOCKED_ARMS[code] ?? code
}

/**
 * Why a run did not finish cleanly.
 *
 * The benchmark sends a code for anything it decided itself, and the raw text
 * of whatever failed for anything it did not. So a code that is not in this
 * table is shown as it came: an unrecognised failure is still a failure the
 * owner should see, and hiding it would be worse than showing it untranslated.
 */
export const RUN_PROBLEMS: Record<string, string> = {
  target_gone: 'The benchmark no longer has this endpoint on its list.',
  no_card:
    'No card could be assembled — there were no graded answers to report. Check the run itself above.',
  publish_refused: 'The card was measured but the Space would not take it',
  service_restarted: 'The benchmark restarted while this run was going. What it measured is kept.',
  // No longer produced: a trial run publishes on the same terms as a full one.
  // Kept so that jobs recorded before that still read as words, not as a code.
  trial_not_published: 'This was a trial run, so nothing was published.',
  no_questions:
    'There were no questions to ask. Either the freshness window let no document through, or the question set has not been built for this endpoint yet.',
  // No guess at the cause here. A spent key, a wrong model name, a network
  // that dropped and a node that is down all produce this one code, and a
  // guess printed beside it reads as a finding: a run refused with 400 for a
  // quoted model name was hunted in the network for an afternoon because this
  // line said the provider was probably down. The benchmark sends the text of
  // one failed call after the colon, and that is what tells them apart.
  nothing_graded:
    'The run went through the whole set and not one call came back with a verdict. Nothing was measured.',
  // The same rule as nothing_graded: no guess at the cause. Building the set
  // fails for the same reasons grading does, and the benchmark sends the text
  // of one refused call after the colon.
  nothing_generated:
    'Not one question could be built — every generator call was refused. The question set is unchanged.',
}

export function runProblemWords(problem: string): string {
  const exact = RUN_PROBLEMS[problem]
  if (exact) return exact
  // Some codes carry what actually failed after a colon: `publish_refused: 422
  // ...`, `nothing_graded: ERROR: ...`. The detail holds colons of its own, so
  // only the first one separates; the rest belong to the text.
  const [code = '', ...rest] = problem.split(':')
  const known = RUN_PROBLEMS[code.trim()]
  if (!known) return problem
  const detail = rest.join(':').trim()
  // The sentence ended where the code ended. With a detail following it, the
  // full stop is in the way of the colon that introduces it.
  return detail ? `${known.replace(/\.$/, '')}: ${detail}` : known
}

/**
 * What a pass is doing, in words.
 *
 * The benchmark sends the arm and the check as codes; an owner watching a run
 * needs to know what is being compared, not which enum value is current.
 */
export const ARMS: Record<string, string> = {
  closed_book: 'the model on its own',
  open_book: 'the endpoint answering as itself',
  model_with_context: 'the model with what the search returned',
}

export const BLOCKS: Record<string, string> = {
  direct: 'asked once',
  denial_loop: 'pushed back on',
  monte_carlo: 'repeated at several temperatures',
}

export const ARM_LETTERS: Record<string, string> = {
  closed_book: 'A',
  open_book: 'B',
  model_with_context: 'C',
}

export function armWords(arm: string): string {
  const letter = ARM_LETTERS[arm]
  const what = ARMS[arm] ?? arm
  return letter ? `Arm ${letter} — ${what}` : what
}

export function blockWords(block: string): string {
  return BLOCKS[block] ?? block
}
