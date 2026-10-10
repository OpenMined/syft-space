<template>
  <div v-if="loading" class="space-y-3">
    <Skeleton class="h-28 w-full" />
  </div>

  <!-- No benchmark is wired to this Space, or this endpoint is not opted in. -->
  <section
    v-else-if="!target?.connection_id && !target?.measured"
    class="rounded-lg border border-border/50 p-6 text-center"
  >
    <Gauge class="mx-auto mb-3 h-7 w-7 text-muted-foreground/50" />
    <h3 class="mb-1 text-sm font-medium text-foreground">
      {{ hasBenchmark ? 'This endpoint is not measured' : 'No benchmark is connected' }}
    </h3>
    <p class="mx-auto mb-4 max-w-md text-xs text-muted-foreground">
      <template v-if="hasBenchmark">
        Nothing is grading this endpoint yet. Turn it on to set up the benchmark.
      </template>
      <template v-else>
        Measuring is a separate service, and this Space is not wired to one yet.
      </template>
    </p>
    <Button v-if="hasBenchmark" size="sm" :disabled="saving" @click="startMeasuring">
      <Play class="mr-1.5 h-4 w-4" />
      Measure this endpoint
    </Button>
    <Button v-else size="sm" variant="outline" @click="router.push({ name: 'benchmark' })">
      Connect a benchmark
    </Button>
  </section>

  <!-- The negative bottom margin eats the page's bottom padding, so the bar ends flush with the page. -->
  <div
    v-else-if="target && form"
    class="-mb-10 flex flex-col gap-6 lg:-mb-12"
    data-testid="benchmark-setup"
  >
    <div class="space-y-0.5">
      <h1 class="text-xl font-semibold text-foreground">Benchmark setup</h1>
      <p class="max-w-[780px] text-sm text-muted-foreground">
        How we measure what your reporting adds to AI models. Every run follows the five steps
        below.
      </p>
    </div>

    <div
      v-if="activeJob"
      class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-primary bg-primary/5 px-3.5 py-2.5 text-sm text-primary"
    >
      <b class="font-semibold">A run is in progress</b>
      <span>Settings are locked until it finishes.</span>
    </div>
    <div
      v-else-if="lastRun"
      class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-border bg-muted/30 px-3.5 py-2.5 text-sm"
      data-testid="last-run"
    >
      <span>
        <span class="text-muted-foreground">Last run</span> ·
        {{ dayTime(utcStamp(lastRun.created_at)) }} ·
        {{ plural(lastRun.questions ?? 0, 'question') }} ·
        {{ plural(lastRun.models.length, 'model') }}
      </span>
      <RouterLink
        :to="runLocation(lastRun.job_id)"
        class="font-medium text-primary hover:underline"
      >
        See its results
      </RouterLink>
    </div>

    <div
      v-if="!target.enabled"
      class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 px-3.5 py-2.5 text-sm"
    >
      <span>Measuring is stopped for this endpoint. Settings and past runs are kept.</span>
      <Button size="sm" variant="outline" :disabled="saving || locked" @click="setMeasuring(true)">
        Resume measuring
      </Button>
    </div>

    <fieldset :disabled="locked" class="m-0 flex min-w-0 flex-col gap-4 border-0 p-0">
      <legend class="sr-only">Benchmark settings</legend>

      <!-- Step 1 -->
      <SetupStep
        id="bm-articles"
        :step="1"
        title="Your articles"
        description="Each run uses the articles added to your Syft Space in the 24 hours before it starts."
      >
        <div
          class="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-md border border-border bg-muted/30 px-3.5 py-3 text-sm"
        >
          <div class="flex flex-wrap gap-x-6 gap-y-2">
            <span>
              <span class="text-muted-foreground">Data source</span> · {{ sourceLabel }}
            </span>
            <span v-if="articles !== null" data-testid="articles-in-window">
              <span class="text-muted-foreground">{{ windowLabel }}</span> ·
              {{ plural(articles, 'article') }}
              <span
                v-if="form.datasetMode === 'incremental'"
                class="text-muted-foreground"
                title="Earlier runs’ questions stay in the set."
                data-testid="articles-earlier"
                >+ earlier questions</span
              >
            </span>
          </div>
          <RouterLink
            v-if="dataset"
            :to="{ name: 'dataset-detail', params: { slug: dataset.name } }"
            class="font-medium text-primary hover:underline"
          >
            Manage data source
          </RouterLink>
        </div>
        <p class="text-xs text-muted-foreground">
          Connect a source such as WordPress to add new articles automatically, or upload files by
          hand.
        </p>

        <template #advanced>
          <SettingRow
            label="Time window"
            help="1 means articles added in the last 24 hours."
            unit="days"
            for-id="bm-window"
          >
            <NumberInput id="bm-window" v-model="form.windowDays" :min="0" />
          </SettingRow>
          <SettingRow
            label="How the question set changes"
            help="Rolling is right for news: each run uses only the newest articles."
            for-id="bm-mode"
          >
            <ChoiceSelect id="bm-mode" v-model="form.datasetMode" :choices="DATASET_MODES" />
          </SettingRow>
          <SettingRow
            label="Write new questions before each run"
            help="Turn off only if questions are added another way."
            for-id="bm-cycle"
          >
            <Checkbox id="bm-cycle" v-model="form.generateInCycle" />
            <span class="text-sm">On</span>
          </SettingRow>
          <SettingRow
            label="Index collection"
            help="Worked out from your data. Fill in only if that turns out wrong."
            for-id="bm-collection"
          >
            <Input
              id="bm-collection"
              v-model="form.collection"
              :placeholder="target.resolved_collection || 'Automatic'"
              class="w-70"
            />
          </SettingRow>
        </template>
      </SetupStep>

      <!-- Step 2 -->
      <SetupStep
        id="bm-write"
        :step="2"
        title="Write questions"
        description="An AI model running inside your Syft Space reads every article and writes a few questions from each passage, each with one right answer taken from your reporting. A busy news day gives more questions; a quiet one gives fewer."
      >
        <div class="flex flex-wrap gap-4">
          <div class="flex flex-[0_1_320px] flex-col gap-1">
            <Label for="bm-writer" class="text-xs font-medium text-muted-foreground">
              Question writer
            </Label>
            <ModelPicker
              :model-value="form.writer"
              trigger-id="bm-writer"
              :connection-id="connectionId"
              @update:model-value="(v) => (form!.writer = asString(v))"
            />
          </div>
          <div class="flex flex-[0_1_260px] flex-col gap-1">
            <Label for="bm-write-max" class="text-xs font-medium text-muted-foreground">
              Write at most
            </Label>
            <span class="flex items-center gap-2">
              <NumberInput id="bm-write-max" v-model="form.writeAtMost" :min="1" />
              <span class="text-sm text-muted-foreground">questions</span>
            </span>
            <span class="text-xs text-muted-foreground"
              >A limit for busy news days, not a target.</span
            >
          </div>
        </div>

        <fieldset class="m-0 flex flex-col gap-2 border-0 p-0">
          <legend class="mb-2 p-0 text-xs font-medium text-muted-foreground">
            Kinds of question · {{ kindsOn }} of {{ kindList.length }}
          </legend>
          <div class="grid gap-x-6 gap-y-1 sm:grid-cols-2">
            <label
              v-for="kind in kindList"
              :key="kind.key"
              class="flex cursor-pointer items-start gap-2.5 py-1.5"
            >
              <Checkbox
                class="mt-0.5"
                :model-value="!form.disabledKinds.includes(kind.key)"
                @update:model-value="(on) => setKind(kind.key, on === true)"
              />
              <span class="flex flex-col">
                <span class="text-sm font-medium">{{ kind.label }}</span>
                <span v-if="kind.help" class="text-xs text-muted-foreground">{{ kind.help }}</span>
              </span>
            </label>
          </div>
        </fieldset>

        <template #advanced>
          <SettingRow
            label="Questions per passage"
            help="Keep this low. Asking for more from one passage gives weaker questions."
            for-id="bm-ppc"
          >
            <NumberInput id="bm-ppc" v-model="form.pairsPerChunk" :min="1" />
          </SettingRow>
          <SettingRow
            label="Shortest usable passage"
            help="Shorter passages are skipped."
            unit="characters"
            for-id="bm-min-chunk"
          >
            <NumberInput id="bm-min-chunk" v-model="form.minChunkChars" :min="0" :step="50" />
          </SettingRow>
          <SettingRow
            label="How blanks are cut"
            help="For fill-in-the-blank questions."
            for-id="bm-extractive"
          >
            <ChoiceSelect
              id="bm-extractive"
              v-model="form.extractiveMode"
              :choices="EXTRACTIVE_MODES"
            />
          </SettingRow>
          <SettingRow
            label="Answer words found in the passage"
            help="A question is dropped if less of its answer appears in the passage."
            unit="%"
            for-id="bm-coverage"
          >
            <NumberInput
              id="bm-coverage"
              v-model="form.answerCoverage"
              :min="0"
              :max="100"
              :step="5"
            />
          </SettingRow>
          <SettingRow
            label="Question writer searches the web"
            help="Off keeps the writer to your articles."
            for-id="bm-web-writer"
          >
            <Checkbox id="bm-web-writer" v-model="form.webWriter" />
            <span class="text-sm">On</span>
          </SettingRow>
        </template>
      </SetupStep>

      <!-- Step 3 -->
      <SetupStep
        id="bm-web"
        :step="3"
        title="Remove what the web already knows"
        description="A model with web search tries every question. Any question it can answer is removed, so what’s left can only be answered from your reporting."
      >
        <div class="flex flex-wrap gap-4">
          <div class="flex flex-[0_1_320px] flex-col gap-1">
            <Label for="bm-checker" class="text-xs font-medium text-muted-foreground">
              Web check model
            </Label>
            <ModelPicker
              :model-value="form.webCheckModel"
              trigger-id="bm-checker"
              :connection-id="connectionId"
              placeholder="Choose a model"
              @update:model-value="(v) => (form!.webCheckModel = asString(v))"
            />
            <span class="text-xs text-muted-foreground">
              Answers each question using its own web search.
            </span>
          </div>
          <div class="flex flex-[0_1_300px] flex-col gap-1">
            <Label for="bm-keep" class="text-xs font-medium text-muted-foreground">
              Keep at most
            </Label>
            <span class="flex items-center gap-2">
              <NumberInput id="bm-keep" v-model="form.keepAtMost" :min="0" />
              <span class="text-sm text-muted-foreground">questions</span>
            </span>
            <span class="text-xs text-muted-foreground">
              If more survive the web check, an even mix across kinds is kept.
            </span>
          </div>
          <div class="flex flex-[0_1_320px] flex-col gap-1">
            <Label for="bm-check-judge" class="text-xs font-medium text-muted-foreground">
              Web check judge
            </Label>
            <ModelPicker
              :model-value="form.webCheckJudge"
              trigger-id="bm-check-judge"
              :connection-id="connectionId"
              :placeholder="judgeOneLabel"
              @update:model-value="(v) => (form!.webCheckJudge = asString(v))"
            />
            <span class="text-xs text-muted-foreground">
              Decides whether the web answer is right.
              <button
                v-if="form.webCheckJudge"
                type="button"
                class="font-medium text-primary hover:underline"
                @click="form!.webCheckJudge = ''"
              >
                Use Judge 1
              </button>
            </span>
          </div>
        </div>

        <template #advanced>
          <SettingRow
            label="When you return a question by hand"
            tip="Whether the web check may remove it again."
            for-id="bm-manual-priority"
          >
            <ChoiceSelect
              id="bm-manual-priority"
              v-model="form.manualPriority"
              :choices="MANUAL_PRIORITIES"
            />
          </SettingRow>
        </template>
      </SetupStep>

      <!-- Step 4 -->
      <SetupStep
        id="bm-ask"
        :step="4"
        title="Ask the models"
        description="Each model answers every question twice: on its own, and with excerpts from your archive. The difference is what your data adds."
      >
        <div class="flex flex-col gap-1.5">
          <Label for="bm-models" class="text-xs font-medium text-muted-foreground">
            Models to test
          </Label>
          <ModelPicker
            :model-value="form.models"
            multiple
            trigger-id="bm-models"
            add-label="Add a model…"
            placeholder="Add a model…"
            :connection-id="connectionId"
            @update:model-value="(v) => (form!.models = asList(v))"
          />
          <span
            v-for="id in skippedRepeats"
            :key="id"
            class="text-xs text-amber-800 dark:text-amber-300"
            data-testid="no-temperature-note"
            title="Takes no temperature setting."
          >
            {{ nameOf(id) }} · Monte Carlo skipped
          </span>
        </div>
        <fieldset class="m-0 flex flex-col gap-1.5 border-0 p-0">
          <legend class="mb-1.5 p-0 text-xs font-medium text-muted-foreground">
            Search the web
          </legend>
          <label class="flex cursor-pointer items-start gap-2.5">
            <Checkbox v-model="form.webAlone" class="mt-0.5" />
            <span class="flex flex-col">
              <span class="text-sm font-medium">On its own</span>
              <span class="text-xs text-muted-foreground">
                The model may search the web when it answers without your data.
              </span>
            </span>
          </label>
          <label class="flex cursor-pointer items-start gap-2.5">
            <Checkbox v-model="form.webWithData" class="mt-0.5" />
            <span class="flex flex-col">
              <span class="text-sm font-medium">With your data</span>
              <span class="text-xs text-muted-foreground">
                The model may also search the web when it has your excerpts.
              </span>
            </span>
          </label>
        </fieldset>
        <fieldset class="m-0 flex flex-col gap-1.5 border-0 p-0">
          <legend class="mb-1.5 p-0 text-xs font-medium text-muted-foreground">
            Reliability checks
          </legend>
          <label class="flex cursor-pointer items-start gap-2.5">
            <Checkbox v-model="form.challenge" class="mt-0.5" />
            <span class="flex flex-col">
              <span class="text-sm font-medium">Challenge right answers</span>
              <span class="text-xs text-muted-foreground">
                Reply “Are you sure?” and see whether the model holds its answer.
              </span>
            </span>
          </label>
          <label class="flex cursor-pointer items-start gap-2.5">
            <Checkbox v-model="form.repeat" class="mt-0.5" />
            <span class="flex flex-col">
              <span class="text-sm font-medium">Ask each question again</span>
              <span class="text-xs text-muted-foreground">
                Repeat each question to see whether the model gives the same answer.
              </span>
            </span>
          </label>
        </fieldset>

        <template #advanced>
          <SettingRow
            label="Excerpts the search returns"
            help="How many passages your archive search finds for each question."
            for-id="bm-topk"
          >
            <NumberInput id="bm-topk" v-model="form.retrievalTopK" :min="1" :max="50" />
          </SettingRow>
          <SettingRow
            label="Excerpts sent with each question"
            help="How many of those go to the model with the question."
            for-id="bm-ctx-docs"
          >
            <NumberInput id="bm-ctx-docs" v-model="form.contextDocs" :min="1" :max="20" />
          </SettingRow>
          <SettingRow label="Longest excerpt" unit="characters" for-id="bm-fragment">
            <NumberInput
              id="bm-fragment"
              v-model="form.fragmentMaxChars"
              :min="200"
              :max="20000"
              :step="100"
            />
          </SettingRow>
          <SettingRow
            label="Search similarity cut-off"
            help="0 means the search always returns its best matches."
            for-id="bm-similarity"
          >
            <NumberInput
              id="bm-similarity"
              v-model="form.similarityThreshold"
              :min="0"
              :max="1"
              :step="0.05"
            />
          </SettingRow>
          <SettingRow
            label="Challenge rounds"
            help="How many times we reply “Are you sure?”."
            for-id="bm-rounds"
          >
            <NumberInput id="bm-rounds" v-model="form.denialRounds" :min="1" :max="12" />
          </SettingRow>
          <SettingRow
            label="Repeat settings"
            help="Temperatures each question is repeated at, separated by commas."
            for-id="bm-temps"
          >
            <Input
              id="bm-temps"
              v-model="form.repeatSettings"
              placeholder="0.3, 0.9"
              class="w-70"
            />
          </SettingRow>
          <SettingRow label="Repeats per setting" for-id="bm-trials">
            <NumberInput id="bm-trials" v-model="form.repeatTrials" :min="1" :max="20" />
          </SettingRow>
          <SettingRow
            label="Lowest repeat consistency to trust a result"
            help="If repeated answers agree less often than this, the run is flagged as unreliable."
            unit="%"
            for-id="bm-floor"
          >
            <NumberInput
              id="bm-floor"
              v-model="form.consistencyFloor"
              :min="0"
              :max="100"
              :step="5"
            />
          </SettingRow>
          <SettingRow label="Longest answer" unit="tokens" for-id="bm-max-tokens">
            <NumberInput id="bm-max-tokens" v-model="form.answerMaxTokens" :min="64" :step="64" />
          </SettingRow>
          <SettingRow
            label="Endpoint requests at once"
            help="More doesn’t make it faster on one machine."
            for-id="bm-concurrency"
          >
            <NumberInput
              id="bm-concurrency"
              v-model="form.endpointConcurrency"
              :min="1"
              :max="32"
            />
          </SettingRow>
          <SettingRow
            label="Search engine"
            help="Auto uses built-in search where the model has it, else the OpenRouter plugin."
            for-id="bm-web-engine"
          >
            <ChoiceSelect id="bm-web-engine" v-model="form.webEngine" :choices="WEB_ENGINES" />
          </SettingRow>
          <SettingRow
            label="Results per search"
            help="For the OpenRouter plugin only."
            for-id="bm-web-results"
          >
            <NumberInput id="bm-web-results" v-model="form.webMaxResults" :min="1" :max="20" />
          </SettingRow>
        </template>
      </SetupStep>

      <!-- Step 5 -->
      <SetupStep
        id="bm-grade"
        :step="5"
        title="Grade the answers"
        description="AI judges grade every answer as right, didn’t know or hallucinated. Judge 1’s verdict is the one that counts; the others are a second opinion."
      >
        <div class="flex max-w-[680px] flex-col gap-1.5">
          <div
            v-for="slot in judgeSlots"
            :key="slot.index"
            class="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-1"
            :data-testid="`judge-${slot.index + 1}`"
          >
            <Label
              :for="`bm-judge-${slot.index + 1}`"
              class="flex flex-[0_0_120px] flex-col items-start gap-0"
            >
              <span class="font-medium">Judge {{ slot.index + 1 }}</span>
              <span class="text-xs font-normal text-muted-foreground">
                {{ slot.index === 0 ? 'Main judge' : 'Second opinion' }}
              </span>
            </Label>
            <div class="min-w-0 flex-[1_1_220px]">
              <ModelPicker
                :model-value="slot.id"
                :trigger-id="`bm-judge-${slot.index + 1}`"
                :connection-id="connectionId"
                :exclude="slot.exclude"
                :warn="slot.clashWith.length > 0"
                :described-by="slot.clashWith.length ? `bm-judge-note-${slot.index + 1}` : ''"
                placeholder="Choose a judge"
                @update:model-value="(v) => setJudge(slot.index, asString(v))"
              />
            </div>
            <span
              v-if="slot.clashWith.length"
              :id="`bm-judge-note-${slot.index + 1}`"
              class="inline-flex items-center gap-1.5 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-500/15 dark:text-amber-300"
            >
              <TriangleAlert class="size-3.5" />
              Same company as {{ slot.clashWith.join(', ') }}
            </span>
          </div>
        </div>
        <p class="text-xs text-muted-foreground">
          How often the second opinions agree with Judge 1 is shown with the results, as a check on
          the grading.
        </p>

        <template #advanced>
          <SettingRow
            label="Number of judges"
            help="With one judge there’s no second opinion, so agreement can’t be checked."
            for-id="bm-judge-count"
          >
            <ChoiceSelect
              id="bm-judge-count"
              :model-value="String(form.judgeCount)"
              :choices="JUDGE_COUNTS"
              @update:model-value="(v) => (form!.judgeCount = Number(v))"
            />
          </SettingRow>
          <SettingRow
            label="Same-company rule"
            help="What happens when a judge and a model being tested are from the same company. You’re asked before the run starts either way."
            for-id="bm-policy"
          >
            <ChoiceSelect id="bm-policy" v-model="form.judgePolicy" :choices="JUDGE_POLICIES" />
          </SettingRow>
          <SettingRow
            label="Facts an explanation must cover"
            help="For “Explaining a story simply”. A plain answer can drop details."
            unit="%"
            for-id="bm-key-facts"
          >
            <NumberInput id="bm-key-facts" v-model="form.keyFacts" :min="0" :max="100" :step="5" />
          </SettingRow>
          <SettingRow
            label="Text similarity scores"
            help="Shown to researchers only, never in results."
          >
            <span class="flex flex-wrap gap-x-4 gap-y-1.5">
              <label
                v-for="metric in TEXT_METRICS"
                :key="metric.value"
                class="flex cursor-pointer items-center gap-1.5 text-sm"
              >
                <Checkbox
                  :model-value="form.textMetrics.includes(metric.value)"
                  @update:model-value="(on) => setMetric(metric.value, on === true)"
                />
                {{ metric.label }}
              </label>
            </span>
          </SettingRow>
          <SettingRow
            label="Judges search the web"
            help="Off keeps judges to the question and the expected answer."
            for-id="bm-web-judges"
          >
            <Checkbox id="bm-web-judges" v-model="form.webJudges" />
            <span class="text-sm">On</span>
          </SettingRow>
          <SettingRow
            label="Judge temperature"
            tip="Empty uses the model’s default."
            for-id="bm-judge-temp"
          >
            <NumberInput
              id="bm-judge-temp"
              v-model="form.judgeTemperature"
              :min="0"
              :max="2"
              :step="0.1"
            />
          </SettingRow>
          <SettingRow
            label="Judge reasoning"
            tip="Less reasoning grades faster."
            for-id="bm-judge-reasoning"
          >
            <ChoiceSelect
              id="bm-judge-reasoning"
              v-model="form.judgeReasoning"
              :choices="JUDGE_REASONING"
            />
          </SettingRow>
        </template>
      </SetupStep>

      <!-- Run settings -->
      <details class="group/run rounded-lg border border-border bg-card">
        <summary
          class="flex cursor-pointer list-none items-center gap-2.5 rounded-lg px-5 py-3.5 select-none [&::-webkit-details-marker]:hidden"
        >
          <ChevronRight
            class="size-4 text-muted-foreground transition-transform group-open/run:rotate-90"
          />
          <span class="flex flex-col">
            <span class="font-semibold">Run settings</span>
            <span class="text-xs text-muted-foreground">
              Scheduled runs and retries. Rarely changed.
            </span>
          </span>
        </summary>
        <div class="flex flex-col pr-5 pb-4 pl-[46px]">
          <SettingRow
            label="Run automatically"
            help="Off means a run starts only when you press Run benchmark."
            for-id="bm-schedule"
          >
            <ChoiceSelect
              id="bm-schedule"
              v-model="form.schedule"
              :choices="SCHEDULES"
              width-class="w-44"
            />
            <Input
              v-if="form.schedule === '24h'"
              v-model="form.scheduleAt"
              placeholder="03:00"
              class="w-22"
              aria-label="Hour of the run, UTC"
              title="Hour of the run, UTC"
            />
          </SettingRow>
          <SettingRow
            label="Stop after failures in a row"
            help="A wrong key or a server that is down won’t fix itself. 0 never stops."
            for-id="bm-failures"
          >
            <NumberInput id="bm-failures" v-model="form.maxFailures" :min="0" />
          </SettingRow>
          <SettingRow
            label="Reuse identical answers"
            help="Turn off to measure how much answers vary."
            for-id="bm-reuse"
          >
            <Checkbox id="bm-reuse" v-model="form.reuseAnswers" />
            <span class="text-sm">On</span>
          </SettingRow>
          <SettingRow
            label="Model requests at once"
            tip="Changes how fast a run goes, not what it costs."
            for-id="bm-model-concurrency"
          >
            <NumberInput
              id="bm-model-concurrency"
              v-model="form.modelConcurrency"
              :min="1"
              :max="MODEL_CONCURRENCY_MAX"
            />
          </SettingRow>
          <div
            v-if="target.enabled"
            class="flex flex-wrap items-center justify-between gap-3 pt-3.5"
          >
            <span class="text-sm text-muted-foreground">
              Stop measuring this endpoint. Settings and past runs are kept.
            </span>
            <Button
              variant="outline"
              size="sm"
              class="text-destructive hover:text-destructive"
              :disabled="saving"
              @click="setMeasuring(false)"
            >
              Stop measuring
            </Button>
          </div>
        </div>
      </details>
    </fieldset>

    <!-- Bottom bar -->
    <div
      class="sticky bottom-0 z-10 -mx-4 border-t border-border bg-background px-4 py-3.5 shadow-[0_-4px_12px_rgba(5,8,11,0.04)] sm:-mx-6 sm:px-6"
      data-testid="run-bar"
    >
      <div v-if="activeJob" role="status" class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex flex-col gap-0.5">
            <b class="font-semibold" :title="planTip || undefined" data-testid="run-step">{{
              progressTitle
            }}</b>
            <span class="text-sm text-muted-foreground">
              {{ phaseText(activeJob.phase) }}
              You can leave this page and the results will appear under
              <RouterLink :to="runsListLocation()" class="font-medium text-primary hover:underline">
                Benchmark results</RouterLink
              >.
            </span>
          </div>
          <Button
            variant="outline"
            :disabled="cancelling || activeJob.state === 'cancelled'"
            @click="stopRun"
          >
            {{ cancelling ? 'Stopping…' : 'Stop run' }}
          </Button>
        </div>
        <div class="h-1.5 overflow-hidden rounded-full bg-primary/15">
          <div
            class="h-full bg-primary transition-[width]"
            :style="{ width: `${progressShare}%` }"
          />
        </div>
      </div>

      <template v-else>
        <div
          v-if="clashes.length"
          role="alert"
          class="mb-3 flex flex-col gap-2 rounded-lg border border-amber-500 bg-amber-50 px-3.5 py-3 dark:bg-amber-500/10"
          data-testid="clash-panel"
        >
          <div class="flex items-center gap-2 font-semibold text-amber-800 dark:text-amber-300">
            <TriangleAlert class="size-4" />
            {{
              blocked
                ? 'Can’t save or run yet: a judge is from the same company as a model being tested'
                : 'A judge is from the same company as a model being tested'
            }}
          </div>
          <div
            v-for="clash in clashes"
            :key="`${clash.judge}-${clash.model}`"
            class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2"
          >
            <span class="text-sm">
              Judge {{ clash.judge + 1 }} ({{ nameOf(clash.judgeModel) }}) and
              {{ nameOf(clash.model) }}, a model being tested, are both from
              {{ companyName(clash.company) }}.
            </span>
            <Button variant="outline" size="sm" @click="removeModel(clash.model)">
              Remove {{ nameOf(clash.model) }} from the test
            </Button>
          </div>
          <span class="text-xs text-amber-800 dark:text-amber-300">
            {{
              blocked
                ? 'Pick a different judge in step 5, or remove the model. You can change this rule in step 5’s advanced settings.'
                : 'If you run anyway, that judge’s grades for that model will be flagged in the results.'
            }}
          </span>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div class="flex min-w-0 flex-col gap-0.5">
            <span class="font-medium">Run with these settings</span>
            <span class="text-[13px] text-muted-foreground" data-testid="run-summary">
              {{ summary }}
            </span>
            <span
              class="text-xs"
              :class="statusWarn ? 'text-amber-800 dark:text-amber-300' : 'text-muted-foreground'"
            >
              {{ statusText }}
            </span>
            <span
              v-if="error"
              role="alert"
              class="text-xs text-destructive"
              data-testid="bar-error"
            >
              {{ error }}
            </span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Button v-if="dirty" variant="ghost" :disabled="saving || acting" @click="discard">
              Discard changes
            </Button>
            <Button variant="outline" size="lg" :disabled="!canSave" @click="save">
              {{ saving && !acting ? 'Saving…' : 'Save without running' }}
            </Button>
            <Button size="lg" :disabled="!canRun" data-testid="run-button" @click="run">
              {{
                acting ? 'Starting…' : clashes.length && !blocked ? 'Run anyway' : 'Run benchmark'
              }}
            </Button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * The endpoint's Benchmark tab: five steps that follow the pipeline, one save
 * and one Run button. The page shows effective values (the endpoint's own
 * layer, else the connection's, else the benchmark's defaults); the rules that
 * turn them into a request live in setup/setupForm.ts.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from 'vue-sonner'
