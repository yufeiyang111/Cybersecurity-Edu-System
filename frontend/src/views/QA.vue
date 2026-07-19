<template>
  <div class="qa-page">
    <!-- 顶部导航 -->
    <header class="qa-header">
      <div class="header-left">
        <div class="logo" @click="$router.push('/')">
          <el-icon :size="28" color="#10b981"><Shield /></el-icon>
          <span>智能问答</span>
        </div>
      </div>
      <div class="header-right">
        <el-select v-model="currentConversation" placeholder="选择会话" clearable @change="handleConversationChange">
          <el-option
            v-for="conv in conversations"
            :key="conv.id"
            :label="conv.title"
            :value="conv.id"
          />
        </el-select>
        <el-button @click="createNewConversation">新建会话</el-button>
      </div>
    </header>

    <div class="qa-container">
      <!-- 左侧会话列表 -->
      <aside class="qa-sidebar">
        <div class="sidebar-header">
          <span>会话列表</span>
        </div>
        <div class="conversation-list">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="conversation-item"
            :class="{ active: currentConversation === conv.id }"
            @click="selectConversation(conv)"
          >
            <el-icon><ChatDotRound /></el-icon>
            <span class="conv-title">{{ conv.title || '新会话' }}</span>
            <el-dropdown trigger="click" @command="handleConvCommand($event, conv)">
              <el-icon class="conv-actions"><MoreFilled /></el-icon>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </aside>

      <!-- 主聊天区域 -->
      <main class="qa-main">
        <!-- 欢迎信息 -->
        <div v-if="messages.length === 0" class="welcome-area">
          <div class="welcome-icon">
            <el-icon :size="64" color="#10b981"><ChatDotSquare /></el-icon>
          </div>
          <h2>欢迎使用网络安全智能问答系统</h2>
          <p>我可以帮助您解答网络安全相关的问题，包括但不限于：</p>
          <div class="welcome-topics">
            <el-tag v-for="topic in welcomeTopics" :key="topic" @click="quickAsk(topic)">
              {{ topic }}
            </el-tag>
          </div>
        </div>

        <!-- 消息列表 -->
        <div v-else ref="messageListRef" class="message-list">
          <div v-for="(msg, index) in messages" :key="index" class="message-item" :class="msg.role">
            <div class="message-avatar">
              <el-avatar v-if="msg.role === 'user'" :size="36" :src="userStore.user?.avatar_url || undefined">
                {{ userStore.user?.nickname?.[0] || userStore.user?.username?.[0] || '用户' }}
              </el-avatar>
              <el-avatar v-else :size="36" color="#0d9488">
                <el-icon :size="24"><ElementPlus /></el-icon>
              </el-avatar>
            </div>
            <div class="message-content">
              <div class="message-bubble">
                <div v-if="msg.role === 'assistant' && msg.sources?.length" class="source-info">
                  <span class="source-label">知识来源：</span>
                  <el-tag
                    v-for="(source, sIdx) in msg.sources"
                    :key="sIdx"
                    size="small"
                    class="source-tag"
                    @click="showSourceDetail(source)"
                  >
                    {{ source.title || source.id }}
                  </el-tag>
                </div>
                <div class="message-text markdown-content" v-html="renderMarkdown(msg.content)"></div>
                <div v-if="msg.confidence" class="confidence-info">
                  <span>置信度：</span>
                  <el-rate v-model="msg.confidence" disabled show-score :max="1" size="small" />
                </div>
              </div>
              
              <!-- 助手消息操作 -->
              <div v-if="msg.role === 'assistant'" class="message-actions">
                <el-button-group size="small">
                  <el-button @click="toggleFavorite(msg)" :type="msg.isFavorite ? 'warning' : ''">
                    <el-icon><Star /></el-icon>
                    {{ msg.isFavorite ? '已收藏' : '收藏' }}
                  </el-button>
                  <el-button @click="copyMessage(msg.content)">
                    <el-icon><CopyDocument /></el-icon>复制
                  </el-button>
                  <el-button @click="shareMessage(msg)">
                    <el-icon><Share /></el-icon>分享
                  </el-button>
                </el-button-group>
                
                <div class="feedback-section">
                  <span>答案满意吗？</span>
                  <el-button
                    v-for="fb in ['good', 'neutral', 'bad']"
                    :key="fb"
                    size="small"
                    :type="msg.feedback === fb ? getFeedbackType(fb) : ''"
                    @click="submitFeedback(msg, fb)"
                  >
                    {{ getFeedbackText(fb) }}
                  </el-button>
                </div>
              </div>
            </div>
          </div>
          
          <!-- 加载状态 -->
          <div v-if="loading" class="message-item assistant">
            <div class="message-avatar">
              <el-avatar :size="36" color="#67c23a">
                <el-icon :size="24"><ElementPlus /></el-icon>
              </el-avatar>
            </div>
            <div class="message-content">
              <div class="message-bubble loading">
                <el-icon class="is-loading" :size="20"><Loading /></el-icon>
                <span>正在思考中...</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部输入区 -->
        <div class="input-area">
          <div class="input-container">
            <div class="category-select" v-if="categories.length">
              <el-select v-model="selectedCategory" placeholder="选择分类（可选）" clearable size="small">
                <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
              </el-select>
            </div>
            <el-input
              v-model="question"
              type="textarea"
              :rows="3"
              placeholder="请输入您的网络安全问题..."
              resize="none"
              @keydown.enter.ctrl="handleSubmit"
            />
            <div class="input-actions">
              <div class="suggestions" v-if="suggestions.length && question">
                <span>推荐问题：</span>
                <el-tag
                  v-for="(sug, idx) in suggestions"
                  :key="idx"
                  size="small"
                  @click="selectSuggestion(sug)"
                >
                  {{ sug }}
                </el-tag>
              </div>
              <el-button type="primary" :loading="loading" @click="handleSubmit" :disabled="!question.trim()">
                <el-icon><Promotion /></el-icon>
                发送问题
              </el-button>
            </div>
          </div>
        </div>
      </main>
    </div>

    <!-- 来源详情弹窗 -->
    <el-dialog v-model="sourceDialogVisible" title="知识来源详情" width="600px">
      <div v-if="currentSource" class="source-detail">
        <h3>{{ currentSource.title }}</h3>
        <el-divider />
        <div class="source-meta">
          <span>来源：{{ currentSource.source }}</span>
          <span>相似度：{{ (currentSource.similarity * 100).toFixed(1) }}%</span>
        </div>
        <el-divider />
        <div class="source-content markdown-content">
          {{ currentSource.content || '暂无详细内容' }}
        </div>
      </div>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { qaAPI, knowledgeAPI } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import hljs from 'highlight.js'

