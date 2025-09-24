<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppNavbar from './components/AppNavbar.vue'

const route = useRoute()
const showNavbar = computed(() => route.name !== 'create-service')
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppNavbar v-if="showNavbar" />
    
    <main>
      <router-view />
    </main>
  </div>
</template>

<style scoped></style>
