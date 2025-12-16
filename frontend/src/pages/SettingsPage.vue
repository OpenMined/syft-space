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
      <!-- Wallet Manager Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="p-2 bg-primary/10 rounded-md">
            <Shield class="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-medium text-foreground">Wallet Manager</h3>
            <p class="text-sm text-muted-foreground">
              Configure your wallet management settings and authentication
            </p>
          </div>
        </div>

        <!-- Warning Alert -->
        <div
          class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6 dark:bg-yellow-950 dark:border-yellow-800"
        >
          <div class="flex items-start gap-3">
            <AlertCircle class="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
            <p class="text-sm text-yellow-800 dark:text-yellow-200">
              Please ensure you fully trust this wallet manager as it handles financial transactions
            </p>
          </div>
        </div>

        <!-- Form Fields -->
        <div class="space-y-6">
          <!-- Manager URL -->
          <div class="space-y-2">
            <Label for="manager-url" class="text-sm font-medium">Manager URL</Label>
            <div class="relative">
              <Input
                id="manager-url"
                type="url"
                v-model="userStore.walletManagerUrl"
                placeholder="https://payments.openmined.org"
                class="pr-10"
              />
              <Copy
                class="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground cursor-pointer hover:text-foreground"
              />
            </div>
          </div>

          <!-- Email Address -->
          <div class="space-y-2">
            <Label for="email" class="text-sm font-medium">Email Address</Label>
            <Input
              id="email"
              type="email"
              v-model="userStore.email"
              placeholder="Enter your email address"
            />
          </div>

          <!-- Auth Token -->
          <div class="space-y-2">
            <Label for="auth-token" class="text-sm font-medium">Auth Token</Label>
            <Input
              id="auth-token"
              type="password"
              v-model="userStore.authToken"
              placeholder="Enter your authentication token"
            />
          </div>
        </div>
      </div>

      <!-- Collectives Section -->
      <div class="bg-card border border-border rounded-xl p-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="p-2 bg-primary/10 rounded-md">
            <Users class="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-medium text-foreground">Collectives</h3>
            <p class="text-sm text-muted-foreground">
              Collectives you are a member of
            </p>
          </div>
        </div>

        <!-- Collectives List -->
        <div v-if="collectives.length > 0" class="space-y-3">
          <div
            v-for="collective in collectives"
            :key="collective.id"
            class="flex items-center justify-between p-4 bg-muted/50 rounded-lg border border-border"
          >
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Users class="h-5 w-5 text-primary" />
              </div>
              <div>
                <h4 class="font-medium text-foreground">{{ collective.name }}</h4>
                <p class="text-sm text-muted-foreground">{{ collective.domain }}</p>
              </div>
            </div>
            <Badge :variant="collective.role === 'admin' ? 'default' : 'secondary'">
              {{ collective.role }}
            </Badge>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="text-center py-8 border-2 border-dashed border-border rounded-lg">
          <Users class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <p class="text-sm text-muted-foreground">You are not a member of any collectives yet</p>
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
import { Settings, Shield, AlertCircle, Copy, Users } from 'lucide-vue-next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useUserStore } from '@/stores/user'
import { ref } from 'vue'

const userStore = useUserStore()

// Mock collectives data - in real app, this would come from an API
const collectives = ref([
  {
    id: '1',
    name: 'Harvard',
    domain: 'irina.harvard.syftbox.net',
    role: 'member',
  },
  {
    id: '2',
    name: 'TCP Collective',
    domain: 'irina.tcp-collective.syftbox.net',
    role: 'admin',
  },
])
</script>
