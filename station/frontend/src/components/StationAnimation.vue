<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

/**
 * The station, animated: a powering core with space nodes orbiting it,
 * linked graph-style by spokes. Nodes join amber ("setting up"), flash
 * green ("running"), then settle — mirroring the space lifecycle.
 *
 * Props:
 * - busy: speeds everything up (e.g. while signing in)
 * - mini: compact single-orbit variant for provisioning indicators;
 *   its amber node never settles, so it reads as "in progress"
 *
 * Pure CSS/SVG, theme-aware, paused for reduced-motion users.
 */
const props = defineProps<{ busy?: boolean; mini?: boolean }>()

type Orbit = 'inner' | 'outer'
type NodeState = 'provisioning' | 'flash' | 'running' | 'leaving'
interface SpaceNode {
  id: number
  orbit: Orbit
  angle: number
  state: NodeState
}

const INNER_R = 44
const OUTER_R = 74
const MAX_NODES = 9

let nextId = 0
// Irregular angles on purpose so it reads as a live graph, not a clock face
const nodes = ref<SpaceNode[]>([
  { id: nextId++, orbit: 'inner', angle: 15, state: 'running' },
  { id: nextId++, orbit: 'inner', angle: 130, state: 'running' },
  { id: nextId++, orbit: 'inner', angle: 250, state: 'provisioning' },
  { id: nextId++, orbit: 'outer', angle: 70, state: 'running' },
  { id: nextId++, orbit: 'outer', angle: 160, state: 'running' },
  { id: nextId++, orbit: 'outer', angle: 265, state: 'running' },
  { id: nextId++, orbit: 'outer', angle: 340, state: 'running' },
])

const innerNodes = computed(() => nodes.value.filter((n) => n.orbit === 'inner'))
const outerNodes = computed(() => nodes.value.filter((n) => n.orbit === 'outer'))

function pos(angle: number, radius: number) {
  const rad = (angle * Math.PI) / 180
  return { x: 100 + radius * Math.cos(rad), y: 100 + radius * Math.sin(rad) }
}

// ---- Node lifecycle: join (amber) → flash (green) → running → leave ----
const timeouts: number[] = []
let interval: number | undefined

function later(fn: () => void, ms: number) {
  timeouts.push(window.setTimeout(fn, ms))
}

function settle(node: SpaceNode) {
  later(() => {
    node.state = 'flash'
    later(() => {
      node.state = 'running'
    }, 1800)
  }, 3600)
}

/** Pick an angle at least 32° away from every node already on the orbit. */
function freeAngle(orbit: Orbit): number | null {
  const taken = nodes.value.filter((n) => n.orbit === orbit).map((n) => n.angle)
  for (let tries = 0; tries < 8; tries++) {
    const angle = Math.floor(Math.random() * 360)
    const gap = (a: number, b: number) => Math.min(Math.abs(a - b), 360 - Math.abs(a - b))
    if (taken.every((t) => gap(t, angle) > 32)) return angle
  }
  return null
}

function joinOne() {
  const preferred: Orbit = Math.random() < 0.4 ? 'inner' : 'outer'
  const fallback: Orbit = preferred === 'inner' ? 'outer' : 'inner'
  let orbit = preferred
  let angle = freeAngle(preferred)
  if (angle === null) {
    orbit = fallback
    angle = freeAngle(fallback)
  }
  if (angle === null) return
  const node: SpaceNode = { id: nextId++, orbit, angle, state: 'provisioning' }
  nodes.value.push(node)
  settle(node)
}

function leaveOne() {
  const running = nodes.value.filter((n) => n.state === 'running')
  const node = running[Math.floor(Math.random() * running.length)]
  if (!node) return
  node.state = 'leaving'
  later(() => {
    nodes.value = nodes.value.filter((n) => n.id !== node.id)
  }, 700)
}

