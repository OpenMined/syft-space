<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
    <!-- Header -->
    <div class="mb-10">
      <h1 class="heading-3 text-foreground mb-2">Membership Requests</h1>
      <p class="body-lg text-muted-foreground">
        Review and respond to requests to join your collectives
      </p>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      <Card>
        <CardContent class="p-6">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-orange-100 dark:bg-orange-950/50 rounded-lg">
              <Inbox class="h-5 w-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <p class="text-2xl font-light text-foreground">{{ pendingRequests.length }}</p>
              <p class="text-sm text-muted-foreground">Pending</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="p-6">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-green-100 dark:bg-green-950/50 rounded-lg">
              <CheckCircle class="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p class="text-2xl font-light text-foreground">{{ approvedCount }}</p>
              <p class="text-sm text-muted-foreground">Approved</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent class="p-6">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-red-100 dark:bg-red-950/50 rounded-lg">
              <XCircle class="h-5 w-5 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <p class="text-2xl font-light text-foreground">{{ rejectedCount }}</p>
              <p class="text-sm text-muted-foreground">Rejected</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Pending Requests -->
    <div v-if="pendingRequests.length > 0" class="space-y-4">
      <Card
        v-for="request in pendingRequests"
        :key="request.id"
        class="hover:shadow-md transition-all"
      >
        <CardContent class="p-6">
          <div class="flex items-start justify-between">
            <div class="flex items-start gap-4 flex-1">
              <div class="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                <User class="h-6 w-6 text-primary" />
              </div>
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <h3 class="font-medium text-foreground">{{ request.userName }}</h3>
                  <Badge variant="outline" class="text-xs">{{ request.type }}</Badge>
                </div>
                <p class="text-sm text-muted-foreground mb-2">{{ request.userEmail }}</p>
                <div class="flex items-center gap-2 text-sm text-muted-foreground mb-3">
                  <Users class="h-4 w-4" />
                  <span>{{ request.collectiveName }}</span>
                  <span>•</span>
                  <Clock class="h-4 w-4" />
                  <span>{{ formatDate(request.createdAt) }}</span>
                </div>
                <p v-if="request.message" class="text-sm text-muted-foreground bg-muted p-3 rounded-lg">
                  {{ request.message }}
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                class="text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-950/50"
                @click="handleApprove(request.id)"
              >
                <Check class="h-4 w-4 mr-2" />
                Approve
              </Button>
              <Button
                variant="outline"
                size="sm"
                class="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/50"
                @click="handleReject(request.id)"
              >
                <X class="h-4 w-4 mr-2" />
                Reject
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>

    <!-- Empty State -->
    <div v-else class="text-center py-16">
      <div class="mx-auto w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-6">
        <Inbox class="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 class="heading-3 mb-3">No pending requests</h3>
      <p class="body-base text-muted-foreground">
        You're all caught up! New membership requests will appear here.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { User, Users, Inbox, Clock, Check, X, CheckCircle, XCircle } from 'lucide-vue-next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useCollectivesStore } from '@/stores/collectives'

const collectivesStore = useCollectivesStore()

const pendingRequests = computed(() => collectivesStore.getPendingRequests())
const approvedCount = computed(
  () => collectivesStore.requests.filter((r) => r.status === 'approved').length
)
const rejectedCount = computed(
  () => collectivesStore.requests.filter((r) => r.status === 'rejected').length
)

const formatDate = (date: Date) => {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (hours < 1) return 'Just now'
  if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`
  if (days < 7) return `${days} day${days > 1 ? 's' : ''} ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

const handleApprove = (requestId: string) => {
  collectivesStore.approveRequest(requestId)
}

const handleReject = (requestId: string) => {
  collectivesStore.rejectRequest(requestId)
}
</script>


