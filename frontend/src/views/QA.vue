<template>
  <div class="qa-page">
    <ChatSidebar
      :conversations="conversations"
      :active-id="currentConversationId"
      :collapsed="sidebarCollapsed"
      :loading-more="loadingMore"
      :has-more="hasMoreConversations"
      @new-chat="createConversation"
      @select="selectConversation"
      @rename="renameConversation"
      @delete="deleteConversation"
      @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
      @open-settings="settingsOpen = true"
      @load-more="loadMoreConversations"
    />

    <main class="qa-main">
      <div class="qa-topbar">
        <div class="qa-model-picker" @click="notifyModel">
          <span class="qa-model-dot"></span>
           <span>AI 安全助手 · 全部</span>
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2"><path d="M6 9l6 6 6-6" /></svg>
        </div>
      </div>

      <div ref="threadRef" class="qa-thread" @scroll="handleThreadScroll">
        <ChatWelcome v-if="!messages.length && !loading" :topics="welcomeTopics" @select="quickAsk" />
        <div v-else class="qa-thread-inner">
          <div v-if="loadingEarlier" class="qa-loading-earlier">正在加载更早的消息…</div>
          <div v-else-if="hasEarlierMessages" class="qa-loading-earlier">
            已加载 {{ loadedRecords }} / {{ totalRecords }} 条消息，向上滚动加载更早
          </div>
          <ChatMessage
            v-for="msg in messages"
            :key="msg.key"
            :message="msg"
            @copy="copyMessage"
            @favorite="toggleFavorite"
            @feedback="submitFeedback"
          />
        </div>
      </div>

      <ChatComposer :disabled="loading" @send="handleSend" />
      <div class="qa-legal">AI 安全助手可能会犯错。请核查重要信息。</div>
    </main>

    <ChatSettingsDialog v-if="settingsOpen" v-model="settingsOpen" />
  </div>
</template>

<script setup>
import { ref, onMounted, defineAsyncComponent } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import ChatSidebar from '@/components/chat/ChatSidebar.vue'
import ChatWelcome from '@/components/chat/ChatWelcome.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import { useChat } from '@/composables/chat/useChat'
import { useChatPreferences } from '@/composables/chat/useChatPreferences'

const ChatSettingsDialog = defineAsyncComponent(() => import('@/components/chat/ChatSettingsDialog.vue'))

const route = useRoute()
const userStore = useUserStore()

const threadRef = ref(null)
const sidebarCollapsed = ref(false)
const settingsOpen = ref(false)
const { load: loadPreferences } = useChatPreferences()

const {
  messages,
  conversations,
  currentConversationId,
  loading,
  welcomeTopics,
  loadConversations,
  selectConversation,
  createConversation,
  renameConversation,
  deleteConversation,
  sendMessage,
  toggleFavorite,
  submitFeedback,
  copyMessage,
  openConversationByQuery,
  scrollToBottom,
  loadMoreConversations,
  hasMoreConversations,
  loadingMore,
  loadEarlierMessages,
  hasEarlierMessages,
  loadingEarlier,
  loadedRecords,
  totalRecords
} = useChat(threadRef)

// 聊天窗口向上滚动到顶部时加载更早的消息
const handleThreadScroll = () => {
  if (threadRef.value && threadRef.value.scrollTop < 40) {
    loadEarlierMessages()
  }
}

const handleSend = ({ text, files }) => {
  sendMessage({ text, files })
  scrollToBottom()
}

const quickAsk = (topic) => {
  sendMessage({ text: topic, files: [] })
}

const notifyModel = () => {
  ElMessage.info('当前为全部模式：自动选择检索策略')
}

onMounted(async () => {
  if (!userStore.isLoggedIn) {
    ElMessage.info('登录后可保存问答历史')
  }
  void loadPreferences()
  await loadConversations()
  const conversationId = Number(route.query.conversation_id)
  if (conversationId) {
    await openConversationByQuery(conversationId)
  }
})
</script>

<style lang="scss" scoped>
.qa-page {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: var(--chat-canvas);
  font-family: var(--chat-font-family);
}

.qa-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.qa-topbar {
  height: 52px;
  min-height: 52px;
  border-bottom: 1px solid var(--chat-hairline);
  display: flex;
  align-items: center;
  padding: 0 14px;
}

.qa-model-picker {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: var(--chat-radius);
  cursor: pointer; font-size: 14px;
  color: var(--chat-ink);
  &:hover { background: var(--chat-hover); }
  svg { width: 14px; height: 14px; stroke: var(--chat-hollow); }
  .qa-model-dot {
    width: 8px; height: 8px; border-radius: 50%;
   background: var(--chat-accent);
  }
}

.qa-thread {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.qa-thread-inner {
  max-width: var(--chat-content-width);
  width: 100%;
  margin: 0 auto;
   padding: calc(24px * var(--chat-space-scale)) 20px calc(8px * var(--chat-space-scale));
}

.qa-loading-earlier {
  text-align: center;
  font-size: 12px;
  color: var(--chat-hollow, #8a94a6);
  padding: 6px 0;
}

.qa-legal {
  text-align: center;
  font-size: 12px;
  color: var(--chat-hollow);
  padding: 0 20px 12px;
}
</style>
