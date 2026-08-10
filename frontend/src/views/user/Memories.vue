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
        <div class="memories-card__actions">
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
          <button
            type="button"
            class="memories-card__add"
            @click="openCreate"
          >
            新增记忆
          </button>
          <button
            type="button"
            class="memories-card__dream"
            :disabled="dreaming"
            @click="runDream"
          >
            {{ dreaming ? '整理中...' : '记忆整理' }}
          </button>
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
          <div class="memory-item__status">
            <span v-if="item.is_expired" class="memory-item__flag memory-item__flag--expired">已过期</span>
            <span v-if="item.suggest_delete" class="memory-item__flag memory-item__flag--suggest">建议删除</span>
          </div>
          <p class="memory-item__content">{{ item.content }}</p>
          <span class="memory-item__time">{{ formatDate(item.created_at) }}</span>
          <div class="memory-item__ops">
            <button
              type="button"
              class="memory-item__feedback"
              :disabled="feedbackId === item.id"
              @click="rate(item, 1)"
            >
              有用
            </button>
            <button
              type="button"
              class="memory-item__feedback"
              :disabled="feedbackId === item.id"
              @click="rate(item, 0)"
            >
              没用
            </button>
            <button
              type="button"
              class="memory-item__edit"
              @click="openEdit(item)"
            >
              编辑
            </button>
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
      </div>

      <div v-else class="memories-card__empty">
        <p>暂无持久记忆</p>
        <span>开启「全局持久记忆」后，问答中透露的偏好与背景会被自动记住，也可手动新增</span>
      </div>

      <div v-if="dreamAudits.length" class="dream-audits">
        <div class="dream-audits__title">记忆整理记录</div>
        <div v-for="audit in dreamAudits" :key="audit.id" class="dream-audit">
          <span class="dream-audit__action" :class="`dream-audit__action--${audit.action}`">
            {{ actionLabel(audit.action) }}
          </span>
          <span class="dream-audit__detail">{{ audit.detail }}</span>
          <span class="dream-audit__time">{{ formatDate(audit.created_at) }}</span>
        </div>
      </div>

      <MemoryFormDialog
        v-model="formOpen"
        :memory="editing"
        @saved="load"
      />

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
import MemoryFormDialog from '@/components/user/MemoryFormDialog.vue'
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
const formOpen = ref(false)
const editing = ref(null)

const openCreate = () => {
  editing.value = null
  formOpen.value = true
}

const openEdit = (item) => {
  editing.value = item
  formOpen.value = true
}

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

const feedbackId = ref(null)

const rate = async (item, rating) => {
  feedbackId.value = item.id
  try {
    await memoryAPI.feedback(item.id, rating)
    await load()
  } catch (e) {
    errorMessage.value = e?.response?.data?.error || '反馈提交失败'
  } finally {
    feedbackId.value = null
  }
}

const dreaming = ref(false)
const dreamAudits = ref([])

const actionLabel = (action) => ({
  merge: '合并',
  supersede: '取代',
  synthesize: '合成'
}[action] || action)

const runDream = async () => {
  dreaming.value = true
  errorMessage.value = ''
  try {
    const result = await memoryAPI.dream({ dry_run: false })
    if (result.operations > 0) {
      await load()
      await loadDreamAudits()
    }
    const summary = result.failures > 0
      ? `整理完成：${result.operations} 项操作，${result.failures} 项失败`
      : result.operations > 0
        ? `整理完成：${result.operations} 项操作（重复/碎片已合并或取代）`
        : '整理完成：暂无需要整合的记忆碎片'
    window.alert(summary)
  } catch (e) {
    errorMessage.value = e?.response?.data?.error || '记忆整理失败'
  } finally {
    dreaming.value = false
  }
}

const loadDreamAudits = async () => {
  try {
    const res = await memoryAPI.dreamAudits()
    dreamAudits.value = res.items || []
  } catch (e) {
    dreamAudits.value = []
  }
}

onMounted(() => {
  load()
  loadDreamAudits()
})
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

.memories-card__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.memories-card__add {
  padding: 7px 16px;
  border: 0;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  cursor: pointer;

  &:hover {
    background: #1d4ed8;
  }
}

.memories-card__dream {
  padding: 7px 16px;
  border: 1px solid #2563eb;
  border-radius: 6px;
  background: #fff;
  color: #2563eb;
  font-size: 13px;
  cursor: pointer;

  &:hover:not(:disabled) {
    background: #eff6ff;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.dream-audits {
  padding: 14px 20px 6px;
  border-top: 1px solid #eef2f7;

  &__title {
    margin-bottom: 8px;
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
  }
}

.dream-audit {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  font-size: 12px;

  &__action {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 999px;
    font-weight: 600;

    &--merge {
      background: #fef9c3;
      color: #ca8a04;
    }

    &--supersede {
      background: #ede9fe;
      color: #7c3aed;
    }

    &--synthesize {
      background: #dbeafe;
      color: #2563eb;
    }
  }

  &__detail {
    flex: 1;
    min-width: 0;
    color: #475569;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__time {
    flex-shrink: 0;
    color: #94a3b8;
  }
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
  grid-template-columns: auto auto 1fr auto auto;
  align-items: center;
  gap: 12px;
  padding: 14px 4px;
  border-bottom: 1px solid #eef2f7;
  &:last-child {
    border-bottom: 0;
  }
}

.memory-item__status {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.memory-item__flag {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;

  &--expired {
    background: #f1f5f9;
    color: #64748b;
  }

  &--suggest {
    background: #fee2e2;
    color: #dc2626;
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

.memory-item__ops {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.memory-item__feedback {
  padding: 5px 10px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;

  &:hover:not(:disabled) {
    border-color: #2563eb;
    color: #2563eb;
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.memory-item__edit {
  padding: 5px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  cursor: pointer;

  &:hover {
    background: #f8fafc;
  }
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

  .memory-item__status {
    grid-column: 1 / -1;
    flex-direction: row;
  }

  .memory-item__time {
    display: none;
  }

  .memory-item__ops {
    grid-column: 1 / -1;
    justify-self: end;
  }
}
</style>
