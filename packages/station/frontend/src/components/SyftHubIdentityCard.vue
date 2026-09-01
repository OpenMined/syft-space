<script setup lang="ts">
/**
 * The station's SyftHub identity — one API token, shared by every wallet.
 *
 * Two ways to provide it: generate (the admin's password mints one on the
 * hub) or paste an existing syft_pat_… token. Either way it is saved here
 * and never returned, so a connected station shows only who it belongs to.
 *
 * Saving also registers the station's satellite, which is what lets the hub
 * mint buyer tokens against this host.
 */
import { computed, ref } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ApiError } from '@/api/client'
import { useStationStore } from '@/stores/station'

const station = useStationStore()

const mode = ref('generate')
const pastedToken = ref('')
const password = ref('')
const promptOpen = ref(false)
const saving = ref(false)

const connected = computed(() => station.identity?.connected ?? false)

/** Connected and untouched: collapse to a line so the common case is quiet. */
const collapsed = computed(() => connected.value && !promptOpen.value && !pastedToken.value)

async function connect(body: { syfthubApiToken?: string; syfthubPassword?: string }) {
  saving.value = true
  try {
    await station.connectIdentity(body)
    password.value = ''
    pastedToken.value = ''
    promptOpen.value = false
    toast.success('SyftHub connected')
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Could not connect SyftHub')
  } finally {
    saving.value = false
  }
}

function generate() {
  if (!password.value) {
    toast.error('Enter your SyftHub password')
    return
  }
  return connect({ syfthubPassword: password.value })
}

function adopt() {
  if (!pastedToken.value.trim()) {
    toast.error('Paste a SyftHub API token')
    return
  }
  return connect({ syfthubApiToken: pastedToken.value.trim() })
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-center gap-2">
      <Label>SyftHub identity</Label>
      <Badge v-if="connected" variant="secondary">Connected</Badge>
    </div>

    <!-- Connected and idle: one line, plus a way back in. -->
    <div v-if="collapsed" class="flex items-center gap-2">
      <p class="min-w-0 flex-1 truncate text-sm text-muted-foreground">
        <span v-if="station.identity?.username" class="font-medium text-foreground">
          {{ station.identity.username }}
        </span>
        <span v-if="station.identity?.email"> · {{ station.identity.email }}</span>
        <span v-else>Connected to SyftHub</span>
      </p>
      <Button variant="outline" size="sm" @click="promptOpen = true">
        <KeyRound class="mr-1.5 h-3.5 w-3.5" />
        Rotate
      </Button>
    </div>

    <Tabs v-else v-model="mode">
      <TabsList class="grid w-full grid-cols-2">
        <TabsTrigger value="generate">Generate</TabsTrigger>
        <TabsTrigger value="paste">Paste existing</TabsTrigger>
      </TabsList>

      <TabsContent value="generate" class="space-y-1.5">
        <div class="flex gap-2">
          <Input
            v-model="password"
            type="password"
            autocomplete="off"
            placeholder="Your SyftHub password"
            @keydown.enter.prevent="generate"
          />
          <Button :disabled="saving" @click="generate">Generate</Button>
        </div>
        <p class="text-xs text-muted-foreground">
          Your password mints an API token on SyftHub and is discarded. The station uses the token
          to verify buyers' sign-ins for every wallet.
        </p>
      </TabsContent>

      <TabsContent value="paste" class="space-y-1.5">
        <div class="flex gap-2">
          <Input
            v-model="pastedToken"
            autocomplete="off"
            spellcheck="false"
            class="font-mono"
            placeholder="syft_pat_…"
            @keydown.enter.prevent="adopt"
          />
          <Button :disabled="saving" @click="adopt">Save</Button>
        </div>
        <p class="text-xs text-muted-foreground">
          Create one on SyftHub with write scope. Revoke it there at any time.
        </p>
      </TabsContent>
    </Tabs>
  </div>
</template>