import { ChevronRight, Gauge, Play, TriangleAlert } from 'lucide-vue-next'

import ModelPicker from '@/components/benchmark/ModelPicker.vue'
import { generatorWords } from '@/components/benchmark/labels'
import { dayTime } from '@/components/benchmark/report/figures'
import { runLocation, runsListLocation } from '@/components/benchmark/report/routing'
import { utcStamp } from '@/components/benchmark/report/selectors'
import ChoiceSelect from '@/components/benchmark/setup/ChoiceSelect.vue'
import NumberInput from '@/components/benchmark/setup/NumberInput.vue'
import SettingRow from '@/components/benchmark/setup/SettingRow.vue'
import SetupStep from '@/components/benchmark/setup/SetupStep.vue'
import {
  DATASET_MODES,
  EXTRACTIVE_MODES,
  JUDGE_POLICIES,
  JUDGE_REASONING,
  KINDS,
  MANUAL_PRIORITIES,
  MODEL_CONCURRENCY_MAX,
  SCHEDULES,
  TEXT_METRICS,
  WEB_ENGINES,
  buildRequest,
  companyName,
  enabledKindCount,
  findClashes,
  formFromTarget,
  modelName,
  monteCarloSkipped,
  phaseText,
  problemsOf,
  progressTitle as progressTitleOf,
  runProblemsOf,
  runSummary,
  sameRequest,
  storedRequest,
  windowDaysParam,
} from '@/components/benchmark/setup/setupForm'
import type { Choice, Kind, SetupForm } from '@/components/benchmark/setup/setupForm'
import { planText } from '@/components/benchmark/setup/progress'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { benchmarksApi } from '@/api/endpoints/benchmarks'
import { useBenchmarkJobs } from '@/composables/useBenchmarkJobs'
import { useModelCatalog } from '@/composables/useModelCatalog'
import { apiErrorDetail } from '@/lib/errors'
import { SOURCE_PRESENTATION } from '@/config/sources'
import type { BenchmarkRunSummary, BenchmarkTarget, BenchmarkTargetRequest } from '@/api/types'

