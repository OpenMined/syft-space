<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Bug, MessageSquare, Lightbulb, Camera, Loader2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
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
    // Use pre-captured screenshot from the button's pointerdown
    if (props.previewDataUrl) {
      screenshotPreview.value = props.previewDataUrl
      screenshotBlob.value = props.previewBlob ?? null
    }
  } else {
    resetForm()
  }
})

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
      open.value = false
      resetForm()
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
  <Dialog v-model:open="open">
    <DialogContent class="sm:max-w-[480px]">
      <DialogHeader>
        <DialogTitle>Send Feedback</DialogTitle>
        <DialogDescription>
          Help us improve Syft Space. Report a bug, share feedback, or suggest an idea.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-2">
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
            <!-- Thumbnail with popover preview -->
            <Popover v-if="screenshotPreview">
              <PopoverTrigger as-child>
                <button
                  type="button"
                  class="rounded border border-border overflow-hidden hover:ring-2 hover:ring-ring transition-all"
                >
                  <img
                    :src="screenshotPreview"
                    alt="Screenshot preview"
                    class="h-8 w-14 object-cover object-top"
                  />
                </button>
              </PopoverTrigger>
              <PopoverContent side="left" align="center" class="w-96 p-1">
                <img
                  :src="screenshotPreview"
                  alt="Screenshot preview"
                  class="w-full h-auto rounded"
                />
              </PopoverContent>
            </Popover>
            <Switch id="screenshot-toggle" v-model="includeScreenshot" />
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button variant="outline" @click="open = false" :disabled="isSubmitting"> Cancel </Button>
        <Button @click="submit" :disabled="!canSubmit">
          <Loader2 v-if="isSubmitting" class="h-4 w-4 mr-2 animate-spin" />
          {{ isSubmitting ? 'Sending...' : 'Send Feedback' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
