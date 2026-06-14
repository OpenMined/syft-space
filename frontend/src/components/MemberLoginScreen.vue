<template>
  <div class="relative min-h-screen flex items-center justify-center bg-background px-4 py-12">
    <!-- Ambient brand glow -->
    <div class="absolute inset-0 -z-10 opacity-30 dark:opacity-20 blur-3xl" aria-hidden="true">
      <div class="absolute top-[12%] left-[15%] h-80 w-80 rounded-full bg-primary/30" />
      <div class="absolute bottom-[10%] right-[12%] h-72 w-72 rounded-full bg-amber-400/20" />
    </div>

    <div class="w-full max-w-md">
      <div class="rounded-2xl border border-border/60 bg-card shadow-lg p-8">
        <div class="flex flex-col items-center text-center mb-8">
          <div class="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 mb-4">
            <UsersRound class="h-7 w-7 text-primary" />
          </div>
          <Badge variant="secondary" class="mb-3">Collective member sign-in</Badge>
          <h1 class="text-2xl font-semibold tracking-tight text-foreground">
            Welcome to {{ collectiveName }}
          </h1>
          <p class="text-sm text-muted-foreground mt-2 max-w-xs">
            Sign in to run your Syft Space inside the collective. Paste your SyftHub API key to
            continue.
          </p>
        </div>

        <form class="space-y-4" @submit.prevent="handleLogin">
          <div class="space-y-2">
            <Label for="member-api-key" class="text-sm font-medium">SyftHub API key</Label>
            <Input
              id="member-api-key"
              v-model="apiKey"
              type="password"
              placeholder="sk-syftbox-…"
              autocomplete="off"
              autofocus
            />
            <p class="text-xs text-muted-foreground">
              Find this under <span class="font-medium">SyftHub → Settings → API keys</span>.
            </p>
          </div>

          <Button type="submit" class="w-full" size="lg" :disabled="!apiKey.trim()">
            Sign in
          </Button>
        </form>
      </div>

      <p class="text-center text-xs text-muted-foreground mt-6">
        Membership is managed by the collective host — there's nothing to register.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UsersRound } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { useCollectiveMode } from '@/composables/useCollectiveMode'
import { collectiveStatsSummary } from '@/stores/mockCollective'

const { logInMember } = useCollectiveMode()

const collectiveName = collectiveStatsSummary.name
const apiKey = ref('')

const handleLogin = () => {
  if (!apiKey.value.trim()) return
  logInMember()
  apiKey.value = ''
}
</script>
