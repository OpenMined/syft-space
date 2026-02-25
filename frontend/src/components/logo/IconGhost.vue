<template>
  <svg
    :width="width"
    :height="height"
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    :class="className"
  >
    <path d="M10.747 0.722722L7.07704 7.07704L11.9984 4.23621L19.7607 11.9984L13.253 0.722722C12.6961 -0.240907 11.3039 -0.240907 10.747 0.722722Z" fill="url(#paint0_linear_421_1528)"/>
    <path d="M16.9198 7.07704L19.7606 11.9984L12.0016 19.7575L23.2773 13.2468C24.2409 12.6899 24.2409 11.2976 23.2773 10.7407L16.9198 7.07079V7.07704Z" fill="url(#paint1_linear_421_1528)"/>
    <path d="M4.23934 11.9984L12.0016 4.23621L0.722722 10.747C-0.240907 11.3039 -0.240907 12.6961 0.722722 13.253L7.07704 16.923L4.23621 12.0016L4.23934 11.9984Z" fill="url(#paint2_linear_421_1528)"/>
    <path d="M12.0016 19.7607L4.24248 12.0016L10.7532 23.2773C11.3101 24.2409 12.7024 24.2409 13.2593 23.2773L16.9292 16.9198L12.0078 19.7607H12.0016Z" fill="url(#paint3_linear_421_1528)"/>
    <path d="M12.0016 12.0016H16.657L12.0016 7.34611V12.0016Z" fill="url(#paint4_linear_421_1528)"/>
    <path d="M12.0016 12.0016H7.34612L12.0016 16.657V12.0016Z" fill="url(#paint5_linear_421_1528)"/>
    <path d="M12.0016 12.0016V16.657L16.657 12.0016H12.0016Z" fill="url(#paint6_linear_421_1528)"/>
    <path d="M12.0016 12.0016V7.34611L7.34612 12.0016H12.0016Z" fill="url(#paint7_linear_421_1528)"/>
    <defs>
      <linearGradient id="paint0_linear_421_1528" x1="7.08017" y1="6.00078" x2="19.7638" y2="6.00078" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint1_linear_421_1528" x1="17.9992" y1="7.07704" x2="17.9992" y2="19.7607" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint2_linear_421_1528" x1="6.00078" y1="16.9198" x2="6.00078" y2="4.23621" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint3_linear_421_1528" x1="16.923" y1="17.9992" x2="4.23622" y2="17.9992" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint4_linear_421_1528" x1="12.0235" y1="11.9765" x2="16.5663" y2="7.43371" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint5_linear_421_1528" x1="11.9797" y1="12.0235" x2="7.43685" y2="16.5663" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint6_linear_421_1528" x1="11.7387" y1="11.7388" x2="14.4857" y2="14.4857" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
      </linearGradient>
      <linearGradient id="paint7_linear_421_1528" x1="12.2613" y1="12.2612" x2="9.51428" y2="9.51427" gradientUnits="userSpaceOnUse">
        <stop stop-color="white"/>
        <stop offset="1" stop-color="white" stop-opacity="0.6"/>
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
