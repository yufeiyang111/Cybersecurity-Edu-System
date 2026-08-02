import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { qaAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

let keySeed = 0

/**
 * 问答页核心状态与交互逻辑
 * 负责：会话列表 / 消息流 / 发送问答 / 收藏反馈 / 滚动
 */
export function useChat(threadRef) {
  const router = useRouter()
  const userStore = useUserStore()

  const messages = ref([])
  const conversations = ref([])
  const currentConversationId = ref(null)
  const loading = ref(false)

  const welcomeTopics = [
    '什么是SQL注入攻击？如何防范？',
    '如何防范XSS跨站脚本攻击？',
    'HTTPS 的工作原理是什么？',
    '什么是零信任安全架构？',
    '服务器被入侵后应如何排查？'
  ]

  const scrollToBottom = () => {
    nextTick(() => {
      if (threadRef.value) {
        threadRef.value.scrollTop = threadRef.value.scrollHeight
      }
    })
  }

  const normalizeSources = (sources) => (sources || []).map((s) => ({
    ...s,
    source_type: s.source_type || s.source || 'unknown'
  }))

  const loadConversations = async () => {
    try {
      const res = await qaAPI.getConversations({ per_page: 50 })
      conversations.value = res.conversations || []
    } catch (e) {
      console.error('加载会话列表失败', e)
    }
  }

  const selectConversation = async (id) => {
    currentConversationId.value = id
    try {
      const res = await qaAPI.getConversation(id)
      messages.value = []
      for (const r of res.conversation.records) {
        messages.value.push({
          key: ++keySeed,
          role: 'user',
          content: r.question
        })
        if (r.answer) {
          messages.value.push({
            key: ++keySeed,
            role: 'assistant',
            content: r.answer,
            reasoning: r.reasoning || '',
            sources: normalizeSources(r.sources),
            confidence: r.confidence,
            response_time: r.response_time,
            model_name: r.model_name,
            recordId: r.id,
            feedback: r.feedback,
            isFavorite: r.is_favorited,
            favoriteId: r.favoriteId || null
          })
        }
      }
      scrollToBottom()
    } catch (e) {
      ElMessage.error('加载会话失败')
    }
  }

  const createConversation = async () => {
    try {
      const res = await qaAPI.createConversation({ title: '新会话' })
      conversations.value.unshift(res.conversation)
      currentConversationId.value = res.conversation.id
      messages.value = []
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
        messages.value = []
      }
      ElMessage.success('删除成功')
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }

  const sendMessage = async ({ text, files }) => {
    if (loading.value) return

    const userMsg = {
      key: ++keySeed,
      role: 'user',
      content: text,
      attachments: (files || []).map((f) => ({
        name: f.name,
        type: f.type.startsWith('image/') ? 'image' : 'file',
        preview: null
      }))
    }
    messages.value.push(userMsg)
    scrollToBottom()

    const assistantMsg = {
      key: ++keySeed,
      role: 'assistant',
      content: '',
      reasoning: '',
      sources: [],
      attachments: [],
      streaming: true
    }
    messages.value.push(assistantMsg)
    scrollToBottom()

    loading.value = true
    const formData = new FormData()
    formData.append('question', text)
    if (currentConversationId.value) {
      formData.append('conversation_id', currentConversationId.value)
    }
    for (const f of files || []) formData.append('files', f)

    const handleStreamError = (message) => {
      assistantMsg.streaming = false
      assistantMsg.isError = true
      assistantMsg.content = assistantMsg.content || message || '抱歉，生成答案时出现错误，请稍后重试。'
      scrollToBottom()
    }

    try {
      await qaAPI.askStream(formData, {
        onEvent: ({ event, data }) => {
          if (event === 'delta') {
            assistantMsg.content += data.delta || ''
            scrollToBottom()
          } else if (event === 'reasoning') {
            assistantMsg.reasoning += data.delta || ''
          } else if (event === 'done') {
            assistantMsg.streaming = false
            assistantMsg.content = data.answer || assistantMsg.content
            assistantMsg.reasoning = data.reasoning || assistantMsg.reasoning
            assistantMsg.sources = normalizeSources(data.sources)
            assistantMsg.confidence = data.confidence
            assistantMsg.response_time = data.response_time
            assistantMsg.model_name = data.model_name || data.provider
            assistantMsg.recordId = data.id
            if (data.attachments?.length) {
              assistantMsg.attachments = data.attachments.map((a) => ({
                ...a,
                type: a.type === 'image' ? 'image' : 'file'
              }))
              userMsg.attachments = assistantMsg.attachments
            }
            if (currentConversationId.value) {
              const conv = conversations.value.find(c => c.id === currentConversationId.value)
              if (conv) conv.title = conv.title || text.slice(0, 30)
              loadConversations()
            }
            scrollToBottom()
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
      conversations.value.unshift({
        id: res.conversation.id,
        title: res.conversation.title,
        is_archived: res.conversation.is_archived
      })
      await selectConversation(res.conversation.id)
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
    scrollToBottom
  }
}