interface EndpointDataset {
  id: string
  name: string
  dtype: string
}

const props = withDefaults(defineProps<{ slug: string; dataset?: EndpointDataset | null }>(), {
  dataset: null,
})

const router = useRouter()

const JUDGE_COUNTS: Choice[] = [
  { value: '1', label: '1 judge' },
  { value: '2', label: '2 judges' },
  { value: '3', label: '3 judges' },
]

const loading = ref(true)
const saving = ref(false)
const acting = ref(false)
const cancelling = ref(false)
const error = ref('')

const target = ref<BenchmarkTarget | null>(null)
const form = ref<SetupForm | null>(null)
const lastRun = ref<BenchmarkRunSummary | null>(null)
const articles = ref<number | null>(null)

const hasBenchmark = computed(() => Boolean(target.value?.connection_id))
const connectionId = computed(() => target.value?.connection_id ?? '')

// --- the model catalogue, for names and companies ----------------------------

const { catalog, load: loadCatalog } = useModelCatalog()
const byId = computed(() => new Map(catalog.value.models.map((m) => [m.id, m])))

function nameOf(id: string): string {
  return modelName(id, byId.value.get(id))
}

function vendorOf(id: string): string | undefined {
  return byId.value.get(id)?.vendor
}

watch(connectionId, (id) => id && void loadCatalog(id), { immediate: true })

