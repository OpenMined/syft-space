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
            <p class="text-sm text-muted-foreground">Configure how others can access your space</p>
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
              <div class="flex-1">
                <Label for="subdomain" class="font-medium cursor-pointer">
                  Use a URL provided by SyftHub
                  <Badge variant="secondary" class="ml-2">Recommended</Badge>
                </Label>
              </div>
            </div>

            <!-- Subdomain conditional content -->
            <div v-if="networkMode === 'subdomain'" class="ml-7">
              <div class="p-4 bg-muted/50 rounded-lg border space-y-3">
                <div class="flex items-center gap-2">
                  <div
                    class="h-2 w-2 rounded-full"
                    :class="proxyStatus.connected ? 'bg-green-500' : 'bg-yellow-500'"
                  />
                  <span class="text-sm font-medium">
                    {{ proxyStatus.connected ? 'Connected' : 'Disconnected' }}
                  </span>
                </div>

                <div v-if="proxyStatus.publicUrl" class="text-sm">
                  <span class="text-muted-foreground">Public URL:</span>
                  <a
                    :href="proxyStatus.publicUrl"
                    target="_blank"
                    class="ml-2 bg-muted px-2 py-0.5 rounded text-xs font-mono hover:bg-muted/80 inline-flex items-center gap-1"
                  >
                    {{ proxyStatus.publicUrl }}
                    <ExternalLink class="h-3 w-3" />
                  </a>
                </div>
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
                v-model="customUrl"
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
        <Button :disabled="saving" @click="saveChanges">
          <Loader2 v-if="saving" class="h-4 w-4 mr-2 animate-spin" />
          Save Changes
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Settings, Globe, User, ExternalLink, Loader2 } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
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
const saving = ref(false)
const networkMode = ref<'subdomain' | 'custom'>('subdomain')
const customUrl = ref(window.location.origin)

const proxyStatus = reactive({
  connected: false,
  publicUrl: null as string | null,
  hasToken: false,
})

const fetchAccountInfo = async () => {
  loadingAccount.value = true
  try {
    await userStore.fetchMarketplaceInfo()
  } finally {
    loadingAccount.value = false
  }
}

const fetchNetworkConfig = async () => {
  loadingNetwork.value = true
  try {
    const [publicUrlRes, proxyRes] = await Promise.all([
      settingsApi.getPublicUrl(),
      settingsApi.getProxyStatus(),
    ])

    proxyStatus.connected = proxyRes.connected
    proxyStatus.publicUrl = proxyRes.public_url
    proxyStatus.hasToken = proxyRes.has_token

    if (proxyRes.has_token) {
      networkMode.value = 'subdomain'
    } else if (publicUrlRes.public_url) {
      networkMode.value = 'custom'
      customUrl.value = publicUrlRes.public_url
    }
  } catch {
    // If API fails, keep default subdomain mode
  } finally {
    loadingNetwork.value = false
  }
}

const saveChanges = async () => {
  saving.value = true
  try {
    if (networkMode.value === 'subdomain') {
      if (!proxyStatus.connected) {
        const result = await settingsApi.configureProxy()
        proxyStatus.connected = result.connected
        proxyStatus.publicUrl = result.public_url
        proxyStatus.hasToken = result.has_token
        toast.success('Proxy configured successfully')
      }
    } else {
      if (!customUrl.value) {
        toast.error('Please enter your public URL')
        return
      }

      if (proxyStatus.hasToken) {
        await settingsApi.disconnectProxy()
        proxyStatus.connected = false
        proxyStatus.publicUrl = null
        proxyStatus.hasToken = false
      }

      await settingsApi.updatePublicUrl({ public_url: customUrl.value })
      toast.success('Public URL updated successfully')
    }
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to save settings')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  fetchAccountInfo()
  fetchNetworkConfig()
})
</script>