// 配置 marked
marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  }
})

const router = useRouter()
const userStore = useUserStore()

const messages = ref([])
const question = ref('')
const loading = ref(false)
const suggestions = ref([])
const conversations = ref([])
const currentConversation = ref(null)
const categories = ref([])
const selectedCategory = ref(null)
const messageListRef = ref(null)
const sourceDialogVisible = ref(false)
const currentSource = ref(null)

const welcomeTopics = [
  '什么是SQL注入攻击？',
  '如何防范XSS跨站脚本攻击？',
  'HTTPS工作原理',
  '缓冲区溢出漏洞原理',
  'CSRF攻击与防护'
]

// 渲染 Markdown
const renderMarkdown = (content) => {
  if (!content) return ''
  try {
    return marked(content)
  } catch (e) {
    console.error('Markdown渲染错误:', e)
    return content // 降级返回原文
  }
}

// 获取反馈相关
const getFeedbackType = (fb) => {
  const types = { good: 'success', neutral: 'info', bad: 'danger' }
  return types[fb]
}

const getFeedbackText = (fb) => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[fb]
}

// 创建新会话
const createNewConversation = async () => {
  try {
    const res = await qaAPI.createConversation({ title: `会话 ${Date.now()}` })
    conversations.value.unshift(res.conversation)
    currentConversation.value = res.conversation.id
    messages.value = []
  } catch (error) {
    ElMessage.error('创建会话失败')
  }
}

// 选择会话
const selectConversation = async (conv) => {
  currentConversation.value = conv.id
  try {
    const res = await qaAPI.getConversation(conv.id)
    // 按时间顺序交替添加用户消息和AI回答
    messages.value = []
    for (const r of res.conversation.records) {
      // 添加用户问题
      messages.value.push({
        role: 'user',
        content: r.question
      })
      // 添加AI回答
      if (r.answer) {
        messages.value.push({
          role: 'assistant',
          content: r.answer,
          sources: r.sources,
          confidence: r.confidence,
          feedback: r.feedback,
          isFavorite: r.is_favorited,
          favoriteId: r.favoriteId || null,
          recordId: r.id
        })
      }
    }
    scrollToBottom()
  } catch (error) {
    ElMessage.error('加载会话失败')
  }
}

// 会话变更
const handleConversationChange = (val) => {
  if (val) {
    const conv = conversations.value.find(c => c.id === val)
    if (conv) selectConversation(conv)
  } else {
    messages.value = []
  }
}

// 会话操作
const handleConvCommand = async (command, conv) => {
  if (command === 'rename') {
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
    } catch (error) {
      if (error !== 'cancel') ElMessage.error('重命名失败')
    }
  } else if (command === 'delete') {
    try {
      await qaAPI.deleteConversation(conv.id)
      conversations.value = conversations.value.filter(c => c.id !== conv.id)
      if (currentConversation.value === conv.id) {
        currentConversation.value = null
        messages.value = []
      }
      ElMessage.success('删除成功')
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }
}

