<script setup lang="ts">
import AppNavbar from './components/AppNavbar.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar />
    
    <main>
      <router-view />
    </main>
  </div>
</template>

<style scoped></style>
