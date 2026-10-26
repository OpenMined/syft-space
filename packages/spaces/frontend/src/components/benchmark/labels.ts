/** Display words for the benchmark's codes: generators, arms, blocks. */

export interface Words {
  label: string
}

/** Generator names; an unknown key is shown humanised. */
export const GENERATORS: Record<string, Words> = {
  mcq: { label: 'Multiple choice' },
  qa: { label: 'Open question' },
  two_truths_one_lie: { label: 'Two truths, one lie' },
  multihop_synthesis: { label: 'Multi-hop' },
  tiered_explanation: { label: 'Tiered explanation' },
  named_entity_masking: { label: 'Named entity' },
  numeric_masking: { label: 'Number' },
  temporal_masking: { label: 'Date' },
  unanswerable_property: { label: 'Unanswerable' },
  false_premise: { label: 'False premise' },
}

export function generatorWords(key: string): Words {
  return GENERATORS[key] ?? { label: humanise(key) }
}

/** What picking an option at random scores: one over the options. */
export const GUESS_RATE: Record<string, number> = {
  mcq: 1 / 4,
  two_truths_one_lie: 1 / 3,
}

export const GUESS_TIP = 'What picking an option at random would score.'

/** "guess 25%" for a kind answered by picking an option; null otherwise. */
export function guessText(generator: string): string | null {
  const rate = GUESS_RATE[generator]
  return rate === undefined ? null : `guess ${Math.round(rate * 100)}%`
}

/** A model name without its vendor prefix: `openai/gpt-4.1` -> `gpt-4.1`. */
export function shortModel(name: string): string {
  const cut = name.lastIndexOf('/')
  return cut === -1 ? name : name.slice(cut + 1)
}

/** `some_code` -> `Some code`. */
export function humanise(name: string): string {
  const spaced = name.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** What a pass compares, in words. */
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

/** Arm names for answer tiles. */
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

/** Short check codes for narrow column headings. */
export const BLOCK_CODES: Record<string, string> = {
  direct: 'D',
  denial_loop: 'DL',
  monte_carlo: 'MC',
}

export function blockCode(block: string): string {
  return BLOCK_CODES[block] ?? block
}