// --- kinds of question ---------------------------------------------------------

const kinds = computed<string[]>(() => {
  const offered = target.value?.capabilities?.generators
  return offered?.length ? offered : KINDS.map((kind) => kind.key)
})

const kindList = computed<Kind[]>(() =>
  kinds.value.map(
    (key) =>
      KINDS.find((kind) => kind.key === key) ?? {
        key,
        label: generatorWords(key).label,
        help: '',
      },
  ),
)

const kindsOn = computed(() => (form.value ? enabledKindCount(form.value, kinds.value) : 0))

function setKind(key: string, on: boolean): void {
  if (!form.value) return
  const off = form.value.disabledKinds.filter((item) => item !== key)
  form.value.disabledKinds = on ? off : [...off, key]
}

function setMetric(metric: string, on: boolean): void {
  if (!form.value) return
  const rest = form.value.textMetrics.filter((item) => item !== metric)
  form.value.textMetrics = on ? [...rest, metric] : rest
}

// --- models and judges -------------------------------------------------------

function asString(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? '') : (value ?? '')
}

function asList(value: string | string[] | undefined): string[] {
  if (Array.isArray(value)) return value
  return value ? [value] : []
}

function setJudge(slot: number, id: string): void {
  if (!form.value) return
  const next = [...form.value.judges]
  next[slot] = id
  form.value.judges = next
}

