import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
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
          ElMessage.error('登录已过期，请重新登录')
          localStorage.removeItem('token')
          localStorage.removeItem('user')
          router.push('/login')
          break
        case 403:
          ElMessage.error(data.error || '权限不足')
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
  changePassword: (data) => api.put('/auth/password', data),
  getLoginLogs: (params) => api.get('/auth/login-logs', { params }),
  checkAvailable: (params) => api.get('/auth/check', { params })
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
  ask: (data) => api.post('/qa/ask', data),
  getSuggestions: (params) => api.get('/qa/suggestions', { params }),
  getSimilar: (params) => api.get('/qa/similar', { params }),
  getHistory: (params) => api.get('/qa/history', { params }),
  getRecord: (id) => api.get(`/qa/${id}`),
  submitFeedback: (id, data) => api.post(`/qa/${id}/feedback`, data),
  
  // 会话管理
  getConversations: (params) => api.get('/qa/conversations', { params }),
  createConversation: (data) => api.post('/qa/conversations', data),
  getConversation: (id) => api.get(`/qa/conversations/${id}`),
  updateConversation: (id, data) => api.put(`/qa/conversations/${id}`, data),
  deleteConversation: (id) => api.delete(`/qa/conversations/${id}`),
  
  // 收藏
  getFavorites: (params) => api.get('/qa/favorites', { params }),
  addFavorite: (data) => api.post('/qa/favorites', data),
  removeFavorite: (id) => api.delete(`/qa/favorites/${id}`)
}

// 管理后台相关
export const securityAPI = {
  createProject: (data) => api.post('/security/projects', data),
  listProjects: () => api.get('/security/projects'),
  uploadSnapshot: (projectId, formData) => api.post(`/security/projects/${projectId}/snapshots:upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  importGitHubSnapshot: (projectId, data) => api.post(`/security/projects/${projectId}/snapshots:github`, data),
  getTasks: (projectId) => api.get(`/security/projects/${projectId}/tasks`),
  getTask: (taskId) => api.get(`/security/tasks/${taskId}`),
  getFindings: (taskId) => api.get(`/security/tasks/${taskId}/findings`),
  cancelTask: (taskId) => api.post(`/security/tasks/${taskId}/cancel`),
  retryTask: (taskId) => api.post(`/security/tasks/${taskId}/retry`),
  getDependencies: (projectId, params) => api.get(`/security/projects/${projectId}/dependencies`, { params }),

  listKnowledgeSources: (params) => api.get('/security/knowledge/sources', { params }),
  createKnowledgeSource: (data) => api.post('/security/knowledge/sources', data),
  listKnowledgeDocuments: (sourceId, params) => api.get(`/security/knowledge/sources/${sourceId}/documents`, { params }),
  createKnowledgeDocument: (sourceId, data) => api.post(`/security/knowledge/sources/${sourceId}/documents`, data),

  generateRemediationSuggestion: (findingId) => api.post(`/security/findings/${findingId}/suggestions`),
  listRemediationSuggestions: (findingId, params) => api.get(`/security/findings/${findingId}/suggestions`, { params }),
  reviewRemediationSuggestion: (suggestionId, data) => api.post(`/security/suggestions/${suggestionId}/review`, data)
}

export const adminAPI = {
  getOverviewStats: () => api.get('/admin/stats/overview'),
  getQAStats: () => api.get('/admin/stats/qa'),

  getUsers: (params) => api.get('/admin/users', { params }),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),

  getAllKnowledge: (params) => api.get('/admin/knowledge/manage', { params }),
  auditKnowledge: (id, data) => api.post(`/admin/knowledge/${id}/audit`, data),
  updateKnowledge: (id, data) => api.put(`/admin/knowledge/${id}`, data),
  deleteKnowledge: (id) => api.delete(`/admin/knowledge/${id}`),

  getGraphStats: () => api.get('/admin/graph/stats'),
  getGraphNodes: (params) => api.get('/admin/graph/nodes', { params }),
  getGraphEdges: () => api.get('/admin/graph/edges'),
  getRelatedNodes: (id, params) => api.get(`/admin/graph/related/${id}`, { params }),

  rebuildVectorIndex: () => api.post('/admin/vector/rebuild'),
  rebuildAllIndex: () => api.post('/admin/data/rebuild-index'),
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

export default api
