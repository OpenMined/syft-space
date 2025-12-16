<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Hero Section -->
    <div class="mb-16">
      <h1 class="heading-1 font-light text-foreground mb-4">
        Welcome to
        <span class="font-medium text-primary">Collectives</span>
      </h1>
      <p class="body-lg text-muted-foreground max-w-2xl">
        Create and manage data collectives to organize communities, share infrastructure, and enable
        collaborative curation.
      </p>
    </div>

    <!-- Action Cards -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
      <Card
        class="cursor-pointer hover:shadow-lg transition-all border-2"
        @click="$router.push('/create')"
      >
        <CardContent class="p-6">
          <div class="flex flex-col items-center text-center">
            <div class="w-14 h-14 bg-primary/10 rounded-full flex items-center justify-center mb-4">
              <PlusCircle class="w-7 h-7 text-primary" />
            </div>
            <h3 class="heading-3 text-foreground mb-2">Create Collective</h3>
            <p class="body-sm text-muted-foreground">
              Start a new collective to organize your community
            </p>
          </div>
        </CardContent>
      </Card>

      <Card
        class="cursor-pointer hover:shadow-lg transition-all border-2"
        @click="$router.push('/collectives')"
      >
        <CardContent class="p-6">
          <div class="flex flex-col items-center text-center">
            <div
              class="w-14 h-14 bg-purple-100 dark:bg-purple-950/50 rounded-full flex items-center justify-center mb-4"
            >
              <Users class="w-7 h-7 text-purple-600 dark:text-purple-400" />
            </div>
            <h3 class="heading-3 text-foreground mb-2">Manage Collectives</h3>
            <p class="body-sm text-muted-foreground">
              View and manage your existing collectives
            </p>
          </div>
        </CardContent>
      </Card>

      <Card
        class="cursor-pointer hover:shadow-lg transition-all border-2"
        @click="$router.push('/requests')"
      >
        <CardContent class="p-6">
          <div class="flex flex-col items-center text-center">
            <div
              class="w-14 h-14 bg-orange-100 dark:bg-orange-950/50 rounded-full flex items-center justify-center mb-4"
            >
              <Inbox class="w-7 h-7 text-orange-600 dark:text-orange-400" />
            </div>
            <h3 class="heading-3 text-foreground mb-2">Review Requests</h3>
            <p class="body-sm text-muted-foreground">
              Approve or reject membership requests
            </p>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Recent Activity -->
    <div class="bg-card rounded-xl border border-border p-6">
      <h2 class="heading-3 mb-6">Your Collectives</h2>
      <div v-if="collectivesStore.collectives.length > 0" class="space-y-3">
        <Card
          v-for="collective in collectivesStore.collectives"
          :key="collective.id"
          class="cursor-pointer hover:shadow-md transition-all"
          @click="$router.push(`/collectives/${collective.slug}`)"
        >
          <CardContent class="p-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <Users class="h-6 w-6 text-primary" />
                </div>
                <div>
                  <h3 class="font-medium text-foreground">{{ collective.name }}</h3>
                  <p class="text-sm text-muted-foreground">{{ collective.domain }}</p>
                </div>
              </div>
              <Badge :variant="collective.role === 'admin' ? 'default' : 'secondary'">
                {{ collective.role }}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>
      <div v-else class="text-center py-8">
        <p class="text-muted-foreground">No collectives yet. Create your first one!</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Users, PlusCircle, Inbox, Activity } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useCollectivesStore } from '@/stores/collectives'

const collectivesStore = useCollectivesStore()
</script>

