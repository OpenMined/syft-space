import { describe, expect, it } from 'vitest'

import {
  KINDS,
  budgetFromChunks,
  buildRequest,
  chunksForBudget,
  companyOf,
  findClashes,
  formFromTarget,
  fromPercent,
  matchesFilters,
  modelName,
  monteCarloSkipped,
  parseNumberList,
  problemsOf,
  progressTitle,
  runProblemsOf,
  runSummary,
  sameRequest,
  storedRequest,
  takesTemperature,
  toPercent,
  toggleFilter,
  webSearchOf,
  windowDaysParam,
} from '@/components/benchmark/setup/setupForm'
import type { BenchmarkTarget } from '@/api/types'

const KEYS = KINDS.map((k) => k.key)

function makeTarget(over: Partial<BenchmarkTarget> = {}): BenchmarkTarget {
  return {
    endpoint_slug: 'news',
    measured: true,
    connection_id: 'c1',
    connection_name: 'Bench',
    enabled: true,
    collection: '',
    resolved_collection: 'Collection_news',
    probe: {},
    instrument: {},
    schedule: '',
    schedule_at: '',
    next_run_at: null,
    synced_at: null,
    fields: {},
    defaults: {
      probe: {
        dataset_mode: 'rolling',
        document_window_days: 1,
        dataset_max_pairs: 100,
        disabled_generators: [],
        chunks_per_run: 50,
        pairs_per_chunk: 2,
        min_chunk_chars: 400,
        generate_in_cycle: true,
        retrieval_top_k: 5,
        similarity_threshold: 0,
        endpoint_concurrency: 2,
        endpoint_max_tokens: 500,
      },
      instrument: {
        arms: ['closed_book', 'model_with_context'],
        blocks: ['direct', 'denial_loop', 'monte_carlo'],
        denial_rounds: 3,
        monte_carlo_temperatures: [0.3, 0.9],
        monte_carlo_trials: 3,
        context_source: 'endpoint_fragments',
        context_docs: 3,
        fragment_max_chars: 2000,
        answer_max_tokens: 8192,
        generator_model: 'anthropic/claude-opus-5',
        subject_models: ['x-ai/grok-4.6', 'qwen/qwen3.8-27b'],
        judge_model: 'google/gemini-3.1-pro-preview',
        judge_models: ['google/gemini-3.1-pro-preview', 'openai/gpt-5.1'],
        judge_policy: 'strict',
        key_facts_threshold: 0.7,
        answer_coverage_threshold: 0.6,
        consistency_floor: 0.5,
        text_metrics: [],
        extractive_mode: 'auto',
        methodology_profile: 'demosyft',
        max_consecutive_failures: 5,
        reuse_answers: true,
        audit_log: true,
      },
    },
    connection_probe: {},
    connection_instrument: {},
    capabilities: { generators: KEYS },
    last_job: null,
    reachable: true,
    detail: '',
    ...over,
  }
}

describe('companies and clashes', () => {
  it('reads the company from the vendor, else the id prefix, through the alias map', () => {
    expect(companyOf('x-ai/grok-4.6')).toBe('xai')
    expect(companyOf('xai/grok')).toBe('xai')
    expect(companyOf('meta-llama/llama-4')).toBe('meta')
    expect(companyOf('mistralai/large')).toBe('mistral')
    expect(companyOf('gemini/pro')).toBe('google')
    expect(companyOf('bytedance-seed/seed-2')).toBe('bytedance')
    expect(companyOf('whatever/model', 'OpenAI')).toBe('openai')
    expect(companyOf('no-slash')).toBe('')
  })

  it('pairs every judge with each tested model from the same company', () => {
    const clashes = findClashes(
      ['google/gemini-3.1-pro-preview', '', 'x-ai/grok-4.7'],
      ['x-ai/grok-4.6', 'gemini/flash', 'qwen/qwen3.8-27b'],
    )
    expect(clashes).toEqual([
      {
        judge: 0,
        judgeModel: 'google/gemini-3.1-pro-preview',
        model: 'gemini/flash',
        company: 'google',
      },
      { judge: 2, judgeModel: 'x-ai/grok-4.7', model: 'x-ai/grok-4.6', company: 'xai' },
    ])
  })

  it('finds no clash between different companies', () => {
    expect(findClashes(['openai/gpt-5.1'], ['x-ai/grok-4.6'])).toEqual([])
  })

  it('strips the vendor prefix from catalogue names', () => {
    expect(modelName('x-ai/grok-4.6', { name: 'SpaceXAI: Grok 4.6' })).toBe('Grok 4.6')
    expect(modelName('openai/gpt-5.1')).toBe('gpt-5.1')
  })
})

