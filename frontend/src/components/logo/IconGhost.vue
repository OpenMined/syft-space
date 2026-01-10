<template>
  <svg
    :width="width"
    :height="height"
    viewBox="0 0 556 556"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    :class="className"
  >
    <path
      d="M478.246 162.258L278.023 277.997L77.7996 162.258L278.023 46.5185L478.246 162.258Z"
      fill="url(#paint0_linear_345_369)"
    />
    <path
      d="M478.246 162.258V393.737L278.023 509.482V277.997L478.246 162.258Z"
      fill="url(#paint1_linear_345_369)"
    />
    <path
      d="M278.023 277.997V509.482L77.7996 393.737V162.258L278.023 277.997Z"
      fill="url(#paint2_linear_345_369)"
    />
    <defs>
      <linearGradient
        id="paint0_linear_345_369"
        x1="77.7996"
        y1="162.258"
        x2="478.246"
        y2="162.258"
        gradientUnits="userSpaceOnUse"
      >
        <stop stop-color="white" stop-opacity="0.6" />
        <stop offset="0.36" stop-color="white" stop-opacity="0.96" />
        <stop offset="0.501247" stop-color="white" />
        <stop offset="0.64" stop-color="white" stop-opacity="0.96" />
        <stop offset="1" stop-color="white" stop-opacity="0.6" />
      </linearGradient>
      <linearGradient
        id="paint1_linear_345_369"
        x1="277.391"
        y1="502.781"
        x2="470.495"
        y2="173.224"
        gradientUnits="userSpaceOnUse"
      >
        <stop stop-color="white" stop-opacity="0.5" />
        <stop offset="0.37" stop-color="white" stop-opacity="0.86" />
        <stop offset="0.501247" stop-color="white" stop-opacity="0.9" />
        <stop offset="0.63" stop-color="white" stop-opacity="0.86" />
        <stop offset="1" stop-color="white" stop-opacity="0.5" />
      </linearGradient>
      <linearGradient
        id="paint2_linear_345_369"
        x1="79.4133"
        y1="165.305"
        x2="277.391"
        y2="501.258"
        gradientUnits="userSpaceOnUse"
      >
        <stop stop-color="white" stop-opacity="0.4" />
        <stop offset="0.36" stop-color="white" stop-opacity="0.76" />
        <stop offset="0.501247" stop-color="white" stop-opacity="0.8" />
        <stop offset="0.64" stop-color="white" stop-opacity="0.76" />
        <stop offset="1" stop-color="white" stop-opacity="0.4" />
      </linearGradient>
    </defs>
  </svg>
</template>

<script setup lang="ts">
interface IconGhostProps {
  width?: string | number
  height?: string | number
  className?: string
}

withDefaults(defineProps<IconGhostProps>(), {
  width: '100%',
  height: '100%',
  className: '',
})
</script>
