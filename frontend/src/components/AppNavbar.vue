<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, ExternalLink } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const currentRouteName = computed(() => route.name as string)

const navigateTo = (routeName: string) => {
  router.push({ name: routeName })
}

const tabs = [
  { id: 'services', label: 'My Services' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'usage', label: 'Usage' },
  { id: 'settings', label: 'Settings' }
]
</script>

<template>
  <header class="bg-white shadow-sm border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-16 gap-6">
      <!-- Logo and App Name -->
      <div class="flex items-center space-x-3">
        <div class="h-8 w-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-lg">S</span>
        </div>
        <span class="text-xl font-bold text-gray-900 tracking-tight">
          SyftAI Server 
          <span class="ml-1 text-xs font-semibold text-purple-600 align-top">BETA</span>
        </span>
      </div>

      <!-- Navigation Tabs -->
      <nav class="flex items-center space-x-2 flex-grow justify-center">
        <Button
          v-for="tab in tabs"
          :key="tab.id"
          @click="navigateTo(tab.id)"
          :variant="currentRouteName === tab.id ? 'secondary' : 'ghost'"
          size="sm"
          class="text-sm font-medium"
          :class="[
            currentRouteName === tab.id 
              ? 'text-purple-700 bg-purple-50 hover:bg-purple-100' 
              : 'text-gray-700 hover:bg-gray-100'
          ]"
        >
          {{ tab.label }}
        </Button>
      </nav>
      
      <!-- Right side controls -->
      <div class="flex items-center space-x-3">
        <!-- Balance Display -->
        <div class="flex items-center gap-2 bg-gray-50 px-3 py-1.5 rounded-lg">
          <span class="text-sm text-gray-600">Balance:</span>
          <span class="text-sm font-semibold text-green-600">{{ userStore.balance }}</span>
        </div>
        
        <!-- Avatar with Dropdown -->
        <DropdownMenu>
          <DropdownMenuTrigger as-child>
            <Button variant="ghost" size="icon" class="h-10 w-10 rounded-lg">
              <Avatar class="h-8 w-8">
                <AvatarFallback class="bg-gray-200 text-gray-600">
                  <User class="h-4 w-4" />
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent class="w-56 bg-white border border-gray-200 shadow-lg" align="end">
            <div class="p-4 space-y-4">
              <div>
                <p class="text-sm text-gray-500 mb-0.5">Email</p>
                <p class="text-sm font-medium text-gray-900">{{ userStore.email }}</p>
              </div>
              <div>
                <p class="text-sm text-gray-500 mb-0.5">Wallet Manager</p>
                <a 
                  :href="userStore.walletManagerUrl" 
                  target="_blank"
                  class="text-sm font-medium text-gray-900 hover:text-gray-700 inline-flex items-center gap-1.5"
                >
                  {{ userStore.walletManagerUrl.replace('https://', '') }}
                  <ExternalLink class="h-3 w-3 text-gray-400" />
                </a>
              </div>
            </div>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  </header>
</template>