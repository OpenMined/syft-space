<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import AppHeader from '@/components/AppHeader.vue'
import StationAnimation from '@/components/StationAnimation.vue'
import AmbientBackground from '@/components/AmbientBackground.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError } from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { useStationStore } from '@/stores/station'

const router = useRouter()
const session = useSessionStore()
const station = useStationStore()

const email = ref('')
const password = ref('')
const signingIn = ref(false)

async function submit() {
  if (!email.value || !password.value) {
    toast.error('Enter your SyftHub email and password')
    return
  }
  signingIn.value = true
  try {
    const profile = await session.signIn(email.value, password.value)
    toast.success(`Signed in as ${profile.email}`)
    await station.loadSetup().catch(() => {})
    // Honor a post-sign-in destination (e.g. the /credits checkout link).
    const redirect = router.currentRoute.value.query.redirect
    if (typeof redirect === 'string' && redirect) {
      router.push(redirect)
    } else {
      router.push({ name: session.isAdmin ? 'admin' : 'member' })
    }
  } catch (error) {
    toast.error(error instanceof ApiError ? error.message : 'Sign-in failed — is the station up?')
  } finally {
    signingIn.value = false
  }
}
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden bg-background">
    <AppHeader />
    <main class="relative isolate flex min-h-0 flex-1 overflow-hidden">
      <AmbientBackground />
      <!-- Brand panel: the station at full strength, form-free (lg+) -->
      <div
        class="relative z-10 hidden min-w-0 flex-1 flex-col items-center justify-center gap-8 overflow-hidden border-r border-border lg:flex"
      >
        <div class="max-w-md px-8 text-center">
          <h1 class="text-2xl font-semibold tracking-tight">Syft Station</h1>
          <p class="mt-1 text-sm font-medium text-foreground/80">
            Spin up your own Space, dock it to the Station.
          </p>
          <p class="mt-1 text-sm text-muted-foreground">Share the station, never your data.</p>
        </div>
        <StationAnimation :busy="signingIn" class="h-[26rem] w-[26rem] shrink-0" />
      </div>

      <!-- Form pane -->
      <div class="relative z-10 flex min-w-0 flex-1 overflow-y-auto">
        <div class="m-auto w-full max-w-sm px-4 py-8">
          <div class="mb-6 flex flex-col items-center gap-2 text-center lg:hidden">
            <h1 class="text-2xl font-semibold tracking-tight">Syft Station</h1>
            <p class="text-sm font-medium text-foreground/80">
              Spin up your own Space, dock it to the Station.
            </p>
            <p class="text-sm text-muted-foreground">
              Share the station, never your data. Sign in with your SyftHub account to get started.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle class="text-base">Sign in with SyftHub</CardTitle>
              <CardDescription>
                Your identity is verified against SyftHub; your password is never stored.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form class="space-y-4" @submit.prevent="submit">
                <div class="space-y-1.5">
                  <Label for="email">SyftHub email</Label>
                  <Input
                    id="email"
                    v-model="email"
                    type="email"
                    placeholder="you@example.org"
                    autocomplete="email"
                  />
                </div>
                <div class="space-y-1.5">
                  <Label for="password">Password</Label>
                  <Input
                    id="password"
                    v-model="password"
                    type="password"
                    placeholder="••••••••"
                    autocomplete="current-password"
                  />
                </div>
                <Button type="submit" class="w-full" :disabled="signingIn">
                  <Loader2 v-if="signingIn" class="mr-2 h-4 w-4 animate-spin" />
                  Sign in
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  </div>
</template>
