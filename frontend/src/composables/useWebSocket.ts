import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'

export function useWebSocket() {
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null
  let pingTimer: number | null = null
  let reconnectAttempts = 0
  const maxReconnectAttempts = 5

  function buildUrl(storeId: string, token: string) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws/${storeId}?token=${encodeURIComponent(token)}`
  }

  function connect() {
    const auth = useAuthStore()
    if (!auth.accessToken || !auth.user?.storeId) return
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return

    ws = new WebSocket(buildUrl(auth.user.storeId, auth.accessToken))

    ws.onopen = () => {
      connected.value = true
      reconnectAttempts = 0
    }

    ws.onmessage = (event) => {
      if (event.data === 'pong') return
      try {
        const data = JSON.parse(event.data)
        const notif = useNotificationStore()
        notif.push({
          type: data.type || 'system',
          payload: data,
          readAt: null,
        })
      } catch {
        // 忽略非 JSON 消息。
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null
      if (reconnectAttempts < maxReconnectAttempts) {
        const delay = Math.min(1000 * 2 ** reconnectAttempts, 16000)
        reconnectTimer = window.setTimeout(() => {
          reconnectAttempts += 1
          connect()
        }, delay)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
    connected.value = false
  }

  function startPing() {
    if (pingTimer) clearInterval(pingTimer)
    pingTimer = window.setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000)
  }

  onMounted(() => {
    const auth = useAuthStore()
    watch(
      () => [auth.accessToken, auth.user?.storeId],
      ([token, storeId]) => {
        disconnect()
        if (token && storeId) connect()
      },
      { immediate: true },
    )
    startPing()
  })

  onUnmounted(() => {
    if (pingTimer) clearInterval(pingTimer)
    disconnect()
  })

  return { connected }
}
