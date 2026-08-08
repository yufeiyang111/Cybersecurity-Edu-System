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
      <div ref="messageListRef" class="message-list" @scroll="handleScroll">
        <div v-if="loadingEarlier" class="loading-earlier">正在加载更早的消息…</div>
        <div
          v-for="msg in messages"
          :key="msg.key"
          class="message-item"
        >
          <div v-if="msg.role === 'user'" class="message-user">
            <el-avatar :size="36" :src="userStore.user?.avatar_url || undefined">
              {{ userStore.user?.nickname?.[0] || userStore.user?.username?.[0] || '用户' }}
            </el-avatar>
            <div class="message-bubble user-bubble">
              <p>{{ msg.content }}</p>
            </div>
          </div>
          <div v-else class="message-assistant">
            <el-avatar :size="36" color="#67c23a">
              <el-icon :size="24"><ElementPlus /></el-icon>
            </el-avatar>
            <div class="message-bubble assistant-bubble">
              <div v-if="msg.sources?.length" class="source-info">
                <span>来源：</span>
                <el-tag
                  v-for="(source, sIdx) in msg.sources"
                  :key="sIdx"
                  size="small"
                >
                  {{ source.title }}
                </el-tag>
              </div>
              <div class="answer-content markdown-content" v-html="renderMarkdownSafe(msg.content)"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'
import { useConversationMessages } from '@/composables/chat/useConversationMessages'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const conversation = ref(null)
const messageListRef = ref(null)

const {
  messages,
  loading,
  loadingEarlier,
  loadInitial,
  loadEarlier
} = useConversationMessages(messageListRef)

const renderMarkdownSafe = (content) => {
  return renderMarkdown(content)
}

// 向上滚动到顶部时加载更早的消息
const handleScroll = () => {
  if (messageListRef.value && messageListRef.value.scrollTop < 40) {
    loadEarlier()
  }
}

const fetchConversation = async () => {
  try {
    conversation.value = await loadInitial(route.params.id)
  } catch (error) {
    router.push('/qa')
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

.loading-earlier {
  text-align: center;
  font-size: 12px;
  color: #909399;
  padding: 8px 0;
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