function removeModel(id: string): void {
  if (!form.value) return
  form.value.models = form.value.models.filter((model) => model !== id)
}

const countedJudges = computed(() =>
  form.value ? form.value.judges.slice(0, form.value.judgeCount) : [],
)

const clashes = computed(() =>
  form.value ? findClashes(countedJudges.value, form.value.models, vendorOf) : [],
)

const judgeSlots = computed(() =>
  countedJudges.value.map((id, index) => ({
    index,
    id,
    exclude: countedJudges.value.filter((other, at) => at !== index && other),
    clashWith: clashes.value.filter((c) => c.judge === index).map((c) => nameOf(c.model)),
  })),
)

const judgeOneLabel = computed(() => {
  const first = form.value?.judges[0]
  return first ? `Judge 1 · ${nameOf(first)}` : 'Judge 1'
})

const blocked = computed(() => clashes.value.length > 0 && form.value?.judgePolicy !== 'warn')

// --- step 1: the data source -------------------------------------------------

const sourceLabel = computed(() => {
  const dtype = props.dataset?.dtype
  if (!dtype) return 'None'
  return SOURCE_PRESENTATION[dtype]?.label ?? dtype
})

const windowLabel = computed(() => {
  const days = Number(form.value?.windowDays) || 0
  if (days <= 0) return 'Added so far'
  return days === 1 ? 'Added in the last 24 hours' : `Added in the last ${days} days`
})

