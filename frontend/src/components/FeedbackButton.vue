<script setup lang="ts">
import { ref } from 'vue'
import { MessageSquarePlus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import FeedbackDialog from '@/components/FeedbackDialog.vue'

const dialogOpen = ref(false)
</script>

<template>
  <div class="fixed bottom-5 right-5 z-50 animate-slide-in-right">
    <Button
      class="rounded-full shadow-lg px-4 py-2 h-auto gap-2"
      @click="dialogOpen = true"
    >
      <MessageSquarePlus class="h-4 w-4" />
      <span class="text-sm font-medium">Feedback</span>
    </Button>
  </div>

  <FeedbackDialog v-model:open="dialogOpen" />
</template>

<style scoped>
@keyframes slide-in-right {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.animate-slide-in-right {
  animation: slide-in-right 0.4s ease-out 0.5s both;
}
</style>
