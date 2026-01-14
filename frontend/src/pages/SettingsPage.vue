<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center gap-3 mb-3">
        <Settings class="h-6 w-6 text-primary" />
        <h1 class="heading-3">Settings</h1>
      </div>
      <p class="text-lg text-muted-foreground">Configure your workspace preferences</p>
    </div>

    <!-- Content -->
    <div class="space-y-6">
      <!-- SyftHub Account Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="p-2 bg-primary/10 rounded-md">
            <User class="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-medium text-foreground">Account Details</h3>
            <a
              v-if="userStore.marketplaceUrl"
              :href="`${userStore.marketplaceUrl.replace(/\/$/, '')}/profile`"
              target="_blank"
              class="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
            >
              View on SyftHub
              <ExternalLink class="h-3 w-3" />
            </a>
            <p v-else class="text-sm text-muted-foreground">
              Your connected SyftHub account details
            </p>
          </div>
        </div>

        <!-- Loading skeleton -->
        <div v-if="loadingAccount" class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div v-for="i in 3" :key="i" class="space-y-2">
            <Skeleton class="h-4 w-16" />
            <Skeleton class="h-5 w-32" />
          </div>
        </div>

        <!-- Loaded content -->
        <div v-else class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Name -->
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Name</p>
            <p class="text-sm font-medium text-foreground">
              {{ userStore.name || '--' }}
            </p>
          </div>

          <!-- Username -->
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Username</p>
            <p class="text-sm font-medium text-foreground">
              {{ userStore.username || '--' }}
            </p>
          </div>

          <!-- Email -->
          <div class="space-y-1">
            <p class="text-sm text-muted-foreground">Email</p>
            <p class="text-sm font-medium text-foreground">
              {{ userStore.email || '--' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Network Configuration Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="p-2 bg-primary/10 rounded-md">
            <Globe class="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-medium text-foreground">Network Configuration</h3>
            <p class="text-sm text-muted-foreground">
              Configure how others can access your space
            </p>
          </div>
        </div>

        <!-- Loading skeleton -->
        <div v-if="loadingNetwork" class="space-y-4">
          <div v-for="i in 2" :key="i" class="flex items-start space-x-3">
            <Skeleton class="h-4 w-4 rounded-full mt-1" />
            <div class="space-y-2 flex-1">
              <Skeleton class="h-5 w-48" />
              <Skeleton class="h-4 w-64" />
            </div>
          </div>
        </div>

        <!-- Radio options -->
        <div v-else class="space-y-4">
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
                <p class="text-sm text-muted-foreground">
                  Your space is accessible at
                  <code class="bg-muted px-2 py-0.5 rounded text-xs">
                    https://{{ userStore.username || 'yourusername' }}.syfthub.net
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
                <p class="text-sm text-muted-foreground">
                  Use this if you've already set up port forwarding or have a public URL
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
              <p class="text-sm text-muted-foreground">
                Enter the complete web address where your Syft Space can be reached
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Save Button -->
      <div class="mt-8 flex justify-end">
        <Button> Save Changes </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Settings, Globe, User, ExternalLink } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useUserStore } from '@/stores/user'
import { settingsApi } from '@/api/endpoints/settings'

const userStore = useUserStore()

const loadingAccount = ref(true)
const loadingNetwork = ref(true)
const networkMode = ref<'subdomain' | 'custom'>('subdomain')
const devToken = ref('')
const publicUrl = ref('')

const fetchAccountInfo = async () => {
  loadingAccount.value = true
  try {
    await Promise.all([userStore.fetchMarketplaceInfo(), userStore.fetchBalance()])
  } finally {
    loadingAccount.value = false
  }
}

const fetchPublicUrl = async () => {
  loadingNetwork.value = true
  try {
    const response = await settingsApi.getPublicUrl()
    if (response.public_url) {
      publicUrl.value = response.public_url
      networkMode.value = 'custom'
    }
  } catch {
    // If API fails, keep default subdomain mode
  } finally {
    loadingNetwork.value = false
  }
}

onMounted(() => {
  fetchAccountInfo()
  fetchPublicUrl()
})
</script>
