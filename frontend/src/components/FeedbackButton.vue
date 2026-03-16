<script setup lang="ts">
import { ref } from 'vue'
import html2canvas from 'html2canvas-pro'
import { MessageSquarePlus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import FeedbackDialog from '@/components/FeedbackDialog.vue'

const dialogOpen = ref(false)
const screenshotDataUrl = ref<string | null>(null)
const screenshotBlob = ref<Blob | null>(null)

const captureAndOpen = async () => {
  // Capture screenshot BEFORE the dialog opens (and before other dialogs dismiss)
  try {
    const canvas = await html2canvas(document.body, {
      logging: false,
      useCORS: true,
      scale: 1,
    })
    screenshotDataUrl.value = canvas.toDataURL('image/png')
    screenshotBlob.value = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((blob) => resolve(blob), 'image/png')
    })
  } catch {
    screenshotDataUrl.value = null
    screenshotBlob.value = null
  }
  dialogOpen.value = true
}
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed bottom-5 right-5 z-[99999] animate-slide-in-right"
      style="pointer-events: auto !important"
    >
      <Button class="rounded-full shadow-lg px-4 py-2 h-auto gap-2" @click="captureAndOpen">
        <MessageSquarePlus class="h-4 w-4" />
        <span class="text-sm font-medium">Feedback</span>
      </Button>
    </div>
  </Teleport>

  <FeedbackDialog
    v-model:open="dialogOpen"
    :preview-data-url="screenshotDataUrl"
    :preview-blob="screenshotBlob"
  />
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
