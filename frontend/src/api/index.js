import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useUserStore } from '@/stores/user'
import { parseSseFrame } from '@/features/security/agent/sseParser'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

// 会话过期统一处理：清 store 与 localStorage，跳登录页（防并发 401 重复跳转）
let sessionExpiredRedirected = false

function handleSessionExpired(redirectTo) {
  const userStore = useUserStore()
  userStore.logout()
  if (sessionExpiredRedirected) return
  sessionExpiredRedirected = true
  ElMessage.error('登录已过期，请重新登录')
  const current = router.currentRoute.value
  // 已在登录页时保留原有 redirect，避免嵌套 /login?redirect=/login?redirect=...
  const redirect = redirectTo || (current.name === 'Login'
    ? (current.query.redirect || '/')
    : current.fullPath)
  router.push({
    name: 'Login',
    query: { redirect }
  })
}

router.afterEach((to) => {
  if (to.name === 'Login') {
    sessionExpiredRedirected = false
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    const { response } = error
    
    if (response) {
      const { status, data } = response
      
      switch (status) {
        case 401:
          // 登录/注册失败也是 401，属正常业务错误，由页面自行提示，不按会话过期处理
          if (error.config?.url?.startsWith('/auth/login') || error.config?.url?.startsWith('/auth/register')) {
            break
          }
          handleSessionExpired()
          break
        case 422:
          // flask-jwt-extended 对无效 token 返回 422 + msg 字段（业务错误统一用 error 键）
          if (data?.msg) {
            handleSessionExpired()
            break
          }
          ElMessage.error(data.error || '请求参数错误')
          break
        case 403:
          if (!error.config?.suppressGlobalErrorMessage) {
            ElMessage.error(data.error || '权限不足')
          }
          break
        case 404:
          ElMessage.error(data.error || '资源不存在')
          break
        case 500:
          ElMessage.error('服务器错误，请稍后重试')
          break
        default:
          ElMessage.error(data.error || '请求失败')
      }
    } else {
      ElMessage.error('网络连接失败，请检查网络')
    }
    
    return Promise.reject(error)
  }
)

// 认证相关
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  logout: () => api.post('/auth/logout'),
  getMe: () => api.get('/auth/me'),
  updateProfile: (data) => api.put('/auth/me', data),
  getPreferences: () => api.get('/auth/preferences'),
  updatePreferences: (data) => api.put('/auth/preferences', data),
  resetPreferences: () => api.post('/auth/preferences/reset'),
  changePassword: (data) => api.put('/auth/password', data),
  getLoginLogs: (params) => api.get('/auth/login-logs', { params }),
  checkAvailable: (params) => api.get('/auth/check', { params }),
  bindOAuth: (provider) => api.post(`/auth/oauth/${provider}/bind`),
  unbindOAuth: (provider) => api.delete(`/auth/oauth/${provider}/bind`)
}

