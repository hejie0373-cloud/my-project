import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { NotificationMsg } from '@/types/analytics'

export const useNotificationStore = defineStore('notification', () => {
  const messages = ref<NotificationMsg[]>([])

  const unreadCount = computed(() => messages.value.filter((m) => !m.readAt).length)

  function push(msg: NotificationMsg) {
    messages.value.unshift(msg)
    // 最多保留 50 条
    if (messages.value.length > 50) {
      messages.value = messages.value.slice(0, 50)
    }
  }

  function markAllRead() {
    const now = new Date().toISOString()
    messages.value.forEach((m) => {
      if (!m.readAt) m.readAt = now
    })
  }

  function clear() {
    messages.value = []
  }

  return { messages, unreadCount, push, markAllRead, clear }
})
