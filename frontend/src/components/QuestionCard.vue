<template>
  <el-card class="question-card" :class="{ 'is-loading': loading }">
    <div class="card-header">
      <div class="user-info">
        <el-avatar :size="32" :src="question.user?.avatar_url || undefined">
  {{ question.user?.nickname?.[0] || question.user?.username?.[0] || '匿名' }}
</el-avatar>
        <span class="username">{{ question.user?.nickname || '匿名用户' }}</span>
        <span class="time">{{ formatTime(question.created_at) }}</span>
      </div>
      <el-tag v-if="question.feedback" :type="feedbackType" size="small">
        {{ feedbackText }}
      </el-tag>
    </div>

    <div class="question-content">
      <div class="q-label">问题</div>
      <div class="q-text">{{ question.question || '（无问题内容）' }}</div>
    </div>

    <el-divider v-if="question.answer" />

    <div v-if="question.answer" class="answer-content">
      <div class="a-label">答案</div>
      <div class="a-text markdown-renderer" v-html="renderedAnswer"></div>
      
      <div v-if="question.sources?.length" class="sources">
        <div class="sources-label">知识来源</div>
        <div class="sources-list">
          <el-tag
            v-for="(source, idx) in question.sources"
            :key="idx"
            size="small"
            class="source-tag"
            @click="$emit('view-source', source)"
          >
            {{ source.title || source.id }}
          </el-tag>
        </div>
      </div>
    </div>

    <div class="card-actions">
      <el-button-group size="small">
        <el-button @click="$emit('view')">
          <el-icon><View /></el-icon> 查看
        </el-button>
        <el-button @click="$emit('continue')">
          <el-icon><ChatDotRound /></el-icon> 继续问
        </el-button>
        <el-button @click="toggleFavorite" :type="isFavorited ? 'warning' : ''">
          <el-icon><Star /></el-icon> {{ isFavorited ? '已收藏' : '收藏' }}
        </el-button>
      </el-button-group>
      
      <div v-if="showFeedback" class="feedback-buttons">
        <span>评价：</span>
        <el-button
          v-for="fb in feedbackOptions"
          :key="fb.value"
          size="small"
          :type="question.feedback === fb.value ? fb.type : ''"
          @click="$emit('feedback', fb.value)"
        >
          {{ fb.label }}
        </el-button>
      </div>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { renderMarkdown } from '@/features/markdown/renderMarkdown'

const userStore = useUserStore()

const props = defineProps({
  question: {
    type: Object,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  showFeedback: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['view', 'continue', 'feedback', 'favorite', 'view-source'])

const isFavorited = ref(props.question.is_favorited || false)

const feedbackOptions = [
  { value: 'good', label: '满意', type: 'success' },
  { value: 'neutral', label: '一般', type: 'info' },
  { value: 'bad', label: '不满意', type: 'danger' }
]

const feedbackType = computed(() => {
  const types = { good: 'success', neutral: 'info', bad: 'danger' }
  return types[props.question.feedback] || 'info'
})

const feedbackText = computed(() => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[props.question.feedback] || ''
})

const renderedAnswer = computed(() => {
  return renderMarkdown(props.question.answer)
})

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`
  return date.toLocaleDateString('zh-CN')
}

const toggleFavorite = () => {
  isFavorited.value = !isFavorited.value
  emit('favorite', isFavorited.value)
}
</script>

<style lang="scss" scoped>
.question-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;

      .username {
        font-weight: 500;
        color: #303133;
      }

      .time {
        color: #909399;
        font-size: 12px;
      }
    }
  }

  .question-content {
    .q-label, .a-label {
      font-size: 12px;
      color: #909399;
      margin-bottom: 8px;
    }

    .q-text {
      font-size: 16px;
      color: #303133;
      line-height: 1.6;
      padding: 12px 16px;
      background: #f5f7fa;
      border-radius: 8px;
      border-left: 4px solid #409eff;
    }
  }

  .answer-content {
    .a-text {
      padding: 12px 16px;
      background: #fff;
      border-radius: 8px;
    }

    .sources {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px dashed #eee;

      .sources-label {
        font-size: 12px;
        color: #909399;
        margin-bottom: 8px;
      }

      .sources-list {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;

        .source-tag {
          cursor: pointer;
          &:hover {
            opacity: 0.8;
          }
        }
      }
    }
  }

  .card-actions {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #f0f0f0;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .feedback-buttons {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: #909399;
    }
  }

  &.is-loading {
    opacity: 0.7;
  }
}
</style>
