<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h1 class="heading-3 text-foreground mb-2">My Collectives</h1>
          <p class="body-lg text-muted-foreground">
            Manage your collectives and their members
          </p>
        </div>
        <Button @click="$router.push('/create')">
          <Plus class="h-4 w-4 mr-2" />
          New Collective
        </Button>
      </div>
    </div>

    <!-- Collectives Grid -->
    <div v-if="collectivesStore.collectives.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <Card
        v-for="collective in collectivesStore.collectives"
        :key="collective.id"
        class="cursor-pointer hover:shadow-lg transition-all"
        @click="$router.push(`/collectives/${collective.slug}`)"
      >
        <CardHeader>
          <div class="flex items-start justify-between">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                <Users class="h-6 w-6 text-primary" />
              </div>
              <div>
                <CardTitle class="text-lg">{{ collective.name }}</CardTitle>
                <Badge :variant="collective.role === 'admin' ? 'default' : 'secondary'" class="mt-1">
                  {{ collective.role }}
                </Badge>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <CardDescription class="mb-4">{{ collective.description }}</CardDescription>
          
          <div class="space-y-2 text-sm">
            <div class="flex items-center gap-2 text-muted-foreground">
              <Globe class="h-4 w-4" />
              <span>{{ collective.domain }}</span>
            </div>
            
            <div class="flex flex-wrap gap-2 mt-3">
              <Badge v-if="collective.capabilities.collectiveEndpoint" variant="outline" class="text-xs">
                <Zap class="h-3 w-3 mr-1" />
                Endpoint
              </Badge>
              <Badge v-if="collective.capabilities.multiTenancyHosting" variant="outline" class="text-xs">
                <Server class="h-3 w-3 mr-1" />
                Hosting
              </Badge>
              <Badge v-if="collective.capabilities.memberVetting" variant="outline" class="text-xs">
                <Shield class="h-3 w-3 mr-1" />
                Vetting
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-16">
      <div class="mx-auto w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-6">
        <Users class="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 class="heading-3 mb-3">No collectives yet</h3>
      <p class="body-base text-muted-foreground mb-6">
        Create your first collective to start organizing your community
      </p>
      <Button @click="$router.push('/create')">
        <Plus class="h-4 w-4 mr-2" />
        Create Collective
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Users, Plus, Globe, Zap, Server, Shield } from 'lucide-vue-next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useCollectivesStore } from '@/stores/collectives'

const collectivesStore = useCollectivesStore()
</script>


