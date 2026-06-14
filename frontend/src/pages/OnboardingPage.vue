<template>
  <div class="min-h-screen bg-background flex items-center justify-center p-4">
    <div class="w-full max-w-2xl">
      <!-- Header -->
      <div class="text-center mb-8">
        <h1 class="heading-2 text-foreground mb-2">Welcome to Syft Space</h1>
        <p class="body-lg text-muted-foreground">
          Let's get you connected to
          <a
            href="https://syfthub.openmined.org"
            target="_blank"
            rel="noopener noreferrer"
            class="text-primary hover:underline inline-flex items-center gap-1"
          >
            SyftHub
            <ExternalLink class="h-4 w-4" />
          </a>
        </p>
      </div>

      <!-- Single form card -->
      <Card>
        <CardContent class="p-8">
          <form @submit.prevent="handleCompleteSetup" class="space-y-6">
            <!-- Already registered state -->
            <div v-if="isAlreadyRegistered" class="space-y-3">
              <div
                class="flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950"
              >
                <CheckCircle class="h-5 w-5 text-green-600 shrink-0" />
                <div>
                  <p class="body-md font-medium text-foreground">
                    Signed in as <span class="font-semibold">{{ marketplaceData!.username }}</span>
                  </p>
                  <p class="body-sm text-muted-foreground">Your SyftHub account is connected.</p>
                </div>
              </div>
            </div>

            <!-- Account type toggle -->
            <template v-else>
              <div class="space-y-4">
                <h3 class="heading-4 text-foreground">Do you have a SyftHub account?</h3>
                <div class="flex gap-3">
                  <Button
                    type="button"
                    :variant="authMode === 'register' ? 'default' : 'outline'"
                    class="flex-1"
                    @click="authMode = 'register'"
                  >
                    I'm new here
                  </Button>
                  <Button
                    type="button"
                    :variant="authMode === 'signin' ? 'default' : 'outline'"
                    class="flex-1"
                    @click="authMode = 'signin'"
                  >
                    I have an account
                  </Button>
                </div>
              </div>

              <!-- Register Form Fields -->
              <div v-if="authMode === 'register'" class="space-y-4">
                <!-- Username field with availability check -->
                <div class="space-y-2">
                  <Label for="username">Username</Label>
                  <div class="relative">
                    <Input
                      id="username"
                      v-model="registerForm.username"
                      @input="handleUsernameInput"
                      placeholder="johndoe"
                      class="pr-10"
                      :class="{
                        'border-green-500': usernameAvailable === true,
                        'border-red-500': usernameAvailable === false,
                      }"
                    />
                    <div
                      class="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none"
                    >
                      <Loader2
                        v-if="checkingUsername"
                        class="h-4 w-4 text-muted-foreground animate-spin"
                      />
                      <CheckCircle
                        v-else-if="usernameAvailable === true"
                        class="h-4 w-4 text-green-600"
                      />
                      <XCircle
                        v-else-if="usernameAvailable === false"
                        class="h-4 w-4 text-red-600"
                      />
                    </div>
                  </div>
                  <p v-if="usernameAvailable === false" class="body-sm text-red-600">
                    This username is already taken
                  </p>
                  <p v-else-if="usernameAvailable === true" class="body-sm text-green-600">
                    Great! This username is available
                  </p>
                  <p v-else class="body-sm text-muted-foreground">
                    Choose a unique username for your space
                  </p>
                </div>

                <!-- Email field -->
                <div class="space-y-2">
                  <Label for="email">Email</Label>
                  <Input
                    id="email"
                    v-model="registerForm.email"
                    type="email"
                    placeholder="john@example.com"
                  />
                </div>

                <!-- Name field -->
                <div class="space-y-2">
                  <Label for="name">Full Name</Label>
                  <Input id="name" v-model="registerForm.name" placeholder="John Doe" />
                </div>

                <!-- Password field -->
                <div class="space-y-2">
                  <Label for="password">Password</Label>
                  <Input
                    id="password"
                    v-model="registerForm.password"
                    type="password"
                    placeholder="••••••••"
                  />
                  <p class="body-sm text-muted-foreground">Must be at least 8 characters</p>
                </div>

                <!-- Confirm Password field -->
                <div class="space-y-2">
                  <Label for="confirm-password">Confirm Password</Label>
                  <Input
                    id="confirm-password"
                    v-model="confirmPassword"
                    type="password"
                    placeholder="••••••••"
                    :class="{
                      'border-red-500':
                        confirmPassword && registerForm.password !== confirmPassword,
                    }"
                  />
                  <p
                    v-if="confirmPassword && registerForm.password !== confirmPassword"
                    class="body-sm text-red-600"
                  >
                    Passwords do not match
                  </p>
                </div>
              </div>

              <!-- Sign In Form Fields -->
              <div v-else class="space-y-4">
                <!-- Username field -->
                <div class="space-y-2">
                  <Label for="signin-username">Email</Label>
                  <Input
                    id="signin-username"
                    v-model="signinForm.username"
                    placeholder="john@example.com"
                  />
                </div>

                <!-- Password field -->
                <div class="space-y-2">
                  <Label for="signin-password">Password</Label>
                  <Input
                    id="signin-password"
                    v-model="signinForm.password"
                    type="password"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </template>

            <!-- Separator -->
            <Separator />

            <!-- Network setup section -->
            <div class="space-y-4">
              <h3 class="heading-4 text-foreground">How should others access your space?</h3>
              <div
                v-if="isCollectiveAdmin"
                class="rounded-lg border border-border bg-muted/50 p-4 text-sm text-muted-foreground"
              >
                Collective admin mode requires your own public URL. SyftHub-provided URLs are
                disabled for this setup.
              </div>

              <!-- Radio options -->
              <div class="space-y-4">
                <!-- Subdomain option -->
                <div class="space-y-3">
                  <div
                    class="flex items-start space-x-3"
                    :class="{ 'opacity-50': isCollectiveAdmin }"
                  >
                    <input
                      type="radio"
                      id="subdomain"
                      value="subdomain"
                      v-model="networkMode"
                      :disabled="isCollectiveAdmin"
                      class="mt-1 h-4 w-4 text-primary border-gray-300 focus:ring-primary"
                    />
                    <div class="flex-1">
                      <Label
                        for="subdomain"
                        class="font-medium"
                        :class="isCollectiveAdmin ? 'cursor-not-allowed' : 'cursor-pointer'"
                      >
                        Use a URL provided by SyftHub
                        <Badge v-if="isCollectiveAdmin" variant="outline" class="ml-2">
                          Unavailable for collectives
                        </Badge>
                        <Badge v-else variant="secondary" class="ml-2">Recommended</Badge>
                      </Label>
                    </div>
                  </div>
                </div>

                <!-- Custom domain option -->
                <div class="space-y-3">
                  <div class="flex items-start space-x-3">
                    <input
                      type="radio"
                      id="custom"
                      value="custom"
                      v-model="networkMode"
                      class="mt-1 h-4 w-4 text-primary border-gray-300 focus:ring-primary"
                    />
                    <div class="space-y-1 flex-1">
                      <Label for="custom" class="font-medium cursor-pointer">
                        {{ isCollectiveAdmin ? 'Use my collective URL' : 'I have my own URL' }}
                        <Badge :variant="isCollectiveAdmin ? 'secondary' : 'outline'" class="ml-2">
                          {{ isCollectiveAdmin ? 'Required' : 'Advanced' }}
                        </Badge>
                      </Label>
                      <p class="body-sm text-muted-foreground">
                        {{
                          isCollectiveAdmin
                            ? 'Members will use this URL to access the collective space'
                            : "If you've already set up port forwarding or have a public URL"
                        }}
                      </p>
                    </div>
                  </div>

                  <!-- Custom domain conditional field -->
                  <div v-if="networkMode === 'custom'" class="ml-7 space-y-2">
                    <Label for="custom-domain">Your Public URL</Label>
                    <Input
                      id="custom-domain"
                      v-model="publicUrl"
                      type="url"
                      placeholder="https://my-space.example.com"
                    />
                    <p class="body-sm text-muted-foreground">
                      Enter the complete web address where your Syft Space can be reached
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <!-- Separator -->
            <Separator />

            <!-- Diagnostics opt-in -->
            <div class="space-y-3">
              <div class="flex items-start space-x-3">
                <Checkbox id="diagnostics" v-model="diagnosticsOptIn" class="mt-0.5" />
                <Label
                  for="diagnostics"
                  class="text-sm text-foreground cursor-pointer leading-snug"
                >
                  Share anonymous usage data. You can change this anytime in Settings.
                </Label>
              </div>
              <Alert>
                <Info class="h-4 w-4" />
                <AlertDescription>
                  We're in beta — help us find bugs and improve Syft Space faster. No personal data
                  is ever collected.
                </AlertDescription>
              </Alert>
            </div>

            <!-- Error displays -->
            <Alert v-if="authError" variant="destructive">
              <AlertDescription>{{ authError }}</AlertDescription>
            </Alert>
            <Alert v-if="networkError" variant="destructive">
              <AlertDescription>{{ networkError }}</AlertDescription>
            </Alert>

            <!-- Submit button -->
            <Button
              type="submit"
              :disabled="!isSetupValid || isSubmitting"
              class="w-full"
              size="lg"
            >
              <Loader2 v-if="isSubmitting" class="mr-2 h-4 w-4 animate-spin" />
              {{ isAlreadyRegistered ? 'Configure Network' : 'Complete Setup' }}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { CheckCircle, XCircle, Loader2, ExternalLink, Info } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { settingsApi } from '@/api/endpoints/settings'
