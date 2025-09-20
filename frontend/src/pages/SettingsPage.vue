<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center gap-3 mb-2">
      <Settings class="h-6 w-6 text-gray-600" />
      <h1 class="text-2xl font-semibold text-gray-900">Settings</h1>
    </div>
    <p class="text-gray-600 mb-8">Manage your integrations and wallet configuration</p>

    <!-- Tabs -->
    <Tabs default-value="general" class="w-full">
      <TabsList class="h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground grid w-full grid-cols-3 lg:w-[400px] mb-8">
        <TabsTrigger value="general">General</TabsTrigger>
        <TabsTrigger value="integrations">Integrations</TabsTrigger>
        <TabsTrigger value="policies">Policies</TabsTrigger>
      </TabsList>

      <TabsContent value="general" class="space-y-6">
        <!-- Wallet Manager Section -->
        <div class="bg-white border border-gray-200 rounded-lg p-6">
          <div class="flex items-center gap-3 mb-6">
            <div class="p-2 bg-purple-100 rounded-md">
              <Shield class="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <h3 class="text-lg font-medium text-gray-900">Wallet Manager</h3>
              <p class="text-sm text-gray-600">Configure your wallet management settings and authentication</p>
            </div>
          </div>

          <!-- Warning Alert -->
          <div class="bg-yellow-50 border border-yellow-200 rounded-md p-4 mb-6">
            <div class="flex items-start gap-3">
              <AlertCircle class="h-5 w-5 text-yellow-600 mt-0.5" />
              <p class="text-sm text-yellow-800">Please ensure you fully trust this wallet manager as it handles financial transactions</p>
            </div>
          </div>

          <!-- Form Fields -->
          <div class="space-y-6">
            <!-- Manager URL -->
            <div class="space-y-2">
              <Label for="manager-url" class="text-sm font-medium text-gray-700">Manager URL</Label>
              <div class="relative">
                <Input
                  id="manager-url"
                  type="url"
                  v-model="userStore.walletManagerUrl"
                  placeholder="https://payments.openmined.org"
                  class="pr-10"
                />
                <Copy class="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 cursor-pointer hover:text-gray-600" />
              </div>
            </div>

            <!-- Email Address -->
            <div class="space-y-2">
              <Label for="email" class="text-sm font-medium text-gray-700">Email Address</Label>
              <Input
                id="email"
                type="email"
                v-model="userStore.email"
                placeholder="Enter your email address"
              />
            </div>

            <!-- Auth Token -->
            <div class="space-y-2">
              <Label for="auth-token" class="text-sm font-medium text-gray-700">Auth Token</Label>
              <Input
                id="auth-token"
                type="password"
                v-model="userStore.authToken"
                placeholder="Enter your authentication token"
              />
            </div>
          </div>
        </div>
      </TabsContent>

      <TabsContent value="integrations" class="space-y-6">
        <div class="bg-white border border-gray-200 rounded-lg p-6 min-h-[400px] flex items-center justify-center">
          <p class="text-gray-600">Integrations settings will be available soon.</p>
        </div>
      </TabsContent>

      <TabsContent value="policies" class="space-y-6">
        <div class="bg-white border border-gray-200 rounded-lg p-6 min-h-[400px] flex items-center justify-center">
          <p class="text-gray-600">Policies settings will be available soon.</p>
        </div>
      </TabsContent>
    </Tabs>

    <!-- Save Button -->
    <div class="mt-8 flex justify-end">
      <Button class="bg-purple-600 hover:bg-purple-700 text-white px-6 py-2">
        Save Changes
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Settings, Shield, AlertCircle, Copy } from 'lucide-vue-next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
</script>