<script setup lang="ts">
import { ref } from 'vue'

const activeTab = ref<'services' | 'inbox' | 'usage' | 'settings'>('services')

const showUserDropdown = ref(false)
const hasWalletManager = ref(true) // This would come from your API/state management

const handleTabChange = (tab: 'services' | 'inbox' | 'usage' | 'settings') => {
  activeTab.value = tab
}
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
          SyftNSAI 
          <span class="ml-1 text-xs font-semibold text-purple-600 align-top">ALPHA</span>
        </span>
      </div>

      <!-- Navigation Tabs -->
      <nav class="flex items-center space-x-2 flex-grow justify-center">
        <button
          @click="handleTabChange('services')"
          :class="[
            'px-4 py-2 rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500',
            activeTab === 'services'
              ? 'text-purple-700 bg-purple-50'
              : 'text-gray-700 hover:bg-gray-100'
          ]"
        >
          Services
        </button>
        <button
          @click="handleTabChange('inbox')"
          :class="[
            'px-4 py-2 rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500',
            activeTab === 'inbox'
              ? 'text-purple-700 bg-purple-50'
              : 'text-gray-700 hover:bg-gray-100'
          ]"
        >
          Inbox
        </button>
        <button
          @click="handleTabChange('usage')"
          :class="[
            'px-4 py-2 rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500',
            activeTab === 'usage'
              ? 'text-purple-700 bg-purple-50'
              : 'text-gray-700 hover:bg-gray-100'
          ]"
        >
          Usage
        </button>
        <button
          @click="handleTabChange('settings')"
          :class="[
            'px-4 py-2 rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-purple-500',
            activeTab === 'settings'
              ? 'text-purple-700 bg-purple-50'
              : 'text-gray-700 hover:bg-gray-100'
          ]"
        >
          Settings
        </button>
      </nav>
      
      <!-- Right side controls -->
      <div class="flex items-center space-x-3">
        <!-- Create Service Button -->
        <button
          class="flex items-center space-x-2 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          <span>Create Service</span>
        </button>
        
        <!-- Avatar with Dropdown -->
        <div class="relative">
          <button
            @click="showUserDropdown = !showUserDropdown"
            class="flex items-center justify-center h-10 w-10 rounded-lg bg-gray-200 hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <svg class="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </button>
          
          <!-- Dropdown Menu -->
          <div 
            v-if="showUserDropdown"
            class="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-gray-200 z-50"
          >
            <div class="p-4">
              <div class="mb-4">
                <p class="text-sm text-gray-500">Email</p>
                <p class="text-sm font-medium text-gray-900">tauquir@openmined.org</p>
              </div>
              
              <div class="mb-4">
                <p class="text-sm text-gray-500">Balance</p>
                <p v-if="hasWalletManager" class="text-lg font-semibold text-green-600">$87.20</p>
                <p v-else class="text-sm font-medium text-red-600">Missing</p>
              </div>
              
              <div>
                <p class="text-sm text-gray-500">Wallet Manager</p>
                <a v-if="hasWalletManager" 
                   href="https://payments.openmined.org" 
                   target="_blank"
                   class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">
                  https://payments.openmined.org
                </a>
                <p v-else class="text-sm font-medium text-gray-600">Not registered</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>