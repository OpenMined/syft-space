<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Globe, Rocket } from 'lucide-vue-next'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { slugify } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const station = useStationStore()

const spaceName = ref('')
const subdomain = ref('')
const ownerEmail = ref('')
const subdomainEdited = ref(false)

// Reset the form each time the dialog opens
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      spaceName.value = ''
      subdomain.value = ''
      ownerEmail.value = ''
      subdomainEdited.value = false
    }
  },
)

// Subdomain follows the space name until the admin edits it directly
watch(spaceName, (name) => {
  if (!subdomainEdited.value) subdomain.value = slugify(name)
})

// Reserved by a running space OR a request already provisioning
const subdomainTaken = computed(() => station.subdomainInUse(slugify(subdomain.value)))

const emailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(ownerEmail.value.trim()))

function create() {
  if (!spaceName.value.trim()) {
    toast.error('Space name is required')
    return
  }
  if (!slugify(subdomain.value)) {
    toast.error('Subdomain is required')
    return
  }
  if (subdomainTaken.value) {
    toast.error(`Subdomain "${subdomain.value}" is already in use`)
    return
  }
  if (!emailValid.value) {
    toast.error('A valid owner email is required')
    return
  }
  station.createSpace({
    spaceName: spaceName.value.trim(),
    subdomain: slugify(subdomain.value),
    ownerEmail: ownerEmail.value.trim(),
  })
  toast.success('Setting up the space', {
    description: `${slugify(subdomain.value)}.${station.domain}`,
  })
  emit('update:open', false)
}
</script>

<template>
  <Dialog :open="open" @update:open="(v: boolean) => emit('update:open', v)">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>New space</DialogTitle>
        <DialogDescription>
          Create a space for a member directly — no request needed. They pick up their API key from
          their dashboard after signing in with SyftHub.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4">
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-1.5">
            <Label for="create-name">Space name</Label>
            <Input id="create-name" v-model="spaceName" placeholder="research-lab" />
          </div>
          <div class="space-y-1.5">
            <Label for="create-subdomain">Subdomain</Label>
            <Input id="create-subdomain" v-model="subdomain" @input="subdomainEdited = true" />
          </div>
        </div>
        <p class="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Globe class="h-3 w-3" />
          {{ slugify(subdomain) || '—' }}.{{ station.domain }}
          <span v-if="subdomainTaken" class="text-destructive">— already in use</span>
        </p>

        <div class="space-y-1.5">
          <Label for="create-owner">Owner email (SyftHub account)</Label>
          <Input
            id="create-owner"
            v-model="ownerEmail"
            type="email"
            placeholder="member@example.org"
          />
        </div>

        <div class="rounded-md border bg-muted/40 px-3 py-2.5">
          <p class="mb-1.5 text-xs font-medium text-muted-foreground">This space will get</p>
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
      </div>

      <DialogFooter>
        <Button variant="outline" @click="emit('update:open', false)">Cancel</Button>
        <Button @click="create">
          <Rocket class="mr-1.5 h-4 w-4" />
          Create space
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