// 提交问题
const handleSubmit = async () => {
  const q = question.value.trim()
  if (!q || loading.value) return
  
  // 添加用户消息
  messages.value.push({
    role: 'user',
    content: q
  })
  
  question.value = ''
  suggestions.value = []
  loading.value = true
  scrollToBottom()
  
  try {
    const res = await qaAPI.ask({
      question: q,
      conversation_id: currentConversation.value,
      category_id: selectedCategory.value
    })
    
    messages.value.push({
      role: 'assistant',
      content: res.answer,
      sources: res.sources,
      confidence: res.confidence,
      recordId: res.id
    })
    
    scrollToBottom()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '抱歉，生成答案时出现错误，请稍后重试。'
    })
    ElMessage.error('生成答案失败')
  } finally {
    loading.value = false
  }
}

// 快速提问
const quickAsk = (topic) => {
  question.value = topic
  handleSubmit()
}

// 实时获取建议
watch(question, async (val) => {
  if (val.trim().length > 2) {
    try {
      const res = await qaAPI.getSuggestions({ q: val })
      suggestions.value = res.suggestions || []
    } catch (error) {
      suggestions.value = []
    }
  } else {
    suggestions.value = []
  }
})

// 选择建议
const selectSuggestion = (sug) => {
  question.value = sug.replace(/^追问：/, '').replace(/^追问:/, '')
  suggestions.value = []
}

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 收藏
const toggleFavorite = async (msg) => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }

  if (msg.isFavorite && msg.favoriteId) {
    // 取消收藏
    try {
      await qaAPI.removeFavorite(msg.favoriteId)
      msg.isFavorite = false
      msg.favoriteId = null
      ElMessage.success('已取消收藏')
    } catch (error) {
      ElMessage.error('取消收藏失败')
    }
  } else if (!msg.isFavorite && msg.recordId) {
    // 添加收藏
    try {
      const res = await qaAPI.addFavorite({ qa_record_id: msg.recordId })
      msg.isFavorite = true
      msg.favoriteId = res.id
      ElMessage.success('已添加收藏')
    } catch (error) {
      console.error('收藏失败:', error)
      ElMessage.error('收藏失败')
    }
  } else {
    ElMessage.warning('无法收藏此消息')
  }
}

// 复制
const copyMessage = (content) => {
  navigator.clipboard.writeText(content).then(() => {
    ElMessage.success('已复制到剪贴板')
  })
}

// 分享
const shareMessage = (msg) => {
  ElMessage.info('分享功能开发中')
}

// 反馈
const submitFeedback = async (msg, type) => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录')
    return
  }
  
  try {
    await qaAPI.submitFeedback(msg.recordId, { feedback: type })
    msg.feedback = type
    ElMessage.success('感谢您的反馈')
  } catch (error) {
    ElMessage.error('反馈失败')
  }
}

// 显示来源详情
const showSourceDetail = async (source) => {
  currentSource.value = source
  try {
    const res = await knowledgeAPI.getKnowledge(source.id)
    currentSource.value = {
      ...currentSource.value,
      content: res.item?.content
    }
  } catch (error) {
    console.error('获取来源详情失败')
  }
  sourceDialogVisible.value = true
}

// 加载会话列表
const loadConversations = async () => {
  try {
    const res = await qaAPI.getConversations({ per_page: 50 })
    conversations.value = res.conversations || []
  } catch (error) {
    console.error('加载会话列表失败')
  }
}

// 加载分类
const loadCategories = async () => {
  try {
    const res = await knowledgeAPI.getCategories()
    categories.value = res.categories || []
  } catch (error) {
    console.error('加载分类失败')
  }
}

onMounted(() => {
  if (!userStore.isLoggedIn) {
    ElMessage.info('登录后可保存问答历史')
  }
  loadConversations()
  loadCategories()
})
</script>

<style lang="scss" scoped>
.qa-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #f5f7fa 0%, #e4e7ed 100%);
}

.qa-header {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

  .header-left {
    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 20px;
      font-weight: 600;
      color: #303133;
      cursor: pointer;
      transition: color 0.2s;

      &:hover {
        color: #10b981;
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }
}

.qa-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.qa-sidebar {
  width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.02);

  .sidebar-header {
    padding: 20px 16px;
    font-weight: 600;
    color: #303133;
    border-bottom: 1px solid #f0f0f0;
    display: flex;
    align-items: center;
    gap: 8px;

    .el-icon {
      color: #10b981;
    }
  }

  .conversation-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px;

    .conversation-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 10px;
      cursor: pointer;
      transition: all 0.2s;
      margin-bottom: 4px;

      &:hover {
        background: #f5f7fa;
      }

      &.active {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        color: #10b981;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.15);
      }

      .conv-title {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 14px;
      }

      .conv-actions {
        opacity: 0;
        transition: opacity 0.2s;
      }

      &:hover .conv-actions {
        opacity: 1;
      }
    }
  }
}