import { setDiagnosticsEnabled } from '@/lib/sentry'
import { setPosthogDiagnosticsEnabled } from '@/lib/posthog'
import { useOnboarding } from '@/composables/useOnboarding'
import { useCollectiveMode } from '@/composables/useCollectiveMode'
import { loadGlobalData } from '@/lib/utils'
import { checkOnboardingStatus, clearOnboardingCache } from '@/router'

const router = useRouter()
const route = useRoute()
const { isCollectiveAdmin } = useCollectiveMode()

// Check if already onboarded and redirect, or load partial state
onMounted(async () => {
  const isOnboarded = await checkOnboardingStatus()
  if (isOnboarded) {
    const nextUrl = route.query.next as string | undefined
    if (nextUrl) {
      router.replace(nextUrl)
    } else {
      router.replace({ name: 'home' })
    }
    return
  }

  // Not fully onboarded — check if registration already completed
  await loadExistingState()

  // Load current diagnostics preference
  try {
    const res = await settingsApi.getDiagnostics()
    diagnosticsOptIn.value = res.enabled
  } catch {
    // Default to false if fetch fails
  }
})

// Use onboarding composable
const {
  authMode,
  registerForm,
  signinForm,
  networkMode,
  publicUrl,
  checkingUsername,
  usernameAvailable,
  authError,
  networkError,
  marketplaceData,
  checkUsernameAvailability,
  register,
  signIn,
  completeSetup,
  loadExistingState,
} = useOnboarding()