onMounted(() => {
  // The mini indicator keeps its amber node forever ("in progress");
  // the full version settles it like any other new space
  if (!props.mini) {
    nodes.value.filter((n) => n.state === 'provisioning').forEach(settle)
  }
  if (props.mini || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  interval = window.setInterval(() => {
    const active = nodes.value.filter((n) => n.state !== 'leaving').length
    if (active >= MAX_NODES) leaveOne()
    else if (active <= 5) joinOne()
    else if (Math.random() < 0.65) joinOne()
    else leaveOne()
  }, 7000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
  timeouts.forEach((t) => clearTimeout(t))
})
</script>

<template>
  <svg
    viewBox="0 0 200 200"
    class="station-anim"
    :class="{ busy, mini }"
    aria-hidden="true"
    role="presentation"
  >
    <!-- Orbit guides -->
    <circle cx="100" cy="100" :r="INNER_R" class="orbit-ring" />
    <circle v-if="!mini" cx="100" cy="100" :r="OUTER_R" class="orbit-ring" />

    <!-- Outer orbit: spaces + spokes, rotating clockwise -->
    <g v-if="!mini" class="orbit orbit-outer">
      <g
        v-for="node in outerNodes"
        :key="node.id"
        class="node-g"
        :class="node.state"
      >
        <line
          x1="100"
          y1="100"
          :x2="pos(node.angle, OUTER_R).x"
          :y2="pos(node.angle, OUTER_R).y"
          class="spoke"
        />
        <circle
          v-if="node.state === 'flash'"
          :cx="pos(node.angle, OUTER_R).x"
          :cy="pos(node.angle, OUTER_R).y"
          r="5"
          class="join-ring"
        />
        <circle
          :cx="pos(node.angle, OUTER_R).x"
          :cy="pos(node.angle, OUTER_R).y"
          r="5"
          class="space-node"
        />
      </g>
    </g>

    <!-- Inner orbit: spaces + spokes, rotating counter-clockwise -->
    <g class="orbit orbit-inner">
      <g
        v-for="node in innerNodes"
        :key="node.id"
        class="node-g"
        :class="node.state"
      >
        <line
          x1="100"
          y1="100"
          :x2="pos(node.angle, INNER_R).x"
          :y2="pos(node.angle, INNER_R).y"
          class="spoke"
        />
        <circle
          v-if="node.state === 'flash'"
          :cx="pos(node.angle, INNER_R).x"
          :cy="pos(node.angle, INNER_R).y"
          r="4.5"
          class="join-ring"
        />
        <circle
          :cx="pos(node.angle, INNER_R).x"
          :cy="pos(node.angle, INNER_R).y"
          r="4.5"
          class="space-node"
        />
      </g>
    </g>

    <!-- Station core: ambient glow + powering-up pulses + steady center -->
    <circle v-if="!mini" cx="100" cy="100" r="34" class="core-glow" />
    <circle cx="100" cy="100" r="13" class="core-pulse" />
    <circle cx="100" cy="100" r="13" class="core-pulse core-pulse-late" />
    <circle cx="100" cy="100" r="13" class="core-halo" />
    <circle cx="100" cy="100" r="6" class="core" />
  </svg>
</template>

<style scoped>
.station-anim {
  overflow: visible;
}

.orbit-ring {
  fill: none;
  stroke: var(--border);
  stroke-width: 1;
  stroke-dasharray: 3 5;
}

.orbit {
  transform-origin: 100px 100px;
  animation: spin 56s linear infinite;
}

.orbit-inner {
  animation-duration: 40s;
  animation-direction: reverse;
}

/* Node enter/leave */
.node-g {
  animation: node-in 0.7s ease-out both;
  transition: opacity 0.7s ease;
}

.node-g.leaving {
  opacity: 0;
}

.spoke {
  stroke: var(--primary);
  stroke-width: 1;
  opacity: 0.25;
}

.space-node {
  fill: var(--background);
  stroke: var(--primary);
  stroke-width: 1.5;
  transition: stroke 0.5s ease;
}

/* Space lifecycle: setting up (amber, blinking) → running (green flash) */
.node-g.provisioning .space-node {
  stroke: var(--warning);
  animation: blink 1.6s ease-in-out infinite;
}

.node-g.flash .space-node {
  stroke: var(--success);
}

.join-ring {
  fill: none;
  stroke: var(--success);
  stroke-width: 1.5;
  transform-box: fill-box;
  transform-origin: center;
  animation: join-ring 1.6s ease-out both;
}

.core {
  fill: var(--primary);
}

.core-halo {
  fill: var(--primary);
  opacity: 0.15;
}

.core-glow {
  fill: var(--primary);
  opacity: 0.12;
  filter: blur(10px);
}

.core-pulse {
  fill: none;
  stroke: var(--primary);
  stroke-width: 1.5;
  transform-origin: 100px 100px;
  animation: pulse 6.4s ease-out infinite;
}

.core-pulse-late {
  animation-delay: 3.2s;
}

/* Busy (e.g. signing in): the whole station spins up */
.busy .orbit {
  animation-duration: 14s;
}

.busy .orbit-inner {
  animation-duration: 10s;
}

.busy .core-pulse {
  animation-duration: 2s;
}

.busy .core-pulse-late {
  animation-delay: 1s;
}

/* Mini indicator: single orbit, contained pulses */
.mini .core-pulse {
  animation-name: pulse-mini;
  animation-duration: 3.2s;
}

.mini .core-pulse-late {
  animation-delay: 1.6s;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.7;
  }
  100% {
    transform: scale(5.2);
    opacity: 0;
  }
}

@keyframes pulse-mini {
  0% {
    transform: scale(1);
    opacity: 0.7;
  }
  100% {
    transform: scale(2.2);
    opacity: 0;
  }
}

@keyframes node-in {
  from {
    opacity: 0;
  }
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@keyframes join-ring {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  100% {
    transform: scale(3);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .orbit,
  .core-pulse,
  .node-g.provisioning .space-node {
    animation: none;
  }

  .core-pulse {
    opacity: 0;
  }
}
</style>