// 知识库相关
export const knowledgeAPI = {
  getCategories: (params) => api.get('/knowledge/categories', { params }),
  getCategory: (id) => api.get(`/knowledge/categories/${id}`),
  createCategory: (data) => api.post('/knowledge/categories', data),
  updateCategory: (id, data) => api.put(`/knowledge/categories/${id}`, data),
  deleteCategory: (id) => api.delete(`/knowledge/categories/${id}`),
  
  getKnowledgeList: (params) => api.get('/knowledge', { params }),
  getKnowledge: (id) => api.get(`/knowledge/${id}`),
  createKnowledge: (data) => api.post('/knowledge', data),
  updateKnowledge: (id, data) => api.put(`/knowledge/${id}`, data),
  deleteKnowledge: (id) => api.delete(`/knowledge/${id}`),
  importKnowledge: (data) => api.post('/knowledge/import', data),
  uploadDocument: (formData) => api.post('/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  uploadDocumentsBatch: (formData) => api.post('/knowledge/upload/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  
  search: (params) => api.get('/knowledge/search', { params }),
  getHot: (params) => api.get('/knowledge/hot', { params }),
  getTags: () => api.get('/knowledge/tags'),

  // 收藏
  getFavoriteStatus: (id) => api.get(`/knowledge/${id}/favorite`),
  addFavorite: (id) => api.post(`/knowledge/${id}/favorite`),
  removeFavorite: (id) => api.delete(`/knowledge/${id}/favorite`),
  getMyFavorites: (params) => api.get('/knowledge/favorites', { params }),

  // 相关知识
  getRelatedKnowledge: (id, params) => api.get(`/knowledge/${id}/related`, { params }),

  // 相关问答
  getRelatedQA: (id, params) => api.get(`/knowledge/${id}/related-qa`, { params })
}

// 问答相关
export const qaAPI = {
  ask: (data) => {
    if (data instanceof FormData) {
      return api.post('/qa/ask', data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    }
    return api.post('/qa/ask', data)
  },

  // SSE 流式问答：formData 请求体，逐事件回调 { event, data }
  askStream: async (formData, { onEvent, onError, signal } = {}) => {
    const token = localStorage.getItem('token')
    let res
    try {
      res = await fetch('/api/qa/ask/stream', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
        signal
      })
    } catch (e) {
      if (e?.name !== 'AbortError') onError?.(e)
      return
    }
    if (!res.ok) {
      let msg = '请求失败'
      try {
        const body = await res.json()
        if (body?.error) msg = body.error
      } catch (e) { /* ignore */ }
      if (res.status === 401) {
        handleSessionExpired()
        return
      }
      onError?.(new Error(msg))
      return
    }
    if (!res.body) {
      onError?.(new Error('浏览器不支持流式响应'))
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const flush = () => {
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        parseSSEEvent(raw, onEvent)
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        flush()
      }
      if (buffer.trim()) parseSSEEvent(buffer, onEvent)
    } catch (e) {
      if (e?.name !== 'AbortError') onError?.(e)
    }
  },

  getSuggestions: (params) => api.get('/qa/suggestions', { params }),
  getSimilar: (params) => api.get('/qa/similar', { params }),
  getHistory: (params) => api.get('/qa/history', { params }),
  getRecord: (id) => api.get(`/qa/${id}`),
  getEvidence: (id) => api.get(`/qa/records/${id}/evidence`),
  submitFeedback: (id, data) => api.post(`/qa/${id}/feedback`, data),
  
  // 会话管理
  getConversations: (params) => api.get('/qa/conversations', { params }),
  createConversation: (data) => api.post('/qa/conversations', data),
  getConversation: (id, params) => api.get(`/qa/conversations/${id}`, { params }),
  updateConversation: (id, data) => api.put(`/qa/conversations/${id}`, data),
  deleteConversation: (id) => api.delete(`/qa/conversations/${id}`),
  
  // 收藏
  getFavorites: (params) => api.get('/qa/favorites', { params }),
  addFavorite: (data) => api.post('/qa/favorites', data),
  removeFavorite: (id) => api.delete(`/qa/favorites/${id}`)
}

function parseSSEEvent(raw, onEvent) {
  let event = 'message'
  let dataText = ''
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataText += line.slice(5).trim()
    }
  }
  if (!dataText) return
  try {
    const data = JSON.parse(dataText)
    if (onEvent) onEvent({ event, data })
  } catch (e) {
    console.error('SSE 解析失败', e)
  }
}

