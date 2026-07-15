<script setup lang="ts">
import { ref } from 'vue'
import { Check, Copy, KeyRound, TriangleAlert } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { Space } from '@/lib/types'
import { useStationStore } from '@/stores/station'

const props = defineProps<{ space: Space }>()

const station = useStationStore()

const open = ref(false)
const revealedKey = ref<string | null>(null)
const copied = ref(false)

function reveal() {
  // Claiming is one-time: once this dialog has been opened, the key is gone
  revealedKey.value = station.claimApiKey(props.space.id)
  open.value = true
}

async function copyKey() {
  if (!revealedKey.value) return
  await navigator.clipboard.writeText(revealedKey.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

function close() {
  open.value = false
  revealedKey.value = null
}
</script>

<template>
  <Button v-if="!space.apiKeyClaimed" size="sm" variant="outline" @click="reveal">
    <KeyRound class="mr-1.5 h-3.5 w-3.5" />
    Reveal API key
  </Button>
  <span v-else class="text-xs text-muted-foreground">API key claimed</span>

  <Dialog :open="open" @update:open="(v: boolean) => !v && close()">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Your space API key</DialogTitle>
        <DialogDescription>
          Admin API key for <span class="font-medium">{{ space.name }}</span>
        </DialogDescription>
      </DialogHeader>

      <Alert class="border-warning/50 bg-warning/10">
        <TriangleAlert class="h-4 w-4" />
        <AlertTitle>Shown only once</AlertTitle>
        <AlertDescription>
          Store this key somewhere safe — it cannot be retrieved again.
        </AlertDescription>
      </Alert>

      <div class="flex items-center gap-2">
        <code class="flex-1 overflow-x-auto rounded-md border bg-muted px-3 py-2 font-mono text-xs">
          {{ revealedKey }}
        </code>
        <Button size="sm" variant="outline" @click="copyKey">
          <Check v-if="copied" class="h-3.5 w-3.5 text-success" />
          <Copy v-else class="h-3.5 w-3.5" />
        </Button>
      </div>

      <DialogFooter>
        <Button @click="close">I saved it</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