describe('write at most', () => {
  it('derives passages per run from the budget', () => {
    expect(chunksForBudget(1000, 2, 10)).toBe(50)
    expect(chunksForBudget(1000, 2, 9)).toBe(56)
    expect(chunksForBudget(1, 2, 10)).toBe(1)
    expect(chunksForBudget(0, 2, 10)).toBe(1)
  })

  it('shows the stored passage count back as a budget', () => {
    expect(budgetFromChunks(50, 2, 10)).toBe(1000)
    expect(budgetFromChunks(chunksForBudget(1000, 2, 10), 2, 10)).toBe(1000)
  })
})

describe('values on the page', () => {
  it('converts percentages both ways without float noise', () => {
    expect(toPercent(0.7)).toBe(70)
    expect(toPercent(0.55)).toBe(55)
    expect(fromPercent(70)).toBe(0.7)
    expect(fromPercent(toPercent(0.6))).toBe(0.6)
  })

  it('reads repeat settings text as a number list', () => {
    expect(parseNumberList('0.3, 0.9')).toEqual([0.3, 0.9])
    expect(parseNumberList('0.3,0.6 0.9')).toEqual([0.3, 0.6, 0.9])
    expect(parseNumberList('0.3, hot')).toBeNull()
    expect(parseNumberList(' ')).toBeNull()
  })

  it('shows effective values: endpoint layer, else connection, else defaults', () => {
    const target = makeTarget({
      connection_probe: { pairs_per_chunk: 3 },
      probe: { dataset_max_pairs: 40 },
      instrument: { judge_policy: 'recuse' },
    })
    const form = formFromTarget(target, KEYS)
    expect(form.pairsPerChunk).toBe(3)
    expect(form.keepAtMost).toBe(40)
    expect(form.windowDays).toBe(1)
    expect(form.writeAtMost).toBe(50 * 3 * 10)
    expect(form.answerCoverage).toBe(60)
    expect(form.judges).toEqual(['google/gemini-3.1-pro-preview', 'openai/gpt-5.1', ''])
    expect(form.judgeCount).toBe(2)
    // Only strict and warn are offered.
    expect(form.judgePolicy).toBe('strict')
  })

  it('a page left alone holds no changes', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    expect(sameRequest(buildRequest(target, form, KEYS), storedRequest(target))).toBe(true)
  })
})