.qa-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fafafa;
}

.welcome-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  animation: fadeIn 0.5s ease;

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .welcome-icon {
    width: 100px;
    height: 100px;
    background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
    border-radius: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 32px;
    box-shadow: 0 8px 24px rgba(16, 185, 129, 0.3);

    .el-icon {
      font-size: 48px;
      color: #fff;
    }
  }

  h2 {
    font-size: 28px;
    color: #303133;
    margin-bottom: 16px;
    font-weight: 600;
  }

  p {
    color: #909399;
    margin-bottom: 32px;
    font-size: 15px;
  }

  .welcome-topics {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    justify-content: center;
    max-width: 600px;

    .el-tag {
      cursor: pointer;
      padding: 12px 20px;
      font-size: 14px;
      border-radius: 20px;
      transition: all 0.2s;
      border: 1px solid #dcdfe6;

      &:hover {
        background: #10b981;
        color: #fff;
        border-color: #10b981;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
      }
    }
  }
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  scroll-behavior: smooth;

  .message-item {
    display: flex;
    gap: 16px;
    margin-bottom: 28px;
    animation: messageIn 0.3s ease;

    @keyframes messageIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    &.user {
      flex-direction: row-reverse;

      .message-avatar {
        .el-avatar {
          background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
        }
      }

      .message-bubble {
        background: linear-gradient(135deg, #10b981 0%, #14b8a6 100%);
        color: #fff;
        border-radius: 20px 20px 4px 20px;
        box-shadow: 0 4px 16px rgba(16, 185, 129, 0.3);
      }
    }

    &.assistant {
      .message-avatar {
        .el-avatar {
          background: linear-gradient(135deg, #0d9488 0%, #14b8a6 100%);
        }
      }

      .message-bubble {
        background: #fff;
        border-radius: 20px 20px 20px 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
        border: 1px solid #f0f0f0;
      }
    }

    .message-content {
      max-width: 72%;
      display: flex;
      flex-direction: column;
      gap: 8px;

      .message-bubble {
        padding: 18px 22px;
        line-height: 1.7;

        &.loading {
          display: flex;
          align-items: center;
          gap: 12px;
          color: #909399;
          padding: 20px 24px;

          .el-icon {
            animation: spin 1s linear infinite;
          }

          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        }

        .source-info {
          margin-bottom: 14px;
          padding-bottom: 14px;
          border-bottom: 1px solid #f0f0f0;
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;

          .source-label {
            font-size: 12px;
            color: #909399;
            font-weight: 500;
          }

          .source-tag {
            cursor: pointer;
            transition: all 0.2s;

            &:hover {
              opacity: 0.8;
              transform: scale(1.02);
            }
          }
        }

        .confidence-info {
          margin-top: 12px;
          font-size: 12px;
          color: #909399;
          display: flex;
          align-items: center;
          gap: 8px;
        }
      }

      .message-actions {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding-left: 4px;

        .el-button-group {
          .el-button {
            border-radius: 16px;
          }
        }

        .feedback-section {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 13px;
          color: #909399;
          padding: 8px 12px;
          background: rgba(0, 0, 0, 0.02);
          border-radius: 8px;
          width: fit-content;

          .el-button {
            padding: 4px 10px;
            font-size: 12px;
          }
        }
      }
    }
  }
}

.input-area {
  padding: 20px 24px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.02);

  .input-container {
    max-width: 900px;
    margin: 0 auto;

    .category-select {
      margin-bottom: 14px;

      .el-select {
        width: 200px;
      }
    }

    .el-textarea {
      :deep(.el-textarea__inner) {
        border-radius: 16px;
        padding: 14px 18px;
        font-size: 15px;
        line-height: 1.6;
        transition: all 0.2s;

        &:focus {
          box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
        }
      }
    }

    .input-actions {
      margin-top: 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;

      .suggestions {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        font-size: 13px;
        color: #909399;

        .el-tag {
          cursor: pointer;
          transition: all 0.2s;

          &:hover {
            color: #10b981;
            border-color: #10b981;
          }
        }
      }

      .el-button {
        padding: 12px 28px;
        border-radius: 20px;
        font-size: 15px;
      }
    }
  }
}

.source-detail {
  h3 {
    margin: 0 0 16px;
    color: #303133;
  }

  .source-meta {
    display: flex;
    gap: 24px;
    color: #909399;
    font-size: 14px;
  }

  .source-content {
    max-height: 400px;
    overflow-y: auto;
    line-height: 1.8;
  }
}
</style>
