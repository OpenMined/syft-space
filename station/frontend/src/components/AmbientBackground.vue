<template>
  <div class="ambient" aria-hidden="true" />
</template>

<script setup lang="ts">
// A soft OpenMined-spectrum wash: brand-hued glows seep in from the corners and
// fade toward the centre, so whatever sits on top stays legible. Static (no
// animation), theme-aware, decorative only. Place it as the first child of a
// `relative` container; content above needs a stacking context (e.g. z-10).
</script>

<style scoped>
.ambient {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(
      46rem 34rem at 0% 0%,
      color-mix(in oklab, var(--color-teal-500) 44%, transparent),
      transparent 64%
    ),
    radial-gradient(
      42rem 32rem at 100% 0%,
      color-mix(in oklab, var(--color-violet-500) 40%, transparent),
      transparent 64%
    ),
    radial-gradient(
      46rem 34rem at 0% 100%,
      color-mix(in oklab, var(--color-green-500) 40%, transparent),
      transparent 64%
    ),
    radial-gradient(
      44rem 34rem at 100% 100%,
      color-mix(in oklab, var(--color-orange-400) 36%, transparent),
      transparent 64%
    );
  opacity: 0.7;
}

/* A little softer on dark surfaces so the glows read as ambience, not spotlights. */
:root[data-theme='dark'] .ambient {
  opacity: 0.55;
}
</style>
