<template>
  <div class="min-h-screen bg-background">
    <!-- Navigation -->
    <nav class="border-b border-border bg-card">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between h-16">
          <div class="flex items-center gap-8">
            <router-link to="/" class="flex items-center gap-3">
              <Users class="h-6 w-6 text-primary" />
              <span class="text-xl font-semibold text-foreground">Collectives</span>
            </router-link>
            
            <div class="hidden md:flex items-center gap-1">
              <router-link
                v-for="link in navLinks"
                :key="link.path"
                :to="link.path"
                class="px-3 py-2 rounded-md text-sm font-medium transition-colors"
                :class="$route.path === link.path
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'"
              >
                {{ link.name }}
              </router-link>
            </div>
          </div>

          <div class="flex items-center gap-4">
            <Button @click="() => $router.push('/create')" size="sm">
              <Plus class="h-4 w-4 mr-2" />
              New Collective
            </Button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { Users, Plus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const navLinks = [
  { name: 'Overview', path: '/' },
  { name: 'My Collectives', path: '/collectives' },
  { name: 'Requests', path: '/requests' },
]
</script>


