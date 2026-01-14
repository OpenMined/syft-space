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
            <!-- Account type toggle -->
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
                    <XCircle v-else-if="usernameAvailable === false" class="h-4 w-4 text-red-600" />
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
                    'border-red-500': confirmPassword && registerForm.password !== confirmPassword,
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
                <Label for="signin-username">Username</Label>
                <Input id="signin-username" v-model="signinForm.username" placeholder="johndoe" />
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

            <!-- Separator -->
            <Separator />

            <!-- Network setup section -->
            <div class="space-y-4">
              <h3 class="heading-4 text-foreground">How should others access your space?</h3>

              <!-- Radio options -->
              <div class="space-y-4">
                <!-- Subdomain option -->
                <div class="space-y-3">
                  <div class="flex items-start space-x-3">
                    <input
                      type="radio"
                      id="subdomain"
                      value="subdomain"
                      v-model="networkMode"
                      class="mt-1 h-4 w-4 text-primary border-gray-300 focus:ring-primary"
                    />
                    <div class="space-y-1 flex-1">
                      <Label for="subdomain" class="font-medium cursor-pointer">
                        Use a subdomain provided by SyftHub
                        <Badge variant="secondary" class="ml-2">Recommended</Badge>
                      </Label>
                      <p class="body-sm text-muted-foreground">
                        We'll make your space accessible at
                        <code class="bg-muted px-2 py-0.5 rounded text-xs">
                          https://{{
                            registerForm.username || signinForm.username || 'yourusername'
                          }}.syfthub.net
                        </code>
                      </p>
                    </div>
                  </div>

                  <!-- Subdomain conditional field -->
                  <div v-if="networkMode === 'subdomain'" class="ml-7 space-y-2">
                    <Label for="dev-token">Developer Token</Label>
                    <Input
                      id="dev-token"
                      v-model="devToken"
                      type="password"
                      placeholder="Enter your SyftHub developer token"
                    />
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
                        I have my own URL
                        <Badge variant="outline" class="ml-2">Advanced</Badge>
                      </Label>
                      <p class="body-sm text-muted-foreground">
                        If you've already set up port forwarding or have a public URL
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
              Complete Setup
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { CheckCircle, XCircle, Loader2, ExternalLink } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { useOnboarding } from '@/composables/useOnboarding'

const router = useRouter()
const route = useRoute()

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
  checkUsernameAvailability,
  register,
  signIn,
  completeSetup,
} = useOnboarding()

// Additional form state
const devToken = ref('')
const confirmPassword = ref('')
const isSubmitting = ref(false)

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
    return devToken.value.trim() !== ''
  }
  if (networkMode.value === 'custom') {
    return publicUrl.value.trim() !== '' && publicUrl.value.startsWith('http')
  }
  return false
})

const isSetupValid = computed(() => {
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

const handleCompleteSetup = async () => {
  isSubmitting.value = true

  try {
    // First, authenticate
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

    // Update the public URL based on network mode
    if (networkMode.value === 'subdomain') {
      // For subdomain, construct the URL
      const username =
        authMode.value === 'register' ? registerForm.value.username : signinForm.value.username
      publicUrl.value = `https://${username}.syfthub.net`
    }
    // For custom domain, publicUrl is already set by user input

    // Complete the setup
    const setupSuccess = await completeSetup()
    if (setupSuccess) {
      // TODO: Save the devToken if using subdomain
      localStorage.setItem('isOnboarded', 'true')
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
