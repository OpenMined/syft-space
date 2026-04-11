import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export interface InboxItem {
  id: string
  source: string
  title: string
  summary: string
  longDescription: string
  timestamp: Date
  read: boolean
  dismissed: boolean
  actions?: {
    positive?: {
      label: string
      handler: () => void
    }
    negative?: {
      label: string
      handler: () => void
    }
  }
}

export const useInboxStore = defineStore('inbox', () => {
  const inboxItems = ref<InboxItem[]>([])

  const activeItems = computed(() => {
    return inboxItems.value
      .filter((item) => !item.dismissed)
      .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
  })

  const unreadCount = computed(
    () => inboxItems.value.filter((item) => !item.dismissed && !item.read).length,
  )

  const markAsRead = (itemId: string) => {
    const item = inboxItems.value.find((item) => item.id === itemId)
    if (item) {
      item.read = true
    }
  }

  const dismissItem = (itemId: string) => {
    const item = inboxItems.value.find((item) => item.id === itemId)
    if (item) {
      item.dismissed = true
    }
  }

  return {
    inboxItems,
    activeItems,
    unreadCount,
    markAsRead,
    dismissItem,
  }
})
