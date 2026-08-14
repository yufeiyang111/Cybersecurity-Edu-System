import { ref, computed, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { qaAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { titleFromQuestion } from '@/features/chat/conversationTitle'
import { useConversationMessages } from '@/composables/chat/useConversationMessages'
import { normalizeAssistantEvidence } from '@/features/chat/citationPresentation'

let typeTimer = null

const stopTyping = () => {
  if (typeTimer !== null) {
    clearInterval(typeTimer)
    typeTimer = null
  }
}

const TYPE_TICK_MS = 16
const TYPE_CHARS_PER_TICK = 3

/**
 * 问答页核心状态与交互逻辑
 * 负责：会话列表 / 消息流 / 发送问答 / 收藏反馈 / 滚动
 */
export function useChat(threadRef) {
  const router = useRouter()
  const userStore = useUserStore()

  onUnmounted(stopTyping)

  // 消息流由 useConversationMessages 管理：打开会话只取最近一页，向上滚动加载更早消息
  const {
    messages,
    loadingEarlier,
    hasEarlierMessages,
    loadedRecords,
    totalRecords,
    loadInitial,
    loadEarlier,
    scrollToBottom,
    reset: resetMessages,
    nextKey
  } = useConversationMessages(threadRef)

  const conversations = ref([])
  const currentConversationId = ref(null)
  const loading = ref(false)
  // 会话列表分页状态：初始只加载最近一页，滚动到列表底部时按页加载更早的会话
  const conversationPage = ref(1)
  const conversationTotalPages = ref(1)
  const loadingMore = ref(false)

  const hasMoreConversations = computed(() => conversationPage.value < conversationTotalPages.value)

  const welcomeTopics = [
    '什么是SQL注入攻击？如何防范？',
    '如何防范XSS跨站脚本攻击？',
    'HTTPS 的工作原理是什么？',
    '什么是零信任安全架构？',
    '服务器被入侵后应如何排查？'
  ]

  const loadConversations = async () => {
    try {
      const res = await qaAPI.getConversations({ page: 1, per_page: 15 })
      conversations.value = res.conversations || []
      conversationPage.value = 1
      conversationTotalPages.value = res.pages || 1
    } catch (e) {
      console.error('加载会话列表失败', e)
    }
  }

  // 加载更早的会话（下一页），追加到列表尾部并去重
  const loadMoreConversations = async () => {
    if (loadingMore.value || !hasMoreConversations.value) return
    loadingMore.value = true
    try {
      const nextPage = conversationPage.value + 1
      const res = await qaAPI.getConversations({ page: nextPage, per_page: 15 })
      const existingIds = new Set(conversations.value.map((c) => c.id))
      const fresh = (res.conversations || []).filter((c) => !existingIds.has(c.id))
      conversations.value.push(...fresh)
      conversationPage.value = nextPage
      conversationTotalPages.value = res.pages || conversationTotalPages.value
    } catch (e) {
      console.error('加载更早会话失败', e)
    } finally {
      loadingMore.value = false
    }
  }

  const selectConversation = async (id) => {
    currentConversationId.value = id
    try {
      await loadInitial(id)
    } catch (e) {
      ElMessage.error('加载会话失败')
    }
  }

  const createConversation = async () => {
    try {
      const res = await qaAPI.createConversation({ title: '新会话' })
      if (!res?.conversation) {
        ElMessage.error('创建会话失败：响应缺少会话数据')
        return
      }
      conversations.value.unshift(res.conversation)
      currentConversationId.value = res.conversation.id
      resetMessages()
    } catch (e) {
      ElMessage.error('创建会话失败')
    }
  }

  const renameConversation = async (conv) => {
    try {
      const { value: newTitle } = await ElMessageBox.prompt('请输入新会话标题', '重命名会话', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: conv.title || '新会话'
      })
      if (!newTitle?.trim()) return
      await qaAPI.updateConversation(conv.id, { title: newTitle.trim() })
      const found = conversations.value.find(c => c.id === conv.id)
      if (found) found.title = newTitle.trim()
      ElMessage.success('重命名成功')
    } catch (e) {
      if (e !== 'cancel') ElMessage.error('重命名失败')
    }
  }

  const deleteConversation = async (conv) => {
    try {
      await ElMessageBox.confirm('删除后不可恢复，确定删除该会话？', '删除会话', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      })
    } catch (e) {
      return
    }
    try {
      await qaAPI.deleteConversation(conv.id)
      conversations.value = conversations.value.filter(c => c.id !== conv.id)
      if (currentConversationId.value === conv.id) {
        currentConversationId.value = null
        resetMessages()
      }
      ElMessage.success('删除成功')
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }

  const sendMessage = async ({ text, files }) => {
    if (loading.value) return

    messages.value.push({
      key: nextKey(),
      role: 'user',
      content: text,
      attachments: (files || []).map((f) => ({
        name: f.name,
        type: f.type.startsWith('image/') ? 'image' : 'file',
        preview: null
      }))
    })
    const userMsg = messages.value[messages.value.length - 1]
    scrollToBottom()

    const pendingEvidence = normalizeAssistantEvidence({ isStreaming: true })
    messages.value.push({
      key: nextKey(),
      role: 'assistant',
      content: '',
      reasoning: '',
      legacySources: pendingEvidence.legacySources,
      attachments: [],
      streaming: true,
      answerStatus: pendingEvidence.answerStatus,
      citationManifest: pendingEvidence.citationManifest,
      citationState: pendingEvidence.citationState,
      evidenceLoadState: 'idle',
      evidenceError: '',
      citationDetails: [],
      citationDetailsTruncated: false,
      retrievalSignal: null
    })
    const assistantMsg = messages.value[messages.value.length - 1]
    scrollToBottom()

    loading.value = true
    const activeConversation = conversations.value.find((conversation) => conversation.id === currentConversationId.value)
    if (activeConversation && (!activeConversation.title || activeConversation.title === '新会话')) {
      const generatedTitle = titleFromQuestion(text)
      activeConversation.title = generatedTitle
      qaAPI.updateConversation(activeConversation.id, { title: generatedTitle }).catch(() => {})
    }
    const formData = new FormData()
    formData.append('question', text)
    if (currentConversationId.value) {
      formData.append('conversation_id', currentConversationId.value)
    }
    for (const f of files || []) formData.append('files', f)

    // 打字机分片渲染：无论后端块多大，都逐小片刷出
    const typeBuffer = []
    const feedTyping = (text) => {
      typeBuffer.push(...Array.from(text))
      if (typeTimer === null) {
        typeTimer = setInterval(() => {
          if (!typeBuffer.length) {
            stopTyping()
            return
          }
          assistantMsg.content += typeBuffer.splice(0, TYPE_CHARS_PER_TICK).join('')
          scrollToBottom()
        }, TYPE_TICK_MS)
      }
    }
    const flushTyping = () => {
      stopTyping()
      if (typeBuffer.length) {
        assistantMsg.content += typeBuffer.join('')
        typeBuffer.length = 0
        scrollToBottom()
      }
    }

    const handleStreamError = (message) => {
      flushTyping()
      assistantMsg.streaming = false
      assistantMsg.isError = true
      assistantMsg.answerStatus = 'degraded'
      assistantMsg.citationState = 'degraded'
      assistantMsg.content = assistantMsg.content || message || '抱歉，生成答案时出现错误，请稍后重试。'
      scrollToBottom()
    }

    try {
      await qaAPI.askStream(formData, {
        onEvent: ({ event, data }) => {
          if (event === 'delta') {
            feedTyping(data.delta || '')
          } else if (event === 'reasoning') {
            assistantMsg.reasoning += data.delta || ''
          } else if (event === 'done') {
            flushTyping()
            assistantMsg.streaming = false
            assistantMsg.content = data.answer || assistantMsg.content
            assistantMsg.reasoning = data.reasoning || assistantMsg.reasoning
            const evidence = normalizeAssistantEvidence({
              answerStatus: data.answer_status,
              citations: data.citations,
              sources: data.sources,
              pipelineVersion: data.pipeline_version
            })
            assistantMsg.legacySources = evidence.legacySources
            assistantMsg.confidence = data.confidence
            assistantMsg.response_time = data.response_time
            assistantMsg.model_name = data.model_name || data.provider
            assistantMsg.ragWarnings = data.rag_warnings || []
            assistantMsg.recordId = data.id
            assistantMsg.answerStatus = evidence.answerStatus
            assistantMsg.citationManifest = evidence.citationManifest
            assistantMsg.citationState = evidence.citationState
            assistantMsg.pipelineVersion = data.pipeline_version || null
            assistantMsg.evidenceLoadState = 'idle'
            assistantMsg.evidenceError = ''
            assistantMsg.citationDetails = []
            assistantMsg.citationDetailsTruncated = false
            assistantMsg.retrievalSignal = null
            if (data.attachments?.length) {
              assistantMsg.attachments = data.attachments.map((a) => ({
                ...a,
                type: a.type === 'image' ? 'image' : 'file'
              }))
              userMsg.attachments = assistantMsg.attachments
            }
            if (data.conversation_id && !currentConversationId.value) {
              // 无会话直接提问时，后端自动创建了新会话：更新前端状态，侧栏立即显示
              currentConversationId.value = data.conversation_id
              const generatedTitle = titleFromQuestion(text)
              conversations.value.unshift({
                id: data.conversation_id,
                title: generatedTitle,
                is_archived: false
              })
              qaAPI.updateConversation(data.conversation_id, { title: generatedTitle }).catch(() => {})
            } else {
              // 已有会话：刷新列表保持按最近活跃排序
              loadConversations()
            }
            scrollToBottom()
          } else if (event === 'memory') {
            // 持久记忆抽取在 done 之后异步完成（不阻塞回答与资料展示），
            // 抽取结果通过本事件送达，新增提示对标 ChatGPT "Memory updated"
            if (data?.added > 0) {
              ElMessage({
                message: `已记住 ${data.added} 条新信息`,
                duration: 4000,
                onClick: () => router.push('/user/memories')
              })
            }
          } else if (event === 'error') {
            handleStreamError(data.error)
            ElMessage.error(data.error || '生成答案失败')
          }
        },
        onError: (err) => {
          handleStreamError(err?.message)
          ElMessage.error(err?.message || '生成答案失败')
        }
      })
    } catch (e) {
      handleStreamError()
      ElMessage.error('生成答案失败')
    } finally {
      loading.value = false
      scrollToBottom()
    }
  }

  const toggleFavorite = async (msg) => {
    if (!userStore.isLoggedIn) {
      ElMessage.warning('请先登录')
      return
    }
    if (msg.isFavorite && msg.favoriteId) {
      try {
        await qaAPI.removeFavorite(msg.favoriteId)
        msg.isFavorite = false
        msg.favoriteId = null
        ElMessage.success('已取消收藏')
      } catch (e) {
        ElMessage.error('取消收藏失败')
      }
    } else if (!msg.isFavorite && msg.recordId) {
      try {
        const res = await qaAPI.addFavorite({ qa_record_id: msg.recordId })
        msg.isFavorite = true
        msg.favoriteId = res.id
        ElMessage.success('已添加收藏')
      } catch (e) {
        console.error('收藏失败', e)
        ElMessage.error('收藏失败')
      }
    } else {
      ElMessage.warning('无法收藏此消息')
    }
  }

  const submitFeedback = async (msg, type) => {
    if (!userStore.isLoggedIn) {
      ElMessage.warning('请先登录')
      return
    }
    if (!msg.recordId) {
      ElMessage.warning('该消息暂不支持反馈')
      return
    }
    try {
      await qaAPI.submitFeedback(msg.recordId, { feedback: type })
      msg.feedback = type
      ElMessage.success('感谢您的反馈')
    } catch (e) {
      ElMessage.error('反馈失败')
    }
  }

  const copyMessage = async (msg) => {
    try {
      await navigator.clipboard.writeText(msg.content)
      ElMessage.success('已复制到剪贴板')
    } catch (e) {
      ElMessage.error('复制失败')
    }
  }

  const openConversationByQuery = async (conversationId) => {
    const found = conversations.value.find(c => c.id === conversationId)
    if (found) {
      await selectConversation(found.id)
      return
    }
    try {
      const res = await qaAPI.getConversation(conversationId)
      const conv = res?.conversation
      if (!conv) {
        ElMessage.error('会话不存在或无权访问')
        return
      }
      conversations.value.unshift({
        id: conv.id,
        title: conv.title || '新会话',
        is_archived: conv.is_archived
      })
      await selectConversation(conv.id)
    } catch (e) {
      ElMessage.error('会话不存在或无权访问')
    }
  }

  return {
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
    loadEarlierMessages: loadEarlier,
    hasEarlierMessages,
    loadingEarlier,
    loadedRecords,
    totalRecords
  }
}
