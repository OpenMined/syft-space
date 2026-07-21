<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, Globe, Send } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/api/client'
import { slugify } from '@/lib/types'
import { useStationStore } from '@/stores/station'
import { useSessionStore } from '@/stores/session'

const emit = defineEmits<{ submitted: [] }>()

const station = useStationStore()
const session = useSessionStore()

const spaceName = ref('')
const purpose = ref('')
const submitting = ref(false)

const subdomain = computed(() => slugify(spaceName.value))

async function submit() {
  if (!session.profile) return
  if (!subdomain.value) {
    toast.error('Give your space a name')
    return
  }
  submitting.value = true
  try {
    await station.submitRequest({
      spaceName: spaceName.value.trim(),
      purpose: purpose.value.trim(),
    })
    toast.success('Request submitted', {
      description: 'The station admin will review it. Track the status here.',
    })
    spaceName.value = ''
    purpose.value = ''
    emit('submitted')
  } catch (error) {
    // 409 = subdomain already taken; anything else is unexpected
    toast.error(error instanceof ApiError ? error.message : 'Submitting the request failed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="text-base">Request a space</CardTitle>
      <CardDescription> Your own hosted Syft Space — set up and run for you. </CardDescription>
    </CardHeader>
    <CardContent>
      <form class="space-y-4" @submit.prevent="submit">
        <div class="space-y-1.5">
          <Label for="space-name">Space name</Label>
          <Input id="space-name" v-model="spaceName" placeholder="e.g. research-lab" />
          <p v-if="subdomain" class="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Globe class="h-3 w-3" />
            {{ subdomain }}.{{ station.domain }}
          </p>
        </div>

        <div class="space-y-1.5">
          <Label for="req-email">SyftHub email</Label>
          <Input id="req-email" :model-value="session.profile?.email" disabled />
          <p class="text-xs text-muted-foreground">Verified via SyftHub sign-in</p>
        </div>

        <div class="space-y-1.5">
          <Label for="req-name">Full name</Label>
          <Input id="req-name" :model-value="session.profile?.fullName" disabled />
        </div>

        <div class="space-y-1.5">
          <Label for="purpose">What will you use it for?</Label>
          <Textarea
            id="purpose"
            v-model="purpose"
            placeholder="A sentence or two helps the admin review faster"
            rows="3"
          />
        </div>

        <div class="rounded-md border bg-muted/40 px-3 py-2.5">
          <p class="mb-1.5 text-xs font-medium text-muted-foreground">Every space includes</p>
          <ul class="space-y-1">
            <li
              v-for="item in station.spaceIncludes"
              :key="item"
              class="flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <Check class="h-3 w-3 shrink-0 text-success" />
              {{ item }}
            </li>
          </ul>
        </div>

        <Button type="submit" class="w-full" :disabled="submitting">
          <Send class="mr-2 h-4 w-4" />
          Submit request
        </Button>
      </form>
    </CardContent>
  </Card>
</template>
