<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Bug, MessageSquare, Lightbulb, Camera, Loader2, X } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { feedbackApi } from '@/api/endpoints/feedback'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  previewDataUrl?: string | null
  previewBlob?: Blob | null
}>()

type FeedbackCategory = 'bug' | 'feedback' | 'idea'

const categories: { value: FeedbackCategory; label: string; icon: typeof Bug }[] = [
  { value: 'bug', label: 'Bug', icon: Bug },
  { value: 'feedback', label: 'Feedback', icon: MessageSquare },
  { value: 'idea', label: 'Idea', icon: Lightbulb },
]

const selectedCategory = ref<FeedbackCategory>('feedback')
const description = ref('')
const includeScreenshot = ref(true)
const isSubmitting = ref(false)
const screenshotPreview = ref<string | null>(null)
const screenshotBlob = ref<Blob | null>(null)
const showPreview = ref(false)

const route = useRoute()

const canSubmit = computed(() => description.value.trim().length > 0 && !isSubmitting.value)

const resetForm = () => {
  selectedCategory.value = 'feedback'
  description.value = ''
  includeScreenshot.value = true
  screenshotPreview.value = null
  screenshotBlob.value = null
}

watch(open, (isOpen) => {
  if (isOpen) {
    if (props.previewDataUrl) {
      screenshotPreview.value = props.previewDataUrl
      screenshotBlob.value = props.previewBlob ?? null
    }
  } else {
    resetForm()
  }
})

const close = () => {
  open.value = false
}

const submit = async () => {
  if (!canSubmit.value) return

  isSubmitting.value = true
  try {
    const result = await feedbackApi.submit({
      category: selectedCategory.value,
      description: description.value.trim(),
      page_url: route.fullPath,
      app_version: '0.1.0',
      browser_info: navigator.userAgent,
      screenshot: includeScreenshot.value ? screenshotBlob.value : null,
    })

    if (result.success) {
      toast.success(result.message)
      close()
    } else {
      toast.error(result.message)
    }
  } catch {
    toast.error('Failed to submit feedback. Please try again.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <!-- Screenshot preview floating to the left of the panel -->
    <Transition name="fade">
      <div
        v-if="open && showPreview && screenshotPreview && includeScreenshot"
        class="fixed top-1/2 right-[430px] z-[100000] -translate-y-1/2 rounded-lg border bg-background p-1.5 shadow-2xl"
        style="pointer-events: auto !important; max-width: calc(100vw - 450px); max-height: 80vh"
        @mouseenter="showPreview = true"
        @mouseleave="showPreview = false"
      >
        <img
          :src="screenshotPreview"
          alt="Screenshot preview"
          class="rounded max-h-[78vh] w-auto object-contain"
        />
      </div>
    </Transition>

    <Transition name="slide">
      <div
        v-if="open"
        class="fixed top-0 right-0 bottom-0 z-[99999] w-full sm:w-[420px] border-l bg-background shadow-2xl flex flex-col"
        style="pointer-events: auto !important"
        @pointerdown.stop
      >
        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b">
          <div>
            <h2 class="text-lg font-semibold leading-none tracking-tight">Send Feedback</h2>
            <p class="text-sm text-muted-foreground mt-1">
              Report a bug, share feedback, or suggest an idea.
            </p>
          </div>
          <Button variant="ghost" size="icon" class="h-8 w-8 shrink-0" @click="close">
            <X class="h-4 w-4" />
          </Button>
        </div>

        <!-- Body -->
        <div class="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          <!-- Category Selector -->
          <div class="space-y-2">
            <Label>Category</Label>
            <div class="flex gap-2">
              <Button
                v-for="cat in categories"
                :key="cat.value"
                :variant="selectedCategory === cat.value ? 'default' : 'outline'"
                size="sm"
                @click="selectedCategory = cat.value"
                class="flex-1"
              >
                <component :is="cat.icon" class="h-4 w-4 mr-1.5" />
                {{ cat.label }}
              </Button>
            </div>
          </div>

          <!-- Description -->
          <div class="space-y-2">
            <Label for="feedback-description">What happened?</Label>
            <Textarea
              id="feedback-description"
              v-model="description"
              placeholder="Describe the issue, feedback, or idea..."
              class="min-h-[120px] resize-none"
            />
          </div>

          <!-- Screenshot Toggle -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Camera class="h-4 w-4 text-muted-foreground" />
              <Label for="screenshot-toggle" class="text-sm font-normal cursor-pointer">
                Include screenshot of current page
              </Label>
            </div>
            <div class="flex items-center gap-2">
              <div
                v-if="screenshotPreview && includeScreenshot"
                class="relative"
                @mouseenter="showPreview = true"
                @mouseleave="showPreview = false"
              >
                <button
                  type="button"
                  class="rounded border border-border overflow-hidden hover:ring-2 hover:ring-ring transition-all"
                  @click="showPreview = !showPreview"
                >
                  <img
                    :src="screenshotPreview"
                    alt="Screenshot preview"
                    class="h-8 w-14 object-cover object-top"
                  />
                </button>
              </div>
              <Switch id="screenshot-toggle" v-model="includeScreenshot" />
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-end gap-2 px-5 py-4 border-t">
          <Button variant="outline" @click="close" :disabled="isSubmitting"> Cancel </Button>
          <Button @click="submit" :disabled="!canSubmit">
            <Loader2 v-if="isSubmitting" class="h-4 w-4 mr-2 animate-spin" />
            {{ isSubmitting ? 'Sending...' : 'Send Feedback' }}
          </Button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
