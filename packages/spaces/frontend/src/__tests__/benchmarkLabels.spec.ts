import { describe, expect, it } from 'vitest'
import { RUN_PROBLEMS, runProblemWords } from '@/components/benchmark/labels'

describe('runProblemWords', () => {
  it('translates a bare code', () => {
    expect(runProblemWords('target_gone')).toBe(RUN_PROBLEMS.target_gone)
  })

  it('shows the failed call the benchmark sent after the code', () => {
    // Without this the owner is told only that nothing was graded, while the
    // line that says why — a model name the provider refuses, a spent key, a
    // node that is down — stays in the benchmark's database.
    const words = runProblemWords(
      'nothing_graded: ERROR: "qwen/qwen3.6-plus" -> 400: not a valid model ID',
    )
    expect(words).toContain('not a valid model ID')
    // The detail carries colons of its own; only the first one separates.
    expect(words).toContain('-> 400:')
    // The sentence ends where the code ends, and the full stop gives way to
    // the colon that introduces the detail.
    expect(words).not.toContain('measured.:')
  })

  it('guesses at no cause when it has none', () => {
    // Every failure of the rig produces this one code. A guess printed beside
    // it reads as a finding, and on a 400 from a live provider it sends the
    // search in the wrong direction.
    expect(RUN_PROBLEMS.nothing_graded).not.toMatch(/provider is down|usually/i)
  })

  it('shows a code it does not know rather than hiding it', () => {
    expect(runProblemWords('something_new')).toBe('something_new')
    expect(runProblemWords('something_new: with a detail')).toBe('something_new: with a detail')
  })
})
