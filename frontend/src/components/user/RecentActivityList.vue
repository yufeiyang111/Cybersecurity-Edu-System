<template>
  <div class="activity-card">
    <div class="activity-card__header">
      <h3 class="activity-card__title">近期问答</h3>
      <span class="activity-card__sub">最近活跃的 3 条</span>
    </div>

    <div v-loading="loading" class="activity-card__body">
      <el-empty v-if="!loading && !records.length" description="暂无问答记录" :image-size="80" />

      <div v-else class="activity-list">
        <div v-for="r in records" :key="r.id" class="activity-item" @click="goAsk(r)">
          <div class="activity-item__icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div class="activity-item__main">
            <div class="activity-item__title">{{ r.question }}</div>
            <div class="activity-item__meta">
              <span>{{ formatRelativeTime(r.created_at) }}</span>
              <el-tag
                v-if="r.feedback"
                size="small"
                :type="feedbackType(r.feedback)"
                effect="plain"
              >
                {{ feedbackText(r.feedback) }}
              </el-tag>
              <el-tag v-else size="small" type="info" effect="plain">未反馈</el-tag>
            </div>
          </div>
          <el-icon class="activity-item__arrow"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { qaAPI } from '@/api'
import { formatRelativeTime } from '@/features/user/format'

const router = useRouter()
const loading = ref(false)
const records = ref([])

const feedbackType = (fb) => {
  const types = { good: 'success', neutral: 'info', bad: 'danger' }
  return types[fb] || 'info'
}

const feedbackText = (fb) => {
  const texts = { good: '满意', neutral: '一般', bad: '不满意' }
  return texts[fb] || ''
}

const goAsk = (row) => {
  if (row.conversation_id) {
    router.push({ path: '/qa', query: { conversation_id: row.conversation_id } })
  } else {
    router.push({ path: '/qa', query: { topic: row.question } })
  }
}

const fetchRecent = async () => {
  loading.value = true
  try {
    const res = await qaAPI.getHistory({ page: 1, per_page: 3 })
    records.value = res.records || []
  } catch (error) {
    records.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchRecent()
})
</script>

<style lang="scss" scoped>
@use '@/styles/user-vars' as *;

.activity-card {
  padding: 20px;
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 8px;
  box-shadow: $shadow-soft;
}

.activity-card__header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.activity-card__title {
  font-size: 16px;
  font-weight: 600;
  color: $text-primary;
  margin: 0;
}

.activity-card__sub {
  font-size: 12px;
  color: $text-secondary;
}

.activity-list {
  display: flex;
  flex-direction: column;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: $bg-hover;
  }
}

.activity-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 6px;
  background: $brand-light;
  color: $brand-color;
  font-size: 16px;
}

.activity-item__main {
  flex: 1;
  min-width: 0;
}

.activity-item__title {
  font-weight: 600;
  font-size: 14px;
  color: $text-primary;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.activity-item__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: $text-secondary;
}

.activity-item__arrow {
  margin-top: 8px;
  color: $text-placeholder;
  flex-shrink: 0;
}
</style>