describe('the save request', () => {
  it('maps reliability checks to blocks, direct always first', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.challenge = false
    expect(buildRequest(target, form, KEYS).instrument!.blocks).toEqual(['direct', 'monte_carlo'])
    form.repeat = false
    expect(buildRequest(target, form, KEYS).instrument!.blocks).toEqual(['direct'])
    form.challenge = true
    expect(buildRequest(target, form, KEYS).instrument!.blocks).toEqual(['direct', 'denial_loop'])
  })

  it('puts unticked kinds in disabled_generators and rescales chunks_per_run', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.disabledKinds = ['qa', 'mcq']
    form.writeAtMost = 1000
    const req = buildRequest(target, form, KEYS)
    // Benchmark order, not click order.
    expect(req.probe.disabled_generators).toEqual(['mcq', 'qa'])
    expect(req.probe.chunks_per_run).toBe(Math.ceil(1000 / (2 * 8)))
  })

  it('requires at least one kind ticked', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.disabledKinds = [...KEYS]
    expect(problemsOf(form, KEYS)).toContain('Tick at least one kind of question.')
  })

  it('writes judges in order, Judge 1 as judge_model', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.judgeCount = 3
    form.judges = ['openai/gpt-5.1', 'anthropic/claude-sonnet-5', 'google/gemini-3.1-pro-preview']
    const req = buildRequest(target, form, KEYS)
    expect(req.instrument!.judge_model).toBe('openai/gpt-5.1')
    expect(req.instrument!.judge_models).toEqual(form.judges)
    form.judgeCount = 1
    expect(buildRequest(target, form, KEYS).instrument!.judge_models).toEqual(['openai/gpt-5.1'])
  })

  it('stores percentages as shares and repeat settings as numbers', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.answerCoverage = 75
    form.consistencyFloor = 40
    form.keyFacts = 90
    form.repeatSettings = '0.2, 0.5, 1'
    const req = buildRequest(target, form, KEYS)
    expect(req.instrument!.answer_coverage_threshold).toBe(0.75)
    expect(req.instrument!.consistency_floor).toBe(0.4)
    expect(req.instrument!.key_facts_threshold).toBe(0.9)
    expect(req.instrument!.monte_carlo_temperatures).toEqual([0.2, 0.5, 1])
  })

  it('sends the web check model and keeps fixed values', () => {
    const target = makeTarget({
      instrument: { arms: ['closed_book', 'open_book'], audit_log: false },
    })
    const form = formFromTarget(target, KEYS)
    form.webCheckModel = 'openai/gpt-5.1'
    const req = buildRequest(target, form, KEYS)
    expect(req.instrument!.filter_model).toBe('openai/gpt-5.1')
    // Equal to the inherited fixed values, so taken out of the endpoint layer.
    expect(req.instrument!.arms).toBeUndefined()
    expect(req.instrument!.audit_log).toBeUndefined()
  })

  it('writes fixed values when the layer above disagrees', () => {
    const target = makeTarget()
    target.defaults.instrument!.methodology_profile = 'omsyft'
    target.defaults.instrument!.judge_policy = 'recuse'
    const req = buildRequest(target, formFromTarget(target, KEYS), KEYS)
    expect(req.instrument!.methodology_profile).toBe('demosyft')
    expect(req.instrument!.judge_policy).toBe('strict')
  })

  it('keeps keys the page does not manage and drops the hour off a non-daily schedule', () => {
    const target = makeTarget({ probe: { endpoint_max_tokens: 900 }, schedule_at: '03:00' })
    const form = formFromTarget(target, KEYS)
    form.schedule = '6h'
    const req = buildRequest(target, form, KEYS)
    expect(req.probe.endpoint_max_tokens).toBe(900)
    expect(req.schedule).toBe('6h')
    expect(req.schedule_at).toBe('')
    expect(req).not.toHaveProperty('limit')
  })
})

describe('summary and articles', () => {
  it('builds the summary line from page values', () => {
    const form = formFromTarget(makeTarget(), KEYS)
    expect(runSummary(form, 9)).toBe(
      '9 articles · up to 1000 questions written, 100 kept · 2 models · 2 judges',
    )
    expect(runSummary(form, null)).toBe(
      'up to 1000 questions written, 100 kept · 2 models · 2 judges',
    )
  })

  it('asks for the window on the page, or the saved one when it is not a day count', () => {
    expect(windowDaysParam(1)).toBe(1)
    expect(windowDaysParam(0)).toBe(0)
    expect(windowDaysParam('3')).toBe(3)
    expect(windowDaysParam('')).toBeUndefined()
    expect(windowDaysParam(-1)).toBeUndefined()
    expect(windowDaysParam(1.5)).toBeUndefined()
  })
})

