<template>
  <svg
    :width="width"
    :height="height"
    viewBox="0 0 100 100"
    preserveAspectRatio="xMidYMid slice"
    xmlns="http://www.w3.org/2000/svg"
    :class="className"
  >
    <defs>
      <!-- 1) Warm peach at top‑left -->
      <radialGradient id="g1" cx="20%" cy="20%" r="60%" gradientUnits="objectBoundingBox">
        <stop offset="0%" stop-color="#F09463" />
        <stop offset="100%" stop-color="#F09463" stop-opacity="0" />
      </radialGradient>

      <!-- 2) Bright coral nearer the top center -->
      <radialGradient id="g2" cx="50%" cy="10%" r="70%" gradientUnits="objectBoundingBox">
        <stop offset="0%" stop-color="#FDC676" />
        <stop offset="100%" stop-color="#FDC676" stop-opacity="0" />
      </radialGradient>

      <!-- 3) Magenta‑pink at the left‑mid -->
      <radialGradient id="g3" cx="0%" cy="60%" r="60%" gradientUnits="objectBoundingBox">
        <stop offset="0%" stop-color="#AF3A7E" />
        <stop offset="100%" stop-color="#AF3A7E" stop-opacity="0" />
      </radialGradient>

      <!-- 4) Teal‑green down near the bottom center -->
      <radialGradient id="g4" cx="60%" cy="80%" r="60%" gradientUnits="objectBoundingBox">
        <stop offset="0%" stop-color="#7BC3AB" />
        <stop offset="100%" stop-color="#7BC3AB" stop-opacity="0" />
      </radialGradient>

      <!-- 5) Pale lime at the right -->
      <radialGradient id="g5" cx="100%" cy="40%" r="60%" gradientUnits="objectBoundingBox">
        <stop offset="0%" stop-color="#C1C68E" />
        <stop offset="100%" stop-color="#C1C68E" stop-opacity="0" />
      </radialGradient>
    </defs>

    <!-- Base is white so that any "holes" fade back to white -->
    <rect width="100%" height="100%" fill="#FFFFFF" />

    <!-- Layer the five radial gradients in the same order -->
    <rect width="100%" height="100%" fill="url(#g1)" />
    <rect width="100%" height="100%" fill="url(#g2)" />
    <rect width="100%" height="100%" fill="url(#g3)" />
    <rect width="100%" height="100%" fill="url(#g4)" />
    <rect width="100%" height="100%" fill="url(#g5)" />
  </svg>
</template>

<script setup lang="ts">
interface BackgroundGradientsProps {
  width?: string | number
  height?: string | number
  className?: string
}

withDefaults(defineProps<BackgroundGradientsProps>(), {
  width: '100%',
  height: '100%',
  className: '',
})
</script>
