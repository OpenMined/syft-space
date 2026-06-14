<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
    <template v-if="isCollectiveViewActive">
      <div class="mb-12">
        <div class="flex items-center gap-3 mb-3">
          <UsersRound class="h-6 w-6 text-primary" />
          <h1 class="text-2xl font-semibold tracking-tight text-foreground">Members</h1>
        </div>
        <p class="body-lg text-muted-foreground md:max-w-[68%]">
          Members of the collective you are running who are your tenants: they are running a virtual
          Syft Space on your system.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Collective members</CardTitle>
        </CardHeader>
        <CardContent class="p-0">
          <div class="divide-y divide-border">
            <div
              v-for="member in collectiveMembers"
              :key="member.id"
              class="grid grid-cols-1 lg:grid-cols-[1.4fr_0.8fr] gap-4 px-6 py-5"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <p class="font-medium text-foreground truncate">{{ member.name }}</p>
                  <Badge :variant="member.role === 'Admin' ? 'default' : 'outline'" class="text-xs">
                    {{ member.role }}
                  </Badge>
                </div>
                <p class="text-sm text-muted-foreground truncate mt-1">{{ member.email }}</p>
              </div>

              <div>
                <p class="text-xs uppercase tracking-wider text-muted-foreground mb-1">Status</p>
                <div class="flex items-center gap-2">
                  <span class="h-2 w-2 rounded-full" :class="statusDotClass(member.status)" />
                  <span class="text-sm font-medium">{{ member.status }}</span>
                </div>
                <p class="text-xs text-muted-foreground mt-1">
                  {{ statusDetail(member) }}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </template>

    <div v-else class="max-w-xl mx-auto text-center py-20">
      <UsersRound class="h-10 w-10 text-muted-foreground mx-auto mb-4" />
      <h1 class="text-2xl font-semibold tracking-tight text-foreground mb-3">Members</h1>
      <p class="text-muted-foreground">
        Members management appears when Syft Space is booted in collective admin mode.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { UsersRound } from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCollectiveMode } from '@/composables/useCollectiveMode'
import { collectiveMembers, type CollectiveMember } from '@/stores/mockCollective'

const { isCollectiveViewActive } = useCollectiveMode()

const statusDotClass = (status: CollectiveMember['status']) => {
  return status === 'Active' ? 'bg-green-500' : 'bg-muted-foreground'
}

const statusDetail = (member: CollectiveMember) => {
  if (member.status === 'Active') {
    return `Active ${member.lastActive}`
  }
  return `Last active ${member.lastActive}`
}
</script>