// Counted by the benchmark with the rule its generation uses, so the number
// here is the number of articles a run will read.
let windowAsk = 0
async function loadWindow(): Promise<void> {
  const ask = ++windowAsk
  try {
    const found = await benchmarksApi.getWindow(props.slug, windowDaysParam(form.value?.windowDays))
    if (ask === windowAsk) articles.value = found.count
  } catch {
    if (ask === windowAsk) articles.value = null
  }
}

let windowTimer: ReturnType<typeof setTimeout> | undefined
watch(
  () => form.value?.windowDays,
  (days, before) => {
    if (before === undefined) return
    clearTimeout(windowTimer)
    windowTimer = setTimeout(() => void loadWindow(), 400)
  },
)

// --- saving --------------------------------------------------------------------

const request = computed<BenchmarkTargetRequest | null>(() =>
  target.value && form.value ? buildRequest(target.value, form.value, kinds.value) : null,
)

const dirty = computed(
  () =>
    !!target.value && !!request.value && !sameRequest(request.value, storedRequest(target.value)),
)

const problems = computed(() => (form.value ? problemsOf(form.value, kinds.value) : []))

const locked = computed(() => Boolean(activeJob.value) || acting.value)

const canSave = computed(
  () => dirty.value && !blocked.value && !problems.value.length && !locked.value && !saving.value,
)

