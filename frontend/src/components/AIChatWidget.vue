<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { askInsight } from '@/api/metrics'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const open = ref(false)
const question = ref('')
const loading = ref(false)
const suggestions = [
  '哪些客户最近最可能流失？',
  '本周适合做什么召回活动？',
  '怎么提升高价值客户复购？',
]

interface Msg { role: 'user' | 'ai'; text: string }
const messages = ref<Msg[]>([
  { role: 'ai', text: '你好！我是客留 AI 助手。关于你的店铺经营、客户留存、营销策略，有什么可以帮你的？' },
])
const chatBody = ref<HTMLElement | null>(null)

async function send() {
  const q = question.value.trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', text: q })
  question.value = ''
  loading.value = true
  await nextTick()
  scrollBottom()
  try {
    const { data } = await askInsight(q)
    messages.value.push({ role: 'ai', text: data.answer || '抱歉，暂时无法回答这个问题' })
  } catch {
    messages.value.push({ role: 'ai', text: '网络异常，请稍后重试。如果 AI 服务未配置，请检查 Dify 连接。' })
  } finally {
    loading.value = false
    await nextTick()
    scrollBottom()
  }
}

function askSuggestion(text: string) {
  question.value = text
  void send()
}

function clearChat() {
  messages.value = [
    { role: 'ai', text: '你好！我是客留 AI 助手。关于你的店铺经营、客户留存、营销策略，有什么可以帮你的？' },
  ]
}

function scrollBottom() {
  if (chatBody.value) {
    chatBody.value.scrollTop = chatBody.value.scrollHeight
  }
}
</script>

<template>
  <button v-if="!open" class="chat-fab" type="button" title="打开 AI 助手" @click="open = true">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
    </svg>
  </button>

  <Teleport to="body">
    <div v-if="open" class="chat-panel">
      <div class="chat-header">
        <div class="chat-header-left">
          <div class="chat-avatar">AI</div>
          <div>
            <div class="chat-title">客留 AI 助手</div>
            <div class="chat-subtitle">{{ auth.user?.name || '用户' }} 的店铺 · Dify 洞察</div>
          </div>
        </div>
        <div class="chat-actions">
          <button class="icon-btn" type="button" title="清空对话" @click="clearChat">清</button>
          <button class="icon-btn" type="button" title="关闭" @click="open = false">×</button>
        </div>
      </div>

      <div ref="chatBody" class="chat-body">
        <div class="suggestions">
          <button v-for="item in suggestions" :key="item" type="button" @click="askSuggestion(item)">
            {{ item }}
          </button>
        </div>
        <div v-for="(m, i) in messages" :key="i" :class="['chat-msg', m.role]">
          <div class="msg-bubble">{{ m.text }}</div>
        </div>
        <div v-if="loading" class="chat-msg ai">
          <div class="msg-bubble typing"><span></span><span></span><span></span></div>
        </div>
      </div>

      <div class="chat-footer">
        <textarea
          v-model="question"
          placeholder="输入问题，如：如何降低流失率？"
          class="chat-input"
          rows="1"
          @keyup.enter="send"
        />
        <button class="chat-send" type="button" :disabled="loading || !question.trim()" @click="send">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.chat-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 999;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #0072b2;
  color: #fff;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(0,114,178,0.28);
  transition: transform 0.2s, box-shadow 0.2s;
}
.chat-fab:hover { transform: scale(1.06); box-shadow: 0 6px 24px rgba(0,114,178,0.36); }

.chat-panel {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  width: 380px;
  height: 520px;
  background: #fff;
  border: 1px solid #dbe3ec;
  border-radius: 8px;
  box-shadow: 0 18px 50px rgba(15,23,42,0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.25s ease;
}
@keyframes slideUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

@media (max-width: 480px) {
  .chat-panel { width: calc(100vw - 24px); right: 12px; bottom: 12px; height: 520px; }
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #eef2f7;
  background: #fff;
}
.chat-header-left { display: flex; align-items: center; gap: 12px; }
.chat-avatar {
  width: 36px; height: 36px; border-radius: 8px;
  background: #0072b2;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; font-weight: 700;
}
.chat-title { font-size: 0.95rem; font-weight: 700; color: #111827; }
.chat-subtitle { font-size: 0.75rem; color: #9ca3af; }
.chat-actions { display: flex; gap: 6px; }
.icon-btn {
  width: 28px;
  height: 28px;
  border: 1px solid #e3e8ef;
  border-radius: 6px;
  background: #fff;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.82rem;
}
.icon-btn:hover { border-color: #0072b2; color: #0072b2; }

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #f8fafc;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 2px;
}
.suggestions button {
  padding: 6px 9px;
  border: 1px solid #e3e8ef;
  border-radius: 999px;
  background: #fff;
  color: #0072b2;
  cursor: pointer;
  font-size: 0.76rem;
}
.suggestions button:hover { background: #e6f2f8; }
.chat-msg { display: flex; }
.chat-msg.user { justify-content: flex-end; }
.chat-msg.ai { justify-content: flex-start; }
.msg-bubble {
  max-width: 82%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 0.88rem;
  line-height: 1.55;
  white-space: pre-wrap;
}
.chat-msg.user .msg-bubble { background: #0072b2; color: #fff; border-bottom-right-radius: 3px; }
.chat-msg.ai .msg-bubble { background: #fff; color: #111827; border: 1px solid #e3e8ef; border-bottom-left-radius: 3px; }

.typing { display: flex; gap: 4px; padding: 14px 18px; }
.typing span { width: 7px; height: 7px; border-radius: 50%; background: #c4c4c4; animation: bounce 1.4s infinite ease-in-out both; }
.typing span:nth-child(1) { animation-delay: -0.32s; }
.typing span:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%,80%,100% { transform: scale(0); } 40% { transform: scale(1); } }

.chat-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #eef2f7;
  background: #fff;
}
.chat-input {
  flex: 1;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 0.88rem;
  outline: none;
  background: #f8fafc;
  transition: border-color 0.2s;
  resize: none;
  max-height: 90px;
  font-family: inherit;
}
.chat-input:focus { border-color: #0072b2; background: #fff; }
.chat-send {
  width: 38px; height: 38px; border-radius: 8px;
  background: #0072b2; color: #fff; border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s; flex-shrink: 0;
}
.chat-send:hover { background: #005f95; }
.chat-send:disabled { background: #d1d5db; cursor: not-allowed; }
</style>