describe('web search settings', () => {
  it('reads the benchmark defaults when no layer sets them', () => {
    const form = formFromTarget(makeTarget(), KEYS)
    expect(form.webAlone).toBe(true)
    expect(form.webWithData).toBe(false)
    expect(form.webWriter).toBe(false)
    expect(form.webJudges).toBe(false)
    expect(form.webEngine).toBe('auto')
    expect(form.webMaxResults).toBe(5)
    expect(form.webCheckJudge).toBe('')
  })

  it('a page left alone writes no web fields, with or without them in the defaults', () => {
    const bare = makeTarget()
    expect(buildRequest(bare, formFromTarget(bare, KEYS), KEYS).instrument).not.toHaveProperty(
      'web_search_closed_book',
    )
    const withDefaults = makeTarget()
    Object.assign(withDefaults.defaults.instrument!, {
      web_search_engine: 'auto',
      web_search_closed_book: true,
      web_search_with_context: false,
      web_search_generator: false,
      web_search_judge: false,
      web_search_max_results: 5,
      filter_judge_model: null,
    })
    const form = formFromTarget(withDefaults, KEYS)
    expect(sameRequest(buildRequest(withDefaults, form, KEYS), storedRequest(withDefaults))).toBe(
      true,
    )
  })

  it('maps every toggle to its flat instrument field', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.webAlone = false
    form.webWithData = true
    form.webWriter = true
    form.webJudges = true
    form.webEngine = 'plugin'
    form.webMaxResults = 8
    form.webCheckJudge = 'openai/gpt-5.1'
    expect(buildRequest(target, form, KEYS).instrument).toMatchObject({
      web_search_closed_book: false,
      web_search_with_context: true,
      web_search_generator: true,
      web_search_judge: true,
      web_search_engine: 'plugin',
      web_search_max_results: 8,
      filter_judge_model: 'openai/gpt-5.1',
    })
  })

  it('clamps results per search to 1..20 and drops an unknown engine', () => {
    const target = makeTarget({ instrument: { web_search_engine: 'exa' } })
    const form = formFromTarget(target, KEYS)
    expect(form.webEngine).toBe('auto')
    form.webMaxResults = 50
    expect(buildRequest(target, form, KEYS).instrument!.web_search_max_results).toBe(20)
    form.webMaxResults = 0
    expect(buildRequest(target, form, KEYS).instrument!.web_search_max_results).toBe(1)
  })

  it('clears the web check judge back to Judge 1', () => {
    const target = makeTarget({ instrument: { filter_judge_model: 'openai/gpt-5.1' } })
    const form = formFromTarget(target, KEYS)
    expect(form.webCheckJudge).toBe('openai/gpt-5.1')
    form.webCheckJudge = ''
    expect(buildRequest(target, form, KEYS).instrument).not.toHaveProperty('filter_judge_model')
  })
})