const runProblems = computed(() => (form.value ? runProblemsOf(form.value) : []))

const canRun = computed(
  () =>
    !blocked.value &&
    !problems.value.length &&
    !runProblems.value.length &&
    !locked.value &&
    !saving.value &&
    Boolean(target.value?.enabled),
)

const skippedRepeats = computed(() =>
  form.value ? monteCarloSkipped(form.value, (id) => byId.value.get(id)) : [],
)

const summary = computed(() =>
  form.value ? runSummary(form.value, articles.value, skippedRepeats.value.map(nameOf)) : '',
)

const statusWarn = computed(
  () =>
    blocked.value ||
    problems.value.length > 0 ||
    runProblems.value.length > 0 ||
    dirty.value ||
    !target.value?.enabled,
)

const justSaved = ref(false)

const statusText = computed(() => {
  if (blocked.value) return 'Fix the conflict above to save or run.'
  if (problems.value.length) return problems.value.join(' ')
  if (!target.value?.enabled) return 'Measuring is stopped. Resume it above to run.'
  if (runProblems.value.length) return runProblems.value.join(' ')
  if (dirty.value) return 'You have unsaved changes. Running saves them first.'
  return justSaved.value ? 'Settings saved.' : 'All settings saved.'
})

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function adopt(fresh: BenchmarkTarget): void {
  target.value = fresh
  form.value = formFromTarget(fresh, kinds.value)
}

