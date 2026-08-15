import { ref, computed, nextTick } from 'vue'
import { qaAPI } from '@/api'
import { normalizeAssistantEvidence } from '@/features/chat/citationPresentation'
import { isNearStreamBottom } from '@/features/chat/streamFollowState'

const PAGE_SIZE = 5

let keySeed = 0

// 问答记录 → 聊天消息对象（含收藏/来源/置信度等展示字段）
const buildMessages = (records) => {
  const list = []
  for (const r of records) {
    list.push({
      key: ++keySeed,
      role: 'user',
      content: r.question,
      recordId: r.id
    })
    if (r.answer) {
      const evidence = normalizeAssistantEvidence({
        answerStatus: r.answer_status,
        citations: r.citations,
        sources: r.sources,
        pipelineVersion: r.pipeline_version
      })
      list.push({
        key: ++keySeed,
        role: 'assistant',
        content: r.answer,
        reasoning: r.reasoning || '',
        legacySources: evidence.legacySources,
        confidence: r.confidence,
        response_time: r.response_time,
        model_name: r.model_name,
        ragWarnings: r.rag_warnings || [],
        recordId: r.id,
        feedback: r.feedback,
        isFavorite: r.is_favorited,
        favoriteId: r.favoriteId || null,
        answerStatus: evidence.answerStatus,
        citationManifest: evidence.citationManifest,
        citationState: evidence.citationState,
        pipelineVersion: r.pipeline_version || null,
        evidenceLoadState: 'idle',
        evidenceError: '',
        citationDetails: [],
        citationDetailsTruncated: false,
        retrievalSignal: null,
        ragProcess: null
      })
    }
  }
  return list
}

/**
 * 会话消息分页加载
 * 打开会话只取最近一页（page=-1），向上滚动时按页加载更早消息并保持阅读位置。
 * @param {import('vue').Ref<HTMLElement|null>} threadRef 聊天滚动容器
 */
export function useConversationMessages(threadRef) {
  const messages = ref([])
  const conversationId = ref(null)
  const hasMore = ref(false)
  const totalRecords = ref(0)
  const loadingEarlier = ref(false)
  const loading = ref(false)
  const shouldFollowStream = ref(true)

  const hasEarlierMessages = computed(() => hasMore.value)

  // 已加载的记录数（user/assistant 消息同属一条记录，按 recordId 去重）
  const loadedRecords = computed(() => {
    const ids = new Set()
    for (const m of messages.value) {
      if (m.recordId) ids.add(m.recordId)
    }
    return ids.size
  })

  const updateStreamFollowState = () => {
    shouldFollowStream.value = isNearStreamBottom(threadRef.value)
  }

  const scrollToBottom = ({ force = false } = {}) => {
    if (!force && !shouldFollowStream.value) {
      return
    }
    nextTick(() => {
      if (!threadRef.value || (!force && !shouldFollowStream.value)) {
        return
      }
      threadRef.value.scrollTop = threadRef.value.scrollHeight
    })
  }

  // 加载最近一页消息（打开会话 / 切换会话）
  const loadInitial = async (id) => {
    conversationId.value = id
    loading.value = true
    try {
      const res = await qaAPI.getConversation(id, { limit: PAGE_SIZE })
      messages.value = buildMessages(res?.conversation?.records || [])
      const meta = res.record_meta
      hasMore.value = meta ? !!meta.has_more : false
      totalRecords.value = meta?.total ?? loadedRecords.value
      shouldFollowStream.value = true
      scrollToBottom({ force: true })
      return res.conversation
    } finally {
      loading.value = false
    }
  }

  const handleThreadScroll = () => {
    updateStreamFollowState()
    if (threadRef.value && threadRef.value.scrollTop < 40) {
      void loadEarlier()
    }
  }
  // 向上加载更早一页消息，插入头部并保持滚动位置
  const loadEarlier = async () => {
    if (loadingEarlier.value || !hasMore.value || !conversationId.value) return
    if (!messages.value.length) return
    loadingEarlier.value = true
    const beforeHeight = threadRef.value ? threadRef.value.scrollHeight : 0
    try {
      const res = await qaAPI.getConversation(conversationId.value, {
        limit: PAGE_SIZE,
        before_id: messages.value[0].recordId
      })
      const earlier = buildMessages(res?.conversation?.records || [])
      if (earlier.length) {
        messages.value.unshift(...earlier)
      }
      const meta = res.record_meta
      hasMore.value = meta ? !!meta.has_more : false
      totalRecords.value = meta?.total ?? totalRecords.value
      await nextTick()
      if (threadRef.value) {
        const grown = threadRef.value.scrollHeight - beforeHeight
        threadRef.value.scrollTop += grown
      }
    } finally {
      loadingEarlier.value = false
    }
  }

  const reset = () => {
    messages.value = []
    conversationId.value = null
    hasMore.value = false
    totalRecords.value = 0
    loadingEarlier.value = false
    shouldFollowStream.value = true
  }

  return {
    messages,
    loading,
    loadingEarlier,
    hasEarlierMessages,
    loadedRecords,
    totalRecords,
    loadInitial,
    loadEarlier,
    handleThreadScroll,
    scrollToBottom,
    reset,
    nextKey: () => ++keySeed
  }
}