// 管理后台相关
export const securityAPI = {
  createProject: (data) => api.post('/security/projects', data),
  listProjects: () => api.get('/security/projects'),
  updateProject: (projectId, data) => api.put(`/security/projects/${projectId}`, data),
  deleteProject: (projectId) => api.delete(`/security/projects/${projectId}`),
  uploadSnapshot: (projectId, formData) => api.post(`/security/projects/${projectId}/snapshots:upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  importGitHubSnapshot: (projectId, data) => api.post(`/security/projects/${projectId}/snapshots:github`, data),
  rescanProject: (projectId) => api.post(`/security/projects/${projectId}/rescan`),
  listSnapshots: (projectId, params) => api.get(`/security/projects/${projectId}/snapshots`, { params }),
  deleteSnapshot: (projectId, snapshotId) => api.delete(`/security/projects/${projectId}/snapshots/${snapshotId}`),
  getExclusions: (projectId) => api.get(`/security/projects/${projectId}/exclusions`),
  replaceExclusions: (projectId, patterns) => api.put(`/security/projects/${projectId}/exclusions`, { patterns }),
  addExclusion: (projectId, pattern) => api.post(`/security/projects/${projectId}/exclusions/items`, { pattern }),
  deleteExclusion: (projectId, ruleId) => api.delete(`/security/projects/${projectId}/exclusions/items/${ruleId}`),
  getTasks: (projectId) => api.get(`/security/projects/${projectId}/tasks`),
  getWorkbenchOverview: () => api.get('/security/workbench/overview'),
  getMyWorkspace: () => api.get('/security/my-workspace'),
  getTask: (taskId) => api.get(`/security/tasks/${taskId}`),
  getFindings: (taskId, params) => api.get(`/security/tasks/${taskId}/findings`, { params }),
  cancelTask: (taskId) => api.post(`/security/tasks/${taskId}/cancel`),
  retryTask: (taskId) => api.post(`/security/tasks/${taskId}/retry`),
  deleteTask: (taskId) => api.delete(`/security/tasks/${taskId}`),
  getDependencies: (projectId, params) => api.get(`/security/projects/${projectId}/dependencies`, { params }),

  listKnowledgeSources: (params) => api.get('/security/knowledge/sources', { params }),
  createKnowledgeSource: (data) => api.post('/security/knowledge/sources', data),
  updateKnowledgeSource: (sourceId, data) => api.put(`/security/knowledge/sources/${sourceId}`, data),
  deleteKnowledgeSource: (sourceId) => api.delete(`/security/knowledge/sources/${sourceId}`),
  listKnowledgeDocuments: (sourceId, params) => api.get(`/security/knowledge/sources/${sourceId}/documents`, { params }),
  getKnowledgeDocument: (sourceId, documentId) => api.get(`/security/knowledge/sources/${sourceId}/documents/${documentId}`),
  createKnowledgeDocument: (sourceId, data) => api.post(`/security/knowledge/sources/${sourceId}/documents`, data),
  updateKnowledgeDocument: (sourceId, documentId, data) => api.put(`/security/knowledge/sources/${sourceId}/documents/${documentId}`, data),
  deleteKnowledgeDocument: (sourceId, documentId) => api.delete(`/security/knowledge/sources/${sourceId}/documents/${documentId}`),

  generateRemediationSuggestion: (findingId) => api.post(`/security/findings/${findingId}/suggestions`),
  listRemediationSuggestions: (findingId, params) => api.get(`/security/findings/${findingId}/suggestions`, { params }),
  reviewRemediationSuggestion: (suggestionId, data) => api.post(`/security/suggestions/${suggestionId}/review`, data),
  deleteRemediationSuggestion: (suggestionId) => api.delete(`/security/suggestions/${suggestionId}`)
}

export const llmAPI = {
  listProviders: () => api.get('/llm/providers'),
  getProvider: (id) => api.get(`/llm/providers/${id}`),
  createProvider: (data) => api.post('/llm/providers', data),
  updateProvider: (id, data) => api.put(`/llm/providers/${id}`, data),
  deleteProvider: (id) => api.delete(`/llm/providers/${id}`),
  testProvider: (id) => api.post(`/llm/providers/${id}/test`),
  setDefaultProvider: (id) => api.post(`/llm/providers/${id}/default`),
  toggleProvider: (id, isEnabled) => api.post(`/llm/providers/${id}/toggle`, { is_enabled: isEnabled }),
  listLogs: (params) => api.get('/llm/logs', { params }),
  getLogSummary: (params) => api.get('/llm/logs/summary', { params }),
  getAnalytics: (params) => api.get('/llm/analytics', { params })
}

// Agent 工作台：持久化 Run、暂停/恢复/取消、可重放 SSE 事件流
// T11：单一 parser 来自 features/security/agent/sseParser（Node 可测的纯函数）。
function parseAgentSSE(raw, onEvent) {
  const frame = parseSseFrame(raw)
  if (!frame) return
  onEvent(frame)
}

export const agentAPI = {
  createRun: (projectId, data) => api.post(`/security/projects/${projectId}/agent-runs`, data),
  getRun: (runId) =>
    api.get(`/security/agent-runs/${runId}`, { suppressGlobalErrorMessage: true }),
  pauseRun: (runId) => api.post(`/security/agent-runs/${runId}/pause`),
  resumeRun: (runId) => api.post(`/security/agent-runs/${runId}/resume`),
  cancelRun: (runId) => api.post(`/security/agent-runs/${runId}/cancel`),
  getEvents: (runId, params) => api.get(`/security/agent-runs/${runId}/events`, { params }),
  getCoverage: (runId, params) => api.get(`/security/agent-runs/${runId}/coverage`, { params }),
  getRunCosts: (runId) => api.get(`/security/agent-runs/${runId}/costs`),
  getGraph: (runId, params) => api.get(`/security/agent-runs/${runId}/graph`, { params }),
  buildGraph: (runId) => api.post(`/security/agent-runs/${runId}/graph/build`),
  getGraphNeighbors: (runId, nodeId, params) =>
    api.get(`/security/agent-runs/${runId}/graph/nodes/${nodeId}/neighbors`, { params }),
  getGraphNodesByFile: (runId, params) =>
    api.get(`/security/agent-runs/${runId}/graph/by-file`, { params }),
  getGraphCodeSlice: (runId, params) =>
    api.get(`/security/agent-runs/${runId}/graph/code-slice`, { params }),
  sendMessage: (runId, content, clientMessageId) =>
    api.post(`/security/agent-runs/${runId}/messages`, {
      content,
      client_message_id: clientMessageId
    }),
  getRunPlans: (runId) => api.get(`/security/agent-runs/${runId}/plans`),
  getRunDecisions: (runId) => api.get(`/security/agent-runs/${runId}/decisions`),
  getObservations: (runId, params) =>
    api.get(`/security/agent-runs/${runId}/observations`, { params }),
  getObservation: (runId, observationId) =>
    api.get(`/security/agent-runs/${runId}/observations/${observationId}`),
  reviewObservation: (runId, observationId, data) =>
    api.post(`/security/agent-runs/${runId}/observations/${observationId}/review`, data),
  generateRemediationDiff: (runId, observationId) =>
    api.post(`/security/agent-runs/${runId}/observations/${observationId}/remediation-diff`),
  getApprovals: (params) => api.get(`/security/agent-approvals`, { params }),
  getRunApprovals: (runId) => api.get(`/security/agent-runs/${runId}/approvals`),
  resolveApproval: (runId, approvalId, data) =>
    api.post(`/security/agent-runs/${runId}/approvals/${approvalId}/resolve`, data),
  getProviderPolicy: (workspaceId) =>
    api.get(`/security/workspaces/${workspaceId}/agent-provider-policy`),
  updateProviderPolicy: (workspaceId, data) =>
    api.put(`/security/workspaces/${workspaceId}/agent-provider-policy`, data),
  getObservabilityOverview: (params) =>
    api.get(`/security/agent/observability/overview`, { params }),
  getObservabilityRuns: (params) =>
    api.get(`/security/agent/observability/runs`, { params }),
  createConversation: (projectId, data) => api.post(`/security/projects/${projectId}/agent-conversations`, data || {}),
  listProjectConversations: (projectId, params) => api.get(`/security/projects/${projectId}/agent-conversations`, { params }),
  getConversation: (conversationId) => api.get(`/security/agent-conversations/${conversationId}`),
  getConversationMessages: (conversationId, params) => api.get(`/security/agent-conversations/${conversationId}/messages`, { params }),
  postConversationMessage: (conversationId, data) => api.post(`/security/agent-conversations/${conversationId}/messages`, data),

  // 可重放 SSE：Last-Event-ID 只通过请求头传递，JWT 不进入 URL。
  // resolve：'ended'（服务端正常关闭）| 'aborted'（主动取消）；异常 throw。
  streamAgentEvents: async (runId, { lastEventId = 0, signal, onEvent } = {}) => {
    const token = localStorage.getItem('token')
    const headers = token ? { Authorization: `Bearer ${token}` } : {}
    headers['Last-Event-ID'] = String(lastEventId || 0)
    let response
    try {
      response = await fetch(`/api/security/agent-runs/${runId}/events/stream`, { headers, signal })
    } catch (error) {
      if (error?.name === 'AbortError') return 'aborted'
      throw error
    }
    if (!response.ok) {
      let message = '事件流请求失败'
      try {
        const body = await response.json()
        if (body?.error) message = body.error
      } catch (e) { /* ignore */ }
      if (response.status === 401) {
        handleSessionExpired()
        return 'ended'
      }
      const error = new Error(message)
      error.response = { status: response.status, data: { error: message } }
      throw error
    }
    if (!response.body) return 'ended'

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let separator
      while ((separator = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, separator)
        buffer = buffer.slice(separator + 2)
        parseAgentSSE(raw, onEvent)
      }
    }
    if (buffer.trim()) parseAgentSSE(buffer, onEvent)
    return 'ended'
  }
}

export const adminAPI = {
  getOverviewStats: () => api.get('/admin/stats/overview'),
  getQAStats: () => api.get('/admin/stats/qa'),
  getRagTrace: (traceId) => api.get(`/admin/rag/traces/${traceId}`),
  getRagEvaluationRuns: (params) => api.get('/admin/rag/evaluation-runs', { params }),
  getRagEvaluationRun: (runId, params) => api.get(`/admin/rag/evaluation-runs/${runId}`, { params }),

  getUsers: (params) => api.get('/admin/users', { params }),
  getUserDetail: (id) => api.get(`/admin/users/${id}/detail`),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),

  getAllKnowledge: (params) => api.get('/admin/knowledge/manage', { params }),
  auditKnowledge: (id, data) => api.post(`/admin/knowledge/${id}/audit`, data),
  updateKnowledge: (id, data) => api.put(`/admin/knowledge/${id}`, data),
  deleteKnowledge: (id) => api.delete(`/admin/knowledge/${id}`),

  getGraphStats: () => api.get('/admin/graph/stats'),
  getGraphNodes: (params) => api.get('/admin/graph/nodes', { params }),
  getGraphEdges: (params) => api.get('/admin/graph/edges', { params }),
  getGraphCommunities: () => api.get('/admin/graph/communities'),
  getCommunityNodes: (communityId, params) => api.get(`/admin/graph/communities/${communityId}/nodes`, { params }),
  getCommunitySummary: (communityId) => api.get(`/admin/graph/communities/${communityId}/summary`),
  generateCommunitySummary: (communityId, data) => api.post(`/admin/graph/communities/${communityId}/summary`, data),
  generateCommunitySummaries: (data) => api.post('/admin/graph/communities/summaries/batch', data),
  globalGraphSearch: (data) => api.post('/admin/graph/global-search', data),
  localGraphSearch: (data) => api.post('/admin/graph/local-search', data),

  // 图谱问答 SSE 流式：逐事件回调 { event, data }（reasoning/delta/done/error）
  graphSearchStream: async (path, data, { onEvent, onError, signal } = {}) => {
    const token = localStorage.getItem('token')
    let res
    try {
      res = await fetch(`/api/admin/graph/${path}`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : {},
        body: JSON.stringify(data),
        signal
      })
    } catch (e) {
      if (e?.name !== 'AbortError') onError?.(e)
      return
    }
    if (!res.ok) {
      let msg = '请求失败'
      try {
        const body = await res.json()
        if (body?.error) msg = body.error
      } catch (e) { /* ignore */ }
      if (res.status === 401) {
        handleSessionExpired()
        return
      }
      onError?.(new Error(msg))
      return
    }
    if (!res.body) {
      onError?.(new Error('浏览器不支持流式响应'))
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const flush = () => {
      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        parseSSEEvent(raw, onEvent)
      }
    }

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        flush()
      }
      if (buffer.trim()) parseSSEEvent(buffer, onEvent)
    } catch (e) {
      if (e?.name !== 'AbortError') onError?.(e)
    }
  },
  backfillDescriptions: (data) => api.post('/admin/graph/entities/backfill-descriptions', data),
  getBackfillStatus: () => api.get('/admin/graph/entities/backfill-descriptions/status'),
  getRelatedNodes: (id, params) => api.get(`/admin/graph/related/${id}`, { params }),
  getGraphPath: (params) => api.get('/admin/graph/path', { params }),
  getGraphCentrality: (params) => api.get('/admin/graph/centrality', { params }),
  mergeGraphNodes: (data) => api.post('/admin/graph/merge', data),
  deduplicateGraph: () => api.post('/admin/graph/deduplicate'),

  rebuildVectorIndex: () => api.post('/admin/vector/rebuild'),
  rebuildAllIndex: () => api.post('/admin/data/rebuild-index'),
  startVectorRebuildTask: (data) => api.post('/admin/vector/rebuild/task', data),
  getVectorRebuildStatus: () => api.get('/admin/vector/rebuild/task'),
  getRoles: () => api.get('/admin/roles'),

  // 数据初始化
  initSampleData: () => api.post('/admin/data/init'),

  // 系统配置
  getConfigs: () => api.get('/admin/config'),
  updateConfig: (key, data) => api.put(`/admin/config/${key}`, data)
}

// 系统相关
export const systemAPI = {
  health: () => api.get('/health')
}

// 政策文档相关
export const policyAPI = {
  list: () => api.get('/policies'),
  get: (slug) => api.get(`/policies/${slug}`),
  update: (slug, data) => api.put(`/policies/${slug}`, data)
}

// 持久记忆相关
export const memoryAPI = {
  list: (params) => api.get('/memories', { params }),
  create: (data) => api.post('/memories', data),
  update: (memoryId, data) => api.put(`/memories/${memoryId}`, data),
  remove: (memoryId) => api.delete(`/memories/${memoryId}`),
  feedback: (memoryId, rating) => api.post(`/memories/${memoryId}/feedback`, { rating }),
  dream: (data) => api.post('/memories/dream', data),
  dreamAudits: () => api.get('/memories/dream/audits')
}

// 用户活跃统计（个人中心热力图）
export const userAPI = {
  getActivity: () => api.get('/user/activity')
}

// 帮助中心相关（公开读取 + 管理员 CRUD）
export const helpAPI = {
  getTree: () => api.get('/help/tree'),
  getDocument: (slug) => api.get(`/help/documents/${slug}`),
  getAdminTree: () => api.get('/help/admin/tree'),
  getAdminDocument: (documentId) => api.get(`/help/admin/documents/${documentId}`),
  createCategory: (data) => api.post('/help/admin/categories', data),
  updateCategory: (categoryId, data) => api.put(`/help/admin/categories/${categoryId}`, data),
  deleteCategory: (categoryId) => api.delete(`/help/admin/categories/${categoryId}`),
  createDocument: (data) => api.post('/help/admin/documents', data),
  updateDocument: (documentId, data) => api.put(`/help/admin/documents/${documentId}`, data),
  deleteDocument: (documentId) => api.delete(`/help/admin/documents/${documentId}`)
}

export default api
