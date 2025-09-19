<script setup lang="ts">
import Navbar from './components/Navbar.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <Navbar />
    
    <main>
      <router-view />
    </main>
  </div>
</template>

<style scoped></style>
