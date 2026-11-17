/** The kinds of question, in the order the benchmark runs them: the one source of their names. */

interface Kind {
  key: string
  label: string
  /** One line under the kind's checkbox on the setup tab. */
  help: string
  /** What the kind asks the model to do, for the report. */
  description: string
}

export const KINDS: Kind[] = [
  {
    key: 'named_entity_masking',
    label: 'Names',
    help: 'Fill in a missing name.',
    description: 'Fill in a missing name in a sentence from your article.',
  },
  {
    key: 'numeric_masking',
    label: 'Numbers',
    help: 'Fill in a missing figure.',
    description: 'Fill in a missing figure.',
  },
  {
    key: 'temporal_masking',
    label: 'Dates',
    help: 'Fill in a missing date.',
    description: 'Fill in a missing date.',
  },
  {
    key: 'mcq',
    label: 'Multiple choice',
    help: 'Pick the right answer from four.',
    description: 'Pick the right answer from four.',
  },
  {
    key: 'two_truths_one_lie',
    label: 'Spotting a false claim',
    help: 'Find the false statement among three.',
    description: 'Find the one false statement among three.',
  },
  {
    key: 'multihop_synthesis',
    label: 'Connecting facts',
    help: 'Combine facts from different parts of a story.',
    description: 'Combine facts from different parts of a story.',
  },
  {
    key: 'tiered_explanation',
    label: 'Explaining a story simply',
    help: 'Explain it for a young reader.',
    description:
      'Explain a story simply. Graded on its key facts; anything the story doesn’t support counts as hallucinated.',
  },
  {
    key: 'qa',
    label: 'Open questions',
    help: 'Answer a direct question in a sentence.',
    description: 'Answer a direct question in a sentence.',
  },
  {
    key: 'unanswerable_property',
    label: 'Trick questions',
    help: 'Ask for a detail that isn’t there.',
    description:
      'Ask for a detail your reporting does not contain. The right response is “I don’t know”.',
  },
  {
    key: 'false_premise',
    label: 'Questions with a false premise',
    help: 'Assume something that didn’t happen.',
    description: 'Notice that the question assumes something that did not happen.',
  },
]

const BY_KEY = new Map(KINDS.map((kind) => [kind.key, kind]))

/** `some_code` -> `Some code`. */
function humanise(name: string): string {
  const spaced = name.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** The kind's name; an unknown key is shown humanised. */
export function kindLabel(generator: string): string {
  return BY_KEY.get(generator)?.label ?? humanise(generator)
}

/** The kind's line under its checkbox on the setup tab; empty for an unknown key. */
export function kindHelp(generator: string): string {
  return BY_KEY.get(generator)?.help ?? ''
}

/** What the kind asks the model to do; empty for an unknown key. */
export function kindDescription(generator: string): string {
  return BY_KEY.get(generator)?.description ?? ''
}
