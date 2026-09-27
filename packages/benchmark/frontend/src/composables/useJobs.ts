import { ref, onMounted, onUnmounted, computed } from "vue";
import { listJobs } from "@/api/console";
import type { JobView } from "@/api/types";

// Same cadence and the same reasoning as spaces/frontend's RunControl.vue:
// a phase runs for minutes to hours, so 5s is watching for a state change,
// not for a number to tick.
const POLL_MS = 5000;

/** Every job for this target, polled while any of them is still running. */
export function useJobs() {
  const jobs = ref<JobView[]>([]);
  let timer: ReturnType<typeof setInterval> | undefined;

  const running = computed(() =>
    jobs.value.some((j) => j.state === "queued" || j.state === "running"),
  );

  async function refresh(): Promise<void> {
    try {
      jobs.value = await listJobs();
    } catch {
      // A blink in the control API must not wipe the progress the owner is
      // watching — same reasoning as RunControl.vue's own poll.
    }
  }

  function latestOf(kind: JobView["kind"]): JobView | undefined {
    return jobs.value.find((j) => j.kind === kind);
  }

  onMounted(async () => {
    await refresh();
    timer = setInterval(refresh, POLL_MS);
  });
  onUnmounted(() => {
    if (timer) clearInterval(timer);
  });

  return { jobs, running, refresh, latestOf };
}

/**
 * What a running job is doing right now, from the fields a pass reports as
 * it goes — model, which question within the pass, which pass within the
 * whole run. Generation, filtering and judging leave all three blank (they
 * have no notion of a "pass"), so this reads as an empty string for them and
 * `jobStateWords` falls back to the plain state word.
 */
function runningDetail(job: JobView): string {
  const parts: string[] = [];
  if (job.model) parts.push(job.model);
  if (job.step_total) parts.push(`question ${job.step_done} of ${job.step_total}`);
  if (job.total) parts.push(`pass ${job.done + 1} of ${job.total}`);
  return parts.join(" · ");
}

export function jobStateWords(job: JobView | undefined): string {
  if (!job) return "";
  switch (job.state) {
    case "queued":
      return "Queued";
    case "running":
      return job.message || runningDetail(job) || "Running";
    case "succeeded":
      return job.error ? `Done, with notes: ${job.error}` : "Done";
    case "failed":
      return `Failed: ${job.error || "no details given"}`;
    case "cancelled":
      return "Stopped";
    default:
      return job.state;
  }
}
