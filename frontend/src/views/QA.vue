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
           <span>{{ t('qa.topbar') }}</span>
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
            @view-evidence="handleLoadEvidence"
            @citation-detail="handleCitationDetail"
            @citation-original="handleCitationOriginal"
          />
        </div>
      </div>

      <ChatComposer :disabled="loading" @send="handleSend" />
      <div class="qa-legal">{{ t('qa.legal') }}</div>
    </main>

    <ChatSettingsDialog v-if="settingsOpen" v-model="settingsOpen" />
    <CitationDetailDrawer
      :visible="drawerVisible"
      :citation="selectedCitation"
      :retrieval-signal="selectedSignal"
      @close="closeDrawer"
      @open-original="handleDrawerOpenOriginal"
    />
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
import CitationDetailDrawer from '@/components/chat/CitationDetailDrawer.vue'
import { useChat } from '@/composables/chat/useChat'
import { useCitationEvidence } from '@/composables/chat/useCitationEvidence'
import { useChatPreferences } from '@/composables/chat/useChatPreferences'
import { useI18n } from '@/features/chat/i18n'

const ChatSettingsDialog = defineAsyncComponent(() => import('@/components/chat/ChatSettingsDialog.vue'))

const route = useRoute()
const userStore = useUserStore()
const { t } = useI18n()

const threadRef = ref(null)
const sidebarCollapsed = ref(false)
const settingsOpen = ref(false)
const { load: loadPreferences } = useChatPreferences()
const {
  drawerVisible,
  selectedCitation,
  selectedSignal,
  selectedRecordId,
  loadEvidence,
  openCitation,
  openOriginalDocument,
  closeDrawer
} = useCitationEvidence()

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
  hasEarlierMessages,
  loadingEarlier,
  loadedRecords,
  totalRecords,
  handleThreadScroll
} = useChat(threadRef)

const handleSend = ({ text, files }) => {
  sendMessage({ text, files })
  scrollToBottom()
}

const quickAsk = (topic) => {
  sendMessage({ text: topic, files: [] })
}

const applyEvidenceDetails = (message, evidence) => {
  message.citationDetails = evidence.citationDetails
  message.citationDetailsTruncated = evidence.citationDetailsTruncated
  message.retrievalSignal = evidence.retrievalSignal
  message.evidenceLoadState = 'success'
  message.evidenceError = ''
}

const handleLoadEvidence = async (message) => {
  if (!message?.recordId || message.evidenceLoadState === 'loading') {
    return
  }
  message.evidenceLoadState = 'loading'
  message.evidenceError = ''
  try {
    const evidence = await loadEvidence(message.recordId)
    applyEvidenceDetails(message, evidence)
  } catch (error) {
    message.evidenceLoadState = 'error'
    message.evidenceError = '证据详情暂时无法加载，请稍后重试。'
  }
}

const handleCitationDetail = async (message, citation, origin) => {
  try {
    const evidence = await loadEvidence(message.recordId)
    applyEvidenceDetails(message, evidence)
    await openCitation(message.recordId, citation.citationId, origin)
  } catch (error) {
    ElMessage.warning('该引用详情当前不可用。')
  }
}

const handleCitationOriginal = async (message, citation) => {
  try {
    const evidence = await loadEvidence(message.recordId)
    applyEvidenceDetails(message, evidence)
    await openOriginalDocument(message.recordId, citation.citationId)
  } catch (error) {
    ElMessage.warning('该引用的知识库原文当前不可用。')
  }
}

const handleDrawerOpenOriginal = async ({ citation }) => {
  try {
    if (!selectedRecordId.value) {
      throw new Error('无法定位引用所属记录。')
    }
    await openOriginalDocument(selectedRecordId.value, citation.citationId)
  } catch (error) {
    ElMessage.warning('该引用的知识库原文当前不可用。')
  }
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
  position: sticky;
  top: 0;
  z-index: 10;
  text-align: center;
  font-size: 12px;
  color: var(--chat-hollow, #8a94a6);
  background: var(--chat-canvas, #f5f7fa);
  padding: 6px 0;
  border-radius: 6px;
}

.qa-legal {
  text-align: center;
  font-size: 12px;
  color: var(--chat-hollow);
  padding: 0 20px 12px;
}
</style>