// Additional form state
const confirmPassword = ref('')
const isSubmitting = ref(false)
const diagnosticsOptIn = ref(false)

// Computed properties
const isRegisterFormValid = computed(() => {
  return (
    registerForm.value.username.trim() !== '' &&
    registerForm.value.email.trim() !== '' &&
    registerForm.value.name.trim() !== '' &&
    registerForm.value.password.length >= 8 &&
    registerForm.value.password === confirmPassword.value &&
    usernameAvailable.value === true
  )
})

const isSignInFormValid = computed(() => {
  return signinForm.value.username.trim() !== '' && signinForm.value.password.trim() !== ''
})

const isNetworkSetupValid = computed(() => {
  if (networkMode.value === 'subdomain') {
    return true
  }
  if (networkMode.value === 'custom') {
    return publicUrl.value.trim() !== '' && publicUrl.value.startsWith('http')
  }
  return false
})

const isSetupValid = computed(() => {
  if (isAlreadyRegistered.value) {
    return isNetworkSetupValid.value
  }

  const accountValid =
    authMode.value === 'register' ? isRegisterFormValid.value : isSignInFormValid.value

  return isNetworkSetupValid.value && accountValid
})

const handleUsernameInput = () => {
  const username = registerForm.value.username.trim()
  if (username) {
    checkUsernameAvailability(username)
  } else {
    // Reset availability state when username is empty
    usernameAvailable.value = null
  }
}

const isAlreadyRegistered = computed(() => marketplaceData.value !== null)

watch(
  isCollectiveAdmin,
  (enabled) => {
    if (enabled) {
      networkMode.value = 'custom'
    }
  },
  { immediate: true },
)

const handleCompleteSetup = async () => {
  isSubmitting.value = true

  try {
    // Skip auth if already registered (retry after network failure)
    if (!isAlreadyRegistered.value) {
      let authSuccess = false
      if (authMode.value === 'register') {
        authSuccess = await register()
      } else {
        authSuccess = await signIn()
      }

      if (!authSuccess) {
        isSubmitting.value = false
        return
      }
    }

    // Complete the setup
    const setupSuccess = await completeSetup()
    if (setupSuccess) {
      // Save diagnostics preference and update Sentry
      await settingsApi.updateDiagnostics({ enabled: diagnosticsOptIn.value })
      setDiagnosticsEnabled(diagnosticsOptIn.value)
      setPosthogDiagnosticsEnabled(diagnosticsOptIn.value)

      // Clear cache so next check gets fresh status
      clearOnboardingCache()

      // Fetch global data now that onboarding is complete
      await loadGlobalData()

      // Redirect to the original destination or home
      const nextUrl = route.query.next as string | undefined
      if (nextUrl) {
        router.push(nextUrl)
      } else {
        router.push({ name: 'home' })
      }
    }
  } finally {
    isSubmitting.value = false
  }
}
</script>