describe('web check gate and speed', () => {
  it('reads the benchmark defaults when no layer sets them', () => {
    const form = formFromTarget(makeTarget(), KEYS)
    expect(form.manualPriority).toBe('filter')
    expect(form.modelConcurrency).toBe(16)
    expect(form.endpointConcurrency).toBe(2)
  })

  it('a page left alone writes neither field, with or without them in the defaults', () => {
    const bare = makeTarget()
    const req = buildRequest(bare, formFromTarget(bare, KEYS), KEYS)
    expect(req.instrument).not.toHaveProperty('manual_status_priority')
    expect(req.instrument).not.toHaveProperty('concurrency')
    const withDefaults = makeTarget()
    Object.assign(withDefaults.defaults.instrument!, {
      manual_status_priority: 'filter',
      concurrency: 16,
    })
    const form = formFromTarget(withDefaults, KEYS)
    expect(sameRequest(buildRequest(withDefaults, form, KEYS), storedRequest(withDefaults))).toBe(
      true,
    )
  })

  it('maps the hand-returned rule and model requests to instrument fields', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.manualPriority = 'manual'
    form.modelConcurrency = 32
    form.endpointConcurrency = 4
    const req = buildRequest(target, form, KEYS)
    expect(req.instrument).toMatchObject({ manual_status_priority: 'manual', concurrency: 32 })
    expect(req.probe.endpoint_concurrency).toBe(4)
  })

  it('reads an unknown rule as the web check deciding, and clamps requests to 1..64', () => {
    const target = makeTarget({ instrument: { manual_status_priority: 'other', concurrency: 8 } })
    const form = formFromTarget(target, KEYS)
    expect(form.manualPriority).toBe('filter')
    expect(form.modelConcurrency).toBe(8)
    form.modelConcurrency = 500
    expect(buildRequest(target, form, KEYS).instrument!.concurrency).toBe(64)
    form.modelConcurrency = 0
    expect(buildRequest(target, form, KEYS).instrument!.concurrency).toBe(1)
  })

  it('saves without a web check model but does not run', () => {
    const form = formFromTarget(makeTarget(), KEYS)
    expect(form.webCheckModel).toBe('')
    expect(problemsOf(form, KEYS)).toEqual([])
    expect(runProblemsOf(form)).toEqual(['Choose a web check model.'])
    form.webCheckModel = 'openai/gpt-5.1'
    expect(runProblemsOf(form)).toEqual([])
  })
})

describe('a run in progress', () => {
  const job = {
    state: 'running' as const,
    phase: 'evaluate',
    message: '',
    step_done: 3,
    step_total: 10,
  }

  it('shows the step, or the job message while writing questions', () => {
    expect(progressTitle(job)).toBe('Running now · step 3 of 10')
    expect(progressTitle({ ...job, state: 'queued' })).toBe('Queued · starts shortly')
    expect(
      progressTitle({
        ...job,
        phase: 'generate',
        message: 'written 12 · checked 8 · removed 3',
        step_total: 0,
      }),
    ).toBe('Running now · written 12 · checked 8 · removed 3')
    expect(progressTitle({ ...job, phase: 'generate', step_total: 0 })).toBe('Running now')
    expect(progressTitle({ ...job, message: 'something else' })).toBe('Running now · step 3 of 10')
  })
})

describe('model capabilities', () => {
  const native = { supports: ['temperature'], web_search: 'native' as const }
  const plugin = { supports: ['temperature'], web_search: 'plugin' as const }
  const noTemp = { supports: ['tools'], web_search: 'plugin' as const }
  const legacy = { supports: [] }

  it('reads web search and temperature, assuming temperature when unknown', () => {
    expect(webSearchOf(native)).toBe('native')
    expect(webSearchOf(legacy)).toBe('none')
    expect(takesTemperature(noTemp)).toBe(false)
    expect(takesTemperature(legacy)).toBe(true)
    expect(takesTemperature(undefined)).toBe(true)
  })

  it('filters by built-in search and temperature', () => {
    const all = [native, plugin, noTemp, legacy]
    expect(all.filter((m) => matchesFilters(m, ['web']))).toEqual([native])
    expect(all.filter((m) => matchesFilters(m, ['no-web']))).toEqual([plugin, noTemp, legacy])
    expect(all.filter((m) => matchesFilters(m, ['no-temperature']))).toEqual([noTemp])
    expect(all.filter((m) => matchesFilters(m, ['no-web', 'temperature']))).toEqual([
      plugin,
      legacy,
    ])
    expect(all.filter((m) => matchesFilters(m, []))).toEqual(all)
  })

  it('keeps one chip of each pair on', () => {
    expect(toggleFilter([], 'web')).toEqual(['web'])
    expect(toggleFilter(['web', 'temperature'], 'no-web')).toEqual(['temperature', 'no-web'])
    expect(toggleFilter(['web'], 'web')).toEqual([])
  })

  it('notes tested models that skip Monte Carlo, only while repeats are on', () => {
    const entries: Record<string, { supports: string[] }> = {
      'openai/o5': { supports: ['tools'] },
      'x-ai/grok-4.6': { supports: ['temperature'] },
    }
    const form = { repeat: true, models: ['openai/o5', 'x-ai/grok-4.6', 'new/unknown'] }
    expect(monteCarloSkipped(form, (id) => entries[id])).toEqual(['openai/o5'])
    expect(monteCarloSkipped({ ...form, repeat: false }, (id) => entries[id])).toEqual([])
  })

  it('adds the skipped models to the summary', () => {
    const form = formFromTarget(makeTarget(), KEYS)
    expect(runSummary(form, null, ['o5'])).toBe(
      'up to 1000 questions written, 100 kept · 2 models · 2 judges · Monte Carlo skipped: o5',
    )
  })
})

