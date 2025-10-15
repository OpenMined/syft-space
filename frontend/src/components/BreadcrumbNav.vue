<template>
  <nav class="flex mb-6" aria-label="Breadcrumb">
    <ol class="flex items-center space-x-2">
      <li v-for="(item, index) in breadcrumbs" :key="index">
        <div v-if="index > 0" class="flex items-center">
          <ChevronRight class="h-4 w-4 text-gray-400 mx-2" />
        </div>

        <router-link
          v-if="item.route"
          :to="item.route"
          class="text-gray-500 hover:text-gray-700 text-sm font-medium flex items-center"
        >
          <component v-if="item.icon" :is="item.icon" class="h-4 w-4 mr-1" />
          {{ item.label }}
        </router-link>

        <span v-else class="text-gray-900 text-sm font-medium flex items-center">
          <component v-if="item.icon" :is="item.icon" class="h-4 w-4 mr-1" />
          {{ item.label }}
        </span>
      </li>
    </ol>
  </nav>
</template>

<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import type { Component } from 'vue'
import type { NavigationRoute } from '@/composables/useNavigation'

export interface BreadcrumbItem {
  label: string
  route?: NavigationRoute | string
  icon?: Component
}

interface Props {
  breadcrumbs: BreadcrumbItem[]
}

defineProps<Props>()
</script>
