<script setup lang="ts">
import Navbar from './components/Navbar.vue'
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <Navbar />
    
    <!-- Main Content Area - Placeholder -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="bg-white shadow rounded-lg p-6">
        <h1 class="text-2xl font-bold text-gray-900 mb-4">Welcome to SyftNSAI</h1>
        <p class="text-gray-600">
          This is a placeholder for the main content area. The actual content will be added later.
        </p>
        <div class="mt-6 p-4 bg-gray-100 rounded">
          <p class="text-sm text-gray-500">
            Main content area will display:
          </p>
          <ul class="mt-2 space-y-1 text-sm text-gray-600 list-disc list-inside">
            <li>Service management when "Services" tab is selected</li>
            <li>Inbox messages when "Inbox" tab is selected</li>
            <li>Usage statistics and analytics when "Usage" tab is selected</li>
            <li>Application settings when "Settings" tab is selected</li>
          </ul>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped></style>