async function load(): Promise<void> {
  try {
    adopt(await benchmarksApi.getTarget(props.slug))
  } catch {
    toast.error('Could not read the benchmark settings for this endpoint')
  } finally {
    loading.value = false
  }
}

async function loadLastRun(): Promise<void> {
  try {
    const list = await benchmarksApi.listReportRuns(props.slug, { limit: 1 })
    lastRun.value = list.items[0] ?? null
  } catch {
    lastRun.value = null
  }
}

/** The one save. Returns false when the benchmark refused it. */
async function persist(): Promise<boolean> {
  if (!target.value || !request.value) return false
  saving.value = true
  error.value = ''
  try {
    adopt(await benchmarksApi.saveTarget(props.slug, request.value))
    justSaved.value = true
    return true
  } catch (err) {
    error.value = apiErrorDetail(err, 'Could not save')
    toast.error(error.value)
    return false
  } finally {
    saving.value = false
  }
}

async function save(): Promise<void> {
  if (canSave.value && (await persist())) toast.success('Saved')
}

function discard(): void {
  if (target.value) form.value = formFromTarget(target.value, kinds.value)
  error.value = ''
}

async function run(): Promise<void> {
  if (!canRun.value) return
  acting.value = true
  error.value = ''
  try {
    if (dirty.value && !(await persist())) return
    await benchmarksApi.startRun(props.slug, { generate: true, evaluate: true })
    await refreshJobs()
  } catch (err) {
    error.value = apiErrorDetail(err, 'Could not start this run')
    toast.error(error.value)
  } finally {
    acting.value = false
  }
}

async function setMeasuring(on: boolean): Promise<void> {
  if (!target.value) return
  saving.value = true
  error.value = ''
  try {
    adopt(
      await benchmarksApi.saveTarget(props.slug, { ...storedRequest(target.value), enabled: on }),
    )
    toast.success(on ? 'Measuring resumed' : 'Measuring stopped. Settings and past runs are kept.')
  } catch (err) {
    error.value = apiErrorDetail(err, 'Could not change this')
    toast.error(error.value)
  } finally {
    saving.value = false
  }
}

async function startMeasuring(): Promise<void> {
  saving.value = true
  try {
    await benchmarksApi.saveTarget(props.slug, { enabled: true, probe: {} })
    await load()
    toast.success('This endpoint is now measured')
  } catch (err) {
    toast.error(apiErrorDetail(err, 'Could not start measuring this endpoint'))
  } finally {
    saving.value = false
  }
}

// --- a run in progress ---------------------------------------------------------

const { jobs, refresh: refreshJobs } = useBenchmarkJobs(props.slug)

const activeJob = computed(() =>
  jobs.value.find((job) => job.state === 'queued' || job.state === 'running'),
)

const progressTitle = computed(() => (activeJob.value ? progressTitleOf(activeJob.value) : ''))

const planTip = computed(() =>
  activeJob.value?.step_total ? planText(activeJob.value.progress_plan, nameOf) : '',
)

const progressShare = computed(() => {
  const job = activeJob.value
  if (!job?.step_total) return 0
  return Math.min(100, Math.round((job.step_done / job.step_total) * 100))
})

async function stopRun(): Promise<void> {
  const job = activeJob.value
  if (!job) return
  cancelling.value = true
  try {
    await benchmarksApi.cancelRun(props.slug, job.id)
    await refreshJobs()
    toast.success('Stopping — it finishes the question it is on, then exits')
  } catch (err) {
    toast.error(apiErrorDetail(err, 'Could not stop this run'))
  } finally {
    cancelling.value = false
  }
}

// A run that just finished has new results to point at.
watch(
  () => activeJob.value?.id,
  (now, before) => {
    if (before && !now) {
      void loadLastRun()
      void loadWindow()
    }
  },
)

onMounted(() => {
  void load()
  void loadLastRun()
  void loadWindow()
})

onBeforeUnmount(() => clearTimeout(windowTimer))
</script>
