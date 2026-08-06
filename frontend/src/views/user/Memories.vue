<template>
  <div class="memories-page">
    <ProfileTabs
      :questions="0"
      :favorites="0"
    />

    <section class="memories-card">
      <div class="memories-card__header">
        <div>
          <h3>我的持久记忆</h3>
          <span class="memories-card__sub">系统从你的问答中记住的事实，回答时会自动参考</span>
        </div>
        <div class="memories-card__filters">
          <select v-model="category" class="memories-card__select" @change="load">
            <option value="">全部分类</option>
            <option value="preference">偏好</option>
            <option value="fact">事实</option>
            <option value="decision">决定</option>
            <option value="goal">目标</option>
            <option value="other">其他</option>
          </select>
        </div>
      </div>

      <div v-if="errorMessage" class="memories-card__error">{{ errorMessage }}</div>

      <div v-if="loading" class="memories-card__skeleton">
        <div v-for="index in 4" :key="index" class="skeleton-row" />
      </div>

      <div v-else-if="items.length" class="memories-list">
        <div
          v-for="item in items"
          :key="item.id"
          class="memory-item"
        >
          <span class="memory-item__badge" :class="`memory-item__badge--${item.category}`">
            {{ item.category_label || '其他' }}
          </span>
          <p class="memory-item__content">{{ item.content }}</p>
          <span class="memory-item__time">{{ formatDate(item.created_at) }}</span>
          <button
            type="button"
            class="memory-item__delete"
            :disabled="deletingId === item.id"
            @click="remove(item)"
          >
            {{ deletingId === item.id ? '删除中...' : '删除' }}
          </button>
        </div>
      </div>

      <div v-else class="memories-card__empty">
        <p>暂无持久记忆</p>
        <span>开启「全局持久记忆」后，问答中透露的偏好与背景会被自动记住</span>
      </div>

      <div v-if="total > perPage" class="memories-card__pagination">
        <button
          type="button"
          :disabled="page <= 1"
          @click="changePage(page - 1)"
        >
          ‹
        </button>
        <span>{{ page }} / {{ pages }}</span>
        <button
          type="button"
          :disabled="page >= pages"
          @click="changePage(page + 1)"
        >
          ›
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import ProfileTabs from '@/components/user/ProfileTabs.vue'
import { memoryAPI } from '@/api'

const items = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 10
const pages = ref(1)
const category = ref('')
const loading = ref(false)
const deletingId = ref(null)
const errorMessage = ref('')

const formatDate = (value) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

const load = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await memoryAPI.list({
      page: page.value,
      per_page: perPage,
      category: category.value
    })
    items.value = res.items || []
    total.value = res.total || 0
    pages.value = Math.max(1, Math.ceil(total.value / perPage))
  } catch (e) {
    errorMessage.value = e?.response?.data?.error || '加载记忆失败'
  } finally {
    loading.value = false
  }
}

const changePage = (next) => {
  page.value = next
  load()
}

const remove = async (item) => {
  deletingId.value = item.id
  try {
    await memoryAPI.remove(item.id)
    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await load()
  } catch (e) {
    errorMessage.value = e?.response?.data?.error || '删除失败'
  } finally {
    deletingId.value = null
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.memories-page {
  min-width: 0;
}

.memories-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
}

.memories-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #e2e8f0;

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #0f172a;
  }
}

.memories-card__sub {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #64748b;
}

.memories-card__select {
  height: 34px;
  padding: 0 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  color: #475569;
  font-size: 13px;
  background: #fff;
}

.memories-card__error {
  margin: 14px 20px 0;
  padding: 10px 12px;
  border: 1px solid #fecaca;
  border-radius: 7px;
  background: #fef2f2;
  color: #dc2626;
  font-size: 13px;
}

.memories-card__skeleton {
  padding: 20px;

  .skeleton-row {
    height: 56px;
    margin-bottom: 12px;
    border-radius: 8px;
    background: #f1f5f9;
    animation: skeleton 1.4s ease-in-out infinite alternate;
  }
}

@keyframes skeleton {
  from {
    opacity: 0.55;
  }
  to {
    opacity: 1;
  }
}

.memories-list {
  padding: 6px 20px;
}

.memory-item {
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 12px;
  padding: 14px 4px;
  border-bottom: 1px solid #eef2f7;

  &:last-child {
    border-bottom: 0;
  }
}

.memory-item__badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;

  &--preference {
    background: #dbeafe;
    color: #2563eb;
  }

  &--fact {
    background: #dcfce7;
    color: #16a34a;
  }

  &--decision {
    background: #fef9c3;
    color: #ca8a04;
  }

  &--goal {
    background: #ede9fe;
    color: #7c3aed;
  }

  &--other {
    background: #f1f5f9;
    color: #64748b;
  }
}

.memory-item__content {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.memory-item__time {
  color: #94a3b8;
  font-size: 11px;
  white-space: nowrap;
}

.memory-item__delete {
  padding: 5px 12px;
  border: 1px solid #fecaca;
  border-radius: 6px;
  background: #fff;
  color: #dc2626;
  font-size: 12px;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: #fef2f2;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.memories-card__empty {
  padding: 56px 20px;
  text-align: center;

  p {
    margin: 0 0 8px;
    color: #475569;
    font-size: 14px;
    font-weight: 600;
  }

  span {
    color: #94a3b8;
    font-size: 12px;
  }
}

.memories-card__pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 14px;
  border-top: 1px solid #eef2f7;

  button {
    width: 30px;
    height: 30px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #fff;
    color: #475569;
    cursor: pointer;

    &:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
  }

  span {
    color: #64748b;
    font-size: 12px;
  }
}

@media (max-width: 640px) {
  .memories-card__header {
    flex-direction: column;
  }

  .memory-item {
    grid-template-columns: auto 1fr auto;
  }

  .memory-item__time {
    display: none;
  }
}
</style>