describe('judge settings', () => {
  it('reads the benchmark defaults: temperature 0, low reasoning', () => {
    const form = formFromTarget(makeTarget(), KEYS)
    expect(form.judgeTemperature).toBe(0)
    expect(form.judgeReasoning).toBe('low')
  })

  it('a page left alone writes neither field, with or without them in the defaults', () => {
    const bare = makeTarget()
    const req = buildRequest(bare, formFromTarget(bare, KEYS), KEYS)
    expect(req.instrument).not.toHaveProperty('judge_temperature')
    expect(req.instrument).not.toHaveProperty('judge_reasoning_effort')
    const withDefaults = makeTarget()
    Object.assign(withDefaults.defaults.instrument!, {
      judge_temperature: 0,
      judge_reasoning_effort: 'low',
    })
    const form = formFromTarget(withDefaults, KEYS)
    expect(sameRequest(buildRequest(withDefaults, form, KEYS), storedRequest(withDefaults))).toBe(
      true,
    )
  })

  it('maps temperature and reasoning to instrument fields, clamping to 0..2', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.judgeTemperature = 0.5
    form.judgeReasoning = 'default'
    expect(buildRequest(target, form, KEYS).instrument).toMatchObject({
      judge_temperature: 0.5,
      judge_reasoning_effort: 'default',
    })
    form.judgeTemperature = 7
    expect(buildRequest(target, form, KEYS).instrument!.judge_temperature).toBe(2)
  })

  it('stores an empty temperature as the model default, and reads it back as empty', () => {
    const target = makeTarget()
    const form = formFromTarget(target, KEYS)
    form.judgeTemperature = NaN
    const req = buildRequest(target, form, KEYS)
    expect(req.instrument!.judge_temperature).toBe('default')
    const saved = makeTarget({ instrument: req.instrument! })
    expect(formFromTarget(saved, KEYS).judgeTemperature).toBeNaN()
    expect(
      sameRequest(buildRequest(saved, formFromTarget(saved, KEYS), KEYS), storedRequest(saved)),
    ).toBe(true)
  })

  it('writes a default value back when a higher layer set another one', () => {
    const target = makeTarget({
      connection_instrument: { judge_temperature: 1, judge_reasoning_effort: 'high' },
    })
    const form = formFromTarget(target, KEYS)
    expect(form.judgeTemperature).toBe(1)
    expect(form.judgeReasoning).toBe('high')
    form.judgeTemperature = 0
    form.judgeReasoning = 'low'
    expect(buildRequest(target, form, KEYS).instrument).toMatchObject({
      judge_temperature: 0,
      judge_reasoning_effort: 'low',
    })
  })

  it('reads an unknown reasoning effort as low', () => {
    const target = makeTarget({ instrument: { judge_reasoning_effort: 'extreme' } })
    expect(formFromTarget(target, KEYS).judgeReasoning).toBe('low')
  })
})
