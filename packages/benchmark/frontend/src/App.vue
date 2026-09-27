<script setup lang="ts">
import { ref, watch, computed, onMounted } from "vue";
import { Toaster, toast } from "vue-sonner";
import { hasToken, ApiError } from "@/api/client";
import {
  buildReport,
  getProbe,
  publishReport,
  retractReport,
  runFilter,
  runJudge,
  saveProbe,
  startRun,
} from "@/api/console";
import { useJobs, jobStateWords } from "@/composables/useJobs";
import PhaseGroup from "@/components/PhaseGroup.vue";
import PhaseBlock from "@/components/PhaseBlock.vue";
import PairList from "@/components/PairList.vue";
import ResultList from "@/components/ResultList.vue";
import ProbeForm from "@/components/ProbeForm.vue";
import type { JobView, ProbeField, ProbeLayer } from "@/api/types";

const authorized = hasToken();
const { jobs, running, refresh, latestOf } = useJobs();

// Bumped so PairList/ResultList reload without each of them polling the job
// queue on their own — on every poll while something is running, since
// generation and filtering write pairs one at a time as they go and the
// owner watching Generation should see them appear rather than wait for the
// whole pass to end; and once more on the exact tick a job finishes, in case
// the last poll landed a beat before its final row.
const refreshKey = ref(0);
const seenFinal = new Set<string>();
watch(
  jobs,
  (current) => {
    let sawFinal = false;
    for (const job of current) {
      const final =
        job.state === "succeeded" ||
        job.state === "failed" ||
        job.state === "cancelled";
      if (final && !seenFinal.has(job.id)) {
        seenFinal.add(job.id);
        sawFinal = true;
      }
    }
    if (sawFinal || running.value) {
      refreshKey.value += 1;
    }
  },
  { deep: true },
);

// `kind` alone cannot tell a generation-only pipeline job from an
// execution-only one — both are `pipeline`, and the benchmark leaves
// `phase` at `done` once either finishes, so a job's own fields cannot say
// afterwards which block started it either. So each block that can start a
// `pipeline` job remembers the id of the one IT started, and reads that
// job's current state back out of the poll — rather than the latest job of
// its kind, which might belong to a different block entirely.
const startedJobId = ref<Record<string, string>>({});

function jobFor(name: string): JobView | undefined {
  const id = startedJobId.value[name];
  return id ? jobs.value.find((job) => job.id === id) : undefined;
}

const generationJob = computed(() => jobFor("generation"));
const executionJob = computed(() => jobFor("execution"));
const filterJob = computed(() => latestOf("filter"));
const judgeJob = computed(() => latestOf("judge"));

function progressOf(job: JobView | undefined): number | "indeterminate" | null {
  if (!job || job.state !== "running") return null;
  // The finer of the two counters wins: `step_total` is a count of
  // questions within whatever is running now (a pass, a judging batch),
  // and moves continuously, where `total` only moves once a whole pass
  // ends. Generation and filtering report neither — "running with no
  // total" still means something is happening, just not how far along.
  if (job.step_total) return Math.round((job.step_done / job.step_total) * 100);
  if (!job.total) return "indeterminate";
  return Math.round((job.done / job.total) * 100);
}

const acting = ref<string | null>(null);

async function act(name: string, fn: () => Promise<JobView>): Promise<void> {
  acting.value = name;
  try {
    const job = await fn();
    startedJobId.value[name] = job.id;
    await refresh();
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : `Could not start ${name}`,
    );
  } finally {
    acting.value = null;
  }
}

const busy = computed(() => acting.value !== null || running.value);

// This target's own probe layer — dataset and retrieval parameters, the one
// settings group a single endpoint's session may change. The instrument
// (arms, judges, thresholds) is decided once for every endpoint of a
// connection, from the Space's own settings page.
const probe = ref<ProbeLayer>({});
const probeInherited = ref<ProbeLayer>({});
const probeFields = ref<ProbeField[]>([]);
const probeSaving = ref(false);

async function loadProbe(): Promise<void> {
  try {
    const settings = await getProbe();
    probe.value = settings.probe;
    probeInherited.value = settings.inherited;
    probeFields.value = settings.fields;
  } catch (error) {
    toast.error(
      error instanceof ApiError
        ? error.message
        : "Could not read this target's settings",
    );
  }
}

async function doSaveProbe(): Promise<void> {
  probeSaving.value = true;
  try {
    const settings = await saveProbe(probe.value);
    probe.value = settings.probe;
    probeInherited.value = settings.inherited;
    toast.success("Saved");
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : "Could not save");
  } finally {
    probeSaving.value = false;
  }
}

onMounted(loadProbe);

// Report state, refreshed on demand rather than polled: it is a fast,
// synchronous call, not a queued job.
const report = ref<Record<string, unknown> | null>(null);
const reportLoading = ref(false);

async function doBuildReport(): Promise<void> {
  reportLoading.value = true;
  try {
    report.value = await buildReport();
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not build the report",
    );
  } finally {
    reportLoading.value = false;
  }
}

async function doPublish(): Promise<void> {
  reportLoading.value = true;
  try {
    report.value = await publishReport();
    toast.success("Published");
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not publish",
    );
  } finally {
    reportLoading.value = false;
  }
}

