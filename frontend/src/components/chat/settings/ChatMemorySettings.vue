<template>
  <div class="settings-section">
    <h2>{{ t('memory.title') }}</h2>
    <p class="section-help">{{ t('memory.help') }}</p>

    <div class="memory-toggle">
      <div class="memory-toggle__info">
        <strong>{{ t('memory.enableLabel') }}</strong>
        <p>{{ t('memory.enableDesc') }}</p>
      </div>
      <label class="switch">
        <input
          type="checkbox"
          :checked="enabled"
          :disabled="savingToggle"
          @change="onToggle"
        >
        <span class="switch__slider" />
      </label>
    </div>

    <div v-if="items.length" class="memory-list">
      <div v-for="item in items" :key="item.id" class="memory-item">
        <span
          class="memory-item__badge"
          :class="`memory-item__badge--${item.category}`"
        >
          {{ item.category_label || '其他' }}
        </span>
        <p class="memory-item__content">{{ item.content }}</p>
        <div class="memory-item__ops">
          <button
            type="button"
            class="memory-item__btn"
            @click="openEdit(item)"
          >
            {{ t('memory.edit') }}
          </button>
          <button
            type="button"
            class="memory-item__btn memory-item__btn--danger"
            :disabled="deletingId === item.id"
            @click="remove(item)"
          >
            {{ deletingId === item.id ? '…' : t('memory.delete') }}
          </button>
        </div>
      </div>
      <button
        v-if="hasMore"
        type="button"
        class="memory-list__more"
        @click="loadNext"
      >
        {{ t('memory.loadMore') }}
      </button>
    </div>

    <div v-else-if="!loading" class="memory-empty">
      <p>{{ t('memory.empty') }}</p>
      <span>{{ t('memory.emptyHint') }}</span>
    </div>

    <div v-else class="memory-skeleton">
      <div v-for="index in 3" :key="index" class="memory-skeleton__row" />
    </div>

    <div class="memory-footer">
      <button type="button" class="memory-footer__add" @click="openCreate">
        {{ t('memory.add') }}
      </button>
      <RouterLink class="memory-footer__link" to="/user/memories">
        {{ t('memory.viewAll') }}
      </RouterLink>
    </div>

    <MemoryFormDialog
      v-model="formOpen"
      :memory="editing"
      @saved="reload"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authAPI, memoryAPI } from '@/api'
import { useI18n } from '@/features/chat/i18n'
import MemoryFormDialog from '@/components/user/MemoryFormDialog.vue'

const { t } = useI18n()

const enabled = ref(false)
const savingToggle = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const perPage = 20
const loading = ref(false)
const deletingId = ref(null)
const formOpen = ref(false)
const editing = ref(null)

const hasMore = () => items.value.length < total.value

const loadToggle = async () => {
  try {
    const res = await authAPI.getPreferences()
    enabled.value = Boolean(res?.preferences?.persistent_memory_enabled ?? res?.persistent_memory_enabled)
  } catch (e) {
    /* 忽略加载失败 */
  }
}

const onToggle = async (event) => {
  const next = event.target.checked
  savingToggle.value = true
  try {
    await authAPI.updatePreferences({ persistent_memory_enabled: next })
    enabled.value = next
  } catch (e) {
    enabled.value = !next
  } finally {
    savingToggle.value = false
  }
}

const load = async (nextPage) => {
  loading.value = true
  try {
    const res = await memoryAPI.list({
      page: nextPage,
      per_page: perPage
    })
    items.value = nextPage === 1 ? (res.items || []) : items.value.concat(res.items || [])
    total.value = res.total || 0
    page.value = nextPage
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || t('memory.loadFailed'))
  } finally {
    loading.value = false
  }
}

const reload = () => load(1)

const loadNext = () => load(page.value + 1)

const openCreate = () => {
  editing.value = null
  formOpen.value = true
}

const openEdit = (item) => {
  editing.value = item
  formOpen.value = true
}

const remove = async (item) => {
  deletingId.value = item.id
  try {
    await memoryAPI.remove(item.id)
    ElMessage.success(t('memory.deleted'))
    await reload()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || t('memory.deleteFailed'))
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  loadToggle()
  load(1)
})
</script>

<style scoped>
.settings-section h2 {
  margin: 0;
  font-size: 21px;
  color: var(--chat-ink);
}

.section-help {
  margin: 6px 0 22px;
  color: var(--chat-hollow);
  font-size: 13px;
}

.memory-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 10px;
  background: var(--chat-field);
  margin-bottom: 18px;
}

.memory-toggle__info {
  strong {
    color: var(--chat-ink);
    font-size: 14px;
  }

  p {
    margin: 6px 0 0;
    color: var(--chat-hollow);
    font-size: 12px;
    line-height: 1.6;
  }
}

.memory-list {
  border: 1px solid var(--chat-hairline);
  border-radius: 10px;
  overflow: hidden;
}

.memory-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--chat-hairline);

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
  color: var(--chat-muted);
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.memory-item__ops {
  display: flex;
  gap: 6px;
  white-space: nowrap;
}

.memory-item__btn {
  padding: 4px 10px;
  border: 1px solid var(--chat-hairline-strong);
  border-radius: 6px;
  background: var(--chat-field);
  color: var(--chat-muted);
  font-size: 12px;
  cursor: pointer;

  &:hover:not(:disabled) {
    color: var(--chat-accent);
    border-color: var(--chat-accent);
  }

  &--danger {
    color: #dc2626;
    border-color: var(--chat-hairline-strong);

    &:hover:not(:disabled) {
      background: #fef2f2;
      border-color: #fecaca;
    }
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.memory-list__more {
  display: block;
  width: 100%;
  padding: 10px;
  border: 0;
  border-top: 1px solid var(--chat-hairline);
  background: var(--chat-field);
  color: var(--chat-accent);
  font-size: 13px;
  cursor: pointer;

  &:hover {
    background: var(--chat-hover);
  }
}

.memory-empty {
  padding: 40px 16px;
  text-align: center;

  p {
    margin: 0 0 8px;
    color: var(--chat-muted);
    font-size: 14px;
    font-weight: 600;
  }

  span {
    color: var(--chat-hollow);
    font-size: 12px;
  }
}

.memory-skeleton {
  padding: 14px;

  &__row {
    height: 52px;
    margin-bottom: 10px;
    border-radius: 8px;
    background: var(--chat-hover);

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.memory-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
}

.memory-footer__add {
  padding: 7px 16px;
  border: 0;
  border-radius: 6px;
  background: var(--chat-accent);
  color: #fff;
  font-size: 13px;
  cursor: pointer;

  &:hover {
    filter: brightness(1.05);
  }
}

.memory-footer__link {
  color: var(--chat-accent);
  font-size: 13px;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}

.switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;

  input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  &__slider {
    position: absolute;
    inset: 0;
    border-radius: 999px;
    background: #cbd5e1;
    transition: background 0.3s ease;

    &::before {
      content: '';
      position: absolute;
      width: 18px;
      height: 18px;
      left: 3px;
      top: 3px;
      border-radius: 50%;
      background: #fff;
      transition: transform 0.3s ease;
    }
  }

  input:checked + &__slider {
    background: var(--chat-accent);
  }

  input:checked + &__slider::before {
    transform: translateX(20px);
  }

  input:disabled + &__slider {
    opacity: 0.6;
  }
}

@media (max-width: 620px) {
  .memory-item {
    grid-template-columns: auto 1fr;
  }

  .memory-item__ops {
    grid-column: 1 / -1;
    justify-self: end;
  }

  .memory-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .memory-footer__link {
    text-align: center;
  }
}
</style>
