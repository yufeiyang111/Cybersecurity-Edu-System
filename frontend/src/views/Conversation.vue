<template>
  <div class="conversation-page">
    <header class="page-header">
      <div class="header-content">
        <el-button text @click="$router.push('/qa')">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1>{{ conversation?.title || '会话详情' }}</h1>
      </div>
    </header>

    <div class="conversation-container" v-loading="loading">
      <div ref="messageListRef" class="message-list">
        <div
          v-for="(record, index) in records"
          :key="index"
          class="message-item"
        >
          <div class="message-user">
            <el-avatar :size="36" :src="userStore.user?.avatar_url || undefined">
              {{ userStore.user?.nickname?.[0] || userStore.user?.username?.[0] || '用户' }}
            </el-avatar>
            <div class="message-bubble user-bubble">
              <p>{{ record.question }}</p>
            </div>
          </div>
          <div class="message-assistant">
            <el-avatar :size="36" color="#67c23a">
              <el-icon :size="24"><ElementPlus /></el-icon>
            </el-avatar>
            <div class="message-bubble assistant-bubble">
              <div v-if="record.sources?.length" class="source-info">
                <span>来源：</span>
                <el-tag
                  v-for="(source, sIdx) in record.sources"
                  :key="sIdx"
                  size="small"
                >
                  {{ source.title }}
                </el-tag>
              </div>
              <div class="answer-content markdown-content" v-html="renderMarkdown(record.answer)"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { qaAPI } from '@/api'
import { marked } from 'marked'
import hljs from 'highlight.js'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const conversation = ref(null)
const records = ref([])
const messageListRef = ref(null)

marked.setOptions({
  highlight: function(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  }
})

const renderMarkdown = (content) => {
  if (!content) return ''
  return marked(content)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

const fetchConversation = async () => {
  loading.value = true
  try {
    const res = await qaAPI.getConversation(route.params.id)
    conversation.value = res.conversation
    records.value = res.conversation.records || []
    scrollToBottom()
  } catch (error) {
    router.push('/qa')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchConversation()
})
</script>

<style lang="scss" scoped>
.conversation-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.page-header {
  background: #fff;
  padding: 12px 20px;
  border-bottom: 1px solid #e4e7ed;

  .header-content {
    display: flex;
    align-items: center;
    gap: 16px;
    max-width: 900px;
    margin: 0 auto;

    h1 {
      margin: 0;
      font-size: 18px;
      color: #303133;
    }
  }
}

.conversation-container {
  flex: 1;
  overflow: hidden;
  padding: 20px;
}

.message-list {
  max-width: 900px;
  margin: 0 auto;
  height: 100%;
  overflow-y: auto;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
}

.message-item {
  margin-bottom: 24px;

  .message-user, .message-assistant {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
  }

  .message-assistant {
    flex-direction: row;
  }

  .message-bubble {
    max-width: 70%;

    p {
      margin: 0;
      line-height: 1.6;
    }
  }

  .user-bubble {
    padding: 12px 16px;
    background: #409eff;
    color: #fff;
    border-radius: 12px 12px 4px 12px;
  }

  .assistant-bubble {
    padding: 16px;
    background: #f5f7fa;
    border-radius: 12px 12px 12px 4px;

    .source-info {
      margin-bottom: 12px;
      padding-bottom: 12px;
      border-bottom: 1px solid #e4e7ed;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: #909399;
    }
  }
}
</style>
