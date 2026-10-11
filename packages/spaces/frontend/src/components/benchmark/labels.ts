/**
 * Words for what the benchmark describes by code: generators, arms, blocks,
 * run problems.
 *
 * The benchmark sends codes — never prose. The wording belongs to whoever
 * renders it, in his reader's language. This file is that wording for this
 * Space. A generator with no entry here is shown humanised.
 */

export interface Words {
  label: string
  help?: string
}

/**
 * What each generator builds.
 *
 * The benchmark names its generators; this is the one-line explanation of
 * what each produces, so switching one off is an informed choice rather than
 * a guess from the key alone.
 */
export const GENERATORS: Record<string, Words> = {
  mcq: {
    label: 'Multiple choice',
    help: 'Four options, one correct. The gold answer is the option itself, not a letter chosen ahead of time — options are shuffled per question.',
  },
  qa: {
    label: 'Open question',
    help: 'A free-form question with a written reference answer, taken from a single fragment.',
  },
  two_truths_one_lie: {
    label: 'Two truths, one lie',
    help: 'Three statements about the fragment, one of them knowingly false.',
  },
  multihop_synthesis: {
    label: 'Multi-hop',
    help: 'Answerable only by connecting facts from more than one part of the document — a single fragment will not do.',
  },
  tiered_explanation: {
    label: 'Tiered explanation',
    help: 'The same fact explained at a different level of the reader — a child, a professional, an expert. Judged by which facts survive, not by wording.',
  },
  named_entity_masking: {
    label: 'Named entity',
    help: 'A named entity blanked out of a sentence lifted verbatim from the document.',
  },
  numeric_masking: {
    label: 'Number',
    help: 'A number blanked out of a sentence lifted verbatim from the document.',
  },
  temporal_masking: {
    label: 'Date',
    help: 'A date blanked out of a sentence lifted verbatim from the document.',
  },
  unanswerable_property: {
    label: 'Unanswerable',
    help: 'The control half: no answer exists anywhere in the corpus. The correct behaviour is to say so, not to invent one.',
  },
  false_premise: {
    label: 'False premise',
    help: 'The control half: the question assumes something untrue. The correct behaviour is to correct it, not answer it as asked.',
  },
}

export function generatorWords(key: string): Words {
  return GENERATORS[key] ?? { label: humanise(key) }
}

/**
 * A model's own name, without the house that serves it.
 *
 * `openai/gpt-4.1` reads as `gpt-4.1`. The vendor matters where independence
 * is decided — a grader from the same house as a model under test is a
 * conflict of interest — and nowhere in a list of verdicts, where it is the
 * same prefix repeated down the page.
 */
export function shortModel(name: string): string {
  const cut = name.lastIndexOf('/')
  return cut === -1 ? name : name.slice(cut + 1)
}

/** What to call a code nobody has written words for yet. */
export function humanise(name: string): string {
  const spaced = name.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
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
  // Kept for jobs recorded while a trial run withheld publishing, so those
  // records still read as words, not as a code.
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
    'Not one question could be built — every generator call was refused. The question set is unchanged.',}

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

/**
 * The arms as the difference they make, not as their place in the methodology.
 *
 * "Arm A" and "Arm C" are the right names in a report, where the letters are
 * defined on the page and the same three comparisons recur in a fixed order. In
 * front of one answer they are a lookup the reader has to perform to understand
 * what he is looking at, and the thing he is looking up — did the model have the
 * endpoint's material or not — is the whole point of the comparison.
 */
export const ARM_TILES: Record<string, string> = {
  closed_book: 'Without data',
  open_book: "The endpoint's own answer",
  model_with_context: 'With data',
}

export function armTileWords(arm: string): string {
  return ARM_TILES[arm] ?? arm
}

export const BLOCKS_BRIEF: Record<string, string> = {
  direct: 'asked once',
  denial_loop: 'pushed back on',
  monte_carlo: 'repeated',
}

export function blockBrief(block: string): string {
  return BLOCKS_BRIEF[block] ?? block
}

/**
 * The checks as column headings, where there is room for two letters.
 *
 * A table of judges against checks is read down its columns, and a heading as
 * wide as its cells would set the width of the whole thing. The words are on
 * hover, where a reader who does not know the codes looks.
 */
export const BLOCK_CODES: Record<string, string> = {
  direct: 'D',
  denial_loop: 'DL',
  monte_carlo: 'MC',
}

export function blockCode(block: string): string {
  return BLOCK_CODES[block] ?? block
}