async function doRetract(): Promise<void> {
  reportLoading.value = true;
  try {
    await retractReport();
    toast.success("Retracted");
  } catch (error) {
    toast.error(
      error instanceof ApiError ? error.message : "Could not retract",
    );
  } finally {
    reportLoading.value = false;
  }
}
</script>

<template>
  <Toaster theme="system" />
  <div v-if="!authorized" class="max-w-md mx-auto mt-24 text-center space-y-2">
    <h1 class="text-lg font-semibold">No session</h1>
    <p class="text-sm text-muted-foreground">
      This page opens from a link in the Space's own settings — there is nothing
      to show without one.
    </p>
  </div>

  <main v-else class="max-w-3xl mx-auto p-4 space-y-4">
    <h1 class="text-lg font-semibold">Benchmark console</h1>

    <details class="group border border-border rounded-lg">
      <summary
        class="flex items-center gap-3 p-4 cursor-pointer select-none list-none [&::-webkit-details-marker]:hidden"
      >
        <span class="font-semibold">Settings</span>
        <span class="text-sm text-muted-foreground"
          >Dataset and retrieval, for this endpoint</span
        >
      </summary>
      <div class="border-t border-border p-4 space-y-4">
        <ProbeForm
          v-model="probe"
          :fields="probeFields"
          :inherited="probeInherited"
        />
        <button
          type="button"
          class="rounded-md bg-primary text-primary-foreground text-sm px-3 py-1.5 disabled:opacity-50"
          :disabled="probeSaving"
          @click="doSaveProbe"
        >
          {{ probeSaving ? "Saving…" : "Save" }}
        </button>
      </div>
    </details>

    <PhaseGroup
      title="Preparation"
      status="Generation, then filtering"
      action-label="Run preparation"
      :action-disabled="busy"
      @action="
        act('preparation', () => startRun({ generate: true, evaluate: false }))
      "
    >
      <PhaseBlock
        title="Generation"
        help="Builds new question/answer pairs from the corpus. Everything it builds lands pending — nothing here decides whether a pair is any good, that is Filtering's job."
        :status="jobStateWords(generationJob)"
        :progress="progressOf(generationJob)"
        action-label="Run"
        :action-disabled="busy"
        @action="
          act('generation', () =>
            startRun({ generate: true, evaluate: false, filter: false }),
          )
        "
      >
        <PairList :refresh-key="refreshKey" />
      </PhaseBlock>

      <PhaseBlock
        title="Filtering"
        help="Screens pending pairs for grounding and, for control items, checks live retrieval again. Only pending pairs are touched automatically — overturn a verdict by hand below."
        :status="jobStateWords(filterJob)"
        :progress="progressOf(filterJob)"
        action-label="Run"
        :action-disabled="busy"
        @action="act('filter', () => runFilter())"
      >
        <PairList status="pending" :refresh-key="refreshKey" />
      </PhaseBlock>
    </PhaseGroup>

    <PhaseGroup
      title="Testing"
      status="Execution, judging and the report"
      action-label="Run testing"
      :action-disabled="busy"
      @action="
        act('testing', () => startRun({ generate: false, evaluate: true }))
      "
    >
      <PhaseBlock
        title="Execution"
        help="Asks the active questions. Run on its own, it defers judging so the Judging block has pending verdicts to grade — Testing above grades inline instead."
        :status="jobStateWords(executionJob)"
        :progress="progressOf(executionJob)"
        action-label="Run"
        :action-disabled="busy"
        @action="
          act('execution', () =>
            startRun({
              generate: false,
              evaluate: true,
              defer_judging: true,
              publish: false,
            }),
          )
        "
      >
        <p class="text-xs text-muted-foreground">
          Answers are graded in the Judging block below, or reviewed on the
          target's published card once Testing has run.
        </p>
        <ResultList :refresh-key="refreshKey" />
      </PhaseBlock>

      <PhaseBlock
        title="Judging"
        help="Grades pending verdicts — the ones Execution left ungraded. Never rewrites a verdict, only adds a new one; every reader already takes the freshest."
        :status="jobStateWords(judgeJob)"
        :progress="progressOf(judgeJob)"
        action-label="Run"
        :action-disabled="busy"
        @action="act('judge', () => runJudge())"
      >
        <ResultList :refresh-key="refreshKey" />
      </PhaseBlock>

      <PhaseBlock
        title="Report"
        help="Builds the card from what is active and graded right now — no fresh run needed. Publishing is a separate, explicit step."
        status=""
        action-label="Build"
        :action-disabled="reportLoading"
        @action="doBuildReport"
      >
        <div v-if="report" class="space-y-2 text-sm">
          <pre class="rounded-md bg-muted p-2 text-xs overflow-auto">{{
            report
          }}</pre>
          <div class="flex gap-2">
            <button
              type="button"
              class="rounded-md bg-primary text-primary-foreground text-sm px-3 py-1.5 disabled:opacity-50"
              :disabled="reportLoading"
              @click="doPublish"
            >
              Publish
            </button>
            <button
              type="button"
              class="rounded-md border border-border text-sm px-3 py-1.5 disabled:opacity-50"
              :disabled="reportLoading"
              @click="doRetract"
            >
              Retract
            </button>
          </div>
        </div>
        <p v-else class="text-sm text-muted-foreground">Not built yet.</p>
      </PhaseBlock>
    </PhaseGroup>
  </main>
</template>
