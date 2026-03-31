<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ArrowDownLeft, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { walletsApi } from '@/api/endpoints/wallets'
import { useUserStore } from '@/stores/user'
import { formatPrice, truncateEmail, formatTimeAgo } from '@/lib/formatters'
import type { TransactionResponse } from '@/api/types'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const allTransactions = ref<TransactionResponse[]>([])
const loading = ref(false)
const error = ref(false)
const currentPage = ref(1)
const pageSize = 10

const totalPages = computed(() => Math.ceil(allTransactions.value.length / pageSize))
const total = computed(() => allTransactions.value.length)

const paginatedTransactions = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return allTransactions.value.slice(start, end)
})

const userStore = useUserStore()

const fetchTransactions = async () => {
  if (!userStore.walletId) {
    allTransactions.value = []
    return
  }
  loading.value = true
  error.value = false
  try {
    allTransactions.value = await walletsApi.getMppTransactions(userStore.walletId)
    currentPage.value = 1
  } catch (e) {
    console.error('Failed to fetch transactions:', e)
    error.value = true
    allTransactions.value = []
  } finally {
    loading.value = false
  }
}

const goToPage = (page: number) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && allTransactions.value.length === 0) {
      fetchTransactions()
    }
  },
)


</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>Transaction History</DialogTitle>
      </DialogHeader>

      <div class="space-y-4">
        <!-- Loading state -->
        <template v-if="loading">
          <div v-for="i in 5" :key="i" class="flex items-center gap-3 py-2">
            <Skeleton class="h-10 w-10 rounded-full" />
            <div class="flex-1 space-y-1.5">
              <Skeleton class="h-4 w-40" />
              <Skeleton class="h-3 w-24" />
            </div>
            <Skeleton class="h-4 w-14" />
          </div>
        </template>

        <!-- Error state -->
        <div v-else-if="error" class="text-center py-8">
          <p class="text-sm text-destructive">Failed to load transactions</p>
          <Button variant="outline" size="sm" class="mt-2" @click="fetchTransactions">
            Try again
          </Button>
        </div>

        <!-- Empty state -->
        <div v-else-if="allTransactions.length === 0" class="text-center py-8">
          <p class="text-sm text-muted-foreground">No transactions found</p>
        </div>

        <!-- Transaction list -->
        <div v-else class="space-y-1">
          <div
            v-for="transaction in paginatedTransactions"
            :key="transaction.id"
            class="flex items-center gap-3 py-2 px-2 rounded-lg hover:bg-muted/50"
          >
            <div
              class="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center flex-shrink-0"
            >
              <ArrowDownLeft class="h-4 w-4 text-green-600 dark:text-green-400" />
            </div>
            <div class="flex-1 min-w-0">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <p class="text-sm font-medium truncate cursor-default">
                      From {{ truncateEmail(transaction.sender_email, 10) }}
                    </p>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{{ transaction.sender_email }}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <span class="text-xs text-muted-foreground cursor-default">
                      {{ formatTimeAgo(transaction.created_at) }}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{{ new Date(transaction.created_at).toLocaleString() }}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
            <span class="text-sm font-semibold text-green-600 dark:text-green-400">
              +${{ formatPrice(transaction.amount) }}
            </span>
          </div>
        </div>

        <!-- Pagination -->
        <div
          v-if="!loading && !error && allTransactions.length > 0"
          class="flex items-center justify-between pt-2 border-t border-border"
        >
          <p class="text-sm text-muted-foreground">
            Page {{ currentPage }} of {{ totalPages }} ({{ total }} total)
          </p>
          <div v-if="totalPages > 1" class="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              class="h-8 w-8"
              :disabled="currentPage <= 1"
              @click="goToPage(currentPage - 1)"
            >
              <ChevronLeft class="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              class="h-8 w-8"
              :disabled="currentPage >= totalPages"
              @click="goToPage(currentPage + 1)"
            >
              <ChevronRight class="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
